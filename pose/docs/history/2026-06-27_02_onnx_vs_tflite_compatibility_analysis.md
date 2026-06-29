# 2026-06-27 — UNO Q 호환성 결정 요인 분석: 양자화 비트 ≠ 호환성, 포장 형식 = 호환성

## 시점
2026-06-27 (`2026-06-27_01_onnx_introspection_qnn_dependency_confirmed.md` 직후 후속 분석)

## 사건
"ASR이 됐는데 Pose는 안 됨" 비교 + "ASR w8a8 맞나?" + "ONNX는 아예 안 되나?" 질문 검증. 두 가설 모두 기각.

## 검증 1 — ASR Whisper Tiny.en 양자화 실측

`asr/scripts/inspect_whisper_quant.py` 실행 (asr-dev 컨테이너):

| 항목 | 값 |
|---|---|
| 파일 | `whisper_tiny_en.tflite` 39.7 MB |
| 총 텐서 | 1120 |
| float32 | 1007 (90%) |
| int8 | 76 (6.8%) |
| int32 | 35, bool | 2 |
| 입력 dtype | float32 (mel 1×80×3000) |
| 출력 dtype | int32 (token IDs) |

→ **w8a8 아님**. Dynamic Range Quantization (weight-only int8) — 일부 큰 weight만 int8 저장, activations + 잔여 weight는 float32. 진짜 w8a8(full int8 PTQ)였다면 ~10 MB + 입출력 int8/uint8이어야 함.

## 검증 2 — ONNX 자체가 안 되는 게 아니다

ONNX는 두 가지 변형:

| 종류 | 구조 | UNO Q |
|---|---|---|
| 표준 ONNX | 가중치 .onnx 안에 포함, 표준 op (Conv/MatMul/Add ...) | ✓ onnxruntime + CPU EP |
| precompiled QNN ONNX (우리 다운로드) | wrapper(KB) + 외부 qairt_context.bin(MB), `EPContext` 1 노드 | ✗ QNN EP + HTP 필수 |

`EPContext`는 `com.microsoft` 도메인 확장 op — 표준 ONNX op 아님. "외부 EP가 외부 context 파일 로드해서 처리해라" placeholder. CPU EP는 처리 불가, QNN EP만 처리하고 QNN EP는 HTP 하드웨어에 컨텍스트 업로드 후 실행.

차단 두 단계:
1. IR v13 > 호스트 ORT 1.22 max IR v10 → 파싱 실패 (ORT 최신화로 해결 가능)
2. IR 통과해도 EPContext (source=QNN) → CPU EP 모름, QNN EP 필요, QNN EP는 HTP 필요 → QRB2210 불가

QAIRT SDK 깔아도 같은 결과 — `.bin`이 X2 Elite HTP v8.1 타겟 사전 컴파일이라 다른 backend(QnnCpu/QnnGpu)나 다른 HTP 버전에서 못 읽음. 원본에서 재컴파일하면 가능하지만 그러면 사전 컴파일 zip 쓰는 의미 없음.

## 호환성 결정 요인 재정리

| 모델 | 양자화 | 포장 형식 | 디바이스 런타임 | UNO Q |
|---|---|---|---|---|
| YOLOv8n (vision) | full int8 (w8a8) | TFLite | ai-edge-litert + XNNPACK | ✓ 9.23 FPS |
| Whisper Tiny.en (ASR) | partial int8 (DRQ) | TFLite | ai-edge-litert + XNNPACK | ✓ 3.18 s |
| MediaPipe Pose (AI Hub) | full int8 (w8a8) | precompiled QNN ONNX | QNN EP + HTP | ✗ |

**핵심**: 양자화 비트 폭(w8a8/DRQ/fp16)은 호환성을 결정하지 않음. 같은 w8a8이라도 TFLite로 포장하면 UNO Q에서 동작, QNN context binary로 사전 컴파일하면 동작 불가. 결정 요인은 **포장/런타임 백엔드 종속성**.

## UNO Q에서 가능한 형식 매트릭스

| 형식 | 런타임 | 디바이스 상태 |
|---|---|---|
| TFLite (양자화 무관) | `ai-edge-litert` + XNNPACK | ✓ 검증 완료 (vision/ASR) |
| 표준 ONNX (가중치 내장) | `onnxruntime` aarch64 + CPU EP | △ 미검증 (Python 3.13 wheel 가용성 변수) |
| precompiled QNN ONNX | QNN EP + HTP | ✗ HTP 없음 |
| QNN context binary 단독 | QAIRT + HTP | ✗ HTP 없음 |
| TF SavedModel | tensorflow | ✗ 디바이스 미설치 (무거움) |

## 진로 결정 영향

`issues/2026-06-27_01_*.md` 진로 후보 재평가:

- 옵션 A (AI Hub 다른 형식) — chipset-agnostic TFLite 변형 있으면 1순위, 표준 ONNX 변형은 onnxruntime aarch64 검증 비용 추가
- 옵션 B (MediaPipe 원본 TFLite) — vision/ASR 동일 스택 → 검증 비용 최소

stack 통일성 관점에서 **TFLite 우선**, 표준 ONNX는 backup.

## 자산
- `asr/scripts/inspect_whisper_quant.py` (Whisper 양자화 dtype 분포 출력)
- `asr/docs/history/2026-06-27_01_*.md` (양자화 실측 ASR 라인 기록)

## 관련
- 직전 작업: `2026-06-27_01_onnx_introspection_qnn_dependency_confirmed.md`
- 이슈: `../issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md`
- 사전 결정: `../../vision/docs/02_model_selection_log.md` §3-5
