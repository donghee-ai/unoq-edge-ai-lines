# unoq-asr — Real-time ASR on Arduino UNO Q (Whisper Tiny.en TFLite)

Arduino UNO Q (Qualcomm Dragonwing QRB2210, CPU only) 위에서 OpenAI Whisper Tiny.en TFLite 모델로 영어 자유발화를 텍스트로 변환하는 임베디드 ASR 모듈. 본인 교감로봇 작품(`unoq-companion-robot` vision 라인)의 **음성 입력 채널** 담당. 이벤트 기반 운영으로 vision YOLO 9 FPS 동시 운영을 목표.

## 합격선 통과 (2026-06-25 실측)

| 기준 | 임계값 | 실측 | 결과 |
|---|---|---|---|
| invoke latency mean (디바이스, dummy input, warmup 5) | ≤ 5 초 | **2.015 초** | **통과** |
| invoke p95 | ≤ 7 초 | 2.020 초 | 통과 |
| 이벤트 응답 e2e (10초 음성 → 텍스트) | ≤ 5 초 | **3.18 초** | **통과** |
| feature 일치 (호스트 ↔ 디바이스 같은 wav) | 100% 동일 | **JFK wav 텍스트 완전 일치** | **통과** |
| 본인 발화 정확도 (6 명령) | 정량 | **5/6 = 83%** ("light"→"line" 1단어 오인식) | 우수 |
| 모델·코드·데이터셋 라이선스 | 상업 OK | **MIT / Apache-2.0 / CC BY 4.0** | 3중 클린 |

## 5분 요약

| 항목 | 내용 |
|---|---|
| 타겟 | Arduino UNO Q (QRB2210, Cortex-A53 ×4 @ 2.0 GHz, CPU only, NPU/DSP 없음) |
| 모델 | Whisper Tiny.en TFLite (40 MB, MIT, encoder+decoder 통합 단일 invoke) |
| 런타임 | ai-edge-litert 2.1.5 (vision YOLO와 동일) |
| 입력 | 16 kHz mono PCM 30초 청크 → mel spectrogram `(1, 80, 3000)` |
| 출력 | int32 `(1, 448)` token IDs → tokenizer.decode → 영어 텍스트 |
| Preprocess | numpy 자작 log-mel (Whisper 공식 알고리즘 복제, librosa 의존 X) |
| Tokenizer | HuggingFace `tokenizers` + Whisper tokenizer.json (~50k vocab) |
| 마이크 | USB Audio Class (Generalplus 1b3f:2008) — 48 kHz 캡처 + 16 kHz resample |
| 운영 모드 | 이벤트 기반 (Silero VAD trigger 예정) |

## 5분 원샷 실행 (외부 진입자용)

전제 조건:
- WSL2 Ubuntu 24.04 (Windows 11) + Docker Desktop
- Arduino UNO Q 디바이스 + SSH 접속 정보 (`arduino@<IP>`)
- USB Audio Class 마이크 (디바이스 USB 포트에 연결)
- 디스크 ~3 GB

```bash
# 1. 진입 폴더
cd /mnt/c/Project/unoq-companion-robot/asr   # WSL 경로

# 2. asr-dev Docker 컨테이너 빌드 + 진입 (첫 빌드 ~10분, 이후 5초)
bash docker/run-asr.sh
```

컨테이너 안 (`dev@unoq-asr-dev:/work$`):

```bash
# 3. 자산 다운로드 (모델 40 MB + mel 7 KB + tokenizer 2 MB + 테스트 wav 344 KB)
mkdir -p models/audio data/samples
wget -O models/audio/whisper_tiny_en.tflite \
  https://raw.githubusercontent.com/nyadla-sys/whisper.tflite/main/models/whisper-tiny-en.tflite
wget -O models/audio/mel_filters.npz \
  https://github.com/openai/whisper/raw/main/whisper/assets/mel_filters.npz
wget -O models/audio/tokenizer.json \
  "https://huggingface.co/openai/whisper-tiny.en/resolve/main/tokenizer.json?download=true"
wget -O data/samples/jfk.wav \
  https://github.com/ggml-org/whisper.cpp/raw/master/samples/jfk.wav

# 4. 컨테이너 의존성 1회 추가 (재빌드는 정식 lock 갱신 시)
pip install tokenizers

# 5. 호스트 검증 — JFK 11초 wav 입력 → 영어 텍스트 (호스트 baseline)
python3 src/transcribe.py \
  --model models/audio/whisper_tiny_en.tflite \
  --mel-filters models/audio/mel_filters.npz \
  --tokenizer models/audio/tokenizer.json \
  --input data/samples/jfk.wav

# 기대 출력: >>> And so my fellow Americans ask not what your country can do for you...
# 호스트 (Ryzen 7) latency: ~1.3초

exit   # 컨테이너 빠져나옴
```

호스트 WSL:

```bash
# 6. 디바이스 SSH 변수 (본인 값으로 override)
export UNO_Q_USER=arduino
export UNO_Q_HOST=192.168.0.45

# 7. 디바이스 audio 의존성 1회 셋업 (호스트 → 디바이스 SSH)
bash scripts/setup_device_audio.sh
ssh -t ${UNO_Q_USER}@${UNO_Q_HOST} 'sudo apt install -y libportaudio2'
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && pip install sounddevice scipy tokenizers soundfile'

# 8. 자산 디바이스 전송 (모델 + mel + tokenizer + jfk wav + 3 src)
scp models/audio/whisper_tiny_en.tflite models/audio/mel_filters.npz models/audio/tokenizer.json \
    ${UNO_Q_USER}@${UNO_Q_HOST}:/opt/unoq-yolo/models/
scp data/samples/jfk.wav ${UNO_Q_USER}@${UNO_Q_HOST}:/opt/unoq-yolo/media/
scp src/preprocess.py src/tokenizer.py src/transcribe.py ${UNO_Q_USER}@${UNO_Q_HOST}:~/

# 9. 디바이스 검증 — 같은 JFK wav (feature 일치 게이트, 호스트와 같은 텍스트 나와야 함)
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && python3 ~/transcribe.py \
  --model /opt/unoq-yolo/models/whisper_tiny_en.tflite \
  --mel-filters /opt/unoq-yolo/models/mel_filters.npz \
  --tokenizer /opt/unoq-yolo/models/tokenizer.json \
  --input /opt/unoq-yolo/media/jfk.wav'

# 디바이스 latency: invoke ~2초, total ~3.5초

# 10. 마이크 녹음 + 인식 (실시간 시연, 10초 발화)
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && \
  mkdir -p /tmp/unoq-yolo/audio-debug && \
  python3 -u ~/transcribe.py \
    --model /opt/unoq-yolo/models/whisper_tiny_en.tflite \
    --mel-filters /opt/unoq-yolo/models/mel_filters.npz \
    --tokenizer /opt/unoq-yolo/models/tokenizer.json \
    --record 10 --device 0 --save /tmp/unoq-yolo/audio-debug/'

# 카운트다운 3-2-1 후 "*** SPEAK NOW ***" 메시지가 나오면 즉시 영어 발화
# 예: "Hello robot. Come here. Stop. Yes. No. Turn on the light."

# 11. 녹음된 wav 회수 (재생/검토용)
mkdir -p data/samples/recorded
scp "${UNO_Q_USER}@${UNO_Q_HOST}:/tmp/unoq-yolo/audio-debug/record_*.wav" data/samples/recorded/
```

## 폴더 구조

```
asr/
├── README.md                       (본 문서)
├── docker/
│   ├── Dockerfile.asr              Ubuntu 22.04 + Python 3.10 + audio system libs
│   ├── requirements-asr.txt        의도 표현 (12 패키지)
│   ├── .dockerignore
│   └── run-asr.sh                  원샷 빌드+진입 (SCRIPT_DIR 패턴)
├── scripts/
│   └── setup_device_audio.sh       디바이스 PortAudio + pip + smoke test
├── src/
│   ├── preprocess.py               wav → mel (numpy 자작, Whisper 알고리즘 복제)
│   ├── tokenizer.py                HF tokenizers wrapper
│   ├── transcribe.py               통합 진입점 (--input wav / --record N)
│   └── validate_kws.py             모델 introspection + 단발 latency
├── models/audio/                   (다운로드 자산 — git에는 미포함)
│   ├── whisper_tiny_en.tflite      40 MB, MIT
│   ├── mel_filters.npz             7 KB
│   └── tokenizer.json              2 MB
├── data/
│   ├── samples/                    테스트 wav (jfk.wav 등)
│   └── samples/recorded/           디바이스 녹음 회수
├── benchmarks/audio/               (측정 결과 JSON)
├── docs/
│   ├── 00_project_blueprint.md                      한 페이지 청사진
│   ├── 01_preflight_notes.md                        작업 시작 전 체크리스트 + 함정
│   ├── 02_quickstart_asr.md                         본 README의 상세 절차 (디버깅 항목 포함)
│   ├── 03_implementation_log.md                     실제 진행 + 함정 8건 + 해결
│   ├── 04_quickstart_kws_tflite_unoq.md             KWS 진입 절차 (v0.3.0 후보 모델)
│   ├── 05_robust_kws_inference_code.md              KWS 추론 코드 가이드
│   └── 06_testing_benchmarking_reliability_kws.md   KWS 측정/신뢰도 가이드
└── (예정) src/audio_io.py, src/vad.py, src/infer_mic.py, src/benchmark_asr.py
```

## 알려진 함정 (외부 진입자 주의)

상세는 [`docs/03_implementation_log.md`](docs/03_implementation_log.md) 참조. 빈번 함정 5개:

1. **컨테이너에 `python` 명령 없음** — `python3` 사용.
2. **`scp` / `ssh`는 호스트 WSL에서** — 컨테이너 안에선 OpenSSH 미설치.
3. **nested SSH 함정** — 디바이스 SSH 안에서 또 `ssh` 명령 X. `exit`로 호스트 복귀.
4. **USB Audio Class 16 kHz 지원 X** — `transcribe.py`가 자동 fallback (48 kHz → 16 kHz resample).
5. **ssh non-tty stdout buffering** — `python3 -u` 옵션으로 unbuffered, "SPEAK NOW" 메시지 즉시 표시.

## 라이선스 (3중 클린)

| 계층 | 라이선스 | 상업 사용 |
|---|---|---|
| 본인 코드 (`src/`, `scripts/`, `docker/`) | (Public 전환 시) Apache-2.0 권장 | OK |
| 모델 (Whisper Tiny.en) | MIT (OpenAI) | OK |
| Mel filter bank | MIT (Whisper 공식) | OK |
| Tokenizer | Apache-2.0 (OpenAI) | OK |
| 학습 데이터 (Whisper) | OpenAI 자체 수집 | OK |
| 의존 패키지 | BSD / Apache / MIT 계열 | OK |
| 테스트 wav (jfk.wav) | Whisper.cpp 샘플 (예시 자료) | OK |

## 관련 프로젝트

- **`unoq-companion-robot`** (vision 라인): Arduino UNO Q 위 YOLOv8n int8 객체 검출, 9.23 FPS 합격선 통과.
- 두 모듈은 형제 폴더 (`c:\Project\vision/` + `c:\Project\asr/`)로 임시 분리. 향후 monorepo 통합 예정. 상세는 [`docs/00_project_blueprint.md`](docs/00_project_blueprint.md) §8 참조.

## 다음 단계

| 우선순위 | 작업 | 상태 |
|---|---|---|
| 1 | Silero VAD 추가 → 이벤트 기반 운영 (vision 동시 운영 핵심) | 미실시 |
| 2 | `src/benchmark_asr.py` 100회 벤치 + RSS + temp + JSON (멘토 06 형식) | 미실시 |
| 3 | LibriSpeech / 본인 녹음으로 WER 측정 (정량 정확도) | 미실시 |
| 4 | Vision + ASR 동시 운영 thermal soak test 8h+ | 미실시 |
| 5 | MCU(STM32U585) 통신 + fusion (음성 의도 → 동작 트리거) | 미실시 |
| 6 | monorepo 통합 (개선방안: `vision/docs/improvement_monorepo_restructure.md`) | 미실시 |

## 문의 / 기여

- 작성자: DongHee Kim (donghee-ai), 한성대
- 멘토 가이드 기반 원칙 적용 (출처는 본인 docs에 일반 원칙으로만 인용, 멘토 docs 자체는 별도 폴더 대외비 처리)
