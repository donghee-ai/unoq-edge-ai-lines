# UNO Q 디바이스 첫 추론 결과 — YOLOv8n int8

> 본 문서는 STEP 4 (모델 전송) + STEP 5 (디바이스 실행)의 첫 측정 결과를 기록합니다.
> 호스트 baseline(`05_host_validation_results.md`)과 비교하여 본 작품 합격선 판정의 근거가 됩니다.

---

## 결정 요약 (한 화면)

| 항목 | 값 |
|---|---|
| 측정 모델 | `yolov8n_int8.tflite` (3.19 MB, 320×320) |
| 디바이스 | Arduino UNO Q (QRB2210, Cortex-A53 ×4, 4 GB RAM) |
| Runtime | `ai_edge_litert` + XNNPACK delegate (4 스레드) |
| latency mean | **101.27 ms** |
| latency p50 / p95 | 94.03 / 129.06 ms |
| **FPS mean** | **🎯 9.88** |
| 합격선 (≥ 8 FPS) | ✅ **통과** |
| 호스트 대비 | 약 **8.1× 느림** (사전 추정 8~15× 범위의 빠른 쪽) |
| 결론 | YOLO 유지, MediaPipe 전환 트리거 발동 안 됨 |

---

## 1. 측정 절차 (재현 가능 기록)

### 1-1. Phase A — 디바이스 셋업 (1회)

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

설치된 패키지:
- ai-edge-litert 2.1.5
- numpy 2.5.0
- 부수: tqdm, protobuf, flatbuffers, backports.strenum, typing-extensions

### 1-2. Phase B — 파일 전송

호스트 WSL에서:
```bash
cd /mnt/c/Project/unoq-companion-robot
scp models/yolov8n_saved_model/yolov8n_int8.tflite \
    arduino@192.168.0.45:/opt/unoq-yolo/models/
scp src/validate_model.py arduino@192.168.0.45:~/
```

전송 크기: 3,269 KB (.tflite) + 7.6 KB (.py). 약 0.5초.

### 1-3. Phase C — 디바이스에서 추론 실행

```bash
# 디바이스 SSH 셸 안에서
source ~/venv-unoq/bin/activate
python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite
```

소요: 약 30초 (모델 로드 + warmup 5 + 측정 50회).

---

## 2. 측정 환경

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

---

## 3. 모델 메타데이터 (디바이스에서 자동 추출)

호스트와 **완전히 동일** (같은 .tflite 파일이라 당연하지만 확인됨):

| 속성 | Input | Output |
|---|---|---|
| 이름 | `images` | `Identity` |
| Shape | `[1, 320, 320, 3]` | `[1, 84, 2100]` |
| Dtype | `float32` | `float32` |
| Quantization | `(0.0, 0)` | `(0.0, 0)` |

→ 후처리 코드는 호스트/디바이스 동일하게 작성 가능.

---

## 4. Latency 측정 (50회 반복)

| 통계 | 값 (ms) |
|---|---|
| min | 87.748 |
| max | 163.091 |
| mean | **101.268** |
| median | 94.028 |
| p50 | 94.027 |
| p95 | 129.063 |
| **FPS mean** | **9.875** |

### 4-1. 분포 해석

- **p95 / mean ≈ 1.27** — 호스트(1.20)보다 약간 큰 변동성. 임베디드 시스템 백그라운드 작업/스케줄링 영향
- **min ~ p95 약 41 ms 차이** — 가끔 느린 프레임 있음, 그러나 평균은 안정
- **median 94 ms vs mean 101 ms** — 우측 꼬리(가끔 느린 측정) 있음, 정상 분포

### 4-2. FPS 의미

- **9.88 FPS = 약 100 ms 주기로 검출**
- 인간 인지 임계점: 100 ms = "지연 없는 즉시 반응" 경계선
- 책상 위 교감로봇 시나리오에서 **자연스러운 인터랙션 가능 수준**

---

## 5. 호스트 vs 디바이스 비교

| 지표 | 호스트 (Ryzen 7 6800HS) | UNO Q (Cortex-A53) | 디바이스/호스트 비율 |
|---|---|---|---|
| latency min | 10.09 ms | 87.75 ms | 8.7× |
| latency mean | 12.51 ms | **101.27 ms** | **8.1×** |
| latency p50 | 12.23 ms | 94.03 ms | 7.7× |
| latency p95 | 14.98 ms | 129.06 ms | 8.6× |
| latency max | 16.11 ms | 163.09 ms | 10.1× |
| FPS mean | 79.96 | 9.88 | 1/8.1 |

### 5-1. 사전 추정과의 비교

`05_host_validation_results.md` Section 4-2의 추정:
- latency 추정: 100~190 ms → **101 ms 실측** (가장 빠른 쪽)
- FPS 추정: 5~10 → **9.88 실측** (가장 빠른 쪽)

**사전 추정 정확. CPU 아키텍처 비교(약 8~15×)가 잘 들어맞음.**

### 5-2. 왜 8.1×인가 (해설)

| 차이 요소 | 영향 |
|---|---|
| Zen3+ vs Cortex-A53 IPC | Zen3+ 약 3× 빠름 |
| 클럭 (3.2 GHz vs 2.0 GHz) | 1.6× 차이 |
| SIMD (AVX2 vs NEON) | Zen3+ 약 2× 빠름 |
| 캐시 크기 | Zen3+ 훨씬 큼 |
| **종합** | **8~10× 추정, 실측 8.1×** |

XNNPACK delegate가 ARM NEON 잘 활용하고 있다는 신호 — Cortex-A53급 치고는 좋은 결과.

---

## 6. 합격 판정 — 트리거 평가

`01_model_selection_log.md`에서 정의한 의사결정 트리:

| 조건 | 실측 | 액션 |
|---|---|---|
| FPS ≥ 8 | **9.88 ≥ 8** ✅ | **YOLO 유지** |
| FPS < 8 | — | (해당 없음) 최적화 또는 MediaPipe 전환 |

→ **MediaPipe Face 전환 트리거 발동 안 됨.** YOLOv8n int8 그대로 유지하며 다음 단계 진행.

여유 마진: 9.88 - 8 = **1.88 FPS** (약 24% 여유). 다음 단계에서 전처리/후처리/추론 합산 시 약간 떨어질 가능성을 감안해도 합격선 유지 가능 전망.

---

## 7. 알려진 한계 + 후속 측정 계획

### 7-1. 본 측정의 한계
- 더미 입력 (random float32)만 사용 — 실제 이미지 latency는 비슷할 가능성 높지만 검증 필요
- 추론만 측정 (전처리/후처리 미포함) — end-to-end FPS는 본 수치보다 낮을 것
- 측정 1회만 (시간대/온도/시스템 부하 다른 조건 미검증)
- 메모리 RSS, 온도 미측정

### 7-2. 추가 측정 권장 (멘토 docs 06번 기준)

본 측정에 미수집된 항목:
- max RSS (MB) — `/proc/[pid]/status`의 VmRSS
- max temperature (°C) — `/sys/class/thermal/thermal_zone*/temp`
- dropped frames — 실제 카메라 입력 시 측정
- preprocess_ms_mean, postprocess_ms_mean — 후처리 모듈 작성 후 측정 가능
- thread count sweep (1, 2, 4) — 최적 스레드 수 확인용

위 항목은 후속 단계 (실제 이미지 추론 + 후처리 코드 작성) 진입 후 점진적 수집.

### 7-3. GPU delegate 시도 — 후순위
- QRB2210은 `/dev/kgsl*` 미노출 (디바이스 진단 결과)
- OpenCL/Adreno 가속 어려울 가능성 큼
- CPU에서 합격선 통과했으므로 GPU 시도 후순위로 보류

---

## 8. 본 측정의 작품/포트폴리오 가치

- **인터넷 미공개 데이터 포인트**: "QRB2210 + YOLOv8n int8 320×320, CPU 4 thread XNNPACK = 9.88 FPS" 정확한 숫자가 공개 자료에 거의 없음
- **본인 작품의 unique contribution** — 측정 자체가 가치
- 멘토/Qualcomm 보고 시 "추정이 아니라 실측 데이터" 제시 가능
- 향후 다른 모델(MediaPipe 등) 시도 시 비교 baseline

---

## 9. 빠른 참조 — 재측정

### 호스트 측 변경 없이 디바이스 측만 재측정
```bash
# 호스트 WSL에서 디바이스에 명령 단일 호출
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite'
```

### JSON 결과 저장 + 호스트로 회수 (멘토 보고 용)
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

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성 | UNO Q 디바이스 첫 추론 + latency 측정 (9.88 FPS) — 합격선 통과 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 측정 시점 | 디바이스 셋업 직후 (첫 측정) |
| 관련 문서 | `05_host_validation_results.md` (비교 baseline), `06_device_setup.md` (디바이스 환경), `01_model_selection_log.md` (의사결정 트리) |
| 다음 갱신 시점 | 후처리 모듈 추가 후 end-to-end FPS 측정 시 |
