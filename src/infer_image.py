#!/usr/bin/env python3
"""
이미지 한 장 추론 + 시각화 스크립트 (호스트/디바이스 공용).

흐름:
  1. 이미지 로드 (cv2 BGR)
  2. Letterbox 전처리 → 모델 입력 텐서
  3. TFLite 추론 (invoke)
  4. 후처리 (decode + NMS + scale)
  5. 박스 + 라벨 그리기 → PNG 저장

단계별 latency 측정 → end-to-end FPS 산출.
호스트(컨테이너)와 UNO Q에서 동일하게 동작.

사용:
  python src/infer_image.py <model> <image> [--output OUT] [--conf 0.25] [--iou 0.45] [--threads 4]

예 (호스트):
  python src/infer_image.py \\
    models/yolov8n_saved_model/yolov8n_int8.tflite \\
    datasets/coco128/images/train2017/000000000009.jpg

예 (UNO Q):
  python3 ~/infer_image.py \\
    /opt/unoq-yolo/models/yolov8n_int8.tflite \\
    /opt/unoq-yolo/media/test.jpg
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import cv2

# 같은 폴더의 postprocess 모듈
sys.path.insert(0, str(Path(__file__).resolve().parent))
from postprocess import (
    decode_yolov8,
    non_max_suppression,
    scale_boxes,
    draw_detections,
    COCO_NAMES,
)

# TFLite 런타임 3단 폴백 (validate_model.py와 동일 패턴)
try:
    from ai_edge_litert import interpreter as tflite
    RUNTIME = "ai_edge_litert"
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        RUNTIME = "tflite_runtime"
    except ImportError:
        import tensorflow.lite as tflite
        RUNTIME = "tensorflow.lite"


def letterbox(image_bgr, target_size, pad_value=114):
    """
    YOLOv8 표준 letterbox 전처리: 종횡비 유지하면서 target_size에 맞춰 padding.

    Args:
        image_bgr: 원본 BGR 이미지
        target_size: (W, H) 모델 입력 크기
        pad_value: 패딩 픽셀 값 (YOLOv8 표준: 114 회색)

    Returns:
        padded: target_size BGR 이미지
        scale:  원본 → 리사이즈 scale (float)
        pad:    (left, top, right, bottom) 적용된 패딩
    """
    h0, w0 = image_bgr.shape[:2]
    tw, th = target_size

    scale = min(tw / w0, th / h0)
    nw, nh = int(round(w0 * scale)), int(round(h0 * scale))

    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)

    pad_w = tw - nw
    pad_h = th - nh
    left = pad_w // 2
    right = pad_w - left
    top = pad_h // 2
    bottom = pad_h - top

    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=(pad_value, pad_value, pad_value),
    )
    return padded, scale, (left, top, right, bottom)


def prepare_input(rgb_image, input_detail):
    """모델 입력 dtype에 맞춰 텐서 준비"""
    dtype = input_detail['dtype']
    if dtype == np.float32:
        x = rgb_image.astype(np.float32) / 255.0
    elif dtype == np.uint8:
        x = rgb_image.astype(np.uint8)
    elif dtype == np.int8:
        x = (rgb_image.astype(np.int16) - 128).clip(-128, 127).astype(np.int8)
    else:
        raise TypeError(f"Unsupported input dtype: {dtype}")
    return np.expand_dims(x, axis=0)


def main():
    ap = argparse.ArgumentParser(description="YOLOv8 단일 이미지 추론 + 시각화")
    ap.add_argument("model", help=".tflite 파일 경로")
    ap.add_argument("image", help="입력 이미지 경로")
    ap.add_argument("--output", help="결과 PNG 저장 경로 (기본: <image>_annotated.<ext>)")
    ap.add_argument("--conf", type=float, default=0.25, help="confidence threshold (기본 0.25)")
    ap.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold (기본 0.45)")
    ap.add_argument("--threads", type=int, default=4, help="CPU 스레드 수 (기본 4)")
    args = ap.parse_args()

    model_path = Path(args.model)
    image_path = Path(args.image)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")
    if not image_path.exists():
        sys.exit(f"ERROR: image not found: {image_path}")

    output_path = (
        Path(args.output) if args.output
        else image_path.with_name(f"{image_path.stem}_annotated{image_path.suffix}")
    )

    print("== Inference setup ==")
    print(f"  runtime: {RUNTIME}")
    print(f"  model:   {model_path}")
    print(f"  image:   {image_path}")
    print(f"  output:  {output_path}")
    print(f"  conf:    {args.conf}, iou: {args.iou}, threads: {args.threads}")

    # 모델 로드
    interpreter = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    _, model_h, model_w, _ = (int(x) for x in input_detail['shape'])
    print(f"  input shape: ({model_w}x{model_h}, dtype={input_detail['dtype'].__name__})")

    # 이미지 로드
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        sys.exit(f"ERROR: failed to load image: {image_path}")
    h0, w0 = image_bgr.shape[:2]
    print(f"  image size: {w0}x{h0}")

    # === 단계별 latency 측정 ===

    # 1. Preprocess
    t0 = time.perf_counter()
    padded, _scale, pad = letterbox(image_bgr, (model_w, model_h))
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    input_tensor = prepare_input(rgb, input_detail)
    t_preprocess = (time.perf_counter() - t0) * 1000

    # 2. Inference
    t0 = time.perf_counter()
    interpreter.set_tensor(input_detail['index'], input_tensor)
    interpreter.invoke()
    raw_output = interpreter.get_tensor(output_detail['index'])
    t_inference = (time.perf_counter() - t0) * 1000

    # 3. Postprocess (decode + NMS + scale)
    t0 = time.perf_counter()
    boxes_in, scores, class_ids = decode_yolov8(
        raw_output, (model_w, model_h), conf_threshold=args.conf
    )
    keep = non_max_suppression(boxes_in, scores, class_ids, iou_threshold=args.iou)
    boxes_in = boxes_in[keep]
    scores = scores[keep]
    class_ids = class_ids[keep]
    boxes_orig = scale_boxes(boxes_in, (model_w, model_h), (w0, h0), letterbox_pad=pad)
    t_postprocess = (time.perf_counter() - t0) * 1000

    # 4. Draw
    t0 = time.perf_counter()
    annotated = draw_detections(image_bgr, boxes_orig, scores, class_ids)
    t_draw = (time.perf_counter() - t0) * 1000

    # 5. Save (실시간 시나리오에선 보통 매 프레임 저장 안 함 — 별도 측정)
    t0 = time.perf_counter()
    cv2.imwrite(str(output_path), annotated)
    t_save = (time.perf_counter() - t0) * 1000

    # === 결과 ===
    t_realtime = t_preprocess + t_inference + t_postprocess + t_draw  # 실시간 루프 기준 (저장 제외)
    t_total = t_realtime + t_save                                     # 한 장 저장 포함

    print(f"\n== Detections ({len(scores)} objects) ==")
    if len(scores) == 0:
        print("  (none above conf threshold)")
    else:
        for box, score, cls_id in zip(boxes_orig, scores, class_ids):
            x1, y1, x2, y2 = box.astype(int)
            print(f"  {COCO_NAMES[int(cls_id)]:20s} {score:.3f}  bbox=[{x1}, {y1}, {x2}, {y2}]")

    print(f"\n== Latency (single image, cold start) ==")
    print(f"  preprocess:   {t_preprocess:7.2f} ms")
    print(f"  inference:    {t_inference:7.2f} ms")
    print(f"  postprocess:  {t_postprocess:7.2f} ms")
    print(f"  draw:         {t_draw:7.2f} ms")
    print(f"  save (jpg):   {t_save:7.2f} ms     ← 실시간 루프에선 보통 제외")
    print(f"  ──────────────────────")
    print(f"  realtime:     {t_realtime:7.2f} ms  →  {1000/t_realtime:.2f} FPS (save 제외)")
    print(f"  total:        {t_total:7.2f} ms  →  {1000/t_total:.2f} FPS (save 포함)")
    print(f"\n  NOTE: 첫 호출은 cold start. 정확한 FPS는 validate_model.py 50회 반복 측정 참조.")

    print(f"\n== Output ==")
    print(f"  {output_path}")
    print(f"\n== 완료 ==")


if __name__ == "__main__":
    main()
