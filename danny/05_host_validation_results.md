# 호스트 모델 검증 결과 - YOLOv8n int8 TFLite

> 본 문서는 STEP 3 (전송 전 모델 검증)의 호스트 CPU 측정 결과를 기록합니다.
> 향후 UNO Q 디바이스 측정 결과의 비교 baseline으로 사용됩니다.

---

## 결정 요약 (한 화면)

| 항목 | 값 |
|---|---|
| 측정 대상 모델 | `yolov8n_int8.tflite` (3.19 MB, 320×320, 양자화: w8a8 hybrid) |
| 측정 환경 | 호스트 도커 컨테이너 (Ubuntu 22.04, Python 3.10, TF 2.19.1) |
| CPU | AMD Ryzen 7 6800HS (Zen3+, 4스레드 활용) |
| Runtime | `tensorflow.lite` + XNNPACK delegate |
| Mean latency | **12.5 ms** |
| p50 / p95 | 12.2 ms / 15.0 ms |
| FPS (mean) | **79.96** |
| 결론 | 호스트 baseline 확보. UNO Q 실측 시 본 수치의 약 1/8~1/15 예상 (5~10 FPS) |

---

## 1. 측정 환경

### 1-1. 하드웨어

| 항목 | 값 |
|---|---|
| CPU | AMD Ryzen 7 6800HS with Radeon Graphics |
| 아키텍처 | Zen3+ (x86-64) |
| 사용 스레드 | 4 |
| RAM | (호스트 가용) |

### 1-2. 소프트웨어 스택

| 컴포넌트 | 버전 |
|---|---|
| OS (컨테이너) | Ubuntu 22.04 |
| Python | 3.10.12 |
| TensorFlow | 2.19.1 |
| TFLite Interpreter | `tensorflow.lite` (XNNPACK 자동 활성화) |
| Ultralytics | 8.4.75 (export 시점) |
| numpy | 1.26.4 |

전체 패키지 버전은 `requirements.lock` 참조.

### 1-3. 측정 도구

- 스크립트: `src/validate_model.py`
- 호출: `python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite`
- 절차: warmup 5회 → 측정 50회 (`time.perf_counter`)

---

## 2. 모델 메타데이터 (자동 추출)

### 2-1. Input

| 속성 | 값 |
|---|---|
| 이름 | `images` |
| Shape | `[1, 320, 320, 3]` |
| Dtype | `float32` |
| Quantization | `(0.0, 0)` (입력 텐서 자체는 비양자화) |
| Quantization params | `{'scales': [], 'zero_points': [], 'quantized_dimension': 0}` |

### 2-2. Output

| 속성 | 값 |
|---|---|
| 이름 | `Identity` |
| Shape | `[1, 84, 2100]` |
| Dtype | `float32` |
| Quantization | `(0.0, 0)` |
| Quantization params | `{'scales': [], 'zero_points': [], 'quantized_dimension': 0}` |

### 2-3. 출력 Shape 해석 — `[1, 84, 2100]`

- `1` = batch
- `84` = **4 (bbox: x_center, y_center, width, height) + 80 (COCO class score)**
- `2100` = anchor 개수 (320 입력 기준)
  - YOLOv8은 anchor-free + multi-scale: 40×40 + 20×20 + 10×10 = 2100
- 후처리 단계에서 (a) confidence threshold, (b) NMS, (c) coordinate scaling 필요

### 2-4. "Int8 모델인데 입출력이 float32"인 이유

Ultralytics int8 export의 표준 동작:
- **Weight는 int8 양자화** (모델 크기 12.7 MB → 3.19 MB, 약 4× 압축)
- **내부 op는 int8 산술**
- 입출력 텐서만 float32 (사용자 코드에서 quant/dequant 변환 불필요)

따라서 후처리 코드는 출력 텐서를 곧바로 float 연산으로 처리 가능.

---

## 3. Latency 측정 결과 (50회 반복)

| 통계 | 값 (ms) |
|---|---|
| min | 10.091 |
| max | 16.108 |
| mean | **12.506** |
| median | 12.290 |
| p50 | 12.227 |
| p95 | 14.980 |
| FPS (mean 역수) | **79.962** |

### 3-1. 분포 해석

- p95 / mean ≈ 1.20 — **분포 안정적**, 이상치 영향 작음
- min ~ p95 차이 약 5 ms — XNNPACK delegate가 일관된 성능 제공
- 호스트 CPU 자체의 thermal throttle 등 외부 요인 없음 (50회 짧은 측정)

### 3-2. FPS 의미

- 호스트에서 **약 80 FPS** = 실시간 비디오 (30 FPS) 대비 2.5× 여유
- 단, 이는 **호스트의 강력한 CPU 기준**이며 UNO Q에선 다름

---

## 4. UNO Q로의 변환 추정

### 4-1. CPU 성능 비교

| 항목 | 호스트 | UNO Q | 비율 |
|---|---|---|---|
| 아키텍처 | Zen3+ (Out-of-Order, 큰 SIMD) | Cortex-A53 (In-Order, 작은 SIMD) | — |
| 클럭 | ~3.2 GHz | 2.0 GHz | 1.6× |
| IPC | 높음 (현세대 데스크탑) | 낮음 (효율 코어) | ~3× |
| 종합 단일 스레드 추정 차이 | — | — | **약 5~10× 느림** |
| Thread count | 4 (호스트는 8 코어 16 스레드 중 4개) | 4 (전부) | — |
| **종합 예상** | — | — | **약 8~15× 느림** |

### 4-2. UNO Q 예상 수치

| 지표 | 호스트 실측 | UNO Q 추정 |
|---|---|---|
| latency mean (ms) | 12.5 | 100~190 |
| FPS mean | 80 | 5~10 |

### 4-3. 본 작품 시나리오에서의 의미

- 본 작품 합격선: **8 FPS 이상** (`01_model_selection_log.md`)
- UNO Q 추정 범위 (5~10 FPS) — **경계선**
- 실측 결과에 따라:
  - 8 FPS 이상 → YOLO 유지, 후속 단계 진행
  - 8 FPS 미만 → 최적화 (해상도 축소, frame skip) 또는 MediaPipe Face 전환 검토

---

## 5. 알려진 한계 및 후속 측정 계획

### 5-1. 본 측정의 한계
- **호스트 CPU 기준** — 디바이스 실측이 진실값
- **더미 입력 (random uint8)** — 실제 이미지 사용 시 약간 다를 수 있음 (정확도엔 영향, latency엔 미미)
- **XNNPACK delegate 자동 사용** — 디바이스에서도 동일한 delegate가 활성화되는지 확인 필요
- **단일 측정 1회** — 시간대/온도/시스템 부하 차이 미반영

### 5-2. UNO Q 측정 시 추가 수집할 데이터
- latency p50/p95/mean
- FPS mean
- **max RSS** (메모리 peak)
- **max temperature** (`/sys/class/thermal/...`에서 읽기)
- **dropped frames** (실제 비디오 입력 시)
- 추가: GPU delegate 시도 결과 (`benchmark_model --use_gpu=true`)

---

## 6. 빠른 참조

### 6-1. 측정 재실행
```bash
# 컨테이너 진입
cd /mnt/c/Project/unoq-companion-robot
bash run.sh

# 컨테이너 안에서
cd /work
python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite
```

### 6-2. JSON 저장 (멘토 보고용)
```bash
python src/validate_model.py \
  models/yolov8n_saved_model/yolov8n_int8.tflite \
  --json /work/benchmarks/host_validate_int8_$(date +%Y%m%d).json
```

(`benchmarks/` 폴더는 `.gitignore` 패턴 점검 후 git에 포함할지 결정. 현재는 미포함)

### 6-3. 다른 변종 모델로 비교
```bash
# float32 (양자화 없음, 정확도 기준선)
python src/validate_model.py models/yolov8n_saved_model/yolov8n_float32.tflite

# float16 (중간 옵션)
python src/validate_model.py models/yolov8n_saved_model/yolov8n_float16.tflite
```

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성, 호스트 baseline 12.5ms / 80 FPS 기록 | STEP 3 완료 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 다음 갱신 시점 | UNO Q 디바이스 실측 후 (Section 4-2 표 채움) |
| 관련 스크립트 | `src/validate_model.py` |
| 관련 모델 | `models/yolov8n_saved_model/yolov8n_int8.tflite` (gitignored) |
