# KWS 모델 후보 — 상업 라이선스 안전 최우선 (2026-07-02)

> **이 문서의 숫자는 대부분 우리가 잰 값이 아니다.** 모델 크기·입출력 shape·정확도는
> 각 프로젝트가 발표한 사양이고, 채택 판단의 근거로 **참조**한 것이다.
> 디바이스 실측(latency / RSS / thermal)은 아직 하지 않았다 — 측정하면 이 문서가 아니라
> `docs/`의 벤치마크 문서와 `benchmarks/` JSON에 우리 값으로 따로 남긴다.

본 문서는 **상업 사용 가능한 KWS 모델** 후보 비교 + 채택 근거. 사용자 요건: **절대 라이센스 문제가 있어서는 안 됨** — Apache-2.0 / MIT / BSD-3 / CC-BY 4.0 만 허용, Non-Commercial / GPL / Custom EULA 는 전면 기각.

## 0. 라이선스 필터 결과

| 후보 | 코드 라이선스 | 데이터 라이선스 | 상업 가능 | 판정 |
|---|---|---|---|---|
| **MLPerf Tiny KWS DS-CNN INT8** | Apache-2.0 | CC BY 4.0 (Speech Commands v2) | ✓ | **1순위 채택** |
| **Google TFLM MicroSpeech** | Apache-2.0 | CC BY 4.0 (Speech Commands v2) | ✓ | **2순위 fallback** |
| ARM ML-KWS-for-MCU (DS-CNN Small) | Apache-2.0 | CC BY 4.0 | ✓ | 3순위 (모델 재훈련 필요 — 사전학습 가중치가 TFLite 로 shipped 안됨) |
| Silicon Labs MLTK KWS models | Apache-2.0 (repo) | CC BY 4.0 | ✓ | 예비 (다양한 vocab, 모델 파일 shipped) |
| openWakeWord | Apache-2.0 | 다양 (CC0/MIT) | ✓ | ONNX 전용 — stack 불일치로 기각 |
| Picovoice Porcupine | **Non-Commercial 무료** | proprietary | **X** | **기각** — 상업 시 유료 라이선스 필요 |
| Snowboy (Kitt.AI) | 서비스 종료 (2020) | — | **X** | **기각** — EOL |
| DeepSpeech Kaldi | Apache-2.0 | 다양 | △ | KWS 특화 아님 (STT 위주) |
| Vosk KWS | Apache-2.0 | Apache-2.0 | ✓ | 후보 — 하지만 STT 오버킬 (본 작품 4~12 단어만 필요) |
| Qualcomm AI Hub KWS | Qualcomm EULA | proprietary | △ | pose 라인과 동일 이유로 QRB2210 비호환 |

**필터 통과 최상위 3개**: MLPerf Tiny DS-CNN / Google MicroSpeech / Silicon Labs MLTK.

## 1. 1순위 — MLPerf Tiny KWS DS-CNN INT8

### 1-1. 출처

- 저장소: `https://github.com/mlcommons/tiny`
- 정확한 경로: `benchmark/training/keyword_spotting/`
- MLPerf Tiny 벤치마크의 공식 참조 모델 — MLCommons 관리, 산업 표준
- 학습 스크립트 + 가중치 모두 Apache-2.0

### 1-2. 라이선스 확인

`https://github.com/mlcommons/tiny/blob/master/LICENSE.md`:

> Apache License Version 2.0

Speech Commands Dataset v2 (Pete Warden, Google, 2018): **CC BY 4.0** — Creative Commons Attribution 4.0 International, 상업 사용 명시적 허용.

**결론**: 완전히 상업 안전. 필요 표기: "Trained on Google Speech Commands v2 (CC BY 4.0). Model architecture: MLPerf Tiny KWS reference (Apache-2.0)."

### 1-3. 모델 스펙

| 항목 | 값 |
|---|---|
| 아키텍처 | DS-CNN (Depthwise Separable CNN) — ARM 원본 설계 |
| 크기 (INT8) | ~52 KB |
| 입력 | `[1, 49, 10, 1]` int8 |
| 출력 | `[1, 12]` int8 (softmax pre-quantized) |
| 클래스 (12) | `Down, Go, Left, No, Off, On, Right, Stop, Up, Yes, _silence_, _unknown_` |
| 오디오 프론트엔드 | MFCC 10 계수, 25ms 윈도우, 10ms 홉, 1s 클립 → 49 프레임 |
| Sample rate | 16 kHz mono |
| 정확도 | **참조** ~90.5% — 출처: [MLPerf Tiny 리더보드](https://mlcommons.org/benchmarks/inference-tiny/). **우리 실측 아님** |

### 1-4. 다운로드 절차

MLPerf Tiny 저장소는 파일 위치를 정기적으로 재구성. 안전한 접근:

```bash
# 옵션 A — MLPerf Tiny 저장소 clone (가장 확실)
git clone --depth 1 https://github.com/mlcommons/tiny.git /tmp/mlperf-tiny
cp /tmp/mlperf-tiny/benchmark/training/keyword_spotting/trained_models/kws_ref_model.tflite \
   models/kws_ref_model_ds_cnn_int8.tflite

# 옵션 B — scripts/download_model.py 자동 시도
python3 scripts/download_model.py --model ds_cnn --dest models/
```

`scripts/download_model.py` 는 다중 URL fallback 을 시도하고 SHA256 검증. 실패 시 옵션 A 수동 clone 안내.

### 1-5. 채택 근거

| 근거 | 내용 |
|---|---|
| 라이선스 안전 | Apache-2.0 + CC BY 4.0 — 명시적 상업 허용 |
| 어휘 풍부 (12) | 모드 스위칭 명령 매핑 여유 (up/down/stop/go/yes/no) |
| 산업 표준 | MLPerf 참조 모델 → 벤치마크 대비 성능 검증 완료 |
| 크기 초소형 | 52 KB — pose 6.8 MB 대비 무시 가능 |
| stack 일치 | TFLite + XNNPACK — pose/vision/ASR 라인 동일 |
| chipset 비종속 | CPU 순수 (QRB2210 지원) |

## 2. 2순위 — Google TFLM MicroSpeech (fallback)

### 2-1. 출처

- 저장소: `https://github.com/tensorflow/tflite-micro`
- 정확한 경로: `tensorflow/lite/micro/examples/micro_speech/models/`
- Google TensorFlow 팀 공식 예제 — 최소 KWS 참조

### 2-2. 라이선스

`https://github.com/tensorflow/tflite-micro/blob/main/LICENSE`:

> Apache License Version 2.0

**결론**: 완전히 상업 안전.

### 2-3. 모델 스펙

| 항목 | 값 |
|---|---|
| 아키텍처 | Tiny Conv (2 conv + FC) |
| 크기 (INT8) | ~18 KB |
| 입력 | `[1, 1960]` int8 — 49×40 log-Mel flatten |
| 출력 | `[1, 4]` int8 |
| 클래스 (4) | `_silence_, _unknown_, yes, no` |
| 오디오 프론트엔드 | Google microspeech-frontend (40-band log-Mel, 30ms/20ms window/hop) |
| Sample rate | 16 kHz mono |

### 2-4. 채택 조건

DS-CNN 다운로드/변환 실패 시 즉시 전환. 4 클래스로도 모드 스위칭 가능 (버튼 augmentation):

- KWS `yes` = 확인 → 후보 모드 적용
- KWS `no` = 취소 → IDLE 복귀
- 버튼 short-press = 후보 모드 cycle (IDLE → SQUAT → PUSHUP → SURVEIL → IDLE)
- 버튼 long-press (>1s) = 즉시 STOP

## 3. 3순위 예비 — Silicon Labs MLTK KWS models

### 3-1. 출처

- 저장소: `https://github.com/SiliconLabs/mltk`
- 라이선스: **Apache-2.0**
- 다양한 사전학습 TFLite 모델 (`mltk/models/tinyml/keyword_spotting_*`):
  - `keyword_spotting_on_off` — 3 클래스 (on/off/_unknown_)
  - `keyword_spotting_on_off_v2` — 3 클래스 개선 버전
  - `keyword_spotting_pacman` — 게임 명령 (up/down/left/right/stop)
  - `keyword_spotting_pacman_v2` — v2 개선
  - `keyword_spotting_alexa` — 웨이크워드
  - `keyword_spotting_numbers` — 숫자 인식

### 3-2. 라이선스 확인

MLTK 프로젝트 최상위: Apache-2.0. 각 model spec 폴더에도 Apache-2.0 명시.

### 3-3. 채택 조건

특정 vocab이 본 작품 사용처에 맞을 때. 예: `keyword_spotting_pacman` (up/down/left/right/stop) → 모드 스위칭용 자연스러움.

## 4. 4순위 예비 — 자체 훈련 (Speech Commands v2 → TFLite 변환)

### 4-1. 시나리오

- 위 3개 모두 링크 rot / 변환 문제 발생 시
- 또는 한국어 명령 (예: "시작", "정지", "다음") 지원 시 → **자체 훈련 필수** (기존 KWS 모델은 영어)

### 4-2. 파이프라인 (참고)

1. Speech Commands v2 다운로드 (`https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz`, CC BY 4.0)
2. ARM ML-KWS-for-MCU 학습 스크립트 (Apache-2.0) 로 DS-CNN Small 훈련
3. TFLite 변환 + INT8 PTQ (`tf.lite.TFLiteConverter`)
4. 호스트 introspection + 디바이스 push
5. 정확도 검증 (test set > 90%)

한국어 명령 지원 시 별도 코퍼스 필요 (Common Voice Korean — CC0 / CC BY 4.0 검증 필요).

## 5. 기각 상세 — 왜 안 되는가

### 5-1. Picovoice Porcupine

- 라이선스: Non-Commercial (Personal Use) 무료 / **상업 사용 유료** (Enterprise Plan)
- 본 작품이 상업 배포 조건 명시 → **기각**
- 유료 라이선스 협상은 본 작품 범위 외

### 5-2. Snowboy / Kitt.AI

- 프로젝트 종료 (2020-12-31 EOL)
- 유지보수 없음, 새 학습 불가
- **기각**

### 5-3. openWakeWord

- 라이선스 자체는 OK (Apache-2.0)
- **ONNX 전용** — pose 라인 `ai-edge-litert` stack 과 불일치
- 추가로 `onnxruntime aarch64` 설치 필요 (venv-unoq 확장)
- **기각** — v0.3.0 사이클 우선 stack 일관성 유지, 후속 v0.4+에서 재검토 가능

## 6. 채택 매트릭스 (요약)

| 후보 | 라이선스 | 크기 | 어휘 | stack 일치 | chipset 비종속 | 순위 |
|---|---|---|---|---|---|---|
| MLPerf Tiny DS-CNN INT8 | Apache-2.0 + CC BY 4.0 | 52 KB | 12 | O | O | **1** |
| TFLM MicroSpeech | Apache-2.0 + CC BY 4.0 | 18 KB | 4 | O | O | **2** |
| Silicon Labs MLTK | Apache-2.0 + CC BY 4.0 | 다양 | 3~10 | O | O | 3 (특정 vocab 필요 시) |
| 자체 훈련 | Apache-2.0 (파이프라인) + CC BY 4.0 (데이터) | 조절 | 조절 | O | O | 4 (한국어 명령 필요 시) |
| Picovoice | Non-Commercial | 수백 KB | 확장 | X | X | 기각 |
| Snowboy | EOL | 수백 KB | 확장 | X | X | 기각 |
| openWakeWord | Apache-2.0 | ~수백 KB | 확장 | X (ONNX) | O | 기각 (stack) |

## 7. 채택 (본 사이클 결정)

**1순위 시도 → 미달 시 2순위 즉시 전환**:

```
MLPerf Tiny DS-CNN INT8  (12 클래스, 52 KB)
        │
        ├── 다운로드 성공 + 디바이스 latency ≤ 50ms → 채택
        │
        └── 실패 (URL rot / 변환 불가 / 정확도 < 80%)
                │
                ▼
        TFLM MicroSpeech (4 클래스, 18 KB)
                │
                └── (반드시 성공 — 최소 fallback)
```

전환 트리거: **DS-CNN 디바이스 invoke > 50 ms (p95)** 또는 **다운로드 5회 실패**.

## 8. 관련

- 청사진: [`00_project_blueprint.md`](00_project_blueprint.md)
- Quickstart (모델 다운로드): [`02_quickstart_kws.md`](02_quickstart_kws.md)
- Pose 라인 모델 후보 (참조 패턴): [`../../pose/docs/01_model_candidates.md`](../../pose/docs/01_model_candidates.md)
- 라이선스 원문:
  - MLPerf Tiny: `https://github.com/mlcommons/tiny/blob/master/LICENSE.md`
  - TFLM: `https://github.com/tensorflow/tflite-micro/blob/main/LICENSE`
  - Speech Commands v2: `https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz` (README에 CC BY 4.0 명시)
