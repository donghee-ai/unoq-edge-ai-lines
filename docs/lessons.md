# 다시 쓸 판단 — 모델 선택과 밟은 함정

측정값은 [`measurements.md`](measurements.md). 이 문서는 **숫자보다 오래 남는 것**을
담는다. 왜 이 모델을 골랐고, 어디서 시간을 버렸나.

## 1. 모델 선택

### 1-1. 네 라인 공통 필터

순서대로 걸렀고, 하나라도 걸리면 후보에서 뺐다.

| # | 필터 | 이유 |
|---|---|---|
| 1 | **상업 사용 가능 라이선스만** — Apache-2.0 / MIT / BSD-3 / CC BY 4.0 | Non-Commercial · GPL · 커스텀 EULA는 전면 기각 |
| 2 | **TFLite + `ai-edge-litert`** 스택 | 4 라인이 같은 런타임을 쓰면 컨테이너·디버깅이 하나로 끝난다 |
| 3 | **chipset 비종속** | §2 — 특정 칩용으로 미리 컴파일된 모델은 QRB2210에서 안 돈다 |
| 4 | **가중치가 파일에 들어 있고 `wget`으로 바로 받아지는 것** | 계정·SDK·재훈련이 필요하면 재현이 끊긴다 |

### 1-2. 채택한 모델 — 출처와 라이선스

**이 표가 제3자 자산 표기다.** 모델은 전부 외부에서 받아온 것이고, 우리가 만든 것은
없다.

| 라인 | 모델 | 출처 | 라이선스 |
|---|---|---|---|
| Vision | YOLOv8n int8 | [Ultralytics](https://docs.ultralytics.com/) 표준 export 경로 | **AGPL-3.0** — §1-4 참고 |
| Pose | MoveNet Thunder INT8 | TensorFlow Hub (Google) | Apache-2.0 (모델) + CC BY 4.0 |
| ASR | Whisper Tiny.en TFLite | [nyadla-sys/whisper.tflite](https://github.com/nyadla-sys/whisper.tflite) | **MIT** — Copyright (c) 2023 Niranjan Yadla. 원본 Whisper도 MIT (OpenAI) |
| KWS † | MLPerf Tiny DS-CNN INT8 | [mlcommons/tiny](https://github.com/mlcommons/tiny) | Apache-2.0 (코드) + CC BY 4.0 (데이터) |

**YOLOv8n 가중치는 이 리포에 넣지 않는다** — AGPL-3.0이라 재배포하면 라이선스 의무가
따라붙는다. 아래 export를 각자 로컬에서 돌려서 만든다.

리포가 실제로 재배포하는 제3자 바이너리는 **Whisper 변환본 하나뿐**이고(MIT),
MIT가 요구하는 저작권 고지를 모델 옆에
[`asr/models/audio/LICENSE-whisper-tflite.txt`](../asr/models/audio/LICENSE-whisper-tflite.txt)에
동봉했다. MoveNet은 wget 한 줄이라 넣지 않았고, Qualcomm 산출물은 EULA라 뺐다(§1-4).

```bash
# Vision — 받는 게 아니라 직접 export (AGPL, 재배포 금지)
#   imgsz=320 필수: postprocess.py가 320 전용(앵커 2100개)이고 실측도 320 기준
pip install ultralytics
yolo export model=yolov8n.pt format=tflite int8=True imgsz=320
#   -> yolov8n_saved_model/yolov8n_full_integer_quant.tflite 를 쓴다
#   (yolov8n.pt는 ultralytics가 자동으로 받아온다 - 따로 구할 필요 없다)

# Pose — 채택본
wget -O movenet_thunder_int8.tflite \
  "https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4?lite-format=tflite"

# Pose — 속도 폴백 (미사용)
wget -O movenet_lightning_int8.tflite \
  "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/int8/4?lite-format=tflite"

# ASR
wget -O whisper_tiny_en.tflite \
  https://raw.githubusercontent.com/nyadla-sys/whisper.tflite/main/models/whisper-tiny-en.tflite
# 대안: https://huggingface.co/DocWolle/whisper_tflite_models/resolve/main/whisper-tiny.en.tflite

# KWS — 선정만 하고 측정엔 못 갔다 (§1-5)
git clone --depth 1 https://github.com/mlcommons/tiny.git
```

† KWS는 채택까지만 하고 **실기 측정에 도달하지 못했다.** 구현 코드도 리포에서 뺐다
([`measurements.md`](measurements.md) §5). 아래 §1-5의 조사 결과만 남긴다.

### 1-3. 폴백은 하나도 안 썼다

| 라인 | 폴백 계획 | 발동 |
|---|---|---|
| Vision | FPS < 8~10이면 MediaPipe Face로 교체 | **아니오** — 트리거 미발동 |
| Pose | Lightning INT8(192×192) → MediaPipe Pose int8 BQ(ONNX, 2-stage) | **아니오** — 1순위로 합격 |

Pose는 정확도 우선으로 Thunder(256×256, 17 keypoint, 단일 invoke)를 먼저 시도했다 —
Lightning(192)보다 keypoint 정밀도가 높고, 그게 관절 각도 측정 정밀도로 직결되기
때문이다. 실제 수치는 [`measurements.md`](measurements.md).

### 1-4. 필터 1의 예외 — Vision은 AGPL-3.0이다

§1-1에서 "상업 사용 가능 라이선스만"이라고 걸러놓고 Vision만 **AGPL-3.0**(Ultralytics
기반)을 채택했다. 모순이 아니라 **범위를 좁혀서 통과시킨 것**이다 — 이 리포는 측정이
목적이고 배포하지 않으므로 AGPL 조항이 발동하지 않는다.

> **상업 배포 단계로 가면 이 예외가 유효하지 않다.** Ultralytics 상용 라이선스를 사거나
> 대체 모델(MediaPipe Face 등)로 바꿔야 한다. 나머지 세 라인은 그대로 써도 된다.

같은 이유로 **YOLOv8n 가중치 파일은 리포에서 뺐다**(2026-09-09). 코드와 측정값은
남기고 모델만 §1-2의 export 명령으로 대체했다 — 재배포하지 않으면 AGPL 의무가
발생하지 않기 때문이다.

**왜 가중치만 빼고 `vision/` 코드와 Dockerfile은 남겼나** — AGPL이 걸리는 것은
*Ultralytics 저작물을 배포*하는 행위인데, 이 리포가 배포하던 건 가중치뿐이었다.

| | Ultralytics 저작물인가 | 판단 |
|---|---|---|
| `yolov8n_int8.tflite` 가중치 | **예** | 뺐다 |
| `vision/src/*.py` | 아니오 — `ultralytics`를 import하지 않는다. `ai-edge-litert`(Apache-2.0)로 `.tflite`를 직접 돌리고, 디코딩·NMS는 numpy로 자체 구현했다 | 남긴다 |
| `vision/docker/requirements.txt` | 아니오 — `ultralytics`를 **이름으로 나열**할 뿐이다. 빌드하는 사람이 PyPI에서 각자 받는다 | 남긴다 |

요약하면 **우리 코드는 Ultralytics의 2차적 저작물이 아니다.** `infer_camera.py`가 MJPEG를
HTTP로 서빙하지만, AGPL의 네트워크 사용 조항도 같은 이유로 닿지 않는다.
(법률 자문은 아니고, 보수적으로 읽은 결과다.)

> 다만 `requirements.txt`가 **export 도구 체인**(ultralytics·onnx·onnx2tf 등)과
> **런타임**(ai-edge-litert·numpy·cv2)을 한 파일에 섞어두고 있다. 이제 가중치를
> 안 넣으니 둘을 나눠두면 "실행에 필요한 것"과 "모델 만들 때만 필요한 것"이 분명해진다.

| 모델 | 리포에 있나 | 이유 |
|---|---|---|
| YOLOv8n int8 | **없음** | AGPL-3.0 — export로 각자 생성 |
| Whisper Tiny.en | 있음 (`asr/models/audio/`) | MIT — 재배포 가능 |
| MoveNet Thunder | 없음 | 용량. wget 한 줄이면 받는다 |
| QNN 컨텍스트 바이너리 | **없음** | Qualcomm AI Hub EULA(proprietary) — 재배포하지 않는다. 판별 결과는 §2 표에 남겼다 |

### 1-5. KWS — 라이선스 필터가 후보를 반으로 줄였다

**KWS는 측정까지 못 갔지만 이 표는 남긴다.** 실측 없이도 성립하는 결과이고, 이 리포에서
가장 재사용 가치가 높다 — "상업적으로 못 쓰는 것"이 생각보다 많다.

| 후보 | 코드 | 데이터 | 상업 | 판정 |
|---|---|---|---|---|
| **MLPerf Tiny DS-CNN INT8** | Apache-2.0 | CC BY 4.0 | ✓ | **1순위 채택** |
| Google TFLM MicroSpeech | Apache-2.0 | CC BY 4.0 | ✓ | 2순위 fallback |
| ARM ML-KWS-for-MCU | Apache-2.0 | CC BY 4.0 | ✓ | 3순위 — **사전학습 가중치가 TFLite로 배포 안 됨**(재훈련 필요) |
| Silicon Labs MLTK | Apache-2.0 | CC BY 4.0 | ✓ | 예비 |
| openWakeWord | Apache-2.0 | CC0/MIT | ✓ | 기각 — **ONNX 전용**, 스택 불일치 |
| **Picovoice Porcupine** | Non-Commercial 무료 | proprietary | **✗** | **기각** — 상업 시 유료 |
| **Snowboy** | — | — | **✗** | **기각** — 2020 서비스 종료 |
| Vosk KWS | Apache-2.0 | Apache-2.0 | ✓ | 오버킬 (STT 전체, 우리는 4~12 단어) |
| Qualcomm AI Hub KWS | **Qualcomm EULA** | proprietary | △ | 기각 — §2 |

채택 모델 스펙(**전부 프로젝트 발표치. 우리 실측 아님**): 크기 ~52 KB · 입력
`[1,49,10,1]` int8 · 출력 12 클래스 · MFCC 10계수 / 25 ms 윈도우 / 10 ms 홉 / 16 kHz ·
정확도 ~90.5 % — 출처 [MLPerf Tiny 리더보드](https://mlcommons.org/benchmarks/inference-tiny/).

필요 표기: *"Trained on Google Speech Commands v2 (CC BY 4.0). Model architecture:
MLPerf Tiny KWS reference (Apache-2.0)."*

## 2. Qualcomm AI Hub 모델은 QRB2210에서 못 쓴다

TFLite로 간 가장 큰 이유다. 추측이 아니라 직접 받아서 열어보고 확인했다.

**증상** — `mediapipe_pose-precompiled_qnn_onnx-w8a8-qualcomm_snapdragon_x2_elite.zip`을
받아 onnxruntime으로 로드하면:

```
[ONNXRuntimeError] : 1 : FAIL : Load model from pose_detector.onnx failed:
Unsupported model IR version: 13, max supported IR version: 10
```

**원인** — 파일을 열어보면 나온다.

| 항목 | 값 |
|---|---|
| producer | Qualcomm AI Hub Workbench (aihub-2026.06.08.2) |
| IR version | **13** (onnxruntime 1.22.1은 10까지) |
| op_types | `DequantizeLinear ×5`, `QuantizeLinear ×5`, **`EPContext ×1`** |
| EPContext.source | **`QNN`** |

**이건 ONNX 모델이 아니다.** 사전 컴파일된 **QNN 컨텍스트 바이너리**를 ONNX 껍데기로
싼 것이고 `EPContext` 노드가 그 증거다. 실제 연산은 QNN Execution Provider가 해야 하며
**컴파일 대상 칩(Snapdragon X2 Elite)에서만 돈다.** IR 버전을 맞춰도 소용없다.

**재발 방지** — 모델을 받기 전에 **대상 칩**과 `EPContext` 유무를 확인할 것. 확장자가
`.onnx`라고 다 이식 가능한 게 아니다.

> **받은 파일 자체는 리포에 두지 않는다.** Qualcomm AI Hub 산출물은 Qualcomm EULA
> (proprietary) 아래 있어서 재배포 대상이 아니다 — §1-1 필터 1이 기각한 바로 그
> 조건이다. 위 표(producer·IR version·op_types·EPContext.source)가 판별에 필요한
> 전부이고, 원본이 필요하면 AI Hub에서 각자 받으면 된다.

## 3. 모델 카드를 믿지 말고 텐서를 열어볼 것

Whisper Tiny.en TFLite를 "int8"로 알고 받았는데 열어보니 **weight-only DRQ**였다.
판별 과정과 텐서 분포는 [`measurements.md`](measurements.md) §4-1.

크기와 dtype 분포만 봐도 양자화 형태를 역산할 수 있다 — 받자마자 한 번 열어보는 데
드는 시간이 나중에 성능을 오해하는 비용보다 훨씬 싸다.

## 4. "Billboard Device만 보인다" = 케이블을 의심하라

**증상** — 허브를 거치면 ADB에 디바이스가 안 뜨거나, 떠도 **"Billboard Device"(VID
2f61)만** 등록된다.

**원인** — Billboard Device는 USB-C **Power Delivery 협상 시 등록되는 메타 장치**로,
실제 데이터 인터페이스가 없다는 신호다. 확률 순으로 ① **USB-C 케이블이 충전 전용**
(생김새가 같아도 D+/D− 핀이 없다) ② 허브 데이터 패스가 alt mode로 빠짐 ③ 허브 전력 부족.

**대응** — 데이터 지원 케이블로 교체 + 직결. 이후 SSH 기반 작업으로 전환해 ADB 의존을
줄였다. 허브·포트·드라이버를 뒤지기 전에 **케이블부터** 바꿔볼 것.

## 5. 짧게 재고 thermal을 판정하면 안 된다

**증상** — 136초 측정에서는 68.6 °C(합격)였는데 **지속 구동에서 71.4 °C plateau**로
합격선 70 °C를 1.4 °C 넘겼다.

**원인(추정)** — A53 4코어 78 % 사용 누적 발열 + MJPEG 서빙(JPEG 인코딩 + 소켓 I/O)
추가 부하. UNO Q는 **passive 방열만** 한다.

**상태** — 미해결. soak 측정을 하지 않았다. 이 항목의 핵심은 온도 숫자가 아니라
**측정 길이가 결론을 바꾼다**는 것이다.

## 6. 구동 중 USB를 뽑으면 컨트롤러가 통째로 죽는다

**증상** — 마이크 USB를 분리하는 순간 `xhci-hcd` USB host controller가 deregister.
카메라까지 같이 사라진다.

**원인(추정)** — 분리 동작이 ① UNO Q↔허브 USB-C 접점을 흔들었거나 ② 허브 PD 상태
변동으로 xhci enumeration 재시작이 실패했거나 ③ PD power role 협상 중 드라이버 상태가
깨진 것. **USB-C 1포트 + 허브 의존 토폴로지의 구조적 약점**이다.

**대응** — 구동 중에는 뽑지 말 것. 뽑아야 하면 프로세스를 먼저 내린다.

## 7. 카메라 높이가 검출률을 지배한다

**증상** — 정면은 잘 잡히는데 **측면·후면에서 keypoint 검출률이 급락**한다.

**원인** — 카메라가 바닥 근처라 **수직 화각이 부족**하다. hip/knee/ankle이 원근 왜곡으로
정상 비례를 벗어나고, 측면에서는 한쪽 다리 occlusion + 신체 일부가 프레임 밖으로,
후면에서는 nose/eyes/shoulders가 안 보여 MoveNet 전체 신뢰도가 떨어진다.

**근거** — 정면은 L·R 둘 다 ~170°(Standing) / 90° 이하(Squat)로 명확히 갈리는데,
측면·후면 구간에서는 한쪽이 미검출로 빠진다.

**대응** — 카메라를 높이거나 사람이 더 뒤로. **알고리즘으로 해결할 문제가 아니다.**

## 8. 워크스페이스로 열린 폴더는 이름을 못 바꾼다

**증상** — PowerShell `Rename-Item` 후 `unoq-mediapipe-pose;C` 같은 빈 폴더가 잔류.
재현 시에는 `Device or resource busy` → `Access denied`.

**원인** — 대상 폴더를 다른 프로세스(VSCode 파일 감시자·탐색기)가 점유해 atomic rename이
부분만 처리된다. 에디터를 닫고 해야 한다.
