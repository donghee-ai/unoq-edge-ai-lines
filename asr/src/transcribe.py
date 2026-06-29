"""transcribe.py — wav 또는 마이크 → Whisper Tiny.en → English text.

Modes:
  --input <wav>       : wav file (offline verification)
  --record <seconds>  : mic record + save wav + recognize
  --device <idx>      : sounddevice card index (default: system default)
  --save <dir>        : save recorded wav here (mic mode, opt-in per privacy policy)

Examples:
  # Host: offline wav -> text
  python src/transcribe.py \\
      --model models/audio/whisper_tiny_en.tflite \\
      --mel-filters models/audio/mel_filters.npz \\
      --tokenizer models/audio/tokenizer.json \\
      --input data/samples/jfk.wav

  # Device: mic record 5s + save + recognize
  python3 ~/transcribe.py \\
      --model /opt/unoq-yolo/models/whisper_tiny_en.tflite \\
      --mel-filters /opt/unoq-yolo/models/mel_filters.npz \\
      --tokenizer /opt/unoq-yolo/models/tokenizer.json \\
      --record 5 \\
      --save /tmp/unoq-yolo/audio-debug/
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# 3단 import 폴백 (vision 패턴 동일)
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        import tflite_runtime.interpreter as _tflite

        Interpreter = _tflite.Interpreter
    except ImportError:
        import tensorflow.lite as _tflite

        Interpreter = _tflite.Interpreter

# Same-folder imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preprocess import (  # noqa: E402
    SAMPLE_RATE,
    load_mel_filters,
    load_wav,
    log_mel_spectrogram,
    pad_or_trim,
)
from tokenizer import WhisperTokenizer  # noqa: E402


def record_audio(seconds, device=None, capture_sr=None):
    """sounddevice로 N초 녹음 → 16 kHz mono float32 PCM.

    1) 지원되는 sample rate 자동 탐지 (16000 우선, USB UAC면 48000 등 fallback)
    2) 3-2-1 카운트다운 (stdout flush로 ssh non-tty 환경에서도 즉시 표시)
    3) blocking 녹음
    4) 16 kHz 아니면 resample
    """
    import sys
    import time

    import sounddevice as sd

    # 1. Find supported sample rate (silent test, no stream open)
    candidates = [capture_sr] if capture_sr else [SAMPLE_RATE, 48000, 44100, 32000]
    used_sr = None
    last_err = None
    for sr in candidates:
        try:
            sd.check_input_settings(
                device=device, samplerate=sr, channels=1, dtype="float32"
            )
            used_sr = sr
            break
        except Exception as e:
            last_err = e
    if used_sr is None:
        raise RuntimeError(f"No supported sample rate found. Last error: {last_err}")

    # 2. Countdown with explicit flush (critical for ssh non-tty buffering)
    print(f"==> Will record {seconds}s @ {used_sr} Hz mono, device={device}", flush=True)
    for i in range(3, 0, -1):
        print(f"    Speak in {i}...", flush=True)
        sys.stdout.flush()
        time.sleep(1)
    print(f"    *** SPEAK NOW (recording {seconds}s) ***", flush=True)
    sys.stdout.flush()

    # 3. Record (blocking)
    audio = sd.rec(
        int(seconds * used_sr),
        samplerate=used_sr,
        channels=1,
        dtype="float32",
        device=device,
        blocking=True,
    ).flatten()
    print(f"==> Recording done ({used_sr} Hz, {len(audio)} samples)", flush=True)

    # 4. Resample to 16 kHz if needed
    if used_sr != SAMPLE_RATE:
        from math import gcd

        from scipy.signal import resample_poly

        g = gcd(used_sr, SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // g, used_sr // g)
        print(
            f"==> Resampled {used_sr} -> {SAMPLE_RATE} Hz, samples={len(audio)}",
            flush=True,
        )
    return np.ascontiguousarray(audio.astype(np.float32))


def save_wav(audio, path):
    """float32 PCM → 16 kHz mono int16 wav file."""
    import soundfile as sf

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, SAMPLE_RATE, subtype="PCM_16")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, help="Whisper TFLite path")
    ap.add_argument("--mel-filters", required=True, help="mel_filters.npz path")
    ap.add_argument("--tokenizer", required=True, help="tokenizer.json path")
    ap.add_argument("--input", help="input wav file (offline mode)")
    ap.add_argument("--record", type=int, help="record N seconds from mic (mic mode)")
    ap.add_argument("--save", help="save recorded wav under this dir (mic mode)")
    ap.add_argument("--device", type=int, default=None, help="sounddevice index (e.g., 0)")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    if not args.input and not args.record:
        print("ERROR: must specify --input <wav> OR --record <seconds>", file=sys.stderr)
        return 2

    # 1. Load model
    print(f"==> Load model: {args.model}")
    interp = Interpreter(model_path=args.model, num_threads=args.threads)
    interp.allocate_tensors()
    in_d = interp.get_input_details()[0]
    out_d = interp.get_output_details()[0]
    print(f"    input  {list(in_d['shape'])} {in_d['dtype'].__name__}")
    print(f"    output {list(out_d['shape'])} {out_d['dtype'].__name__}")

    # 2. Load tokenizer
    print(f"==> Load tokenizer: {args.tokenizer}")
    tok = WhisperTokenizer(args.tokenizer)

    # 3. Load mel filters
    print(f"==> Load mel filters: {args.mel_filters}")
    mel_filters = load_mel_filters(args.mel_filters)

    # 4. Acquire audio
    if args.input:
        print(f"==> Load wav: {args.input}")
        audio = load_wav(args.input)
    else:
        audio = record_audio(args.record, device=args.device)
        if args.save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved = save_wav(audio, Path(args.save) / f"record_{ts}.wav")
            print(f"==> Saved wav: {saved}")

    duration_s = len(audio) / SAMPLE_RATE
    print(f"    audio duration: {duration_s:.2f}s")

    # 5. Preprocess (pad/trim + log-mel)
    t0 = time.perf_counter()
    audio_padded = pad_or_trim(audio)
    mel = log_mel_spectrogram(audio_padded, mel_filters)
    t_preprocess = (time.perf_counter() - t0) * 1000
    print(f"==> Preprocess: mel{list(mel.shape)} {t_preprocess:.0f} ms")

    # 6. Invoke Whisper
    t0 = time.perf_counter()
    interp.set_tensor(in_d["index"], mel)
    interp.invoke()
    token_ids = interp.get_tensor(out_d["index"])
    t_invoke = (time.perf_counter() - t0) * 1000
    print(f"==> Invoke: output{list(token_ids.shape)} {t_invoke:.0f} ms")

    # 7. Decode tokens -> text
    t0 = time.perf_counter()
    text = tok.decode(token_ids)
    t_decode = (time.perf_counter() - t0) * 1000

    # 8. Output
    print()
    print("=" * 60)
    print(f">>> {text if text else '(empty)'}")
    print("=" * 60)
    print(f"  preprocess: {t_preprocess:>7.0f} ms")
    print(f"  invoke:     {t_invoke:>7.0f} ms")
    print(f"  decode:     {t_decode:>7.0f} ms")
    print(f"  total:      {t_preprocess + t_invoke + t_decode:>7.0f} ms")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
