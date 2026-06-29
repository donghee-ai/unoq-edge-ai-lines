# 멘토 보고 — UNO Q Pose 라인 (스쿼트 측정 + 카운팅)

**작성일**: 2026-06-27
**대상 디바이스**: Arduino UNO Q (Qualcomm QRB2210, Cortex-A53 ×4 @ 2.0 GHz, 4 GB LPDDR4, 32 GB eMMC, **NPU/HTP 없음**)
**런타임**: Linux 7.0 + Python 3.13.5 + `ai-edge-litert` 2.1.5 (TFLite + XNNPACK CPU delegate)

## 한 줄 요약

> Google MoveNet Thunder INT8 TFLite(6.8 MB) 채택 → UNO Q CPU only에서 **e2e 9.57~9.69 FPS, RSS 95 MB, thermal plateau ~71°C**. **17 keypoint 출력 + 무릎 각도 hysteresis 상태 머신**으로 스쿼트 카운팅 정확 동작(실측 3회 9·13 rep, deepest 28~46°). 정면 인식 우수, **측면/후면은 알고리즘 단일 신호 한계 — 다중 신호(머리 낙차/엉덩이 각도) 통합 후속 진행 예정**.

---

## 1. 모델 선정

### 1-1. 채택 — MoveNet Thunder INT8 (Google)

| 항목 | 값 |
|---|---|
| 출처 | TensorFlow Hub (`tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4`) |
| 형식 | TFLite (full int8 PTQ, 텐서 87% 양자화) |
| 크기 | 6.80 MB |
| 입력 | `[1, 256, 256, 3]` uint8 (image 0-255) |
| 출력 | `[1, 1, 17, 3]` float32 — 1 person × 17 keypoint × (y_norm, x_norm, confidence) |
| 라이선스 | Apache-2.0 (code) + CC BY 4.0 (model) |
| 디바이스 런타임 | `ai-edge-litert` + XNNPACK delegate (chipset 비종속) |

### 1-2. 채택 근거 — 4 가지

1. **stack 일치**: vision YOLOv8n int8 / ASR Whisper Tiny.en TFLite와 **동일 ai-edge-litert + XNNPACK CPU** 경로. 디바이스에 새 패키지 설치 없음.
2. **chipset 비종속**: 표준 TFLite — UNO Q(QRB2210) CPU에서 그대로 동작. QNN EP / HTP NPU 의존 없음.
3. **합격선 마진**: 입력 256×256(vision 320×320보다 작음) + 단일 모델 1 invoke → e2e 9.7 FPS로 합격선 8 FPS 통과.
4. **각도 측정 충분**: 17 keypoint에 hip/knee/ankle 모두 포함 → 무릎 굽힘 각도(hip-knee-ankle) 직접 계산 가능.

### 1-3. 기각 — Qualcomm AI Hub precompiled QNN ONNX

AI Hub에서 사전 다운로드한 `mediapipe_pose-precompiled_qnn_onnx-w8a8-qualcomm_snapdragon_x2_elite.zip` 검증 결과 **UNO Q 호환 불가**:

| 차단 | 사유 |
|---|---|
| ONNX wrapper IR v13 | 호스트 onnxruntime 1.22의 max IR v10 초과 |
| EPContext 노드 (source=QNN) | ONNX Runtime **QNN Execution Provider** 필요 + 외부 `*_qairt_context.bin` (X2 Elite HTP v8.1 사전 컴파일) 로드 |
| HTP NPU | **QRB2210에 HTP 없음** → QNN EP 깔아도 컨텍스트 실행 불가 |

→ 같은 양자화(w8a8)라도 **포장 형식(TFLite vs precompiled QNN ONNX)**이 UNO Q 호환성을 결정. TFLite로 우회 → MoveNet 채택.

상세 진단: `docs/issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md`
분석 노트: `docs/history/2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md`

### 1-4. 후보 비교 (모두 chipset 비종속, Apache-2.0 계열)

| 후보 | 입력 | keypoint | 단계 | 본 라인 채택 여부 |
|---|---|---|---|---|
| **MoveNet Thunder INT8** ★ | 256×256 | 17 (COCO) | 1 단계 | **채택** |
| MoveNet Lightning INT8 | 192×192 | 17 (COCO) | 1 단계 | 2순위 폴백 (미시행) |
| OpenCV Zoo MediaPipe Pose INT8 BQ | 256×256 | 33 (BlazePose) | 2 단계 (detector + landmark) | 3순위 백업 (미시행) |

Thunder 1차 시도가 합격 → Lightning/BlazePose 폴백 불필요.

---

## 2. 성능 측정

### 2-1. 디바이스 e2e (USB UVC 카메라 SU200, 640×480 MJPG, threads=4)

| 측정 차수 | 시간 | frames | fps_eff | invoke p50 | cpu_peak | rss_peak | temp_peak | 카운팅 |
|---|---|---|---|---|---|---|---|---|
| 1 (단기 e2e) | 136 s | 1,320 | **9.69** | 80 ms | 316% | 95.0 MB | 68.6°C | OFF |
| 2 (sustained + 카운터) | 294 s | 2,813 | **9.55** | 87 ms | 311% | 95.5 MB | **71.4°C** ⚠ | **13 rep, deepest 28°** |
| 3 (자세 미세 조정) | 157 s | 1,505 | **9.57** | 87 ms | 312% | 95.6 MB | 68.6°C | **9 rep, deepest 46°** |

합격 평가 (vision/ASR과 동일 기준):

| 기준 | 합격선 | 측정 | 평가 |
|---|---|---|---|
| 디바이스 e2e FPS | ≥ 8 | 9.55~9.69 | ✓ |
| 디바이스 RSS | ≪ 2.4 GB (총 4 GB의 60%) | ~95 MB | ✓ |
| dropped_frames | 0 | 0 | ✓ |
| **thermal** | **≤ 70°C** | sustained 측정 **71.4°C** | **⚠ 초과** |

### 2-2. thermal 정량 — plateau ~71°C 도달

| 시점 (초) | 온도 (°C) | 비고 |
|---|---|---|
| 0 | 54.5 | start |
| 50 | 63.0 | 빠른 ramp |
| 100 | 65.8 | |
| 225 | 70.2 | ★ 70°C 첫 진입 |
| 270 | 71.1 | plateau 진입 |
| 295 | **71.4 (peak)** | plateau 형성 |

→ **단기 측정(~3 min)으로는 합격 보이지만, sustained(5 min+)에서 plateau 71°C 진입 — 합격선 1.4°C 초과**.

**FPS는 71°C에서도 안정** (10.6~11.0 유지) → 명확한 throttle 흔적 없음. soft fail로 판단, 마진 확보 방안 다음 사이클 진행.

### 2-3. 호스트 baseline (x86 Docker, threads=4)

| 측정 | 값 |
|---|---|
| invoke mean | 14.71 ms |
| invoke p50 | 14.03 ms |
| invoke p95 | 17.35 ms |
| FPS p50 | 71.3 |

→ 호스트 → 디바이스 약 **5.7× 느려짐** (vision YOLO 7.9×보다 양호, 입력 256<320 효과).

### 2-4. 자원 합산 (3 라인 동시 운영 추정)

| 시나리오 | CPU% | RSS MB | 합격 평가 |
|---|---|---|---|
| Vision YOLO continuous | 286 | 102 | OK |
| ASR Whisper burst (1회 invoke) | 212 | 357 | OK |
| Pose Thunder continuous | 311 | 95.5 | OK |
| **3 라인 동시 burst** | **809** | **555** | 4 코어 한계(400) 초과 — **이벤트 기반 운영 필수** |

→ Pose는 카메라 라이브로 continuous 운영. ASR/Pose는 vision과 동시 운영 시 **CPU 경합 발생** — 멀티라인 동시 청사진은 다음 측정 사이클에서 정량.

---

## 3. 알고리즘 구조

### 3-1. 4단계 파이프라인

```
[1] MoveNet 출력 [1,1,17,3]
         ↓
[2] 무릎 각도 = angle(hip, knee, ankle)   ← 좌/우 각각
         ↓
[3] 좌/우 → 1개 대표 각도 (better mode)
         ↓
[4] 상태 머신: UP ↔ DOWN, 한 사이클 = 1 rep
```

### 3-2. 무릎 각도 계산

```
ba = hip - knee
bc = ankle - knee
angle = arccos(ba · bc / (|ba| · |bc|))   → 0~180°
```

- confidence < 0.3인 keypoint 포함 시 → None (해당 측면 무효)
- 각도 의미:
  - **180°**: 다리 펴짐 (Standing)
  - **~90°**: Parallel squat (운동 표준)
  - **30~70°**: ATG (full depth)

### 3-3. 상태 머신 + Hysteresis

```
                angle < 100° + dwell ≥ 200ms
        UP ──────────────────────────────→ DOWN
         ↑                                   │
         │      angle > 140° + dwell ≥ 200ms │
         │            reps += 1              │
         └───────────────────────────────────┘
```

**Hysteresis (down_th=100° < up_th=140°)**: 임계 사이(100~140°)에서 떨림이 발생해도 상태 유지 → 카운트 폭발 방지.

**`min_dwell_ms = 200ms`**: 상태 전환 직후 짧은 시간 내 재전환 차단 → false positive 방지.

### 3-4. 좌/우 신호 융합 — `better` 모드

```
양쪽 검출 → 평균
한쪽만 검출 → 검출된 쪽 사용
양쪽 모두 미검출 → None → 상태 freeze
```

본 측정에서 사용자가 옆모습 가까운 자세 → 한쪽 다리 자주 occlusion. `better` 모드로 가능한 신호 모두 활용해 카운팅률 향상.

### 3-5. 검출 누락 강건성

매 프레임 독립이 아니라 **마지막 상태 + min_angle을 메모리에 누적**. 검출 누락 프레임(`update(None)`)은 즉시 return → 상태 freeze. 다음 검출에서 그대로 이어감.

**실측 trace 예** — 검출 누락 끼어도 사이클 인식:
```
[720] L=130 UP        [730] L=59  DOWN!     [733] L=48  DOWN (min 갱신)
[721]  ?    UP        [731]  ?    DOWN       [734]  ?    DOWN
                                              ...
                                              ★ REP #1  bottom=48°  (frame 747)
                                              [750] L=172 UP, reps=1
```

상태 머신 + 사이클 게이트 덕분에 매 100ms 단위 검출이 불완전해도 **2~3초 스쿼트 사이클 안에 임계 통과 샘플 1~2개만 있으면 카운팅 성공**.

---

## 4. 라이선스

### 4-1. 모델
- **MoveNet (Google)**: Apache-2.0 (code) + **CC BY 4.0** (model weights). 상업/시연/배포 모두 허용, 출처 표기 필요.
- 모델 카드: <https://www.tensorflow.org/hub/tutorials/movenet>

### 4-2. 본 라인 코드
- 본인 작성. 라이선스 미명시(필요 시 결정).

### 4-3. 의존 라이브러리 (호스트/디바이스 모두 일관 stack)
| 패키지 | 버전 | 라이선스 |
|---|---|---|
| `ai-edge-litert` (TFLite runtime) | 호스트 2.1.1 / 디바이스 2.1.5 | Apache-2.0 |
| `numpy` | 호스트 2.1.3 / 디바이스 2.5.0 | BSD-3 |
| `opencv-python(-headless)` | 호스트 4.x / 디바이스 4.13 | Apache-2.0 |
| `scipy` | 1.14+ | BSD-3 |

→ **모든 의존성 상업 호환 라이선스**. 벤더 락-인 없음.

### 4-4. vision/ASR 라인 라이선스 노트
| 라인 | 모델 | 라이선스 |
|---|---|---|
| Vision YOLOv8n int8 | Ultralytics YOLOv8 | **AGPL-3.0** (상업화 단계에서는 상용 라이선스 또는 대체 모델 검토 필요) |
| ASR Whisper Tiny.en | OpenAI Whisper | MIT |
| **Pose MoveNet Thunder** | **Google** | **Apache-2.0 + CC BY 4.0** (가장 깨끗) |

본 작품 시연/사내 노출 범위에선 무관. 상업 배포 단계 진입 시 vision YOLO 교체 검토 별도 진행.

---

## 5. 현재 한계 + 개선 방향

### 5-1. 알고리즘 — 단일 신호 한계

본 라인 카운터는 **무릎 각도 한 가지**에만 의존. 사용처별 동작:

| 사용 자세 | 인식 결과 | 원인 |
|---|---|---|
| **정면** | ✓ 안정 카운팅 | hip/knee/ankle 잘 보이고 각도 변화 명확 |
| **측면** | △ 사용자가 더 깊게 굽혀야 카운팅됨 | perspective로 무릎 각도가 실제보다 큼 (90° → 측정 ~120°) |
| **후면** | ✗ pose는 인식하나 카운트 거의 X | hip-knee-ankle 일직선에 가까워 각도가 항상 170~180° 사이 — **임계 100° 절대 못 내려감** |

### 5-2. 개선안 — 다중 신호 OR 결합

| 신호 | 검출 의존 | 후면 효과 |
|---|---|---|
| 무릎 각도 (hip-knee-ankle) | 발목 필요 | × |
| **엉덩이 각도** (shoulder-hip-knee) | 발목 무관 | △ |
| **머리(nose) y 좌표 낙차** | nose만 | **○** |

3개 카운터를 **사이클 OR** + 중복 방지 → 정면/측면/후면 모두 카운팅 + 방향 자동 인식으로 임계 동적 조정.

자세한 알고리즘 설계: `docs/04_squat_algorithm.md` §7~8

### 5-3. Thermal — 마진 1~3°C 확보 필요

| 방안 | 효과 추정 |
|---|---|
| **threads 4 → 3** | -2~4°C (FPS 일부 하락) |
| 환기 개선 | -1~3°C |
| JPEG quality 70→50 (debug serve) | -1~2°C |
| Frame skip (매 2 프레임만 invoke) | -3~5°C (FPS 절반) |
| passive heatsink (작은 알루미늄) | -5~10°C |

저비용 — `--threads 3` + 환기 정리 권장.

### 5-4. 카메라 PTZ — 물리적 보완 (2026-06-27 멘토 미팅 후 확정)

현재: 렌즈 10 cm 높이 + 위로 20° 기울임 → 정면 인식 우수.

| 단계 | 안 | 효과 + 부담 |
|---|---|---|
| 즉시 | 카메라 위치 무릎 높이(~40~50 cm)로 조정 | 측면/후면 인식률 향상, 비용 0 |
| **본 작품 마무리** | **PTZ 서보** (위/아래/양옆) — 카메라만 회전, 본체 정지 | 사람 frame 중심 유지. 서보 2 ($15), 0.5~1일. 안전 |
| (폐기) | ~본체 자율 추적~ | 멘토 미팅에서 본 작품 범위 외 — 모터/IMU 부담 회피 |

알고리즘 신호 보완(§5-2 A/B/C)과 PTZ는 **독립적이고 보완 관계** — 둘 다 적용 시 정면/측면/후면 모든 사용처에서 인식 안정성 최대.

---

## 6. 사용 시나리오 (운영 가이드)

### 6-1. 라이브 디버그 + 스쿼트 카운터 (SSH 모드)

```bash
ssh arduino@192.168.0.45
source ~/venv-unoq/bin/activate
python3 ~/pose_test/scripts/infer_camera_pose.py \
    ~/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 \
    --count --side better --down-th 100 --up-th 140 --min-dwell-ms 200
```

→ PC 브라우저: `http://192.168.0.45:8080/`
- 좌: MJPEG 스트림 (skeleton + 무릎 각도 + REPS 카운트 오버레이)
- 우: 500 ms 갱신 stats JSON (FPS / stage_ms / CPU / RAM / thermal / squat)

### 6-2. 빠른 회귀 검증 (ADB 모드)

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
& $ADB shell "source /home/arduino/venv-unoq/bin/activate && \
  MODEL_PATH=/home/arduino/pose_test/models/movenet_thunder_int8.tflite \
  python3 /home/arduino/pose_test/scripts/inspect_movenet_thunder.py"
```

→ invoke latency p50/p95 + 텐서 분포 + 출력 sanity (카메라 미사용).

---

## 7. 다음 단계 (우선순위)

### 7-1. 소프트웨어 (UNO Q 단독, 하드웨어 추가 X)

| # | 항목 | 효과 |
|---|---|---|
| 1 | **A+B+C 다중 신호 카운터 통합** | 측면/후면 카운팅 누락 직접 해결 |
| 2 | **Soak test ≥10 min + threads 3 시도** | thermal 마진 1~3°C 확보 (합격선 70°C 진입) |
| 3 | **Vision + Pose 동시 운영 자원 청사진** | 멀티라인 운영 정량 (CPU 합산 602% 경합 정량) |
| 4 | **`--json` benchmark 저장** | 측정 자료 누적 + 멘토 06 형식 |

### 7-2. 하드웨어 통합 (STM32U585 + 서보) — 2026-06-27 멘토 미팅 후 확정

| # | 단계 | 부담 |
|---|---|---|
| 5 | **PTZ PoC 검증** (Shawn fork, `ptz/` 폴더) — H1~H4 가설 측정 | $15, 3~4일 |
| 5.5 | **PoC 통과 시 v1.2 통합** — 메인 라인과 PTZ 한 프로세스로 합침 | 2일 |
| 6 | **MCU 트리거** (rep → LED/효과음/모터 반응) | 위 펌웨어에 추가만 |
| (폐기) | ~본체 자율 추적~ | 멘토 미팅에서 본 작품 범위 외 |

### 7-2-A. PTZ와 메인 라인 — 현재 별개 / 통합 진로

**현재 (PoC 검증 단계)**: PTZ(`ptz/`)와 메인 라인(Pose v1, `scripts/infer_camera_pose.py`)은 **완전 분리된 별도 프로세스**. 동시 운영 X (카메라 device 충돌). PoC 측정 시 메인 정지 필수.

**통합 후 (v1.2)**: 한 프로세스에서 카메라 1회 capture + MoveNet 1회 invoke → `squat_counter.update()` + `Bridge.call("track_pose", ...)` 동시. CPU/메모리 절약 + 단일 HTTP UI.

자세히: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md) §6-A/6-B/6-C

### 7-3. 시연 모드 확장 (멘토 미팅 추가 결정)

| 모드 | 내용 |
|---|---|
| **헬스케어 봇 (메인)** | 현재 — 스쿼트 카운팅 + 자세 코칭 |
| 감시 모드 (시연용) | 사람 검출 + 위치 추적 + 비정상 동작 알람 (같은 keypoint 다른 해석) |

### 7-4. 버전관리 (멘토 미팅 추가 결정)

본 시점 모든 라인 상태 = **v1 베이스라인**. 후속 변경은 v1.1 / v2 등 부여. 자세히: [`07_versioning.md`](07_versioning.md).

---

## 부록 — 자료 위치

- 청사진 + 디렉토리 구조: [`00_project_blueprint.md`](00_project_blueprint.md)
- 모델 후보 결정 + 각도 분석: [`01_model_candidates.md`](01_model_candidates.md)
- Quickstart (0→30분 진입): [`02_quickstart_pose.md`](02_quickstart_pose.md)
- 운영 런북 (시나리오별 명령): [`03_runbook_camera_serve.md`](03_runbook_camera_serve.md)
- **알고리즘 자세한 흐름 + 한계 + 개선안**: [`04_squat_algorithm.md`](04_squat_algorithm.md)
- 마일스톤 누적: [`history/`](history/)
- 함정 + 재발 방지: [`issues/`](issues/)

코드:
- `scripts/inspect_movenet_thunder.py` (호스트/디바이스 introspection + latency)
- `scripts/infer_camera_pose.py` (실시간 카메라 + HTTP serve + 스쿼트 카운터 통합)
- `scripts/squat_counter.py` (상태 머신 모듈)
