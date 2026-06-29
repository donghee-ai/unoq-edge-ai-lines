#!/usr/bin/env python3
"""validate_kws.py — KWS TFLite model introspection + optional latency benchmark.

vision/validate_model.py 패턴을 audio 도메인으로 옮긴 것.
mentor_style/04 §1 introspection + §4 benchmark_kws.

Usage:
    # introspection만
    python src/validate_kws.py models/audio/speech_commands_v2.tflite

    # 50회 latency 측정 추가
    python src/validate_kws.py models/audio/speech_commands_v2.tflite --runs 50

    # JSON 저장
    python src/validate_kws.py models/audio/speech_commands_v2.tflite \
        --runs 50 --json benchmarks/audio/host_kws_$(date +%Y%m%d).json

    # 디바이스에서 (venv-unoq 활성화 상태)
    python3 ~/validate_kws.py /opt/unoq-yolo/models/speech_commands_v2.tflite --runs 50
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

# 3단 import 폴백 — mentor_style/04 §3 패턴
try:
    from ai_edge_litert.interpreter import Interpreter  # type: ignore
    _RUNTIME = "ai_edge_litert"
except ImportError:
    try:
        import tflite_runtime.interpreter as _tflite  # type: ignore
        Interpreter = _tflite.Interpreter
        _RUNTIME = "tflite_runtime"
    except ImportError:
        import tensorflow.lite as _tflite  # type: ignore
        Interpreter = _tflite.Interpreter
        _RUNTIME = "tensorflow.lite"

import numpy as np


# ---------------------------------------------------------------------------
# Helpers (mentor_style/04 §1)
# ---------------------------------------------------------------------------

def _clean_value(v):
    # 클래스 / dtype 자체 (numpy.int32, numpy.float32 등) — instance 아님
    if isinstance(v, type):
        return getattr(v, "__name__", str(v))
    # ndarray / scalar instance — bound method 안전
    if hasattr(v, "tolist"):
        try:
            return v.tolist()
        except TypeError:
            return str(v)
    if hasattr(v, "__name__"):
        return v.__name__
    return v


def _clean_detail(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = {kk: _clean_value(vv) for kk, vv in v.items()}
        else:
            out[k] = _clean_value(v)
    return out


def classify_input(shape, dtype):
    """KWS input 형태 분류 — frontend 위치 결정용 (mentor_style/04 §1)."""
    rank = len(shape)
    if rank == 2 and shape[1] >= 8000:
        return (
            "raw_pcm",
            f"frontend 모델 내장. 디바이스에 feature 라이브러리 불필요. "
            f"shape={list(shape)} dtype={dtype.__name__}",
        )
    if rank in (3, 4):
        return (
            "feature_2d",
            f"외부 MFCC/log-Mel 사전 변환 필요. shape={list(shape)} — "
            f"학습 파이프라인 파라미터(sr/n_mel/hop/window) 정확히 복제 필수.",
        )
    return ("unknown", f"알 수 없는 입력 형식. shape={list(shape)} 모델 카드 재확인.")


def _make_dummy_input(input_detail):
    """introspection / latency 측정용 더미 입력 생성."""
    shape = tuple(int(s) for s in input_detail["shape"])
    dtype = input_detail["dtype"]
    rng = np.random.default_rng(seed=42)
    if dtype == np.float32:
        # raw PCM 또는 normalized feature
        return rng.standard_normal(shape).astype(np.float32) * 0.1
    if dtype == np.uint8:
        return rng.integers(0, 256, size=shape, dtype=np.uint8)
    if dtype == np.int8:
        return rng.integers(-128, 128, size=shape, dtype=np.int8)
    if dtype == np.int16:
        return rng.integers(-32768, 32768, size=shape, dtype=np.int16)
    raise TypeError(f"unsupported input dtype: {dtype}")


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

def introspect(interpreter, model_path):
    in_details = interpreter.get_input_details()
    out_details = interpreter.get_output_details()
    in_shape = in_details[0]["shape"]
    in_dtype = in_details[0]["dtype"]
    kind, hint = classify_input(in_shape, in_dtype)

    report = {
        "model": str(model_path),
        "model_size_bytes": Path(model_path).stat().st_size,
        "runtime": _RUNTIME,
        "platform": {
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "inputs": [_clean_detail(d) for d in in_details],
        "outputs": [_clean_detail(d) for d in out_details],
        "input_kind": kind,
        "input_hint": hint,
        "num_classes": int(out_details[0]["shape"][-1]),
    }
    return report


# ---------------------------------------------------------------------------
# Latency benchmark (mentor_style/04 §4)
# ---------------------------------------------------------------------------

def benchmark_latency(interpreter, runs=50, warmup=5):
    in_detail = interpreter.get_input_details()[0]
    x = _make_dummy_input(in_detail)

    for _ in range(warmup):
        interpreter.set_tensor(in_detail["index"], x)
        interpreter.invoke()

    values = []
    for _ in range(runs):
        t0 = time.perf_counter()
        interpreter.set_tensor(in_detail["index"], x)
        interpreter.invoke()
        values.append((time.perf_counter() - t0) * 1000.0)

    s = sorted(values)
    p95 = s[int(0.95 * (len(s) - 1))]
    return {
        "runs": runs,
        "warmup": warmup,
        "latency_ms_min": min(values),
        "latency_ms_mean": statistics.mean(values),
        "latency_ms_p50": statistics.median(values),
        "latency_ms_p95": p95,
        "latency_ms_max": max(values),
        "fps_mean": 1000.0 / statistics.mean(values),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", help="path to .tflite model")
    ap.add_argument(
        "--runs",
        type=int,
        default=0,
        help="latency benchmark iterations (0 = introspection only)",
    )
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--json", default=None, help="path to save JSON report")
    args = ap.parse_args(argv)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"ERROR: model not found: {model_path}", file=sys.stderr)
        return 2

    interpreter = Interpreter(model_path=str(model_path), num_threads=args.threads)
    interpreter.allocate_tensors()

    report = introspect(interpreter, model_path)

    if args.runs > 0:
        report["latency"] = benchmark_latency(
            interpreter, runs=args.runs, warmup=args.warmup
        )

    # 합격선 평가 (멘토 06 / preflight §11 — KWS target)
    if args.runs > 0:
        lat = report["latency"]
        report["pass_fail"] = {
            "latency_mean_le_50ms": lat["latency_ms_mean"] <= 50.0,
            "latency_p95_le_80ms": lat["latency_ms_p95"] <= 80.0,
        }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"\n==> JSON saved: {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
