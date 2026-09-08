# Quickstart — KWS on UNO Q (원샷 실행 가이드)

본 문서는 본 라인 미경험자가 **30분 안에 디바이스에서 마이크 → 키워드 검출 + Pose 통합 인터럽트**까지 도달하는 절차. [00_project_blueprint.md](00_project_blueprint.md) 결정에 따른 실제 명령 시퀀스.

디바이스 SSH 접속 → 벤치마크 회수 전 과정 별도 문서: [`03_ssh_to_benchmark_walkthrough.md`](03_ssh_to_benchmark_walkthrough.md).

## 0. 사전 조건 체크리스트

| 항목 | 명령 | 기대 결과 |
|---|---|---|
| WSL2 동작 | `wsl -l -v` | Ubuntu STATE=Running |
| Docker 동작 | `docker --version` | `Docker version 2x.x.x` |
| ADB 동작 | `& "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe" devices` | 디바이스 serial `1204329696` |
| 디바이스 venv-unoq | `adb shell 'ls -d ~/venv-unoq'` | 폴더 표시 |
| 디바이스 ai-edge-litert | `adb shell 'source ~/venv-unoq/bin/activate && python3 -c "import ai_edge_litert"'` | 출력 없음 |
| **디바이스 USB UAC 마이크** | `adb shell 'arecord -l'` | `card N:` 카드 최소 1개 |
| Pose 라인 baseline | `~/pose_test/models/movenet_thunder_int8.tflite` 존재 | 확인 |

pose 라인 setup 이 선행되어 있어야 합니다 — [`../../pose/docs/02_quickstart_pose.md`](../../pose/docs/02_quickstart_pose.md).

## 1. 호스트 환경 진입 (Docker)

```bash
cd /mnt/c/Project/unoq-companion-robot/kws
bash docker/run-kws.sh          # 첫 빌드 ≈3 min, 이후 5초
```

### 진입 확인

```text
==> Enter container unoq-kws (mount: /mnt/c/Project/unoq-companion-robot/kws -> /work)
dev@unoq-kws:/work$
```

### Smoke test (컨테이너 안)

```bash
python3 -c "import numpy, scipy, sounddevice, librosa, ai_edge_litert, python_speech_features; \
    print('numpy', numpy.__version__); \
    print('scipy', scipy.__version__); \
    print('sounddevice', sounddevice.__version__); \
    print('librosa', librosa.__version__); \
    print('ai_edge_litert', ai_edge_litert.__version__); \
    print('python_speech_features OK')"
```

## 2. 모델 다운로드

### 2-1. 자동 (권장)

```bash
python3 scripts/download_model.py --model ds_cnn --dest models/
```

기대:
```text
=== Download KWS model: ds_cnn ===
  license: Apache-2.0 (code) + CC BY 4.0 (data)
  vocab:   12 classes
  dest:    models/kws_ref_model_ds_cnn_int8.tflite
  try: https://github.com/mlcommons/tiny/raw/master/...
  verify: size=52640 bytes
    sha256: 0x...
[done] models/kws_ref_model_ds_cnn_int8.tflite
```

### 2-2. 수동 fallback (URL rot 시)

```bash
git clone --depth 1 https://github.com/mlcommons/tiny.git /tmp/mlperf-tiny
cp /tmp/mlperf-tiny/benchmark/training/keyword_spotting/trained_models/kws_ref_model.tflite \
   models/kws_ref_model_ds_cnn_int8.tflite
```

### 2-3. 2순위 fallback — MicroSpeech

DS-CNN 다운로드 실패 or 정확도 미달 시:
```bash
python3 scripts/download_model.py --model micro_speech --dest models/
```

## 3. 호스트 introspection + latency

```bash
python3 scripts/inspect_kws.py models/kws_ref_model_ds_cnn_int8.tflite \
    --json benchmarks/host_baseline.json
```

기대 (호스트 x86 Docker, threads=4):
```text
size:    52640 bytes (51.41 KB)
input:   [1, 49, 10, 1] int8
output:  [1, 12] int8
양자화 판정: full int8 PTQ
Latency p50: ~2 ms (~500 Hz)  ← 호스트 x86 기준
```

## 4. 모듈 self-test

```bash
python3 scripts/mfcc_frontend.py       # frontend shape 검증
python3 scripts/mode_controller.py     # ModeBus 이벤트 흐름 검증
python3 scripts/kws_worker.py          # 실 모델 dummy invoke
```

## 5. 디바이스로 push (ADB 모드)

**전제**: UNO Q USB-C 직접 PC 연결 (허브 X).

```powershell
# PowerShell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

# 디렉토리 생성
& $ADB shell "mkdir -p /home/arduino/kws_test/models /home/arduino/kws_test/scripts /home/arduino/kws_test/benchmarks"

# 모델 + 스크립트 push
& $ADB push "C:\Project\unoq-companion-robot\kws\models\kws_ref_model_ds_cnn_int8.tflite" "/home/arduino/kws_test/models/"
& $ADB push "C:\Project\unoq-companion-robot\kws\scripts\." "/home/arduino/kws_test/scripts/"

# Pose multimode 통합 스크립트도 push
& $ADB push "C:\Project\unoq-companion-robot\pose\scripts\infer_camera_pose_multimode.py" "/home/arduino/pose_test/scripts/"
& $ADB push "C:\Project\unoq-companion-robot\pose\scripts\pushup_counter.py" "/home/arduino/pose_test/scripts/"
```

## 6. 디바이스 의존성 추가 (1회)

```powershell
& $ADB shell 'source ~/venv-unoq/bin/activate && \
  pip install sounddevice soundfile python_speech_features scipy'

& $ADB shell 'sudo apt install -y libportaudio2 libsndfile1'
```

## 7. 디바이스 introspection + latency

```powershell
& $ADB shell "source ~/venv-unoq/bin/activate && \
  python3 /home/arduino/kws_test/scripts/inspect_kws.py \
  /home/arduino/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
  --threads 1 --runs 100 \
  --json /home/arduino/kws_test/benchmarks/device_baseline.json"
```

기대 (UNO Q QRB2210, threads=1):
```text
Latency p50: ~15~30 ms
```

## 8. 마이크 KWS 단독 실행 (SSH 모드 전환)

### 8-1. USB 토폴로지 전환

UNO Q USB-C 를 PC 에서 분리 → 허브 메인에 다시 꽂기. 마이크는 허브 자식 포트.

### 8-2. SSH 진입 + KWS 단독 실행

```bash
ssh arduino@192.168.0.45
source ~/venv-unoq/bin/activate

# 마이크 장치 확인
python3 ~/kws_test/scripts/infer_mic_kws.py --list-devices

# KWS 실행 (12 클래스)
python3 ~/kws_test/scripts/infer_mic_kws.py \
    ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    ~/kws_test/scripts/labels_12.txt \
    --preset ds_cnn \
    --conf 0.60 \
    --print-every 5
```

명령 발화 예:
- "up" → EVENT src=kws label=Up target=PUSHUP
- "down" → EVENT src=kws label=Down target=SQUAT
- "stop" → EVENT src=kws label=Stop target=IDLE

## 9. Pose 통합 실행 (본 문서 핵심)

```bash
python3 ~/pose_test/scripts/infer_camera_pose_multimode.py \
    ~/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 \
    --initial-mode SQUAT \
    --enable-kws \
    --kws-model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    --kws-labels ~/kws_test/scripts/labels_12.txt \
    --kws-preset ds_cnn \
    --kws-conf 0.60
```

브라우저 진입: **http://192.168.0.45:8080/**

기대 동작:
- 초기 SQUAT 모드로 스쿼트 카운팅
- "stop" 발화 → IDLE (카운팅 즉시 중지)
- "up" 발화 → PUSHUP 모드 (팔꿈치 각도 카운팅)
- 브라우저 stats JSON 에 `mode`, `mode_bus`, `kws` 필드 표시

## 10. 함정 / 디버깅

| 증상 | 점검 + 해결 |
|---|---|
| `arecord -l` 빈 출력 | USB UAC 재연결 → `sudo modprobe -r snd_usb_audio && sudo modprobe snd_usb_audio` |
| `sounddevice PortAudio not found` | `sudo apt install libportaudio2` |
| KWS 정확도 0% (모두 unknown) | frontend 파라미터 불일치 — `--preset` 확인 (ds_cnn ↔ micro_speech), sample rate 16000 확인 |
| KWS latency > 50 ms | threads 조정 (1→2→4), pose 4 threads 와 경합 시 pose 3 + kws 1 권장 |
| Pose FPS 급락 | KWS thread 경합 — `--kws-threads 1` 고정, `--kws-hop-ms 300` (호출 빈도 감소) |
| False trigger 폭발 | `--kws-conf 0.75` 상향, ModeBus debounce_ms 확대 |
| Bus 이벤트 무반응 | pose main loop 에서 `bus.poll()` 호출 확인 (multimode 스크립트는 매 프레임 호출) |
| Button 미반응 | `--gpio-line` 확인, `--gpio-active-high false` 로 반전, sysfs vs libgpiod 백엔드 확인 |

## 11. 다음 단계

| 우선 | 항목 | 참조 |
|---|---|---|
| 1 | SSH → 벤치마크 회수 전 과정 | [`03_ssh_to_benchmark_walkthrough.md`](03_ssh_to_benchmark_walkthrough.md) |
| 2 | 인터럽트 아키텍처 이해 | [`04_mode_interrupt_architecture.md`](04_mode_interrupt_architecture.md) |
| 3 | 물리 버튼 배선 | [`05_button_wiring.md`](05_button_wiring.md) |
| 4 | Clean + 생활 노이즈 양측 false trigger 측정 | benchmarks 누적 |
| 5 | history 기록 | [`history/`](history/) |
