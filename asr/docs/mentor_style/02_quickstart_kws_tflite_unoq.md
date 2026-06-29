# Uno Q KWS TFLite Quickstart

이 문서는 KWS(Keyword Spotting) TFLite 모델을 Arduino UNO Q에서 처음 실행하는 빠른 절차를 정리합니다. 기본 경로는 “TFLite 모델 + Python/sounddevice + CPU”입니다. 깊은 의사결정/측정/벤치는 본문 docs(`02_model_selection_log.md` 이후)에서 다룹니다.

## 0. 목표

- 입력: USB UVC Audio Class 마이크 또는 테스트 wav 파일.
- 추론: int8 또는 float32 TFLite KWS 모델 (1순위 Google Speech Commands v2).
- 출력: 35 클래스 중 top-1 라벨 + confidence, (옵션) MCU 트리거 메시지.
- 기본 런타임: CPU, 4 threads.
- optional 런타임: GPU delegate, 장치에서 `/dev/kgsl*` 노출 + 실측 검증된 경우에만 enable.
- feature 추출: 호스트는 librosa, 디바이스는 python_speech_features 또는 numpy 자작 (학습 파이프라인 파라미터 동일 필수).

## 1. 호스트 PC 준비

```bash
# WSL2 Ubuntu 24.04에서, asr-dev 별도 Docker 컨테이너 진입 후
cd /mnt/c/Project/unoq-companion-robot/asr
bash docker/run-asr.sh         # 작성 예정 — Dockerfile.asr + requirements-asr.lock 기반
```

컨테이너 안에서 (`asr-dev` 진입 직후) Smoke test:

```bash
python -c "import numpy, scipy, sounddevice, librosa, ai_edge_litert; \
  print('numpy', numpy.__version__); \
  print('scipy', scipy.__version__); \
  print('sounddevice', sounddevice.__version__); \
  print('librosa', librosa.__version__)"
```

TensorFlow 버전은 프로젝트 재현성을 위해 `docker/audio/requirements-asr.lock`에 byte-exact 고정합니다. vision의 `requirements.lock`(94 패키지)과 별도 관리.

## 2. 모델 준비 전략

### 권장 순서

1. 먼저 가장 작은 KWS 모델로 시작합니다: Google Speech Commands v2 TFLite (~300 KB int8).
2. 모델이 raw PCM 입력인지 / MFCC 사전 변환 입력인지 input shape로 확인합니다.
3. 학습 시 사용한 feature 추출 파라미터(sr / n_mel / hop / window / dtype)를 모델 카드에서 기록합니다. 이걸 디바이스 추론 시 정확히 복제합니다.
4. 모델 파일마다 input/output metadata를 자동 추출(§3)로 기록합니다.
5. 성능이 부족하면 모델을 더 줄이거나(TFLite Micro KWS 예제 <100 KB), confidence threshold + 연속 N-frame confirm으로 false trigger를 억제합니다.
6. 자유발화 한국어가 hard requirement라면 KWS가 아니라 Whisper Tiny int8 (MIT)로 전환합니다.

### Google Speech Commands v2 모델 획득 (옵션 A)

```bash
# 호스트 컨테이너 안에서
mkdir -p models/audio
# TF Hub 또는 Google AI Edge에서 직접 다운로드
# 정확한 URL은 모델 카드 확인 (Apache-2.0 라이선스 사본 동봉 보관)
wget -O models/audio/speech_commands_v2.tflite <MODEL_URL>
wget -O models/audio/labels_35.txt <LABELS_URL>
```

### TFLite 변환 직접 (옵션 B — 본 작품 1차에선 비권장)

학습된 KWS Keras/TF SavedModel이 있을 때:

```python
import tensorflow as tf

converter = tf.lite.TFLiteConverter.from_saved_model('kws_saved_model')
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# 대표 데이터셋 (실제 발화 wav 일부)
def representative_dataset():
    import numpy as np
    for i in range(200):
        # 16 kHz 1초 mono PCM
        yield [np.random.randn(1, 16000).astype(np.float32)]

converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8

tflite_model = converter.convert()
with open('models/audio/kws_int8_manual.tflite', 'wb') as f:
    f.write(tflite_model)
print('int8 KWS 모델 저장 완료')
```

## 3. 모델 검증

호스트 컨테이너 안에서 모델 metadata 자동 추출:

```bash
python3 - <<'PY'
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    import tensorflow.lite as tflite
    Interpreter = tflite.Interpreter

model_path = 'models/audio/speech_commands_v2.tflite'
interpreter = Interpreter(model_path=model_path, num_threads=4)
interpreter.allocate_tensors()
for kind, details in [('INPUTS', interpreter.get_input_details()), ('OUTPUTS', interpreter.get_output_details())]:
    print('\n' + kind)
    for d in details:
        print('name=', d.get('name'))
        print('index=', d.get('index'))
        print('shape=', d.get('shape'))
        print('dtype=', d.get('dtype'))
        print('quantization=', d.get('quantization'))
        print('quantization_parameters=', d.get('quantization_parameters'))
PY
```

확인 포인트:
- input shape이 `[1, 16000]`이면 **raw PCM 입력** — 모델 내부에 frontend 내장, 디바이스에 feature 추출 라이브러리 불필요 (가장 가벼움).
- input shape이 `[1, 49, 40, 1]` 또는 `[1, 40, 49]` 등이면 **MFCC/log-Mel 사전 변환 입력** — 학습 시 파라미터 정확히 복제 필요.
- dtype = `int8` / `float32` 분기 — preprocessor에서 변환 처리.
- output shape `[1, 35]` 또는 `[1, N]` — 클래스 수 확인.

## 4. 장치 준비

```bash
export UNO_Q_USER=arduino
export UNO_Q_HOST=192.168.0.45
export APP_ROOT=/opt/unoq-yolo                 # 현재 vision 명칭 — monorepo 통합 시 rename 검토

# 디렉토리 / venv는 vision 셋업으로 이미 준비됨
ssh ${UNO_Q_USER}@${UNO_Q_HOST} "ls ${APP_ROOT}/models && ls -d ~/venv-unoq"

# audio 의존성 추가 (1회) — librosa 절대 X, 가벼운 대안만
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'source ~/venv-unoq/bin/activate && \
  pip install sounddevice scipy python_speech_features'

# PortAudio 시스템 라이브러리 (sounddevice 의존)
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'sudo apt install -y libportaudio2 portaudio19-dev'

# 모델 전송
scp models/audio/speech_commands_v2.tflite ${UNO_Q_USER}@${UNO_Q_HOST}:${APP_ROOT}/models/
scp models/audio/labels_35.txt ${UNO_Q_USER}@${UNO_Q_HOST}:${APP_ROOT}/labels/
```

ADB 경로 (옵션):

```bash
adb devices
adb push models/audio/speech_commands_v2.tflite /tmp/
adb shell "sudo cp /tmp/speech_commands_v2.tflite /opt/unoq-yolo/models/"
```

## 5. 장치에서 Python runtime smoke test

```bash
ssh ${UNO_Q_USER}@${UNO_Q_HOST}
source ~/venv-unoq/bin/activate
python3 - <<'PY'
try:
    from ai_edge_litert.interpreter import Interpreter
    print('ai-edge-litert OK')
except Exception as e:
    print('ai-edge-litert not available:', e)
try:
    import sounddevice as sd
    print('sounddevice OK, devices:', sd.query_devices())
except Exception as e:
    print('sounddevice not available:', e)
try:
    from python_speech_features import mfcc, logfbank
    print('python_speech_features OK')
except Exception as e:
    print('python_speech_features not available:', e)
try:
    import numpy
    print('numpy', numpy.__version__)
except Exception as e:
    print('numpy not available:', e)
PY
```

## 6. 첫 실행의 합격 기준

- 모델 파일이 존재한다.
- `allocate_tensors()`가 성공한다.
- 입력 shape/dtype이 문서화된다.
- raw 입력(랜덤 PCM 또는 zeros) inference가 성공한다.
- output shape이 기록된다.
- 마이크 캡처 1초 16 kHz mono PCM이 성공한다.
- 캡처 → feature 추출(또는 raw) → invoke → top-1 라벨 출력의 한 사이클이 동작한다.
- 호스트와 디바이스의 같은 golden wav 1개에 대해 top-1 라벨 일치를 확인한다 (feature 일치 검증, 멘토 리뷰 단점 2).
- 평균 latency와 p95 latency를 기록한다 (target: mean ≤ 50 ms / p95 ≤ 80 ms).

## 7. 실패 시 우선순위

1. `File not found`: 모델 경로와 권한 (`/opt/unoq-yolo/models/` 소유자 = `arduino`).
2. `ImportError: sounddevice`: PortAudio 시스템 라이브러리 미설치 (`sudo apt install libportaudio2`).
3. `allocate_tensors` 실패: 모델 op compatibility — 다른 TFLite 변종 또는 ai-edge-litert 버전 확인.
4. dtype mismatch: preprocessor에서 `uint8`/`int8`/`float32` 분기.
5. PCM 정규화 범위: 모델이 `[-1.0, 1.0]` float32를 기대하는지 `int16` `[-32768, 32767]`인지 확인.
6. **accuracy 0%**: feature 추출 파라미터(sr/n_mel/hop/window) 학습 시점과 불일치 — 가장 흔한 원인.
7. latency 초과: 입력 shape (raw PCM이 MFCC보다 일반적으로 무거움), thread count(1/2/4 sweep), feature 추출 비용(librosa→python_speech_features 교체).
8. 마이크 인식 실패: `arecord -l` 빈 출력 → `sudo modprobe -r snd_usb_audio; sudo modprobe snd_usb_audio` 후 재확인. USB 케이블 / 포트 의심.
9. `numpy` 충돌: vision 기존 numpy 2.5.0 + audio 신규 패키지가 다른 numpy 강제 시 → `pip install --dry-run`으로 사전 검출, 충돌 시 venv 분리 재검토 (디스크 비용 vs 격리 trade-off).
10. GPU delegate 실패: `/dev/kgsl*` 부재면 CPU 단독으로 fallback (vision과 동일 처리).

## 8. 본 빠른시작과 본문 docs의 관계

| 본문 | 본 빠른시작이 다룬 정도 |
|---|---|
| `02_model_selection_log.md` | 후보 비교 / 라이선스는 본 문서 §2에서 표면만 — 상세는 본문 |
| `03_host_env_setup.md` | Dockerfile / requirements.lock 상세는 본문 |
| `04_device_audio.md` | 마이크 진단 / `arecord -l` 결과 / `lsusb` 함정은 본문 |
| `05_validation.md` | latency 50회 측정 / 멘토 06 JSON / golden wav 검증은 본문 |
| `06_realtime_mic.md` | ring buffer / sliding window / VAD / N-frame confirm은 본문 |
| `07_official_benchmark.md` | 100회 벤치 / max RSS / max temp는 본문 |

본 빠른시작 = 한 번에 통과하는 최소 경로. 깊은 측정/디버깅/함정 기록은 본문 docs.

## 9. 1회 사이클 예상 시간

| 단계 | 호스트 | 디바이스 |
|---|---|---|
| asr-dev 컨테이너 첫 빌드 | ~10분 | — |
| 모델 다운로드 + 검증 (§2~§3) | ~5분 | — |
| 디바이스 의존성 설치 (§4) | — | ~5분 (numpy 충돌 없을 시) |
| Smoke test (§5) | — | ~2분 |
| 첫 inference + 마이크 캡처 + 라벨 출력 (§6) | — | ~10분 (모델 따라) |
| **합계 (정상 경로)** | **~15분** | **~17분** |

## 10. 다음 진입

본 빠른시작 통과 후:

1. `02_model_selection_log.md` — 후보 비교 + 라이선스 상세 + 채택 근거
2. `03_host_env_setup.md` — Docker 환경 정의 + requirements.lock
3. `04_device_audio.md` — 마이크 진단 + 함정 기록
4. `05_validation.md` — 호스트/디바이스 50회 latency + golden wav 검증
5. `06_realtime_mic.md` — 실시간 스트리밍 설계
6. `07_official_benchmark.md` — 100회 벤치 + 멘토 06 JSON
