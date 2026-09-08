# Pose 모델 후보 — 1/2/3순위 결정 (2026-06-27)

본 문서는 UNO Q (QRB2210, Cortex-A53 ×4 CPU only, HTP NPU 없음) 위에서 양자화된 pose 모델 선정 결과. AI Hub precompiled QNN ONNX (X2 Elite 종속) 비호환 확정 후 ([issues/2026-06-27_01_*.md](issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md)) 대체 후보 검색 결과.

## 0. 결정

| 순위 | 모델 | 진행 단계 |
|---|---|---|
| **1차 시도** | **MoveNet Thunder INT8** (Google) | 본 세션 진행 |
| **속도 미달 시** | MoveNet Lightning INT8 (Google) | Thunder 미달 시 즉시 전환 |
| **백업** | OpenCV Zoo MediaPipe Pose int8 BQ (ONNX) | TFLite 두 옵션 모두 미달 시 |

전환 트리거: **Thunder 디바이스 e2e < 8 FPS** (vision/ASR 1차 PoC 합격선과 동일).

## 1. 후보 비교

| 항목 | 1순위 시도 | 2순위 폴백 | 3순위 백업 |
|---|---|---|---|
| 이름 | **MoveNet Thunder INT8** | MoveNet Lightning INT8 | MediaPipe Pose int8 BQ |
| 출처 | TensorFlow Hub (Google) | TensorFlow Hub (Google) | OpenCV Zoo (Hugging Face) |
| 형식 | **TFLite** | TFLite | **ONNX** (표준, 가중치 내장) |
| 양자화 | int8 (full PTQ) | int8 (full PTQ) | int8 block-quantized (block_size=64) |
| 입력 | 256×256 | 192×192 | 256×256 (추정, 확인 필요) |
| keypoints | 17 (COCO 17점) | 17 (COCO 17점) | **33 (BlazePose)** |
| 디바이스 런타임 | ai-edge-litert + XNNPACK | ai-edge-litert + XNNPACK | onnxruntime aarch64 + CPU EP |
| 라이선스 | Apache-2.0 + CC BY 4.0 | Apache-2.0 + CC BY 4.0 | Apache-2.0 |
| 직접 wget | O | O | O |
| chipset 종속 | X | X | X |
| stack 일치 | **vision/ASR과 동일** | vision/ASR과 동일 | 추가 검증 (onnxruntime aarch64) |
| 모델 단계 | 단일 (1 invoke) | 단일 (1 invoke) | 2-stage (detector + landmark) |

### 다운로드 URL

```bash
# 1순위 (본 세션)
wget -O models/movenet_thunder_int8.tflite \
  "https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4?lite-format=tflite"

# 2순위 폴백
wget -O models/movenet_lightning_int8.tflite \
  "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/int8/4?lite-format=tflite"

# 3순위 백업
wget -O models/pose_estimation_mediapipe_2023mar_int8bq.onnx \
  "https://huggingface.co/opencv/pose_estimation_mediapipe/resolve/main/pose_estimation_mediapipe_2023mar_int8bq.onnx"
```

## 2. 1순위 채택 근거 (Thunder)

| 근거 | 내용 |
|---|---|
| 정확도 우선 | Lightning(192) 대비 Thunder(256)가 keypoint 정밀도 우위 — 각도 측정 정밀도 직결 |
| stack 일치 | ai-edge-litert 디바이스 이미 설치, 추가 wheel/패키지 없음 |
| 검증 사이클 단순 | 단일 모델 1 invoke (vs MediaPipe 2-stage) |
| 라이선스 깨끗 | Apache-2.0 / CC BY 4.0 — 상업 호환 |
| 속도 폴백 명확 | 미달 시 Lightning으로 1줄 wget 교체 |

## 3. 17 keypoint 검증 — 각도 측정 가능 여부

MoveNet 출력 17 keypoint (COCO 표준):

```
0  nose            5  left_shoulder    11 left_hip
1  left_eye        6  right_shoulder   12 right_hip
2  right_eye       7  left_elbow       13 left_knee
3  left_ear        8  right_elbow      14 right_knee
4  right_ear       9  left_wrist       15 left_ankle
                  10  right_wrist      16 right_ankle
```

### 측정 가능 각도

| 각도 | 3점 구성 | 가능? | 의미 |
|---|---|---|---|
| **무릎 굽힘** | hip → knee → ankle | ✓ | 서있음/앉음/한 다리 들기 판별 |
| **엉덩이 굽힘** | shoulder → hip → knee | ✓ | 상체 굽힘/숙임 판별 |
| 발목 굽힘 (dorsi/plantar flexion) | knee → ankle → toe | △ | toe(발끝) 없음 — knee→ankle 벡터 방향만 (수직 대비 기울기) |
| 팔꿈치 굽힘 | shoulder → elbow → wrist | ✓ | 손 흔들기/팔 들기 판별 |
| 어깨 굽힘/외전 | hip → shoulder → elbow | ✓ | 만세/팔 옆으로 펴기 판별 |
| 몸통 기울기 | midhip → midshoulder (또는 nose) | ✓ | 좌우 기울기 |

### 발목 각도 — 정확 측정 불가, 대안

- 17 keypoint에 **toe(발끝) 미포함** → 진짜 발목 굽힘 각도(knee-ankle-toe)는 측정 불가
- 대안 1: knee→ankle 벡터의 **수직 대비 각도** 만 측정 (다리 기울기와 합쳐짐, 발목 단독 분리 X)
- 대안 2: 발목 각도가 필수면 MediaPipe BlazePose 33 keypoint (3순위 백업) 또는 별도 FootPose 모델 추가
- 본 작품 교감로봇 인터랙션 범위에서 발목 각도 단독 측정 필요성 낮음 — 무릎/엉덩이 각도로 자세 인식 충분

### 각도 계산 공식 (3점 a, b, c — 중심 b)

```python
import numpy as np

def angle_at(a, b, c):
    """3점 a-b-c 사이에서 b를 꼭짓점으로 한 각도 (degree).

    a, b, c: shape (2,) — (y, x) 또는 (x, y) 일관성만 유지
    반환: 0~180 도
    """
    ba = a - b
    bc = c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

# 예시
left_knee_angle = angle_at(kp[11], kp[13], kp[15])   # hip-knee-ankle
right_hip_angle = angle_at(kp[6], kp[12], kp[14])    # shoulder-hip-knee
```

### confidence 임계

각 keypoint마다 `confidence_score` 제공 — 임계 (e.g. 0.3) 미만이면 해당 keypoint 추정 신뢰 X. 각도 계산 전 3점 모두 임계 통과 확인 필요.

## 4. 검증 사이클 (본 세션)

| # | 작업 | 누가 |
|---|---|---|
| 1 | Thunder int8 다운로드 | Claude |
| 2 | 호스트 introspection (TFLite Interpreter, 텐서 dtype/qparams) | Claude |
| 3 | 호스트 dummy invoke (random uint8 입력) + latency p50/p95 | Claude |
| 4 | (호스트 통과 시) ADB push + 디바이스 invoke + latency | Claude |
| 5 | 합격 평가 (e2e ≥ 8 FPS, RSS, CPU%) | Claude |
| 6 | 미달 시 Lightning으로 폴백 + 동일 사이클 재실행 | Claude |
| 7 | 합격 시 각도 계산 데모 + 시각화 (옵션) | Claude / 사용자 결정 |
| 8 | history 기록 + 보고용 한 줄 갱신 | Claude |

## 5. 관련

- AI Hub QNN 비호환 결론: [issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md](issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md)
- 호환성 결정 요인 분석: [history/2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md](history/2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md)
- 사전 결정 (모델 선택 로그): [../../vision/docs/02_model_selection_log.md](../../vision/docs/02_model_selection_log.md)
- 세션 컨텍스트: [../SESSION_SUMMARY_2026-06-27.md](../SESSION_SUMMARY_2026-06-27.md)
