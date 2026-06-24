# Initial Inference Measurement — Host Baseline and Device First Run

본 문서는 YOLOv8n int8 TFLite의 순수 inference latency를 호스트 Docker 컨테이너와 UNO Q 디바이스 양쪽에서 측정한 첫 결과를 통합 기록합니다. 두 환경 모두 `src/validate_model.py`로 측정 (warmup → 50회 반복) → 호스트 baseline 확보 + 디바이스 잠정 합격 판정.

## 0. 핵심 결정

| 항목 | 내용 |
|---|---|
| **측정 도구** | `src/validate_model.py` (호스트/디바이스 공용) |
| **측정 모델** | `yolov8n_int8.tflite` (3.19 MB, 320×320, w8a8 hybrid) |
| **호스트 결과** | mean 12.5 ms / FPS 79.96 (Ryzen 7 6800HS, tensorflow.lite + XNNPACK) |
| **디바이스 결과** | mean 101.3 ms / FPS 9.88 (Cortex-A53 ×4, ai_edge_litert + XNNPACK) |
| **합격선 (FPS ≥ 8)** | 통과 (순수 inference 기준, 잠정) |
| **종합 결론** | 호스트 baseline 확보 + 디바이스 첫 측정 합격선 통과. e2e / 공식 벤치는 별도 문서(07) |

## 1. 모델 메타데이터 (자동 추출, 호스트/디바이스 동일)

`get_input_details()` / `get_output_details()`로 두 환경에서 동일 결과 확인.

### 1-1. Input

| 속성 | 값 |
|---|---|
| 이름 | `images` |
| Shape | `[1, 320, 320, 3]` |
| Dtype | `float32` |
| Quantization | `(0.0, 0)` (입력 텐서 자체는 비양자화) |
| Quantization params | `{'scales': [], 'zero_points': [], 'quantized_dimension': 0}` |

### 1-2. Output

| 속성 | 값 |
|---|---|
| 이름 | `Identity` |
| Shape | `[1, 84, 2100]` |
| Dtype | `float32` |
| Quantization | `(0.0, 0)` |
| Quantization params | `{'scales': [], 'zero_points': [], 'quantized_dimension': 0}` |

### 1-3. 출력 Shape 해석 — `[1, 84, 2100]`

- `1` = batch.
- `84` = 4 (bbox: x_center, y_center, width, height) + 80 (COCO class score).
- `2100` = anchor 개수 (320 입력 기준). YOLOv8은 anchor-free + multi-scale: 40×40 + 20×20 + 10×10 = 2100.
- 후처리 단계에서 (a) confidence threshold, (b) NMS, (c) coordinate scaling 필요.

### 1-4. int8 모델인데 입출력이 float32인 이유

Ultralytics int8 export의 표준 동작:

- Weight는 int8 양자화 (모델 크기 12.7 MB → 3.19 MB, 약 4× 압축).
- 내부 op는 int8 산술.
- 입출력 텐서만 float32 (사용자 코드에서 quant/dequant 변환 불필요).

따라서 후처리 코드는 출력 텐서를 곧바로 float 연산으로 처리 가능.

## 2. 측정 도구 — `src/validate_model.py`

- 절차: warmup → 측정 N회 반복 (`time.perf_counter`).
- 호출 예 (호스트): `python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite`
- 호출 예 (디바이스): `python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite`
- 호스트 측 warmup 5 + 측정 50회 / 디바이스 측 warmup 5 + 측정 50회.

## 3. 호스트 baseline 결과

### 3-1. 측정 환경

| 항목 | 값 |
|---|---|
| CPU | AMD Ryzen 7 6800HS with Radeon Graphics |
| 아키텍처 | Zen3+ (x86-64) |
| 사용 스레드 | 4 |
| OS (컨테이너) | Ubuntu 22.04 |
| Python | 3.10.12 |
| TensorFlow | 2.19.1 |
| TFLite Interpreter | `tensorflow.lite` (XNNPACK 자동 활성화) |
| Ultralytics | 8.4.75 (export 시점) |
| numpy | 1.26.4 |

전체 패키지 버전은 `requirements.lock` 참조.

### 3-2. Latency 측정 (50회)

| 통계 | 값 (ms) |
|---|---|
| min | 10.091 |
| max | 16.108 |
| mean | 12.506 |
| median | 12.290 |
| p50 | 12.227 |
| p95 | 14.980 |
| FPS (mean 역수) | 79.962 |

### 3-3. 분포 해석

- p95 / mean ≈ 1.20 — 분포 안정적, 이상치 영향 작음.
- min ~ p95 차이 약 5 ms — XNNPACK delegate가 일관된 성능 제공.
- 호스트 CPU 자체의 thermal throttle 등 외부 요인 없음 (50회 짧은 측정).
- 호스트에서 약 80 FPS = 실시간 비디오 (30 FPS) 대비 2.5× 여유.

## 4. 디바이스 첫 측정 결과

### 4-1. 측정 환경

| 항목 | 값 |
|---|---|
| Hostname | unoq-korea01 |
| SoC | QRB2210 (soc_id 524) |
| CPU | Cortex-A53 ×4 @ 2.0 GHz |
| RAM (가용) | 2.4 GiB (전체 3.6 GiB) |
| Storage | 2.9 GB free (9.8 GB total) |
| OS | Debian (Linux 7.0.0-g122c2c22d838) |
| Python | 3.13.5 |
| 가상환경 | `~/venv-unoq` |
| Runtime | `ai_edge_litert` 2.1.5 |
| Numpy | 2.5.0 (디바이스 측, 호스트 1.26.4와 다른 버전이지만 모델 결과 동일) |
| Delegate | XNNPACK (CPU 자동) |
| Threads | 4 |

### 4-2. 디바이스 셋업 절차 (1회)

`scripts/setup_device.sh` 또는 수동:

```bash
# 디바이스 SSH 셸 안에서
sudo apt update && sudo apt install -y python3-pip python3-venv
python3 -m venv ~/venv-unoq
source ~/venv-unoq/bin/activate
pip install --upgrade pip
pip install ai-edge-litert numpy
sudo mkdir -p /opt/unoq-yolo/{models,labels,media,configs,logs}
sudo chown -R arduino:arduino /opt/unoq-yolo
```

설치된 패키지: ai-edge-litert 2.1.5, numpy 2.5.0, 부수(tqdm, protobuf, flatbuffers, backports.strenum, typing-extensions).

### 4-3. 파일 전송 + 측정 실행

```bash
# 호스트 WSL에서 디바이스로 전송
cd /mnt/c/Project/unoq-companion-robot
scp models/yolov8n_saved_model/yolov8n_int8.tflite arduino@192.168.0.45:/opt/unoq-yolo/models/
scp src/validate_model.py arduino@192.168.0.45:~/

# 디바이스 SSH 셸 안에서 측정
source ~/venv-unoq/bin/activate
python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite
```

소요: 약 30초 (모델 로드 + warmup 5 + 측정 50회).

### 4-4. Latency 측정 (50회)

| 통계 | 값 (ms) |
|---|---|
| min | 87.748 |
| max | 163.091 |
| mean | 101.268 |
| median | 94.028 |
| p50 | 94.027 |
| p95 | 129.063 |
| FPS mean | 9.875 |

### 4-5. 분포 해석

- p95 / mean ≈ 1.27 — 임베디드 시스템 백그라운드 작업 / 스케줄링 영향.
- min ~ p95 약 41 ms 차이 — 가끔 느린 프레임 있음, 그러나 평균은 안정.
- median 94 ms vs mean 101 ms — 우측 꼬리(가끔 느린 측정) 있음, 정상 분포.
- 9.88 FPS = 약 100 ms 주기로 검출. 인간 인지 임계점(100 ms) 경계선. 책상 위 교감로봇 시나리오에서 자연스러운 인터랙션 가능 수준.

## 5. 호스트 vs 디바이스 비교

### 5-1. Latency 비율

| 지표 | 호스트 (Ryzen 7) | UNO Q (Cortex-A53) | 디바이스 / 호스트 비율 |
|---|---|---|---|
| latency min (ms) | 10.09 | 87.75 | 8.7× |
| latency mean (ms) | 12.51 | 101.27 | 8.1× |
| latency p50 (ms) | 12.23 | 94.03 | 7.7× |
| latency p95 (ms) | 14.98 | 129.06 | 8.6× |
| latency max (ms) | 16.11 | 163.09 | 10.1× |
| FPS mean | 79.96 | 9.88 | 1/8.1 |

### 5-2. 비율 해석

- inference 약 8.1× 느림. CPU 아키텍처 차이 (Zen3+ Out-of-Order, 큰 SIMD vs Cortex-A53 In-Order, 작은 SIMD).
- XNNPACK delegate가 ARM NEON 잘 활용하고 있다는 신호 — Cortex-A53급 치고는 좋은 결과.
- 공식 100회 + 단계별 e2e 종합 비교는 문서 07 (공식 벤치마크) 참조.

## 6. 합격 판정 — 트리거 평가 (잠정)

본 프로젝트 의사결정 트리(02 모델 선택):

| 조건 | 실측 (순수 inference) | 액션 |
|---|---|---|
| FPS ≥ 8 | 9.88 ≥ 8 | YOLO 유지 (잠정) |
| FPS < 8 | — | (해당 없음) 최적화 또는 MediaPipe 전환 |

### 6-1. 본 판정의 범위 — 순수 inference만 측정

본 9.88 FPS는 `interpreter.invoke()` 단독 측정. 다음 단계들은 포함되지 않음:

- 카메라 캡쳐.
- 이미지 → 텐서 전처리 (resize, BGR→RGB, dtype 변환).
- raw output → bbox 디코딩 + NMS.
- 좌표 스케일링, 라벨 매핑.
- 결과 표시 / 저장.

end-to-end (위 단계들 포함) 시 추가 비용 예상:

| 추가 단계 | UNO Q 예상 추가 시간 |
|---|---|
| 카메라 캡쳐 (UVC 30fps) | 5~15 ms |
| 전처리 (cv2 resize + dtype) | 3~8 ms |
| 후처리 (NMS, scaling, mapping) | 5~15 ms |
| 합계 추가 | 약 13~38 ms |
| end-to-end latency 추정 | 약 115~140 ms |
| end-to-end FPS 추정 | 약 7.1~8.7 |

### 6-2. 결론 — 순수 inference 합격, e2e는 별도 측정

- 본 문서 범위: 순수 inference 합격선 통과.
- end-to-end 측정은 별도 문서 (06 후처리 + e2e, 07 공식 벤치, 08 카메라).
- 현 시점 결정: YOLO 유지 (잠정). MediaPipe 전환 트리거 보류.

## 7. 알려진 한계 + 후속 측정 계획

### 7-1. 본 측정의 한계

- 더미 입력 (random)만 사용 — 실제 이미지 latency는 비슷할 가능성 높지만 검증 필요.
- 추론만 측정 (전처리 / 후처리 미포함) — end-to-end FPS는 본 수치보다 낮을 것.
- 측정 1회 (시간대 / 온도 / 시스템 부하 다른 조건 미검증).
- 메모리 RSS, 온도 미측정.

### 7-2. 추가 측정 권장 (멘토 docs 06번 기준)

본 측정에 미수집된 항목:

- max RSS (MB) — `/proc/[pid]/status`의 VmRSS.
- max temperature (°C) — `/sys/class/thermal/thermal_zone*/temp`.
- dropped frames — 실제 카메라 입력 시 측정.
- preprocess_ms_mean, postprocess_ms_mean — 후처리 모듈 작성 후 측정 가능.
- thread count sweep (1, 2, 4) — 최적 스레드 수 확인용.

위 항목은 공식 벤치마크(07) + 카메라 측정(08)에서 수집.

### 7-3. GPU delegate 시도 — 후순위

- QRB2210은 `/dev/kgsl*` 미노출 (디바이스 진단 결과).
- OpenCL / Adreno 가속 어려울 가능성 큼.
- CPU에서 합격선 통과했으므로 GPU 시도 후순위로 보류.

## 8. 빠른 참조 — 재측정

### 8-1. 호스트 재측정

```bash
cd /mnt/c/Project/unoq-companion-robot
bash run.sh                                                 # 컨테이너 진입
python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite
```

### 8-2. 디바이스 재측정 (호스트 WSL에서 원격 단일 호출)

```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
  python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite'
```

### 8-3. JSON 저장 + 호스트로 회수

```bash
# 디바이스 SSH 셸에서
mkdir -p ~/benchmarks
python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite \
  --json ~/benchmarks/device_validate_int8_$(date +%Y%m%d).json

# 호스트 WSL에서 회수
mkdir -p /mnt/c/Project/unoq-companion-robot/benchmarks
scp arduino@192.168.0.45:~/benchmarks/device_validate_int8_*.json \
    /mnt/c/Project/unoq-companion-robot/benchmarks/
```

### 8-4. 다른 변종 모델로 호스트 비교

```bash
# float32 (양자화 없음, 정확도 기준선)
python src/validate_model.py models/yolov8n_saved_model/yolov8n_float32.tflite

# float16 (중간 옵션)
python src/validate_model.py models/yolov8n_saved_model/yolov8n_float16.tflite
```

## 9. 본 측정의 작품 / 포트폴리오 가치

- 인터넷 미공개 데이터 포인트: "QRB2210 + YOLOv8n int8 320×320, CPU 4 thread XNNPACK = 9.88 FPS" 정확한 숫자가 공개 자료에 거의 없음.
- 본인 작품의 unique contribution — 측정 자체가 가치.
- 멘토 / Qualcomm 보고 시 "추정이 아니라 실측 데이터" 제시 가능.
- 향후 다른 모델(MediaPipe 등) 시도 시 비교 baseline.
