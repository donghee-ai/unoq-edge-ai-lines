"""KWSWorker — daemon thread 에서 마이크 스트림 → KWS 추론 → ModeBus push.

구조:
  Ring buffer (16000 samples × 3 = 3초, 슬라이딩) ← 마이크 콜백 (sounddevice)
                            │
                       200 ms hop
                            │
                            ▼
                   1초 윈도우 자르기
                            │
                     MFCC frontend
                            │
                     TFLite invoke
                            │
                    softmax + top-1
                            │
                confidence > threshold ?
                            │
                            ▼
                    ModeBus.push(source="kws", ...)

주의:
  - 마이크 콜백은 별도 스레드 (sounddevice PortAudio) — ring buffer 는 lock 보호
  - 추론 스레드가 200ms 마다 슬라이딩 윈도우 자르기 → 프레임 스킵 방지
  - _silence_ / _unknown_ 은 push 안 함 (필터)
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from ai_edge_litert import interpreter as tflite
    _RUNTIME = "ai_edge_litert"
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        _RUNTIME = "tflite_runtime"
    except ImportError:
        import tensorflow.lite as tflite
        _RUNTIME = "tensorflow.lite"

try:
    import sounddevice as sd
    _HAS_SD = True
except (ImportError, OSError):
    _HAS_SD = False

from fractions import Fraction

from mfcc_frontend import (
    PRESETS,
    FrontendPreset,
    compute_features,
    dequantize_from_int8,
    quantize_to_int8,
)
from mode_controller import KWS_TO_MODE_4, KWS_TO_MODE_12, Mode, ModeBus

try:
    from scipy.signal import resample_poly
    _HAS_RESAMPLE = True
except ImportError:
    _HAS_RESAMPLE = False


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max()
    e = np.exp(x)
    return e / (e.sum() + 1e-9)


def _load_labels(path: Path) -> list[str]:
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    return [l for l in lines if l]


class KWSWorker:
    """마이크 → KWS → ModeBus."""

    def __init__(
        self,
        model_path: str,
        labels_path: str,
        preset_name: str,
        bus: ModeBus,
        input_device: Optional[int] = None,
        threads: int = 1,
        confidence_threshold: float = 0.70,
        hop_ms: float = 200.0,
        clip_ms: float = 1000.0,
        push_map: Optional[dict] = None,
    ):
        self.model_path = Path(model_path)
        self.labels = _load_labels(Path(labels_path))
        self.preset: FrontendPreset = PRESETS[preset_name]
        self.bus = bus
        self.input_device = input_device
        self.threads = threads
        self.confidence_threshold = confidence_threshold
        self.hop_ms = hop_ms
        self.clip_ms = clip_ms

        # KWS 라벨 → Mode 매핑
        if push_map is not None:
            self.push_map = push_map
        elif len(self.labels) == 12:
            self.push_map = KWS_TO_MODE_12
        elif len(self.labels) == 4:
            self.push_map = KWS_TO_MODE_4
        else:
            self.push_map = {}  # 알 수 없는 라벨 세트 — 사용자 지정 필요

        # 통계
        self.stats = {
            "invocations": 0,
            "detections": 0,
            "silence_count": 0,
            "unknown_count": 0,
            "sub_threshold_count": 0,
            "last_label": None,
            "last_confidence": None,
            "last_invoke_ms": None,
        }

        # 런타임 상태
        self._itp = None
        self._in_d = None
        self._out_d = None
        self._in_scale = 1.0
        self._in_zp = 0
        self._out_scale = 1.0
        self._out_zp = 0

        # Ring buffer (float32 [-1,1]) — 3 s 여유 (KWS 모델 sample rate 기준)
        self._ring_size = int(self.preset.sample_rate * 3)
        self._ring = np.zeros(self._ring_size, dtype=np.float32)
        self._ring_write = 0                            # 다음 쓰기 위치
        self._ring_lock = threading.Lock()
        self._filled = 0                                # 누적 write 카운트

        # 리샘플링 (USB 마이크가 16kHz native 지원 안 할 때)
        self._native_rate: Optional[int] = None         # 실제 스트림 rate (start() 에서 결정)
        self._resample_up: int = 1
        self._resample_down: int = 1

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stream = None

        self.runtime = _RUNTIME

    # === lifecycle ===

    def _load_model(self):
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"KWS model not found: {self.model_path}\n"
                f"  다운로드: python3 scripts/download_model.py"
            )
        self._itp = tflite.Interpreter(
            model_path=str(self.model_path),
            num_threads=self.threads,
        )
        self._itp.allocate_tensors()
        self._in_d = self._itp.get_input_details()[0]
        self._out_d = self._itp.get_output_details()[0]
        # 양자화 파라미터
        qp_in = self._in_d.get("quantization_parameters", {})
        if qp_in.get("scales") is not None and len(qp_in["scales"]) > 0:
            self._in_scale = float(qp_in["scales"][0])
            self._in_zp = int(qp_in["zero_points"][0])
        else:
            self._in_scale, self._in_zp = self._in_d.get("quantization", (1.0, 0))
        qp_out = self._out_d.get("quantization_parameters", {})
        if qp_out.get("scales") is not None and len(qp_out["scales"]) > 0:
            self._out_scale = float(qp_out["scales"][0])
            self._out_zp = int(qp_out["zero_points"][0])
        else:
            self._out_scale, self._out_zp = self._out_d.get("quantization", (1.0, 0))

    # === 마이크 콜백 ===

    def _audio_cb(self, indata, frames, time_info, status):
        if status:
            # 오버런/언더런 무시 (로그만)
            pass
        pcm = indata[:, 0].astype(np.float32)  # mono

        # 필요 시 리샘플 (native != preset.sample_rate)
        if self._resample_up != self._resample_down:
            if _HAS_RESAMPLE:
                pcm = resample_poly(pcm, self._resample_up, self._resample_down).astype(np.float32)
            else:
                # numpy 스트라이드 폴백 (정수 배수 downsample 만)
                stride = self._resample_down // max(self._resample_up, 1)
                if stride > 1:
                    pcm = pcm[::stride].astype(np.float32)

        with self._ring_lock:
            n = len(pcm)
            end = self._ring_write + n
            if end <= self._ring_size:
                self._ring[self._ring_write:end] = pcm
            else:
                first = self._ring_size - self._ring_write
                self._ring[self._ring_write:] = pcm[:first]
                self._ring[:n - first] = pcm[first:]
            self._ring_write = end % self._ring_size
            self._filled += n

    def _grab_last_1s(self) -> np.ndarray:
        """가장 최근 1초 (16000 samples) 을 ring buffer 에서 복사."""
        clip_samples = self.preset.clip_samples
        with self._ring_lock:
            if self._filled < clip_samples:
                # 아직 1초 데이터 없음
                return np.zeros(clip_samples, dtype=np.float32)
            start = (self._ring_write - clip_samples) % self._ring_size
            end = self._ring_write
            if start < end:
                return self._ring[start:end].copy()
            else:
                return np.concatenate([self._ring[start:], self._ring[:end]]).copy()

    # === 추론 루프 ===

    def _infer_once(self) -> tuple[Optional[str], float, float]:
        """한 번의 KWS invoke. 반환 (label, confidence, invoke_ms)."""
        pcm = self._grab_last_1s()
        # int16 스케일로 변환 (frontend 는 int16/float32 둘 다 처리)
        pcm_i16 = np.clip(pcm * 32768.0, -32768, 32767).astype(np.int16)

        feats_f32 = compute_features(pcm_i16, self.preset)

        # 양자화 (int8)
        if self._in_d["dtype"] == np.int8:
            tensor = quantize_to_int8(feats_f32, self._in_scale, self._in_zp)
        elif self._in_d["dtype"] == np.uint8:
            # scale/zp based uint8 quant
            q = np.round(feats_f32 / self._in_scale + self._in_zp).astype(np.int32)
            tensor = np.clip(q, 0, 255).astype(np.uint8)
        else:
            tensor = feats_f32.astype(np.float32)

        # shape 강제 정합
        tensor = tensor.reshape(self._in_d["shape"])

        t0 = time.perf_counter()
        self._itp.set_tensor(self._in_d["index"], tensor)
        self._itp.invoke()
        raw = self._itp.get_tensor(self._out_d["index"])
        invoke_ms = (time.perf_counter() - t0) * 1000.0

        # 후처리
        if self._out_d["dtype"] == np.int8:
            logits = dequantize_from_int8(raw.flatten(), self._out_scale, self._out_zp)
        elif self._out_d["dtype"] == np.uint8:
            logits = (raw.flatten().astype(np.float32) - self._out_zp) * self._out_scale
        else:
            logits = raw.flatten().astype(np.float32)

        probs = _softmax(logits)
        top = int(np.argmax(probs))
        label = self.labels[top] if 0 <= top < len(self.labels) else str(top)
        return label, float(probs[top]), invoke_ms

    def _loop(self):
        hop_s = self.hop_ms / 1000.0
        while not self._stop_evt.is_set():
            t_iter = time.perf_counter()
            try:
                label, conf, invoke_ms = self._infer_once()
            except Exception as e:
                print(f"[kws_worker] invoke error: {e}")
                time.sleep(hop_s)
                continue

            self.stats["invocations"] += 1
            self.stats["last_label"] = label
            self.stats["last_confidence"] = conf
            self.stats["last_invoke_ms"] = invoke_ms

            # 필터
            if label in ("_silence_", "silence"):
                self.stats["silence_count"] += 1
            elif label in ("_unknown_", "unknown"):
                self.stats["unknown_count"] += 1
            elif conf < self.confidence_threshold:
                self.stats["sub_threshold_count"] += 1
            else:
                # 매핑 → ModeBus push
                target_mode = self.push_map.get(label, None)
                # target_mode 가 None 이어도 push (Yes/Go 같은 신호)
                if label in self.push_map:
                    ok = self.bus.push(
                        source="kws",
                        label=label,
                        target_mode=target_mode,
                        confidence=conf,
                    )
                    if ok:
                        self.stats["detections"] += 1

            elapsed = time.perf_counter() - t_iter
            if elapsed < hop_s:
                time.sleep(hop_s - elapsed)

    # === 외부 API ===

    def _resolve_sample_rate(self) -> int:
        """마이크 native rate 결정 — preset rate 먼저 시도, 실패 시 device default 사용."""
        target = self.preset.sample_rate

        # 1) target rate 직접 시도 (sd.check_input_settings 는 예외 던짐)
        try:
            sd.check_input_settings(
                device=self.input_device,
                samplerate=target,
                channels=1,
                dtype="float32",
            )
            return target
        except Exception:
            pass

        # 2) device 의 default_samplerate 사용
        info = sd.query_devices(self.input_device, "input")
        native = int(info.get("default_samplerate", 48000))
        return native

    def start(self):
        """마이크 open + 추론 스레드 start."""
        if self._thread is not None:
            return
        self._load_model()
        if not _HAS_SD:
            raise RuntimeError(
                "sounddevice not available. "
                "sudo apt install libportaudio2 && pip install sounddevice"
            )

        native_rate = self._resolve_sample_rate()
        self._native_rate = native_rate
        target_rate = self.preset.sample_rate

        # 리샘플 비율 (up/down)
        if native_rate != target_rate:
            frac = Fraction(target_rate, native_rate).limit_denominator(1000)
            self._resample_up = frac.numerator
            self._resample_down = frac.denominator
            print(
                f"[kws_worker] mic native rate {native_rate} Hz → "
                f"resample to {target_rate} Hz (up={self._resample_up}, down={self._resample_down}, "
                f"{'scipy' if _HAS_RESAMPLE else 'numpy stride fallback'})"
            )
        else:
            self._resample_up = 1
            self._resample_down = 1

        # blocksize 는 native rate 기준으로 계산 (200ms 만큼)
        blocksize = int(native_rate * self.hop_ms / 1000)

        self._stream = sd.InputStream(
            samplerate=native_rate,
            channels=1,
            dtype="float32",
            device=self.input_device,
            blocksize=blocksize,
            callback=self._audio_cb,
        )
        self._stream.start()
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="kws-worker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def snapshot(self) -> dict:
        return {
            "runtime": self.runtime,
            "preset": self.preset.name,
            "model": self.model_path.name,
            "labels": self.labels,
            "threads": self.threads,
            "confidence_threshold": self.confidence_threshold,
            "hop_ms": self.hop_ms,
            "native_sample_rate": self._native_rate,
            "resample": f"{self._resample_up}/{self._resample_down}",
            "stats": dict(self.stats),
        }


# === CLI 자기검증 ===

def _self_test():
    """모델 파일 있으면 마이크 열지 않고 invoke 1회 (dummy PCM)."""
    import os, sys

    model = os.environ.get(
        "KWS_MODEL",
        "kws/models/kws_ref_model_ds_cnn_int8.tflite",
    )
    labels = os.environ.get(
        "KWS_LABELS",
        "kws/scripts/labels_12.txt",
    )
    preset = os.environ.get("KWS_PRESET", "ds_cnn")

    if not Path(model).exists():
        print(f"[skip] model missing: {model}")
        return

    bus = ModeBus(initial=Mode.IDLE)
    w = KWSWorker(
        model_path=model,
        labels_path=labels,
        preset_name=preset,
        bus=bus,
        threads=1,
        confidence_threshold=0.5,
    )
    w._load_model()
    print(f"loaded: {w.model_path.name}")
    print(f"input:  shape={w._in_d['shape']} dtype={w._in_d['dtype'].__name__}")
    print(f"output: shape={w._out_d['shape']} dtype={w._out_d['dtype'].__name__}")
    # dummy 1초 zeros PCM 으로 1회 invoke
    with w._ring_lock:
        w._filled = w.preset.clip_samples
    label, conf, ms = w._infer_once()
    print(f"invoke (zeros): label={label}  conf={conf:.3f}  latency={ms:.1f}ms")


if __name__ == "__main__":
    _self_test()
