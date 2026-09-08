# 환경 구성 — 호스트와 디바이스

네 라인이 **같은 방식**으로 돌아갑니다. 라인마다 흩어져 있던 quickstart를 하나로
합쳤고, 라인별로 다른 부분만 §4에 표로 남겼습니다.

측정 결과는 [`02_measurements.md`](02_measurements.md), 밟은 함정은
[`04_traps.md`](04_traps.md).

## 0. 두 개의 환경

| | 용도 | 런타임 |
|---|---|---|
| **호스트(개발 PC)** | 모델 introspection · 알고리즘 검증 · 대조군 측정 | Docker (Ubuntu 22.04, Python 3.10) |
| **디바이스(UNO Q)** | 실제 측정 — 이 리포의 목적 | `~/venv-unoq` (Python 3.13, aarch64) |

호스트는 **대조군**이다. 합격/불합격을 가르는 숫자는 전부 디바이스에서 나온다.

## 1. 디바이스 사양 (실측)

| 항목 | 값 |
|---|---|
| SoC | Qualcomm Dragonwing QRB2210 |
| CPU | Cortex-A53 ×4 @ 2.0 GHz |
| **NPU / GPU 델리게이트** | **없음 — CPU only** |
| RAM | 4 GB LPDDR4 |
| 저장소 | 32 GB eMMC |
| Python | 3.13.5 (`/usr/bin/python3`) |
| pip | **미설치** (`No module named pip`) |

## 2. 디바이스 런타임 — venv + `ai-edge-litert`

pip이 없고 Debian 12+ **PEP 668**이 시스템 Python 직접 수정을 막는다. 그래서 venv를 쓴다.

```bash
ssh arduino@<UNO_Q_IP>

python3 -m venv ~/venv-unoq
source ~/venv-unoq/bin/activate
python -m ensurepip --upgrade
pip install ai-edge-litert numpy opencv-python-headless
```

### 왜 `tflite-runtime`이 아니라 `ai-edge-litert`인가

`tflite-runtime`은 **Python 3.13 / aarch64 조합에 휠이 없다.** `ai-edge-litert`가 같은
TFLite 인터프리터를 제공하면서 이 환경에서 설치가 된다. 네 라인 모두 이걸 쓴다.

```python
from ai_edge_litert.interpreter import Interpreter
interp = Interpreter(model_path=..., num_threads=4)
```

> **`num_threads=4`가 기본이다.** 코어가 4개고 invoke가 병목이라 스레드를 줄일 이유가
> 없다. 1스레드 대조가 필요하면 그때만 바꾼다.

## 3. 호스트 컨테이너

라인별로 Dockerfile이 하나씩 있고, 실행 스크립트가 컨테이너 진입까지 해준다.

```bash
cd vision && bash docker/run-vision.sh      # 첫 빌드 ~10분, 이후 5초
cd pose   && bash docker/run-pose.sh
cd asr    && bash docker/run-asr.sh
cd kws    && bash docker/run-kws.sh         # 첫 빌드 ~3분
```

## 4. 라인별로 다른 것

| 라인 | 모델 파일 | 입력 | 실행 스크립트 |
|---|---|---|---|
| Vision | `yolov8n_int8.tflite` | 640×640 | `vision/src/infer_camera.py` · `benchmark_e2e.py` |
| Pose | `movenet_thunder_int8.tflite` | 256×256 letterbox | `pose/scripts/infer_camera_pose.py` |
| ASR | `whisper_tiny_en.tflite` | 80×3000 mel | `asr/src/` |
| KWS | `kws_ref_model_ds_cnn_int8.tflite` | `[1,49,10,1]` MFCC | `kws/scripts/` |

모델은 리포에 없다. 각 라인의 `models/README.md` 또는
[`03_model_choice.md`](03_model_choice.md)의 출처에서 받는다.

## 5. 실기에서 반드시 확인할 것

```bash
ls /dev/video*                      # 카메라 노드 — 부팅마다 번호가 바뀐다
lsusb                               # 허브·카메라·시리얼이 다 보이는지
cat /sys/class/thermal/thermal_zone0/temp   # ÷1000 = °C
```

- **노드 번호를 규칙으로 외우지 말 것.** 부팅 순서에 따라 뒤바뀐다.
- **구동 중 USB를 뽑지 말 것** — 컨트롤러가 통째로 죽은 적이 있다
  ([`04_traps.md`](04_traps.md) §3).
- **온도를 짧게 재고 판정하지 말 것** — 136초 68.6 °C였다가 지속 구동에서 71.4 °C로
  합격선을 넘겼다 ([`04_traps.md`](04_traps.md) §4).

## 6. 측정할 때

측정값은 **반드시 JSON으로 저장한다.** vision만 `benchmarks/*.json`이 남아 있고
나머지 세 라인은 숫자가 history 문서 안에만 있어서 기계 판독이 안 된다. 같은 실수를
반복하지 말 것 — [`02_measurements.md`](02_measurements.md) §7.

## 7. 원본 문서

통합 전 라인별 셋업·quickstart 문서는 각 라인의 `docs/history/superseded/`에 그대로 있다.
디바이스 사양 실측 원문은 `vision/docs/history/superseded/04_device_setup.md`.
