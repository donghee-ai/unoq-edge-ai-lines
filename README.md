# UNO Q Companion Robot

> Arduino UNO Q (Qualcomm Dragonwing QRB2210) 위에서 동작하는 책상용 교감로봇 프로젝트.
> TFLite로 얼굴/표정을 실시간 분석하여 LED·모터·소리로 반응합니다.

**현재 상태**: STEP 1~5 완료. UNO Q 디바이스에서 **9.88 FPS 실측 확인** — 본 작품 합격선(8 FPS) 통과.

---

## 하드웨어 사양

| 항목 | 값 |
|---|---|
| 보드 | Arduino UNO Q |
| SoC | Qualcomm Dragonwing QRB2210 |
| CPU | 4 × Arm Cortex-A53 @ 2.0 GHz |
| GPU | Adreno 702 (CPU 폴백 우선 사용) |
| NPU / DSP / HTP | **없음** — TFLite/LiteRT CPU 단독 경로 |
| MCU (제어) | STM32U585 (Cortex-M33, 최대 160 MHz) |
| RAM / 저장소 | 2~4 GB LPDDR4 / 16~32 GB eMMC |
| OS | Linux Debian (사전 설치됨) |

---

## 개발 환경

| 컴포넌트 | 버전 |
|---|---|
| 호스트 OS | Windows 11 + WSL2 (Ubuntu 24.04) |
| 컨테이너 OS | Ubuntu 22.04 |
| Python | 3.10.12 |
| TensorFlow | 2.19.1 |
| Ultralytics | 8.4.75 |
| 모든 deps | `requirements.lock`으로 byte-exact 고정 (94 패키지) |

---

## 빠른 시작

### 사전 준비
- Docker (Desktop 또는 Engine)
- bash 셸 (Windows는 WSL2 또는 Git Bash)
- 디스크 여유 약 5 GB

### 1. 클론 + 환경 빌드 (1회, 약 15분)
```bash
git clone https://github.com/donghee-ai/unoq-companion-robot.git
cd unoq-companion-robot
bash run.sh
```

성공 시 컨테이너 안 프롬프트로 진입:
```
dev@unoq-yolo-dev:/work$
```

### 2. YOLOv8n int8 TFLite 모델 export (약 5분, 1회만)
```bash
mkdir -p models
cd models
python -c "from ultralytics import YOLO; \
  m=YOLO('yolov8n.pt'); \
  m.export(format='tflite', int8=True, imgsz=320, data='coco128.yaml')"
```

결과물: `models/yolov8n_saved_model/yolov8n_int8.tflite` (3.19 MB)

### 3. 모델 검증 + 호스트 baseline 측정
```bash
cd /work
python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite
```

상세 절차는 [`danny/00_environment_setup.md`](danny/00_environment_setup.md) 참조.

---

## 현재 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 호스트 PC Docker 개발 환경 | ✅ |
| 2 | YOLOv8n int8 TFLite export | ✅ |
| 2-α | `requirements.lock`으로 환경 재현성 확보 | ✅ |
| 3 | 호스트 모델 검증 + latency baseline | ✅ (12.5 ms / 80 FPS) |
| 4 | UNO Q 디바이스 셋업 + 모델 전송 | ✅ (ai-edge-litert + venv) |
| 5 | UNO Q에서 추론 실행 + 실측 | ✅ (**101 ms / 9.88 FPS**) |
| 6 | GPU delegate 트러블슈팅 (선택) | ⏳ (CPU로 합격선 통과로 후순위) |
| 7 | 후처리 모듈 (NMS, 박스 디코딩) | ⏳ |
| 8 | 실제 이미지 추론 + 시각화 | ⏳ |
| 9 | 얼굴 검출 / 표정 추론 파이프라인 | ⏳ |
| 10 | MCU 연동 (LED, 모터) | ⏳ |

---

## 성능 데이터

| 측정 환경 | 모델 | latency mean | FPS mean | 비고 |
|---|---|---|---|---|
| 호스트 CPU (Ryzen 7 6800HS, 4 thread, XNNPACK) | YOLOv8n int8 320×320 | 12.5 ms | 79.96 | baseline |
| **UNO Q CPU (Cortex-A53 ×4, ai-edge-litert + XNNPACK)** | YOLOv8n int8 320×320 | **101.27 ms** | **9.88** | 호스트 대비 8.1× 느림 |

작품 합격선: **8 FPS 이상** → ✅ **통과** (여유 1.88 FPS).

상세 분석:
- 호스트 baseline: [`danny/05_host_validation_results.md`](danny/05_host_validation_results.md)
- UNO Q 첫 추론: [`danny/07_device_first_inference.md`](danny/07_device_first_inference.md)

---

## 프로젝트 구조

```
unoq-companion-robot/
├── Dockerfile              컨테이너 이미지 정의
├── requirements.txt        Python 의존성 (사람 친화적 의도)
├── requirements.lock       94 패키지 byte-exact 핀 (Docker가 이걸로 설치)
├── .dockerignore           빌드 컨텍스트 정리
├── .gitignore              모델/데이터셋/캐시 제외 패턴
├── run.sh                  원샷 빌드+실행 스크립트
├── danny/                  프로젝트 의사결정 로그 (한국어)
│   ├── 00_environment_setup.md
│   ├── 01_model_selection_log.md
│   ├── 02_export_environment_fix.md
│   ├── 03_project_conventions.md
│   ├── 04_uno_q_env_setup.md
│   └── 05_host_validation_results.md
├── scripts/
│   ├── env.sh              UNO Q 접속 환경 변수
│   └── setup_device.sh     UNO Q 디바이스 셋업 자동화 (idempotent)
└── src/
    └── validate_model.py   TFLite 모델 검증 + latency 측정 (호스트/디바이스 공용)
```

---

## 주요 문서

| 문서 | 내용 |
|---|---|
| [`danny/00_environment_setup.md`](danny/00_environment_setup.md) | Docker 호스트 환경 셋업 절차 |
| [`danny/01_model_selection_log.md`](danny/01_model_selection_log.md) | 모델 선택 의사결정 로그 (YOLO ↔ MediaPipe) |
| [`danny/02_export_environment_fix.md`](danny/02_export_environment_fix.md) | Export 환경 충돌 해결 + lock 적용 |
| [`danny/03_project_conventions.md`](danny/03_project_conventions.md) | 프로젝트 코딩/운영 규약 |
| [`danny/04_uno_q_env_setup.md`](danny/04_uno_q_env_setup.md) | UNO Q 접속 환경 변수 사용법 |
| [`danny/05_host_validation_results.md`](danny/05_host_validation_results.md) | 호스트 baseline + UNO Q 실측 비교 |
| [`danny/06_device_setup.md`](danny/06_device_setup.md) | UNO Q 디바이스 환경 셋업 + 런타임 선택 |
| [`danny/07_device_first_inference.md`](danny/07_device_first_inference.md) | UNO Q 첫 추론 결과 (9.88 FPS, 합격 판정) |
| [`danny/08_usage_runbook.md`](danny/08_usage_runbook.md) | 실행 방법 가이드 (호스트/디바이스 공용 명령) |

---

## 설계 결정 요약

- **모델 1차 선택**: YOLOv8n int8 (TFLite). 본 작품 목적엔 기능적으로 충분
- **속도 대안 사전 조사**: MediaPipe Face (UNO Q 실측 8 FPS 미만 시 전환)
- **양자화 방식**: int8 (w8a8) — weight 4× 압축, 입출력은 float32로 유지
- **재현성 정책**: `requirements.lock` 우선, `requirements.txt`는 의도 표현용
- **UNO Q 접속**: `<UNO_Q_USER>` 변수 표준화 (기본 `arduino`), `scripts/env.sh`에서 관리

---

## 라이선스

(현재 Private. Public 전환 시점에 Apache License 2.0 또는 동등 권한 라이선스 추가 예정)

---

## 작성자

DongHee Kim · 한성대학교
