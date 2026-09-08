# UNO Q Edge AI Lines

> **Arduino UNO Q (Qualcomm QRB2210, Cortex-A53 ×4, NPU 없음)** 위에서
> **Vision · ASR · Pose · KWS** 추론 라인을 CPU만으로 돌린 PoC + 실측 기록.
> 이 중 Pose 자산으로 만든 제품 라인은 별도 리포
> [`health_care_bot`](https://github.com/donghee-ai/health_care_bot)에 있다.

**메인 사용처**: 헬스케어 봇 — 스쿼트 자세 측정 + 카운팅 + 음성 인터랙션
**시연 모드**: 감시 모드 (같은 keypoint 신호의 다른 해석)
**현재 버전**: `v0.1.0` (2026-06-29, 첫 GitHub release)

---

## 1차 PoC 합격 측정 (2026-06-27)

**아래 수치는 전부 이 디바이스에서 우리가 직접 측정한 값이다.** 벤더 발표치나 논문 수치가
아니다. 측정 방법과 원본 JSON은 각 라인의 `docs/` · `benchmarks/`에 있다.

Vision · ASR · Pose 3 라인이 디바이스에서 합격선 통과. KWS는 후보 선정 단계:

| 라인 | 모델 | 크기 | e2e | 비고 |
|---|---|---|---|---|
| **Vision** | YOLOv8n int8 TFLite | 3.19 MB | **9.23 FPS** | thermal 70.8°C |
| **ASR** | Whisper Tiny.en TFLite (partial int8) | 39.7 MB | **3.18 s** | JFK wav 6/7 단어 정확 |
| **Pose** | MoveNet Thunder INT8 TFLite | 6.80 MB | **9.69 FPS** | 스쿼트 13 rep 카운팅 + 무릎 각도 |
| KWS | MLPerf Tiny DS-CNN INT8 | 52 KB | **미측정** | 후보 선정만 완료, 디바이스 실측 전 → [`kws/`](kws/) |

합격 기준 (Vision/ASR/Pose 공통): e2e FPS ≥ 8, RSS ≪ 2.4 GB, thermal ≤ 70°C, dropped frames = 0

> **수치 표기 규칙** — 이 리포의 표에 들어가는 숫자는 **우리가 잰 것**이 기본이다.
> 벤더·논문·리더보드가 발표한 값을 인용할 때는 `(참조: 출처)`를 붙여 우리 실측과
> 구분한다. 아직 안 잰 것은 비워두거나 **미측정**이라고 적는다.

## 기술 스택

| 구성 | 기술 |
|---|---|
| 디바이스 | Arduino UNO Q (QRB2210, Cortex-A53 ×4 @ 2.0 GHz, 4 GB LPDDR4, 32 GB eMMC) |
| **NPU/GPU** | **없음 — CPU only** (XNNPACK delegate) |
| 추론 런타임 | `ai-edge-litert` (TFLite Runtime) 2.1.5 |
| 컨테이너 | Docker (Ubuntu 22.04, Python 3.10) — 호스트 검증용 |
| 카메라 | USB UVC (SU200 720p) |
| MCU (계획) | STM32U585 — 서보 PTZ + LED ring |

## 작품 구조 (Monorepo)

```
unoq-edge-ai-lines/
├── vision/                       Vision YOLOv8n int8 라인
│   ├── docker/   docs/   models/   scripts/   src/
├── asr/                          ASR Whisper Tiny.en 라인
│   ├── docker/   docs/   models/   scripts/   src/
├── pose/                         Pose MoveNet Thunder + 스쿼트 카운터
│   ├── docker/   docs/   models/   scripts/
│   └── ptz/                      PTZ PoC (Shawn Hymel fork, MIT)
│       ├── python/   sketch/
├── kws/                          KWS DS-CNN 라인 (후보 선정 완료, 실측 전)
│   ├── docker/   docs/   models/   scripts/
├── device-deploy/                디바이스에 올리는 런타임 묶음
└── README.md                     (본 문서)
```

각 라인은 **자체 docs/ 가이드 + history (작업 기록) + issues (함정 모음)** 포함.

## 빌드 + 실행 — 라인별

```bash
# Vision YOLO 라인
cd vision && bash docker/run-vision.sh

# ASR Whisper 라인
cd asr && bash docker/run-asr.sh

# Pose MoveNet 라인 (스쿼트 카운터 포함)
cd pose && bash docker/run-pose.sh
```

자세한 진입 절차:
- [`vision/docs/01_host_environment_setup.md`](vision/docs/01_host_environment_setup.md)
- [`asr/docs/02_quickstart_asr.md`](asr/docs/02_quickstart_asr.md)
- [`pose/docs/02_quickstart_pose.md`](pose/docs/02_quickstart_pose.md)

## 디바이스 운영 — 이중 모드

USB-C 1포트 + 허브 토폴로지 제약으로 2 모드 분리:

| 모드 | 토폴로지 | 용도 |
|---|---|---|
| **ADB** | PC ↔ USB-C ↔ UNO Q (직접) | 자동화, 모델 push, 자료 회수 |
| **SSH** | UNO Q ↔ 허브 ↔ 카메라/마이크. PC는 LAN | 카메라 라이브, HTTP MJPEG 디버그 |

자세히: [`vision/docs/history/2026-06-25_03_usb_topology_decision.md`](vision/docs/history/2026-06-25_03_usb_topology_decision.md)

## 라이선스

| 구성 | 라이선스 |
|---|---|
| 본 작품 코드 | 미설정 (Apache-2.0 권장 — 후속 release 시 추가) |
| Vision YOLOv8n | AGPL-3.0 (Ultralytics) — 상업화 시 검토 필요 |
| ASR Whisper Tiny.en | MIT (OpenAI) |
| Pose MoveNet Thunder | Apache-2.0 (code) + CC BY 4.0 (model weights) — Google |
| PTZ PoC (`pose/ptz/`) | MIT (Shawn Hymel) — [원본](https://github.com/ShawnHymel/face-expression-detection-robot) |
| 의존 라이브러리 (`ai-edge-litert`, `numpy`, `opencv`, `scipy`) | Apache-2.0 / BSD-3 |

본 작품 시연/사내 범위에선 라이선스 호환. 상업 배포 단계 진입 시 vision YOLO 교체 또는 상용 라이선스 검토.

## 버전 로드맵

| 버전 | 시점 | 주요 변경 |
|---|---|---|
| **v0.1.0** ★ | **2026-06-29 (현재)** | 첫 GitHub release — 3 라인 PoC + monorepo + docs |
| v0.2.0 | 다음 사이클 | PTZ PoC 검증 + Pose A+B+C 다중 신호 카운터 |
| v0.3.0 | 후속 | ASR Whisper → KWS 교체 (인터럽트 지원) |
| v0.4.0 | 후속 | 하우징 시제품 + STM32U585 통합 |
| **v1.0.0** | **본 작품 마감** | 첫 stable release — 시연 가능 |

자세한 버전 규칙: [`pose/docs/07_versioning.md`](pose/docs/07_versioning.md)

## 본 작품 특징 (리뷰 미팅 결정, 2026-06-27)

- **NPU 없는 CPU 환경**에서 3 라인 동시 운영 가능성 입증 (Qualcomm 보고용)
- **AI Hub precompiled QNN ONNX 비호환** 정량 진단 + TFLite 우회 진로
- 본체 자율 추적은 **본 작품 범위 외** — PTZ 서보만 (안전, 단순)
- 메인 = 헬스케어 봇 / 시연 보조 = 감시 모드 (같은 keypoint 다른 해석)
- 하우징 컨셉: 귀여운 캐릭터 or Qualcomm 드래곤 (드래곤윙 프로세서 참조), 파란색 + 흰색

## 자료

| 종류 | 위치 |
|---|---|
| 라인별 청사진 | `vision/docs/00_project_blueprint.md`, `asr/docs/00_*`, `pose/docs/00_*` |
| 알고리즘 가이드 | [`pose/docs/04_squat_algorithm.md`](pose/docs/04_squat_algorithm.md) (스쿼트 카운터 자세) |
| 보고서 | [`pose/docs/05_pose_line_report.md`](pose/docs/05_pose_line_report.md) |
| PTZ PoC 정의 | [`pose/docs/08_ptz_camera_angle_validation.md`](pose/docs/08_ptz_camera_angle_validation.md) |
| 작업 기록 | 각 라인 `docs/history/` (총 19+) |
| 함정 모음 | 각 라인 `docs/issues/` (총 5) |

## 백업

본 작품 monorepo 통합 직전 평행 폴더 3개:
- `c:/Project/backup-2026-06-29/{unoq-companion-robot, unoq-asr, unoq-pose}/`

## 다음 작업 후보

- [ ] PTZ PoC 하드웨어 측정 (Shawn fork 기반)
- [ ] Pose A+B+C 다중 신호 카운터 (측면/후면 카운팅 누락 해결)
- [ ] ASR KWS 모델 후보 검토 + 교체
- [ ] 하우징 3D 프린팅 시제품
- [ ] 시연 영상 녹화 + 포트폴리오 README 보강

---

**작자**: DongHee Kim (한성대) | **레포**: `donghee-ai/unoq-edge-ai-lines` (Private)
