# 2026-06-27 — Pose ONNX introspection: QNN EP + HTP 의존 정량 확인

## 시점
2026-06-27 (세션 summary 작성 직후, 후속 검증 세션 1차 작업)

## 사건
다운로드된 `mediapipe_pose-precompiled_qnn_onnx-w8a8-qualcomm_snapdragon_x2_elite.zip` 풀고 호스트 도커(`unoq-pose:22.04`)에서 introspection 진행. **CPU EP로 두 ONNX 모두 로드 실패** — IR v13 미지원 + EPContext (QNN) 노드 의존성 확인.

## 진행

1. ZIP → `models/`로 flat 압축 해제 (5개 파일, 합 5.5 MB)
2. wrapper ONNX (`pose_detector.onnx` 2.2 KB, `pose_landmark_detector.onnx` 1.2 KB) `strings`로 1차 확인 → `EPContext` + `ep_cache_context: ./*_qairt_context.bin` + `source: QNN` 패턴 식별
3. `scripts/introspect_onnx.py` 작성 후 호스트 도커 안에서 실행 — onnx 1.18.0 / onnxruntime 1.22.1 / numpy 2.1.3 가용
4. CPUExecutionProvider InferenceSession 시도 → 두 모델 모두 `Unsupported model IR version: 13, max supported IR version: 10`로 거부

## 측정값

| 모델 | 크기 | IR | producer | 입력 shape | 출력 shape | op_types | EPContext 외부 .bin |
|---|---|---|---|---|---|---|---|
| pose_detector.onnx | 2263 B | 13 | Qualcomm AI Hub Workbench aihub-2026.06.08.2 | image [1,128,128,3] uint8 | box_coords_1/2 [1,512/384,12], box_scores_1/2 [1,512/384,1] | DQ×5, Q×5, EPContext×1 | pose_detector_qairt_context.bin (1.34 MB) |
| pose_landmark_detector.onnx | 1217 B | 13 | (동일) | image [1,256,256,3] uint8 | scores [1], landmarks [1,25,4] | DQ×3, Q×3, EPContext×1 | pose_landmark_detector_qairt_context.bin (4.24 MB) |

호스트 onnxruntime providers: `['AzureExecutionProvider', 'CPUExecutionProvider']` — QNN EP 없음.

## 결정

`issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md` 기록 — UNO Q (QRB2210, NPU/HTP 없음)에서 본 형식 사용 불가. AI Hub의 X2 Elite/QCS6490 chipset 종속 zip은 검증 진로 후보에서 제외.

진로 후보:
- 옵션 A — AI Hub 페이지에서 chipset-agnostic TFLite 변형 검색 + 재다운로드
- **옵션 B (권장)** — Google MediaPipe Solutions 직접 다운로드 (Apache-2.0, ai-edge-litert로 디바이스 직접 실행)

본 결정은 docs/02_model_selection_log.md §3-5의 사전 조사("AI Hub QRB2210 미지원, MediaPipe 원본 직접 획득 필요")를 정량으로 확인.

## 자산
- `scripts/introspect_onnx.py` (90줄, 호스트 unoq-pose:22.04 컨테이너에서 실행)
- `models/` 압축 해제 5개 파일 (호환 불가, 향후 정리 대상)

## 다음 단계
1. 사용자가 AI Hub 페이지에서 TFLite 형식 chipset 옵션 확인 (옵션 A 가능 여부)
2. 옵션 A 불가 시 옵션 B로 전환 — `wget`으로 `pose_landmarker_lite.task` 직접 다운로드 → bundle 해제 → 호스트 검증 → ADB push → 디바이스 추론
3. 검증 사이클 결과 history에 기록 (`2026-06-27_02_<topic>.md`)

## 관련
- 이슈: `../issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md`
- 세션 컨텍스트: `../SESSION_SUMMARY_2026-06-27.md`
- 사전 결정: `../../vision/docs/02_model_selection_log.md`
