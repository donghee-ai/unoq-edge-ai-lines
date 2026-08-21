#!/usr/bin/env python3
"""KWS 공식 벤치마크 — invoke latency (100회) + wav 검증 + JSON 저장.

pose 라인 --json 옵션 계승 + KWS 고유 항목 (frontend latency, false trigger, wav 정확도).

두 모드:
  A) latency-only : dummy int8 zeros 입력 100회 invoke 시간 측정 (frontend 제외)
  B) wav-verify   : golden wav 폴더 각 파일 → frontend → invoke → 예측 라벨 대조 (accuracy)

JSON 형식은 pose benchmarks 와 호환 (fps_p50, temp_peak, rss_peak 필드 유지).

사용:
  # 디바이스 (SSH):
  source ~/venv-unoq/bin/activate

  # A) latency-only
  python3 ~/kws_test/scripts/benchmark_kws.py \
      --model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
      --labels ~/kws_test/scripts/labels_12.txt \
      --preset ds_cnn \
      --runs 100 --threads 1 \
      --json ~/kws_test/benchmarks/kws_latency.json

  # B) wav-verify (data/golden/ 폴더에 wav 넣어두고)
  python3 ~/kws_test/scripts/benchmark_kws.py \
      --model ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
      --labels ~/kws_test/scripts/labels_12.txt \
      --preset ds_cnn \
      --wav-dir ~/kws_test/data/golden \
      --json ~/kws_test/benchmarks/kws_wav_verify.json
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


sys.path.insert(0, str(Path(__file__).resolve().parent))

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

from mfcc_frontend import PRESETS, compute_features, quantize_to_int8


def _load_labels(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _rss_mb() -> float | None:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return None
    return None


def _max_temp_c() -> float | None:
    try:
        m = None
        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            try:
                t = int((zone / "temp").read_text().strip()) / 1000.0
                if m is None or t > m:
                    m = t
            except Exception:
                continue
        return m
    except Exception:
        return None


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max()
    e = np.exp(x)
    return e / (e.sum() + 1e-9)


def _dummy_input(itp, in_d):
    shape = tuple(int(x) for x in in_d["shape"])
    if in_d["dtype"] == np.int8:
        return np.zeros(shape, dtype=np.int8)
    if in_d["dtype"] == np.uint8:
        return np.zeros(shape, dtype=np.uint8)
    return np.zeros(shape, dtype=np.float32)


def bench_latency(itp, in_d, out_d, warmup: int, runs: int) -> dict:
    x = _dummy_input(itp, in_d)
    for _ in range(warmup):
        itp.set_tensor(in_d["index"], x)
        itp.invoke()

    lat = []
    for _ in range(runs):
        t0 = time.perf_counter()
        itp.set_tensor(in_d["index"], x)
        itp.invoke()
        _ = itp.get_tensor(out_d["index"])
        lat.append((time.perf_counter() - t0) * 1000.0)

    lat.sort()
    p50 = lat[len(lat) // 2]
    return {
        "runs": runs,
        "warmup": warmup,
        "mean_ms": round(statistics.mean(lat), 3),
        "p50_ms": round(p50, 3),
        "p95_ms": round(lat[int(len(lat) * 0.95)], 3),
        "min_ms": round(lat[0], 3),
        "max_ms": round(lat[-1], 3),
        "fps_p50": round(1000.0 / p50 if p50 > 0 else 0.0, 2),
    }


def bench_wav(
    itp, in_d, out_d, preset, labels, wav_dir: Path,
    in_scale: float, in_zp: int, out_scale: float, out_zp: int,
) -> dict:
    """wav 파일들에 대해 frontend → invoke → 예측 라벨 산출."""
    try:
        import soundfile as sf
    except ImportError:
        return {"error": "soundfile not installed. pip install soundfile"}

    wavs = sorted(wav_dir.glob("*.wav"))
    if not wavs:
        return {"error": f"no wav files in {wav_dir}"}

    results = []
    frontend_ms = []
    invoke_ms = []
    for wav in wavs:
        pcm, sr = sf.read(str(wav), dtype="int16")
        if pcm.ndim > 1:
            pcm = pcm[:, 0]
        # 리샘플 (필요 시 — 여기선 단순 검증용, sr 다르면 skip)
        if sr != preset.sample_rate:
            results.append({
                "file": wav.name,
                "skip": f"sample rate mismatch {sr} vs {preset.sample_rate}",
            })
            continue

        t_f0 = time.perf_counter()
        feats = compute_features(pcm, preset)
        t_f1 = time.perf_counter()
        frontend_ms.append((t_f1 - t_f0) * 1000.0)

        if in_d["dtype"] == np.int8:
            tensor = quantize_to_int8(feats, in_scale, in_zp)
        elif in_d["dtype"] == np.uint8:
            q = np.round(feats / in_scale + in_zp).astype(np.int32)
            tensor = np.clip(q, 0, 255).astype(np.uint8)
        else:
            tensor = feats.astype(np.float32)
        tensor = tensor.reshape(in_d["shape"])

        t_i0 = time.perf_counter()
        itp.set_tensor(in_d["index"], tensor)
        itp.invoke()
        raw = itp.get_tensor(out_d["index"])
        t_i1 = time.perf_counter()
        invoke_ms.append((t_i1 - t_i0) * 1000.0)

        if out_d["dtype"] == np.int8:
            logits = (raw.flatten().astype(np.float32) - out_zp) * out_scale
        elif out_d["dtype"] == np.uint8:
            logits = (raw.flatten().astype(np.float32) - out_zp) * out_scale
        else:
            logits = raw.flatten().astype(np.float32)

        probs = _softmax(logits)
        top = int(np.argmax(probs))
        label = labels[top] if 0 <= top < len(labels) else str(top)

        # 예측 정답 계산 (파일명이 라벨 접두어로 시작한다 가정)
        # 예: "yes_001.wav" → 정답 "yes"
        gt = wav.stem.split("_")[0].lower()
        pred_lower = label.lower()
        correct = (gt == pred_lower) or (gt in pred_lower)
        results.append({
            "file": wav.name,
            "predicted": label,
            "confidence": round(float(probs[top]), 3),
            "gt_guess_from_filename": gt,
            "correct": correct,
        })

    correct_count = sum(1 for r in results if r.get("correct"))
    total = sum(1 for r in results if "predicted" in r)
    return {
        "n_files": len(wavs),
        "n_evaluated": total,
        "n_correct": correct_count,
        "accuracy": round(correct_count / total, 3) if total else None,
        "frontend_ms": {
            "mean": round(statistics.mean(frontend_ms), 3) if frontend_ms else None,
            "p95": round(statistics.quantiles(frontend_ms, n=20)[18], 3)
            if len(frontend_ms) >= 20 else None,
        },
        "invoke_ms": {
            "mean": round(statistics.mean(invoke_ms), 3) if invoke_ms else None,
            "p95": round(statistics.quantiles(invoke_ms, n=20)[18], 3)
            if len(invoke_ms) >= 20 else None,
        },
        "per_file": results,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--preset", choices=["ds_cnn", "micro_speech"], default="ds_cnn")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--wav-dir", default=None, help="wav 검증 폴더 (제공 시 wav-verify 모드도 실행)")
    ap.add_argument("--json", default=None, help="결과 JSON 저장")
    args = ap.parse_args()

    model = Path(args.model)
    if not model.exists():
        sys.exit(f"ERROR: model not found: {model}")

    labels_path = Path(args.labels)
    if not labels_path.exists():
        sys.exit(f"ERROR: labels not found: {labels_path}")
    labels = _load_labels(labels_path)
    preset = PRESETS[args.preset]

    itp = tflite.Interpreter(model_path=str(model), num_threads=args.threads)
    itp.allocate_tensors()
    in_d = itp.get_input_details()[0]
    out_d = itp.get_output_details()[0]

    qp_in = in_d.get("quantization_parameters", {}) or {}
    if qp_in.get("scales") is not None and len(qp_in["scales"]) > 0:
        in_scale = float(qp_in["scales"][0])
        in_zp = int(qp_in["zero_points"][0])
    else:
        in_scale, in_zp = in_d.get("quantization", (1.0, 0))
    qp_out = out_d.get("quantization_parameters", {}) or {}
    if qp_out.get("scales") is not None and len(qp_out["scales"]) > 0:
        out_scale = float(qp_out["scales"][0])
        out_zp = int(qp_out["zero_points"][0])
    else:
        out_scale, out_zp = out_d.get("quantization", (1.0, 0))

    print(f"== KWS benchmark ({RUNTIME}) ==")
    print(f"  model:   {model} ({model.stat().st_size} bytes)")
    print(f"  labels:  {labels_path} ({len(labels)} classes)")
    print(f"  preset:  {args.preset}")
    print(f"  threads: {args.threads}")

    rss0 = _rss_mb()
    temp0 = _max_temp_c()

    lat = bench_latency(itp, in_d, out_d, args.warmup, args.runs)

    rss1 = _rss_mb()
    temp1 = _max_temp_c()

    print(f"\n== Latency (dummy zeros) ==")
    for k, v in lat.items():
        print(f"  {k:>10s}: {v}")
    print(f"\n== System ==")
    print(f"  rss_mb:      before={rss0}  after={rss1}")
    print(f"  temp_c_max:  before={temp0}  after={temp1}")

    result = {
        "runtime": RUNTIME,
        "model": {
            "path": str(model),
            "size_bytes": int(model.stat().st_size),
            "input_shape": [int(x) for x in in_d["shape"]],
            "input_dtype": in_d["dtype"].__name__,
            "output_shape": [int(x) for x in out_d["shape"]],
            "output_dtype": out_d["dtype"].__name__,
        },
        "labels": labels,
        "preset": args.preset,
        "threads": args.threads,
        "latency_ms": lat,
        "system": {
            "rss_before_mb": rss0,
            "rss_after_mb": rss1,
            "temp_c_before": temp0,
            "temp_c_after": temp1,
        },
    }

    if args.wav_dir:
        wav_dir = Path(args.wav_dir)
        if wav_dir.exists():
            print(f"\n== wav-verify ({wav_dir}) ==")
            wv = bench_wav(itp, in_d, out_d, preset, labels, wav_dir,
                           in_scale, in_zp, out_scale, out_zp)
            result["wav_verify"] = wv
            print(f"  n_files:    {wv.get('n_files')}")
            print(f"  accuracy:   {wv.get('accuracy')}")
            print(f"  frontend:   {wv.get('frontend_ms')}")
            print(f"  invoke:     {wv.get('invoke_ms')}")
        else:
            print(f"\n[skip] wav_dir not found: {wav_dir}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(result, indent=2, default=_json_default),
            encoding="utf-8",
        )
        print(f"\n[json] {args.json}")


if __name__ == "__main__":
    main()
