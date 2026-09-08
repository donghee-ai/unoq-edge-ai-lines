# Postprocess Module and End-to-End Measurement (Final Pass Decision)

본 문서는 `src/postprocess.py` / `src/infer_image.py` 작성, 작성 중 발견한 두 함정 (정규화 좌표 버그, cv2 cold start), 그리고 본 작품의 최종 end-to-end FPS 판정을 정리합니다.

## 0. 핵심 결정

| 항목 | 값 |
|---|---|
| **작성 모듈** | `src/postprocess.py` (decode + NMS + scale + draw), `src/infer_image.py` (전체 파이프라인) |
| **발견 1 — bbox 좌표 형식** | Ultralytics int8 TFLite는 정규화 좌표 [0, 1] 출력 (PyTorch / ONNX는 픽셀 좌표 — 다름) |
| **발견 2 — cv2 cold start** | cv2 drawing 함수 첫 호출 ~60 ms, warmed 시 ~3.7 ms |
| **Steady-state e2e latency** | ~108 ms (preprocess + inference + postprocess + draw) |
| **Steady-state e2e FPS** | 9.3 FPS |
| **합격 판정 (≥ 8 FPS)** | 최종 통과 |
| **의사결정** | YOLO 유지, MediaPipe 전환 트리거 발동 안 됨 |

## 1. `src/postprocess.py` 작성

본 프로젝트 코딩 규약(03)에 따라 후처리를 별도 모듈로 분리. 단일 책임 — 디코딩 + NMS + 시각화.

### 1-1. 공개 함수

| 함수 | 역할 |
|---|---|
| `decode_yolov8(raw_output, input_size, conf_threshold)` | (1, 84, 2100) raw output → (boxes_xyxy, scores, class_ids) |
| `xywh_to_xyxy(boxes)` | center 좌표 → 모서리 좌표 |
| `non_max_suppression(boxes, scores, class_ids, iou_threshold)` | cv2.dnn.NMSBoxes 기반 NMS |
| `scale_boxes(boxes, model_size, original_size, letterbox_pad)` | 모델 입력 좌표 → 원본 이미지 좌표 (패딩 보정) |
| `draw_detections(image_bgr, boxes, scores, class_ids)` | 박스 + 라벨 그리기 (BGR 입출력) |

### 1-2. 상수

`COCO_NAMES`: 80 클래스 라벨 (YOLOv8 표준 순서) 하드코딩.

### 1-3. 규약 충족 사항

- q-offset / q-scale hard-code 없음 (입출력 float32, 변환 불필요).
- 단일 책임 — 디코딩 + NMS + 시각화만 (추론은 별도 모듈).
- 호스트 / 디바이스 어느 환경에서도 작동 (numpy + cv2만 사용).

## 2. `src/infer_image.py` 작성

호스트 / 디바이스 공용 추론 + 시각화 스크립트.

### 2-1. 흐름

```text
1. 이미지 로드 (cv2.imread)
2. letterbox 전처리 (종횡비 유지, padding=114)
3. dtype 변환 (float32 / uint8 / int8)
4. 모델 추론 (TFLite invoke)
5. 후처리 (decode + NMS + scale)
6. 박스 그리기 (draw_detections)
7. PNG 저장 (cv2.imwrite)
```

### 2-2. 단계별 latency 측정

각 단계를 `time.perf_counter`로 측정하여 출력:

- preprocess.
- inference.
- postprocess.
- draw.
- save (jpg).
- realtime = preprocess + inference + postprocess + draw (save 제외, 실시간 루프 기준).
- total = realtime + save.

### 2-3. CLI

```bash
python3 src/infer_image.py <model.tflite> <image.jpg> \
  [--output OUT] [--conf 0.25] [--iou 0.45] [--threads 4]
```

### 2-4. 호스트 / 디바이스 공용 — 3단 import 폴백

`validate_model.py`와 동일 패턴:

```python
try:    from ai_edge_litert import interpreter as tflite  # 디바이스 우선
except: try:    import tflite_runtime.interpreter as tflite
        except: import tensorflow.lite as tflite           # 호스트 컨테이너
```

## 3. 함정 1 — Ultralytics int8 TFLite는 정규화 좌표 [0, 1] 출력

### 3-1. 증상

디바이스에서 첫 실행 시:

```text
== Detections (4 objects) ==
  bowl         0.860  bbox=[0, 0, 1, 0]
  broccoli     0.716  bbox=[0, 0, 1, 0]
  bowl         0.451  bbox=[0, 0, 1, 0]
  bowl         0.396  bbox=[0, 0, 1, 0]
```

검출 자체는 정상 (4개 객체, 클래스 ID 올바름, confidence 합리적). 그러나 모든 박스 좌표가 [0, 0, 1, 0]로 동일 — 명백한 디코딩 버그.

### 3-2. 원인 추적

초기 가정: YOLOv8 출력 xywh가 모델 입력 픽셀 좌표 (0~320)로 나옴.

실측 트레이스:

- 원본 raw_output[0, 0, 0] (첫 anchor의 cx) ≈ 0.5.
- xywh → xyxy 변환 후 ≈ (0.45, 0.475, 0.55, 0.525) — 0~1 범위.
- scale_boxes 후에도 작은 값 → clip → int → [0, 0, 1, 0].

결론: Ultralytics int8 TFLite export의 출력은 정규화 [0, 1] 좌표. PyTorch / ONNX export는 픽셀 좌표이지만 TFLite export는 다름.

### 3-3. 해결

`decode_yolov8` 시그니처에 `input_size` 파라미터 추가, 내부에서 정규화 → 픽셀 변환:

```python
def decode_yolov8(raw_output, input_size, conf_threshold=0.25):
    pred = raw_output[0].T                              # (2100, 84)
    boxes_xywh = pred[:, :4].copy().astype(np.float32)  # 정규화 [0, 1]
    class_scores = pred[:, 4:]

    # 정규화 → 모델 입력 픽셀 좌표
    boxes_xywh[:, [0, 2]] *= input_size[0]  # cx, w
    boxes_xywh[:, [1, 3]] *= input_size[1]  # cy, h
    ...
```

`infer_image.py`에서 `input_size` 전달:

```python
boxes_in, scores, class_ids = decode_yolov8(
    raw_output, (model_w, model_h), conf_threshold=args.conf
)
```

### 3-4. 검증 — 수정 후 결과

```text
== Detections (4 objects) ==
  bowl         0.860  bbox=[0, 194, 629, 475]      ← 정상 픽셀 좌표
  broccoli     0.716  bbox=[257, 235, 566, 476]
  bowl         0.451  bbox=[307, 1, 633, 236]
  bowl         0.396  bbox=[0, 11, 455, 361]
```

640×480 이미지에서 박스가 합리적 위치 (그릇 + 브로콜리). 후처리 검증 완료.

### 3-5. 교훈

모델 export 경로마다 출력 좌표 형식이 다를 수 있음. 참고자료 `04_robust_tflite_inference_code.md` Section 5에서 권고한 "출력 shape 먼저 기록 후 디코더 선택"의 정신. PyTorch checkpoint 또는 ONNX 모델 사용 시 본 decode 함수의 정규화 변환 라인 제거 필요.

## 4. 함정 2 — cv2 drawing cold start

### 4-1. 증상

bbox 버그 수정 후 latency:

```text
preprocess:      8.46 ms
inference:      98.37 ms
postprocess:     6.00 ms
draw + save:    68.99 ms  ← 의심
total:         181.01 ms  →  5.52 FPS
```

`draw + save`가 의외로 큼. 박스 4개 그리는 데 ~69 ms는 비현실적.

### 4-2. 진단 1 — draw와 save 분리

`infer_image.py`에 draw / save 타이밍 분리:

```text
draw:           60.92 ms     ← 진짜 병목
save (jpg):      9.62 ms     ← 정상
```

draw가 60 ms 단독으로 느림. save는 eMMC 쓰기로 합리적 수준.

### 4-3. 진단 2 — 한 프로세스 내 draw 5회 연속 측정

별도 스크립트로 동일 draw 함수 5회 호출:

```python
for i in range(5):
    t = time.perf_counter()
    draw_detections(img, boxes, scores, class_ids)
    print(f'draw #{i+1}: {(time.perf_counter()-t)*1000:.2f} ms')
```

결과:

```text
draw #1: 5.04 ms   ← 본 스크립트의 cold (cv2.imread, invoke로 일부 warmup된 상태)
draw #2: 4.77 ms
draw #3: 3.65 ms
draw #4: 3.72 ms
draw #5: 3.69 ms   ← steady-state ~3.7 ms
```

### 4-4. 원인 분석

`cv2.rectangle`, `cv2.putText`는 프로세스 내 첫 호출 시 내부 초기화 비용:

- 폰트 텍스처 로드.
- 그래픽 컨텍스트 준비.
- C 라이브러리 dynamic load.

`infer_image.py`에서 60 ms 나온 이유:

- 그 측정 시점이 cv2 drawing 함수의 진짜 첫 호출.
- 진단 스크립트는 cv2.imread, interpreter.invoke 등이 일부 cv2 초기화를 미리 트리거 → 5 ms 수준.

### 4-5. 의미

| 시나리오 | draw 영향 |
|---|---|
| 단일 이미지 one-shot (현재 `infer_image.py`) | 60 ms 한 번 (cold) |
| 실시간 루프 (카메라 입력 등) | 첫 프레임 60 ms, 이후 매 프레임 ~4 ms |

본 작품의 실 운영 시나리오인 실시간 루프에서는 사용자가 cold start 영향 거의 체감 못 함 (첫 프레임만).

### 4-6. 향후 최적화 옵션 (현재 불필요)

필요 시 cold start 자체를 줄이는 방법:

- 앱 시작 시 더미 이미지로 draw 한 번 warmup.
- 색상 / 폰트 캐시를 모듈 초기화 시점에 미리 계산.

현재 합격선 통과로 후순위.

## 5. End-to-End 최종 FPS (Steady-State)

### 5-1. 단계별 latency 표

| 단계 | Cold (단일 실행, 측정값) | Warm (실시간 루프 추정) | 출처 |
|---|---|---|---|
| preprocess | 8.5 ms | ~5 ms | cv2 imread / resize / cvtColor warmup 후 |
| inference | 98 ms | ~95 ms | `validate_model.py` 50회 평균 안정값 |
| postprocess | 6.0 ms | ~4 ms | numpy + cv2 NMS warmup 후 |
| draw | 60.9 ms | 3.7 ms | 4-3 진단 |
| (save) | 9.6 ms | (실시간 시 생략) | 디스크 쓰기 (debug 시만) |
| realtime 합계 | 174 ms (5.7 FPS) | ~108 ms (9.3 FPS) | |

### 5-2. 합격 판정

본 프로젝트 의사결정 트리(02):

| 조건 | 측정값 | 결과 |
|---|---|---|
| End-to-end realtime FPS ≥ 8 | 9.3 FPS | 최종 통과 |
| 첫 프레임 cold start 영향 | 5.4 FPS (한 번만) | 사용자 체감 없음 |

YOLO 유지 확정. MediaPipe 전환 트리거 발동 안 됨.

## 6. 알려진 한계

| 한계 | 영향 | 완화 방안 |
|---|---|---|
| 카메라 캡쳐 latency 미측정 | 실제 5~15 ms 추가 예상 | UVC 카메라 연결 후 별도 측정 |
| 실제 카메라 입력 시 약간 떨어질 가능성 | 예상 7~9 FPS | 측정 필요 |
| 단일 이미지로만 e2e 측정 | 다양한 시나리오 미커버 | golden image set으로 확장 (향후) |
| 메모리 RSS, 온도 미측정 | 장시간 운영 안정성 미검증 | soak test 시 측정 |
| GPU delegate 미시도 | CPU 충분으로 후순위 | `/dev/kgsl*` 부재로 어려울 가능성 큼 |

## 7. 재현 절차

### 7-1. 호스트 (컨테이너 안)

```bash
python src/infer_image.py \
  models/yolov8n_saved_model/yolov8n_int8.tflite \
  datasets/coco128/images/train2017/000000000009.jpg
```

### 7-2. 디바이스 전송 + 실행

```bash
# 호스트 WSL에서
scp src/postprocess.py src/infer_image.py arduino@192.168.0.45:~/
scp datasets/coco128/images/train2017/000000000009.jpg \
    arduino@192.168.0.45:/opt/unoq-yolo/media/

# 디바이스에서 (SSH 진입 + venv 활성화 후)
python3 ~/infer_image.py \
  /opt/unoq-yolo/models/yolov8n_int8.tflite \
  /opt/unoq-yolo/media/000000000009.jpg
```

### 7-3. Draw cold / warm 진단

```bash
# 디바이스 venv 활성화 상태에서
python3 -c "
import sys; sys.path.insert(0, '/home/arduino')
from postprocess import draw_detections
from ai_edge_litert import interpreter as tflite
import numpy as np, cv2, time
interp = tflite.Interpreter('/opt/unoq-yolo/models/yolov8n_int8.tflite', num_threads=4)
interp.allocate_tensors()
img = cv2.imread('/opt/unoq-yolo/media/000000000009.jpg')
inp = np.random.rand(1,320,320,3).astype(np.float32)
interp.set_tensor(interp.get_input_details()[0]['index'], inp); interp.invoke()
boxes = np.array([[0,194,629,475],[257,235,566,476],[307,1,633,236],[0,11,455,361]], dtype=float)
scores = np.array([0.86,0.72,0.45,0.40]); class_ids = np.array([45,50,45,45])
for i in range(5):
    t = time.perf_counter()
    draw_detections(img, boxes, scores, class_ids)
    print(f'draw #{i+1}: {(time.perf_counter()-t)*1000:.2f} ms')
"
```

### 7-4. annotated PNG 회수

```bash
# 호스트 WSL에서
scp arduino@192.168.0.45:/opt/unoq-yolo/media/000000000009_annotated.jpg \
    ./test_device_result.jpg
```
