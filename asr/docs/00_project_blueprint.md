# Project Blueprint — UNO Q Real-time ASR (Whisper Tiny.en)

본 문서는 본 모듈의 전반적 청사진을 한 페이지로 정리합니다. UNO Q 디바이스 사양, 모델 선택 결과와 대안 후보, 데이터셋과 아키텍처, 합격 기준, 그리고 후속 문서들의 진행 흐름을 포함합니다. `unoq-companion-robot` (vision 라인)과의 관계도 명시합니다.

## 0. 프로젝트 목적

Arduino UNO Q (Qualcomm Dragonwing QRB2210, CPU only) 위에서 **Whisper Tiny.en TFLite (자유발화 ASR)** 모델로 사용자 음성을 텍스트로 변환하여 교감로봇의 의도 이해 + 응답 트리거에 활용하는 음성 입력 모듈. 1차 PoC 단계 — **영어 전용 (English-only)** 사전학습 Whisper Tiny 채택, 한국어 (Multilingual)는 2차 보강.

운영 모드: **이벤트 기반 (event-driven)** — Silero VAD가 발화 감지 시에만 Whisper 호출. 평소엔 vision YOLO 9 FPS 그대로 유지.

본 모듈은 멘토 요청("음성 모델 ASR 하나 올려봐, 음성으로 조정하거나 해야하잖아, 작은 모델로")에 대한 직접 응답이며, 본인 교감로봇 작품의 음성 입력 채널을 담당합니다.

## 1. UNO Q 디바이스 스펙

| 항목 | 값 |
|---|---|
| **SoC** | Qualcomm Dragonwing QRB2210 (Agatti) |
| **CPU** | Arm Cortex-A53 ×4 @ 2.0 GHz |
| **GPU** | Adreno 702 (저티어, 본 모듈은 CPU 단독 경로) |
| **MCU** | STM32U585 (Arm Cortex-M33, ~160 MHz) |
| **RAM** | 4 GB LPDDR4 (가용 2.4 GiB) |
| **eMMC** | 16 GB (root `/`엔 9.8 GB 할당, 가용 2.9 GB) |
| **OS** | Linux Debian aarch64 (kernel 7.0) |
| **AI 가속기** | 없음 (DSP / HTP / NPU 모두 미장착) |
| **공식 AI 런타임** | TFLite (LiteRT) 단독. QAIRT / SNPE / QNN 미지원 |
| **마이크** | USB UVC Audio Class (보유 — 디바이스 인식 점검 필요) |

런타임은 `ai-edge-litert` — vision 라인과 동일. 4 스레드 CPU + XNNPACK delegate.

## 2. 모델 선택

### 2-1. 1차 채택 — Google Speech Commands v2 TFLite (KWS)

| 항목 | 값 |
|---|---|
| **모델** | Google Speech Commands v2 (KWS, Keyword Spotting) |
| **크기** | ~300 KB int8 (또는 float32 ~수백 KB) |
| **입력** | 1초 16 kHz mono PCM → MFCC / log-Mel spectrogram |
| **출력** | 35 클래스 확률 (영어 단어) |
| **양자화** | int8 (사전 양자화 제공) |
| **라이선스** | Apache-2.0 (모델 + 데이터 + 코드 3중 클린) |
| **획득 경로** | TF Hub / TF examples / Google AI Edge |

### 2-2. 채택 근거 (5가지)

1. **TFLite 즉시 사용** — vision YOLO와 같은 `ai-edge-litert` 런타임, 추가 변환 작업 0
2. **3중 라이선스 클린** — 모델 Apache-2.0 / 데이터 CC BY 4.0 / 코드 Apache-2.0 → 상업 배포 안전
3. **0.3 MB 모델** = YOLOv8n int8 (3.19 MB)의 1/10 → 멘토 "작은 모델로" 의도 정확히 일치
4. **본 작품 컨셉 정합** = 교감로봇 명령 트리거 ("이리와 / 정지 / 따라와") — 자유발화 불필요, KWS가 본질적으로 적합
5. **YOLO 동시 실행 부담 없음** — < 30 ms KWS + ~100 ms YOLO를 별 스레드로 돌려도 thermal margin 영향 미미

### 2-3. 전환 트리거와 대안

| 조건 | 액션 |
|---|---|
| 디바이스 KWS latency ≤ 50 ms + accuracy ≥ 80% | Speech Commands 유지, 한국어 fine-tune 검토 |
| latency > 50 ms (overkill 신호) | TFLite Micro KWS 예제로 다운사이즈 (~100 KB) |
| accuracy < 60% (35 클래스 부담) | 명령 단어 수 축소 (top-N) 또는 본인 도메인 데이터 fine-tune |
| 자유발화 한국어 필요 | Whisper Tiny int8 (MIT) — 2차 보강 |

### 2-4. 대안 후보 (사전 조사, 적용은 트리거 충족 시)

| 모델 | 종류 | 라이선스 | 상업 가능 | 메모 |
|---|---|---|---|---|
| TFLite Micro KWS 예제 | KWS | Apache-2.0 | OK | <100 KB, MCU급도 동작 — 다운사이즈 후보 |
| Whisper Tiny | Full ASR | MIT | OK | 39 MB int8, 한국어 가능, 1~3초 청크 latency |
| Vosk small | Full ASR | Apache-2.0 | OK | TFLite 아님 (Kaldi) — 호환성 부담 |
| Porcupine | Wake word | 상용 | **차단** | 무료 평가 가능하나 상업 라이선스 별도 |
| Coqui STT | Full ASR | MPL-2.0 | 조건부 | 수정 파일만 공개 의무 |

상세 비교는 [01_model_selection_log.md](01_model_selection_log.md) 작성 예정.

## 3. 데이터셋

| 용도 | 데이터셋 | 출처 / 라이선스 |
|---|---|---|
| **추론 클래스 라벨** | 35단어 (yes/no/up/down/left/right/on/off/stop/go/zero~nine/sheila/marvin/visual/...) | Google Speech Commands v2 표준 |
| **모델 학습 (사전학습)** | Google Speech Commands v2 (~106k 발화, ~2.6k 화자) | CC BY 4.0 |
| **int8 양자화 calibration** | 표준 calibration set (모델 export 시 포함됨) | Apache-2.0 |
| **본 작품 검증** | 본인 목소리 + 표준 샘플 wav | 본인 녹음 |

본 모듈은 별도 도메인 학습 없이 표준 사전학습 그대로 사용. 향후 한국어 명령 fine-tune은 2차 보강 단계.

## 4. 모델 아키텍처

### 4-1. 입출력 텐서 (예상, 모델 다운로드 후 확정)

| 텐서 | shape (예상) | dtype |
|---|---|---|
| **Input** | `[1, 49, 40, 1]` (MFCC 49 frames × 40 mel bins) 또는 `[1, 16000]` (raw PCM) | float32 또는 int8 |
| **Output** | `[1, 35]` (35 클래스 logit/probability) | float32 |

실제 shape는 호스트에서 `interpreter.get_input_details()` / `get_output_details()`로 자동 추출 — vision 라인 규약(`vision/docs/03 §5-1`)과 동일.

### 4-2. 후처리 파이프라인

1. raw mic input (16 kHz mono PCM) → 1초 sliding window
2. PCM → MFCC 또는 log-Mel spectrogram (`librosa` 또는 `tf.signal`)
3. dtype 변환 (float32 / uint8 / int8 분기 — vision 후처리 규약과 동일)
4. 모델 추론 (`interpreter.invoke()`)
5. softmax (logit인 경우) → top-1 class index
6. confidence threshold (기본 0.7) 필터
7. 클래스 ID → 단어 라벨 매핑 (`labels_35.txt`)
8. (옵션) MCU(STM32U585) 메시지 송신 또는 stdout 출력

코드 모듈 예정:
- `src/preprocess.py` — MFCC / log-Mel 변환
- `src/audio_io.py` — `sounddevice` 래퍼, 16 kHz PCM 캡처
- `src/validate_kws.py` — 모델 검증 + latency 측정 (vision `validate_model.py` 패턴)
- `src/infer_mic.py` — 실시간 마이크 → KWS → 라벨 루프
- `src/benchmark_kws.py` — 100회 벤치마크 (멘토 06 JSON 포맷)

## 5. 합격선 — 4기준 + 참고 1 (멘토 06 형식 준수)

vision 라인 합격 패턴 + ASR(Whisper) 특화 임계값. **2026-06-25 실측으로 latency 부분 통과 확정**.

| 기준 | 임계값 | 측정값 (2026-06-25) | 결과 |
|---|---|---|---|
| **추론 latency (mean, 30초 청크)** | ≤ 5 초 | **2.015 초** | **통과 (40% 사용)** |
| **추론 latency p95** | ≤ 7 초 | **2.020 초** | **통과 (29% 사용)** |
| **이벤트 응답 (발화 종료 → 텍스트)** | ≤ 5 초 | ~2.5~3 초 추정 (mel preprocess + invoke + decode) | 통과 예상 |
| **메모리 (max RSS, Whisper 활성)** | < 300 MB | 미측정 | 실시간 운영 단계 측정 |
| **온도 (max temp, 이벤트 기반)** | ≤ 70°C | 미측정 | soak test 단계 측정 |
| **정확도 (참고 지표)** | WER ≤ 15% | 미측정 (golden wav 미구축) | golden wav 셋 구축 후 |

분포 안정성: p95/mean = **1.002** (매우 안정, 변동 0.5%). UNO Q에서 Whisper Tiny.en이 일관된 2초 latency 보장 — 이벤트 기반 운영에 매우 유리.

Whisper Tiny.en은 vision (108 ms / 100 MB)보다 ~20배 무겁지만, **이벤트 기반 운영**(VAD trigger 시만 호출)이라 평균 부하는 작음. soak test에서 vision + audio 동시 thermal 검증 필수.

## 6. 진행 흐름 — 후속 문서

| 번호 | 문서 | 역할 | 소요 시간 (예상) |
|---|---|---|---|
| 00 | `00_project_blueprint.md` (본 문서) | 한 페이지 청사진 | 읽기만 |
| 01 | `01_preflight_notes.md` | 작업 시작 전 알아둘 점 (환경·규약·라이선스·함정·체크리스트) | 1회 정독 |
| 02 | `02_model_selection_log.md` | 후보 비교 + 라이선스 + 채택 근거 상세 | 작성 예정 |
| 03 | `03_host_env_setup.md` | `asr-dev` Docker (Dockerfile.asr + requirements-asr.lock) | 작성 예정 |
| 04 | `04_device_audio.md` | USB 마이크 인식 + `arecord -l` + `sounddevice` smoke test | 작성 예정 |
| 05 | `05_validation.md` | 모델 검증 + 호스트/디바이스 latency 측정 | 작성 예정 |
| 06 | `06_realtime_mic.md` | 실시간 마이크 → KWS → 라벨 출력 | 작성 예정 |
| 07 | `07_official_benchmark.md` | 100회 벤치마크 + 멘토 06 JSON | 작성 예정 |

## 7. 사전 조건 (외부 진입자용 체크리스트)

### 7-1. 호스트 PC

- Windows 11 + WSL2 (Ubuntu 24.04) — vision 라인과 동일
- Docker Desktop 또는 Docker Engine (별도 컨테이너 `asr-dev` 사용)
- 디스크 여유 ~3 GB (이미지 + 패키지 + 모델)

### 7-2. UNO Q 디바이스

- vision 라인 셋업 완료 상태 (venv-unoq + ai-edge-litert)
- USB 마이크 (USB Audio Class 표준) — 보유, 인식 점검 필요
- `arecord -l` / `cat /proc/asound/cards`로 디바이스 인식 확인

### 7-3. 디바이스 venv 추가 의존성

```bash
# 디바이스에서 (venv-unoq 활성화 상태)
pip install sounddevice scipy librosa
```

numpy 메이저 호환성 사전 점검 (vision의 numpy 2.5.0과 충돌 여부 확인 필요).

### 7-4. 시작 명령 (호스트 WSL에서)

```bash
cd /mnt/c/Project/unoq-companion-robot/asr
bash docker/run-asr.sh                   # 컨테이너 진입 (작성 예정)
```

## 8. `unoq-companion-robot` (vision 라인)과의 관계

### 8-1. 현재 — 형제 폴더 분리

```text
c:\Project\
├── vision/     ← vision 라인 (YOLO + 카메라, 9.23 FPS 합격선 통과)
└── asr/                 ← audio 라인 (KWS, 본 폴더)
```

분리 사유:
- 시간 압박 (멘토 보고 데드라인)
- 의존성 충돌 회피 (`librosa` · `scipy` ↔ `torch` · `numpy` ABI)
- vision 자산 보존 (안정화 상태 흔들지 않게)

### 8-2. 향후 — 단일 monorepo 통합 예정

통합 계획: [`vision/docs/improvement_monorepo_restructure.md`](../../vision/docs/improvement_monorepo_restructure.md) 참조.

통합 시점 트리거:
- fusion 코드 작성 (vision 검출 + audio 명령 결합)
- Public 전환 / 시연 단일 진입점 필요
- CI/CD 구축
- 멘토 최종 인계

통합 시 본 폴더 → `vision/src/unoq/audio/` + `docs/audio/` + `docker/audio/` 등으로 흡수.

### 8-3. 디바이스 측은 처음부터 통합

UNO Q `~/venv-unoq` 한 환경에 vision + audio 의존성 모두 설치. 호스트 측만 분리된 상태이며, 디바이스 측 작업은 vision 라인과 같은 venv / 경로 그대로 사용.

## 9. 멘토 가이드 채택 원칙 (출처 비표기)

vision 라인에서 채택한 원칙들을 그대로 본 모듈에도 적용:

### 9-1. 추론 코드 패턴
- dtype별 입력 변환 분기 (float32 / uint8 / int8)
- quantization parameter 자동 추출 (`get_input_details()`)
- GPU delegate optional + CPU fallback (본 작품은 CPU 단독 경로)
- latency p50/p95 + warmup 분리 측정

### 9-2. 벤치마크 JSON 형식

```json
{
  "model", "runtime", "input_shape", "frames",
  "latency_ms_p50", "latency_ms_p95", "fps_mean",
  "preprocess_ms_mean", "postprocess_ms_mean",
  "dropped_frames", "max_rss_mb", "max_temp_c"
}
```

### 9-3. 운영 안정성
- Soak test: 8h 연속 마이크 + KWS 추론 (향후)
- Watchdog: heartbeat 1s, no-heartbeat 5s restart
- 로그: JSON lines, raw 오디오 저장 default off (개인정보 보호)

### 9-4. 보안 / 개인정보 (음성 모듈 특화)
- 마이크 raw 오디오 저장 기본 off — 영상 저장 정책과 동일
- 디버그 wav 저장은 `--save-dir` opt-in
- 로컬 추론만, 클라우드 음성 인식 사용 안 함 (raw audio retention X)
- secrets 600 권한

## 10. 본 모듈의 작품 / 보고 가치

- 멘토 요청("음성으로 조정") 직접 응답
- Edge AI 멀티모달 (vision + audio) 단일 디바이스 구현 사례
- 모든 모델·데이터·코드 라이선스 상업 호환 (Apache-2.0 / CC BY 4.0)
- vision 라인 합격 측정 자산(9.23 FPS) 보존 + audio 라인 독립 검증
- 인터넷 미공개 데이터 포인트 예상: "QRB2210 + Speech Commands v2 KWS, CPU 4 thread XNNPACK = ? ms" 정확한 수치

## 11. 알려진 한계 (1차 PoC 단계)

| 한계 | 영향 | 향후 대응 |
|---|---|---|
| 영어 35단어만 인식 | 한국어 명령 불가 | transfer learning fine-tune (2차 보강) |
| 마이크 USB 인식 미검증 | 디바이스에서 동작 여부 미확정 | `03_device_audio.md` 단계에서 점검 |
| 노이즈 / 거리 영향 미검증 | 실제 책상 환경 정확도 미확인 | golden wav set + soak test |
| MCU(STM32U585) 트리거 미구현 | 음성 명령 → 실 동작 연결 안 됨 | fusion 단계 (vision + audio + MCU) |
| `unoq-companion-robot`과 분리 운영 | 호스트에서 두 컨테이너 진입 필요 | 통합 시점에 monorepo 흡수 |
| numpy 메이저 호환성 미검증 | vision venv와 audio venv 의존성 충돌 가능 | `02_host_env_setup.md` 단계에서 점검 |

## 한 줄 요약

> **Arduino UNO Q (QRB2210, CPU only) 위에서 Whisper Tiny.en TFLite (자유발화 ASR, MIT) 모델로 영어 발화를 텍스트 변환하는 음성 입력 모듈 — Silero VAD 이벤트 기반 운영으로 vision YOLO 동시 운영 + thermal 안정 목표, 1차 PoC는 영어 전용 + 한국어는 Multilingual 2차 보강 예정.**
