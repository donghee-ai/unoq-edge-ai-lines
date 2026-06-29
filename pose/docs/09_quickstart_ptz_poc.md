# Quickstart — PTZ PoC

본 문서는 [`../ptz/`](../ptz/) 폴더 PoC를 0→1시간 안에 빌드 + 실행 + 측정까지 도달하는 절차. 본 작품 메인 라인 외부 검증 단계 — 자세한 정의: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md).

## 0. 사전 조건

| 항목 | 확인 |
|---|---|
| Arduino UNO Q | PC와 같은 LAN |
| Arduino App Lab 1회 실행 | 펌웨어 최신 |
| SSH 접속 | `ssh arduino@<UNO_Q_IP>` 가능 |
| 하드웨어 | SG90 서보 2개 (pan/tilt) + WS2812B LED ring 12 + USB UVC 카메라 + 3D 프린팅 마운트 |
| 모델 | `models/movenet_thunder_int8.tflite` (Pose v1 자산) |

서보 + LED 핀 매핑 (sketch.ino):
- PAN servo: GPIO 9
- TILT servo: GPIO 10
- WS2812B LED ring: ws2812b-bitbang.h 기본 핀 (코드 확인)

## 1. 3D 프린팅 (선택 — 하드웨어 사전 준비)

본 PoC가 활용하는 STL: **ShawnHymel mechanical/** (MIT)
- `base.stl`, `camera-mount.stl`, `gears.stl`, `holder.stl`
- `top-with-led-ring.stl`, `spacers-*.stl` (3종)
- 원본: <https://github.com/ShawnHymel/face-expression-detection-robot/tree/main/mechanical>

본 작품 SU200 카메라가 Shawn webcam과 다르면 `camera-mount.stl`만 FreeCAD 원본(`spacers.FCStd` 참조 → 본 작품 카메라용 신규 작성) 수정 필요.

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

## 9. 본 작품 메인 라인과 동시 운영

본 PoC는 Arduino UNO Q App. 본 작품 메인 라인 (`scripts/infer_camera_pose.py`)은 venv-unoq + SSH script.

**동시 운영 금지** — 같은 카메라 device를 두 프로세스가 사용 시도하면 충돌. 본 PoC 측정 중에는 메인 라인 script 정지.

PoC 측정 후 즉시 본 작품 메인 시연 가능 — `arduino-app-cli app stop` 후 `python3 infer_camera_pose.py ...` 실행.

## 10. 관련

- PoC 정의 + 가설: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md)
- 코드 README: [`../ptz/README.md`](../ptz/README.md)
- 본 작품 메인 (PTZ 무관): [`02_quickstart_pose.md`](02_quickstart_pose.md)
- Shawn 원본: <https://github.com/ShawnHymel/face-expression-detection-robot>
