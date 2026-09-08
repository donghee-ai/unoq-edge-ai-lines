#!/usr/bin/env python3
"""
End-to-End 벤치마크 스크립트 (벤치마크 표준 권고 형식 + RSS/온도 모니터링).

단일 이미지를 N회 반복 추론하여 참고자료 `06_testing_benchmarking_reliability.md`
Section 3의 JSON 형식으로 결과 저장.

수집 항목:
- latency_ms_p50, p95, mean, median, min, max (각 단계 + total)
- fps_mean
- preprocess_ms_mean, postprocess_ms_mean (리뷰어 요구)
- inference_ms_mean, draw_ms_mean (추가 상세)
- max_rss_mb (피크 메모리, /proc/self/status VmRSS)
- max_temp_c (피크 온도, /sys/class/thermal/*)
- frames, warmup, runtime, threads, input_shape

사용:
  python3 src/benchmark_e2e.py <model> <image> [--runs 100] [--warmup 10] [--json out.json]

예 (디바이스):
  python3 ~/benchmark_e2e.py /opt/unoq-yolo/models/yolov8n_int8.tflite \\
    /opt/unoq-yolo/media/000000000009.jpg \\
    --runs 100 --json ~/benchmarks/device_e2e_$(date +%Y%m%d).json
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from postprocess import decode_yolov8, non_max_suppression, scale_boxes, draw_detections

# TFLite 런타임 3단 폴백
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


def get_rss_mb():
    """현재 프로세스의 RSS 메모리 (MB). 못 읽으면 None."""
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return None
    return None


def get_max_temp_c():
    """시스템 모든 thermal zone의 max 온도 (°C). 못 읽으면 None."""
    max_temp = None
    try:
        zones = sorted(Path('/sys/class/thermal').glob('thermal_zone*'))
        for zone in zones:
            try:
                temp_str = (zone / 'temp').read_text().strip()
                temp_c = int(temp_str) / 1000.0
                if max_temp is None or temp_c > max_temp:
                    max_temp = temp_c
            except Exception:
                continue
    except Exception:
        return None
    return max_temp


def letterbox(image_bgr, target_size, pad_value=114):
    h0, w0 = image_bgr.shape[:2]
    tw, th = target_size
    scale = min(tw / w0, th / h0)
    nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_w, pad_h = tw - nw, th - nh
    left, top = pad_w // 2, pad_h // 2
    right, bottom = pad_w - left, pad_h - top
    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=(pad_value, pad_value, pad_value),
    )
    return padded, (left, top, right, bottom)


def prepare_input(rgb, dtype):
    if dtype == np.float32:
        x = rgb.astype(np.float32) / 255.0
    elif dtype == np.uint8:
        x = rgb.astype(np.uint8)
    elif dtype == np.int8:
        x = (rgb.astype(np.int16) - 128).clip(-128, 127).astype(np.int8)
    else:
        raise TypeError(f"Unsupported dtype: {dtype}")
    return np.expand_dims(x, axis=0)


def run_one(image_bgr, interp, input_detail, output_detail, mw, mh, w0, h0, conf, iou):
    """한 프레임 처리. 각 단계 latency 반환 (단위 ms). 마지막 detection 개수도."""
    # preprocess
    t0 = time.perf_counter()
    padded, pad = letterbox(image_bgr, (mw, mh))
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    tensor = prepare_input(rgb, input_detail['dtype'])
    t_pre = (time.perf_counter() - t0) * 1000

    # inference
    t0 = time.perf_counter()
    interp.set_tensor(input_detail['index'], tensor)
    interp.invoke()
    raw = interp.get_tensor(output_detail['index'])
    t_inf = (time.perf_counter() - t0) * 1000

    # postprocess
    t0 = time.perf_counter()
    boxes_in, scores, class_ids = decode_yolov8(raw, (mw, mh), conf_threshold=conf)
    keep = non_max_suppression(boxes_in, scores, class_ids, iou_threshold=iou)
    boxes_in, scores, class_ids = boxes_in[keep], scores[keep], class_ids[keep]
    boxes_orig = scale_boxes(boxes_in, (mw, mh), (w0, h0), letterbox_pad=pad)
    t_post = (time.perf_counter() - t0) * 1000

    # draw (실시간 루프 기준 — 화면 출력 또는 LED 반응으로 가는 단계)
    t0 = time.perf_counter()
    _ = draw_detections(image_bgr, boxes_orig, scores, class_ids)
    t_draw = (time.perf_counter() - t0) * 1000

    return t_pre, t_inf, t_post, t_draw, len(scores)


def pct(arr, p):
    s = sorted(arr)
    return s[int(p * (len(s) - 1))]


def stats(arr):
    return {
        "mean": statistics.mean(arr),
        "median": statistics.median(arr),
        "p50": pct(arr, 0.50),
        "p95": pct(arr, 0.95),
        "min": min(arr),
        "max": max(arr),
    }


def main():
    ap = argparse.ArgumentParser(description="YOLOv8 e2e benchmark (benchmark standard format)")
    ap.add_argument("model", help=".tflite 파일 경로")
    ap.add_argument("image", help="입력 이미지 경로")
    ap.add_argument("--runs", type=int, default=100, help="측정 반복 횟수 (기본 100, 리뷰어 권고)")
    ap.add_argument("--warmup", type=int, default=10, help="워밍업 반복 횟수 (기본 10)")
    ap.add_argument("--threads", type=int, default=4, help="CPU 스레드 수")
    ap.add_argument("--conf", type=float, default=0.25, help="confidence threshold")
    ap.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold")
    ap.add_argument("--json", help="JSON 출력 경로 (선택)")
    args = ap.parse_args()

    model_path = Path(args.model)
    image_path = Path(args.image)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")
    if not image_path.exists():
        sys.exit(f"ERROR: image not found: {image_path}")

    print("== E2E Benchmark (benchmark standard format) ==")
    print(f"  runtime: {RUNTIME}")
    print(f"  model:   {model_path}")
    print(f"  image:   {image_path}")
    print(f"  runs:    {args.runs}   warmup: {args.warmup}   threads: {args.threads}")

    # Setup
    interp = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    interp.allocate_tensors()
    input_detail = interp.get_input_details()[0]
    output_detail = interp.get_output_details()[0]
    _, mh, mw, _ = (int(x) for x in input_detail['shape'])

    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        sys.exit(f"ERROR: cv2.imread failed: {image_path}")
    h0, w0 = image_bgr.shape[:2]
    print(f"  input: {mw}x{mh} ({input_detail['dtype'].__name__})   image: {w0}x{h0}")

    # Warmup
    print(f"\n  warmup ({args.warmup} runs)...")
    for _ in range(args.warmup):
        run_one(image_bgr, interp, input_detail, output_detail, mw, mh, w0, h0, args.conf, args.iou)

    # Measured runs + peak monitoring
    print(f"  measuring ({args.runs} runs)...")
    t_pre_list, t_inf_list, t_post_list, t_draw_list, t_total_list = [], [], [], [], []
    rss_peak = get_rss_mb() or 0
    temp_peak = get_max_temp_c() or 0
    last_det_count = 0

    progress_step = max(args.runs // 10, 1)
    for i in range(args.runs):
        t_total_start = time.perf_counter()
        t_pre, t_inf, t_post, t_draw, det_count = run_one(
            image_bgr, interp, input_detail, output_detail, mw, mh, w0, h0, args.conf, args.iou
        )
        t_total = (time.perf_counter() - t_total_start) * 1000

        t_pre_list.append(t_pre)
        t_inf_list.append(t_inf)
        t_post_list.append(t_post)
        t_draw_list.append(t_draw)
        t_total_list.append(t_total)
        last_det_count = det_count

        rss = get_rss_mb()
        if rss and rss > rss_peak:
            rss_peak = rss
        temp = get_max_temp_c()
        if temp and temp > temp_peak:
            temp_peak = temp

        if (i + 1) % progress_step == 0:
            print(f"    {i+1}/{args.runs} ...")

    # Aggregate
    pre_s = stats(t_pre_list)
    inf_s = stats(t_inf_list)
    post_s = stats(t_post_list)
    draw_s = stats(t_draw_list)
    total_s = stats(t_total_list)
    fps_mean = 1000.0 / total_s['mean']

    print(f"\n== Results ({args.runs} measured runs, warm steady-state) ==")
    print(f"  stage         mean      p50      p95      min      max     (ms)")
    print(f"  preprocess  {pre_s['mean']:7.2f}  {pre_s['p50']:7.2f}  {pre_s['p95']:7.2f}  {pre_s['min']:7.2f}  {pre_s['max']:7.2f}")
    print(f"  inference   {inf_s['mean']:7.2f}  {inf_s['p50']:7.2f}  {inf_s['p95']:7.2f}  {inf_s['min']:7.2f}  {inf_s['max']:7.2f}")
    print(f"  postprocess {post_s['mean']:7.2f}  {post_s['p50']:7.2f}  {post_s['p95']:7.2f}  {post_s['min']:7.2f}  {post_s['max']:7.2f}")
    print(f"  draw        {draw_s['mean']:7.2f}  {draw_s['p50']:7.2f}  {draw_s['p95']:7.2f}  {draw_s['min']:7.2f}  {draw_s['max']:7.2f}")
    print(f"  total       {total_s['mean']:7.2f}  {total_s['p50']:7.2f}  {total_s['p95']:7.2f}  {total_s['min']:7.2f}  {total_s['max']:7.2f}")
    print()
    print(f"  FPS mean:           {fps_mean:.2f}")
    print(f"  max RSS:            {rss_peak:.1f} MB")
    print(f"  max temp:           {temp_peak:.1f} °C")
    print(f"  detections (last):  {last_det_count}")

    if args.json:
        report = {
            # 벤치마크 표준 Section 3 형식
            "model": str(model_path),
            "runtime": f"{RUNTIME}:{args.threads}",
            "input_shape": [int(x) for x in input_detail['shape']],
            "frames": args.runs,
            "latency_ms_p50": total_s['p50'],
            "latency_ms_p95": total_s['p95'],
            "fps_mean": fps_mean,
            "preprocess_ms_mean": pre_s['mean'],
            "postprocess_ms_mean": post_s['mean'],
            "dropped_frames": 0,  # 단일 이미지 반복이라 X (카메라 시 적용)
            "max_rss_mb": round(rss_peak, 1),
            "max_temp_c": round(temp_peak, 1) if temp_peak else None,
            # 추가 상세
            "warmup": args.warmup,
            "inference_ms_mean": inf_s['mean'],
            "draw_ms_mean": draw_s['mean'],
            "stages": {
                "preprocess": pre_s,
                "inference": inf_s,
                "postprocess": post_s,
                "draw": draw_s,
                "total": total_s,
            },
            "last_detections_count": last_det_count,
            "thresholds": {"conf": args.conf, "iou": args.iou},
        }
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
        print(f"\n  JSON saved: {out_path}")

    print("\n== 완료 ==")


if __name__ == "__main__":
    main()
