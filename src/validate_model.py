#!/usr/bin/env python3
"""
TFLite 모델 검증 및 호스트 CPU 1차 latency 측정 스크립트.

본 프로젝트 규약 (danny/03_project_conventions.md Section 5)에 따라:
- 모델 메타데이터는 hard-code 금지, get_input_details() / get_output_details()로 자동 추출
- CPU 기본, GPU delegate는 향후 feature flag로 추가
- 후처리(NMS, decoding)는 본 스크립트 범위 외 (별도 모듈)

사용:
    python src/validate_model.py <model_path> [--runs N] [--warmup N] [--threads N] [--json OUT]

예:
    python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite
    python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite --json /tmp/unoq-yolo/bench.json
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

# tflite_runtime이 있으면 우선 (디바이스 친화적), 없으면 tensorflow.lite 폴백
try:
    import tflite_runtime.interpreter as tflite
    RUNTIME = "tflite_runtime"
except ImportError:
    import tensorflow.lite as tflite
    RUNTIME = "tensorflow.lite"


def clean_value(v):
    """numpy/특수 객체를 JSON 직렬화 가능 형태로 변환

    주의: numpy type 클래스 (예: np.uint8 그 자체)는 tolist가 unbound method라 호출 불가.
    따라서 isinstance(v, type) 체크가 ndarray/scalar 체크보다 먼저 와야 함.
    """
    # numpy type 클래스 자체 (예: np.uint8, np.float32 — instance 아님)
    if isinstance(v, type):
        return v.__name__
    # numpy ndarray
    if isinstance(v, np.ndarray):
        return v.tolist()
    # numpy scalar instance
    if isinstance(v, np.generic):
        return v.item()
    # 그 외 native Python 타입
    return v


def clean_detail(d):
    """interpreter detail dict 정리"""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = {kk: clean_value(vv) for kk, vv in v.items()}
        else:
            out[k] = clean_value(v)
    return out


def make_dummy_input(input_detail):
    """input shape/dtype에 맞는 더미 입력 생성"""
    shape = tuple(int(x) for x in input_detail["shape"])
    dtype = input_detail["dtype"]

    if dtype == np.uint8:
        return np.random.randint(0, 256, size=shape, dtype=np.uint8)
    if dtype == np.int8:
        return np.random.randint(-128, 128, size=shape, dtype=np.int8)
    if dtype == np.float32:
        return np.random.rand(*shape).astype(np.float32)
    if dtype == np.float16:
        return np.random.rand(*shape).astype(np.float16)
    raise ValueError(f"Unsupported input dtype: {dtype}")


def benchmark(interpreter, input_detail, dummy_input, runs, warmup):
    """latency 측정 (warmup 후 runs회 반복)"""
    for _ in range(warmup):
        interpreter.set_tensor(input_detail["index"], dummy_input)
        interpreter.invoke()

    times_ms = []
    for _ in range(runs):
        t0 = time.perf_counter()
        interpreter.set_tensor(input_detail["index"], dummy_input)
        interpreter.invoke()
        times_ms.append((time.perf_counter() - t0) * 1000.0)

    times_sorted = sorted(times_ms)
    p50 = times_sorted[int(0.50 * (len(times_sorted) - 1))]
    p95 = times_sorted[int(0.95 * (len(times_sorted) - 1))]

    return {
        "runs": runs,
        "warmup": warmup,
        "latency_ms_min": min(times_ms),
        "latency_ms_max": max(times_ms),
        "latency_ms_mean": statistics.mean(times_ms),
        "latency_ms_median": statistics.median(times_ms),
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "fps_mean": 1000.0 / statistics.mean(times_ms),
    }


def main():
    ap = argparse.ArgumentParser(description="TFLite 모델 검증 및 latency 측정")
    ap.add_argument("model", help=".tflite 파일 경로")
    ap.add_argument("--runs", type=int, default=50, help="벤치마크 반복 횟수 (기본 50)")
    ap.add_argument("--warmup", type=int, default=5, help="워밍업 반복 횟수 (기본 5)")
    ap.add_argument("--threads", type=int, default=4, help="CPU 스레드 수 (기본 4)")
    ap.add_argument("--json", help="JSON 결과 출력 파일 경로 (선택)")
    args = ap.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"ERROR: model file not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    size_mb = model_path.stat().st_size / 1024 / 1024

    print("== TFLite 모델 검증 ==")
    print(f"  runtime: {RUNTIME}")
    print(f"  model:   {model_path}")
    print(f"  size:    {size_mb:.2f} MB")
    print(f"  threads: {args.threads}")

    # 1. 로드
    interpreter = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    interpreter.allocate_tensors()

    # 2. 메타데이터 추출
    inputs = [clean_detail(d) for d in interpreter.get_input_details()]
    outputs = [clean_detail(d) for d in interpreter.get_output_details()]

    print("\n== INPUTS ==")
    for i, d in enumerate(inputs):
        print(f"  [{i}] name={d.get('name')}")
        print(f"      shape={d.get('shape')}  dtype={d.get('dtype')}")
        print(f"      quantization={d.get('quantization')}")
        print(f"      quant_params={d.get('quantization_parameters')}")

    print("\n== OUTPUTS ==")
    for i, d in enumerate(outputs):
        print(f"  [{i}] name={d.get('name')}")
        print(f"      shape={d.get('shape')}  dtype={d.get('dtype')}")
        print(f"      quantization={d.get('quantization')}")
        print(f"      quant_params={d.get('quantization_parameters')}")

    # 3. 더미 입력으로 smoke 추론
    print("\n== Smoke Inference (더미 입력) ==")
    input_detail = interpreter.get_input_details()[0]
    dummy = make_dummy_input(input_detail)
    print(f"  input shape: {dummy.shape}, dtype: {dummy.dtype}")

    interpreter.set_tensor(input_detail["index"], dummy)
    interpreter.invoke()

    raw_output_info = []
    for od in interpreter.get_output_details():
        out = interpreter.get_tensor(od["index"])
        raw_output_info.append({
            "name": od.get("name"),
            "shape": list(out.shape),
            "dtype": str(out.dtype),
        })
        print(f"  output: name={od.get('name')} shape={out.shape} dtype={out.dtype}")

    # 4. Benchmark
    print(f"\n== Benchmark (warmup={args.warmup}, runs={args.runs}) ==")
    bench = benchmark(interpreter, input_detail, dummy, args.runs, args.warmup)
    for k, v in bench.items():
        if isinstance(v, float):
            print(f"  {k:20s} = {v:.3f}")
        else:
            print(f"  {k:20s} = {v}")

    # 5. JSON 출력 (선택)
    if args.json:
        report = {
            "model": str(model_path),
            "runtime": RUNTIME,
            "threads": args.threads,
            "model_size_mb": size_mb,
            "inputs": inputs,
            "outputs": outputs,
            "smoke_inference_output": raw_output_info,
            "benchmark": bench,
        }
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nJSON 결과 저장: {out_path}")

    print("\n== 검증 완료 ==")


if __name__ == "__main__":
    main()
