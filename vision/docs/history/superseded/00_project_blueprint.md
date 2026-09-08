# Project Blueprint — UNO Q Real-time YOLOv8 Detection

본 문서는 본 프로젝트의 전반적 청사진을 한 페이지로 정리합니다. UNO Q 디바이스 사양, 모델 선택 결과와 대안 후보, 데이터셋과 아키텍처, 합격 기준, 그리고 후속 문서들의 진행 흐름을 포함합니다.

## 0. 프로젝트 목적

Arduino UNO Q (Qualcomm Dragonwing QRB2210, CPU only) 위에서 YOLOv8n int8 TFLite 모델을 실시간 카메라 입력으로 추론하여 객체를 검출하는 임베디드 AI 작품. 본 보고 시점 합격선(end-to-end 8 FPS 이상)에 도달.

## 1. UNO Q 디바이스 스펙

| 항목 | 값 |
|---|---|
| **SoC** | Qualcomm Dragonwing QRB2210 (Agatti) |
| **CPU** | Arm Cortex-A53 ×4 @ 2.0 GHz |
| **GPU** | Adreno 702 (저티어, 본 작품은 CPU 단독 경로) |
| **MCU** | STM32U585 (Arm Cortex-M33, ~160 MHz) |
| **RAM** | 4 GB LPDDR4 (가용 2.4 GiB) |
| **eMMC** | 16 GB (root `/`엔 9.8 GB 할당, 가용 2.9 GB) |
| **OS** | Linux Debian aarch64 (kernel 7.0) |
| **AI 가속기** | 없음 (DSP / HTP / NPU 모두 미장착) |
| **공식 AI 런타임** | TFLite (LiteRT) 단독. QAIRT / SNPE / QNN 미지원 |

본 작품에서 채택한 런타임은 `ai-edge-litert` (Google AI Edge의 모던 TFLite 구현). 4 스레드 CPU + XNNPACK delegate.

## 2. 모델 선택

### 2-1. 1차 채택 — YOLOv8n int8

| 항목 | 값 |
|---|---|
| **모델** | YOLOv8n int8 TFLite |
| **크기** | 3.19 MB (int8 weight, 약 4× 압축) |
| **입력 해상도** | 320 × 320 |
| **양자화** | w8a8 hybrid (weight int8, 입출력 float32) |
| **라이선스** | AGPL-3.0 (Ultralytics 기반, 상업 배포 시 별도 검토) |
| **획득 경로** | Ultralytics 표준 export (호스트에서 변환) |

### 2-2. 전환 트리거와 대안

| 조건 | 액션 |
|---|---|
| 디바이스 FPS ≥ 8 | YOLO 유지, 후속 단계(얼굴 처리) 진행 |
| 디바이스 FPS < 8 | 최적화 1차 시도(해상도 / 스레드 / frame skipping) → 그래도 미달이면 MediaPipe Face로 전환 |

### 2-3. 대안 후보 — MediaPipe Face

| 항목 | 값 |
|---|---|
| **모델 패밀리** | `face_detector` (BlazeFace) + `face_landmark_detector` (FaceMesh 468점) |
| **라이선스** | Apache-2.0 (배포 자유) |
| **포맷** | TFLite 네이티브 (추가 변환 불필요) |
| **예상 추론** | face_detector 5~25 ms + face_landmark 25~80 ms (CPU only) |
| **현 상태** | 사전 조사 완료, 적용은 트리거 충족 시점 |

### 2-4. 측정 결과 — 트리거 발동 없이 YOLO 유지

디바이스 첫 측정 9.88 FPS (순수 inference), e2e 9.3 FPS, 공식 100회 벤치 9.23 FPS, 카메라 입력 8.52~8.29 FPS — 모두 합격선 통과. MediaPipe 전환 보류.

## 3. 데이터셋

| 용도 | 데이터셋 | 출처 |
|---|---|---|
| **추론 클래스 라벨** | COCO 80 classes (`person`, `bicycle`, `car`, ..., `toothbrush`) | `src/postprocess.py`의 `COCO_NAMES` 상수 |
| **모델 학습 (사전학습)** | COCO train2017 (~118k 이미지) | Ultralytics YOLOv8n 표준 사전학습 |
| **int8 양자화 calibration** | COCO128 (128장) | Ultralytics 자동 다운로드 (`coco128.yaml`) |
| **본 작품 검증 이미지** | COCO128 train2017 일부 (예: `000000000009.jpg`) | 호스트 + 디바이스 측정 시 사용 |

본 작품은 별도 도메인 데이터셋 학습 없이 Ultralytics 표준 YOLOv8n 사전학습 그대로 사용. 향후 얼굴 / 표정 단계에서 도메인 fine-tune 검토.

## 4. 모델 아키텍처 — YOLOv8 anchor-free

### 4-1. 입출력 텐서

| 텐서 | shape | dtype |
|---|---|---|
| **Input** | `[1, 320, 320, 3]` | float32 (정규화 [0, 1]) |
| **Output** | `[1, 84, 2100]` | float32 |

입출력은 float32이지만 내부 weight 와 op는 int8 양자화 (Ultralytics int8 export 표준 동작). 사용자 코드에서 quant / dequant 변환 불필요.

### 4-2. Output `[1, 84, 2100]` 해석

- `1` = batch.
- `84` = 4 (bbox: cx, cy, w, h) + 80 (COCO 클래스 점수).
- `2100` = anchor 개수 (anchor-free + multi-scale: 40×40 + 20×20 + 10×10 = 2100, 320 입력 기준).

bbox 좌표는 **정규화 [0, 1] 범위** (Ultralytics int8 TFLite export의 특성. PyTorch / ONNX는 픽셀 좌표 — 다름). 후처리에서 `input_size`(320)를 곱해 픽셀 좌표로 변환.

### 4-3. 후처리 파이프라인

1. raw output `[1, 84, 2100]` → `[2100, 84]` (transpose).
2. 정규화 [0, 1] → 모델 입력 픽셀 좌표 [0, 320] (input_size 곱).
3. xywh → xyxy 변환.
4. confidence threshold (기본 0.25) 필터.
5. NMS (cv2.dnn.NMSBoxes, IoU 임계 0.45).
6. letterbox padding 제거 + 원본 이미지 좌표로 scale.
7. 클래스 ID → COCO 라벨 매핑 + 박스 그리기.

코드 모듈: `src/postprocess.py`. 자세한 함정 (정규화 좌표 버그 / cv2 cold start) → 06 참조.

## 5. 합격선 — 4기준

본 프로젝트 의사결정 트리(02 모델 선택)와 벤치마크 표준 권고를 결합한 운영 합격 기준:

| 기준 | 임계값 | 측정 |
|---|---|---|
| **실시간 FPS (mean)** | ≥ 8 | 디바이스 단일 이미지 9.23, 카메라 8.52 / 8.29 |
| **분포 안정성 (p95 FPS)** | ≥ 6 | 7.53 (단일 이미지) / 6.85, 6.42 (카메라) |
| **메모리 (max RSS)** | ≪ 가용 2.4 GB | 100.8 ~ 116.9 MB (4 ~ 4.9%) |
| **온도 (max temp)** | ≤ 70°C | 60.5°C (단일) / 59.2°C (카메라 100f) / 70.8°C (카메라 285s 운영 — 임계 1도 초과 발견) |

모든 기준 통과. 단 장시간 운영의 thermal margin은 좁음 → 향후 soak test 권고.

## 6. 진행 흐름 — 후속 문서

| 번호 | 문서 | 역할 | 소요 시간 (예상) |
|---|---|---|---|
| 01 | `01_host_environment_setup.md` | Docker 호스트 환경 빌드 | 15분 (첫 빌드) |
| 02 | `02_model_selection_log.md` | 모델 선택의 자세한 의사결정 로그 | 읽기만 |
| 03 | `03_project_conventions.md` | 코딩 / 디렉토리 / 보안 규약 | 읽기만 |
| 04 | `04_device_setup.md` | UNO Q SSH + `setup_device.sh` 실행 | 10분 |
| 05 | `05_initial_inference_measurement.md` | 호스트 baseline + 디바이스 첫 측정 | 30분 |
| 06 | `06_postprocess_and_e2e.md` | 후처리 모듈 + 함정 + e2e 합격 | 30분 |
| 07 | `07_official_benchmark.md` | 공식 100회 벤치마크 | 10분 |
| 08 | `08_realtime_camera.md` | 카메라 실시간 측정 + 함정 | 10분 |
| 09 | `09_usage_runbook.md` | 자주 쓰는 명령 모음 (참조용) | 진행 중 옆에 두기 |

## 7. 사전 조건 (외부 진입자용 체크리스트)

### 7-1. 호스트 PC

- Windows 11 + WSL2 (Ubuntu 24.04) — 또는 Linux / macOS + Docker.
- Docker Desktop 또는 Docker Engine.
- 디스크 여유 ~5 GB (이미지 + 패키지 + 데이터셋).

### 7-2. UNO Q 디바이스

- UNO Q 보드 (4 GB RAM 변종 권장).
- USB UVC 카메라 (Logitech C270, C920 등 표준 UVC).
- LAN 케이블 또는 동일 WiFi (호스트 ↔ 디바이스 SSH).
- 디바이스 SSH 비밀번호 (App Lab 초기 설정).

### 7-3. 시작 명령 (호스트 WSL에서)

```bash
git clone https://github.com/donghee-ai/unoq-edge-ai-lines.git
cd unoq-edge-ai-lines
bash docker/run-vision.sh                      # 컨테이너 진입 (첫 빌드 ~15분)
```

자세한 절차는 01 참조.
