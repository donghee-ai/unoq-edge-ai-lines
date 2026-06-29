# 2026-06-27 — MoveNet Thunder INT8 디바이스 1차 PoC 합격 (12.5 FPS)

## 시점
2026-06-27 (AI Hub QNN ONNX 비호환 결론 직후 같은 세션)

## 사건
Google MoveNet Thunder INT8 TFLite 다운로드 → 호스트 introspection → ADB push → UNO Q 디바이스 latency 측정. **1차 PoC 합격선(≥8 FPS) 통과 — 12.5 FPS 안정**. Lightning 폴백 불필요.

## 진행

1. 후보 비교 + 결정 문서화 → [`docs/01_model_candidates.md`](../docs/01_model_candidates.md) 1순위 Thunder / 2순위 Lightning / 3순위 OpenCV Zoo BlazePose ONNX
2. `curl`로 TensorFlow Hub에서 직접 다운로드 (chipset 비종속)
   ```
   https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4?lite-format=tflite
   ```
3. `scripts/inspect_movenet_thunder.py` — 텐서 분포 + qparams + dummy invoke latency
4. 호스트 컨테이너(`unoq-pose:22.04`)에서 실행 — full int8 PTQ 확인 + latency baseline
5. ADB(Arduino IDE 번들)로 모델 + 스크립트 push (Git Bash 경로 변환 함정 → PowerShell로 진행)
6. 디바이스 venv-unoq에서 동일 스크립트 실행 — **12.5 FPS** 합격

## 측정값

### 모델

| 항목 | 값 |
|---|---|
| 파일 | `movenet_thunder_int8.tflite` 6.80 MB (7,126,768 B) |
| 입력 | `[1, 256, 256, 3]` **uint8** (image normalized 0-255) |
| 출력 | `[1, 1, 17, 3]` **float32** (1 person × 17 keypoint × y/x/conf) |
| 텐서 (333) | int8 215 (64%), int32 106 (32%), float32 11 (3.3%), uint8 1 |
| 양자화 분포 | quantized 289 / float 11 / other 33 → **full int8 PTQ** |

vision YOLOv8n int8과 동일하게 ai-edge-litert + XNNPACK delegate로 동작 (디바이스 로그 `INFO: Created TensorFlow Lite XNNPACK delegate for CPU`).

### Latency — invoke only (warmup 5 + runs 100, threads=4)

| 환경 | mean | p50 | p95 | min/max | FPS p50 |
|---|---|---|---|---|---|
| 호스트 (x86, unoq-pose:22.04) | 14.71 ms | 14.03 ms | 17.35 ms | 12.09 / 34.37 | 71.3 |
| **UNO Q (QRB2210 Cortex-A53 ×4)** | **80.33 ms** | **80.29 ms** | **80.85 ms** | **79.87 / 81.52** | **12.5** |

호스트 → 디바이스 5.7× 느려짐 — vision YOLOv8n(320 입력) 7.9×보다 양호 (256 입력 + 더 작은 모델 효과).

분산 1.65 ms (p95-min) → **매우 안정**. thermal margin 충분.

### 출력 sanity

```
shape  : [1, 1, 17, 3]
dtype  : float32
range  : 0.0161 ~ 0.9795 (호스트) / 0.0161 ~ 0.8349 (디바이스)
```

17 keypoint × (y, x, confidence) — COCO 17점 (각도 계산 가능, `docs/01_model_candidates.md §3`).

## 1차 PoC 합격 평가 (vision/ASR과 동일 기준)

| 기준 | 합격선 | 측정 | 평가 |
|---|---|---|---|
| 디바이스 FPS | ≥ 8 | 12.5 | ✓ (56% 여유) |
| 디바이스 invoke latency | ≤ 200 ms | 80.3 ms | ✓ |
| 모델 크기 | ≤ 50 MB | 6.80 MB | ✓ |
| 양자화 형식 | 디바이스 가능 | full int8 PTQ + XNNPACK | ✓ |

→ **MoveNet Thunder INT8 1차 PoC 합격**. Lightning 폴백 미시행 (불필요).

## 통과 의의

- AI Hub precompiled QNN ONNX(X2 Elite 종속) 비호환 결론 [`issues/2026-06-27_01_*.md`](../issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md) 직후 **대안 형식 1발 합격**
- **AI Hub 우회 + TFLite + chipset 비종속** 전략 일관 (ASR Whisper와 동일 패턴)
- vision/ASR/Pose **세 라인 모두 1차 PoC 통과** — 멘토 보고용 한 줄 갱신 가능

## 미확인 (다음 세션 후보)

| 항목 | 비고 |
|---|---|
| **e2e 측정** (카메라 + 전처리 + invoke + 후처리) | 본 측정은 invoke only — 카메라 합산은 +캡처 1.4 ms + 전처리 (resize 320→256, uint8) + 후처리 (keypoint 좌표 정규화 해제 + 각도 계산) |
| **CPU%/RSS** (`time -v` 또는 top) | 본 측정 미수집 — vision YOLO 286% / 102 MB 와 동일 수준 예상 |
| **thermal soak** (10분+) | 안정성 확인 (단일 측정만으로는 thermal plateau 미검증) |
| **각도 계산 데모** | hip-knee-ankle, shoulder-hip-knee, shoulder-elbow-wrist — 코드 `docs/01_model_candidates.md §3` 공식 그대로 |
| **카메라 라이브 시연** | infer_camera.py 패턴 적용 (vision 기존 코드 참조) |
| **vision + Pose 동시 운영** | 자원 청사진 측정 (vision 286% + Pose 추가) |

## 자산
- `models/movenet_thunder_int8.tflite` (6.80 MB)
- `scripts/inspect_movenet_thunder.py` (텐서 분포 + latency, `MODEL_PATH`/`N_RUNS`/`N_WARMUP` env 지원)
- `docs/01_model_candidates.md` (1/2/3순위 후보 + 각도 측정 가능 분석)

## 관련
- 이전 단계 (불호환 결론): `2026-06-27_01_onnx_introspection_qnn_dependency_confirmed.md`
- 호환성 결정 요인 분석: `2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md`
- 후보 결정: [`../docs/01_model_candidates.md`](../docs/01_model_candidates.md)
- 모델 출처: https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4
