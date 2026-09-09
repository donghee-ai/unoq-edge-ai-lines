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

### 1-2. 채택한 것

| 라인 | 채택 | 폴백 계획 | 폴백 썼나 |
|---|---|---|---|
| Vision | YOLOv8n int8 (Ultralytics 표준 export) | FPS < 8~10이면 MediaPipe Face | **아니오** — 트리거 미발동 |
| Pose | **MoveNet Thunder INT8** (TF Hub, Apache-2.0 + CC BY 4.0, 256×256, 17 keypoint, 단일 invoke) | Lightning INT8(192×192) → MediaPipe Pose int8 BQ(ONNX, 2-stage) | **아니오** — 1순위로 합격 |
| ASR | Whisper Tiny.en TFLite | — | — |
| KWS | MLPerf Tiny DS-CNN INT8 | TFLM MicroSpeech | 미측정이라 판단 불가 |

실제 수치는 [`measurements.md`](measurements.md).

Pose는 정확도 우선으로 Thunder를 먼저 시도했다 — Lightning(192)보다 keypoint 정밀도가
높고, 그게 관절 각도 측정 정밀도로 직결되기 때문이다.

### 1-3. KWS — 라이선스 필터가 후보를 반으로 줄였다

이 리포에서 가장 재사용 가치가 높은 표다. "상업적으로 못 쓰는 것"이 생각보다 많다.

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
