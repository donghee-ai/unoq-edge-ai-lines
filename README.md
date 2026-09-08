# UNO Q Edge AI Lines

> **NPU 없는 Arduino UNO Q(Qualcomm Dragonwing QRB2210, Cortex-A53 ×4)에서
> 객체검출·포즈추정·음성인식을 CPU만으로 얼마나 돌릴 수 있는지 잰 기록.**

이건 **측정 리포**다. 제품을 만드는 곳이 아니라, "NPU 없이 이 정도 나온다"를 실기에서
확인하고 근거를 남기는 것이 전부다. 여기서 검증한 Pose 자산으로 만든 제품 라인은
별도 리포 [`health_care_bot`](https://github.com/donghee-ai/health_care_bot)에 있다.

## 결과

**전부 UNO Q 실기에서 직접 잰 값이다.** 벤더 발표치는 섞여 있지 않다.

| 라인 | 모델 | 크기 | e2e | 결과 |
|---|---|---|---|---|
| Vision | YOLOv8n int8 TFLite | 3.19 MB | **9.23 FPS** | 합격 |
| Pose | MoveNet Thunder INT8 TFLite | 6.80 MB | **9.69 FPS** | 합격 |
| ASR | Whisper Tiny.en TFLite (DRQ) | 39.7 MB | **3.18 s** (11초 오디오) | 합격 |
| KWS | MLPerf Tiny DS-CNN INT8 | 52 KB | **미측정** | 후보 선정만 완료 |

합격선: e2e FPS ≥ 8 · RSS ≪ 2.4 GB · thermal ≤ 70 °C · dropped frames = 0

세 라인 모두 **invoke(추론)가 병목**이고 전처리·후처리·드로잉은 다 합쳐도 13~22 %다.
화면을 꺼도 FPS가 안 오르는 이유가 이것이다. 단계별 분해는
[`docs/02_measurements.md`](docs/02_measurements.md) §1-1.

> **thermal은 여유가 없다.** 짧은 측정에서는 68.6 °C였지만 지속 구동에서 71.4 °C까지
> 올라 합격선을 넘겼다. soak 측정은 아직 안 했다.

## 이 리포에서 건질 것

측정값 자체보다 **다시 쓸 수 있는 판단들**이 남았다.

| | |
|---|---|
| **Qualcomm AI Hub 모델은 QRB2210에서 못 쓴다** | 받은 `.onnx`가 실은 다른 칩용 QNN 컨텍스트 바이너리였다. `EPContext` 노드가 증거 → [03 §4](docs/03_model_choice.md) |
| **모델 카드를 믿지 말고 텐서를 열어볼 것** | "int8"로 알려진 Whisper가 실제로는 int8 텐서 6.8 %인 weight-only DRQ였다 → [02 §3-1](docs/02_measurements.md) |
| **KWS 라이선스 필터** | 후보 10종 중 Picovoice·Snowboy 등이 상업 사용 불가로 탈락. 근거와 표기 문구까지 → [03 §3](docs/03_model_choice.md) |
| **밟은 함정 6종** | Billboard Device = 케이블 의심 신호, USB 뽑으면 컨트롤러가 죽는다 등 → [04](docs/04_traps.md) |

## 문서

네 개면 충분하다.

| # | 문서 | 담는 것 |
|---|---|---|
| 01 | [`01_device_setup.md`](docs/01_device_setup.md) | 호스트·디바이스 환경 구성, 라인별 차이 |
| 02 | [`02_measurements.md`](docs/02_measurements.md) | **측정 결과 전부** + 단계별 분해 + 원본 위치 |
| 03 | [`03_model_choice.md`](docs/03_model_choice.md) | 무엇을 왜 골랐나, 라이선스 필터, AI Hub 비호환 |
| 04 | [`04_traps.md`](docs/04_traps.md) | 밟은 함정 — 증상에서 원인으로 |

기록은 라인별 `docs/history/` · `docs/issues/`에 그대로 있다(append-only).
2026-09-08 통합 전의 상설 문서 38개는 `<라인>/docs/history/superseded/`에 보존돼 있다 —
지운 게 아니라 상설에서 내린 것이다.

## 구조

```text
unoq-edge-ai-lines/
├── docs/                  상설 문서 4개 (위 표)
├── vision/                YOLOv8n int8 — 코드 · Dockerfile · benchmarks/*.json
├── pose/                  MoveNet Thunder — 코드 · Dockerfile
│   └── ptz/               PTZ PoC (Shawn Hymel fork, MIT)
├── asr/                   Whisper Tiny.en — 코드 · Dockerfile
├── kws/                   DS-CNN — 코드 · Dockerfile (측정 전)
│   └── docs/03_ssh_to_benchmark_walkthrough.md   측정 절차 (미실행)
└── device-deploy/         디바이스에 올리는 런타임 묶음
```

모델 파일은 리포에 없다. 출처는 [`docs/03_model_choice.md`](docs/03_model_choice.md).

## 실행

```bash
cd vision && bash docker/run-vision.sh     # 호스트 컨테이너 (대조군)
```

디바이스는 `~/venv-unoq` + `ai-edge-litert`로 돈다. 절차는
[`docs/01_device_setup.md`](docs/01_device_setup.md).

## 수치 표기 규칙

- 표의 숫자는 **우리가 잰 것**이 기본이다.
- 벤더·논문·리더보드 인용은 `(참조: 출처)`를 붙여 구분한다.
- **안 잰 것은 "미측정"이라고 쓴다.** 빈 칸이나 `?`로 채운 결과 표를 만들지 않는다 —
  데이터가 있는 것처럼 보여서 없느니만 못하다.

## 남은 일

1. **KWS 디바이스 측정** — 절차는 준비돼 있고 실행만 남았다
2. **soak(장시간) thermal 측정** — 합격선을 넘긴 71.4 °C의 지속 거동 확인
3. Vision 외 세 라인의 측정값을 JSON으로 남기기 (현재는 history 문서 안에만 있다)

---

**작자**: DongHee Kim (한성대) | **리포**: `donghee-ai/unoq-edge-ai-lines` (Private)
