# Improvement Plan — Monorepo Restructure (향후 작업)

본 문서는 현재 `unoq-companion-robot` (vision 라인) + `unoq-asr` (audio 라인, 형제 폴더로 분리 시작) 구성을 향후 단일 monorepo로 통합할 때 적용할 산업 표준 구조와 마이그레이션 계획을 보관합니다. **현재 즉시 작업이 아니며, 통합 시점 트리거 충족 시 본 문서를 참조하여 진행합니다.**

## 0. 핵심 결정 (요약)

| 항목 | 결정 |
|---|---|
| **현재 상태** | 시간 압박으로 `unoq-companion-robot`(vision) + `unoq-asr`(audio) 형제 폴더 임시 분리 |
| **장기 목표** | 단일 monorepo + modality 기반 도메인 분리 (Edge AI 산업 표준) |
| **통합 시점** | fusion 코드 작성, Public 전환, 또는 시연 단일 진입점 필요 시 |
| **예상 작업 시간** | ≈ 1.5 시간 (Phase별 게이트 검증 포함) |
| **롤백 보험** | `git tag pre-monorepo-restructure` 사전 생성 |

## 1. 산업 표준 패턴 — Edge AI / Robotics

본 작품이 따라가야 할 표준 패턴 3가지:

| 패턴 | 출처 | 본 작품 적용 |
|---|---|---|
| **Monorepo + 도메인 분리** | TFLite examples, NVIDIA jetson-inference, ROS 2 workspace | 단일 repo 안에서 vision / audio / fusion 폴더 분리 |
| **Modality 기반 명명** | autonomous driving, robotics 표준 | `vision`(YOLO 교체돼도 유지) / `audio`(KWS·ASR 교체돼도 유지) |
| **공유 layer** (`common/`) | Google monorepo, Bazel | interpreter 로더 · 벤치마크 · JSON 로깅 = vision · audio 공통 |

핵심 원칙: **"모델 이름이 아니라 입력 modality로 명명"** — `yolo/`/`kws/`는 모델이 바뀌면 의미 흐려짐, `vision/`/`audio/`는 작품 수명 전체 유지.

## 2. 현재 분리 상태 (왜 분리했나)

| 이유 | 설명 |
|---|---|
| 시간 압박 | ASR 요구사항 다음 날 보고 — 폴더 정리 1.5 시간이 부담 |
| 도메인 격리 의지 | 사용자가 `yolo` / `asr` 명확히 분리 선호 |
| 의존성 충돌 회피 | librosa / scipy ↔ torch / numpy ABI 충돌 가능성 — 별도 Docker로 사전 차단 |
| 작업 격리 | vision 안정화 상태 보존, audio 실험이 vision 자산 흔들지 않게 |

→ 임시 분리는 합리적이지만, fusion 단계에선 통합 필수. 본 문서는 그 시점의 마이그레이션 계획.

## 3. 목표 통합 구조 (트리)

```
vision/
├── README.md
├── LICENSE                                ← Apache-2.0
├── pyproject.toml                         ← (선택) 패키지화 시
│
├── docker/
│   ├── vision/                            ← 현 Dockerfile + requirements.lock + run.sh
│   ├── audio/                             ← 현 unoq-asr Docker
│   └── runtime/                           ← (선택) 통합 시연용
│
├── src/unoq/
│   ├── common/                            ← interpreter, benchmark, io_json, logging
│   ├── vision/                            ← 현 src/*.py
│   ├── audio/                             ← 현 unoq-asr src
│   └── fusion/                            ← 신규 (vision + audio → MCU)
│
├── models/
│   ├── vision/                            ← yolov8n_int8.tflite 등
│   └── audio/                             ← speech_commands_v2.tflite
│
├── data/                                  ← CCDS 패턴
│   ├── samples/{vision,audio}/
│   ├── golden/{vision,audio}/
│   └── calibration/{vision,audio}/
│
├── benchmarks/
│   ├── vision/
│   └── audio/
│
├── docs/
│   ├── overview/                          ← 작품 전체 청사진 + 운영 + 규약
│   ├── vision/                            ← 현 docs/01~08 이동
│   ├── audio/                             ← 현 asr/docs 이동
│   └── _private_refs/                            ← 대외비, 그대로
│
├── scripts/
│   ├── env.sh
│   ├── setup_device.sh                    ← vision + audio 의존성 통합 설치
│   ├── deploy_vision.sh
│   └── deploy_audio.sh
│
└── tests/
    ├── common/
    ├── vision/
    └── audio/
```

핵심: **docker · src · models · data · benchmarks · docs 6개 영역이 modality 축으로 미러링**. 같은 도메인 자산이 항상 같은 경로에서 보이게.

## 4. 마이그레이션 4 Phase

### Phase 0 — 롤백 보험

```bash
cd unoq-companion-robot
git tag pre-monorepo-restructure
git push --tags
```

### Phase A — Docker 이동

```bash
mkdir -p docker/vision
git mv Dockerfile docker/vision/
git mv requirements.txt docker/vision/
git mv requirements.lock docker/vision/
git mv .dockerignore docker/vision/
git mv run.sh docker/vision/
```

**필수 수정 2건**:

1. `docker/vision/run.sh` 마운트 경로:
   ```bash
   # Before
   docker run -v "$PWD:/work" ...
   # After
   SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
   ROOT="$SCRIPT_DIR/../.."
   docker run -v "$ROOT:/work" ...
   ```

2. `docker/vision/Dockerfile` build context 처리:
   ```bash
   # 호출 방식
   docker build -f docker/vision/Dockerfile docker/vision/
   ```

**게이트 검증**: `bash docker/vision/run.sh` → 컨테이너 진입 + Smoke test 통과.

### Phase B — src 이동

```bash
mkdir -p src/unoq/{common,vision,audio,fusion}
touch src/unoq/__init__.py
touch src/unoq/{common,vision,audio,fusion}/__init__.py
git mv src/*.py src/unoq/vision/
```

import 경로는 같은 폴더 안 이동이라 그대로 동작 (현재 `from postprocess import ...` 식).

**게이트 검증**: `python -m unoq.vision.validate_model models/vision/yolov8n_int8.tflite` 동작.

### Phase C — models / benchmarks / data 이동

```bash
mkdir -p models/{vision,audio}
git mv models/yolov8n_saved_model/yolov8n_int8.tflite models/vision/
git mv models/yolov8n_saved_model/yolov8n_float32.tflite models/vision/
git mv models/yolov8n_saved_model/yolov8n_float16.tflite models/vision/
# yolov8n_saved_model/ 폴더는 SavedModel 메타데이터라 평탄화하지 말고 그대로 둘 수도 있음 — 결정 시 재검토

mkdir -p benchmarks/{vision,audio}
git mv benchmarks/host_e2e_*.json benchmarks/vision/
git mv benchmarks/device_e2e_*.json benchmarks/vision/
git mv benchmarks/cam_*.json benchmarks/vision/
```

### Phase D — docs 이동 + 링크 갱신

```bash
mkdir -p docs/{overview,vision}
git mv docs/00_project_blueprint.md docs/overview/00_project_blueprint.md
git mv docs/03_project_conventions.md docs/overview/01_conventions.md
git mv docs/09_usage_runbook.md docs/overview/02_usage_runbook.md
git mv docs/01_host_environment_setup.md docs/vision/00_host_env.md
git mv docs/02_model_selection_log.md docs/vision/01_model_selection.md
git mv docs/04_device_setup.md docs/vision/02_device_setup.md
git mv docs/05_initial_inference_measurement.md docs/vision/03_initial_measurement.md
git mv docs/06_postprocess_and_e2e.md docs/vision/04_postprocess_e2e.md
git mv docs/07_official_benchmark.md docs/vision/05_official_benchmark.md
git mv docs/08_realtime_camera.md docs/vision/06_realtime_camera.md
# asr/docs/* → docs/audio/* 이동
```

**docs 내부 상대 링크 검토** (~30분):

```bash
grep -rn "docs/0" docs/ README.md
# 결과를 보고 각 링크 갱신
```

### Phase E — README + Audio 통합

```bash
# unoq-asr 폴더 내용을 monorepo로 흡수
git mv ../asr/docs/* docs/audio/
git mv ../asr/src/* src/unoq/audio/
git mv ../asr/docker/* docker/audio/
git mv ../asr/models/* models/audio/
# unoq-asr 폴더 자체 삭제
rm -rf ../unoq-asr
```

## 5. 위험 4지점 + 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| **`run.sh` `$PWD` 마운트** | 컨테이너에 빈 폴더 마운트 → 즉시 깨짐 | `SCRIPT_DIR` 패턴으로 수정 (Phase A) |
| **Dockerfile COPY 경로** | 빌드 실패 | build context를 `docker/vision/`으로 명시 (Phase A) |
| **docs 내부 상대 링크** | 죽은 링크 다수 | Phase D에서 grep + 수동 갱신 |
| **README 링크** | 외부 진입자 혼동 | Phase D 마지막에 README 검토 |

영향 없음 (자동 처리): import 경로(같은 폴더 이동), 디바이스 측 코드(평탄 구조 유지), git history(`git mv`로 보존), `.gitignore` 패턴.

## 6. 통합 시점 트리거

다음 중 **하나 이상** 충족 시 본 계획 발동:

1. **fusion 코드 작성 시점** — vision 결과 + audio 결과를 호스트에서 동시 시뮬레이션 필요
2. **Public 전환 / 시연** — 외부에 단일 진입점(`bash docker/run-vision.sh`) 제공
3. **CI/CD 구축** — 통합 빌드로 vision + audio 회귀 테스트
4. **최종 인계** — 한 묶음 작품으로 정리

현 단계(KWS PoC + 안정화)에선 트리거 미충족 → 분리 유지가 정답.

## 7. 재현성 검증 체크리스트 (Phase D 완료 후)

마이그레이션 commit 직전 6가지 동작 확인:

| # | 명령 | 기대 결과 |
|---|---|---|
| 1 | `bash docker/vision/run.sh` | 컨테이너 진입 성공 |
| 2 | (컨테이너) `python -m unoq.vision.validate_model models/vision/yolov8n_int8.tflite` | 호스트 baseline 80 FPS 동일 |
| 3 | `scp src/unoq/vision/validate_model.py arduino@192.168.0.45:~/` | 전송 성공 |
| 4 | (디바이스) `python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite` | 9.88 FPS 동일 |
| 5 | `git archive HEAD -o test.zip README.md docs/` | 압축 성공, _private_refs/SESSION 제외 |
| 6 | README + docs 내부 링크 클릭 | 모두 살아있음 |

6개 다 통과해야 commit. 1개라도 실패 시 `git reset --hard pre-monorepo-restructure`로 롤백.

## 8. 디바이스 측 영향

| 영역 | 영향 | 비고 |
|---|---|---|
| `~/venv-unoq` | 변경 없음 | 호스트 정리는 디바이스 venv와 무관 |
| `/opt/unoq-yolo/` | 변경 없음 (또는 `/opt/unoq-companion/`으로 리네임 — 별도 결정) | 디바이스 측 경로 변경은 ssh + sudo mv 추가 작업 |
| 디바이스 측 .py 파일 | 평탄 구조 유지 (`~/validate_model.py` 등) | scp 호스트 측 경로만 변경, 디바이스 쪽은 그대로 |
| 9.23 FPS 재측정 | 동일 결과 기대 | 코드 변경 없음 |

→ **디바이스 측은 마이그레이션 영향 0**. 호스트 측 정리만으로 충분.

## 9. 작업 시간 예상

| Phase | 작업 | 시간 |
|---|---|---|
| 0 | git tag | 1분 |
| A | docker/ 이동 + run.sh / Dockerfile 수정 + 게이트 검증 | 20분 |
| B | src/ 이동 + `__init__.py` + 게이트 검증 | 15분 |
| C | models / benchmarks / data 이동 | 10분 |
| D | docs 이동 + 상대 링크 갱신 + 게이트 검증 | 30분 |
| E | unoq-asr 흡수 | 10분 |
| 재현성 검증 (6 체크) | 10분 |
| README 갱신 + commit | 10분 |
| **합계** | | **약 1.5 시간** |

## 10. 본 문서 위치 선정 근거

- **`vision/docs/`에 보관** — 통합 후엔 `unoq-companion-robot`이 monorepo 루트가 되므로 본 문서가 그 안에 있어야 자연스러움
- 통합 작업 진행 시 본 문서를 그대로 참조 + 완료 후 `docs/overview/`로 이동 또는 SESSION_SUMMARY로 회수

## 11. 미반영 / 향후 결정 사항

| 항목 | 결정 보류 사유 |
|---|---|
| `pyproject.toml` 도입 | 임베디드 단일 작품엔 over-engineering 가능 — fusion 코드 작성 시 재검토 |
| 디바이스 측 `/opt/unoq-yolo/` 리네임 | 디바이스 측 작업 비용 + 9.23 FPS 측정 자산 경로 의존 — 통합 시점에 별도 결정 |
| `docker/runtime/` 통합 컨테이너 | 분리 유지가 더 안전 — Public 전환 시점에만 결정 |
| `tests/` pytest 도입 | 현재 측정 스크립트 중심이라 후순위 — Prototype 단계(4~6주) 권장 |

## 한 줄 요약

> **현재 형제 폴더 분리는 시간 압박에 의한 임시 결정. fusion 코드 / Public 전환 / 시연 단일 진입점 중 하나라도 필요해지면 본 계획 발동 — 약 1.5 시간 + Phase별 게이트 검증으로 안전 통합 가능.**
