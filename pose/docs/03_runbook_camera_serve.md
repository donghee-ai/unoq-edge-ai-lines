# 운영 런북 — 카메라 + HTTP serve 시나리오별 명령

본 문서는 본 라인을 실제 사용/검증/측정할 때의 명령 모음입니다. 시나리오별로 명령을 그대로 복사해서 쓰는 형태. 사전 준비 + 첫 실행은 [`02_quickstart_pose.md`](02_quickstart_pose.md) 선행.

## 0. 공통 — SSH 진입

```bash
ssh arduino@192.168.0.45
source ~/venv-unoq/bin/activate
cd ~/pose_test
```

이후 모든 명령은 위 prompt 안에서 실행.

## 1. 시나리오 — 라이브 디버그 (HTTP serve)

```bash
python3 scripts/infer_camera_pose.py \
    models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 --print-every 10
```

→ PC 브라우저: `http://192.168.0.45:8080/`

stats JSON 필드 (500ms 갱신):
```json
{
  "fps": 10.7,
  "stage_ms": { "capture":, "preprocess":, "inference":, "postprocess":, "draw": },
  "knee_angle_deg": { "left": 95.0, "right": 168.0 },
  "depth_state":    { "left": "Parallel", "right": "Standing" },
  "system": {
    "cpu_pct_process": 295.0,
    "cpu_pct_per_core_avg": 73.8,
    "rss_mb": 94.0,
    "temp_c_max": 65.5,
    "num_cores": 4
  },
  "dropped_frames": 0,
  "camera_actual": [640, 480]
}
```

## 2. 시나리오 — 스쿼트 카운터 (rep counting)

```bash
python3 scripts/infer_camera_pose.py \
    models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 \
    --count --side better --down-th 100 --up-th 140 --min-dwell-ms 200
```

옵션 의미:
- `--count`           : 카운터 활성화
- `--side better`     : 좌/우 둘 다 있으면 평균, 한쪽만 있으면 그쪽 사용
- `--down-th 100`     : 무릎 각도 100° 미만 → DOWN 상태 진입
- `--up-th 140`       : 무릎 각도 140° 초과 → UP 상태 복귀 (1 rep 완료)
- `--min-dwell-ms 200`: 상태 전환 후 최소 유지 시간 (떨림으로 인한 false positive 방지)

영상 우상단에 `REPS N [UP/DOWN]` 큰 글자 표시. 콘솔에 `★ REP #N  bottom=XX°` 출력.

stats JSON에 추가 필드:
```json
"squat": {
  "state": "UP",
  "reps": 12,
  "deepest_overall_deg": 67.0,
  "last_rep_min_deg": 84.0,
  "current_down_min_deg": null,
  "thresholds_deg": { "down": 100, "up": 140 }
}
```

### 임계 튜닝 가이드

| 자세 깊이 | 권장 down_th |
|---|---|
| Quarter squat | 130° |
| Half squat | 110° |
| **Parallel squat (표준)** | **100°** ★ |
| ATG (full depth) | 80° |

up_th는 down_th보다 30~40° 높게 (hysteresis) 떨림에서 카운트 폭발 방지.

## 3. 시나리오 — 카메라 없이 latency 측정 (ADB 모드)

USB-C 직접 PC 연결 후 ADB로:

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
& $ADB shell "source /home/arduino/venv-unoq/bin/activate && \
  MODEL_PATH=/home/arduino/pose_test/models/movenet_thunder_int8.tflite \
  python3 /home/arduino/pose_test/scripts/inspect_movenet_thunder.py"
```

→ 빠른 회귀 검증 (모델 교체/스레드 변경 시).

## 4. 시나리오 — 자료 회수 (ADB pull)

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

# 디바이스에서 호스트로 — 측정 JSON / 로그 / 캡처 등
& $ADB pull "/home/arduino/pose_test/benchmarks/" "C:\Project\pose\benchmarks\device\"
```

(현재 `--json` 옵션 미구현, JSON 저장 기능 후속 추가 예정.)

## 5. 시나리오 — 카메라 진단

`L=? R=?`가 지속되거나 카메라가 안 잡힐 때:

```bash
# 카메라 노드 + 드라이버 확인
ls /dev/video*
v4l2-ctl --list-devices
v4l2-ctl --list-formats-ext -d /dev/video0

# UVC 드라이버 재로드 (USB 인식 끊김 복구)
sudo modprobe -r uvcvideo
sudo modprobe uvcvideo
sleep 2
ls /dev/video*
```

기대 — SU200 USB UVC 카메라의 경우:
```
Type: Video Capture (single-plane)
Driver: uvcvideo
MJPG : 1280x720 30 fps / 640x480 25 fps
YUYV : 1280x720 10 fps / 640x480 25 fps
```

`Type: Video Capture Multiplanar` + `NV12/Q08C/H264` 등이 보이면 Qualcomm Venus 코덱 노드 — USB UVC 카메라 아님. USB 재연결 + uvcvideo 재로드 후 정상 UVC 노드 확인.

## 6. 시나리오 — Soak test (장시간 thermal plateau 확인)

```bash
python3 scripts/infer_camera_pose.py \
    models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 \
    --print-every 60 \
    --max-frames 0    # 0 = 무제한
```

권장 측정 시간:
- 10 min — thermal plateau 1차 확인
- 30 min — 합격 기준 안정 마진 확인

종료 후 SUMMARY의 `temp_peak_c`가 합격선(70°C) 이내인지 확인. ≥ 68°C면 보수적으로 추가 측정 권장.

## 7. 보안 / 운영 주의

| 항목 | 권고 |
|---|---|
| HTTP serve 인증 | 없음 (DEBUG 전용) — 로컬 LAN 외부 노출 금지 |
| 영상 저장 | default OFF — `--save-dir` 같은 opt-in 옵션 미구현 (필요 시 추가) |
| 토큰/.env | `.env`는 `.gitignore` 차단. 본 라인은 토큰 미사용 (vision/asr 일관성 보존만) |
| 디바이스 SSH key | 현재 비밀번호 인증 (Public 전환 시 key 인증 + 비번 비활성 권장) |

## 8. 실측 사례 (참고)

3회 측정 누적 패턴:

| # | 시간 | rep | deepest | temp_peak | 비고 |
|---|---|---|---|---|---|
| 1 | 136 s | — (카운터 OFF) | — | 68.6°C | 단기 e2e |
| 2 | 294 s | **13** | 28° | **71.4°C** ⚠ | sustained, ATG 위주 |
| 3 | 157 s | **9** | 46° | 68.6°C | 측정 자세 미세 조정 |

관찰:
- **카운터 신뢰 일관** — 사이클 명확하면 누락 없이 카운팅
- **검출 패턴**: 양쪽 모두 잡히는 프레임은 드물고, 한쪽만 자주 검출 — `--side better`가 결정적
- **thermal**: 단기(150s 이내)는 70°C 미만, sustained(5분+)는 71°C 진입 — soak 후속 측정 권장
- **카메라 자세**: 정면(렌즈 10cm + 위로 20°)에서 정확. 측면/후면은 알고리즘 한계 ([`04_squat_algorithm.md`](04_squat_algorithm.md) §7)

## 9. 관련

- 청사진: [`00_project_blueprint.md`](00_project_blueprint.md)
- 모델 결정: [`01_model_candidates.md`](01_model_candidates.md)
- Quickstart: [`02_quickstart_pose.md`](02_quickstart_pose.md)
- 알고리즘: [`04_squat_algorithm.md`](04_squat_algorithm.md)
- 멘토 보고: [`05_mentor_report_pose_line.md`](05_mentor_report_pose_line.md)
- 함정 모음: [`issues/`](issues/)
- 측정 누적: [`history/`](history/)
