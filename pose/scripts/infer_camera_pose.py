#!/usr/bin/env python3
"""실시간 카메라 + MoveNet Thunder INT8 추론 + HTTP serve.

vision/infer_camera.py 패턴 적용 + pose 라인 특화:
  - 모델: MoveNet Thunder INT8 (256×256 uint8 → [1,1,17,3] float32)
  - 후처리: keypoint 좌표 정규화 해제 + 좌/우 무릎 각도 (hip-knee-ankle)
  - 시각화: skeleton + 좌/우 무릎 각도 텍스트 + 스쿼트 depth state
  - HTTP serve: vision과 동일 패턴, stats 페이지에 CPU%/RAM/온도 추가

사용 (UNO Q SSH 모드):
  source ~/venv-unoq/bin/activate
  python3 ~/pose_test/scripts/infer_camera_pose.py \\
      ~/pose_test/models/movenet_thunder_int8.tflite \\
      --camera 0 --serve 8080
  → 브라우저: http://192.168.0.45:8080/
"""
import argparse
import http.server
import json
import os
import socketserver
import statistics
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import cv2

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

# 스쿼트 카운터 (같은 폴더의 모듈)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from squat_counter import SquatCounter, pick_angle


# === MoveNet 17 keypoint (COCO 17) ===
KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
KP = {n: i for i, n in enumerate(KP_NAMES)}

SKELETON = [
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 6),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
]


# === 각도 + depth state ===

def angle_3pt(a, b, c):
    """3개 2D 점 (y, x), 중심 b — 각도 0~180 deg."""
    ba = a - b
    bc = c - b
    cos = float(np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9))
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def knee_angle(kp, side, conf_th=0.3):
    """kp shape (17,3) (y_px, x_px, conf). side='left'|'right'.
    신뢰도 미달 시 None."""
    if side == "left":
        h, k, a = KP["left_hip"], KP["left_knee"], KP["left_ankle"]
    else:
        h, k, a = KP["right_hip"], KP["right_knee"], KP["right_ankle"]
    if min(kp[h, 2], kp[k, 2], kp[a, 2]) < conf_th:
        return None
    return angle_3pt(kp[h, :2], kp[k, :2], kp[a, :2])


def depth_state(angle):
    if angle is None:
        return "?"
    if angle >= 160:
        return "Standing"
    if angle >= 130:
        return "Quarter"
    if angle >= 95:
        return "Half"
    if angle >= 75:
        return "Parallel"
    return "ATG"


# === Preprocessing (letterbox 256 정사각) ===

def letterbox_square(image_bgr, target=256, pad_value=114):
    h, w = image_bgr.shape[:2]
    s = target / max(h, w)
    nh, nw = int(round(h * s)), int(round(w * s))
    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_t = (target - nh) // 2
    pad_l = (target - nw) // 2
    pad_b = target - nh - pad_t
    pad_r = target - nw - pad_l
    padded = cv2.copyMakeBorder(
        resized, pad_t, pad_b, pad_l, pad_r,
        cv2.BORDER_CONSTANT, value=(pad_value, pad_value, pad_value),
    )
    return padded, (pad_l, pad_t, s)


def unletterbox_kp(kp_norm, pad_info, target=256):
    """kp_norm shape (17,3) — (y_norm, x_norm, conf).
    → (y_orig_px, x_orig_px, conf)."""
    pad_l, pad_t, s = pad_info
    kp_out = kp_norm.copy().astype(np.float32)
    kp_out[:, 0] = (kp_norm[:, 0] * target - pad_t) / s   # y
    kp_out[:, 1] = (kp_norm[:, 1] * target - pad_l) / s   # x
    return kp_out


# === Draw ===

def draw_pose(image, kp_orig, conf_th=0.3, knee_angles=None):
    h, w = image.shape[:2]
    # skeleton
    for a, b in SKELETON:
        if kp_orig[a, 2] >= conf_th and kp_orig[b, 2] >= conf_th:
            pa = (int(kp_orig[a, 1]), int(kp_orig[a, 0]))
            pb = (int(kp_orig[b, 1]), int(kp_orig[b, 0]))
            cv2.line(image, pa, pb, (0, 255, 0), 2, cv2.LINE_AA)
    # keypoint dots
    for i in range(17):
        if kp_orig[i, 2] >= conf_th:
            p = (int(kp_orig[i, 1]), int(kp_orig[i, 0]))
            cv2.circle(image, p, 4, (0, 200, 255), -1)
    # knee angle highlight (3점 강조 + 각도 텍스트 keypoint 근처)
    if knee_angles:
        for side, ang in knee_angles.items():
            if ang is None:
                continue
            k_idx = KP[f"{side}_knee"]
            if kp_orig[k_idx, 2] >= conf_th:
                p = (int(kp_orig[k_idx, 1]), int(kp_orig[k_idx, 0]))
                cv2.circle(image, p, 8, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(image, f"{ang:.0f}",
                            (p[0] + 10, p[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 0, 255), 2, cv2.LINE_AA)
    return image


# === CPU% / RAM / 온도 ===

_last_cpu_t = None
_last_wall_t = None
_NUM_CORES = os.cpu_count() or 4


def get_cpu_pct_process():
    """프로세스 누적 CPU% (멀티코어, max ~= num_cores*100). 첫 호출 None."""
    global _last_cpu_t, _last_wall_t
    now_cpu = os.times()
    now_wall = time.perf_counter()
    if _last_cpu_t is None:
        _last_cpu_t = now_cpu
        _last_wall_t = now_wall
        return None
    cpu_used = (now_cpu.user - _last_cpu_t.user) + (now_cpu.system - _last_cpu_t.system)
    wall = now_wall - _last_wall_t
    pct = 100.0 * cpu_used / wall if wall > 0 else 0.0
    _last_cpu_t = now_cpu
    _last_wall_t = now_wall
    return pct


def get_rss_mb():
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return None
    return None


def get_max_temp_c():
    try:
        m = None
        for zone in sorted(Path('/sys/class/thermal').glob('thermal_zone*')):
            try:
                t = int((zone / 'temp').read_text().strip()) / 1000.0
                if m is None or t > m:
                    m = t
            except Exception:
                continue
        return m
    except Exception:
        return None


# === HTTP MJPEG serve ===

_state_lock = threading.Lock()
_latest_jpg = None
_latest_stats = {}


def update_live_state(annotated_bgr, stats_dict, q=70):
    global _latest_jpg, _latest_stats
    ok, buf = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
    if not ok:
        return
    with _state_lock:
        _latest_jpg = buf.tobytes()
        _latest_stats = dict(stats_dict)


def get_latest_jpg():
    with _state_lock:
        return _latest_jpg


def get_latest_stats():
    with _state_lock:
        return dict(_latest_stats)


_INDEX_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>UNO Q Pose Live</title>
<style>
body{font-family:system-ui,sans-serif;margin:16px;background:#1a1a1a;color:#ddd;}
h2{color:#4fc3f7;margin:0 0 12px;}
.layout{display:flex;gap:16px;flex-wrap:wrap;}
.stream{flex:1 1 640px;}
.stream img{width:100%;max-width:960px;border:1px solid #555;border-radius:4px;background:#000;}
.stats{flex:0 1 380px;}
pre{background:#000;color:#8bc34a;padding:12px;border-radius:4px;overflow:auto;font-size:12px;line-height:1.4;}
.warn{color:#ff7043;font-size:12px;margin-top:8px;}
.tag{display:inline-block;padding:2px 6px;background:#333;border-radius:3px;font-size:11px;color:#aaa;margin-right:4px;}
</style></head><body>
<h2>UNO Q MoveNet Thunder INT8 — Pose Live
<span class="tag">256x256</span><span class="tag">int8</span><span class="tag">XNNPACK</span></h2>
<div class="layout">
<div class="stream">
<img src="/stream.mjpg" alt="live">
<div class="warn">DEBUG ONLY. 인증 없음. 로컬 LAN 외부 노출 금지.</div>
</div>
<div class="stats"><pre id="stats">loading...</pre></div>
</div>
<script>
async function tick(){
  try{
    const r=await fetch('/stats.json',{cache:'no-store'});
    document.getElementById('stats').textContent=JSON.stringify(await r.json(),null,2);
  }catch(e){document.getElementById('stats').textContent='(stream lost: '+e.message+')';}
}
setInterval(tick,500);tick();
</script></body></html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            body = _INDEX_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/stats.json':
            data = json.dumps(get_latest_stats(), default=str).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    jpg = get_latest_jpg()
                    if jpg is None:
                        time.sleep(0.05)
                        continue
                    self.wfile.write(
                        b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                        + str(len(jpg)).encode() + b'\r\n\r\n'
                    )
                    self.wfile.write(jpg)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                    time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        else:
            self.send_response(404)
            self.end_headers()


class TServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="MoveNet Thunder INT8 TFLite 파일 경로")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--print-every", type=int, default=10)
    ap.add_argument("--serve", type=int, default=0,
                    help="HTTP MJPEG 포트. 0 = 비활성")
    ap.add_argument("--jpeg-quality", type=int, default=70)
    # 스쿼트 카운터
    ap.add_argument("--count", action="store_true",
                    help="스쿼트 rep 카운터 활성화 (90° 통과 사이클)")
    ap.add_argument("--side", choices=["left", "right", "avg", "better"], default="better",
                    help="카운터에 쓸 각도 선택 (기본 better: 둘 다 있으면 평균, 한쪽만 있으면 그쪽)")
    ap.add_argument("--down-th", type=float, default=100.0,
                    help="DOWN 진입 임계 (기본 100°)")
    ap.add_argument("--up-th", type=float, default=140.0,
                    help="UP 복귀 임계 (기본 140°)")
    ap.add_argument("--min-dwell-ms", type=float, default=200.0,
                    help="상태 전환 후 최소 유지 시간 (기본 200 ms — 떨림 방지)")
    args = ap.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")

    itp = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    itp.allocate_tensors()
    in_d = itp.get_input_details()[0]
    out_d = itp.get_output_details()[0]
    _, h_in, w_in, _ = (int(x) for x in in_d['shape'])
    assert h_in == w_in, f"expected square input, got {h_in}x{w_in}"

    print(f"== Pose live ({RUNTIME}) ==")
    print(f"  model:   {model_path}")
    print(f"  input:   {w_in}x{h_in} ({in_d['dtype'].__name__})")
    print(f"  camera:  /dev/video{args.camera} @ {args.width}x{args.height}")
    print(f"  threads: {args.threads}, conf_th: {args.conf}, cores: {_NUM_CORES}")
    if args.count:
        print(f"  squat:   ON  (side={args.side}, down<{args.down_th}, up>{args.up_th}, "
              f"dwell≥{args.min_dwell_ms}ms)")
    if args.serve:
        print(f"  serve:   http://<device-ip>:{args.serve}/  (DEBUG, no auth)")

    if args.serve:
        try:
            srv = TServer(('0.0.0.0', args.serve), Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            print(f"  [http]   started on port {args.serve}")
        except Exception as e:
            sys.exit(f"ERROR: failed to start HTTP server: {e}")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit(
            f"ERROR: cannot open camera /dev/video{args.camera}\n"
            f"  점검: ls /dev/video*  +  v4l2-ctl --list-devices"
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  actual:  {actual_w}x{actual_h}")

    # warmup CPU% accumulator
    get_cpu_pct_process()

    counter = SquatCounter(down_th=args.down_th, up_th=args.up_th,
                           min_dwell_ms=args.min_dwell_ms) if args.count else None

    loop_window = deque(maxlen=30)
    frame_idx = 0
    dropped = 0
    rss_peak = get_rss_mb() or 0.0
    temp_peak = get_max_temp_c() or 0.0
    cpu_peak = 0.0
    t_start = time.perf_counter()

    print(f"\n[run] start (Ctrl+C to stop)\n")

    try:
        while True:
            t0 = time.perf_counter()
            ret, frame_bgr = cap.read()
            if not ret or frame_bgr is None:
                dropped += 1
                time.sleep(0.05)
                continue
            t_cap = time.perf_counter()

            padded, pad_info = letterbox_square(frame_bgr, target=h_in, pad_value=114)
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            x = np.expand_dims(rgb.astype(np.uint8), 0)
            t_pre = time.perf_counter()

            itp.set_tensor(in_d['index'], x)
            itp.invoke()
            raw = itp.get_tensor(out_d['index'])  # [1, 1, 17, 3]
            t_inf = time.perf_counter()

            kp_norm = raw[0, 0]
            kp_orig = unletterbox_kp(kp_norm, pad_info, target=h_in)
            left = knee_angle(kp_orig, "left", conf_th=args.conf)
            right = knee_angle(kp_orig, "right", conf_th=args.conf)

            # 스쿼트 카운터 갱신 (옵션)
            rep_event = None
            if counter is not None:
                ang = pick_angle(left, right, mode=args.side)
                rep_event = counter.update(ang, now_ms=time.perf_counter() * 1000.0)
            t_post = time.perf_counter()

            annotated = frame_bgr.copy()
            draw_pose(annotated, kp_orig, conf_th=args.conf,
                      knee_angles={"left": left, "right": right})
            t_draw = time.perf_counter()

            ms_loop = (t_draw - t0) * 1000.0
            ms_cap = (t_cap - t0) * 1000.0
            ms_pre = (t_pre - t_cap) * 1000.0
            ms_inf = (t_inf - t_pre) * 1000.0
            ms_post = (t_post - t_inf) * 1000.0
            ms_draw = (t_draw - t_post) * 1000.0
            loop_window.append(ms_loop)
            avg = sum(loop_window) / len(loop_window)
            fps = 1000.0 / avg if avg > 0 else 0.0

            # 영상 위 오버레이 (좌상단 FPS + 좌하단 무릎 각도 큰 글자)
            cv2.putText(annotated, f"FPS {fps:.1f}  ({avg:.0f}ms)",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 0), 2, cv2.LINE_AA)
            y_text = actual_h - 50
            for side, ang in (("L", left), ("R", right)):
                txt = f"{side} knee: " + (f"{ang:.0f} deg ({depth_state(ang)})" if ang is not None else "?")
                cv2.putText(annotated, txt, (10, y_text),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (255, 255, 0), 2, cv2.LINE_AA)
                y_text += 28
            # 우상단 REPS 큰 글자
            if counter is not None:
                txt = f"REPS {counter.reps}  [{counter.state}]"
                color = (0, 255, 255) if rep_event else (200, 200, 200)
                cv2.putText(annotated, txt,
                            (actual_w - 280, 36),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
                if counter.last_rep_min_angle is not None:
                    cv2.putText(annotated, f"last min {counter.last_rep_min_angle:.0f}°",
                                (actual_w - 280, 64),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                (200, 200, 200), 1, cv2.LINE_AA)

            # 자원 모니터링
            rss = get_rss_mb()
            if rss and rss > rss_peak:
                rss_peak = rss
            temp = get_max_temp_c()
            if temp and temp > temp_peak:
                temp_peak = temp
            cpu = get_cpu_pct_process()
            if cpu and cpu > cpu_peak:
                cpu_peak = cpu

            frame_idx += 1

            if args.serve:
                live = {
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
                    "knee_angle_deg": {
                        "left": round(left, 1) if left is not None else None,
                        "right": round(right, 1) if right is not None else None,
                    },
                    "depth_state": {
                        "left": depth_state(left),
                        "right": depth_state(right),
                    },
                    "system": {
                        "cpu_pct_process": round(cpu, 1) if cpu is not None else None,
                        "cpu_pct_per_core_avg": round(cpu / _NUM_CORES, 1) if cpu is not None else None,
                        "cpu_peak_pct": round(cpu_peak, 1) if cpu_peak else None,
                        "rss_mb": round(rss, 1) if rss else None,
                        "rss_peak_mb": round(rss_peak, 1),
                        "temp_c_max": round(temp, 1) if temp else None,
                        "temp_peak_c": round(temp_peak, 1) if temp_peak else None,
                        "num_cores": _NUM_CORES,
                    },
                    "dropped_frames": dropped,
                    "camera_actual": [actual_w, actual_h],
                }
                if counter is not None:
                    live["squat"] = counter.snapshot()
                    if rep_event:
                        live["last_event"] = {
                            "type": rep_event[0],
                            "rep_total": rep_event[1],
                            "min_angle_deg": round(rep_event[2], 1),
                            "frame": frame_idx,
                        }
                update_live_state(annotated, live, q=args.jpeg_quality)

            if rep_event:
                print(f"  ★ REP #{rep_event[1]}  bottom={rep_event[2]:.0f}°  "
                      f"(state→{counter.state}, frame {frame_idx})")

            if frame_idx % args.print_every == 0:
                la = f"{left:.0f}" if left is not None else "?"
                ra = f"{right:.0f}" if right is not None else "?"
                cp = f"{cpu:.0f}" if cpu is not None else "?"
                rm = f"{rss:.0f}" if rss else "?"
                tp = f"{temp:.1f}" if temp else "?"
                reps_str = f"  reps={counter.reps:3d} [{counter.state}]" if counter is not None else ""
                print(f"[{frame_idx:5d}] fps={fps:5.2f}  "
                      f"L={la:>3s} R={ra:>3s} deg  "
                      f"cpu={cp:>4s}%  rss={rm:>4s}MB  temp={tp:>5s}C  "
                      f"(inf={ms_inf:6.2f}ms){reps_str}")

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break

    except KeyboardInterrupt:
        print("\n[stop] interrupted")

    finally:
        try:
            cap.release()
        except Exception:
            pass
        elapsed = time.perf_counter() - t_start
        print()
        print("=" * 64)
        print(f" SUMMARY  frames={frame_idx}  elapsed={elapsed:.1f}s")
        print(f"   fps_effective : {frame_idx / elapsed:.2f}")
        print(f"   dropped       : {dropped}")
        print(f"   cpu_peak_pct  : {cpu_peak:.1f} (per core avg {cpu_peak/_NUM_CORES:.1f})")
        print(f"   rss_peak_mb   : {rss_peak:.1f}")
        print(f"   temp_peak_c   : "
              + (f"{temp_peak:.1f}" if temp_peak else "n/a"))
        if counter is not None:
            snap = counter.snapshot()
            print(f"   squat_reps    : {snap['reps']}")
            print(f"   deepest_deg   : "
                  + (f"{snap['deepest_overall_deg']}" if snap['deepest_overall_deg'] is not None else "n/a"))
            print(f"   last_rep_min  : "
                  + (f"{snap['last_rep_min_deg']}" if snap['last_rep_min_deg'] is not None else "n/a"))
        print("=" * 64)


if __name__ == "__main__":
    main()
