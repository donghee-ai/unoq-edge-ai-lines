# UNO Q Edge AI Lines

> **NPU 없는 Arduino UNO Q(Qualcomm Dragonwing QRB2210, Cortex-A53 ×4)에서
> 객체검출·포즈추정·음성인식을 CPU만으로 얼마나 돌릴 수 있는지 잰 기록.**

측정 리포다. 제품을 만드는 곳이 아니라 "NPU 없이 이 정도 나온다"를 실기에서 확인하고
근거를 남기는 것이 전부다. 여기서 검증한 Pose 자산으로 만든 제품 라인은 별도 리포
[`health_care_bot`](https://github.com/donghee-ai/health_care_bot)에 있다.

측정은 2026-06 사이클에서 끝났고, 이 리포는 그 기록으로 닫혀 있다.

## 결과

**전부 UNO Q 실기에서 직접 잰 값이다.** 벤더 발표치는 섞여 있지 않다.

| 라인 | 모델 | 크기 | e2e | 결과 |
|---|---|---|---|---|
| Vision | YOLOv8n int8 TFLite | 3.19 MB | **9.23 FPS** | 합격 |
| Pose | MoveNet Thunder INT8 TFLite | 6.80 MB | **9.69 FPS** | 합격 |
| ASR | Whisper Tiny.en TFLite (DRQ) | 39.7 MB | **3.18 s** (11초 오디오) | 합격 |

합격선: e2e FPS ≥ 8 · RSS ≪ 2.4 GB · thermal ≤ 70 °C · dropped frames = 0

세 라인 모두 **invoke(추론)가 병목**이고 전처리·후처리·드로잉은 다 합쳐도 13~22 %다.
화면을 꺼도 FPS가 안 오르는 이유가 이것이다.

> **네 번째 라인(KWS)은 재지 못했다.** 후보 선정과 라이선스 검토까지만 하고 사이클이
> 끝나서, 구현 코드와 함께 리포에서 뺐다. 조사 결과는 남아 있다 —
> [`docs/lessons.md`](docs/lessons.md) §1-5가 그것이고, 이 리포에서 가장 재사용
> 가치가 높은 표다.

> **thermal은 여유가 없다.** 짧은 측정에서는 68.6 °C였지만 지속 구동에서 71.4 °C까지
> 올라 합격선을 넘겼다. soak 측정은 하지 않았다.

## 문서

두 장이면 충분하다.

| 문서 | 담는 것 |
|---|---|
| [`docs/measurements.md`](docs/measurements.md) | **측정 전부** — 환경·조건·수치·단계별 분해·안 잰 것 |
| [`docs/lessons.md`](docs/lessons.md) | **다시 쓸 판단** — 모델 선택 필터, 라이선스, 밟은 함정 6종 |

가장 재사용 가치가 높은 세 가지만 미리 꼽으면:

- **Qualcomm AI Hub 모델은 QRB2210에서 못 쓴다.** 받은 `.onnx`가 실은 다른 칩용 QNN
  컨텍스트 바이너리였다 — `EPContext` 노드가 증거
- **모델 카드를 믿지 말고 텐서를 열어볼 것.** "int8"로 알려진 Whisper가 실제로는 int8
  텐서 6.8 %인 weight-only DRQ였다
- **"Billboard Device만 보인다" = 케이블을 먼저 의심하라는 신호**

## 구조

```text
unoq-edge-ai-lines/
├── docs/                  문서 2장 (위 표)
├── vision/                YOLOv8n int8 — 코드 · Dockerfile · benchmarks/*.json
├── pose/                  MoveNet Thunder — 코드 · Dockerfile
│   └── ptz/               PTZ PoC (Shawn Hymel fork, MIT). 후속은 health_care_bot으로 이관
└── asr/                   Whisper Tiny.en — 코드 · Dockerfile
```

**모델 출처·라이선스는 [`docs/lessons.md`](docs/lessons.md) §1-2에 있다** — 전부 외부
자산이고 다운로드 URL까지 적혀 있다. **YOLOv8n은 AGPL-3.0이라 가중치를 리포에 두지
않는다**(§1-4). 별도로 구해올 필요는 없고, 아래 컨테이너 안에서 export 한 줄이면 된다 —
`ultralytics`가 이미 이미지에 들어 있고 `yolov8n.pt`도 자동으로 받아온다.

측정 원본 중 기계 판독이 되는 것은 `vision/benchmarks/*.json` 둘뿐이다.

## 실행

```bash
cd vision && bash docker/run-vision.sh              # 컨테이너 진입 (vision/이 /work에 마운트됨)

# 컨테이너 안에서 — 최초 1회, 모델 만들기
yolo export model=yolov8n.pt format=tflite int8=True imgsz=320
```

**모델은 이미지에 굽지 않는다.** Dockerfile은 파이썬 패키지만 깔고, `vision/`이 볼륨으로
마운트되므로 export 산출물은 호스트에 그대로 남는다. `*.tflite`는 gitignore 대상이라
실수로 커밋되지 않는다.

디바이스는 `~/venv-unoq` + `ai-edge-litert`로 돈다. 구성 절차는
[`docs/measurements.md`](docs/measurements.md) §1.

## 이 문서의 숫자를 읽는 법

- 표의 숫자는 **우리가 잰 것**이다. 벤더·논문·리더보드 인용에는 `(참조: 출처)`가 붙는다.
- **안 잰 것은 "미측정"으로 적혀 있다.** 빈 칸이나 `?`로 채운 결과 표는 두지 않았다 —
  데이터가 있는 것처럼 보여서 없느니만 못하기 때문이다.
- KWS 실측과 soak thermal은 하지 않았고, 그 사실을 그대로 적어두는 것으로 마무리한다.

---

**작자**: DongHee Kim (한성대) · **리포**: `donghee-ai/unoq-edge-ai-lines`
