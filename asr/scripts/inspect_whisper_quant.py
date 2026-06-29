"""Whisper Tiny.en TFLite 양자화 형식 확인.

w8a8 = weights int8 + activations int8 (full int8 PTQ)
fp16 = weights float16, activations float32
fp32 = 양자화 안 됨
"""
import sys
from ai_edge_litert.interpreter import Interpreter

path = "/work/models/audio/whisper_tiny_en.tflite"
itp = Interpreter(model_path=path)
itp.allocate_tensors()

ins = itp.get_input_details()
outs = itp.get_output_details()

print(f"=== {path} ===\n")
print(f"input  details ({len(ins)}):")
for d in ins:
    print(f"  name={d['name']}  shape={d['shape']}  dtype={d['dtype'].__name__}  qparams={d['quantization_parameters']}")
print(f"\noutput details ({len(outs)}):")
for d in outs:
    print(f"  name={d['name']}  shape={d['shape']}  dtype={d['dtype'].__name__}  qparams={d['quantization_parameters']}")

dtype_counts = {}
quant_counts = {"quantized": 0, "float": 0}
total_bytes = 0
tensor_count = 0
for i in range(len(itp.get_tensor_details())):
    td = itp.get_tensor_details()[i]
    dn = td['dtype'].__name__
    dtype_counts[dn] = dtype_counts.get(dn, 0) + 1
    qp = td.get('quantization_parameters', {})
    scales = qp.get('scales', [])
    if len(scales) > 0:
        quant_counts["quantized"] += 1
    elif dn in ("float32", "float16"):
        quant_counts["float"] += 1
    tensor_count += 1

print(f"\n=== 전체 텐서 통계 ===")
print(f"총 텐서: {tensor_count}")
print(f"dtype 분포: {dtype_counts}")
print(f"양자화 여부: {quant_counts}")

import os
sz = os.path.getsize(path)
print(f"\n파일 크기: {sz} bytes ({sz/1024/1024:.1f} MB)")
