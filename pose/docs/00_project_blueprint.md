# UNO Q Pose 라인 청사진

본 문서는 본 라인의 목적, 입력/출력, 모델/런타임 결정, 합격 기준, 디렉토리 구조를 정의합니다. 외부 진입자가 본 라인의 의도와 범위를 30분 안에 파악할 수 있도록 작성합니다.

## 0. 목표

- **입력**: USB UVC 카메라 (640×480 25 fps, 변경 가능)
- **추론**: int8 TFLite Pose 모델, CPU only (XNNPACK delegate)
- **출력**:
  - 17 keypoint (COCO 17점) 좌표 + confidence
  - 좌/우 무릎 각도 (hip-knee-ankle)
  - 스쿼트 depth state (Standing/Quarter/Half/Parallel/ATG)
  - (선택) 스쿼트 rep counter (UP→DOWN→UP 사이클)
- **사용처 (메인)**: **헬스케어 봇** — 스쿼트 자세 측정/카운팅 + 자세 코칭. 다른 운동(팔굽혀펴기 등) 동일 알고리즘으로 확장 가능
- **사용처 (시연 보조)**: 감시 모드 — 같은 keypoint 신호의 다른 해석 (사람 검출 + 위치 추적 + 비정상 동작 알람) — 2026-06-27 멘토 미팅 결정
- **합격선** (vision/ASR 라인과 일치):
  - 디바이스 e2e FPS ≥ 8
  - 디바이스 RSS ≪ 2.4 GB (총 4 GB의 60% 이내)
  - 디바이스 thermal ≤ 70°C
  - dropped_frames = 0

## 1. 본 라인 위치 (3 라인 종합)

| 라인 | 폴더 | 모델 | 1차 PoC |
|---|---|---|---|
| Vision | [`vision/`](../../vision/) | YOLOv8n int8 TFLite | 통과 (9.23 FPS / 70.8°C) |
| ASR | [`asr/`](../../asr/) | Whisper Tiny.en TFLite (partial int8) | 통과 (3.18 s / 6+ 단어 정확) |
| **Pose (본 라인)** | `pose/` | **MoveNet Thunder INT8 TFLite** | **통과 (9.57~9.69 FPS, thermal plateau 71.4°C ⚠)** |

세 라인 모두 동일 stack: `ai-edge-litert` + XNNPACK + TFLite int8 → 자원 청사진/디버그/배포 일관.

## 2. 모델/런타임 결정

### 2-1. 채택 — MoveNet Thunder INT8

| 항목 | 값 |
|---|---|
| 출처 | TensorFlow Hub (Google) |
| URL | `https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4?lite-format=tflite` |
| 라이선스 | Apache-2.0 (code) + CC BY 4.0 (model) |
| 크기 | 6.80 MB (7,126,768 B) |
| 입력 | `[1, 256, 256, 3]` uint8 (정규화 X, image normalized 0-255) |
| 출력 | `[1, 1, 17, 3]` float32 (1 person × 17 keypoint × (y_norm, x_norm, conf)) |
| 양자화 | full int8 PTQ (텐서 87% 양자화) |
| 디바이스 런타임 | `ai-edge-litert` 2.1.5 + XNNPACK (chipset 비종속) |
| 측정 (호스트 x86, threads=4) | invoke p50 14.0 ms / 71.3 FPS |
| 측정 (UNO Q QRB2210, threads=4) | invoke p50 80.3 ms / 12.5 FPS, e2e 9.57~9.69 FPS, thermal plateau ~71°C |

### 측정 누적 (3회)

| # | 시간 | frames | fps_eff | cpu | rss | temp_peak | rep 검증 | 비고 |
|---|---|---|---|---|---|---|---|---|
| 1 | 136 s | 1,320 | 9.69 | 316% | 95 MB | 68.6°C | — | 단기 e2e (HTTP serve, 카운터 미사용) |
| 2 | 294 s | 2,813 | 9.55 | 311% | 95.5 MB | **71.4°C** | **13 rep** (deepest 28°) | 카운터 ON, sustained, **70°C 초과** |
| 3 | 157 s | 1,505 | 9.57 | 312% | 95.6 MB | 68.6°C | **9 rep** (deepest 46°) | 카운터 ON, 카메라 자세 미세 조정 |

→ **plateau 약 71°C** (측정 2번 sustained 결과). 짧은 측정은 ramp 단계라 합격(≤70°C)으로 보이지만 5분+ sustained 시 임계 초과. **합격 마진 정량 미확보** — soak + 환기/threads 조정 후속 필요.

### 2-2. 폴백 후보 — 미사용

- MoveNet Lightning INT8 (192×192, 더 빠름) — Thunder 합격으로 미시행
- OpenCV Zoo MediaPipe Pose int8 BQ (ONNX, 33 keypoint) — 미시행

자세한 결정 근거 + 다운로드 URL은 [`01_model_candidates.md`](01_model_candidates.md) 참조.

### 2-3. 기각 — Qualcomm AI Hub precompiled QNN ONNX

X2 Elite HTP NPU 전용 사전 컴파일 → QRB2210 (HTP 없음)에서 실행 불가. 정량 진단은 [`issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md`](issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md) 참조. 비호환 파일은 [`../models/archive/qnn-onnx-x2-elite-incompatible/`](../models/archive/qnn-onnx-x2-elite-incompatible/)로 격리.

## 3. 디렉토리 구조

```
pose/
├── docs/                    본 라인 가이드 + 히스토리 + 이슈 통합
│   ├── 00_project_blueprint.md   청사진 (본 문서)
│   ├── 01_model_candidates.md    모델 후보 + 각도 분석
│   ├── 02_quickstart_pose.md     0→30분 진입 절차
│   ├── 03_runbook_camera_serve.md 시나리오별 운영 명령
│   ├── history/                  작업 과정 기록 (마일스톤별 마크다운)
│   └── issues/                   트러블슈팅 기록 (재발 방지)
├── docker/
│   ├── Dockerfile.pose      Ubuntu 22.04 + ai-edge-litert + opencv (최소 의존성)
│   ├── requirements-pose.txt
│   └── run-pose.sh          빌드+진입 한 줄, --rebuild 옵션
├── models/
│   ├── movenet_thunder_int8.tflite                   채택 모델 (6.80 MB)
│   └── archive/qnn-onnx-x2-elite-incompatible/       비호환 격리 (5 파일)
├── scripts/
│   ├── inspect_movenet_thunder.py   호스트/디바이스 introspection + latency
│   ├── infer_camera_pose.py         실시간 카메라 + HTTP serve + 스쿼트 카운터
│   ├── squat_counter.py             rep 카운팅 상태 머신 (UP↔DOWN)
│   └── introspect_onnx.py           AI Hub precompiled QNN ONNX 진단 (기각 검증용)
├── benchmarks/              JSON 측정 결과 저장 (현재 비어있음, --json 옵션 추가 예정)
├── data/                    테스트 이미지/비디오 (현재 비어있음)
├── src/                     (예약 — 향후 라이브러리화 시 사용)
├── SESSION_SUMMARY_*.md     세션 종료 시 누적 요약
└── .gitignore               models/data/benchmarks/Python/editor 제외
```

## 4. 외부 의존성

| 의존 | 호스트 | 디바이스 |
|---|---|---|
| Docker (Ubuntu 22.04) | 본 라인 진입 위해 필수 | X |
| Python 3.10 | 호스트 컨테이너 안 (Dockerfile) | venv-unoq (3.13.5) |
| ai-edge-litert | 2.1.1 (호스트), 2.1.5 (디바이스) — ABI 호환 | 이미 설치 |
| opencv-python(-headless) | 4.x | 4.13 (이미 설치) |
| numpy | 2.1.3 (호스트), 2.5 (디바이스) | 이미 설치 |
| USB UVC 카메라 (SU200) | X (호스트는 사용 X) | 운영 모드(SSH)에서 사용 |

디바이스 venv-unoq는 vision/ASR 라인과 공유 — 본 라인 신규 설치 없음.

## 5. 운영 모드 (USB 토폴로지)

vision/ASR 라인과 동일 패턴 — [unoq-companion-robot 결정](../../vision/docs/history/2026-06-25_03_usb_topology_decision.md) 적용.

| 모드 | 토폴로지 | 통신 | 본 라인 활용 |
|---|---|---|---|
| **ADB** | PC ↔ USB-C ↔ UNO Q (직접) | `adb shell/push/pull` | 모델 push, introspection, 자료 회수 |
| **SSH** | UNO Q ↔ 허브 ↔ 카메라 + 마이크. PC는 LAN | `ssh arduino@<IP>` | 실시간 카메라 추론, HTTP MJPEG serve |

## 6. 카메라 자세 권장 (실측 기반)

| 항목 | 본 측정 자세 | 인식 결과 |
|---|---|---|
| 렌즈 높이 | 지면 10 cm | 정면 자세 인식 우수 |
| 광축 각도 | 정면(수평)에서 위로 ~20° | 정면 무릎 각도 안정 측정 |
| 측면 자세 | — | **다리 perspective 압축** — 사용자가 더 깊게 굽혀야 down_th 통과 |
| 후면 자세 | — | **pose는 잡힘, 카운트는 안 됨** — hip-knee-ankle 일직선 가까움 |

→ 본 작자세는 정면 인식에 최적화. 측면/후면은 알고리즘 보완 필요 (§7 참조).

## 7. 알고리즘 한계 + 개선 방향

본 라인 스쿼트 카운터는 **무릎 각도 단일 신호** 기반. 자세한 흐름: [`04_squat_algorithm.md`](04_squat_algorithm.md).

| 한계 | 원인 | 개선안 |
|---|---|---|
| 측면 — 더 깊게 굽혀야 카운트 | perspective로 측정값이 실제보다 큼 (90° → 보임 ~120°) | **A. 방향 인식 → 임계 동적 조정** |
| 후면 — pose는 잡지만 카운트 거의 X | hip-knee-ankle 일직선에 가까움 → 임계 절대 못 내려감 | **B. 머리(nose) y 좌표 낙차** 보조 카운팅 |
| 발목 미검출 시 상태 freeze | conf 0.3 임계 → 양쪽 발목 None이면 카운터 정지 | **C. 엉덩이 각도** (shoulder-hip-knee, 발목 무관) 보조 |

세 신호 OR 결합 + 사이클 중복 방지로 정면/측면/후면 모두 카운팅 가능.

## 8. 다음 단계 후보

### 8-1. 소프트웨어 (UNO Q 단독)

| 우선순위 | 항목 |
|---|---|
| 1 | **알고리즘 A+B+C 통합** — 방향 인식 + 머리 낙차 + 엉덩이 각도 OR 카운팅 (측면/후면 신호 부족 해결) |
| 2 | **Soak test** ≥10 min — thermal plateau + 합격 마진 정량 확정 (현재 71°C로 1°C 초과) |
| 3 | **--threads 3** 또는 환기 개선 — 합격 마진 -2~3°C 확보 |
| 4 | Vision + Pose 동시 운영 자원 청사진 (CPU 합산 602% 경합) |
| 5 | JSON benchmark 저장 (`--json` 옵션 — 멘토 06 형식) |

### 8-2. 하드웨어 통합 (STM32U585) — 2026-06-27 멘토 미팅 후 확정

본 작품 마무리 단계로 **카메라 PTZ 추적 → 사람 위치 자동 인식** 진행. 자율 추적(본체 이동)은 폐기.

| 단계 | 안 | 부담 | 결과 |
|---|---|---|---|
| **검증 PoC** | **PTZ 서보 + visibility 기반 추적** (Shawn Hymel 프로젝트 기반) | $15, 3~4일 | "Pose 추적용 카메라 각도 자동 탐색 가능?" 가설 검증. **본 작품 메인 외 임시 작업** |
| (PoC 통과 시) 정식 통합 | PTZ를 본 작품 v1.2로 통합 | — | 본 작품 마무리 기능 |
| MCU 트리거 추가 | rep 이벤트 → LED/효과음/모터 반응 | (펌웨어에 추가만) | 교감 인터랙션 |
| (폐기) | ~본체 자율 추적~ | — | 멘토 미팅에서 본 작품 범위 외 결정 |

PTZ 검증 작업은 **본 작품 핵심 기능 추가가 아니라 검증 단계**. 자세한 정의 + 가설 + 검증 기준: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md).

검증 실패 시 본 작품(헬스케어 봇 + 스쿼트 카운팅 v1)은 PTZ 없이 그대로 시연 가능.

자세한 결정 과정: [`issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md), [`history/2026-06-27_11_mentor_meeting_outcomes.md`](history/2026-06-27_11_mentor_meeting_outcomes.md).

## 9. 관련

- 후보 결정: [`01_model_candidates.md`](01_model_candidates.md)
- Quickstart: [`02_quickstart_pose.md`](02_quickstart_pose.md)
- 운영 런북: [`03_runbook_camera_serve.md`](03_runbook_camera_serve.md)
- 알고리즘 가이드: [`04_squat_algorithm.md`](04_squat_algorithm.md)
- 멘토 보고서: [`05_mentor_report_pose_line.md`](05_mentor_report_pose_line.md)
- 세션 컨텍스트: [`../SESSION_SUMMARY_2026-06-27.md`](../SESSION_SUMMARY_2026-06-27.md)
