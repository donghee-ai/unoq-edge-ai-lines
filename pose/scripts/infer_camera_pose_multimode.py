#!/usr/bin/env python3
"""Pose + KWS + Button 통합 — 모드 스위칭 인터럽트 지원.

기존 infer_camera_pose.py 확장 (원본 보존):
  - 카메라 pose 는 그대로 (MoveNet Thunder INT8)
  - `--enable-kws` : KWS worker daemon thread 로 음성 인터럽트
  - `--enable-button` : GPIO 버튼 watcher daemon thread 로 물리 인터럽트
  - 모드 4개: IDLE / SQUAT / PUSHUP / SURVEIL
    * IDLE    : skeleton overlay 만
    * SQUAT   : SquatCounter (기존)
    * PUSHUP  : PushupCounter (신규, 팔꿈치 각도)
    * SURVEIL : person detect + 좌표 로깅 (skeleton 만, 카운팅 없음)
  - HTTP serve JSON 에 mode/kws/button 필드 추가

사용 (UNO Q SSH):
  source ~/venv-unoq/bin/activate

  # A) KWS + button 모두 활성
  python3 ~/pose_test/scripts/infer_camera_pose_multimode.py \\
      ~/pose_test/models/movenet_thunder_int8.tflite \\
      --camera 0 --serve 8080 \\
      --enable-kws \\
      --kws-model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \\
      --kws-labels ~/kws_test/scripts/labels_12.txt \\
      --kws-preset ds_cnn \\
      --enable-button --gpio-line 17

  # B) KWS 만 (버튼 하드웨어 미준비)
  python3 ~/pose_test/scripts/infer_camera_pose_multimode.py \\
      ~/pose_test/models/movenet_thunder_int8.tflite \\
      --camera 0 --serve 8080 \\
      --enable-kws \\
      --kws-model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \\
      --kws-labels ~/kws_test/scripts/labels_12.txt \\
      --initial-mode SQUAT

  # C) 초기 모드 SQUAT + kws stop 감지 시 IDLE 로 → 인터럽트 데모
"""
import argparse
import http.server
import json
import os
import socketserver
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

# 같은 폴더 pose 모듈
sys.path.insert(0, str(Path(__file__).resolve().parent))
from squat_counter import SquatCounter, pick_angle
from pushup_counter import PushupCounter

# kws 모듈 (../../kws/scripts) — 진입 sys.path 확장
_KWS_DIR = Path(__file__).resolve().parent.parent.parent / "kws" / "scripts"
sys.path.insert(0, str(_KWS_DIR))
try:
    from mode_controller import Mode, ModeBus
    _HAS_MODE = True
except ImportError as e:
    _HAS_MODE = False
    print(f"[warn] mode_controller not found at {_KWS_DIR}: {e}")


# === MoveNet 17 keypoint (COCO 17) — infer_camera_pose.py 와 동일 ===
KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
KP = {n: i for i, n in enumerate(KP_NAMES)}

SKELETON = [
    (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 6), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
]


def angle_3pt(a, b, c):
    ba = a - b
    bc = c - b
    cos = float(np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9))
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def knee_angle(kp, side, conf_th=0.3):
    if side == "left":
        h, k, a = KP["left_hip"], KP["left_knee"], KP["left_ankle"]
    else:
        h, k, a = KP["right_hip"], KP["right_knee"], KP["right_ankle"]
    if min(kp[h, 2], kp[k, 2], kp[a, 2]) < conf_th:
        return None
    return angle_3pt(kp[h, :2], kp[k, :2], kp[a, :2])


def elbow_angle(kp, side, conf_th=0.3):
    """푸시업 rep 카운팅용 — shoulder→elbow→wrist."""
    if side == "left":
        s, e, w = KP["left_shoulder"], KP["left_elbow"], KP["left_wrist"]
    else:
        s, e, w = KP["right_shoulder"], KP["right_elbow"], KP["right_wrist"]
    if min(kp[s, 2], kp[e, 2], kp[w, 2]) < conf_th:
        return None
    return angle_3pt(kp[s, :2], kp[e, :2], kp[w, :2])


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
    pad_l, pad_t, s = pad_info
    kp_out = kp_norm.copy().astype(np.float32)
    kp_out[:, 0] = (kp_norm[:, 0] * target - pad_t) / s
    kp_out[:, 1] = (kp_norm[:, 1] * target - pad_l) / s
    return kp_out


def draw_pose(image, kp_orig, conf_th=0.3):
    for a, b in SKELETON:
        if kp_orig[a, 2] >= conf_th and kp_orig[b, 2] >= conf_th:
            pa = (int(kp_orig[a, 1]), int(kp_orig[a, 0]))
            pb = (int(kp_orig[b, 1]), int(kp_orig[b, 0]))
            cv2.line(image, pa, pb, (0, 255, 0), 2, cv2.LINE_AA)
    for i in range(17):
        if kp_orig[i, 2] >= conf_th:
            p = (int(kp_orig[i, 1]), int(kp_orig[i, 0]))
            cv2.circle(image, p, 4, (0, 200, 255), -1)
    return image


# === system stats — infer_camera_pose.py 와 동일 ===
_last_cpu_t = None
_last_wall_t = None
_NUM_CORES = os.cpu_count() or 4


def get_cpu_pct_process():
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


# === HTTP serve ===
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
<title>UNO Q Pose Multimode Live</title>
<style>
body{font-family:system-ui,sans-serif;margin:16px;background:#1a1a1a;color:#ddd;}
h2{color:#4fc3f7;margin:0 0 12px;}
.mode-badge{display:inline-block;padding:4px 10px;background:#ff9800;color:#000;border-radius:4px;font-weight:600;}
.layout{display:flex;gap:16px;flex-wrap:wrap;}
.stream{flex:1 1 640px;}
.stream img{width:100%;max-width:960px;border:1px solid #555;border-radius:4px;background:#000;}
.stats{flex:0 1 380px;}
pre{background:#000;color:#8bc34a;padding:12px;border-radius:4px;overflow:auto;font-size:12px;line-height:1.4;}
.tag{display:inline-block;padding:2px 6px;background:#333;border-radius:3px;font-size:11px;color:#aaa;margin-right:4px;}
</style></head><body>
<h2>UNO Q Pose + KWS Multimode Live
<span class="tag">Pose 256x256 int8</span><span class="tag">KWS int8</span><span class="tag">XNNPACK</span></h2>
<div class="layout">
<div class="stream">
<img src="/stream.mjpg" alt="live">
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


# === Mode-specific processing ===

def process_by_mode(
    mode, kp_orig, conf_th, squat_counter, pushup_counter, now_ms,
) -> dict:
    """모드에 맞는 카운터 update + 시각화 정보 반환."""
    out = {"mode": mode.value if _HAS_MODE else str(mode)}
    if not _HAS_MODE or mode == Mode.IDLE:
        return out

    if mode == Mode.SQUAT:
        left = knee_angle(kp_orig, "left", conf_th=conf_th)
        right = knee_angle(kp_orig, "right", conf_th=conf_th)
        ang = pick_angle(left, right, mode="better")
        ev = squat_counter.update(ang, now_ms=now_ms)
        out["left_knee"] = round(left, 1) if left is not None else None
        out["right_knee"] = round(right, 1) if right is not None else None
        out["counter"] = squat_counter.snapshot()
        out["rep_event"] = ev
        return out

    if mode == Mode.PUSHUP:
        left = elbow_angle(kp_orig, "left", conf_th=conf_th)
        right = elbow_angle(kp_orig, "right", conf_th=conf_th)
        ang = pick_angle(left, right, mode="better")
        ev = pushup_counter.update(ang, now_ms=now_ms)
        out["left_elbow"] = round(left, 1) if left is not None else None
        out["right_elbow"] = round(right, 1) if right is not None else None
        out["counter"] = pushup_counter.snapshot()
        out["rep_event"] = ev
        return out

    if mode == Mode.SURVEIL:
        # nose 좌표만 로그 (감시 위치 추적)
        nose = kp_orig[KP["nose"]]
        out["nose_conf"] = float(nose[2])
        if nose[2] >= conf_th:
            out["nose_pos"] = [int(nose[1]), int(nose[0])]
        return out

    return out


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
    ap.add_argument("--serve", type=int, default=0)
    ap.add_argument("--jpeg-quality", type=int, default=70)

    # 모드
    ap.add_argument("--initial-mode", choices=["IDLE", "SQUAT", "PUSHUP", "SURVEIL"],
                    default="IDLE")

    # SQUAT 임계 (기존과 동일)
    ap.add_argument("--squat-down-th", type=float, default=100.0)
    ap.add_argument("--squat-up-th", type=float, default=140.0)

    # PUSHUP 임계
    ap.add_argument("--pushup-down-th", type=float, default=90.0)
    ap.add_argument("--pushup-up-th", type=float, default=160.0)

    ap.add_argument("--min-dwell-ms", type=float, default=200.0)

    # KWS 인터럽트
    ap.add_argument("--enable-kws", action="store_true")
    ap.add_argument("--kws-model", default=None)
    ap.add_argument("--kws-labels", default=None)
    ap.add_argument("--kws-preset", choices=["ds_cnn", "micro_speech"], default="ds_cnn")
    ap.add_argument("--kws-conf", type=float, default=0.60)
    ap.add_argument("--kws-threads", type=int, default=1)
    ap.add_argument("--kws-hop-ms", type=float, default=200.0)
    ap.add_argument("--kws-device", type=int, default=None)

    # Button 인터럽트
    ap.add_argument("--enable-button", action="store_true")
    ap.add_argument("--gpio-chip", default="gpiochip0")
    ap.add_argument("--gpio-line", type=int, default=17)
    ap.add_argument("--gpio-active-high", action="store_true", default=True)
    ap.add_argument("--gpio-long-press-ms", type=float, default=1000.0)

    args = ap.parse_args()

    if not _HAS_MODE:
        sys.exit(
            "ERROR: mode_controller not importable.\n"
            f"  expected at: {_KWS_DIR}\n"
            "  kws/ 폴더 존재 확인 + PYTHONPATH 확인"
        )

    model_path = Path(args.model)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")

    itp = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    itp.allocate_tensors()
    in_d = itp.get_input_details()[0]
    out_d = itp.get_output_details()[0]
    _, h_in, w_in, _ = (int(x) for x in in_d['shape'])

    print(f"== Pose Multimode ({RUNTIME}) ==")
    print(f"  pose model:  {model_path}")
    print(f"  input:       {w_in}x{h_in} ({in_d['dtype'].__name__})")
    print(f"  camera:      /dev/video{args.camera} @ {args.width}x{args.height}")
    print(f"  initial:     {args.initial_mode}")
    print(f"  kws:         {'ON' if args.enable_kws else 'off'}")
    print(f"  button:      {'ON' if args.enable_button else 'off'}")

    # === ModeBus + workers ===
    bus = ModeBus(initial=Mode(args.initial_mode))

    kws_worker = None
    if args.enable_kws:
        if not args.kws_model or not args.kws_labels:
            sys.exit("ERROR: --enable-kws 시 --kws-model + --kws-labels 필수")
        from kws_worker import KWSWorker
        kws_worker = KWSWorker(
            model_path=args.kws_model,
            labels_path=args.kws_labels,
            preset_name=args.kws_preset,
            bus=bus,
            input_device=args.kws_device,
            threads=args.kws_threads,
            confidence_threshold=args.kws_conf,
            hop_ms=args.kws_hop_ms,
        )
        try:
            kws_worker.start()
            print(f"  [kws]        started ({args.kws_preset}, conf={args.kws_conf})")
        except Exception as e:
            print(f"  [kws]        FAILED to start: {e}")
            kws_worker = None

    button_watcher = None
    if args.enable_button:
        from button_watcher import ButtonWatcher
        button_watcher = ButtonWatcher(
            bus=bus,
            chip=args.gpio_chip,
            line=args.gpio_line,
            active_high=args.gpio_active_high,
            long_press_ms=args.gpio_long_press_ms,
        )
        try:
            button_watcher.start()
            print(f"  [button]     started (chip={args.gpio_chip} line={args.gpio_line})")
        except Exception as e:
            print(f"  [button]     FAILED to start: {e}")
            button_watcher = None

    # HTTP serve
    if args.serve:
        try:
            srv = TServer(('0.0.0.0', args.serve), Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            print(f"  [http]       http://<device-ip>:{args.serve}/  (DEBUG, no auth)")
        except Exception as e:
            sys.exit(f"ERROR: failed to start HTTP server: {e}")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit(
            f"ERROR: cannot open camera /dev/video{args.camera}\n"
            f"  점검: ls /dev/video* + v4l2-ctl --list-devices"
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    squat_counter = SquatCounter(
        down_th=args.squat_down_th, up_th=args.squat_up_th,
        min_dwell_ms=args.min_dwell_ms,
    )
    pushup_counter = PushupCounter(
        down_th=args.pushup_down_th, up_th=args.pushup_up_th,
        min_dwell_ms=args.min_dwell_ms,
    )

    get_cpu_pct_process()
    loop_window = deque(maxlen=30)
    frame_idx = 0
    dropped = 0
    rss_peak = get_rss_mb() or 0.0
    temp_peak = get_max_temp_c() or 0.0
    cpu_peak = 0.0
    t_start = time.perf_counter()

    last_mode = bus.get_mode()
    print(f"\n[run] start mode={last_mode.value} (Ctrl+C to stop)\n")

    try:
        while True:
            t0 = time.perf_counter()
            ret, frame_bgr = cap.read()
            if not ret or frame_bgr is None:
                dropped += 1
                time.sleep(0.05)
                continue

            # === Mode event poll (매 프레임) ===
            ev = bus.poll()
            if ev is not None:
                print(f"  ★ MODE EVENT  src={ev.source} label={ev.label} "
                      f"target={ev.target_mode.value if ev.target_mode else '(no change)'} "
                      f"conf={ev.confidence}")
                new_mode = bus.get_mode()
                if new_mode != last_mode:
                    # 모드 전환 시 카운터 리셋 여부 결정
                    if new_mode == Mode.SQUAT:
                        squat_counter = SquatCounter(
                            down_th=args.squat_down_th, up_th=args.squat_up_th,
                            min_dwell_ms=args.min_dwell_ms,
                        )
                    elif new_mode == Mode.PUSHUP:
                        pushup_counter = PushupCounter(
                            down_th=args.pushup_down_th, up_th=args.pushup_up_th,
                            min_dwell_ms=args.min_dwell_ms,
                        )
                    print(f"  ── mode {last_mode.value} → {new_mode.value}")
                    last_mode = new_mode

            padded, pad_info = letterbox_square(frame_bgr, target=h_in, pad_value=114)
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            x = np.expand_dims(rgb.astype(np.uint8), 0)

            itp.set_tensor(in_d['index'], x)
            itp.invoke()
            raw = itp.get_tensor(out_d['index'])
            kp_norm = raw[0, 0]
            kp_orig = unletterbox_kp(kp_norm, pad_info, target=h_in)

            now_ms = time.perf_counter() * 1000.0
            mode_out = process_by_mode(
                bus.get_mode(), kp_orig, args.conf,
                squat_counter, pushup_counter, now_ms,
            )

            # 시각화
            annotated = frame_bgr.copy()
            draw_pose(annotated, kp_orig, conf_th=args.conf)

            ms_loop = (time.perf_counter() - t0) * 1000.0
            loop_window.append(ms_loop)
            avg = sum(loop_window) / len(loop_window)
            fps = 1000.0 / avg if avg > 0 else 0.0

            # 오버레이
            cur = bus.get_mode()
            cv2.putText(annotated, f"FPS {fps:.1f}  ({avg:.0f}ms)",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(annotated, f"MODE: {cur.value}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (255, 165, 0), 2, cv2.LINE_AA)

            if "counter" in mode_out:
                snap = mode_out["counter"]
                cv2.putText(annotated, f"REPS {snap['reps']}  [{snap['state']}]",
                            (actual_w - 280, 36), cv2.FONT_HERSHEY_SIMPLEX,
                            0.9, (0, 255, 255), 2, cv2.LINE_AA)

            # KWS live label
            if kws_worker is not None:
                ksnap = kws_worker.snapshot()
                lbl = ksnap["stats"].get("last_label")
                conf = ksnap["stats"].get("last_confidence")
                if lbl:
                    text = f"KWS: {lbl}"
                    if conf is not None:
                        text += f" ({conf:.2f})"
                    cv2.putText(annotated, text, (10, actual_h - 20),
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
                    "mode": cur.value,
                    "mode_out": {k: v for k, v in mode_out.items() if k != "rep_event"},
                    "mode_bus": bus.snapshot(),
                    "system": {
                        "cpu_pct_process": round(cpu, 1) if cpu is not None else None,
                        "rss_mb": round(rss, 1) if rss else None,
                        "rss_peak_mb": round(rss_peak, 1),
                        "temp_c_max": round(temp, 1) if temp else None,
                        "temp_peak_c": round(temp_peak, 1) if temp_peak else None,
                    },
                    "dropped_frames": dropped,
                    "camera_actual": [actual_w, actual_h],
                }
                if kws_worker is not None:
                    live["kws"] = kws_worker.snapshot()
                if button_watcher is not None:
                    live["button"] = button_watcher.snapshot()
                update_live_state(annotated, live, q=args.jpeg_quality)

            # rep 이벤트 로그
            re = mode_out.get("rep_event")
            if re:
                print(f"  ★ REP #{re[1]}  bottom={re[2]:.0f}°  (mode={cur.value})")

            if frame_idx % args.print_every == 0:
                cp = f"{cpu:.0f}" if cpu is not None else "?"
                rm = f"{rss:.0f}" if rss else "?"
                tp = f"{temp:.1f}" if temp else "?"
                mode_str = f"[{cur.value}]"
                extra = ""
                if "counter" in mode_out:
                    snap = mode_out["counter"]
                    extra = f"  reps={snap['reps']} state={snap['state']}"
                print(f"[{frame_idx:5d}] fps={fps:5.2f}  cpu={cp:>4s}%  "
                      f"rss={rm:>4s}MB  temp={tp:>5s}C  {mode_str}{extra}")

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break

    except KeyboardInterrupt:
        print("\n[stop] interrupted")

    finally:
        if kws_worker is not None:
            kws_worker.stop()
        if button_watcher is not None:
            button_watcher.stop()
        try:
            cap.release()
        except Exception:
            pass

        elapsed = time.perf_counter() - t_start
        print()
        print("=" * 68)
        print(f" SUMMARY  frames={frame_idx}  elapsed={elapsed:.1f}s")
        print(f"   fps_effective : {frame_idx / elapsed:.2f}")
        print(f"   dropped       : {dropped}")
        print(f"   cpu_peak_pct  : {cpu_peak:.1f}")
        print(f"   rss_peak_mb   : {rss_peak:.1f}")
        print(f"   temp_peak_c   : {temp_peak:.1f}" if temp_peak else "   temp_peak_c   : n/a")
        print(f"   final_mode    : {bus.get_mode().value}")
        print(f"   mode_switches : {bus.snapshot()['stats']['mode_switches']}")
        if kws_worker is not None:
            ks = kws_worker.snapshot()["stats"]
            print(f"   kws_invokes   : {ks['invocations']}")
            print(f"   kws_detects   : {ks['detections']}")
        if button_watcher is not None:
            bs = button_watcher.snapshot()["stats"]
            print(f"   btn_short/long: {bs['short_press']} / {bs['long_press']}")
        print(f"   squat_reps    : {squat_counter.reps}")
        print(f"   pushup_reps   : {pushup_counter.reps}")
        print("=" * 68)


if __name__ == "__main__":
    main()
