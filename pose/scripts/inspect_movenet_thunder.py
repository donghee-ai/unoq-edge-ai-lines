"""MoveNet Thunder INT8 — 호스트 introspection + dummy invoke latency.

목적:
  1. TFLite 모델 텐서 dtype 분포 확인 (full int8 PTQ 검증)
  2. 입력/출력 details + quantization parameters
  3. dummy uint8 입력으로 latency p50/p95 (warmup 후 100 회)
  4. 출력 shape 확인 (예상: [1, 1, 17, 3])
"""
import os
import time
import numpy as np
from ai_edge_litert.interpreter import Interpreter

PATH = os.environ.get("MODEL_PATH", "/work/models/movenet_thunder_int8.tflite")
N_RUNS = int(os.environ.get("N_RUNS", "100"))
N_WARMUP = int(os.environ.get("N_WARMUP", "5"))

print("=" * 70)
print(f"파일: {PATH}")
sz = os.path.getsize(PATH)
print(f"크기: {sz} bytes ({sz/1024/1024:.2f} MB)")
print("=" * 70)

itp = Interpreter(model_path=PATH, num_threads=4)
itp.allocate_tensors()

ins = itp.get_input_details()
outs = itp.get_output_details()

print(f"\n입력 details ({len(ins)}):")
for d in ins:
    print(f"  name={d['name']}")
    print(f"  shape={list(d['shape'])}  dtype={d['dtype'].__name__}")
    print(f"  qparams={d['quantization_parameters']}")

print(f"\n출력 details ({len(outs)}):")
for d in outs:
    print(f"  name={d['name']}")
    print(f"  shape={list(d['shape'])}  dtype={d['dtype'].__name__}")
    print(f"  qparams={d['quantization_parameters']}")

# 텐서 dtype 분포
dtype_counts = {}
quant_counts = {"quantized": 0, "float": 0, "other": 0}
all_details = itp.get_tensor_details()
for td in all_details:
    dn = td['dtype'].__name__
    dtype_counts[dn] = dtype_counts.get(dn, 0) + 1
    qp = td.get('quantization_parameters', {})
    if len(qp.get('scales', [])) > 0:
        quant_counts["quantized"] += 1
    elif dn in ("float32", "float16"):
        quant_counts["float"] += 1
    else:
        quant_counts["other"] += 1

print(f"\n전체 텐서: {len(all_details)}")
print(f"dtype 분포: {dtype_counts}")
print(f"양자화 분포: {quant_counts}")

# 양자화 형식 판정
in_dtype = ins[0]['dtype'].__name__
out_dtype = outs[0]['dtype'].__name__
int_total = dtype_counts.get('int8', 0) + dtype_counts.get('uint8', 0)
float_total = dtype_counts.get('float32', 0) + dtype_counts.get('float16', 0)
if in_dtype in ('uint8', 'int8') and out_dtype in ('uint8', 'int8', 'float32'):
    if int_total > float_total:
        verdict = "full int8 PTQ (w8a8 또는 weight8+activation8)"
    else:
        verdict = "partial int8 (mixed precision)"
else:
    verdict = "float / mixed (정밀 양자화 X)"
print(f"\n양자화 판정: {verdict}")

# dummy invoke latency
print()
print("=" * 70)
print(f"Latency 측정 — warmup {N_WARMUP}, runs {N_RUNS}, threads=4")
print("=" * 70)

in_shape = ins[0]['shape']
in_dtype_np = ins[0]['dtype']

# 입력 형식에 맞춰 dummy 생성
if in_dtype_np == np.uint8 or in_dtype_np == np.int8:
    dummy = np.random.randint(0, 256, size=in_shape, dtype=np.uint8).astype(in_dtype_np)
else:
    dummy = np.random.random(in_shape).astype(in_dtype_np)

# warmup
for _ in range(N_WARMUP):
    itp.set_tensor(ins[0]['index'], dummy)
    itp.invoke()

# 실측
ts = []
for _ in range(N_RUNS):
    itp.set_tensor(ins[0]['index'], dummy)
    t0 = time.perf_counter()
    itp.invoke()
    ts.append((time.perf_counter() - t0) * 1000)

ts = np.array(ts)
print(f"  mean   : {ts.mean():.2f} ms")
print(f"  p50    : {np.percentile(ts, 50):.2f} ms")
print(f"  p95    : {np.percentile(ts, 95):.2f} ms")
print(f"  min/max: {ts.min():.2f} / {ts.max():.2f} ms")
print(f"  FPS p50: {1000/np.percentile(ts, 50):.1f}")

# 출력 sanity
out = itp.get_tensor(outs[0]['index'])
print(f"\n출력 sanity:")
print(f"  shape    : {list(out.shape)}  dtype={out.dtype}")
print(f"  min/max  : {out.min():.4f} / {out.max():.4f}")
print(f"  17 keypoint expected: shape[-2]={out.shape[-2]} (=17?)")
print(f"  3 channel (y,x,conf) expected: shape[-1]={out.shape[-1]} (=3?)")

print()
print("=" * 70)
print("DONE")
print("=" * 70)
