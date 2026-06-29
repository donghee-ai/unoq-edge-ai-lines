#!/usr/bin/env python3
"""
실시간 카메라 입력 YOLOv8 추론 (호스트/디바이스 공용).

본 스크립트는 멘토 docs 06 권고 사항을 준수합니다:
  - 단계별 latency 측정 (preprocess / inference / postprocess / draw)
  - dropped_frames 카운트 (cap.read 실패)
  - 카메라 reconnect (연속 실패 N회 시 cap.release + 재오픈)
  - max_rss_mb, max_temp_c 모니터링 (benchmark_e2e.py 패턴)
  - 종료 시 멘토 06 Section 3 형식 JSON 저장 (--json 옵션)
  - Privacy: 영상 저장 default off, --save-dir opt-in

추가: --serve PORT 옵션으로 로컬 LAN에 MJPEG HTTP 스트림 + 통계 페이지 제공.
      ⚠️  DEBUG ONLY, 인증 없음. 외부 네트워크 노출 금지 (멘토 07 권고).

흐름:
  1. cv2.VideoCapture로 카메라 오픈
  2. 매 프레임:
     - 캡처 → letterbox → TFLite invoke → 후처리 → 박스 그리기
     - rolling FPS + 오버레이
     - (옵션) HTTP 서버 stream 위해 JPEG 인코딩 + shared state 갱신
  3. cap.read 실패 → dropped_frames++, 연속 N회 실패 시 reconnect 시도
  4. Ctrl+C 또는 'q' 키 → 종료 + 통계 출력 + (옵션) JSON 저장

사용:
  # 디바이스 SSH 헤드리스 (가장 단순):
  python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite \\
      --max-frames 200 --json ~/benchmarks/cam_$(date +%Y%m%d).json

  # 라이브 웹 디버그 (디바이스에서 실행 → 호스트 브라우저 접속):
  python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite --serve 8080
  # → 호스트 브라우저: http://192.168.0.45:8080/

  # 호스트 데스크탑 + 로컬 화면:
  python src/infer_camera.py models/yolov8n_saved_model/yolov8n_int8.tflite --display

  # 디바이스 디버그 (JPEG 저장):
  python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite \\
      --save-dir /tmp/unoq-yolo/cam-debug --save-every 30 --max-frames 100
"""

import argparse
import http.server
import io
import json
import socketserver
import statistics
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import cv2

# 같은 폴더의 postprocess 모듈
sys.path.insert(0, str(Path(__file__).resolve().parent))
from postprocess import (
    decode_yolov8,
    non_max_suppression,
    scale_boxes,
    draw_detections,
    COCO_NAMES,
)

# TFLite 런타임 3단 폴백
try:
    from ai_edge_litert import interpreter as tflite
    RUNTIME = "ai_edge_litert"
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        RUNTIME = "tflite_runtime"
    except ImportError:
        import tensorflow.lite as tflite
        RUNTIME = "tensorflow.lite"


# === 멘토 06 권고: RSS / 온도 피크 모니터링 ===

def get_rss_mb():
    """현재 프로세스의 RSS 메모리 (MB). 못 읽으면 None."""
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return None
    return None


def get_max_temp_c():
    """시스템 thermal zone의 max 온도 (°C). 못 읽으면 None (호스트 컨테이너 등)."""
    max_temp = None
    try:
        for zone in sorted(Path('/sys/class/thermal').glob('thermal_zone*')):
            try:
                temp_c = int((zone / 'temp').read_text().strip()) / 1000.0
                if max_temp is None or temp_c > max_temp:
                    max_temp = temp_c
            except Exception:
                continue
    except Exception:
        return None
    return max_temp


# === 통계 헬퍼 ===

def pct(arr, p):
    s = sorted(arr)
    return s[int(p * (len(s) - 1))]


def stats(arr):
    return {
        "mean": statistics.mean(arr),
        "median": statistics.median(arr),
        "p50": pct(arr, 0.50),
        "p95": pct(arr, 0.95),
        "min": min(arr),
        "max": max(arr),
    }


# === Preprocessing (infer_image.py / benchmark_e2e.py와 동일 패턴) ===

def letterbox(image_bgr, target_size, pad_value=114):
    """종횡비 유지 + padding. (left, top, right, bottom) 패딩 반환."""
    h0, w0 = image_bgr.shape[:2]
    tw, th = target_size
    scale = min(tw / w0, th / h0)
    nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_w, pad_h = tw - nw, th - nh
    left, top = pad_w // 2, pad_h // 2
    right, bottom = pad_w - left, pad_h - top
    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=(pad_value, pad_value, pad_value),
    )
    return padded, (left, top, right, bottom)


def prepare_input(rgb_image, dtype):
    if dtype == np.float32:
        x = rgb_image.astype(np.float32) / 255.0
    elif dtype == np.uint8:
        x = rgb_image.astype(np.uint8)
    elif dtype == np.int8:
        x = (rgb_image.astype(np.int16) - 128).clip(-128, 127).astype(np.int8)
    else:
        raise TypeError(f"Unsupported input dtype: {dtype}")
    return np.expand_dims(x, axis=0)


# === Camera reconnect ===

def open_camera(device, width, height):
    """카메라 오픈 + 해상도 설정. 실패 시 None."""
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


# === HTTP 라이브 스트리밍 (DEBUG ONLY — 인증 없음, 외부 노출 금지) ===

_state_lock = threading.Lock()
_latest_jpg = None          # bytes (JPEG)
_latest_stats = {}          # dict


def update_live_state(annotated_bgr, stats_dict, jpeg_quality=70):
    """메인 루프에서 매 프레임 후 호출. HTTP 핸들러가 읽을 최신 상태 갱신."""
    global _latest_jpg, _latest_stats
    ok, buf = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not ok:
        return
    jpg_bytes = buf.tobytes()
    with _state_lock:
        _latest_jpg = jpg_bytes
        _latest_stats = dict(stats_dict)


def get_latest_jpg():
    with _state_lock:
        return _latest_jpg


def get_latest_stats():
    with _state_lock:
        return dict(_latest_stats)


_INDEX_HTML = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><title>UNO Q YOLO live</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 16px; background: #1a1a1a; color: #ddd; }
  h2 { color: #4fc3f7; margin: 0 0 12px; }
  .layout { display: flex; gap: 16px; flex-wrap: wrap; }
  .stream { flex: 1 1 640px; }
  .stream img { width: 100%; max-width: 960px; border: 1px solid #555; border-radius: 4px; background: #000; }
  .stats { flex: 0 1 360px; }
  pre { background: #000; color: #8bc34a; padding: 12px; border-radius: 4px; overflow: auto; font-size: 12px; line-height: 1.4; }
  .warn { color: #ff7043; font-size: 12px; margin-top: 8px; }
</style></head>
<body>
<h2>UNO Q YOLO — Live Debug</h2>
<div class="layout">
  <div class="stream">
    <img src="/stream.mjpg" alt="live feed">
    <div class="warn">⚠ DEBUG ONLY. 인증 없음. 로컬 LAN 외부 노출 금지.</div>
  </div>
  <div class="stats">
    <pre id="stats">loading...</pre>
  </div>
</div>
<script>
async function tick() {
  try {
    const r = await fetch('/stats.json', { cache: 'no-store' });
    const data = await r.json();
    document.getElementById('stats').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('stats').textContent = '(stream lost: ' + e.message + ')';
  }
}
setInterval(tick, 500);
tick();
</script>
</body></html>
"""


class CameraStreamHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # 로그 억제 (메인 루프 콘솔 깔끔하게)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._serve_index()
        elif self.path == '/stream.mjpg':
            self._serve_mjpeg()
        elif self.path == '/stats.json':
            self._serve_stats()
        else:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()

    def _serve_index(self):
        body = _INDEX_HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def _serve_stats(self):
        data = json.dumps(get_latest_stats(), default=str).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def _serve_mjpeg(self):
        self.send_response(200)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()
        try:
            while True:
                jpg = get_latest_jpg()
                if jpg is None:
                    time.sleep(0.05)
                    continue
                header = (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(jpg)).encode() + b'\r\n\r\n'
                )
                self.wfile.write(header)
                self.wfile.write(jpg)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
                time.sleep(0.03)  # ~30 FPS cap (실제는 메인 루프 속도에 의존)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # 클라이언트 종료


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_http_server(port, bind='0.0.0.0'):
    server = ThreadedHTTPServer((bind, port), CameraStreamHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def main():
    ap = argparse.ArgumentParser(description="YOLOv8 실시간 카메라 추론 (멘토 06 권고 준수)")
    ap.add_argument("model", help=".tflite 파일 경로")
    ap.add_argument("--camera", type=int, default=0,
                    help="카메라 device index (기본 0 = /dev/video0)")
    ap.add_argument("--width", type=int, default=640, help="캡처 가로 해상도 (기본 640)")
    ap.add_argument("--height", type=int, default=480, help="캡처 세로 해상도 (기본 480)")
    ap.add_argument("--conf", type=float, default=0.25, help="confidence threshold (기본 0.25)")
    ap.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold (기본 0.45)")
    ap.add_argument("--threads", type=int, default=4, help="CPU 스레드 수 (기본 4)")
    ap.add_argument("--display", action="store_true",
                    help="cv2.imshow GUI 창 (Wayland/X11 필요. SSH 헤드리스에선 OFF)")
    ap.add_argument("--save-dir", default=None,
                    help="annotated JPEG 저장 디렉토리 (opt-in, 기본 OFF)")
    ap.add_argument("--save-every", type=int, default=30,
                    help="N 프레임마다 1장 저장 (기본 30)")
    ap.add_argument("--max-frames", type=int, default=0,
                    help="N 프레임 후 자동 종료 (0 = 무제한)")
    ap.add_argument("--print-every", type=int, default=10,
                    help="N 프레임마다 콘솔 로그 (기본 10)")
    ap.add_argument("--reconnect-after", type=int, default=5,
                    help="cap.read 연속 N회 실패 시 카메라 재오픈 (기본 5)")
    ap.add_argument("--json", default=None,
                    help="종료 시 멘토 06 형식 통계 JSON 저장 경로")
    ap.add_argument("--serve", type=int, default=0,
                    help="HTTP 라이브 스트리밍 포트 (예: 8080). 0 = 비활성. "
                         "⚠ DEBUG ONLY, 인증 없음. 로컬 LAN 외부 노출 금지")
    ap.add_argument("--jpeg-quality", type=int, default=70,
                    help="--serve 스트리밍 시 JPEG 품질 (기본 70)")
    args = ap.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")

    # === 모델 로드 ===
    interpreter = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    _, model_h, model_w, _ = (int(x) for x in input_detail['shape'])

    print("== Camera inference setup ==")
    print(f"  runtime:        {RUNTIME}")
    print(f"  model:          {model_path}")
    print(f"  input:          {model_w}x{model_h} ({input_detail['dtype'].__name__})")
    print(f"  camera:         /dev/video{args.camera} @ {args.width}x{args.height}")
    print(f"  conf / iou:     {args.conf} / {args.iou}")
    print(f"  threads:        {args.threads}")
    print(f"  display:        {args.display}")
    print(f"  reconnect@:     {args.reconnect_after} consecutive failures")
    if args.save_dir:
        print(f"  save_dir:       {args.save_dir} (every {args.save_every} frames)")
    if args.json:
        print(f"  json:           {args.json}")
    if args.serve:
        print(f"  serve:          http://<device-ip>:{args.serve}/  ⚠ DEBUG ONLY, no auth")

    # === HTTP 서버 시작 (옵션) ===
    if args.serve:
        try:
            start_http_server(args.serve)
            print(f"  [http] streaming on port {args.serve} (LAN only)")
        except Exception as e:
            sys.exit(f"ERROR: failed to start HTTP server on port {args.serve}: {e}")

    # === 카메라 오픈 ===
    cap = open_camera(args.camera, args.width, args.height)
    if cap is None:
        sys.exit(
            f"ERROR: cannot open camera /dev/video{args.camera}\n"
            f"  점검: ls /dev/video*  +  lsusb | grep -iE 'cam|video|uvc'"
        )
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  actual:         {actual_w}x{actual_h}")

    # === 저장 디렉토리 (opt-in) ===
    save_dir = None
    if args.save_dir:
        save_dir = Path(args.save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

    # === 단계별 latency 수집 (종료 시 통계) ===
    t_cap_list = []
    t_pre_list = []
    t_inf_list = []
    t_post_list = []
    t_draw_list = []
    t_loop_list = []

    # === Rolling FPS (최근 30프레임 이동평균) ===
    loop_window = deque(maxlen=30)

    # === 멘토 06 권고: 카운터 + 피크 모니터링 ===
    frame_idx = 0
    dropped_frames = 0
    consecutive_read_failures = 0
    reconnect_count = 0
    last_det_count = 0
    rss_peak = get_rss_mb() or 0
    temp_peak = get_max_temp_c() or 0

    t_start = time.perf_counter()

    print()
    print("[run] starting loop (Ctrl+C to stop" +
          (", or 'q' in window" if args.display else "") + ")")
    print()

    try:
        while True:
            t_loop = time.perf_counter()

            # === 1. 캡처 (실패 시 dropped_frames + reconnect) ===
            ret, frame_bgr = cap.read()
            t_cap = time.perf_counter()

            if not ret or frame_bgr is None:
                dropped_frames += 1
                consecutive_read_failures += 1
                if consecutive_read_failures >= args.reconnect_after:
                    print(f"[warn] {consecutive_read_failures} consecutive read failures "
                          f"→ reconnecting camera...", file=sys.stderr)
                    try:
                        cap.release()
                    except Exception:
                        pass
                    time.sleep(0.5)
                    new_cap = open_camera(args.camera, args.width, args.height)
                    if new_cap is not None:
                        cap = new_cap
                        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        reconnect_count += 1
                        consecutive_read_failures = 0
                        print(f"[ok] camera reconnected ({reconnect_count}x). "
                              f"actual={actual_w}x{actual_h}", file=sys.stderr)
                    else:
                        print(f"[err] reconnect failed, retrying in 2s...", file=sys.stderr)
                        time.sleep(2.0)
                else:
                    time.sleep(0.05)
                continue
            consecutive_read_failures = 0

            # === 2. Preprocess ===
            padded, pad = letterbox(frame_bgr, (model_w, model_h))
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            input_tensor = prepare_input(rgb, input_detail['dtype'])
            t_pre = time.perf_counter()

            # === 3. Inference ===
            interpreter.set_tensor(input_detail['index'], input_tensor)
            interpreter.invoke()
            raw_output = interpreter.get_tensor(output_detail['index'])
            t_inf = time.perf_counter()

            # === 4. Postprocess ===
            boxes_in, scores, class_ids = decode_yolov8(
                raw_output, (model_w, model_h), conf_threshold=args.conf
            )
            keep = non_max_suppression(boxes_in, scores, class_ids, iou_threshold=args.iou)
            boxes_in = boxes_in[keep]
            scores = scores[keep]
            class_ids = class_ids[keep]
            boxes_orig = scale_boxes(
                boxes_in, (model_w, model_h), (actual_w, actual_h), letterbox_pad=pad
            )
            t_post = time.perf_counter()

            # === 5. Draw ===
            annotated = draw_detections(frame_bgr, boxes_orig, scores, class_ids)
            t_draw = time.perf_counter()

            # === latency 누적 (단위 ms) ===
            ms_cap = (t_cap - t_loop) * 1000.0
            ms_pre = (t_pre - t_cap) * 1000.0
            ms_inf = (t_inf - t_pre) * 1000.0
            ms_post = (t_post - t_inf) * 1000.0
            ms_draw = (t_draw - t_post) * 1000.0
            ms_loop = (t_draw - t_loop) * 1000.0

            t_cap_list.append(ms_cap)
            t_pre_list.append(ms_pre)
            t_inf_list.append(ms_inf)
            t_post_list.append(ms_post)
            t_draw_list.append(ms_draw)
            t_loop_list.append(ms_loop)
            loop_window.append(ms_loop)
            last_det_count = len(scores)

            # === Rolling FPS + 오버레이 ===
            avg_ms = sum(loop_window) / len(loop_window)
            fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
            cv2.putText(
                annotated,
                f"FPS: {fps:.1f}  ({avg_ms:.1f} ms)",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            # === 피크 모니터링 ===
            rss = get_rss_mb()
            if rss and rss > rss_peak:
                rss_peak = rss
            temp = get_max_temp_c()
            if temp and temp > temp_peak:
                temp_peak = temp

            frame_idx += 1

            # === HTTP 라이브 스트림 갱신 (옵션) ===
            if args.serve:
                live_stats = {
                    "frame": frame_idx,
                    "fps": round(fps, 2),
                    "loop_ms": round(ms_loop, 2),
                    "stage_ms": {
                        "capture": round(ms_cap, 2),
                        "preprocess": round(ms_pre, 2),
                        "inference": round(ms_inf, 2),
                        "postprocess": round(ms_post, 2),
                        "draw": round(ms_draw, 2),
                    },
                    "detections": last_det_count,
                    "labels": [COCO_NAMES[int(c)] for c in class_ids[:10]],
                    "dropped_frames": dropped_frames,
                    "reconnect_count": reconnect_count,
                    "max_rss_mb": round(rss_peak, 1),
                    "max_temp_c": round(temp_peak, 1) if temp_peak else None,
                    "camera_actual": [actual_w, actual_h],
                }
                update_live_state(annotated, live_stats, jpeg_quality=args.jpeg_quality)

            # === Display (옵션) ===
            if args.display:
                cv2.imshow("UNO Q YOLO", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    print("[stop] key pressed")
                    break

            # === Save (opt-in 디버그) ===
            if save_dir and (frame_idx % args.save_every == 0):
                out_path = save_dir / f"frame_{frame_idx:06d}.jpg"
                cv2.imwrite(str(out_path), annotated)

            # === 콘솔 로그 ===
            if frame_idx % args.print_every == 0:
                names = ",".join(COCO_NAMES[int(c)] for c in class_ids[:3])
                more = "..." if len(class_ids) > 3 else ""
                print(
                    f"[{frame_idx:5d}] {len(boxes_orig):2d} dets "
                    f"({names}{more})  "
                    f"fps={fps:5.2f}  loop={ms_loop:6.2f}ms  "
                    f"(cap={ms_cap:5.1f} pre={ms_pre:4.1f} "
                    f"inf={ms_inf:6.2f} post={ms_post:4.1f} draw={ms_draw:4.1f})  "
                    f"drop={dropped_frames}"
                )

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                print(f"[stop] reached max-frames={args.max_frames}")
                break

    except KeyboardInterrupt:
        print("\n[stop] interrupted (Ctrl+C)")

    finally:
        elapsed = time.perf_counter() - t_start
        try:
            cap.release()
        except Exception:
            pass
        if args.display:
            cv2.destroyAllWindows()

        # === 통계 + 콘솔 요약 ===
        print()
        print("=" * 64)
        print(f" SUMMARY")
        print("=" * 64)
        print(f"  frames processed:     {frame_idx}")
        print(f"  dropped_frames:       {dropped_frames}")
        print(f"  reconnect_count:      {reconnect_count}")
        print(f"  elapsed:              {elapsed:.1f} s")
        print(f"  max_rss_mb:           {rss_peak:.1f}")
        print(f"  max_temp_c:           "
              + (f"{temp_peak:.1f}" if temp_peak else "n/a (no thermal zone)"))

        if frame_idx == 0:
            print("\n  (no frames processed — no stats)")
            return

        loop_s = stats(t_loop_list)
        cap_s = stats(t_cap_list)
        pre_s = stats(t_pre_list)
        inf_s = stats(t_inf_list)
        post_s = stats(t_post_list)
        draw_s = stats(t_draw_list)
        fps_mean = 1000.0 / loop_s['mean']

        print()
        print(f"  stage         mean      p50      p95      min      max     (ms)")
        print(f"  capture     {cap_s['mean']:7.2f}  {cap_s['p50']:7.2f}  {cap_s['p95']:7.2f}  {cap_s['min']:7.2f}  {cap_s['max']:7.2f}")
        print(f"  preprocess  {pre_s['mean']:7.2f}  {pre_s['p50']:7.2f}  {pre_s['p95']:7.2f}  {pre_s['min']:7.2f}  {pre_s['max']:7.2f}")
        print(f"  inference   {inf_s['mean']:7.2f}  {inf_s['p50']:7.2f}  {inf_s['p95']:7.2f}  {inf_s['min']:7.2f}  {inf_s['max']:7.2f}")
        print(f"  postprocess {post_s['mean']:7.2f}  {post_s['p50']:7.2f}  {post_s['p95']:7.2f}  {post_s['min']:7.2f}  {post_s['max']:7.2f}")
        print(f"  draw        {draw_s['mean']:7.2f}  {draw_s['p50']:7.2f}  {draw_s['p95']:7.2f}  {draw_s['min']:7.2f}  {draw_s['max']:7.2f}")
        print(f"  loop        {loop_s['mean']:7.2f}  {loop_s['p50']:7.2f}  {loop_s['p95']:7.2f}  {loop_s['min']:7.2f}  {loop_s['max']:7.2f}")
        print()
        print(f"  FPS mean (loop):      {fps_mean:.2f}")
        print(f"  FPS effective:        {frame_idx / elapsed:.2f}  (= frames / elapsed, includes drops)")
        print("=" * 64)

        # === JSON 저장 (멘토 06 Section 3 형식) ===
        if args.json:
            report = {
                # 멘토 06 표준 필드
                "model": str(model_path),
                "runtime": f"{RUNTIME}:{args.threads}",
                "input_shape": [int(x) for x in input_detail['shape']],
                "frames": frame_idx,
                "latency_ms_p50": loop_s['p50'],
                "latency_ms_p95": loop_s['p95'],
                "fps_mean": fps_mean,
                "preprocess_ms_mean": pre_s['mean'],
                "postprocess_ms_mean": post_s['mean'],
                "dropped_frames": dropped_frames,
                "max_rss_mb": round(rss_peak, 1),
                "max_temp_c": round(temp_peak, 1) if temp_peak else None,
                # 카메라 입력 추가 상세
                "capture_ms_mean": cap_s['mean'],
                "inference_ms_mean": inf_s['mean'],
                "draw_ms_mean": draw_s['mean'],
                "elapsed_s": round(elapsed, 2),
                "fps_effective": round(frame_idx / elapsed, 2),
                "reconnect_count": reconnect_count,
                "camera": {
                    "device": args.camera,
                    "requested": [args.width, args.height],
                    "actual": [actual_w, actual_h],
                },
                "stages": {
                    "capture": cap_s,
                    "preprocess": pre_s,
                    "inference": inf_s,
                    "postprocess": post_s,
                    "draw": draw_s,
                    "loop": loop_s,
                },
                "last_detections_count": last_det_count,
                "thresholds": {"conf": args.conf, "iou": args.iou},
            }
            out_path = Path(args.json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
            print(f"\n  JSON saved: {out_path}")


if __name__ == "__main__":
    main()
