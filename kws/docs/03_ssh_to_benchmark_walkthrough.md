# SSH → 벤치마크 회수 전 과정 (KWS 라인)

본 문서는 **UNO Q SSH 접속부터 KWS 벤치마크 JSON 을 호스트로 회수하기까지의 처음-끝** 전 과정. 다른 문서 안 봐도 이 문서 하나로 직접 돌릴 수 있도록 완전 자립적으로 작성.

**최소 요구**:
- UNO Q 전원 + 네트워크 연결
- USB UAC 마이크 (KWS 실측용)
- (선택) USB UVC 카메라 (Pose 통합 벤치용)

**소요 시간**: 20~40 분 (첫 실행) / 5~10 분 (재실행).

## 목차

1. [초기 상태 점검](#1-초기-상태-점검)
2. [SSH 접속](#2-ssh-접속)
3. [venv 활성 + 의존성 확인](#3-venv-활성--의존성-확인)
4. [디바이스 폴더 준비](#4-디바이스-폴더-준비)
5. [모델 + 스크립트 push (ADB 또는 SCP)](#5-모델--스크립트-push-adb-또는-scp)
6. [단독 KWS latency 벤치마크](#6-단독-kws-latency-벤치마크)
7. [Pose + KWS 통합 벤치마크](#7-pose--kws-통합-벤치마크)
8. [소음/노이즈 조건 false trigger 측정](#8-소음노이즈-조건-false-trigger-측정)
9. [벤치마크 결과 회수 (SCP/ADB pull)](#9-벤치마크-결과-회수-scpadb-pull)
10. [결과 해석 + 합격 판정](#10-결과-해석--합격-판정)
11. [함정 모음](#11-함정-모음)

## 1. 초기 상태 점검

### PC 측 (PowerShell)

```powershell
# ADB 위치
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

# UNO Q 연결 확인
& $ADB devices
# 기대: 1204329696   device

# IP 확인 (SSH 접속용)
& $ADB shell "hostname -I"
# 기대: 192.168.0.45  (사용자 환경 의존)
```

만약 ADB 가 안 잡히면:
- USB-C 케이블 재연결 (데이터 케이블인지 확인)
- `adb kill-server; adb start-server`

### UNO Q 측 (SSH 접속 전 사전 확인)

```powershell
# 마이크 인식
& $ADB shell "arecord -l"
# 기대: card 1: USB [USB Audio Device], device 0: USB Audio ...

# 카메라 (Pose 통합 시)
& $ADB shell "ls /dev/video*"
# 기대: /dev/video0 (or /dev/videoN)
```

## 2. SSH 접속

### 옵션 A — 비밀번호 인증

```bash
ssh arduino@192.168.0.45
# 비밀번호 입력
```

### 옵션 B — SSH 키 인증 (권장, PowerShell 에서 setup)

```powershell
# 이미 되어 있으면 skip (2026-07-01 세션에 setup 진행 기록됨)
$IP = "192.168.0.45"
$USER = "arduino"

# 키 생성 (없으면)
if (-not (Test-Path "$env:USERPROFILE\.ssh\id_ed25519")) {
    ssh-keygen -t ed25519 -N "" -f "$env:USERPROFILE\.ssh\id_ed25519"
}

# authorized_keys 등록 (Windows 에 ssh-copy-id 없어서 수동)
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | `
    ssh $USER@$IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# 이후 비번 없이 접속 확인
ssh $USER@$IP whoami
```

## 3. venv 활성 + 의존성 확인

SSH 세션 안에서:

```bash
source ~/venv-unoq/bin/activate

# 필수 파이썬 패키지
python3 -c "import numpy, scipy, sounddevice, python_speech_features, ai_edge_litert; \
    print('numpy', numpy.__version__); \
    print('scipy', scipy.__version__); \
    print('sounddevice', sounddevice.__version__); \
    print('python_speech_features OK'); \
    print('ai_edge_litert', ai_edge_litert.__version__)"
```

**없으면 설치** (첫 실행 시 1회만):

```bash
pip install sounddevice soundfile python_speech_features scipy
sudo apt install -y libportaudio2 libsndfile1
```

## 4. 디바이스 폴더 준비

SSH 세션 안에서:

```bash
mkdir -p ~/kws_test/{models,scripts,benchmarks,data}
mkdir -p ~/pose_test/{models,scripts,benchmarks}    # pose 이미 있으면 skip
ls -d ~/kws_test ~/pose_test
```

## 5. 모델 + 스크립트 push (ADB 또는 SCP)

### 옵션 A — ADB push (USB-C 직접 연결 시)

PC PowerShell 로:

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
$REPO = "C:\Project\unoq-companion-robot"

# 모델 (호스트에서 이미 다운로드된 경우)
& $ADB push "$REPO\kws\models\kws_ref_model_ds_cnn_int8.tflite" "/home/arduino/kws_test/models/"
# fallback 모델도 같이
& $ADB push "$REPO\kws\models\micro_speech.tflite" "/home/arduino/kws_test/models/" 2>$null

# KWS 스크립트 일괄
& $ADB push "$REPO\kws\scripts\." "/home/arduino/kws_test/scripts/"

# Pose 통합 스크립트 (pose 폴더 이미 있다고 가정)
& $ADB push "$REPO\pose\scripts\infer_camera_pose_multimode.py" "/home/arduino/pose_test/scripts/"
& $ADB push "$REPO\pose\scripts\pushup_counter.py" "/home/arduino/pose_test/scripts/"

# 라벨 확인
& $ADB shell "ls -la /home/arduino/kws_test/models /home/arduino/kws_test/scripts"
```

### 옵션 B — SCP (SSH 모드, USB-C 분리 후)

PC PowerShell 로:

```powershell
$IP = "192.168.0.45"
$USER = "arduino"
$REPO = "C:\Project\unoq-companion-robot"

scp "$REPO\kws\models\kws_ref_model_ds_cnn_int8.tflite" "${USER}@${IP}:/home/arduino/kws_test/models/"
scp -r "$REPO\kws\scripts\*" "${USER}@${IP}:/home/arduino/kws_test/scripts/"
scp "$REPO\pose\scripts\infer_camera_pose_multimode.py" "${USER}@${IP}:/home/arduino/pose_test/scripts/"
scp "$REPO\pose\scripts\pushup_counter.py" "${USER}@${IP}:/home/arduino/pose_test/scripts/"
```

### 옵션 C — 디바이스에서 직접 다운로드

```bash
# SSH 세션 안
cd ~/kws_test
python3 scripts/download_model.py --model ds_cnn --dest models/
```

(옵션 C 는 UNO Q 가 인터넷 접속 가능해야 함).

## 6. 단독 KWS latency 벤치마크

### 6-1. Introspection (모델 metadata 덤프)

```bash
source ~/venv-unoq/bin/activate

python3 ~/kws_test/scripts/inspect_kws.py \
    ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    --threads 1 --runs 100 \
    --json ~/kws_test/benchmarks/inspect_ds_cnn_t1.json
```

기대 출력:
```text
== KWS inspect (ai_edge_litert) ==
  model:   /home/arduino/kws_test/models/kws_ref_model_ds_cnn_int8.tflite
  size:    52640 bytes (51.41 KB)
  input:   [1, 49, 10, 1] int8
  output:  [1, 12] int8
  양자화 판정: full int8 PTQ

== Latency (invoke only, threads=1) ==
  runs:  100
  mean:  ~15~30 ms  (예상)
  p50:   ...
  p95:   ...
```

### 6-2. Latency 정식 벤치마크 (JSON 저장)

```bash
# threads=1 (KWS 만 실행 시 CPU 여유 상황 X — 실제 서비스 시나리오는 1)
python3 ~/kws_test/scripts/benchmark_kws.py \
    --model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    --labels ~/kws_test/scripts/labels_12.txt \
    --preset ds_cnn \
    --threads 1 --runs 100 \
    --json ~/kws_test/benchmarks/kws_latency_t1.json

# threads=4 (KWS 만 최대 성능 시)
python3 ~/kws_test/scripts/benchmark_kws.py \
    --model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    --labels ~/kws_test/scripts/labels_12.txt \
    --preset ds_cnn \
    --threads 4 --runs 100 \
    --json ~/kws_test/benchmarks/kws_latency_t4.json
```

### 6-3. 실 마이크 검증 (30 초)

```bash
# 마이크 앞에서 명령 발화 ("up", "down", "stop", "go") 각 3~5회
python3 ~/kws_test/scripts/infer_mic_kws.py \
    ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    ~/kws_test/scripts/labels_12.txt \
    --preset ds_cnn \
    --conf 0.60 --print-every 3 \
    --max-seconds 30 \
    --json-summary ~/kws_test/benchmarks/mic_verify_30s.json
```

기대 출력 예:
```text
[    5] last=       Up conf=0.87  invoke=18.2ms  det=1  sil=3  unk=1  sub=0  mode=IDLE
  ★ EVENT  src=kws label=Up → mode=PUSHUP  conf=0.87
[   10] last=      Down conf=0.79  invoke=17.9ms  det=2  ...
```

## 7. Pose + KWS 통합 벤치마크

### 7-1. 사전 확인 (Pose 단독 정상 동작)

```bash
python3 ~/pose_test/scripts/infer_camera_pose.py \
    ~/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 --max-frames 300 --print-every 30
# 기대: FPS ~9.5, temp < 70°C
```

### 7-2. 통합 실행 (5 분 측정)

```bash
python3 ~/pose_test/scripts/infer_camera_pose_multimode.py \
    ~/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 \
    --initial-mode SQUAT \
    --enable-kws \
    --kws-model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    --kws-labels ~/kws_test/scripts/labels_12.txt \
    --kws-preset ds_cnn \
    --kws-conf 0.60 --kws-threads 1 \
    --threads 3 \
    --max-frames 3000 \
    --print-every 100 \
    --serve 8080
```

**측정 시나리오**:
1. 시작 시점 (0:00) — SQUAT 로 30 초 스쿼트 수행
2. 30초 시점 — "stop" 발화 → IDLE 전환 확인
3. 45초 시점 — "up" 발화 → PUSHUP 전환 확인
4. 45~120초 — 팔굽혀펴기 카운팅
5. 120초 시점 — "down" 발화 → SQUAT 복귀
6. 이후 4분간 스쿼트 지속 (thermal soak)

**동시 브라우저**: http://192.168.0.45:8080/ → 실시간 모드 + 카운터 + kws 라벨 확인.

Ctrl+C 종료 후 SUMMARY 출력.

### 7-3. SUMMARY 수동 기록 (자동 JSON 미포함 — 필요 시 추가)

```
================================
 SUMMARY  frames=3000  elapsed=310s
   fps_effective : 9.68
   dropped       : 0
   cpu_peak_pct  : 342.1
   rss_peak_mb   : 138.5
   temp_peak_c   : 69.4
   final_mode    : SQUAT
   mode_switches : 4
   kws_invokes   : 1550
   kws_detects   : 8
   squat_reps    : 22
   pushup_reps   : 8
================================
```

**이 출력을 텍스트로 저장**:

```bash
# 위 실행 명령을 tee 로 감싸기
... | tee ~/kws_test/benchmarks/integration_5min_$(date +%Y%m%d_%H%M).log
```

## 8. 소음/노이즈 조건 false trigger 측정

멘토 결정 사항 (`memory/project_unoq_next_cycle_constraints.md`): **clean + 생활노이즈 양쪽 측정**.

### 8-1. Clean 환경 (조용한 방)

```bash
# 60초, 발화 없이 대기 — 이 동안 detections 0이어야 정상
python3 ~/kws_test/scripts/infer_mic_kws.py \
    ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    ~/kws_test/scripts/labels_12.txt \
    --preset ds_cnn --conf 0.60 --print-every 20 \
    --max-seconds 60 \
    --json-summary ~/kws_test/benchmarks/false_trigger_clean.json
```

**합격**: `detections < 2` (60초 안 false trigger 2회 이하).

### 8-2. 생활 노이즈 환경 (TV / 배경 대화 / 키보드)

```bash
# 배경 소음 켜고 60초 (사용자 발화 없음)
python3 ~/kws_test/scripts/infer_mic_kws.py \
    ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
    ~/kws_test/scripts/labels_12.txt \
    --preset ds_cnn --conf 0.60 --print-every 20 \
    --max-seconds 60 \
    --json-summary ~/kws_test/benchmarks/false_trigger_noise.json
```

**합격**: `detections < 4` (60초 안 false trigger 4회 이하, 즉 15초당 1회 이하).

노이즈 조건 실패 시:
- `--kws-conf 0.75` 로 threshold 상향
- ModeBus `debounce_ms=1500` 로 확대
- 2 순위 모델 (MicroSpeech 4클래스) 로 fallback

## 9. 벤치마크 결과 회수 (SCP/ADB pull)

### 옵션 A — SCP (SSH 세션 유지)

PC PowerShell 로:

```powershell
$IP = "192.168.0.45"
$USER = "arduino"
$LOCAL = "C:\Project\unoq-companion-robot\kws\benchmarks\device"

New-Item -ItemType Directory -Force -Path $LOCAL | Out-Null

# 전체 폴더 회수
scp -r "${USER}@${IP}:/home/arduino/kws_test/benchmarks/*" $LOCAL/

ls $LOCAL
```

### 옵션 B — ADB pull (USB-C 재연결 후)

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
$LOCAL = "C:\Project\unoq-companion-robot\kws\benchmarks\device"

New-Item -ItemType Directory -Force -Path $LOCAL | Out-Null
& $ADB pull "/home/arduino/kws_test/benchmarks/" $LOCAL

# Pose 통합 로그도
& $ADB pull "/home/arduino/kws_test/benchmarks/integration_*.log" $LOCAL
```

### 옵션 C — 세션 안에서 rsync (선택)

```bash
# 디바이스에서 → LAN 상 다른 서버로 (rsync 서버가 있을 때만)
rsync -avz ~/kws_test/benchmarks/ user@archive.local:/backups/unoq-kws/
```

## 10. 결과 해석 + 합격 판정

### 10-1. Latency 표

| 파일 | mean | p50 | p95 | fps_p50 | 합격 (≤50ms p95) |
|---|---|---|---|---|---|
| `kws_latency_t1.json` | ? | ? | ? | ? | ? |
| `kws_latency_t4.json` | ? | ? | ? | ? | ? |

### 10-2. 통합 지표

| 지표 | Pose 단독 | Pose+KWS | 증가 | 합격선 | 판정 |
|---|---|---|---|---|---|
| fps_effective | 9.68 | ? | ? | 하락 ≤ 1 | ? |
| cpu_peak_pct | 316 | ? | ? | ≤ 380 | ? |
| rss_peak_mb | 96 | ? | ? | 증가 ≤ 30 MB | ? |
| temp_peak_c | 71.4 | ? | ? | 증가 ≤ 2°C | ? |

### 10-3. False trigger 표

| 조건 | 시간 | detections | 합격선 | 판정 |
|---|---|---|---|---|
| Clean | 60s | ? | < 2 | ? |
| 생활 노이즈 | 60s | ? | < 4 | ? |

### 10-4. 모드 전환 검증

로그에서 `★ EVENT` + `★ MODE EVENT` grep:
- "up" 발화 → PUSHUP 전환 ≤ 500ms
- "stop" 발화 → IDLE 전환 ≤ 500ms
- 카운터 자동 리셋 확인

## 11. 함정 모음

| 증상 | 원인 | 해결 |
|---|---|---|
| `sounddevice PortAudioError` | libportaudio2 미설치 | `sudo apt install libportaudio2` |
| `arecord -l` 빈 출력 | UAC 마이크 커널 미인식 | `sudo modprobe -r snd_usb_audio && sudo modprobe snd_usb_audio` |
| KWS 모든 결과가 `_unknown_` | frontend 파라미터 불일치 | `--preset` 확인, sample_rate 16000 확인, MFCC 계수 수 확인 |
| KWS 정확도 낮음 (< 60%) | 학습 데이터 (영어 명령) vs 사용자 (한국어 억양) mismatch | 자체 훈련 파이프라인 진행 (`01_model_candidates.md §4`) |
| Pose FPS 급락 (9.6 → 6) | CPU 경합 | `--threads 3 --kws-threads 1` 로 분리 |
| RSS 증가 큼 (>50 MB) | librosa dep | python_speech_features 만 사용 (frontend 자동 선택) |
| ModeBus queue full | pose loop 이 너무 늦게 poll | main loop 안 다른 병목 확인 (draw / http) |
| Benchmark JSON 파싱 실패 | thermal_zone 등 int() 파싱 | Python `try/except` 로 감쌈 (이미 처리됨) |
| ADB pull 시 파일 없음 | 절대 경로 오타 | `& $ADB shell "ls /home/arduino/kws_test/benchmarks"` 로 확인 |
| SSH 세션 끊김 | 유선 LAN 유지 권장 | Wi-Fi 시 `ServerAliveInterval 30` in `~/.ssh/config` |

## 12. 다음 사이클로 넘길 것

- 자동 JSON 저장 (통합 스크립트 SUMMARY → JSON) 추가 스크립트
- KWS accuracy 정식 wav 검증 (Speech Commands v2 test set 서브셋 push + 정답 라벨)
- 한국어 명령 자체 훈련 (선택)
- MCU 트리거 통합 (v0.4.0)

## 13. 관련

- 청사진: [`00_project_blueprint.md`](00_project_blueprint.md)
- 모델 후보 + 라이선스: [`01_model_candidates.md`](01_model_candidates.md)
- Quickstart: [`02_quickstart_kws.md`](02_quickstart_kws.md)
- 인터럽트 아키텍처: [`04_mode_interrupt_architecture.md`](04_mode_interrupt_architecture.md)
- 버튼 배선: [`05_button_wiring.md`](05_button_wiring.md)
- Pose 라인 runbook: [`../../pose/docs/03_runbook_camera_serve.md`](../../pose/docs/03_runbook_camera_serve.md)
