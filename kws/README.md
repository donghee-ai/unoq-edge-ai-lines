# UNO Q KWS 라인 — 음성 키워드 모드 스위칭

**목적**: Pose 모델과 동시 동작하는 KWS (Keyword Spotting) 로 **모드 스위칭 인터럽트** 제공. 사용자 발화("stop", "up", "down", ...) 또는 물리 버튼으로 헬스케어 봇의 운동 모드를 즉시 전환.

## 위치

```
kws/                              ← 본 라인 루트
├── docker/                       호스트 개발 환경 (Ubuntu 22.04 + ai-edge-litert + sounddevice)
├── docs/                         청사진 + 모델 후보 + 실행 가이드
│   ├── 00_project_blueprint.md   ★ 시작점
│   ├── 01_model_candidates.md    라이선스 비교 + 채택 근거
│   ├── 02_quickstart_kws.md      호스트 → 디바이스 원샷 실행
│   ├── 03_ssh_to_benchmark_walkthrough.md  ★ SSH 접속 → 벤치마크 회수 (사용자 요청)
│   ├── 04_mode_interrupt_architecture.md   인터럽트 이벤트 버스 설계
│   └── 05_button_wiring.md       GPIO 버튼 배선 + 커널 인터페이스
├── models/                       KWS TFLite 모델 (git 제외)
├── scripts/                      Python 진입점 + worker + 벤치마크
└── benchmarks/                   JSON 측정 결과
```

## 30초 요약

| 항목 | 값 |
|---|---|
| 1순위 모델 | MLPerf Tiny KWS **DS-CNN INT8** (Apache-2.0, 52 KB, 12 클래스) |
| 2순위 fallback | Google TFLM **MicroSpeech** (Apache-2.0, 18 KB, 4 클래스) |
| 런타임 | `ai-edge-litert` + XNNPACK — pose 라인과 동일 stack |
| 예상 latency (QRB2210, threads=1) | ~10~30 ms (모델 크기 비례) |
| 오디오 프론트엔드 | MFCC 10 or 40 계수, sr=16kHz, 40ms/20ms window/hop |
| 인터럽트 대상 | Pose 모델 실행 중 → 모드 전환 (SQUAT ↔ PUSHUP ↔ IDLE ↔ SURVEIL) |
| Fallback | GPIO 버튼 (short=cycle / long=stop) |

## 진입 순서

1. **[docs/00_project_blueprint.md](docs/00_project_blueprint.md)** — 라인 목적/합격선/구조
2. **[docs/01_model_candidates.md](docs/01_model_candidates.md)** — 왜 이 모델을 골랐나
3. **[docs/02_quickstart_kws.md](docs/02_quickstart_kws.md)** — 처음 실행 (호스트 + 디바이스)
4. **[docs/03_ssh_to_benchmark_walkthrough.md](docs/03_ssh_to_benchmark_walkthrough.md)** — SSH 접속 → 벤치마크 회수 전 과정
5. **[docs/04_mode_interrupt_architecture.md](docs/04_mode_interrupt_architecture.md)** — Pose 통합 설계
6. **[docs/05_button_wiring.md](docs/05_button_wiring.md)** — 하드웨어 버튼 배선

## 관련 라인

- Pose (통합 대상): [`../pose/`](../pose/) — MoveNet Thunder INT8, 9.69 FPS
- ASR (기존, Whisper 대체 예정): [`../asr/`](../asr/) — 본 라인은 ASR **경량화 후속**
- 결정 근거: [`../asr/docs/history/2026-06-27_02_mentor_meeting_lightweight_model_and_interrupt_decision.md`](../asr/docs/history/2026-06-27_02_mentor_meeting_lightweight_model_and_interrupt_decision.md)

## v0.3.0 트랙

본 라인은 [`../pose/docs/07_versioning.md`](../pose/docs/07_versioning.md) 기준 **v0.3.0** 목표 — ASR Whisper → KWS 교체 + 인터럽트.
