# 2026-06-27 — Whisper Tiny.en 양자화 실측: w8a8 아닌 partial int8 (DRQ)

## 시점
2026-06-27 (Pose 라인 호환성 분석 중 비교 검증으로 진행)

## 사건
"ASR Whisper Tiny.en이 w8a8인가?" 가설 검증 — 실측 결과 **w8a8 아님**. Dynamic Range Quantization (weight-only int8).

## 검증

`scripts/inspect_whisper_quant.py` 작성, `unoq-asr-dev:22.04` 컨테이너에서 `ai-edge-litert.Interpreter`로 텐서 dtype 분포 출력.

| 항목 | 값 |
|---|---|
| 파일 | `models/audio/whisper_tiny_en.tflite` 39.7 MB |
| 총 텐서 | 1120 |
| float32 | 1007 (90%) |
| int8 | 76 (6.8%) |
| int32 | 35 |
| bool | 2 |
| 입력 details | `serving_default_input_ids:0` shape=[1,80,3000] **float32** (qparams 비어있음) |
| 출력 details | `StatefulPartitionedCall:0` shape=[1,448] **int32** (qparams 비어있음) |

→ 입력/출력 모두 float32/int32 (양자화 X). int8 텐서는 76개 (전체의 6.8%) — 일부 큰 weight matrix만 int8로 저장하고 추론 시 dequantize. activations 전체 + 잔여 weight는 float32 그대로.

## 양자화 형식 식별

| 형식 | 텐서 분포 예상 | 예상 크기 (Whisper Tiny.en 기준) |
|---|---|---|
| fp32 | float32 100% | ~150 MB |
| fp16 | float16 다수 | ~75 MB |
| **DRQ (weight-only int8)** | **float32 다수 + int8 일부 weight** | **~40 MB** ★ 실측 일치 |
| full int8 PTQ (w8a8) | int8/uint8 대다수, 입출력 int8 | ~10 MB |

실측 39.7 MB + dtype 분포 → **DRQ (Dynamic Range Quantization, weight-only int8)** 확정.

## 의미

UNO Q 호환성 관점에서 양자화 형식은 **무관**. TFLite 포장 + ai-edge-litert 런타임 + XNNPACK delegate면 어느 양자화든 CPU에서 실행 가능. DRQ는 fp32 → ~26% 크기 + CPU에서 fp32 dequantize 비용 일부 (vs fp32 추론 대비 latency 개선 효과는 모델/연산 종류 따라 다름).

실측 measurement는 그대로 유지:
- e2e 3.18 s (JFK 11초 wav, 6단어 중 5정확)
- CPU 212%, RSS 357 MB
- 1차 PoC 4+1 기준 통과

양자화 형식 명칭만 정정 — "w8a8" → "partial int8 (Dynamic Range, weight-only)".

## 영향 확인 필요 (다음 세션)

| 항목 | 현재 표기 | 정정 필요 여부 |
|---|---|---|
| `docs/00_project_blueprint.md` | 확인 필요 | 양자화 형식 언급되어 있으면 정정 |
| `docs/02_quickstart_asr.md` | 확인 필요 | 동일 |
| `docs/03_implementation_log.md` | 확인 필요 | 동일 |
| 보고용 한 줄 | "Whisper Tiny.en TFLite (40 MB)" | 크기만, 양자화 형식 미언급 → OK |

## 자산
- `scripts/inspect_whisper_quant.py` (텐서 dtype 분포 출력 90줄)

## 관련
- Pose 비교 분석: `../../unoq-mediapipe-pose/history/2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md`
- 모델 출처: GitHub `nyadla-sys/whisper.tflite` (커뮤니티 변환 TFLite, MIT)
