"""ONNX introspection — Qualcomm AI Hub precompiled QNN ONNX 형식 진단.

목적:
  1. onnx / onnxruntime 가용성 확인 (호스트 unoq-pose:22.04 컨테이너)
  2. 두 wrapper ONNX (pose_detector, pose_landmark_detector) graph 구조 확인
  3. EPContext 노드 + 외부 qairt_context.bin 참조 확인
  4. CPU Execution Provider로 InferenceSession 시도 (예상: 실패 — QNN EP 필요)
  5. providers 목록 출력 (QNN EP 가용 여부)
"""

import sys
import os

print("=" * 70)
print("STEP 0 — 패키지 가용성")
print("=" * 70)

mods = {}
for name in ["onnx", "onnxruntime", "numpy"]:
    try:
        m = __import__(name)
        mods[name] = getattr(m, "__version__", "n/a")
        print(f"  {name:20s} {mods[name]}")
    except ImportError as e:
        mods[name] = None
        print(f"  {name:20s} MISSING ({e})")

if not mods.get("onnx") or not mods.get("onnxruntime"):
    print("\n필수 모듈 누락 — 컨테이너에 pip install 필요")
    sys.exit(2)

import onnx
import onnxruntime as ort
import numpy as np

print(f"\n  onnxruntime providers (가용): {ort.get_available_providers()}")

MODELS_DIR = "/work/models"
TARGETS = ["pose_detector.onnx", "pose_landmark_detector.onnx"]

for fname in TARGETS:
    fpath = os.path.join(MODELS_DIR, fname)
    print()
    print("=" * 70)
    print(f"STEP 1 — onnx.load: {fname}")
    print("=" * 70)

    if not os.path.exists(fpath):
        print(f"  파일 없음: {fpath}")
        continue

    sz = os.path.getsize(fpath)
    print(f"  size       : {sz} bytes ({sz/1024:.1f} KB)")

    m = onnx.load(fpath)
    print(f"  ir_version : {m.ir_version}")
    print(f"  producer   : {m.producer_name} {m.producer_version}")
    print(f"  opset      : {[(o.domain or 'ai.onnx', o.version) for o in m.opset_import]}")
    print()

    print("  inputs:")
    for i in m.graph.input:
        dims = [d.dim_value if d.dim_value > 0 else d.dim_param or "?" for d in i.type.tensor_type.shape.dim]
        dtype = i.type.tensor_type.elem_type
        print(f"    {i.name:20s} shape={dims} elem_type={dtype}")

    print("  outputs:")
    for o in m.graph.output:
        dims = [d.dim_value if d.dim_value > 0 else d.dim_param or "?" for d in o.type.tensor_type.shape.dim]
        dtype = o.type.tensor_type.elem_type
        print(f"    {o.name:20s} shape={dims} elem_type={dtype}")

    print(f"  nodes      : {len(m.graph.node)} 개")
    op_counts = {}
    ep_nodes = []
    for n in m.graph.node:
        op_counts[n.op_type] = op_counts.get(n.op_type, 0) + 1
        if n.op_type == "EPContext":
            ep_nodes.append(n)
    print(f"  op_types   : {op_counts}")

    if ep_nodes:
        print(f"\n  EPContext 노드 {len(ep_nodes)} 개 발견 (QNN EP 의존):")
        for n in ep_nodes:
            print(f"    name={n.name}, domain={n.domain}")
            for attr in n.attribute:
                if attr.type == onnx.AttributeProto.STRING:
                    val = attr.s.decode('utf-8', errors='replace')
                    print(f"      attr {attr.name} = {val!r}")
                elif attr.type == onnx.AttributeProto.INT:
                    print(f"      attr {attr.name} = {attr.i}")

    print()
    print("=" * 70)
    print(f"STEP 2 — InferenceSession (CPU EP only): {fname}")
    print("=" * 70)
    try:
        sess = ort.InferenceSession(fpath, providers=["CPUExecutionProvider"])
        print(f"  세션 생성 성공.")
        print(f"  inputs : {[(i.name, i.shape, i.type) for i in sess.get_inputs()]}")
        print(f"  outputs: {[(o.name, o.shape, o.type) for o in sess.get_outputs()]}")
    except Exception as e:
        print(f"  세션 생성 실패: {type(e).__name__}")
        msg = str(e)
        for line in msg.splitlines()[:8]:
            print(f"    {line}")

print()
print("=" * 70)
print("DONE")
print("=" * 70)
