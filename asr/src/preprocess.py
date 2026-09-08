"""preprocess.py — wav PCM → Whisper mel spectrogram.

Numpy 자작 — librosa 의존 없이 호스트/디바이스 동일 동작 보장.
설계 리뷰 단점 2 (feature 추출 학습 일치) 해결: Whisper 공식 알고리즘 복제.

Reference: openai/whisper whisper/audio.py
Whisper params: sr=16000, n_fft=400, hop=160, n_mels=80, fmin=0, fmax=8000.
mel filter bank: openai/whisper assets/mel_filters.npz (key='mel_80').
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000
N_FFT = 400
HOP_LENGTH = 160
N_MELS = 80
CHUNK_LENGTH = 30  # seconds
N_SAMPLES = CHUNK_LENGTH * SAMPLE_RATE  # 480000
N_FRAMES = N_SAMPLES // HOP_LENGTH  # 3000


def load_wav(path):
    """Load wav file, resample to 16 kHz mono, return float32 PCM in [-1, 1]."""
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # stereo -> mono
    if sr != SAMPLE_RATE:
        from math import gcd

        from scipy.signal import resample_poly

        g = gcd(int(sr), SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // g, int(sr) // g)
    return np.ascontiguousarray(audio.astype(np.float32))


def pad_or_trim(audio, length=N_SAMPLES):
    """Pad/truncate audio to fixed 30s = 480000 samples (Whisper requirement)."""
    if audio.shape[-1] > length:
        return audio[..., :length]
    if audio.shape[-1] < length:
        pad_width = length - audio.shape[-1]
        return np.pad(audio, (0, pad_width)).astype(np.float32)
    return audio


def load_mel_filters(path):
    """Load Whisper mel filter bank from mel_filters.npz (key='mel_80')."""
    with np.load(str(path)) as f:
        return f["mel_80"].astype(np.float32)


def log_mel_spectrogram(audio, mel_filters):
    """Compute log-mel spectrogram (Whisper algorithm, numpy port of torch.stft).

    Input:  audio = float32 (N_SAMPLES,)
    Output: (1, N_MELS, N_FRAMES) = (1, 80, 3000) float32

    Steps (matching whisper.audio.log_mel_spectrogram):
      1. Reflect-pad audio by N_FFT//2 each side (center=True equivalent)
      2. Periodic Hann window (length N_FFT)
      3. STFT per frame, hop=HOP_LENGTH, rfft length N_FFT
      4. Drop last frame (whisper convention)
      5. Magnitude squared (power spectrogram)
      6. Mel filter bank multiplication (80, n_bins) @ (n_bins, n_frames)
      7. Log10 + clip min 1e-10
      8. Dynamic range compression: max(log_spec, log_spec.max() - 8.0)
      9. Normalize: (log_spec + 4.0) / 4.0
    """
    audio = np.pad(audio, (N_FFT // 2, N_FFT // 2), mode="reflect")

    # Periodic Hann window (torch.hann_window default = periodic)
    window = np.hanning(N_FFT + 1)[:-1].astype(np.float32)

    # STFT — manual frame-by-frame FFT
    n_full = 1 + (len(audio) - N_FFT) // HOP_LENGTH
    stft_result = np.empty((N_FFT // 2 + 1, n_full), dtype=np.complex64)
    for i in range(n_full):
        start = i * HOP_LENGTH
        frame = audio[start : start + N_FFT] * window
        stft_result[:, i] = np.fft.rfft(frame)

    # Drop last frame (whisper convention)
    stft_result = stft_result[:, :-1]

    # Truncate / pad to exactly N_FRAMES=3000
    if stft_result.shape[1] > N_FRAMES:
        stft_result = stft_result[:, :N_FRAMES]
    elif stft_result.shape[1] < N_FRAMES:
        pad_n = N_FRAMES - stft_result.shape[1]
        stft_result = np.pad(stft_result, ((0, 0), (0, pad_n)))

    # Power spectrogram
    magnitudes = np.abs(stft_result) ** 2

    # Mel filter bank
    mel_spec = mel_filters @ magnitudes  # (80, 3000)

    # Log + clip + normalize (Whisper convention)
    log_spec = np.log10(np.clip(mel_spec, 1e-10, None))
    log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
    log_spec = (log_spec + 4.0) / 4.0

    return log_spec[np.newaxis, :, :].astype(np.float32)


def wav_to_mel(wav_path, mel_filters_path):
    """End-to-end convenience: wav file path -> (1, 80, 3000) mel ready for Whisper."""
    audio = load_wav(wav_path)
    audio = pad_or_trim(audio)
    mel_filters = load_mel_filters(mel_filters_path)
    return log_mel_spectrogram(audio, mel_filters)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Compute Whisper mel from wav, for debugging.")
    ap.add_argument("wav")
    ap.add_argument("--mel-filters", required=True)
    args = ap.parse_args()

    mel = wav_to_mel(args.wav, args.mel_filters)
    print(f"mel shape: {mel.shape} dtype: {mel.dtype}")
    print(f"mel min/max/mean: {mel.min():.3f} / {mel.max():.3f} / {mel.mean():.3f}")
