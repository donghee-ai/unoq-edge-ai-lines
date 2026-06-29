# Quickstart — Whisper Tiny.en ASR on UNO Q (원샷 실행 가이드)

본 문서는 본 모듈을 처음 접하는 외부 진입자가 **0분 → 30분 안에 디바이스에서 본인 음성 인식까지** 도달하는 절차입니다. README.md의 5분 요약을 상세 절차 + 검증 게이트 + 함정 + 디버깅으로 확장.

## 0. 사전 조건 체크리스트

| 항목 | 명령 | 기대 결과 |
|---|---|---|
| WSL2 동작 | `wsl -l -v` (PowerShell) | Ubuntu STATE=Running |
| Docker 동작 | `docker --version` | `Docker version 2x.x.x` |
| 디스크 여유 (호스트) | `df -h` | ~3 GB |
| Arduino UNO Q 디바이스 | `ssh arduino@<IP> 'uname -a'` | `Linux unoq-korea01 7.0.0-...` |
| 디바이스 venv-unoq 존재 | `ssh arduino@<IP> 'ls -d ~/venv-unoq'` | 폴더 표시 |
| 디바이스 ai-edge-litert 설치 | `ssh arduino@<IP> 'source ~/venv-unoq/bin/activate && python3 -c "import ai_edge_litert"'` | 출력 없음 (=성공) |
| USB 마이크 인식 | `ssh arduino@<IP> 'arecord -l'` | `card 0: Device [Usb Audio Device]` |
| 디스크 여유 (디바이스) | `ssh arduino@<IP> 'df -h /'` | ≥ 500 MB |

`venv-unoq` / `ai-edge-litert`가 없으면 vision 라인 setup이 선행 (`vision/scripts/setup_device.sh`).

## 1. 호스트 환경 준비 (asr-dev Docker)

### 1-1. 진입

```bash
cd /mnt/c/Project/unoq-companion-robot/asr   # WSL2 경로
bash docker/run-asr.sh        # 첫 빌드 ~10분, 이후 5초
```

### 1-2. 진입 확인

```text
==> Enter container unoq-asr-dev (mount: /mnt/c/Project/unoq-companion-robot/asr -> /work)
dev@unoq-asr-dev:/work$
```

### 1-3. Smoke test (컨테이너 안)

```bash
python3 -c "import numpy, scipy, sounddevice, librosa, ai_edge_litert; \
    print('numpy', numpy.__version__); \
    print('librosa', librosa.__version__); \
    print('ai_edge_litert', ai_edge_litert.__version__)"
```

기대 (2026-06-25 시점 lock):
```text
numpy 2.1.3
librosa 0.11.0
ai_edge_litert 2.1.5
```

`ai_edge_litert 2.1.5` = 디바이스와 동일. 추론 결과 bit-exact 보장.

## 2. 자산 다운로드 (컨테이너 안, 한 줄씩)

### 2-1. 폴더 생성

```bash
mkdir -p models/audio data/samples benchmarks/audio
```

### 2-2. Whisper Tiny.en TFLite 모델 (40 MB, MIT)

```bash
wget -O models/audio/whisper_tiny_en.tflite \
  https://raw.githubusercontent.com/nyadla-sys/whisper.tflite/main/models/whisper-tiny-en.tflite
```

대안 출처 (HuggingFace): `https://huggingface.co/DocWolle/whisper_tflite_models/resolve/main/whisper-tiny.en.tflite?download=true` (41.5 MB)

### 2-3. Mel filter bank (7 KB, MIT)

```bash
wget -O models/audio/mel_filters.npz \
  https://github.com/openai/whisper/raw/main/whisper/assets/mel_filters.npz
```

내용: `mel_80` 키에 80 mel bank × 201 FFT bin filter matrix.

### 2-4. Whisper tokenizer (2.4 MB, Apache-2.0)

```bash
wget -O models/audio/tokenizer.json \
  "https://huggingface.co/openai/whisper-tiny.en/resolve/main/tokenizer.json?download=true"
```

### 2-5. 테스트용 wav (jfk.wav 344 KB)

```bash
wget -O data/samples/jfk.wav \
  https://github.com/ggml-org/whisper.cpp/raw/master/samples/jfk.wav
```

길이 11초, 영어, JFK 1961 취임 연설 일부. Whisper 표준 검증 샘플.

### 2-6. 다운로드 확인

```bash
ls -la models/audio/ data/samples/
```

기대:
- `whisper_tiny_en.tflite` 41.5 MB
- `mel_filters.npz` 7 KB
- `tokenizer.json` 2.4 MB
- `jfk.wav` 344 KB

## 3. 컨테이너 의존성 추가 (1회)

```bash
pip install tokenizers
```

(약 30초. `requirements-asr.txt`에 명시되어 있지만 현재 이미지가 lock 갱신 전이면 임시 설치)

## 4. 호스트 검증 — JFK wav → 텍스트

```bash
python3 src/transcribe.py \
  --model models/audio/whisper_tiny_en.tflite \
  --mel-filters models/audio/mel_filters.npz \
  --tokenizer models/audio/tokenizer.json \
  --input data/samples/jfk.wav
```

### 기대 출력

```text
==> Load model: models/audio/whisper_tiny_en.tflite
    input  [1, 80, 3000] float32
    output [1, 448] int32
==> Load tokenizer: models/audio/tokenizer.json
==> Load mel filters: models/audio/mel_filters.npz
==> Load wav: data/samples/jfk.wav
    audio duration: 11.00s
==> Preprocess: mel[1, 80, 3000] ~150 ms
==> Invoke: output[1, 448] ~1200 ms
============================================================
>>>  And so my fellow Americans ask not what your country can do for you,
     ask what you can do for your country.
============================================================
  preprocess:     150 ms
  invoke:        1200 ms
  decode:           0 ms
  total:         1350 ms
```

### 검증 게이트 — 위 텍스트가 정확히 나와야 함

- `And so my fellow Americans...` 영어 텍스트가 출력
- preprocess ~100~200 ms (호스트 CPU 따라)
- invoke ~1~2 초 (호스트 CPU 따라 — Ryzen 7 기준 1.2초)

→ **통과 시 모델 + tokenizer + preprocess 정확성 확정**.

## 5. 디바이스 환경 준비 (호스트 WSL로 복귀)

```bash
exit   # 컨테이너 종료
```

프롬프트가 `(base) a@DESKTOP-...:/mnt/c/Project/unoq-companion-robot/asr$` 형태가 되어야 호스트 WSL.

### 5-1. SSH 변수 (본인 값으로)

```bash
export UNO_Q_USER=arduino
export UNO_Q_HOST=192.168.0.45   # 본인 디바이스 IP
```

### 5-2. PortAudio 시스템 라이브러리 (디바이스, 1회)

```bash
ssh -t ${UNO_Q_USER}@${UNO_Q_HOST} 'sudo apt install -y libportaudio2'
```

`-t` 옵션 필수 (sudo 비번 입력용 pseudo-terminal).

### 5-3. Python 의존성 (디바이스 venv-unoq, 1회)

```bash
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && \
    pip install sounddevice scipy tokenizers soundfile'
```

설치 ~1~2분.

### 5-4. 자산 디바이스 전송 (호스트 → 디바이스)

```bash
# 모델 3종 → /opt/unoq-yolo/models/
scp models/audio/whisper_tiny_en.tflite \
    models/audio/mel_filters.npz \
    models/audio/tokenizer.json \
    ${UNO_Q_USER}@${UNO_Q_HOST}:/opt/unoq-yolo/models/

# 테스트 wav → /opt/unoq-yolo/media/
scp data/samples/jfk.wav ${UNO_Q_USER}@${UNO_Q_HOST}:/opt/unoq-yolo/media/

# Python 모듈 3개 → 디바이스 홈
scp src/preprocess.py src/tokenizer.py src/transcribe.py ${UNO_Q_USER}@${UNO_Q_HOST}:~/
```

각 scp 호출마다 비밀번호 1번. 한/영 영어 모드 확인.

## 6. 디바이스 검증 — 같은 JFK wav (feature 일치 게이트)

```bash
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && python3 ~/transcribe.py \
    --model /opt/unoq-yolo/models/whisper_tiny_en.tflite \
    --mel-filters /opt/unoq-yolo/models/mel_filters.npz \
    --tokenizer /opt/unoq-yolo/models/tokenizer.json \
    --input /opt/unoq-yolo/media/jfk.wav'
```

### 검증 게이트 — 호스트와 100% 동일 텍스트

- 디바이스 텍스트 == 호스트 텍스트 (`>>> And so my fellow Americans ask not...`)
- preprocess ~250~350 ms (A53)
- invoke ~2000~3500 ms (cold start 영향 있음, 2회째부터 ~2000 ms steady)
- total ~3000~3800 ms

→ **통과 시 호스트 ↔ 디바이스 feature 추출 알고리즘 bit-exact 일치 확정** (멘토 리뷰 단점 2 해결).

## 7. 마이크 녹음 + 인식 (실시간 시연)

```bash
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && \
    mkdir -p /tmp/unoq-yolo/audio-debug && \
    python3 -u ~/transcribe.py \
        --model /opt/unoq-yolo/models/whisper_tiny_en.tflite \
        --mel-filters /opt/unoq-yolo/models/mel_filters.npz \
        --tokenizer /opt/unoq-yolo/models/tokenizer.json \
        --record 10 --device 0 --save /tmp/unoq-yolo/audio-debug/'
```

핵심 옵션:
- `python3 -u` — unbuffered stdout (ssh non-tty 환경에서 "SPEAK NOW" 메시지 즉시 표시)
- `--record 10` — 10초 녹음 (충분한 여유)
- `--device 0` — sounddevice card 0 (USB Audio Device)
- `--save <dir>` — 녹음 wav 자동 저장 (debug, opt-in)

### 발화 타이밍 (매우 중요)

```text
==> Will record 10s @ 48000 Hz mono, device=0
    Speak in 3...        ← 마음의 준비
    Speak in 2...
    Speak in 1...
    *** SPEAK NOW (recording 10s) ***   ← 이 메시지 보이는 즉시 발화 시작
       ↑ 10초간 영어로 또렷이 발화
==> Recording done (48000 Hz, 480000 samples)
==> Resampled 48000 -> 16000 Hz, samples=160000
==> Saved wav: /tmp/unoq-yolo/audio-debug/record_<TS>.wav
...
============================================================
>>> Hello robot! Come here, stop! Yes, no! Turn on the light!
============================================================
```

### 시연 영어 발화 예시 (10초에 충분)

- `Hello robot. Come here. Stop. Yes. No. Turn on the light.`
- `The quick brown fox jumps over the lazy dog.`
- `What is your name? Where are you going?`

마이크와 거리 30~50 cm, 또렷한 발음.

## 8. 녹음 wav 회수 (검증/디버깅)

```bash
mkdir -p data/samples/recorded
scp "${UNO_Q_USER}@${UNO_Q_HOST}:/tmp/unoq-yolo/audio-debug/record_*.wav" \
    data/samples/recorded/
```

Windows 탐색기에서 재생:
```bash
explorer.exe data/samples/recorded/
```

자가 발화와 텍스트 비교 → 인식 정확도 확인.

## 9. 자주 만나는 함정 + 해결

상세는 [`docs/03_implementation_log.md`](03_implementation_log.md) 참조.

| 증상 | 원인 | 해결 |
|---|---|---|
| `bash: python: command not found` (컨테이너) | Ubuntu 22.04에 `python` symlink 없음 | `python3` 사용 |
| `bash: scp: command not found` (컨테이너) | 컨테이너에 OpenSSH client 미설치 | `exit`로 호스트 WSL 복귀 후 scp |
| `Connection to 192.168.0.45 closed.` + 명령 무시 | nested SSH (디바이스 안에서 또 ssh) | `exit`로 호스트 복귀 후 다시 |
| `sudo: a terminal is required` | ssh non-interactive에서 sudo | `ssh -t arduino@... 'sudo ...'` |
| `ModuleNotFoundError: sounddevice` (디바이스) | 디바이스에 pip install 안 됨 | `pip install sounddevice scipy tokenizers soundfile` |
| `PortAudioError: Invalid sample rate` | USB Audio Class 16 kHz 미지원 | (자동 처리) `transcribe.py`가 48 kHz fallback + resample |
| 발화 안 했는데 "You"만 인식 | ssh non-tty stdout buffering — "SPEAK NOW" 메시지가 5초 후 표시됨 | `python3 -u` 사용 (unbuffered) |
| `unbound method generic.tolist()` | numpy dtype 클래스 자체에 tolist 호출 | `_clean_value` 함수 fix (current 코드 적용됨) |
| 한/영 IME 한글 모드로 비번 입력 | `Permission denied` | 한/영 키로 영어 모드 확인 |

## 10. 합격선 (4기준 + 참고 1) — 본 작품 자체 기준

| 기준 | 임계값 | 측정 도구 |
|---|---|---|
| invoke latency mean | ≤ 5초 | `validate_kws.py --runs 5` |
| invoke latency p95 | ≤ 7초 | 동상 |
| 이벤트 응답 (음성→텍스트 e2e) | ≤ 5초 | `transcribe.py --record N` |
| max RSS (Whisper 활성) | < 300 MB | `/proc/self/status` VmRSS |
| 정확도 (참고) | WER ≤ 15% (영어 본인 발화) | 미구현 (LibriSpeech / 본인 녹음 + jiwer) |

2026-06-25 실측: latency 부분 통과, RSS/temp/WER 미실시 (다음 단계).

## 11. 다음 단계 (Phase 2 종료 후)

| 단계 | 작업 |
|---|---|
| Phase 3-1 | `src/benchmark_asr.py` 100회 벤치 + RSS + temp + 멘토 06 JSON |
| Phase 3-2 | LibriSpeech / 본인 녹음 WER 측정 (정확도 정량) |
| Phase 4 | Silero VAD 추가 + 이벤트 기반 운영 (vision 동시 운영 핵심) |
| Phase 5 | Vision YOLO + ASR 동시 thermal soak test 8h+ |
| Phase 6 | MCU(STM32U585) 통신 + fusion (음성 의도 → 동작 트리거) |
| Phase 7 | monorepo 통합 (vision 라인과 합치기) |

상세는 [`docs/00_project_blueprint.md`](00_project_blueprint.md) §6.

## 12. 환경 호환성 매트릭스

| 환경 | Python | numpy | ai_edge_litert | librosa | sounddevice | tokenizers |
|---|---|---|---|---|---|---|
| 호스트 asr-dev 컨테이너 (Ubuntu 22.04) | 3.10.12 | 2.1.3 | 2.1.5 | 0.11.0 | 0.5.5 | 0.23.x |
| 디바이스 venv-unoq (Debian aarch64) | 3.13.5 | 2.5.0 | 2.1.5 | (미설치, 자작 mel 사용) | 0.5.5 | 0.23.1 |
| 호환 | OK | OK (둘 다 numpy 2.x) | **bit-exact 동일** | (호스트만) | OK | OK |

핵심: **ai_edge_litert 2.1.5가 양쪽 동일** → 모델 추론 결과 bit-exact. numpy 메이저 (2.x)는 동일, 미세 버전(2.1.3 vs 2.5.0) 차이는 무영향.
