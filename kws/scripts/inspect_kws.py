#!/usr/bin/env python3
"""KWS TFLite 모델 introspection + latency 측정.

pose/scripts/inspect_movenet_thunder.py 패턴 그대로:
  - 텐서 dtype/shape/qparams 덤프
  - 양자화 분포 요약 (int8/uint8/float32)
  - dummy 입력 warmup + N runs invoke latency
  - JSON 저장 (선택)

사용:
  python3 scripts/inspect_kws.py models/kws_ref_model_ds_cnn_int8.tflite
  N_RUNS=200 python3 scripts/inspect_kws.py models/*.tflite
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np


def _json_default(obj):
    """numpy 스칼라/배열을 JSON 직렬화 가능하게 변환."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    if hasattr(obj, "item"):
        return obj.item()
    return str(obj)


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


def _tensor_dtype_summary(itp) -> dict:
    """모든 tensor 의 dtype 을 세어서 int8/uint8/float 분포 파악."""
    counts: dict[str, int] = {}
    for i in range(len(itp.get_tensor_details())):
        d = itp.get_tensor_details()[i]
        name = d["dtype"].__name__ if hasattr(d["dtype"], "__name__") else str(d["dtype"])
        counts[name] = counts.get(name, 0) + 1
    return counts


def _quant_flag(itp) -> str:
    """양자화 판정 — int8 tensor 비율."""
    dt = _tensor_dtype_summary(itp)
    total = sum(dt.values())
    int_tensors = dt.get("int8", 0) + dt.get("uint8", 0) + dt.get("int32", 0)
    ratio = int_tensors / total if total else 0
    if ratio >= 0.8:
        return "full int8 PTQ"
    if ratio >= 0.5:
        return "partial int8"
    return "float32 dominant"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", default=os.environ.get(
        "MODEL_PATH", "models/kws_ref_model_ds_cnn_int8.tflite"))
    ap.add_argument("--threads", type=int, default=int(os.environ.get("THREADS", "4")))
    ap.add_argument("--warmup", type=int, default=int(os.environ.get("N_WARMUP", "5")))
    ap.add_argument("--runs", type=int, default=int(os.environ.get("N_RUNS", "100")))
    ap.add_argument("--json", default=None, help="결과 JSON 저장 경로")
    args = ap.parse_args()

    model = Path(args.model)
    if not model.exists():
        sys.exit(f"ERROR: model not found: {model}")

    size = model.stat().st_size
    print(f"== KWS inspect ({RUNTIME}) ==")
    print(f"  model:   {model}")
    print(f"  size:    {size} bytes ({size / 1024:.2f} KB)")
    print(f"  threads: {args.threads}")

    itp = tflite.Interpreter(model_path=str(model), num_threads=args.threads)
    itp.allocate_tensors()

    in_d = itp.get_input_details()[0]
    out_d = itp.get_output_details()[0]

    print(f"\n== I/O ==")
    print(f"  input:   name={in_d['name']}")
    print(f"           shape={list(in_d['shape'])} dtype={in_d['dtype'].__name__}")
    print(f"           quant={in_d.get('quantization')}")
    print(f"  output:  name={out_d['name']}")
    print(f"           shape={list(out_d['shape'])} dtype={out_d['dtype'].__name__}")
    print(f"           quant={out_d.get('quantization')}")

    dt = _tensor_dtype_summary(itp)
    flag = _quant_flag(itp)
    print(f"\n== 양자화 분포 ==")
    for k, v in sorted(dt.items(), key=lambda x: -x[1]):
        print(f"  {k:>10s}: {v}")
    print(f"  판정: {flag}")

    # dummy 입력 생성 (dtype 에 맞게)
    shape = tuple(int(x) for x in in_d["shape"])
    if in_d["dtype"] == np.int8:
        x = np.zeros(shape, dtype=np.int8)
    elif in_d["dtype"] == np.uint8:
        x = np.zeros(shape, dtype=np.uint8)
    else:
        x = np.zeros(shape, dtype=np.float32)

    # warmup
    for _ in range(args.warmup):
        itp.set_tensor(in_d["index"], x)
        itp.invoke()

    # measure
    lat = []
    for _ in range(args.runs):
        t0 = time.perf_counter()
        itp.set_tensor(in_d["index"], x)
        itp.invoke()
        _ = itp.get_tensor(out_d["index"])
        lat.append((time.perf_counter() - t0) * 1000.0)

    lat.sort()
    mean = statistics.mean(lat)
    p50 = lat[len(lat) // 2]
    p95 = lat[int(len(lat) * 0.95)]
    mn = lat[0]
    mx = lat[-1]
    fps50 = 1000.0 / p50 if p50 > 0 else 0.0

    print(f"\n== Latency (invoke only, threads={args.threads}) ==")
    print(f"  runs:  {args.runs}")
    print(f"  mean:  {mean:6.2f} ms")
    print(f"  p50:   {p50:6.2f} ms  ({fps50:6.1f} Hz)")
    print(f"  p95:   {p95:6.2f} ms")
    print(f"  min:   {mn:6.2f} ms")
    print(f"  max:   {mx:6.2f} ms")

    result = {
        "runtime": RUNTIME,
        "model": str(model),
        "size_bytes": int(size),
        "threads": int(args.threads),
        "input": {
            "shape": [int(x) for x in in_d["shape"]],
            "dtype": in_d["dtype"].__name__,
            "quantization": [float(x) for x in in_d.get("quantization", (0, 0))],
        },
        "output": {
            "shape": [int(x) for x in out_d["shape"]],
            "dtype": out_d["dtype"].__name__,
            "quantization": [float(x) for x in out_d.get("quantization", (0, 0))],
        },
        "dtype_distribution": dt,
        "quantization_flag": flag,
        "latency_ms": {
            "runs": args.runs,
            "mean": round(mean, 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "min": round(mn, 3),
            "max": round(mx, 3),
            "fps_p50": round(fps50, 2),
        },
    }

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(result, indent=2, default=_json_default),
            encoding="utf-8",
        )
        print(f"\n== JSON saved: {args.json}")


if __name__ == "__main__":
    main()
