# Quickstart — Pose on UNO Q (원샷 실행 가이드)

본 문서는 본 라인 미경험자가 **30분 안에 디바이스에서 자신의 자세 인식 + 무릎 각도 출력**까지 도달하는 절차입니다. [00_project_blueprint.md](00_project_blueprint.md)의 결정에 따른 실제 명령 시퀀스.

## 0. 사전 조건 체크리스트

| 항목 | 명령 | 기대 결과 |
|---|---|---|
| WSL2 동작 | `wsl -l -v` (PowerShell) | Ubuntu STATE=Running |
| Docker 동작 | `docker --version` | `Docker version 2x.x.x` |
| ADB 동작 (Arduino 번들) | `& "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe" devices` | 디바이스 serial 표시 (`1204329696`) |
| 디바이스 venv-unoq | `adb shell 'ls -d ~/venv-unoq'` | 폴더 표시 |
| 디바이스 ai-edge-litert | `adb shell 'source ~/venv-unoq/bin/activate && python3 -c "import ai_edge_litert"'` | 출력 없음 (=성공) |
| USB UVC 카메라 (SSH 모드 시) | `ssh arduino@<IP> 'ls /dev/video*'` | `/dev/video0` (또는 다른 인덱스) 표시 |

vision 라인 setup (`vision/scripts/setup_device.sh`)이 선행되어 venv-unoq + ai-edge-litert가 준비되어 있어야 합니다.

## 1. 호스트 환경 진입 (Docker)

```bash
cd /mnt/c/Project/unoq-companion-robot/pose   # WSL2 경로
bash docker/run-pose.sh        # 첫 빌드 ≈3 min, 이후 5초
```

### 진입 확인

```text
==> Enter container unoq-pose (mount: /mnt/c/Project/unoq-companion-robot/pose -> /work)
dev@unoq-pose:/work$
```

### Smoke test (컨테이너 안)

```bash
python3 -c "import numpy, cv2, ai_edge_litert; \
    print('numpy', numpy.__version__); \
    print('cv2', cv2.__version__); \
    print('ai_edge_litert', ai_edge_litert.__version__)"
```

기대:
```text
numpy 2.1.3
cv2 4.x.x
ai_edge_litert 2.1.1
```

## 2. 모델 다운로드 (컨테이너 안 또는 호스트)

```bash
mkdir -p models
curl -L -o models/movenet_thunder_int8.tflite \
  "https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4?lite-format=tflite"

ls -la models/movenet_thunder_int8.tflite
# 기대: 7,126,768 bytes (6.80 MB)
```

다른 후보는 [`01_model_candidates.md`](01_model_candidates.md) §1 참조.

## 3. 호스트 introspection + latency

```bash
python3 scripts/inspect_movenet_thunder.py
```

기대 (호스트 x86 Docker, threads=4):
```text
크기: 6.80 MB
입력: [1, 256, 256, 3] dtype=uint8
출력: [1, 1, 17, 3] dtype=float32
양자화 분포: quantized 289 / float 11 / other 33
양자화 판정: full int8 PTQ
Latency p50: 14 ms (71.3 FPS)
```

## 4. 디바이스로 push (ADB 모드)

**전제**: UNO Q USB-C 직접 PC 연결 (허브 X).

```powershell
# PowerShell (Git Bash는 디바이스 경로를 Windows 경로로 변환하는 함정 있음)
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

& $ADB shell "mkdir -p /home/arduino/pose_test/models /home/arduino/pose_test/scripts"

& $ADB push "C:\Project\pose\models\movenet_thunder_int8.tflite" "/home/arduino/pose_test/models/"
& $ADB push "C:\Project\pose\scripts\inspect_movenet_thunder.py" "/home/arduino/pose_test/scripts/"
& $ADB push "C:\Project\pose\scripts\squat_counter.py" "/home/arduino/pose_test/scripts/"
& $ADB push "C:\Project\pose\scripts\infer_camera_pose.py" "/home/arduino/pose_test/scripts/"
```

## 5. 디바이스 introspection + latency (ADB 모드 그대로)

```powershell
& $ADB shell "source /home/arduino/venv-unoq/bin/activate && \
  MODEL_PATH=/home/arduino/pose_test/models/movenet_thunder_int8.tflite \
  python3 /home/arduino/pose_test/scripts/inspect_movenet_thunder.py"
```

기대 (UNO Q QRB2210 CPU only, threads=4):
```text
Latency p50: 80.3 ms (12.5 FPS)
출력 sanity: [1, 1, 17, 3] float32 — 17 keypoint × (y, x, conf)
```

## 6. 카메라 실시간 (SSH 모드 전환)

### 6-1. USB 토폴로지 전환

UNO Q USB-C를 PC에서 분리 → 허브 메인에 다시 꽂기. 카메라/마이크는 허브 자식 포트에. PC는 같은 LAN.

### 6-2. SSH 진입 + 실행 (HTTP serve + 스쿼트 카운터)

```bash
ssh arduino@192.168.0.45
# 비밀번호 입력

source ~/venv-unoq/bin/activate

# 기본 (HTTP serve, 좌/우 무릎 각도만)
python3 /home/arduino/pose_test/scripts/infer_camera_pose.py \
    /home/arduino/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080

# 스쿼트 카운터 활성화 + HTTP serve
python3 /home/arduino/pose_test/scripts/infer_camera_pose.py \
    /home/arduino/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 \
    --count --side better --down-th 100 --up-th 140
```

### 6-3. 브라우저 디버그

PC 브라우저: **http://192.168.0.45:8080/**

페이지:
- 좌측: 라이브 MJPEG 스트림 (skeleton + 무릎 각도 + REPS 카운트 오버레이)
- 우측: 500ms 갱신 stats JSON (FPS / stage_ms / CPU% / RAM / 온도 / squat 상태)

### 6-4. 종료 + 요약

`Ctrl+C` → 콘솔 SUMMARY 출력:
```text
================================================================
 SUMMARY  frames=N  elapsed=Ns
   fps_effective : ...
   cpu_peak_pct  : ...
   rss_peak_mb   : ...
   temp_peak_c   : ...
   squat_reps    : ...       (--count 활성화 시)
   deepest_deg   : ...
================================================================
```

## 7. 함정 / 디버깅

| 증상 | 점검 + 해결 |
|---|---|
| `cannot open camera /dev/video0` | `ls /dev/video*` + `v4l2-ctl --list-devices` — UVC 노드 식별 후 `--camera N` 변경. SU200 USB 분리/재연결 시 `sudo modprobe -r uvcvideo && sudo modprobe uvcvideo` |
| 브라우저 페이지 안 뜸 | UNO Q 방화벽 + 같은 LAN인지 확인. 또는 `--serve 8081` 다른 포트 |
| `L=? R=?` 계속 표시 (keypoint 미검출) | 1) 거리 1.5~2.5 m 권장 2) 옆모습 권장 3) `--conf 0.2` 임계 낮춤 |
| FPS 8 이하 떨어짐 | thermal throttle 의심 — `--print-every 5`로 temp_peak 추적. 합격선 70°C 마진 확인 |
| REP 카운트 폭발 (떨림) | `--min-dwell-ms 300` 또는 임계 hysteresis 넓힘 (`--down-th 95 --up-th 145`) |
| Git Bash로 adb push 시 destination 경로 망가짐 | PowerShell 사용 (Git Bash의 MSYS 경로 변환 함정) |

## 8. 다음

- 실측 결과는 `history/2026-06-27_*.md`에 누적 기록
- 트러블슈팅은 `issues/` 폴더
- 운영 가이드 (사용 시나리오별 명령 모음): [`03_runbook_camera_serve.md`](03_runbook_camera_serve.md)
