# Quickstart — PTZ PoC

본 문서는 [`../ptz/`](../ptz/) 폴더 PoC를 0→1시간 안에 빌드 + 실행 + 측정까지 도달하는 절차. 본 작품 메인 라인 외부 검증 단계 — 자세한 정의: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md).

## 0. 사전 조건

| 항목 | 확인 |
|---|---|
| Arduino UNO Q | PC와 같은 LAN |
| Arduino App Lab 1회 실행 | 펌웨어 최신 |
| SSH 접속 | `ssh arduino@<UNO_Q_IP>` 가능 |
| 하드웨어 (최소 셋) | SG90 서보 2개 (pan/tilt) + 외부 5V 어댑터 ≥1A + 점퍼 와이어 ~10 + 양면테이프(데모용 카메라 고정) + USB UVC 카메라 (보유 SU200) + 3D 프린팅 STL 7개 |
| 하드웨어 (선택) | WS2812B LED ring 12 (visibility 색상 시각화 — 없어도 회전 동작 OK) |
| 모델 | `models/movenet_thunder_int8.tflite` (Pose v1 자산) |

서보 + LED 핀 매핑 (sketch.ino):
- PAN servo: GPIO 9
- TILT servo: GPIO 10
- WS2812B LED ring: ws2812b-bitbang.h 기본 핀 (코드 확인)

부품 비용 (대략): SG90 ×2 (~$6) + 5V 어댑터 (~$5) + 점퍼 (~$1) + 3D 출력 = **~$12 + 출력 비용**.
서보 토크 부족 시 MG90S (메탈기어, 2.5 kg·cm, ~$5/개) 업그레이드.

## 1. 3D 프린팅 (PoC 단계 — Shawn 원본 7개 다 출력)

본 PoC가 활용하는 STL: **ShawnHymel mechanical/** (MIT) — 원본: <https://github.com/ShawnHymel/face-expression-detection-robot/tree/main/mechanical>

| STL | 출력? | 비고 |
|---|---|---|
| `base.stl` | 필수 | 바닥 받침 |
| `holder.stl` | 필수 | 서보 고정 프레임 |
| `gears.stl` | 필수 | tilt 회전 기어 |
| `top-with-led-ring.stl` | 출력 | LED 생략 시에도 평면 top 역할 |
| `camera-mount.stl` | 출력 | SU200 비호환 시 데모용으로 테이프 고정 |
| `spacers-*.stl` (3종) | 출력 | 높이 맞춤 |

**PoC 단계 FreeCAD 작업 생략** — `camera-mount.stl`을 SU200 치수에 맞춰 재모델링하는 시간을 데모로 회수. 출력 후 안 맞으면 데모용으로 테이프 고정. 정식 v1.x 통합 시 SU200 전용 mount STL 신규 작성 검토.

상세 의사결정: [`history/2026-06-29_06_ptz_pragmatic_poc_pivot.md`](history/2026-06-29_06_ptz_pragmatic_poc_pivot.md)

## 2. 모델 파일 복사

```bash
# 본 작품 폴더에서
cp models/movenet_thunder_int8.tflite ptz/python/movenet_thunder_int8.tflite
```

## 3. UNO Q에 push

```powershell
# PowerShell (Git Bash는 디바이스 경로 변환 함정 — PowerShell 권장)
$UNO = "<UNO_Q_IP>"   # 예: 192.168.0.45

ssh arduino@$UNO 'mkdir -p ~/ArduinoApps/ptz-poc'
scp -r C:\Project\pose\ptz\* arduino@${UNO}:~/ArduinoApps/ptz-poc/
```

## 4. UNO Q에서 실행

```bash
ssh arduino@<UNO_Q_IP>

# 첫 빌드 + 실행 (브릭/패키지 자동 설치)
arduino-app-cli app start ~/ArduinoApps/ptz-poc

# 로그 확인 (별도 터미널 또는 동일 SSH에서 백그라운드 후)
arduino-app-cli app logs ~/ArduinoApps/ptz-poc
```

기대 로그:
```
Model loaded: movenet_thunder_int8.tflite
  input  : [1, 256, 256, 3] uint8
  output : [1, 1, 17, 3] float32
Camera native: 640x480
Inference loop start
Pose: (0.42, 0.51) vis=0.85 track=0
  STAY (visibility >= track threshold)
Pose: (0.65, 0.48) vis=0.62 track=1
```

## 5. 브라우저 디버그

```
http://<UNO_Q_IP>/ptz-poc/
```

→ Web UI에 다음 표시:
- 라이브 카메라 frame + skeleton + visibility 점수
- "TRACK" / "STAY" 상태
- FPS / inference latency

## 6. 측정 시나리오 (가설별)

### H1 — visibility 변동
1. 카메라 정면 + 사람 정면 → visibility 기록
2. 사람 측면으로 이동 → visibility 기록
3. 사람 후면 → visibility 기록
- 합격선: 정면 vs 후면 점수차 ≥ 0.3

### H2 — 자동 추적
1. 사람이 frame 한쪽 (예: 우측 끝)으로 이동
2. 5초 동안 카메라 동작 관찰
- 합격선: 5초 내 사람이 frame 중심에 위치

### H3 — Stop condition
1. 사람이 정면 자세 잘 보이는 위치로 이동 → visibility ≥ 0.7
2. 카메라가 멈추는지 확인
3. 사람이 다시 옆으로 이동 → 추적 재시작
- 합격선: 임계 통과 시 즉시 STAY, 임계 미달 시 즉시 TRACK 재시작

### H4 — 카운팅 정확도
별도 실험 — 본 작품 메인 라인(`infer_camera_pose.py --count`) 측정 트레이스와 PoC 동작 영상 비교.
- 합격선: PTZ ON 시 측정 누락 ≥ 20% 감소

## 7. 트러블슈팅

| 증상 | 원인 + 해결 |
|---|---|
| `Model loaded` 안 나오고 즉시 종료 | `ai-edge-litert` 미설치 → `pip install ai-edge-litert` (UNO Q app build 자동) |
| 카메라 안 잡힘 | `requires_devices: [camera]` 매니페스트 확인 + `ls /dev/video*` 디바이스 확인 |
| `Bridge.call error` | sketch.ino 업로드 안 됨 또는 RouterBridge 초기화 실패 — App Lab 1회 실행 후 재시도 |
| 서보 떨림 | PWM 신호 불안정 — 외부 전원 5V 권장 (UNO Q 5V 핀은 전류 부족 가능) |
| LED ring 안 켜짐 | WS2812B 핀 매핑 + 전원 확인 (5V 직결) |
| visibility 항상 0 | 카메라 frame에 사람 없음 또는 conf 임계 너무 높음 — `CONF_TH = 0.2` 시도 |

## 8. PoC 종료 + 결과 회수

```bash
# 종료
arduino-app-cli app stop ~/ArduinoApps/ptz-poc

# 로그 회수 (호스트로)
ssh arduino@<UNO_Q_IP> 'arduino-app-cli app logs ~/ArduinoApps/ptz-poc' > ptz-poc-log-$(date +%Y%m%d).txt
```

결과는 [`history/2026-06-29_*.md`](history/) 신규 파일에 기록 — H1~H4 합격 여부 + 측정 trace + 결정 (v1.2 통합 / 보류 / 폐기).

## 9. 본 작품 메인 라인과의 관계 — 통합 우선 진로 (2026-06-29 변경)

### 9-1. 진로 변경

직전 계획: 분리 PoC (`pose/ptz/`)에서 H1~H4 검증 → 성공 시 본 작품 통합.

**본 결정**: 분리 PoC 단계 생략 — `pose/scripts/infer_camera_pose.py`에 처음부터 직접 통합. `ENABLE_PTZ` 토글로 PTZ ON/OFF.

근거: MoveNet은 분리 App 안에도 이미 내장되어 카메라 점유 충돌이 발생. 통합하면 MoveNet 1회 invoke로 카운팅 + PTZ 둘 다 처리. 토글 한 줄로 분리 PoC의 "실패 시 무손상" 가치도 보장.

### 9-2. 통합 코드 진입점

```python
# pose/scripts/infer_camera_pose.py (통합 후)
from ptz_helpers import visibility_score, person_center_normalized

ENABLE_PTZ = True   # False면 PTZ 비활성, 기존 카운팅만

while True:
    frame = capture()
    kp = movenet.invoke(letterbox(frame, 256))   # 1회 invoke

    # 스쿼트 카운터 (기존)
    angle = knee_angle(kp, side="better")
    rep_event = counter.update(angle, time.time() * 1000)

    # PTZ (신규)
    if ENABLE_PTZ:
        vis = visibility_score(kp)
        x_n, y_n = person_center_normalized(kp, h, w)
        should_track = vis < 0.7
        if x_n is not None:
            Bridge.call("track_pose", x_n, y_n, vis, should_track)
```

### 9-3. 자산 재사용

`pose/ptz/python/main.py`의 helper 함수는 `pose/scripts/ptz_helpers.py`로 추출:

- `letterbox_square()`
- `unletterbox_kp()`
- `visibility_score()`
- `person_center_normalized()`

STM32 측 `sketch.ino`는 **변경 없음** — Python 측만 통합.

`pose/ptz/python/main.py`는 보존 — fork 출처 표기 + 비교 검증용.

### 9-4. H4 측정 — 토글로 직접 비교

```bash
# PTZ OFF — 기존 카운팅만
ENABLE_PTZ=False python3 infer_camera_pose.py ...

# PTZ ON — 추적 + 카운팅
ENABLE_PTZ=True python3 infer_camera_pose.py ...
```

같은 환경에서 즉시 비교 측정 가능 — 분리 PoC 대비 측정 효율 향상.

상세 의사결정 + 트레이드오프 표: [`history/2026-06-29_06_ptz_pragmatic_poc_pivot.md`](history/2026-06-29_06_ptz_pragmatic_poc_pivot.md)

## 10. 관련

- PoC 정의 + 가설: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md)
- 코드 README: [`../ptz/README.md`](../ptz/README.md)
- 본 작품 메인 (PTZ 무관): [`02_quickstart_pose.md`](02_quickstart_pose.md)
- Shawn 원본: <https://github.com/ShawnHymel/face-expression-detection-robot>
