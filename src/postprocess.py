#!/usr/bin/env python3
"""
YOLOv8 출력 후처리 모듈.

YOLOv8 TFLite 출력 shape: (1, 84, 2100)
  - 1: batch
  - 84: 4 (bbox xywh) + 80 (COCO class scores, post-sigmoid)
  - 2100: anchor 개수 (40x40 + 20x20 + 10x10 = 2100 at 320 입력)

본 프로젝트 규약 (docs/03_project_conventions.md Section 5-2)에 따라:
  - hard-code된 q-offset/scale 없음 (입출력 float32라 양자화 변환 불필요)
  - 단일 책임: 디코딩 + NMS + 시각화. 추론은 별도 모듈
"""

import numpy as np
import cv2


# COCO 80 클래스 이름 (YOLOv8 표준 순서)
COCO_NAMES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
    'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
    'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
    'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard',
    'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase',
    'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]


def decode_yolov8(raw_output, input_size, conf_threshold=0.25):
    """
    YOLOv8 raw output을 (boxes_xyxy, scores, class_ids)로 변환.

    중요: Ultralytics int8 TFLite export의 출력은 **정규화 좌표 [0, 1]** 입니다.
    (PyTorch/ONNX export는 픽셀 좌표지만 TFLite는 다름.)
    따라서 input_size로 픽셀 좌표로 변환합니다.

    Args:
        raw_output: shape (1, 84, 2100) numpy array — 모델 출력 그대로
        input_size: (W, H) 모델 입력 크기. 정규화 → 픽셀 좌표 변환에 사용
        conf_threshold: confidence 임계값 (이하 박스 버림)

    Returns:
        boxes_xyxy: (N, 4) 각 박스 [x1, y1, x2, y2] in 모델 입력 픽셀 좌표 (0~input_size)
        scores:     (N,) confidence
        class_ids:  (N,) class index
    """
    # (1, 84, 2100) → (2100, 84) — 각 anchor가 row가 되도록
    pred = raw_output[0].T  # (2100, 84)

    boxes_xywh = pred[:, :4].copy().astype(np.float32)  # 정규화 [0, 1]
    class_scores = pred[:, 4:]                          # (2100, 80)

    # 정규화 [0, 1] → 입력 픽셀 좌표 [0, input_size]
    boxes_xywh[:, [0, 2]] *= input_size[0]  # center_x, w
    boxes_xywh[:, [1, 3]] *= input_size[1]  # center_y, h

    # anchor별 max class score + class id
    class_ids = np.argmax(class_scores, axis=1)
    scores = class_scores[np.arange(len(class_scores)), class_ids]

    # confidence 필터
    mask = scores >= conf_threshold
    boxes_xywh = boxes_xywh[mask]
    scores = scores[mask]
    class_ids = class_ids[mask]

    # xywh → xyxy
    boxes_xyxy = xywh_to_xyxy(boxes_xywh)

    return boxes_xyxy, scores, class_ids


def xywh_to_xyxy(boxes_xywh):
    """center-x, center-y, w, h → x1, y1, x2, y2"""
    out = np.zeros_like(boxes_xywh)
    out[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2  # x1
    out[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2  # y1
    out[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2  # x2
    out[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2  # y2
    return out


def non_max_suppression(boxes_xyxy, scores, class_ids, iou_threshold=0.45):
    """
    Class-agnostic NMS (cv2.dnn.NMSBoxes 사용).

    Args:
        boxes_xyxy: (N, 4)
        scores:     (N,)
        class_ids:  (N,) — 현재 사용 안 함 (class-agnostic). 향후 class-aware 확장 시 사용.
        iou_threshold: IoU 임계값

    Returns:
        keep_indices: 유지할 박스 인덱스 (numpy array)
    """
    if len(boxes_xyxy) == 0:
        return np.array([], dtype=int)

    # cv2.dnn.NMSBoxes는 [x, y, w, h] 형식 요구
    bxywh = np.zeros_like(boxes_xyxy, dtype=np.float32)
    bxywh[:, 0] = boxes_xyxy[:, 0]                            # x
    bxywh[:, 1] = boxes_xyxy[:, 1]                            # y
    bxywh[:, 2] = boxes_xyxy[:, 2] - boxes_xyxy[:, 0]         # w
    bxywh[:, 3] = boxes_xyxy[:, 3] - boxes_xyxy[:, 1]         # h

    indices = cv2.dnn.NMSBoxes(
        bxywh.tolist(),
        scores.astype(float).tolist(),
        score_threshold=0.0,   # 이미 conf 필터링 완료
        nms_threshold=float(iou_threshold),
    )

    if len(indices) == 0:
        return np.array([], dtype=int)

    # cv2 버전에 따라 shape이 다를 수 있어 평탄화
    return np.array(indices).flatten()


def scale_boxes(boxes_xyxy, model_input_size, original_size, letterbox_pad=None):
    """
    모델 입력 좌표 → 원본 이미지 좌표.

    Args:
        boxes_xyxy: (N, 4) 모델 입력 좌표
        model_input_size: (W, H) 모델 입력 크기
        original_size:    (W, H) 원본 이미지 크기
        letterbox_pad: (left, top, right, bottom) letterbox 패딩
                      None이면 단순 stretch scale

    Returns:
        scaled_boxes_xyxy: (N, 4) 원본 이미지 좌표 (clip 적용)
    """
    scaled = boxes_xyxy.astype(np.float32).copy()

    if letterbox_pad is None:
        # 단순 stretch
        sx = original_size[0] / model_input_size[0]
        sy = original_size[1] / model_input_size[1]
        scaled[:, [0, 2]] *= sx
        scaled[:, [1, 3]] *= sy
    else:
        left, top, right, bottom = letterbox_pad
        # 패딩 제거
        scaled[:, [0, 2]] -= left
        scaled[:, [1, 3]] -= top
        # letterbox는 등배 → x/y 같은 scale
        eff_w = model_input_size[0] - left - right
        eff_h = model_input_size[1] - top - bottom
        scale = max(original_size[0] / eff_w, original_size[1] / eff_h)
        scaled *= scale

    # 원본 경계 내로 clip
    scaled[:, [0, 2]] = np.clip(scaled[:, [0, 2]], 0, original_size[0])
    scaled[:, [1, 3]] = np.clip(scaled[:, [1, 3]], 0, original_size[1])

    return scaled


def draw_detections(image_bgr, boxes_xyxy, scores, class_ids, class_names=None,
                    font_scale=0.5, thickness=2):
    """
    원본 이미지에 박스 + 라벨 그리기. BGR 입력/출력.

    Args:
        image_bgr:  cv2 BGR 이미지 (원본 크기)
        boxes_xyxy: (N, 4) 원본 좌표
        scores:     (N,)
        class_ids:  (N,)
        class_names: list[str], None이면 COCO 80

    Returns:
        annotated: 박스/라벨이 그려진 BGR 이미지 (복사본)
    """
    if class_names is None:
        class_names = COCO_NAMES

    annotated = image_bgr.copy()
    colors = _class_colors(len(class_names))

    for box, score, cls_id in zip(boxes_xyxy, scores, class_ids):
        x1, y1, x2, y2 = box.astype(int)
        cls_id = int(cls_id)
        color = colors[cls_id % len(colors)]

        # 박스
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

        # 라벨
        label = f"{class_names[cls_id]} {score:.2f}"
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        y_text = max(y1 - baseline - 4, th + 4)
        cv2.rectangle(annotated, (x1, y_text - th - baseline),
                      (x1 + tw + 4, y_text), color, -1)
        cv2.putText(annotated, label, (x1 + 2, y_text - baseline - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

    return annotated


def _class_colors(n):
    """클래스별 색상 (재현 가능한 random, BGR)"""
    rng = np.random.RandomState(42)
    arr = rng.randint(64, 255, size=(n, 3), dtype=np.uint8)
    return [tuple(int(v) for v in row) for row in arr]
