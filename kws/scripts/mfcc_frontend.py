"""KWS 오디오 프론트엔드 — MFCC 특징 추출.

두 가지 파라미터 프리셋 지원 (모델별 학습 시점 파라미터 정확히 복제):

  1. "ds_cnn" — MLPerf Tiny KWS DS-CNN INT8
       입력 [1, 49, 10, 1] : MFCC 49 프레임 × 10 계수
       윈도우 25 ms (=400 samples @ 16kHz), 홉 10 ms (=160 samples)
       + 1 프레임 앞뒤 padding → 정확히 49 프레임

  2. "micro_speech" — Google TFLM MicroSpeech
       입력 [1, 1960] : 49 × 40 log-Mel flatten (int8, uint8 shift)
       윈도우 30 ms (=480 samples), 홉 20 ms (=320 samples)
       주의: Google microspeech-frontend 은 표준 MFCC 대신 log-Mel + PCAN 후처리 사용
             본 라인은 근사 재구현 (표준 log-Mel) — 정확도 검증 필요

디바이스에서는 python_speech_features 만 사용 (경량 numpy only).
호스트에서는 librosa 폴백 가능 (있으면 사용, 없으면 python_speech_features).
"""
from __future__ import annotations

import numpy as np


# python_speech_features 기본 파라미터로 MFCC 재현
try:
    from python_speech_features import mfcc, logfbank
    _HAS_PSF = True
except ImportError:
    _HAS_PSF = False

try:
    import librosa
    _HAS_LIBROSA = True
except ImportError:
    _HAS_LIBROSA = False


# === 프리셋 ===

class FrontendPreset:
    """모델별 프리셋 (학습 시점 파라미터).

    파라미터 하나라도 불일치하면 정확도 크게 떨어지므로 신중히 조정.
    """
    def __init__(
        self,
        name: str,
        sample_rate: int,
        window_size_ms: float,
        window_stride_ms: float,
        num_frames: int,
        num_features: int,       # MFCC 계수 수 or log-Mel bin 수
        feature_type: str,       # "mfcc" | "log_mel"
        input_shape: tuple,      # 모델 입력 tensor shape (batch 포함)
        input_dtype: str,        # "int8" | "uint8" | "float32"
    ):
        self.name = name
        self.sample_rate = sample_rate
        self.window_size_ms = window_size_ms
        self.window_stride_ms = window_stride_ms
        self.num_frames = num_frames
        self.num_features = num_features
        self.feature_type = feature_type
        self.input_shape = input_shape
        self.input_dtype = input_dtype

    @property
    def window_samples(self) -> int:
        return int(self.sample_rate * self.window_size_ms / 1000)

    @property
    def stride_samples(self) -> int:
        return int(self.sample_rate * self.window_stride_ms / 1000)

    @property
    def clip_samples(self) -> int:
        # 1초 클립 (KWS 표준)
        return self.sample_rate


PRESET_DS_CNN = FrontendPreset(
    name="ds_cnn",
    sample_rate=16000,
    window_size_ms=40.0,       # MLPerf Tiny KWS 참조 (ARM ML-KWS-for-MCU 계승) — 25 아님
    window_stride_ms=20.0,     # (1000-40)/20 + 1 = 49 프레임 정확
    num_frames=49,
    num_features=10,
    feature_type="mfcc",
    input_shape=(1, 49, 10, 1),
    input_dtype="int8",
)

PRESET_MICRO_SPEECH = FrontendPreset(
    name="micro_speech",
    sample_rate=16000,
    window_size_ms=30.0,
    window_stride_ms=20.0,
    num_frames=49,
    num_features=40,
    feature_type="log_mel",
    input_shape=(1, 1960),   # flatten
    input_dtype="int8",
)


PRESETS = {
    "ds_cnn": PRESET_DS_CNN,
    "micro_speech": PRESET_MICRO_SPEECH,
}


# === 프론트엔드 ===

def _pad_or_trim(pcm: np.ndarray, target_samples: int) -> np.ndarray:
    """1초 (16000 samples) 로 정확히 맞춤. 짧으면 zero-pad, 길면 뒤에서 자름."""
    if len(pcm) == target_samples:
        return pcm
    if len(pcm) < target_samples:
        return np.concatenate([pcm, np.zeros(target_samples - len(pcm), dtype=pcm.dtype)])
    return pcm[-target_samples:]


def _mfcc_via_psf(pcm_f32: np.ndarray, preset: FrontendPreset) -> np.ndarray:
    """python_speech_features 로 MFCC.

    반환: shape (num_frames, num_features) float32
    """
    if not _HAS_PSF:
        raise RuntimeError(
            "python_speech_features not installed. "
            "pip install python_speech_features"
        )
    # MLPerf Tiny KWS / ARM ML-KWS-for-MCU 표준 파라미터:
    #  - 40 mel filterbanks, DCT → 10 MFCC 계수
    #  - lowfreq=20, highfreq=4000 (음성 주요 대역)
    #  - ceplifter=0 (tf.signal.mfccs_from_log_mel_spectrograms 동작 일치)
    #  - nfft=1024 (window 640 sample 커버)
    feats = mfcc(
        signal=pcm_f32,
        samplerate=preset.sample_rate,
        winlen=preset.window_size_ms / 1000.0,
        winstep=preset.window_stride_ms / 1000.0,
        numcep=preset.num_features,
        nfilt=40,
        nfft=1024,
        lowfreq=20,
        highfreq=4000,
        preemph=0.97,
        ceplifter=0,
        appendEnergy=True,
    )
    # 프레임 수 보정 (padding/trim)
    if feats.shape[0] < preset.num_frames:
        pad = np.zeros((preset.num_frames - feats.shape[0], preset.num_features), dtype=feats.dtype)
        feats = np.vstack([feats, pad])
    elif feats.shape[0] > preset.num_frames:
        feats = feats[:preset.num_frames]
    return feats.astype(np.float32)


def _log_mel_via_librosa(pcm_f32: np.ndarray, preset: FrontendPreset) -> np.ndarray:
    """librosa 로 log-Mel spectrogram.

    반환: shape (num_frames, num_features) float32
    """
    if not _HAS_LIBROSA:
        raise RuntimeError(
            "librosa not installed. "
            "pip install librosa  또는 python_speech_features 폴백 사용"
        )
    mel = librosa.feature.melspectrogram(
        y=pcm_f32,
        sr=preset.sample_rate,
        n_fft=512,
        hop_length=preset.stride_samples,
        win_length=preset.window_samples,
        n_mels=preset.num_features,
        fmin=20,
        fmax=preset.sample_rate // 2,
        power=2.0,
    )
    # log 변환
    log_mel = np.log(mel + 1e-6)
    # (n_mels, T) -> (T, n_mels)
    log_mel = log_mel.T
    if log_mel.shape[0] < preset.num_frames:
        pad = np.zeros(
            (preset.num_frames - log_mel.shape[0], preset.num_features),
            dtype=log_mel.dtype,
        )
        log_mel = np.vstack([log_mel, pad])
    elif log_mel.shape[0] > preset.num_frames:
        log_mel = log_mel[:preset.num_frames]
    return log_mel.astype(np.float32)


def _log_mel_via_psf(pcm_f32: np.ndarray, preset: FrontendPreset) -> np.ndarray:
    """python_speech_features 로 log-Mel (fallback)."""
    if not _HAS_PSF:
        raise RuntimeError("python_speech_features not installed.")
    feats = logfbank(
        signal=pcm_f32,
        samplerate=preset.sample_rate,
        winlen=preset.window_size_ms / 1000.0,
        winstep=preset.window_stride_ms / 1000.0,
        nfilt=preset.num_features,
        nfft=512,
        lowfreq=20,
        highfreq=preset.sample_rate // 2,
        preemph=0.97,
    )
    if feats.shape[0] < preset.num_frames:
        pad = np.zeros((preset.num_frames - feats.shape[0], preset.num_features), dtype=feats.dtype)
        feats = np.vstack([feats, pad])
    elif feats.shape[0] > preset.num_frames:
        feats = feats[:preset.num_frames]
    return feats.astype(np.float32)


def compute_features(
    pcm_int16: np.ndarray,
    preset: FrontendPreset,
) -> np.ndarray:
    """1초 PCM (int16 or float32) → 모델 입력 tensor.

    입력:
      pcm_int16 : shape (N,) int16 (일반적 마이크 원본) 또는 float32 [-1, 1]

    반환:
      shape=preset.input_shape, dtype=preset.input_dtype 텐서
    """
    # 정규화 (float32 [-1, 1])
    if pcm_int16.dtype in (np.int16, np.int32, np.int64):
        pcm_f32 = pcm_int16.astype(np.float32) / 32768.0
    else:
        pcm_f32 = pcm_int16.astype(np.float32)

    pcm_f32 = _pad_or_trim(pcm_f32, preset.clip_samples)

    if preset.feature_type == "mfcc":
        feats_2d = _mfcc_via_psf(pcm_f32, preset)  # (num_frames, num_features)
    elif preset.feature_type == "log_mel":
        if _HAS_LIBROSA:
            feats_2d = _log_mel_via_librosa(pcm_f32, preset)
        else:
            feats_2d = _log_mel_via_psf(pcm_f32, preset)
    else:
        raise ValueError(f"unknown feature_type: {preset.feature_type}")

    # shape 조정 → 모델 입력 shape 로
    tensor = feats_2d.reshape(preset.input_shape).astype(np.float32)

    # dtype 조정 (int8 양자화 시 quantization params 필요 — 호출자가 넘겨줌)
    return tensor


def quantize_to_int8(
    tensor_f32: np.ndarray,
    scale: float,
    zero_point: int,
) -> np.ndarray:
    """float32 tensor → int8 (TFLite quantization 표준)."""
    q = np.round(tensor_f32 / scale + zero_point).astype(np.int32)
    q = np.clip(q, -128, 127).astype(np.int8)
    return q


def dequantize_from_int8(
    tensor_i8: np.ndarray,
    scale: float,
    zero_point: int,
) -> np.ndarray:
    """int8 tensor → float32 (softmax 계산용)."""
    return (tensor_i8.astype(np.float32) - zero_point) * scale


# === CLI 진단 ===

def _self_test():
    """더미 1초 zeros PCM 으로 두 프리셋 특징 shape 검증."""
    pcm = np.zeros(16000, dtype=np.int16)
    for name, preset in PRESETS.items():
        try:
            tensor = compute_features(pcm, preset)
            print(f"[{name}] tensor shape={tensor.shape} dtype={tensor.dtype} "
                  f"(expect {preset.input_shape} {preset.input_dtype})")
        except Exception as e:
            print(f"[{name}] FAILED: {e}")


if __name__ == "__main__":
    _self_test()
