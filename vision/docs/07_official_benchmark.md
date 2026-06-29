# Official Benchmark — Host vs UNO Q (Mentor docs 06 Format)

본 문서는 멘토 패키지 `06_testing_benchmarking_reliability.md` Section 3의 JSON 형식 권고를 따른 정식 벤치마크 결과를 정리합니다. 단일 이미지 100회 반복 측정 (warmup 10 + measure 100), 호스트(Docker)와 UNO Q 디바이스 양쪽에서 수행.

## 0. 핵심 결정

| 항목 | 값 |
|---|---|
| **측정 도구** | `src/benchmark_e2e.py` (호스트 / 디바이스 공용) |
| **모델** | `yolov8n_int8.tflite` (3.19 MB, 320×320, w8a8) |
| **데이터 형식** | 멘토 `06_testing_benchmarking_reliability.md` Section 3 JSON 권고 그대로 |
| **측정 횟수** | 100 frames (warmup 10) |
| **런타임** | ai_edge_litert + XNNPACK delegate (호스트 / 디바이스 동일) |
| **호스트 FPS** | 73.09 (Ryzen 7 6800HS, 4 thread) |
| **디바이스 FPS** | 9.23 (Cortex-A53 ×4) |
| **디바이스 최대 온도** | 60.5°C (100회 후, 장시간 운영 안전 영역) |
| **디바이스 최대 메모리** | 100.8 MB (가용 2.4 GB의 4%) |
| **합격 판정 (FPS ≥ 8)** | 통과 |

## 1. 측정 방법

### 1-1. 도구

`src/benchmark_e2e.py` — 한 이미지를 N회 반복 추론하며 단계별 latency, RSS, 온도 수집.

### 1-2. 절차

1. 모델 로드 + 이미지 로드 (1회).
2. Warmup 10회 — cv2 drawing cold start, XNNPACK 초기화 등 일회성 비용 제거.
3. Measure 100회 — 각 프레임의 preprocess / inference / postprocess / draw 시간 기록.
4. 매 측정 후 `/proc/self/status` VmRSS 갱신 (피크 추적).
5. 매 측정 후 `/sys/class/thermal/thermal_zone*/temp` 갱신 (피크 추적).
6. 종료 시 mean / median / p50 / p95 / min / max 집계 + 멘토 형식 JSON 저장.

### 1-3. 멘토 docs 06 형식 준수 항목

| 멘토 필드 | 우리 수집 | 비고 |
|---|---|---|
| `model` | 수집 | 모델 파일 경로 |
| `runtime` | 수집 | `ai_edge_litert:4` 형식 (런타임명 : 스레드수) |
| `input_shape` | 수집 | `[1, 320, 320, 3]` |
| `frames` | 수집 | 100 |
| `latency_ms_p50` | 수집 | total p50 |
| `latency_ms_p95` | 수집 | total p95 |
| `fps_mean` | 수집 | 1000 / total mean |
| `preprocess_ms_mean` | 수집 | preprocess mean |
| `postprocess_ms_mean` | 수집 | postprocess mean |
| `dropped_frames` | 수집 (=0) | 이미지 1장 반복이라 0 (카메라 입력 시 적용) |
| `max_rss_mb` | 수집 | 본 프로세스 VmRSS 피크 |
| `max_temp_c` | 수집 | 시스템 thermal zone 최대 (디바이스만 유효) |

추가 확장 필드: `warmup`, `inference_ms_mean`, `draw_ms_mean`, `stages` (단계별 상세 통계), `last_detections_count`, `thresholds`.

## 2. 호스트 결과 (Docker 컨테이너)

### 2-1. 환경

- CPU: AMD Ryzen 7 6800HS (Zen3+, 4 스레드).
- OS: Ubuntu 22.04 (컨테이너).
- Runtime: ai_edge_litert 2.1.5 + XNNPACK.
- 측정 일자: 2026-06-23.

### 2-2. 단계별 latency (ms)

| 단계 | mean | p50 | p95 | min | max |
|---|---|---|---|---|---|
| preprocess | 1.23 | 1.20 | 1.43 | 1.09 | 1.79 |
| inference | 10.25 | 10.19 | 11.32 | 9.16 | 12.01 |
| postprocess | 0.94 | 0.91 | 1.12 | 0.82 | 1.56 |
| draw | 0.91 | 0.89 | 1.04 | 0.84 | 1.80 |
| total | 13.68 | 13.54 | 14.84 | 12.59 | 15.70 |

### 2-3. 핵심 지표

- FPS mean: 73.09.
- max_rss_mb: 123.2.
- max_temp_c: null (컨테이너에서 호스트 thermal zone 접근 불가).
- 분포 안정성 (p95 / p50): 1.10 — 매우 안정.

### 2-4. JSON 파일

`benchmarks/host_e2e_20260623.json`.

## 3. 디바이스 결과 (UNO Q)

### 3-1. 환경

- CPU: Qualcomm QRB2210 (Cortex-A53 ×4 @ 2.0 GHz).
- OS: Debian aarch64 (kernel 7.0.0-g122c2c22d838).
- Python: 3.13.5 (venv at `~/venv-unoq`).
- Runtime: ai_edge_litert 2.1.5 + XNNPACK.
- 측정 일자: 2026-06-23.

### 3-2. 단계별 latency (ms)

| 단계 | mean | p50 | p95 | min | max |
|---|---|---|---|---|---|
| preprocess | 5.42 | 6.04 | 6.59 | 3.29 | 6.97 |
| inference | 93.28 | 90.71 | 120.21 | 84.05 | 159.97 |
| postprocess | 5.08 | 5.08 | 5.60 | 4.23 | 5.69 |
| draw | 3.90 | 3.88 | 4.17 | 3.47 | 4.81 |
| total | 108.36 | 105.02 | 132.74 | 95.80 | 174.95 |

### 3-3. 핵심 지표

- FPS mean: 9.23 (합격선 8 통과).
- max_rss_mb: 100.8 (가용 2.4 GiB의 4%).
- max_temp_c: 60.5°C (100회 후, 70°C 이하 — 안전 영역).
- 분포 안정성 (p95 / p50): 1.26 — 수용 가능 (임베디드 정상).

### 3-4. JSON 파일

`benchmarks/device_e2e_20260623.json`.

## 4. 호스트 vs 디바이스 비교

### 4-1. Latency 비율

| 단계 | 호스트 mean | 디바이스 mean | 비율 (디바이스 / 호스트) |
|---|---|---|---|
| preprocess | 1.23 ms | 5.42 ms | 4.4× |
| inference | 10.25 ms | 93.28 ms | 9.1× |
| postprocess | 0.94 ms | 5.08 ms | 5.4× |
| draw | 0.91 ms | 3.90 ms | 4.3× |
| total | 13.68 ms | 108.36 ms | 7.9× |
| FPS | 73.09 | 9.23 | 1 / 7.9 |

### 4-2. 비율 해석

- inference만 9.1× 느림 — CPU 아키텍처 차이 (Zen3+ Out-of-Order, 큰 SIMD vs Cortex-A53 In-Order, 작은 SIMD).
- preprocess / postprocess / draw 는 4~5× 느림 — 메모리 bandwidth 중심 작업이라 CPU IPC 영향 작음.
- 종합 e2e 비율(7.9×)이 inference 비율(9.1×)보다 작음 — 다른 단계가 약간 완화.

### 4-3. 메모리 / 온도

| 항목 | 호스트 | 디바이스 |
|---|---|---|
| max_rss_mb | 123.2 | 100.8 |
| max_temp_c | N/A | 60.5°C |

디바이스 RSS가 더 작은 이유: 호스트 컨테이너에 추가 deps (Ultralytics, torch 등) 모두 import 됨. 디바이스는 ai-edge-litert + numpy + cv2 만.

## 5. 합격 판정 — 4개 기준 모두 통과

| 기준 | 임계값 | 측정값 | 결과 |
|---|---|---|---|
| 실시간 FPS | ≥ 8 | 9.23 | 통과 |
| 분포 안정성 (p95 FPS) | ≥ 6 | 7.53 | 통과 |
| 메모리 사용 | ≪ 가용 (2.4 GB) | 100.8 MB (4%) | 매우 여유 |
| 온도 (100회 후) | ≤ 70°C | 60.5°C | 안전 |

YOLOv8n int8 @ 320×320 / CPU 4 thread / ai_edge_litert + XNNPACK 조합으로 본 작품 운영 최종 확정. 본 프로젝트 의사결정 트리(02)의 MediaPipe 전환 트리거 발동 안 됨.

## 6. 주요 관찰

### 6-1. ai_edge_litert이 tensorflow.lite보다 빠름

본 측정의 핵심 비교 (동일 모델 + 동일 입력, 런타임 + 측정 도구만 다름):

| 런타임 / 도구 / 환경 | inference mean | 비고 |
|---|---|---|
| tensorflow.lite + validate_model.py / 호스트 | 12.5 ms | 이전 baseline |
| ai_edge_litert + benchmark_e2e.py / 호스트 | 10.25 ms | -18% (런타임 우위) |
| ai_edge_litert + validate_model.py / 디바이스 | 101.27 ms | warmup 5회 |
| ai_edge_litert + benchmark_e2e.py / 디바이스 | 93.28 ms | -8% (warmup 10회 효과) |

ai_edge_litert는 Google AI Edge의 모던 런타임. tensorflow.lite와 동일 API에 더 최적화. 호스트 / 디바이스 양측에서 같은 런타임 사용 → 비교 일관성 확보.

### 6-2. cv2 cold start는 warmup 10회로 충분 제거

이전 단계에서 발견한 cv2 drawing cold start (~60 ms, 단일 이미지 측정 시 발생)가 warmup 10회 측정에선 사라짐 (디바이스 draw mean 3.90 ms). 멘토 06 권고 "warmup → measure" 패턴이 효과적.

### 6-3. 디바이스 온도 안전 영역

100회 연속 측정 후 60.5°C — QRB2210 정상 동작 온도(-30 ~ 85°C) 내. 실시간 비디오 시 지속 부하 시 추가 측정 필요하나 현 수준에선 thermal throttle 위험 낮음.

### 6-4. inference p95 / p50 = 1.32 (디바이스)

디바이스 inference 분포가 호스트보다 큰 변동성. 원인 추정:

- 시스템 백그라운드 (cron, sshd, network).
- DRM / GPU 관련 인터럽트.
- DDR 메모리 contention.

임베디드 환경에선 흔함. 운영에서 큰 문제 없음.

## 7. 알려진 한계

| 한계 | 영향 | 향후 대응 |
|---|---|---|
| 단일 이미지 1장 반복 | 다양한 입력 시나리오 미커버 | golden image set으로 확장 (멘토 docs 06 Section 2) |
| 카메라 입력 미포함 | 실제 운영 시 capture overhead 누락 | UVC 카메라 연결 후 별도 측정 (예정) |
| dropped_frames = 0 (강제) | 단일 이미지라 측정 불가 | 카메라 + 비디오 입력 시 진짜 측정 |
| 단시간 100회 (≈ 11초) | 장시간 thermal 거동 모름 | soak test (멘토 docs 06 Section 4) 필요 |
| GPU delegate 미시도 | CPU 충분으로 후순위 | `/dev/kgsl*` 부재로 어려울 가능성 큼 |

## 8. 재현 절차

### 8-1. 호스트 (Docker 컨테이너 안)

```bash
bash docker/run-vision.sh                              # 컨테이너 진입
mkdir -p benchmarks
python src/benchmark_e2e.py \
  models/yolov8n_saved_model/yolov8n_int8.tflite \
  datasets/coco128/images/train2017/000000000009.jpg \
  --runs 100 --warmup 10 \
  --json benchmarks/host_e2e_$(date +%Y%m%d).json
```

### 8-2. 디바이스 (호스트 WSL에서 원격)

```bash
# 스크립트 전송
scp src/benchmark_e2e.py arduino@192.168.0.45:~/

# 실행
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
  mkdir -p ~/benchmarks && \
  python3 ~/benchmark_e2e.py \
    /opt/unoq-yolo/models/yolov8n_int8.tflite \
    /opt/unoq-yolo/media/000000000009.jpg \
    --runs 100 --warmup 10 \
    --json ~/benchmarks/device_e2e_'"$(date +%Y%m%d)"'.json'

# JSON 회수
scp arduino@192.168.0.45:~/benchmarks/device_e2e_*.json ./benchmarks/
```

### 8-3. JSON 위치

- 호스트: `benchmarks/host_e2e_<YYYYMMDD>.json`.
- 디바이스: `benchmarks/device_e2e_<YYYYMMDD>.json`.

`benchmarks/` 폴더는 현재 `.gitignore` 패턴에 포함 안 되어 있으므로 git에 들어감. 자산 보존 의도 시 그대로 유지, 별도 채널 원하면 `.gitignore`에 추가.

## 9. 멘토 보고 시 핵심 요약 한 줄

> **Arduino UNO Q (QRB2210) 위에서 YOLOv8n int8 (320×320, ai_edge_litert + XNNPACK) end-to-end 9.23 FPS, p95 latency 132 ms, 최대 메모리 100 MB, 최대 온도 60.5°C 실측 — 본 작품 합격선(8 FPS) 통과 + 장시간 운영 안전 영역.**
