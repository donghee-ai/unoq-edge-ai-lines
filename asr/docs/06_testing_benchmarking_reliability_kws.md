# Testing, Benchmarking, Reliability — KWS

KWS(Keyword Spotting) 모듈의 테스트·벤치마크·신뢰성 표준을 정리합니다. vision의 `06_testing_benchmarking_reliability` 양식 그대로 + audio 도메인 특화(golden wav set, mic disconnect, false trigger 검증, soak test 시 voice activity).

## 1. 테스트 피라미드

```text
Unit tests
- preprocess dtype/shape (PCM int16 / float32 / int8 변환)
- feature extraction (MFCC 파라미터 = 모델 학습 시점과 일치)
- postprocess softmax / top-1 / threshold / N-frame confirm
- config parsing
- trigger filter (deque 윈도잉 로직)

Model tests
- TFLite load (allocate_tensors)
- input/output metadata (shape, dtype, quantization)
- input_kind 분류 (raw_pcm vs feature_2d)
- golden wav 기대 라벨
- host ↔ device feature consistency (같은 wav에서 추출한 feature 일치)

Device tests
- mic open/reconnect (USB unplug/replug)
- inference latency (50회 + p50/p95)
- memory/temperature (max RSS / max temp)
- venv-unoq import (sounddevice + scipy + python_speech_features)
- PortAudio system 라이브러리 (libportaudio2)

System tests
- end-to-end scenario (실시간 마이크 → 라벨 → MCU 트리거)
- actuator safety (false trigger 시 MCU safe state)
- ambient noise (조용한 방 vs 일반 방 vs 시끄러운 방)
- long-duration soak (8시간+ 연속 운영)
- speaker variation (본인 / 다른 화자 / 거리 1m/2m/3m)
```

## 2. Golden wav test

각 모델 버전마다 20~100개의 representative wav를 고정하고 다음을 기록합니다.

```yaml
wav: golden/yes_001.wav
expected:
  label: yes
  min_confidence: 0.70
  speaker: self_clean      # self_clean / self_noisy / other_clean
  distance_m: 0.5
  sample_rate: 16000
  duration_s: 1.0
notes: |
  표준 발화. 마이크 정면 50cm.
```

합격 기준은 use case별로 다르게 설정합니다. 본 작품 1차 PoC = 본인 발화 + 조용한 책상 환경 + N단어 한정. 노이즈 / 거리 / 다른 화자는 별도 단계.

### 2-1. Golden wav 셋업 절차

```bash
# 호스트 컨테이너 안에서 본인 발화 녹음
python -c "
import sounddevice as sd, scipy.io.wavfile as wav
import numpy as np
for word in ['yes', 'no', 'stop', 'go', 'up', 'down', 'left', 'right']:
    input(f'press enter then say: {word}')
    audio = sd.rec(16000, samplerate=16000, channels=1, dtype='float32', blocking=True)
    wav.write(f'data/golden/{word}_001.wav', 16000, (audio * 32767).astype(np.int16))
    print(f'saved: {word}_001.wav')
"
```

각 단어 5~10회 반복 녹음 (다양한 톤·억양). 라벨 + 메타데이터 yaml 동봉.

### 2-2. Golden 결과 평가

```python
# tests/test_golden.py
import yaml, glob
from src.postprocess import decode_kws

passed, failed = 0, 0
for meta_file in glob.glob('data/golden/*.yaml'):
    meta = yaml.safe_load(open(meta_file))
    pcm = load_wav(meta['wav'])
    x = preprocess(pcm, input_detail)
    interpreter.set_tensor(idx, x)
    interpreter.invoke()
    label, conf = decode_kws(interpreter.get_tensor(out_idx), labels)
    if label == meta['expected']['label'] and conf >= meta['expected']['min_confidence']:
        passed += 1
    else:
        failed += 1
        print(f'FAIL {meta["wav"]}: got ({label}, {conf:.2f}), expected ({meta["expected"]["label"]}, ≥{meta["expected"]["min_confidence"]})')

print(f'accuracy: {passed}/{passed+failed} = {100*passed/(passed+failed):.1f}%')
```

## 3. Benchmark command

```bash
python3 src/benchmark_kws.py \
  --model /opt/unoq-yolo/models/speech_commands_v2.tflite \
  --labels /opt/unoq-yolo/labels/labels_35.txt \
  --input /opt/unoq-yolo/media/yes_001.wav \
  --benchmark-runs 100 --warmup 10 \
  --runtime cpu \
  --json-report ~/benchmarks/device_kws_$(date +%Y%m%d).json
```

Benchmark report 예시 (벤치마크 표준 권고 JSON 형식 그대로 + audio 확장):

```json
{
  "model": "speech_commands_v2.tflite",
  "runtime": "cpu:4",
  "input_shape": [1, 16000],
  "input_kind": "raw_pcm",
  "feature_extractor": "model_internal",
  "frames": 100,
  "latency_ms_p50": 32.5,
  "latency_ms_p95": 48.7,
  "fps_mean": 30.8,
  "capture_ms_mean": 0.0,
  "preprocess_ms_mean": 0.5,
  "postprocess_ms_mean": 0.3,
  "dropped_frames": 0,
  "max_rss_mb": 65,
  "max_temp_c": 58.2,
  "accuracy_top1_golden": 0.92,
  "false_positive_rate_silence": 0.01
}
```

audio 확장 필드:
- `input_kind`: raw_pcm / feature_2d
- `feature_extractor`: model_internal / python_speech_features / numpy_custom / librosa
- `capture_ms_mean`: 마이크 캡처 평균 (실시간 측정 시)
- `accuracy_top1_golden`: 골든 wav 셋 top-1 정확도
- `false_positive_rate_silence`: 무음 입력에 trigger 발동 비율 (0이 이상적)

## 4. Soak test

KWS 도메인 특화 최소 기준:

- **8시간 연속 mic capture + KWS inference** (실시간 무한 루프).
- USB hub power 안정성 확인 (vision 카메라와 마이크 동시 USB 연결).
- 로그 파일 크기 제한 확인 (1초당 1줄 JSON → 8h ≈ 29k 줄).
- memory RSS 증가율 확인 (leak 검출).
- mic unplug/replug 10회 (각 회 30초 후 자동 복구).
- 네트워크 끊김/복구 (logging이 네트워크 의존이면).
- App restart 후 자동 복구.
- 장치 reboot 후 자동 복구.
- **무음 입력 시 false trigger rate** ≤ 1/hour.
- **다양한 ambient (조용 / 일반 / 음악 / 대화 배경)에서 정확도 유지** 검증.

### 4-1. Soak test 실행

```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
  nohup python3 ~/infer_mic.py \
    /opt/unoq-yolo/models/speech_commands_v2.tflite \
    --max-frames 0 \
    --json ~/benchmarks/soak_kws_$(date +%Y%m%d).json \
    --log-every 600 \
    > ~/logs/soak_$(date +%Y%m%d).log 2>&1 &'

# 8시간 후 확인
ssh arduino@192.168.0.45 'tail -20 ~/logs/soak_*.log && \
  cat ~/benchmarks/soak_kws_*.json | python3 -m json.tool'
```

## 5. Watchdog policy

vision 패턴 그대로 + audio 특화 항목:

```text
AI process heartbeat interval: 1 s
No heartbeat for 5 s: restart AI process
No mic frame for 10 s: reinitialize mic (modprobe -r/+ snd_usb_audio)
Repeated failures > 3: safe mode
Safe mode: stop actuator (MCU에 safe state 메시지), show LED/error status, keep logs

KWS 특화:
- 연속 N분 (예: 30분) trigger 0회 + ambient sound 정상 → "잠든 상태" 의심 → smoke wav 자체 테스트 (golden wav 1개로 invoke → 라벨 일치 확인)
- 연속 N회 (예: 10회/분) trigger 발동 → "false trigger storm" 의심 → threshold 일시 상향
```

## 6. 성능 최적화 순서

KWS는 vision보다 가벼우므로 1순위가 다름:

1. **입력 형태 확인** (raw PCM vs 사전 MFCC) — raw PCM 모델이 디바이스 부담 작음 (feature 추출 비용 0)
2. **feature 추출 라이브러리 교체** (librosa numba JIT → python_speech_features 또는 자작 numpy → ~10x 빠름)
3. 모델 축소 (Speech Commands v2 → TFLite Micro KWS 예제 <100 KB)
4. inference 주기 제한 (실시간 sliding window hop 0.5s → 1.0s — false trigger 감소 + CPU 감소)
5. VAD (Voice Activity Detection) 추가 — 무음 구간 inference 스킵 (CPU + thermal 절감)
6. ROI 같은 효과 — sliding window를 voice activity 트리거 이후로 제한
7. postprocess vectorization (softmax 자작 vs np.exp 표준)
8. thread count sweep: 1, 2, 4 (Cortex-A53 4코어 — 보통 4가 최적, 그러나 1으로도 충분할 수 있음)
9. GPU delegate 실측 (`/dev/kgsl*` 존재 + delegate 로드 성공 시 1회 벤치)
10. 상위 SoC 검토 (KWS는 보통 불필요 — vision보다 가벼움)

## 7. 비교 — vision vs audio 합격선

| 기준 | vision (YOLOv8n int8 320×320) | audio (Speech Commands v2 KWS) |
|---|---|---|
| Latency mean | ≤ ~125 ms (8 FPS 기준) | ≤ 50 ms |
| Latency p95 | ≤ ~165 ms (6 FPS 기준) | ≤ 80 ms |
| Max RSS | ≪ 가용 2.4 GB | < 100 MB |
| Max temp | ≤ 70°C | ≤ 70°C (vision과 공유) |
| Accuracy 기준 (참고) | bbox IoU ≥ 0.40 (리뷰어 §2 권고) | top-1 ≥ 80% (golden wav) |
| 합격선 | 4기준 (실측 9.23 FPS / 132 ms p95 / 100 MB / 60.5°C 통과) | 4기준 + 참고 accuracy |

audio가 더 가볍지만 thermal은 vision과 공유 (한 SoC) — vision + audio 동시 실행 시 thermal 검증 필수 (vision 단독 285초에 70.8°C 도달했으므로).

## 8. 동시 실행 (vision + audio) 테스트 추가

본 작품 = 교감로봇 = vision + audio 동시 운영이 핵심. 별도 항목으로 검증:

| 항목 | 단독 운영 합격 | 동시 운영 검증 |
|---|---|---|
| vision FPS | 9.23 (단독) | ≥ 7 (동시) — 33% 여유 |
| audio latency | < 50 ms (단독) | < 80 ms (동시) |
| max temp | 70.8°C (vision 285s) | thermal soak 필요 |
| max RSS | 100 MB (vision) + ~70 MB (audio) | 합 ~170 MB, 가용 2.4 GB의 7% |
| 두 프로세스 IPC | (없음 — 단독) | shared memory / socket / pipe — 측정 필요 |
| MCU 트리거 우선순위 | — | vision detection + audio trigger 동시 시 어느 쪽 우선? |

→ **fusion 단계에서 별도 docs (`docs/fusion/*.md`)**.

## 9. 측정 결과 보관

본 작품 표준 워크플로우:

```bash
# 디바이스 측 저장
mkdir -p ~/benchmarks
python3 ~/benchmark_kws.py ... --json ~/benchmarks/device_kws_<MODEL>_<YYYYMMDD>.json

# 호스트 회수
mkdir -p benchmarks/audio
scp arduino@192.168.0.45:~/benchmarks/device_kws_*.json benchmarks/audio/

# 호스트 baseline
python3 src/benchmark_kws.py ... --json benchmarks/audio/host_kws_<MODEL>_<YYYYMMDD>.json
```

JSON 파일명 규칙: `<host|device>_kws_<model_short>_<YYYYMMDD>.json` (vision의 `host_e2e_*.json` / `device_e2e_*.json` 패턴 일관).

## 10. 보고 시 1줄 핵심 (예시)

> **Arduino UNO Q (QRB2210) 위에서 Speech Commands v2 KWS (raw_pcm 16 kHz, ai_edge_litert + XNNPACK 4 thread) end-to-end ~X ms, p95 latency ~Y ms, 최대 메모리 ~Z MB, 최대 온도 ~T°C, 골든 wav 정확도 ~A% 실측 — 본 작품 합격선(50 ms / 80 ms p95 / <100 MB / ≤70°C / ≥80% accuracy) 통과.**

vision 보고 한 줄("YOLOv8n int8 320×320 ... e2e 9.23 FPS, p95 latency 132 ms, ...") 패턴과 정확히 같은 형식.

## 11. 알려진 한계 (1차 PoC 단계)

| 한계 | 영향 | 향후 대응 |
|---|---|---|
| 본인 발화만 측정 (single speaker) | 다른 화자 정확도 미검증 | Prototype 단계 (4~6주) 화자 다양화 |
| 조용한 책상 환경만 | 노이즈 환경 미검증 | ambient sound 시나리오 셋 |
| 영어 35단어만 | 한국어 명령 불가 | transfer learning fine-tune (2차 보강) |
| 단발 측정 (≤ 11초 single 또는 100회 ~5초) | 장기 thermal / leak 미검증 | soak test 8h+ (본 문서 §4) |
| dropped_frames = 0 (단일 wav 반복) | 카메라 라인의 vision 패턴과 동일 한계 | 실시간 마이크 측정으로 진짜 측정 |
| GPU delegate 미시도 | CPU 충분 예상 | `/dev/kgsl*` 점검 후 1회 벤치 |
| vision 동시 실행 thermal 미검증 | vision 단독 70.8°C 도달 | fusion 단계 soak test 필수 |
| MCU 트리거 검증 미실시 | 트리거 → 실 동작 연결 안 됨 | fusion 단계 (vision + audio + MCU) |

## 한 줄 요약

> **테스트 피라미드 4층 + golden wav 셋 + 벤치마크 표준 JSON 형식(audio 확장 5필드) + 8h soak + watchdog + 성능 최적화 10단계 + vision 동시 운영 검증 — vision 라인 testing 표준 그대로, audio 도메인 특화 항목(false trigger / mic reconnect / VAD) 보강.**
