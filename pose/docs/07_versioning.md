# 버전관리 (Pose 라인)

본 문서는 본 라인의 버전 부여 규칙 + v1 베이스라인 정의. 2026-06-27 멘토 미팅 결정 기반.

## 0. v1 베이스라인 (2026-06-27 동결)

| 항목 | v1 시점 상태 |
|---|---|
| 모델 | MoveNet Thunder INT8 TFLite (6.80 MB, Apache-2.0 + CC BY 4.0) |
| 디바이스 | Arduino UNO Q (QRB2210, Cortex-A53 ×4, 4 GB RAM, 32 GB eMMC) |
| 런타임 | `ai-edge-litert` 2.1.5 + XNNPACK CPU |
| 입력 | 카메라 640×480 → letterbox 256×256 uint8 |
| 출력 | [1, 1, 17, 3] float32 — 17 keypoint × (y_norm, x_norm, conf) |
| 알고리즘 | 무릎 각도 (hip-knee-ankle) + 좌/우 better 선택 + Hysteresis FSM (down_th=100°, up_th=140°, dwell=200ms) |
| 카운팅 검증 | 실측 9~13 rep, deepest 28~66° |
| 측정 (디바이스) | e2e 9.55~9.69 FPS, invoke p50 80ms, CPU 311~316%, RSS 95 MB, thermal plateau ~71°C |
| 운영 모드 | ADB (자동화) + SSH (카메라 라이브 + HTTP serve) |
| 자료 | docs 00~07 + history 11 + issues 5 |

## 1. 버전 부여 규칙

| 버전 변경 | 트리거 |
|---|---|
| **major (v1 → v2)** | 모델 교체, 입력/출력 형식 변경, 디바이스 변경, stack 교체 |
| **minor (v1 → v1.1)** | 알고리즘 신호 추가 (A/B/C 통합 등), 새 모드 추가 (감시 모드 등), 큰 옵션 추가 |
| **patch (v1 → v1.0.1)** | 임계값 조정, 함정 수정, docs 갱신, 측정 누적 |

## 2. 계획된 후속 버전

| 버전 | 내용 | 시점 |
|---|---|---|
| **v1** | 본 시점 — 현재 베이스라인 | **2026-06-27 동결** |
| v1.1 | A+B+C 다중 신호 카운터 통합 | 본 사이클 안 (소프트웨어, UNO Q 단독) |
| v1.2 | PTZ 서보 통합 (STM32U585 + UART) | 본 작품 마무리 |
| v1.3 | MCU 트리거 (rep → LED/효과음) | PTZ 통합 후 |
| v1.4 | 감시 모드 추가 (keypoint 다른 해석) | 시연 시점 |
| v2 | (잠재) 모델 교체 / 운동 종류 다양화 | 멘토 보고 사이클 외 |

## 3. 동결 자료 (v1)

본 시점 자료 동결 위치 (변경 시 다른 사본으로):

### 코드
- `scripts/inspect_movenet_thunder.py`
- `scripts/infer_camera_pose.py`
- `scripts/squat_counter.py`

### 모델
- `models/movenet_thunder_int8.tflite` (6.80 MB)

### docs
- `docs/00_project_blueprint.md`
- `docs/01_model_candidates.md`
- `docs/02_quickstart_pose.md`
- `docs/03_runbook_camera_serve.md`
- `docs/04_squat_algorithm.md`
- `docs/05_mentor_report_pose_line.md`
- `docs/06_hardware_housing_design.md`
- `docs/07_versioning.md` (본 문서)

### 측정 자료
- `docs/history/2026-06-27_03_movenet_thunder_int8_device_pass.md`
- `docs/history/2026-06-27_04_pose_camera_e2e_pass.md`
- `docs/history/2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md`

## 4. 동결 ZIP 권장

v1 시점 동결을 명시적 ZIP으로 보관:

```powershell
cd C:\Project\unoq-companion-robot\pose
Compress-Archive -Path docs, scripts, models, docker, SESSION_SUMMARY_*.md `
                 -DestinationPath ..\unoq-pose-v1-2026-06-27.zip
```

또는 git init 시작 + tag:

```bash
cd /c/Project/unoq-pose
git init
git add .
git commit -m "v1 baseline (2026-06-27 mentor meeting)"
git tag v1
```

## 5. 다른 라인과의 동기

v1 베이스라인은 3 라인 동시 동결:

| 라인 | v1 시점 상태 |
|---|---|
| Vision (`unoq-companion-robot`) | YOLOv8n int8, e2e 9.23 FPS, 70.8°C |
| ASR (`unoq-asr`) | Whisper Tiny.en TFLite, e2e 3.18 s |
| **Pose (`unoq-pose`, 본 라인)** | **MoveNet Thunder INT8, e2e 9.6 FPS, 13 rep 카운팅** |

ASR 라인은 멘토 미팅에서 **가벼운 모델 교체 + 인터럽트 지원** 결정 — v2 진입 후보 (별도 라인 history 참조).

## 6. 관련

- 멘토 미팅 결과: [`history/2026-06-27_11_mentor_meeting_outcomes.md`](history/2026-06-27_11_mentor_meeting_outcomes.md)
- 청사진: [`00_project_blueprint.md`](00_project_blueprint.md)
- 멘토 보고: [`05_mentor_report_pose_line.md`](05_mentor_report_pose_line.md)
