# 호스트 모델 검증 결과 - YOLOv8n int8 TFLite

> 본 문서는 호스트 Docker 컨테이너(Ryzen 7 + XNNPACK)에서 측정한 YOLOv8n int8 TFLite의 순수 inference latency를 기록합니다. 단일 책임 — 호스트 baseline 그 자체.

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
| 결론 | 호스트 baseline 확보 |

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
- 호스트 CPU 기준이라 다른 환경(UNO Q 등)에서는 다른 수치가 나옴 — 본 문서 범위 외

---

## 4. 알려진 한계

- **호스트 CPU 기준 측정** — 본 문서는 호스트 baseline만 다룸
- **더미 입력 (random uint8)** — 실제 이미지 사용 시 latency 영향 미미
- **XNNPACK delegate 자동 사용** — `tensorflow.lite`가 컨테이너에서 자동 활성화
- **단일 측정 1회** — 시간대/시스템 부하 차이 미반영

---

## 5. 빠른 참조

### 5-1. 측정 재실행

```bash
# 컨테이너 진입
cd /mnt/c/Project/unoq-companion-robot
bash run.sh

# 컨테이너 안에서
cd /work
python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite
```

### 5-2. JSON 저장

```bash
python src/validate_model.py \
  models/yolov8n_saved_model/yolov8n_int8.tflite \
  --json /work/benchmarks/host_validate_int8_$(date +%Y%m%d).json
```

### 5-3. 다른 변종 모델로 비교

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
| 2026-06-23 | 디바이스 비교/추정 섹션 제거 — 호스트 baseline 단일 책임 명확화 | 중복 정리 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 갱신 정책 | 호스트 환경/모델 변경 시 (디바이스 측정 변동은 본 문서와 무관) |
| 관련 스크립트 | `src/validate_model.py` |
| 관련 모델 | `models/yolov8n_saved_model/yolov8n_int8.tflite` (gitignored) |
