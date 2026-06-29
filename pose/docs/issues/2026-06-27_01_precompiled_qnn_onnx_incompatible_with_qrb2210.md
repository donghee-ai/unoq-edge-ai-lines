# 2026-06-27 — AI Hub precompiled QNN ONNX (w8a8, X2 Elite) UNO Q 비호환

## 증상

Qualcomm AI Hub `mediapipe_pose-precompiled_qnn_onnx-w8a8-qualcomm_snapdragon_x2_elite.zip` 다운로드 후 호스트(`unoq-pose:22.04`) onnxruntime CPUExecutionProvider 로드 시도 시 두 모델 모두 실패.

```
[ONNXRuntimeError] : 1 : FAIL :
Load model from /work/models/pose_detector.onnx failed:
Unsupported model IR version: 13, max supported IR version: 10
```

(`pose_landmark_detector.onnx`도 동일.)

## 원인

다운로드 ZIP는 **사전 컴파일된 QNN 컨텍스트 바이너리**(.bin)를 ONNX wrapper로 포장한 형식. wrapper 자체는 입출력 정량화(Dequantize/Quantize) + `EPContext` 단일 노드만 포함:

| 항목 | 값 |
|---|---|
| producer | Qualcomm AI Hub Workbench (aihub-2026.06.08.2) |
| IR version | 13 (호스트 ORT 1.22.1은 IR 10까지) |
| opset | ai.onnx 13 |
| op_types (detector) | `DequantizeLinear ×5`, `QuantizeLinear ×5`, `EPContext ×1` |
| EPContext.source | `QNN` (Microsoft QNN Execution Provider 식별자) |
| EPContext.ep_cache_context | `./pose_detector_qairt_context.bin` (외부 1.3 MB) |

→ 실제 가중치는 `qairt_context.bin`에 있고, ONNX wrapper는 ORT QNN EP에 컨텍스트 경로만 전달.

### 실행 조건 — 동시 충족 필요

1. **ONNX Runtime QNN Execution Provider** 빌드 (CPU/Azure EP만으로는 EPContext 해석 불가).
2. **Hexagon HTP NPU** 보유 SoC (X2 Elite는 HTP v8.1, soc_model 88).
3. metadata.json `chipset_attributes`에 명시: `qualcomm-snapdragon-x2-elite`, `htp_version 81`, `supports_fp16: true`.

### UNO Q (QRB2210) 환경

| 구성 | 값 | QNN EP 실행 가능? |
|---|---|---|
| SoC | Qualcomm QRB2210 | — |
| CPU | Cortex-A53 ×4 @ 2.0 GHz | (CPU EP는 가능, QNN EP는 HTP 필요) |
| NPU/HTP | **없음** | **불가능** |
| GPU | Adreno 702 (저티어, OpenCL 드라이버 이슈 보고) | (QNN GPU backend 도 무관) |

→ ORT QNN EP를 설치/빌드해도 **HTP 자체가 없어** 컨텍스트 로드 불가. CPU EP로는 IR 13 + EPContext 모두 거부됨.

호스트(x86) 도커도 동일하게 불가 — `ort.get_available_providers()` = `['AzureExecutionProvider', 'CPUExecutionProvider']`.

## 영향

| 라인 | 영향 |
|---|---|
| 본 zip 두 ONNX | UNO Q에서 사용 불가 (호스트에서도 추론 불가) |
| `mediapipe_pose-qnn_context_binary-w8a8-qualcomm_qcs6490.zip` (Downloads에 별도 존재) | 동일 사유 — QCS6490 HTP 전용, UNO Q 비호환 |
| docs/02 모델 선택 로그 | 사전 명시("AI Hub QRB2210 미지원, MediaPipe 원본 직접 획득 필요")와 일치 — 가설 정량 확인 완료 |

## 진로 후보

| 옵션 | 모델 출처 | 라이선스 | 비고 |
|---|---|---|---|
| A | AI Hub 페이지에서 "TFLite (w8a8)" 형식 재다운로드 | 모델 카드 별 | AI Hub TFLite도 chipset 의존이면 동일 함정 — 형식 페이지 검토 필요 |
| B | Google MediaPipe Solutions 직접 다운로드 (`pose_landmarker_lite.task` 등) | Apache-2.0 | docs/02 이미 명시한 권장 경로. `wget`으로 즉시 획득, ai-edge-litert로 디바이스 실행 검증 |
| C | qai-hub로 QRB2210 타겟 compile job | (QRB2210 미지원으로 추정) | docs/02 사전 조사 결과 미지원, 추가 확인 가치 낮음 |

## 다음 행동

1. AI Hub 모델 카드 페이지 (`https://aihub.qualcomm.com/iot/models/mediapipe_pose?isQuantized=true`)에서 "Runtime" / "Chipset" 옵션에 chipset-agnostic TFLite 변형이 있는지 사용자가 페이지 직접 확인 — 있으면 옵션 A 그대로 진행
2. 없거나 모두 chipset 종속이면 옵션 B로 전환 — `pose_landmarker_lite.task` 다운로드 → bundle 해제 → `pose_detection.tflite` + `pose_landmark_lite.tflite` 호스트 검증 → ADB push → 디바이스 ai-edge-litert 추론
3. 두 옵션 모두 다음 세션 사이클 (호스트 introspection → 호스트 invoke → 디바이스 push → 디바이스 invoke → 결과 비교 → history 기록)에 그대로 적용

## 관련

- 검증 스크립트: `../scripts/introspect_onnx.py`
- 다운로드 원본: `C:\Users\A\Downloads\mediapipe_pose-precompiled_qnn_onnx-w8a8-qualcomm_snapdragon_x2_elite.zip`
- 사전 결정: `../../vision/docs/02_model_selection_log.md` §3-5 ("AI Hub QRB2210 미지원, MediaPipe 원본 직접 획득 필요")
- 세션 컨텍스트: `../SESSION_SUMMARY_2026-06-27.md` §6 "ONNX 모델 다운로드 검증 + 디바이스 추론"
