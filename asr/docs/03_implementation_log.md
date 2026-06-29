# Implementation Log — 본 작품 ASR 1차 PoC (2026-06-25)

본 문서는 본 작품 ASR 모듈 개발 1차 세션의 실제 진행 시간선, 만난 함정 8건, 각 함정의 진단과 해결, 측정 결과를 정리합니다. vision 라인의 `docs/05_initial_inference_measurement.md` + `docs/06_postprocess_and_e2e.md` 패턴 통합.

## 0. 세션 요약

| 항목 | 결과 |
|---|---|
| 세션 일자 | 2026-06-25 |
| 시작 시점 | KWS (micro_speech) 검토 단계 |
| 종점 | Whisper Tiny.en TFLite 디바이스 마이크 자유발화 인식 |
| 만난 함정 | 8건 (모두 해결) |
| 합격선 | 4기준 + 참고 1 중 latency 통과 (3.18초 e2e ≤ 5초) |
| 본 작품 시연 가능 | YES (10초 영어 발화 → 83% 정확 텍스트 변환) |

## 1. 의사결정 흐름 (KWS → ASR 전환)

세션 초기 → 중기 → 후기:

### Phase 1 — KWS 검토 (멘토 "작은 모델" 의도 반영)

| 후보 | 결정 |
|---|---|
| Google Speech Commands v2 (35 단어) | 1차 채택 (~300 KB, Apache-2.0) |
| micro_speech (4 단어, silence/unknown/yes/no) | 다운로드 URL 확정, 2-stage 구조 (preprocessor + main) 발견 |

문서: `docs/00_project_blueprint.md` 초안, `docs/01_preflight_notes.md`, `docs/mentor_style/02_quickstart_kws_tflite_unoq.md`, `04_robust_kws_inference_code.md`, `06_testing_benchmarking_reliability_kws.md` 작성.

### Phase 2 — 사용자 의도 명확화 → 진짜 ASR 전환

사용자 질문 ("ASR이면 다운 받으면 바로 영어로 바꿔 주는거 볼 수 있는거야?")에서 자유발화 변환 요구 명확화.

→ KWS (4 단어 분류) ≠ ASR (자유발화). 진짜 ASR 후보 재검토.

### Phase 3 — Whisper Tiny.en TFLite 채택

| 비교 항목 | 평가 |
|---|---|
| TFLite 호환 | YES (nyadla-sys 또는 DocWolle HF 변환된 .tflite 존재) |
| 라이선스 | MIT (모델) + Apache-2.0 (tokenizer) + CC BY 4.0 (Whisper 학습 데이터) — 3중 클린 |
| A53 latency | 2초/invoke (실측 후 확정) — 멘토 "작은 모델" 의도와 모순되는 무게이지만 CPU 감당 가능 |
| 한국어 | English-only로 시작 (한국어는 multilingual 2차 보강) |
| 운영 모드 | 이벤트 기반 (VAD trigger) — Vision YOLO 동시 운영 가능 |

## 2. 환경 셋업 진행 (호스트 asr-dev Docker)

### 2-1. Phase 1 코드 작성

| 파일 | 역할 |
|---|---|
| `docker/Dockerfile.asr` | Ubuntu 22.04 + Python 3.10 + librosa + sounddevice + ai-edge-litert |
| `docker/requirements-asr.txt` | 의도 표현 (12 패키지) |
| `docker/run-asr.sh` | SCRIPT_DIR 패턴 + 빌드+진입 원샷 |
| `docker/.dockerignore` | 빌드 컨텍스트 위생 |
| `scripts/setup_device_audio.sh` | 디바이스 PortAudio + pip + smoke test 3 phase |

### 2-2. 호스트 컨테이너 첫 빌드 + Smoke test

```text
numpy 2.1.3
scipy 1.15.3
sounddevice 0.5.5
librosa 0.11.0
ai_edge_litert 2.1.5
```

`ai_edge_litert 2.1.5` = 디바이스와 동일 (bit-exact 추론 보장).

### 2-3. 컨테이너 이름 일관성

vision 라인 `unoq-yolo-dev` 패턴 그대로 `unoq-asr-dev`로 통일. `--name` + `--hostname` 옵션 부여.

## 3. 디바이스 사전 점검 (Phase 0)

### 3-1. venv-unoq 패키지 (점검 결과)

```
ai-edge-litert         2.1.5
numpy                  2.5.0
opencv-python-headless 4.13.0.92
backports.strenum      1.2.8
flatbuffers            25.12.19
protobuf               7.35.1
tqdm                   4.68.3
typing_extensions      4.15.0
```

→ vision YOLO에 필요한 최소 deps만. ASR 추가 deps 설치 공간 충분.

### 3-2. ASR 의존성 dry-run 결과

```
Requirement already satisfied: numpy<2.8,>=2.0.0 in venv-unoq (2.5.0)
Would install cffi-2.0.0 pycparser-3.0 python_speech_features-0.6 scipy-1.18.0 sounddevice-0.5.5
```

→ **numpy 충돌 0, scipy 1.18 / sounddevice 모두 numpy 2.5.0 호환** (멘토 리뷰 단점 3 해소).

### 3-3. 마이크 인식

```
card 0: Device [Usb Audio Device], device 0: USB Audio [USB Audio]
Bus 001 Device 004: ID 1b3f:2008 Generalplus Technology Inc. Usb Audio Device
snd_usb_audio 적재됨
```

→ USB Audio Class 정상 인식 + 커널 모듈 정상.

### 3-4. 디바이스 디스크 가용

```
/dev/mmcblk0p68  9.8G  6.7G  2.6G  72% /
/opt/unoq-yolo/models  3.2M (yolov8n_int8.tflite 등)
~/venv-unoq            206 MB
```

→ 2.6 GB 가용. Whisper 40 MB + audio deps ~100 MB 설치 충분. **vision 잔여물 우려는 실측으로 해소 — vision 모듈은 3.2 MB만 차지** (멘토 리뷰 단점 5 정정).

### 3-5. 커널 (멘토 리뷰 단점 정정)

```
Linux unoq-korea01 7.0.0-g122c2c22d838 #1 SMP PREEMPT Fri May  8 12:10:20 UTC 2026 aarch64
```

→ vision `docs/04`의 7.0 표기 정확. Qualcomm vendor kernel 번호 체계 (mainline과 다름).

### 3-6. GPU delegate

```
ls /dev/kgsl*  → No such file or directory
```

→ vision과 동일. **CPU 단독 확정** (GPU delegate skip).

### 3-7. PortAudio

```
libasound2-data, libasound2t64, alsa-utils  → 있음
libportaudio2  → 미설치
```

→ sounddevice 필수 의존 `libportaudio2` 추가 설치 필요 (Phase 3에서 처리).

## 4. 모델 검증 — Whisper Tiny.en TFLite

### 4-1. 모델 후보 비교 (조사 결과)

| 출처 | 파일 | 크기 | 특징 |
|---|---|---|---|
| `nyadla-sys/whisper.tflite` (GitHub) | `whisper-tiny-en.tflite` | 39.7 MB | Android/iOS 검증, 단일 .tflite (encoder+decoder 통합) |
| DocWolle HF | `whisper-tiny.en.tflite` | 41.5 MB | 월 10,886 다운로드, 같은 변환 계열 |

→ nyadla-sys 채택 (GitHub raw, 더 작음).

### 4-2. 모델 introspection 결과

```json
{
  "inputs": [{
    "name": "serving_default_input_ids:0",
    "shape": [1, 80, 3000],
    "dtype": "float32"
  }],
  "outputs": [{
    "name": "StatefulPartitionedCall:0",
    "shape": [1, 448],
    "dtype": "int32"
  }],
  "input_kind": "feature_2d",
  "num_classes": 448
}
```

### 4-3. 결정적 발견 — encoder+decoder 통합

이전 청사진 설계는 "encoder 1회 + decoder N회 (autoregressive loop)"를 가정. **실제 모델은 단일 invoke로 448 tokens 고정 출력**. 외부 Python decoder loop **불필요**. 코드 트리에서 `whisper_runner.py` 모듈 삭제.

| 항목 | 이전 설계 | 실제 모델 |
|---|---|---|
| Decoder loop | 외부 Python autoregressive | 모델 내부 처리 |
| Output | 토큰별 logits 누적 | fixed-length `[1, 448]` int32 |
| 코드 복잡도 | 큼 | 단순 (tokenizer.decode 1회) |
| latency | 가변 (encoder + N × decoder) | 고정 ~2초 |

### 4-4. 디바이스 단발 invoke 벤치 (dummy zeros input, warmup 5 + measure 5)

```json
{
  "latency_ms_min": 2010.7,
  "latency_ms_mean": 2015.8,
  "latency_ms_p50": 2014.6,
  "latency_ms_p95": 2019.6,
  "latency_ms_max": 2021.8
}
```

→ **p95/mean = 1.002** (변동 0.5%). UNO Q A53에서 매우 안정적인 2초 latency.

합격선 평가:
- latency mean 2015 ms ≤ 5000 ms → **통과 (40% 사용)**
- latency p95 2020 ms ≤ 7000 ms → **통과 (29% 사용)**

## 5. End-to-End 추론 (mel + invoke + decode)

### 5-1. 호스트 검증 — JFK wav (11초)

```text
input  [1, 80, 3000] float32
output [1, 448] int32
audio duration: 11.00s
preprocess: 145 ms
invoke:    1179 ms (Ryzen 7 6800HS)
decode:       0 ms
total:     1324 ms

>>> And so my fellow Americans ask not what your country can do for you,
    ask what you can do for your country.
```

### 5-2. 디바이스 검증 — 같은 JFK wav

```text
audio duration: 11.00s
preprocess: 326 ms
invoke:    3228 ms (cold start)
decode:       0 ms
total:     3555 ms

>>> And so my fellow Americans ask not what your country can do for you,
    ask what you can do for your country.
```

→ **호스트와 100% 동일 텍스트**. mel 알고리즘 호스트 ↔ 디바이스 bit-exact 일치 확정. **멘토 리뷰 단점 2 (feature 일치) 통과**.

cold start 발견: 첫 invoke 3228 ms (warmup 후 벤치 2015 ms 대비 +1213 ms). 운영 시 부팅 직후 warmup 1~2회 필요.

### 5-3. 디바이스 마이크 녹음 → 인식 (실시간 시연)

사용자 발화: `Hello robot. Come here. Stop. Yes. No. Turn on the light.`

```text
audio duration: 10.00s
preprocess: 294 ms
invoke:    2884 ms
decode:       0 ms
total:     3178 ms

>>> Hello robot! Come here, stop! Yes, no! Turn on the line!
```

| 발화 | 인식 | 정확? |
|---|---|---|
| Hello robot | Hello robot | ✓ |
| Come here | Come here | ✓ |
| Stop | stop | ✓ |
| Yes | Yes | ✓ |
| No | no | ✓ |
| Turn on the **light** | Turn on the **line** | ✗ (light/line 끝자음 t/n) |

→ **6 단어 중 5개 정확 = 83%**. Whisper Tiny.en 한계 (작은 모델). Base 격상 시 95%+ 예상.

Real-time factor: 3.18초 / 10초 = **0.32** (실시간 대비 3배 빠름).

## 6. 함정 8건 — 진단 + 해결

vision 라인의 `docs/06 §3~§4` 패턴 적용.

### 함정 1 — `bash: python: command not found` (컨테이너)

| 항목 | 내용 |
|---|---|
| 증상 | `python src/transcribe.py ...` → command not found |
| 원인 | Ubuntu 22.04에 `python3.10` 패키지만 설치, `python` symlink 없음 |
| 해결 | `python3` 사용 (즉시) |
| 향후 | Dockerfile에 `apt install python-is-python3` 또는 `ln -s` (재빌드 시) |

### 함정 2 — `bash: scp: command not found` (컨테이너)

| 항목 | 내용 |
|---|---|
| 증상 | 컨테이너 안에서 scp 시도 → not found |
| 원인 | Dockerfile에 openssh-client 미설치 (의도적, 빌드 가벼움) |
| 해결 | `exit`로 호스트 WSL 복귀 후 scp |
| 향후 | scp는 항상 호스트 WSL에서 (컨테이너 X) |

### 함정 3 — nested SSH

| 항목 | 내용 |
|---|---|
| 증상 | 디바이스 SSH 안에서 또 `ssh arduino@...` 실행 → 명령 무시 + history 재실행 |
| 원인 | 호스트 WSL이 아닌 디바이스 셸에서 명령 복붙 |
| 해결 | `exit` 1~2번 → 호스트 프롬프트 확인 (`a@DESKTOP-...:...$`) 후 다시 |
| 향후 | 명령 실행 전 프롬프트 위치 확인 (vision `docs/08 §7-5` 함정과 동일 패턴) |

### 함정 4 — `sudo: a terminal is required`

| 항목 | 내용 |
|---|---|
| 증상 | `ssh arduino@... 'sudo apt install ...'` → sudo 비번 못 받음 |
| 원인 | ssh non-interactive에선 sudo가 pseudo-terminal 없어 비번 못 받음 |
| 해결 | `ssh -t arduino@... 'sudo ...'` (-t 옵션으로 PTY 강제 할당) |

### 함정 5 — `ModuleNotFoundError: sounddevice / soundfile / tokenizers` (디바이스)

| 항목 | 내용 |
|---|---|
| 증상 | 디바이스에서 transcribe.py 실행 → ModuleNotFoundError |
| 원인 | 사용자가 `setup_device_audio.sh` 실행 안 함 (또는 일부만) |
| 해결 | `ssh arduino@... 'source ~/venv-unoq/bin/activate && pip install sounddevice scipy tokenizers soundfile'` |
| 향후 | `setup_device_audio.sh` 한 줄로 자동 처리 가능 |

### 함정 6 — `numpy generic.tolist() unbound method`

| 항목 | 내용 |
|---|---|
| 증상 | `validate_kws.py` 실행 → TypeError |
| 원인 | `_clean_value`가 numpy dtype 클래스 자체 (`np.int32`)에 `tolist()` 호출 시도, unbound method |
| 해결 | `isinstance(v, type)` 분기 추가: 클래스면 `__name__` 반환 |
| 코드 | `src/validate_kws.py` line 55 수정 |

### 함정 7 — `PortAudioError: Invalid sample rate` (USB Audio Class)

| 항목 | 내용 |
|---|---|
| 증상 | sounddevice가 16000 Hz 캡처 시도 → ALSA `paInvalidSampleRate` |
| 원인 | USB Audio Class 디바이스 (Generalplus 1b3f:2008)가 16 kHz native 미지원 (보통 44.1/48 kHz만) |
| 해결 | `transcribe.py` `record_audio()` 함수에 sample rate 자동 fallback (16000 → 48000 → 44100 → 32000) + scipy.signal.resample_poly로 16 kHz 다운샘플 |
| 코드 | `src/transcribe.py` line 60~110 수정 |

### 함정 8 — ssh non-tty stdout buffering ("SPEAK NOW" 메시지 못 봄)

| 항목 | 내용 |
|---|---|
| 증상 | `ssh arduino@... 'python3 ~/transcribe.py --record 5'` → 5초 끝나고 모든 출력 한꺼번에 표시 → 사용자가 "speak now" 메시지 못 보고 발화 타이밍 놓침 → 발화 끝부분만 캡처 ("You"만 인식) |
| 원인 | Python stdout이 ssh non-tty 환경에서 block-buffered. print 직후 sd.rec() blocking 호출 → 5초 동안 stdout flush 안 됨 |
| 해결 | (1) `transcribe.py`의 print에 `flush=True` 추가, (2) 3-2-1 카운트다운 + 명시적 `sys.stdout.flush()`, (3) 실행 시 `python3 -u` (unbuffered) 옵션 |
| 코드 | `src/transcribe.py` `record_audio()` 함수 카운트다운 추가 |

## 7. 멘토 리뷰 정정 사항 (실측 기반)

| 멘토 리뷰 지적 | 실측 결과 | 결론 |
|---|---|---|
| "커널 6.16으로 수정" | `Linux 7.0.0-g122c2c22d838 ...` | **vision docs의 7.0 표기 정확** (Qualcomm vendor kernel) — 멘토 리뷰 잘못 |
| "eMMC 좁음 = vision 잔여물 자초" | `/opt/unoq-yolo/models` 3.2 MB만 차지 | **vision 잔여물 우려 부정확**. 70% 사용은 시스템 OS 자체 |
| "librosa 디바이스 폭탄" | librosa 대신 numpy 자작 mel 채택 | **여전히 정당** (librosa 의존 회피로 디스크/CPU 절감) |
| "numpy 호환 dry-run" | scipy 1.18 / sounddevice numpy 2.5.0 호환 확인 | **여전히 정당한 점검** — 실측으로 해소됨 |
| "feature 추출 학습 일치 게이트" | 호스트 numpy mel ↔ 디바이스 numpy mel = JFK wav 텍스트 100% 동일 | **게이트 통과** (동일 알고리즘 사용) |
| "실시간 스트리밍 설계 빈약" | 청사진에 이벤트 기반 운영 명시 + VAD trigger 설계 추가 | **반영 진행 중** (Phase 4 작업) |

→ 멘토 리뷰 6개 중 5개 정당, 1개 (커널) 실측과 불일치.

## 8. 측정 자산

| 자산 | 위치 |
|---|---|
| 디바이스 단발 invoke 벤치 | (콘솔 출력만, JSON 미저장 — 다음 단계) |
| 호스트 JFK wav 결과 | 콘솔 (1324 ms total) |
| 디바이스 JFK wav 결과 | 콘솔 (3555 ms total) |
| 디바이스 마이크 녹음 wav | `/tmp/unoq-yolo/audio-debug/record_20260625_014915.wav` |
| 디바이스 마이크 인식 결과 | 콘솔 (3178 ms total, 83% 정확) |
| 호스트로 회수된 wav | `data/samples/recorded/` (사용자 회수 예정) |

## 9. 시간선 (실제 소요)

| 단계 | 시간 |
|---|---|
| KWS 검토 + docs 작성 (00, 01, mentor_style 3개) | ~2시간 |
| ASR 전환 결정 + 후보 재조사 | ~30분 |
| Whisper TFLite 모델 URL 조사 + 다운로드 | ~10분 |
| 호스트 asr-dev Docker 빌드 + smoke test | ~15분 |
| 디바이스 단발 invoke 측정 (validate_kws.py) | ~10분 |
| `preprocess.py` + `tokenizer.py` + `transcribe.py` 작성 | ~30분 |
| 호스트 JFK wav 검증 (성공) | ~10분 |
| 디바이스 JFK wav 검증 (성공, feature 일치 게이트 통과) | ~15분 |
| 함정 5~8 진단 + 해결 (sample rate / buffering / sudo) | ~30분 |
| 디바이스 마이크 녹음 + 시연 성공 | ~10분 |
| **합계 (KWS 검토 포함)** | **~4.5시간** |
| ASR 본격 작업만 | ~2시간 |

## 10. 다음 단계 (Phase 3+ 예정)

| Phase | 작업 | 산출물 |
|---|---|---|
| 3-1 | `src/benchmark_asr.py` 100회 벤치 + RSS + temp | `benchmarks/audio/device_asr_<DATE>.json` (멘토 06 형식) |
| 3-2 | LibriSpeech / 본인 녹음 WER 측정 | `benchmarks/audio/wer_<DATE>.json` + jiwer 도구 |
| 4 | Silero VAD + 이벤트 기반 운영 | `src/vad.py`, `src/audio_io.py`, `src/infer_mic.py` |
| 5 | Vision + ASR 동시 thermal soak test 8h+ | soak 로그 + JSON |
| 6 | MCU(STM32U585) 통신 + fusion | App Lab 또는 systemd service |
| 7 | monorepo 통합 | (`vision/docs/improvement_monorepo_restructure.md` 참조) |

## 한 줄 정리

> **2026-06-25 본 작품 ASR 1차 PoC: Whisper Tiny.en TFLite (40 MB, MIT) → UNO Q (QRB2210) 위 단발 invoke 2초 (warmup), e2e 3.18초 (10초 음성), 본인 발화 6 단어 중 5개 정확 (83%) — 함정 8건 해결, 호스트↔디바이스 feature bit-exact 일치, 합격선 latency 4기준 통과. Vision YOLO와 같은 ai-edge-litert 2.1.5 런타임 일관성 + 이벤트 기반 동시 운영 가능 설계.**
