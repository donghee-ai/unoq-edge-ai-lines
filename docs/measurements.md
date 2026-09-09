# 측정 — 환경, 수치, 안 잰 것

요약 표는 [README](../README.md)에 있다. 이 문서는 **어떻게 쟀고 무엇이 나왔는지**를
담는다. 판단·함정은 [`lessons.md`](lessons.md).

## 1. 환경

네 라인이 같은 방식으로 돈다.

| | 용도 | 런타임 |
|---|---|---|
| 호스트(개발 PC) | 모델 introspection · 알고리즘 검증 · **대조군** | Docker (Ubuntu 22.04, Python 3.10) |
| 디바이스(UNO Q) | 실제 측정 — 이 리포의 목적 | `~/venv-unoq` (Python 3.13, aarch64) |

합격/불합격을 가르는 숫자는 전부 디바이스에서 나온다.

### 1-1. 디바이스 사양 (실측)

| 항목 | 값 |
|---|---|
| SoC | Qualcomm Dragonwing QRB2210 |
| CPU | Cortex-A53 ×4 @ 2.0 GHz |
| **NPU / GPU 델리게이트** | **없음 — CPU only** |
| RAM / 저장소 | 4 GB LPDDR4 / 32 GB eMMC |
| Python | 3.13.5 (`/usr/bin/python3`), **pip 미설치** |

### 1-2. 디바이스 런타임 — venv + `ai-edge-litert`

pip이 없고 Debian 12+ **PEP 668**이 시스템 Python 수정을 막아서 venv를 쓴다.

```bash
ssh arduino@<UNO_Q_IP>
python3 -m venv ~/venv-unoq && source ~/venv-unoq/bin/activate
python -m ensurepip --upgrade
pip install ai-edge-litert numpy opencv-python-headless
```

**`tflite-runtime`이 아니라 `ai-edge-litert`인 이유**: `tflite-runtime`은 Python 3.13 /
aarch64 조합에 휠이 없다. `ai-edge-litert`가 같은 TFLite 인터프리터를 제공하면서 이
환경에서 설치가 된다.

```python
from ai_edge_litert.interpreter import Interpreter
interp = Interpreter(model_path=..., num_threads=4)
```

`num_threads=4`가 기본이다 — 코어가 4개고 invoke가 병목이라 줄일 이유가 없다.

호스트 컨테이너는 라인마다 스크립트 하나로 들어간다:
`cd <라인> && bash docker/run-<라인>.sh` (첫 빌드 3~10분, 이후 5초).

### 1-3. 라인별로 다른 것

| 라인 | 모델 파일 | 입력 | 진입점 |
|---|---|---|---|
| Vision | `yolov8n_int8.tflite` | 640×640 | `vision/src/infer_camera.py` · `benchmark_e2e.py` |
| Pose | `movenet_thunder_int8.tflite` | 256×256 letterbox | `pose/scripts/infer_camera_pose.py` |
| ASR | `whisper_tiny_en.tflite` | 80×3000 mel | `asr/src/` |

### 1-4. 실기에서 반드시 확인할 것

```bash
ls /dev/video*                               # 노드 번호는 부팅마다 바뀐다
lsusb                                        # 허브·카메라·시리얼이 다 보이는지
cat /sys/class/thermal/thermal_zone0/temp    # ÷1000 = °C
```

노드 번호를 규칙으로 외우지 말 것. **구동 중 USB를 뽑지 말 것**([`lessons.md`](lessons.md) §6).
**온도를 짧게 재고 판정하지 말 것**([`lessons.md`](lessons.md) §5).

## 2. Vision — YOLOv8n int8

원본: [`vision/benchmarks/device_e2e_20260623.json`](../vision/benchmarks/device_e2e_20260623.json)
(호스트 대조군 `host_e2e_20260623.json`). 100 프레임, warmup 10, 4 threads.

| 항목 | 값 |
|---|---|
| fps_mean | **9.23** |
| latency p50 / p95 | 105.0 ms / 132.7 ms |
| max_rss_mb | 100.8 |
| max_temp_c | 60.5 |
| dropped_frames | 0 |

### 2-1. 단계별 분해 — invoke가 86 %

| 단계 | mean | p50 | p95 |
|---|---|---|---|
| preprocess | 5.42 ms | 6.04 | 6.59 |
| **inference** | **93.28 ms** | **90.71** | **120.21** |
| postprocess | 5.08 ms | 5.08 | 5.60 |
| draw | 3.90 ms | 3.88 | 4.17 |
| **total** | **108.36 ms** | 105.02 | — |

전처리·후처리·드로잉을 다 합쳐도 14.4 ms로 전체의 13 %다. **화면을 꺼도 FPS는 거의
안 오른다** — 이 분해가 그 근거다.

## 3. Pose — MoveNet Thunder INT8

1,320 프레임 / 136.2 초 연속 카메라 구동.

| 항목 | 측정 | 합격선 | 평가 |
|---|---|---|---|
| fps_effective | **9.69** | ≥ 8 | 21 % 여유 |
| dropped_frames | **0** | — | 카메라 캡처 손실 없음 |
| cpu_peak_pct (프로세스) | **316.3** | — | 4코어 합산 = 코어당 79 % |
| rss_peak_mb | **95.0** | ≪ 2.4 GB | — |
| temp_peak_c | **68.6** | ≤ 70 | 1.4 °C 여유 |

invoke만 따로 재면 **80.3 ms (p50)** / 12.5 FPS. e2e 103 ms와의 차이 23 ms가 캡처·
letterbox·후처리·draw·JPEG 인코딩·HTTP 서빙 전부다. **invoke 78 %.**

> 위 68.6 °C는 136초 측정값이다. 장시간 구동에서는 **71.4 °C까지 올라 합격선 70 °C를
> 넘겼다**([`lessons.md`](lessons.md) §5). soak 측정은 하지 않았다.

## 4. ASR — Whisper Tiny.en (DRQ)

JFK 1961 취임 연설 11초 wav.

| 항목 | 값 |
|---|---|
| e2e | **3.18 초** (합격선 ≤ 5 초) |
| 정확도 | 7 단어 중 6 개 일치 |
| 모델 크기 | 39.7 MB |

### 4-1. "int8"이 아니었다 — 텐서를 열어 밝힌 것

| 확인 | 결과 |
|---|---|
| 입력 `serving_default_input_ids:0` | `[1,80,3000]` **float32**, qparams 비어 있음 |
| 출력 `StatefulPartitionedCall:0` | `[1,448]` **int32**, qparams 비어 있음 |
| int8 텐서 비율 | 76 개 = 전체의 **6.8 %** (일부 큰 weight matrix만) |

크기로 역산하면 fp32 ~150 MB / fp16 ~75 MB / **DRQ ~40 MB** / full int8 ~10 MB. 실측
39.7 MB + dtype 분포가 DRQ와 정확히 맞는다 → **weight-only int8 (Dynamic Range
Quantization)** 확정. 교훈은 [`lessons.md`](lessons.md) §3.

## 5. KWS — 재지 못했다

네 번째 라인으로 잡았지만 **디바이스 측정에 도달하지 못했다.** 후보 선정과 라이선스
검토까지만 하고 사이클이 끝났고, MFCC 프론트엔드·추론·모드 컨트롤러 구현(약 2,200줄)은
한 번도 실기에서 돌지 않았다. latency·RSS·thermal·오탐률 **전부 미측정**이다.

측정값이 없는 구현을 측정 리포에 두면 네 라인을 다 잰 것처럼 읽히므로 **코드는
리포에서 뺐다**(2026-09-09). git 히스토리에 그대로 있어서 KWS를 다시 하게 되면
거기서 꺼내면 된다.

> **남긴 것** — 후보 조사와 라이선스 필터링 결과는 측정 없이도 성립하는 결과물이라
> [`lessons.md`](lessons.md) §1-5에 그대로 뒀다.

재개한다면 계획했던 측정 조건은 **clean 환경(조용한 방)과 생활 노이즈 환경을 각각
재고 결과를 분리 보고**하는 것이었다. 최소 모델(< 100 KB)로도 실시간 성능이 안 나오면
알고리즘 튜닝 대신 GPIO 버튼으로 전환하기로 했었다.

## 6. 라인 간 비교

| 항목 | Vision (YOLOv8n) | Pose (Thunder) |
|---|---|---|
| e2e FPS | 9.23 | 9.69 |
| invoke p50 | 90.7 ms | 80.3 ms |
| invoke 비중 | 86 % | 78 % |
| RSS peak | 100.8 MB | 95.0 MB |

모델 크기는 2배 차이(3.19 vs 6.80 MB)인데 **속도는 Pose가 오히려 빠르다.** 파일 크기가
추론 시간을 예측하지 못한다는 실증이다 — 연산량과 연산자 구성이 결정한다.

## 7. 이 숫자들을 읽을 때

- **thermal 값이 런마다 다르다.** §2·§3의 온도는 서로 다른 런이고 측정 길이도 다르다.
  soak을 안 했으므로 thermal은 "합격선 근처, 지속 시 초과"로 읽는 것이 정확하다.
- **CPU %는 4코어 합산 기준**이다. 316 % = 코어당 79 %.
- **기계 판독이 되는 원본은 `vision/benchmarks/*.json` 둘뿐이다.** Pose·ASR은 측정
  당시 `--json` 저장을 켜지 않아서, 이 문서의 표가 유일한 정리본이다.
