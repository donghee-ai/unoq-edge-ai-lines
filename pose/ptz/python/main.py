"""PTZ PoC — UNO Q (Cortex-A53) Python 측.

검증 목적: pose 추적용 더 좋은 카메라 각도를 자동 탐색 가능한가?
가설 H1~H4: docs/08_ptz_camera_angle_validation.md

흐름:
  1. 카메라 캡처 (640×480 BGR)
  2. letterbox 256×256 uint8 → MoveNet Thunder INT8 invoke
  3. 17 keypoint (y, x, conf) → 사람 중심점 + visibility score (무릎 가중치 최대)
  4. should_track = visibility < THRESHOLD
  5. Arduino_RouterBridge로 STM32 측에 (person_x, person_y, visibility, should_track) 전달
  6. STM32 측 sketch.ino가 PID로 서보 회전 (should_track True일 때만)

기반:
  ShawnHymel/face-expression-detection-robot (MIT, 2025 Shawn Hymel)
  https://github.com/ShawnHymel/face-expression-detection-robot
  YOLO → MoveNet, bounding box → keypoint, expression → visibility로 교체.
"""

import base64
import gc
import threading
import time

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import cv2
import numpy as np
from ai_edge_litert import interpreter as tflite

# === Settings ===
MODEL_PATH = "movenet_thunder_int8.tflite"
CAMERA_INDEX = 0
TARGET_SIZE = 256                          # MoveNet Thunder input
CONF_TH = 0.3                              # keypoint conf threshold
VISIBILITY_TRACK_TH = 0.7                  # 이 미만이면 추적, 이상이면 STAY
TRACK_KP_WEIGHTS = {                       # visibility score 가중치 (무릎 최대)
    "left_knee": 1.0,  "right_knee": 1.0,
    "left_hip": 0.8,   "right_hip": 0.8,
    "left_ankle": 0.8, "right_ankle": 0.8,
    "left_shoulder": 0.5, "right_shoulder": 0.5,
    "nose": 0.3,
}
CENTER_KP_NAMES = [                        # 사람 중심점 산출용
    "left_shoulder", "right_shoulder",
    "left_hip", "right_hip",
]
WEB_UI_ENABLED = True
WEB_UI_FRAME_SKIP = 2
WEB_UI_JPEG_QUALITY = 50
INFERENCE_THREADS = 4

# === MoveNet 17 keypoint (COCO 17) ===
KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
KP = {n: i for i, n in enumerate(KP_NAMES)}
SKELETON = [
    (5, 7), (7, 9), (6, 8), (8, 10), (5, 6),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
]


# === Preprocessing ===

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
    """kp_norm shape (17,3): (y_norm, x_norm, conf) → 원본 픽셀 좌표."""
    pad_l, pad_t, s = pad_info
    kp = kp_norm.copy().astype(np.float32)
    kp[:, 0] = (kp_norm[:, 0] * target - pad_t) / s
    kp[:, 1] = (kp_norm[:, 1] * target - pad_l) / s
    return kp


# === Score / center 계산 ===

def visibility_score(kp, weights=TRACK_KP_WEIGHTS, conf_th=CONF_TH):
    """가중치 평균 confidence (0~1). conf 임계 미달은 0으로."""
    total_w = 0.0
    score = 0.0
    for name, w in weights.items():
        c = kp[KP[name], 2]
        if c >= conf_th:
            score += c * w
        total_w += w
    return score / total_w if total_w > 0 else 0.0


def person_center_normalized(kp, frame_h, frame_w, conf_th=CONF_TH):
    """어깨/엉덩이 좌표 평균 → frame 안 정규화 (0~1)."""
    valid = []
    for name in CENTER_KP_NAMES:
        idx = KP[name]
        if kp[idx, 2] >= conf_th:
            valid.append(kp[idx, :2])
    if not valid:
        return None, None
    yx = np.mean(valid, axis=0)
    y_norm = float(np.clip(yx[0] / frame_h, 0.0, 1.0))
    x_norm = float(np.clip(yx[1] / frame_w, 0.0, 1.0))
    return x_norm, y_norm


# === Draw ===

def draw_pose(image, kp, conf_th=CONF_TH, visibility=None, should_track=None):
    for a, b in SKELETON:
        if kp[a, 2] >= conf_th and kp[b, 2] >= conf_th:
            pa = (int(kp[a, 1]), int(kp[a, 0]))
            pb = (int(kp[b, 1]), int(kp[b, 0]))
            cv2.line(image, pa, pb, (0, 255, 0), 2, cv2.LINE_AA)
    for i in range(17):
        if kp[i, 2] >= conf_th:
            p = (int(kp[i, 1]), int(kp[i, 0]))
            cv2.circle(image, p, 4, (0, 200, 255), -1)
    # Overlay text
    if visibility is not None:
        txt = f"vis={visibility:.2f}"
        if should_track is not None:
            txt += "  TRACK" if should_track else "  STAY"
        color = (0, 255, 255) if should_track else (255, 255, 0)
        cv2.putText(image, txt, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return image


# === Inference loop ===

class PoseInference:
    def __init__(self, model_path, camera_index=0, target_size=256, threads=4):
        self.camera_index = camera_index
        self.target_size = target_size
        self.running = False
        self.capture = None
        self.thread = None
        self.frame_count = 0
        self.fps = 0.0
        self.actual_w = 0
        self.actual_h = 0
        self.last_visibility = 0.0
        self.last_should_track = False
        self.last_kp = None
        self.last_frame_annotated = None
        self.inference_time_ms = 0.0

        # TFLite Interpreter
        self.itp = tflite.Interpreter(model_path=model_path, num_threads=threads)
        self.itp.allocate_tensors()
        self.in_d = self.itp.get_input_details()[0]
        self.out_d = self.itp.get_output_details()[0]
        print(f"Model loaded: {model_path}")
        print(f"  input  : {list(self.in_d['shape'])} {self.in_d['dtype'].__name__}")
        print(f"  output : {list(self.out_d['shape'])} {self.out_d['dtype'].__name__}")

    def start(self):
        self.capture = cv2.VideoCapture(self.camera_index)
        if not self.capture.isOpened():
            print(f"ERROR: cannot open camera at {self.camera_index}")
            return False
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.actual_w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Camera native: {self.actual_w}x{self.actual_h}")
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.capture:
            self.capture.release()
        print("Inference stopped")

    def _loop(self):
        print("Inference loop start")
        fps_n = 0
        fps_t0 = time.time()
        gc_n = 0
        ui_n = 0

        while self.running:
            # FPS
            fps_n += 1
            now = time.time()
            if now - fps_t0 >= 1.0:
                self.fps = fps_n / (now - fps_t0)
                fps_n = 0
                fps_t0 = now

            # Capture
            self.capture.grab()
            ret, frame = self.capture.retrieve()
            if not ret:
                print("ERROR: capture failed")
                time.sleep(0.5)
                continue
            self.frame_count += 1

            # Preprocess
            padded, pad_info = letterbox_square(frame, target=self.target_size)
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            x = np.expand_dims(rgb.astype(np.uint8), 0)

            # Inference
            t0 = time.time()
            self.itp.set_tensor(self.in_d['index'], x)
            self.itp.invoke()
            raw = self.itp.get_tensor(self.out_d['index'])   # [1,1,17,3]
            self.inference_time_ms = (time.time() - t0) * 1000.0

            # Postprocess: keypoint orig + visibility + center
            kp_norm = raw[0, 0]
            kp = unletterbox_kp(kp_norm, pad_info, self.target_size)
            visibility = visibility_score(kp)
            should_track = visibility < VISIBILITY_TRACK_TH
            x_norm, y_norm = person_center_normalized(kp, self.actual_h, self.actual_w)

            self.last_kp = kp
            self.last_visibility = visibility
            self.last_should_track = should_track

            # Send to STM32 via RouterBridge (Shawn pattern)
            # 사람 검출 시에만 STM32에 좌표 전송
            if x_norm is not None and y_norm is not None:
                try:
                    Bridge.call("track_pose", x_norm, y_norm, visibility, should_track)
                except Exception as e:
                    print(f"Bridge.call error: {e}")

            # Web UI
            if WEB_UI_ENABLED:
                ui_n += 1
                if ui_n >= WEB_UI_FRAME_SKIP:
                    self._update_web_ui(frame, kp, visibility, should_track)
                    ui_n = 0

            # Cleanup
            del padded, rgb, x, raw
            gc_n += 1
            if gc_n >= 30:
                gc.collect()
                gc_n = 0
            time.sleep(0.05)

    def _update_web_ui(self, frame, kp, visibility, should_track):
        annotated = frame.copy()
        draw_pose(annotated, kp, visibility=visibility, should_track=should_track)
        ok, buf = cv2.imencode('.jpg', annotated, [
            cv2.IMWRITE_JPEG_QUALITY, WEB_UI_JPEG_QUALITY,
            cv2.IMWRITE_JPEG_OPTIMIZE, 1,
        ])
        if not ok:
            return
        b64 = base64.b64encode(buf).decode('utf-8')
        try:
            ui.send_message('pose_frame', {
                'image': b64,
                'fps': round(self.fps, 1),
                'inference_time_ms': round(self.inference_time_ms, 1),
                'visibility': round(visibility, 3),
                'should_track': bool(should_track),
                'visibility_track_th': VISIBILITY_TRACK_TH,
            })
        except Exception as e:
            print(f"UI send error: {e}")
        finally:
            del buf, annotated, b64


# === Main ===
ui = WebUI()
inference = PoseInference(
    model_path=MODEL_PATH,
    camera_index=CAMERA_INDEX,
    target_size=TARGET_SIZE,
    threads=INFERENCE_THREADS,
)
if not inference.start():
    print("ERROR: failed to start inference")
App.run()
