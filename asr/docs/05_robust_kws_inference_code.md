# Robust KWS TFLite Inference Code Pattern

KWS(Keyword Spotting) 모델을 commercial product 수준으로 추론할 때 필요한 코드 패턴을 정리합니다. vision의 `04_robust_tflite_inference_code` 양식을 그대로 따르되, audio 도메인 특화 항목(feature 추출 일치, ring buffer, false trigger 억제)을 추가합니다.

기본 패턴이 보강해야 할 항목:
- dtype별 입력 변환 (PCM int16 / float32, MFCC int8 / float32).
- quantization parameter 검사.
- GPU delegate optional 로드와 CPU fallback.
- latency p50/p95 + 단계별(capture / preprocess / inference / postprocess) 분리 기록.
- raw output shape에 따른 후처리 분기 (logit / softmax / topk 포함 여부).
- feature 추출 파이프라인이 학습 파이프라인과 일치하는지 검증.
- 오류 발생 시 exit code와 로그.

## 1. 모델 introspection script

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        Interpreter = tflite.Interpreter
    except ImportError:
        import tensorflow.lite as tflite
        Interpreter = tflite.Interpreter


def clean_value(v):
    if hasattr(v, 'tolist'):
        return v.tolist()
    if hasattr(v, '__name__'):
        return v.__name__
    return v


def clean_detail(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = {kk: clean_value(vv) for kk, vv in v.items()}
        else:
            out[k] = clean_value(v)
    return out


def classify_input(shape, dtype):
    """KWS 입력 형태 분류 — frontend 위치 결정용."""
    rank = len(shape)
    if rank == 2 and shape[1] >= 8000:
        return 'raw_pcm', f'frontend 모델 내장. 디바이스에 feature 라이브러리 불필요. shape={list(shape)} dtype={dtype.__name__}'
    if rank in (3, 4):
        return 'feature_2d', f'외부 MFCC/log-Mel 사전 변환 필요. shape={list(shape)} — 학습 파이프라인 파라미터 정확히 복제 필수.'
    return 'unknown', f'알 수 없는 입력 형식. shape={list(shape)} 모델 카드 재확인.'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('--json-out', default=None)
    args = ap.parse_args()

    if not Path(args.model).exists():
        raise FileNotFoundError(args.model)

    interpreter = Interpreter(model_path=args.model, num_threads=4)
    interpreter.allocate_tensors()

    in_details = interpreter.get_input_details()
    out_details = interpreter.get_output_details()

    report = {
        'model': args.model,
        'inputs': [clean_detail(d) for d in in_details],
        'outputs': [clean_detail(d) for d in out_details],
    }

    # KWS 도메인 특화 분류
    in_shape = in_details[0]['shape']
    in_dtype = in_details[0]['dtype']
    kind, hint = classify_input(in_shape, in_dtype)
    report['input_kind'] = kind
    report['input_hint'] = hint
    report['num_classes'] = int(out_details[0]['shape'][-1])

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
```

## 2. dtype-safe audio preprocessing

```python
import numpy as np
import sounddevice as sd


def capture_pcm_1s(samplerate=16000, channels=1, dtype='float32'):
    """USB UVC Audio Class 마이크에서 1초 PCM 캡처."""
    audio = sd.rec(
        int(samplerate * 1.0),
        samplerate=samplerate,
        channels=channels,
        dtype=dtype,
        blocking=True,
    )
    return audio.flatten()  # (samplerate,)


def normalize_pcm(pcm, target_dtype):
    """PCM 정규화 — 모델 input dtype에 맞춰 변환."""
    if target_dtype == np.float32:
        # 보통 [-1.0, 1.0] float32 가정
        if pcm.dtype == np.int16:
            return pcm.astype(np.float32) / 32768.0
        if pcm.dtype == np.float32:
            return np.clip(pcm, -1.0, 1.0)
        if pcm.dtype == np.int8:
            return pcm.astype(np.float32) / 128.0
        raise TypeError(f'unsupported source dtype: {pcm.dtype}')

    if target_dtype == np.int16:
        if pcm.dtype == np.float32:
            return (np.clip(pcm, -1.0, 1.0) * 32767.0).astype(np.int16)
        return pcm.astype(np.int16)

    if target_dtype == np.int8:
        # 모델 양자화 입력 — 보통 [-128, 127] int8
        if pcm.dtype == np.float32:
            return (np.clip(pcm, -1.0, 1.0) * 127.0).astype(np.int8)
        return pcm.astype(np.int8)

    raise TypeError(f'unsupported target dtype: {target_dtype}')


def prepare_input_for_model(pcm_1s, input_detail):
    """모델 input shape에 맞춰 raw PCM 또는 feature 추출."""
    shape = input_detail['shape']
    dtype = input_detail['dtype']
    rank = len(shape)

    if rank == 2 and shape[1] >= 8000:
        # raw PCM — 정규화만
        x = normalize_pcm(pcm_1s, dtype)
        return np.expand_dims(x, axis=0)  # (1, samplerate)

    if rank in (3, 4):
        # MFCC 또는 log-Mel 사전 변환 필요
        # 학습 시 파라미터와 정확히 일치해야 함 — 모델 카드 확인
        from python_speech_features import logfbank
        # 예시 파라미터 (모델별 다름!)
        feat = logfbank(
            pcm_1s,
            samplerate=16000,
            winlen=0.025,    # 25 ms
            winstep=0.010,   # 10 ms hop
            nfilt=40,        # 40 Mel filters
            nfft=512,
        )
        feat = feat.astype(np.float32)
        if rank == 4:
            feat = feat[..., np.newaxis]  # (frames, mel, 1)
        x = normalize_pcm(feat.reshape(-1), dtype).reshape(feat.shape)
        return np.expand_dims(x, axis=0)

    raise ValueError(f'unsupported input shape: {shape}')
```

핵심: **모델 input shape에 따라 raw PCM 경로 / MFCC 경로 분기**. MFCC 파라미터(winlen, winstep, nfilt, nfft)는 모델 카드에서 학습 시 사용한 값 정확히 복제 — 멘토 리뷰 단점 2 직접 대응.

## 3. Safe interpreter loader

```python
try:
    from ai_edge_litert.interpreter import Interpreter, load_delegate
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        Interpreter = tflite.Interpreter
        load_delegate = tflite.load_delegate
    except ImportError:
        import tensorflow.lite as tflite
        Interpreter = tflite.Interpreter
        load_delegate = tflite.load_delegate


def load_interpreter(model_path, num_threads=4, enable_gpu=False):
    """GPU optional + CPU fallback. silent fail 금지."""
    if enable_gpu:
        for delegate_name in ['libtensorflowlite_gpu_delegate.so', 'libdelegate_gpu.so']:
            try:
                delegate = load_delegate(delegate_name)
                interpreter = Interpreter(
                    model_path=model_path,
                    experimental_delegates=[delegate],
                )
                return interpreter, f'gpu:{delegate_name}'
            except Exception as e:
                # 명시적 fallback (silent X)
                print(f'[WARN] GPU delegate failed ({delegate_name}): {e}')

    interpreter = Interpreter(model_path=model_path, num_threads=num_threads)
    return interpreter, f'cpu:{num_threads}'
```

원칙: CPU가 기본 — GPU는 명시적 opt-in. UNO Q는 `/dev/kgsl*` 부재로 GPU delegate 실패 가능성 큼 → fail-safe fallback.

## 4. Benchmark helper (단계별)

```python
import statistics
import time


def benchmark_kws(interpreter, input_detail, input_tensor, runs=50, warmup=5):
    """순수 inference latency."""
    for _ in range(warmup):
        interpreter.set_tensor(input_detail['index'], input_tensor)
        interpreter.invoke()

    values = []
    for _ in range(runs):
        start = time.perf_counter()
        interpreter.set_tensor(input_detail['index'], input_tensor)
        interpreter.invoke()
        values.append((time.perf_counter() - start) * 1000.0)

    values_sorted = sorted(values)
    p95 = values_sorted[int(0.95 * (len(values_sorted) - 1))]
    return {
        'runs': runs,
        'latency_ms_mean': statistics.mean(values),
        'latency_ms_p50': statistics.median(values),
        'latency_ms_p95': p95,
        'fps_mean': 1000.0 / statistics.mean(values),
    }


def benchmark_e2e_audio(
    interpreter, input_detail, output_detail,
    capture_fn, preprocess_fn, postprocess_fn,
    runs=50, warmup=5,
):
    """단계별 분리 측정 — capture / preprocess / inference / postprocess."""
    stages = {k: [] for k in ('capture', 'preprocess', 'inference', 'postprocess', 'total')}

    for _ in range(warmup):
        pcm = capture_fn()
        x = preprocess_fn(pcm, input_detail)
        interpreter.set_tensor(input_detail['index'], x)
        interpreter.invoke()
        _ = postprocess_fn(interpreter.get_tensor(output_detail['index']))

    for _ in range(runs):
        t0 = time.perf_counter()
        pcm = capture_fn()
        t1 = time.perf_counter()
        x = preprocess_fn(pcm, input_detail)
        t2 = time.perf_counter()
        interpreter.set_tensor(input_detail['index'], x)
        interpreter.invoke()
        t3 = time.perf_counter()
        _ = postprocess_fn(interpreter.get_tensor(output_detail['index']))
        t4 = time.perf_counter()

        stages['capture'].append((t1 - t0) * 1000)
        stages['preprocess'].append((t2 - t1) * 1000)
        stages['inference'].append((t3 - t2) * 1000)
        stages['postprocess'].append((t4 - t3) * 1000)
        stages['total'].append((t4 - t0) * 1000)

    return {k: _stats(v) for k, v in stages.items()}


def _stats(values):
    s = sorted(values)
    return {
        'mean': statistics.mean(values),
        'p50': statistics.median(values),
        'p95': s[int(0.95 * (len(s) - 1))],
        'min': min(values),
        'max': max(values),
    }
```

vision의 `benchmark_e2e.py` 단계 분리 패턴 그대로. capture(마이크) / preprocess(MFCC) / inference / postprocess(softmax + top-1)로 분리하여 병목 식별 용이.

## 5. KWS 후처리 주의

KWS TFLite output shape는 export 경로와 frontend 포함 여부에 따라 달라집니다. 아래를 먼저 기록하고, 그 shape에 맞춰 decoder를 선택합니다.

```python
output_details = interpreter.get_output_details()
for i, d in enumerate(output_details):
    print(i, d['name'], d['shape'], d['dtype'], d.get('quantization'))
```

일반적으로 필요한 후처리 단계:

```text
raw_output
 -> dequantize if needed (int8 → float32)
 -> reshape (보통 [1, N] 또는 [N])
 -> softmax (logit인 경우)
 -> top-1 class index
 -> confidence threshold (기본 0.7)
 -> 연속 N-frame confirm (false trigger 억제)
 -> class ID → label mapping
```

### 5-1. Softmax + Top-1

```python
import numpy as np


def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


def decode_kws(raw_output, labels, threshold=0.7):
    """raw output → (label, confidence) 또는 (None, confidence)."""
    logits = raw_output[0]  # shape (N,)
    probs = softmax(logits) if logits.max() > 1.0 else logits  # 이미 softmax면 그대로
    top_idx = int(np.argmax(probs))
    top_conf = float(probs[top_idx])
    if top_conf < threshold:
        return None, top_conf
    return labels[top_idx], top_conf
```

모델이 이미 softmax를 내장하면 `softmax` 호출 생략 — output 합이 1.0 근처인지로 자동 판단.

### 5-2. False trigger 억제 — N-frame confirm

```python
from collections import deque


class TriggerFilter:
    """연속 N 프레임에서 같은 라벨이 threshold 이상이어야 trigger."""
    def __init__(self, n_consecutive=3, threshold=0.7):
        self.n = n_consecutive
        self.thr = threshold
        self.history = deque(maxlen=n_consecutive)

    def update(self, label, conf):
        self.history.append((label, conf))
        if len(self.history) < self.n:
            return None
        labels = [h[0] for h in self.history]
        confs = [h[1] for h in self.history]
        if labels[0] is None:
            return None
        if all(l == labels[0] for l in labels) and all(c >= self.thr for c in confs):
            return labels[0]
        return None
```

KWS의 진짜 어려운 부분 = false trigger 억제. 단발 confidence는 노이즈에 흔들리므로 연속 N프레임 동의 패턴이 표준.

### 5-3. Feature 일치 검증 (호스트 ↔ 디바이스)

```python
def verify_feature_consistency(host_feature, device_feature, atol=1e-3):
    """같은 wav에서 추출한 feature가 두 환경에서 일치하는지."""
    import numpy as np
    if host_feature.shape != device_feature.shape:
        return False, f'shape mismatch: {host_feature.shape} vs {device_feature.shape}'
    diff = np.abs(host_feature - device_feature).max()
    if diff > atol:
        return False, f'max diff {diff:.6f} > atol {atol}'
    return True, f'OK (max diff {diff:.6f})'
```

Golden wav 1개로 호스트(librosa 또는 본인 자작) ↔ 디바이스(python_speech_features 또는 자작) feature를 비교 — 멘토 리뷰 단점 2 게이트화.

## 6. Production logging fields

```json
{
  "timestamp_ms": 0,
  "model_version": "speech_commands_v2_int8",
  "runtime": "cpu:4",
  "input_shape": [1, 16000],
  "input_dtype": "float32",
  "input_kind": "raw_pcm",
  "feature_extractor": "model_internal",
  "feature_params": null,
  "capture_ms": 0.0,
  "preprocess_ms": 0.0,
  "latency_ms": 0.0,
  "postprocess_ms": 0.0,
  "top1_label": null,
  "top1_confidence": 0.0,
  "trigger_fired": false,
  "trigger_consecutive_frames": 0,
  "dropped_frames": 0,
  "temperature_c": null,
  "mic_status": "ok",
  "error": null
}
```

vision 라인 logging fields에 audio 특화 추가: `capture_ms`, `input_kind`, `feature_extractor`, `feature_params`, `top1_label`, `top1_confidence`, `trigger_fired`, `trigger_consecutive_frames`, `mic_status`.

## 7. 모듈 분리 권고

본 패턴을 본 작품 `src/` 구조에 적용:

| 파일 | 역할 | 멘토 04 매핑 |
|---|---|---|
| `src/audio_io.py` | sounddevice 캡처 + ring buffer | §2 capture |
| `src/preprocess.py` | PCM 정규화 + MFCC/log-Mel | §2 preprocess |
| `src/runtime.py` | interpreter 로더 (3단 import + GPU fallback) | §3 |
| `src/postprocess.py` | softmax + top-1 + threshold + N-frame confirm | §5 |
| `src/validate_kws.py` | introspection + 50회 latency | §1 + §4 benchmark_kws |
| `src/benchmark_kws.py` | e2e 단계별 100회 + JSON | §4 benchmark_e2e_audio + §6 logging |
| `src/infer_mic.py` | 실시간 마이크 → KWS → 라벨 + trigger | §2 + §5 + 6 |
| `tests/feature_consistency.py` | 호스트 ↔ 디바이스 feature 검증 | §5-3 |

## 8. 본 패턴 vs vision 라인 차이

| 항목 | vision (yolo) | audio (kws) |
|---|---|---|
| 입력 | 이미지 (resize + BGR→RGB) | PCM (정규화 + 옵션 MFCC) |
| Frontend 위치 | 항상 외부 (cv2) | **모델 내장 vs 외부 분기** (input shape로 판별) |
| 후처리 | NMS + bbox scaling | softmax + top-1 + N-frame confirm |
| Cold start 함정 | cv2 drawing ~60 ms | sounddevice 첫 호출 + (옵션) librosa numba JIT — 둘 다 warmup 분리 |
| False positive 억제 | confidence threshold (단발) | confidence + 연속 프레임 confirm |
| 단계별 분리 측정 | preprocess/inference/postprocess/draw | capture/preprocess/inference/postprocess |

## 9. 코드 작성 순서 (본문 진입 시)

1. `src/runtime.py` — interpreter 3단 import + GPU fallback (가장 단순, 다른 모듈의 의존)
2. `src/audio_io.py` — sounddevice 캡처 + 디바이스 첫 마이크 점검
3. `src/preprocess.py` — 모델 input shape에 따라 raw PCM / MFCC 분기
4. `src/validate_kws.py` — introspection + 50회 latency 측정
5. `src/postprocess.py` — softmax + top-1 + threshold + N-frame confirm
6. `src/benchmark_kws.py` — e2e 단계별 100회 + 멘토 06 JSON
7. `src/infer_mic.py` — 실시간 루프 통합

각 모듈 작성 후 게이트 검증 (preflight §12·§13).

## 한 줄 요약

> **모델 introspection 자동화 + dtype/feature 추출 학습 일치 + 3단 import 폴백 + GPU optional + 단계별 분리 측정 + softmax/top-1/N-frame confirm + production logging — vision robust_code 양식 그대로, audio 도메인 특화 항목 보강.**
