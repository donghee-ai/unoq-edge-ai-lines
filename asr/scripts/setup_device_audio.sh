#!/usr/bin/env bash
# setup_device_audio.sh — install audio deps on UNO Q device.
# Idempotent: re-runs are safe (apt and pip skip already-installed).
#
# Usage:
#   bash scripts/setup_device_audio.sh
#
# Env override:
#   UNO_Q_USER=arduino UNO_Q_HOST=192.168.0.45 bash scripts/setup_device_audio.sh

set -euo pipefail

UNO_Q_USER="${UNO_Q_USER:-arduino}"
UNO_Q_HOST="${UNO_Q_HOST:-192.168.0.45}"
SSH_TARGET="${UNO_Q_USER}@${UNO_Q_HOST}"

echo "==> Target: ${SSH_TARGET}"

echo "==> Phase 1/3: system packages (libportaudio2 + libsndfile1)"
ssh "${SSH_TARGET}" 'sudo apt update && sudo apt install -y libportaudio2 libsndfile1'

echo "==> Phase 2/3: pip install audio deps into venv-unoq"
ssh "${SSH_TARGET}" 'source ~/venv-unoq/bin/activate && \
    pip install sounddevice scipy python_speech_features'

echo "==> Phase 3/3: import smoke test"
ssh "${SSH_TARGET}" 'source ~/venv-unoq/bin/activate && python3 - <<PY
import sys
results = []
try:
    import sounddevice as sd
    results.append(("sounddevice", sd.__version__))
except Exception as e:
    results.append(("sounddevice", f"FAIL: {e}"))
try:
    import scipy
    results.append(("scipy", scipy.__version__))
except Exception as e:
    results.append(("scipy", f"FAIL: {e}"))
try:
    from python_speech_features import logfbank, mfcc
    results.append(("python_speech_features", "OK"))
except Exception as e:
    results.append(("python_speech_features", f"FAIL: {e}"))
try:
    import numpy
    results.append(("numpy", numpy.__version__))
except Exception as e:
    results.append(("numpy", f"FAIL: {e}"))
try:
    from ai_edge_litert.interpreter import Interpreter
    import ai_edge_litert
    results.append(("ai_edge_litert", ai_edge_litert.__version__))
except Exception as e:
    results.append(("ai_edge_litert", f"FAIL: {e}"))

print("--- import smoke test ---")
fail = 0
for name, ver in results:
    mark = "OK" if not ver.startswith("FAIL") else "X "
    print(f"  [{mark}] {name:25s} {ver}")
    if ver.startswith("FAIL"):
        fail += 1

print()
print("--- sounddevice device query ---")
try:
    import sounddevice as sd
    print(sd.query_devices())
except Exception as e:
    print(f"query_devices FAIL: {e}")
    fail += 1

sys.exit(fail)
PY'

echo "==> Setup complete"
