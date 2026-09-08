# 측정 결과 — NPU 없는 QRB2210에서 얼마나 나오나

이 리포의 본론입니다. **여기 있는 숫자는 전부 UNO Q 실기에서 우리가 직접 잰 값**이고,
벤더 발표치나 논문 수치는 하나도 섞여 있지 않습니다.

- 측정 대상: Arduino UNO Q — Qualcomm Dragonwing QRB2210, Cortex-A53 ×4 @ 2.0 GHz,
  4 GB LPDDR4. **NPU/GPU 델리게이트 없음, CPU only** (`ai-edge-litert` + XNNPACK)
- 합격선: e2e FPS ≥ 8 · RSS ≪ 2.4 GB · thermal ≤ 70 °C · dropped frames = 0
- 재현 방법: [`01_device_setup.md`](01_device_setup.md)

## 0. 한 눈에

| 라인 | 모델 | 크기 | e2e | 결과 |
|---|---|---|---|---|
| Vision | YOLOv8n int8 TFLite | 3.19 MB | **9.23 FPS** | 합격 |
| Pose | MoveNet Thunder INT8 TFLite | 6.80 MB | **9.69 FPS** | 합격 |
| ASR | Whisper Tiny.en TFLite (DRQ) | 39.7 MB | **3.18 s** (11초 오디오) | 합격 |
| KWS | MLPerf Tiny DS-CNN INT8 | 52 KB | **미측정** | 후보 선정만 완료 |

**결론 한 줄** — NPU 없이 A53 4코어만으로 객체검출·포즈추정이 각각 9 FPS대, 11초 음성
전사가 3.2초. 셋 다 invoke(추론)가 병목이고 나머지 단계는 전부 합쳐도 20 % 남짓이다.

## 1. Vision — YOLOv8n int8

원본: [`vision/benchmarks/device_e2e_20260623.json`](../vision/benchmarks/device_e2e_20260623.json)
(호스트 대조군은 `host_e2e_20260623.json`)

100 프레임, warmup 10, `ai_edge_litert` 4 threads.

| 항목 | 값 |
|---|---|
| fps_mean | **9.23** |
| latency p50 / p95 | 105.0 ms / 132.7 ms |
| max_rss_mb | 100.8 |
| max_temp_c | 60.5 |
| dropped_frames | 0 |

### 1-1. 단계별 분해 — invoke가 86 %

| 단계 | mean | p50 | p95 |
|---|---|---|---|
| preprocess | 5.42 ms | 6.04 | 6.59 |
| **inference** | **93.28 ms** | **90.71** | **120.21** |
| postprocess | 5.08 ms | 5.08 | 5.60 |
| draw | 3.90 ms | 3.88 | 4.17 |
| **total** | **108.36 ms** | 105.02 | — |

전처리·후처리·드로잉을 다 합쳐도 14.4 ms로 전체의 13 %다. **화면을 꺼도 FPS는 거의
안 오른다** — 이 분해가 그 근거다.

## 2. Pose — MoveNet Thunder INT8

1,320 프레임 / 136.2 초 연속 카메라 구동. 원본 기록:
[`pose/docs/history/2026-06-27_04_pose_camera_e2e_pass.md`](../pose/docs/history/2026-06-27_04_pose_camera_e2e_pass.md)

| 항목 | 측정 | 합격선 | 평가 |
|---|---|---|---|
| fps_effective | **9.69** | ≥ 8 | 21 % 여유 |
| dropped_frames | **0** | — | 카메라 캡처 손실 없음 |
| cpu_peak_pct (프로세스) | **316.3** | — | 4 코어 중 79 %씩 사용 |
| rss_peak_mb | **95.0** | ≪ 2.4 GB | — |
| temp_peak_c | **68.6** | ≤ 70 | 1.4 °C 여유 |

invoke만 따로 재면 **80.3 ms (p50)** / 12.5 FPS. e2e 103 ms와의 차이 23 ms가 캡처·
letterbox·후처리·draw·JPEG 인코딩·HTTP 서빙 전부다. **invoke 78 %.**

> **thermal은 여유가 없다.** 위 68.6 °C는 136초 측정값이고, 장시간 구동에서는
> **71.4 °C까지 올라 합격선 70 °C를 1.4 °C 넘겼다** —
> [`04_traps.md`](04_traps.md) §5. soak 측정은 아직 안 했다.

## 3. ASR — Whisper Tiny.en (DRQ)

JFK 1961 취임 연설 11초 wav. 원본 기록:
[`asr/docs/history/2026-06-27_01_whisper_quantization_actual_form_confirmed.md`](../asr/docs/history/2026-06-27_01_whisper_quantization_actual_form_confirmed.md)

| 항목 | 값 |
|---|---|
| e2e | **3.18 초** (합격선 ≤ 5 초) |
| 정확도 | 7 단어 중 6 개 일치 |
| 모델 크기 | 39.7 MB |

### 3-1. "int8"이 아니었다 — 실측으로 밝힌 것

받아온 파일이 int8이라고 알려져 있었는데, 텐서를 직접 열어보니 아니었다.

| 확인 | 결과 |
|---|---|
| 입력 `serving_default_input_ids:0` | `[1,80,3000]` **float32**, qparams 비어 있음 |
| 출력 `StatefulPartitionedCall:0` | `[1,448]` **int32**, qparams 비어 있음 |
| int8 텐서 비율 | 76 개 = 전체의 **6.8 %** (일부 큰 weight matrix만) |

크기별 대조표로 역산하면 fp32 ~150 MB / fp16 ~75 MB / **DRQ ~40 MB** / full int8 ~10 MB.
실측 39.7 MB + dtype 분포가 DRQ와 정확히 맞는다 → **weight-only int8 (Dynamic Range
Quantization)** 확정.

**모델 카드를 믿지 말고 텐서를 열어볼 것.** 이 리포에서 가장 재사용 가치가 높은 교훈이다.

## 4. KWS — 미측정

후보 선정과 라이선스 검토만 끝났다([`03_model_choice.md`](03_model_choice.md) §3).
디바이스 latency·RSS·thermal·오탐률은 **아직 재지 않았다.** 측정 절차와 합격 기준은
[`kws/docs/03_ssh_to_benchmark_walkthrough.md`](../kws/docs/03_ssh_to_benchmark_walkthrough.md) §10에 있다.

측정하면 값은 `kws/benchmarks/`의 JSON에 남기고 이 문서 §0 표를 갱신한다.

## 5. 라인 간 비교

| 항목 | Vision (YOLOv8n) | Pose (Thunder) |
|---|---|---|
| e2e FPS | 9.23 | 9.69 |
| invoke p50 | 90.7 ms | 80.3 ms |
| invoke 비중 | 86 % | 78 % |
| RSS peak | 100.8 MB | 95.0 MB |

모델 크기는 2배 차이(3.19 vs 6.80 MB)인데 **속도는 Pose가 오히려 빠르다.** 파일 크기가
추론 시간을 예측하지 못한다는 실증이다 — 연산량과 연산자 구성이 결정한다.

## 6. 이 숫자들을 읽을 때

- **thermal 표기가 문서마다 다르다.** vision JSON은 60.5 °C, 루트 README는 70.8 °C로
  적혀 있는데 서로 다른 런이다. 지속 구동에서 71.4 °C까지 간 기록이 별도로 있다
  (§2 주석). soak 측정을 하기 전까지 thermal은 "합격선 근처"로만 읽을 것.
- **CPU % 는 4코어 합산 기준**이다. 316 % = 코어당 79 %.
- **KWS 열은 비어 있는 게 맞다.** 안 쟀으니 안 쓴다.

## 7. 원본 자료 위치

| 라인 | 원본 |
|---|---|
| Vision | [`vision/benchmarks/*.json`](../vision/benchmarks/) — 유일하게 기계 판독 가능한 원본 |
| Pose | `pose/docs/history/2026-06-27_03`, `_04` |
| ASR | `asr/docs/history/2026-06-27_01` |
| KWS | 없음 (미측정) |

> Vision을 뺀 나머지는 측정값이 history 문서 안에만 있고 JSON 산출물이 없다.
> 다시 측정할 일이 있으면 `--json` 저장을 꼭 켤 것.
