# 모델 선택 — 무엇을 왜 골랐나

라인별로 흩어져 있던 후보 검토를 한 곳에 모았습니다. 측정값은
[`02_measurements.md`](02_measurements.md), 실행은 [`01_device_setup.md`](01_device_setup.md).

## 0. 네 라인에 공통으로 적용한 필터

순서대로 걸렀고, 하나라도 걸리면 후보에서 뺐습니다.

| # | 필터 | 이유 |
|---|---|---|
| 1 | **상업 사용 가능 라이선스만** — Apache-2.0 / MIT / BSD-3 / CC BY 4.0 | Non-Commercial · GPL · 커스텀 EULA는 전면 기각 |
| 2 | **TFLite + `ai-edge-litert`** 스택 | 4 라인이 같은 런타임을 쓰면 컨테이너·디버깅이 하나로 끝난다 |
| 3 | **chipset 비종속** | §4 참고 — 특정 칩용으로 미리 컴파일된 모델은 QRB2210에서 안 돈다 |
| 4 | **가중치가 파일에 들어 있고 `wget`으로 바로 받아지는 것** | 계정·SDK·재훈련이 필요하면 재현이 끊긴다 |

## 1. Vision — YOLOv8n int8

| 항목 | 값 |
|---|---|
| 채택 | YOLOv8n int8 (Ultralytics 표준 export 경로) |
| 전환 트리거 | 실측 FPS가 8~10 미만이면 MediaPipe Face로 교체 |
| 결과 | **9.23 FPS로 트리거 미발동 — 교체 안 함** |

## 2. Pose — MoveNet Thunder INT8

| 항목 | 1순위 (채택) | 2순위 폴백 | 3순위 백업 |
|---|---|---|---|
| 이름 | **MoveNet Thunder INT8** | MoveNet Lightning INT8 | MediaPipe Pose int8 BQ |
| 출처 | TensorFlow Hub (Google) | 동일 | OpenCV Zoo |
| 형식 | **TFLite** | TFLite | **ONNX** |
| 입력 | 256×256 | 192×192 | 256×256 |
| keypoints | 17 (COCO) | 17 (COCO) | 33 (BlazePose) |
| 런타임 | ai-edge-litert + XNNPACK | 동일 | onnxruntime aarch64 |
| 라이선스 | Apache-2.0 + CC BY 4.0 | 동일 | Apache-2.0 |
| 단계 | 단일 (1 invoke) | 단일 | **2-stage** (detector + landmark) |

정확도 우선으로 Thunder를 먼저 시도했다 — Lightning(192)보다 keypoint 정밀도가 높고,
그게 관절 각도 측정 정밀도로 직결되기 때문이다. **9.69 FPS로 합격해 폴백을 쓸 일이
없었다.**

## 3. KWS — 라이선스 필터가 후보를 반으로 줄였다

이 리포에서 가장 재사용 가치가 높은 표다. "상업적으로 못 쓰는 것"이 생각보다 많다.

| 후보 | 코드 | 데이터 | 상업 | 판정 |
|---|---|---|---|---|
| **MLPerf Tiny DS-CNN INT8** | Apache-2.0 | CC BY 4.0 | ✓ | **1순위 채택** |
| Google TFLM MicroSpeech | Apache-2.0 | CC BY 4.0 | ✓ | 2순위 fallback |
| ARM ML-KWS-for-MCU | Apache-2.0 | CC BY 4.0 | ✓ | 3순위 — **사전학습 가중치가 TFLite로 배포 안 됨**(재훈련 필요) |
| Silicon Labs MLTK | Apache-2.0 | CC BY 4.0 | ✓ | 예비 |
| openWakeWord | Apache-2.0 | CC0/MIT | ✓ | 기각 — **ONNX 전용**, 스택 불일치 |
| **Picovoice Porcupine** | Non-Commercial 무료 | proprietary | **✗** | **기각** — 상업 시 유료 |
| **Snowboy** | — | — | **✗** | **기각** — 2020 서비스 종료 |
| Vosk KWS | Apache-2.0 | Apache-2.0 | ✓ | 오버킬 (STT 전체, 우리는 4~12 단어) |
| Qualcomm AI Hub KWS | **Qualcomm EULA** | proprietary | △ | 기각 — §4 |

채택 모델 스펙 (**전부 프로젝트 발표치. 우리 실측 아님**):
크기 ~52 KB · 입력 `[1,49,10,1]` int8 · 출력 12 클래스 · MFCC 10계수 / 25 ms 윈도우 /
10 ms 홉 / 16 kHz · 정확도 ~90.5 % — 출처
[MLPerf Tiny 리더보드](https://mlcommons.org/benchmarks/inference-tiny/).

필요 표기: *"Trained on Google Speech Commands v2 (CC BY 4.0). Model architecture:
MLPerf Tiny KWS reference (Apache-2.0)."*

## 4. Qualcomm AI Hub 모델은 QRB2210에서 못 쓴다 — 실증

TFLite로 간 가장 큰 이유다. 추측이 아니라 직접 받아서 열어보고 확인했다.

`mediapipe_pose-precompiled_qnn_onnx-w8a8-qualcomm_snapdragon_x2_elite.zip`을 받아
onnxruntime으로 로드하면:

```
[ONNXRuntimeError] : 1 : FAIL : Load model from pose_detector.onnx failed:
Unsupported model IR version: 13, max supported IR version: 10
```

파일을 열어보면 원인이 나온다:

| 항목 | 값 |
|---|---|
| producer | Qualcomm AI Hub Workbench (aihub-2026.06.08.2) |
| IR version | **13** (onnxruntime 1.22.1은 10까지) |
| op_types | `DequantizeLinear ×5`, `QuantizeLinear ×5`, **`EPContext ×1`** |
| EPContext.source | **`QNN`** |

**이건 ONNX 모델이 아니다.** 사전 컴파일된 **QNN 컨텍스트 바이너리**를 ONNX 껍데기로
싼 것이고, `EPContext` 노드가 그 증거다. 실제 연산은 QNN Execution Provider가 해야 하며
**컴파일 대상 칩(Snapdragon X2 Elite)에서만 돈다.** IR 버전을 맞춰도 QRB2210에서는
의미가 없다.

> **교훈** — "ONNX 파일"이라고 다 이식 가능한 게 아니다. 받기 전에 대상 칩과
> `EPContext` 유무를 확인할 것. 상세: [`04_traps.md`](04_traps.md) §1.

## 5. ASR — 모델 카드를 믿지 말 것

Whisper Tiny.en TFLite를 "int8"로 알고 받았는데, 텐서를 직접 열어보니 int8 텐서가
전체의 6.8 %뿐인 **weight-only int8 (DRQ)**였다. 입출력은 float32/int32다.

측정과 판별 과정: [`02_measurements.md`](02_measurements.md) §3-1.

## 6. 원본 문서

통합 전 라인별 검토 문서는 각 라인의 `docs/history/superseded/`에 그대로 있다.

| 라인 | 원본 |
|---|---|
| Vision | `vision/docs/history/superseded/02_model_selection_log.md` |
| Pose | `pose/docs/history/superseded/01_model_candidates.md` |
| KWS | `kws/docs/history/superseded/01_model_candidates.md` (라이선스 근거 원문 + 다운로드 절차) |
