# 2026-06-29 — Vision docker/ 폴더 신규 + 3 라인 도커 호환성 점검

## 시점
2026-06-29 (monorepo 통합 직후, 도커 구조 일관성 정리)

## 사건
Vision 라인은 docker 파일들이 root에 있었고(`vision/Dockerfile`, `vision/run.sh`), asr/pose는 이미 `docker/` 하위였음. 일관성 위해 vision도 `vision/docker/` 폴더로 재구성. 동시에 3 라인 모두 monorepo 변경 후 도커 동작 영향 점검.

## 작업

### 1. Vision docker/ 폴더 신규

```
vision/
├── docker/                     (신규)
│   ├── Dockerfile.vision       (구 Dockerfile, rename)
│   ├── requirements.lock       (구 root에서 이동)
│   ├── requirements.txt        (동일)
│   └── run-vision.sh           (구 run.sh, rename + SCRIPT_DIR 패턴으로 재작성)
├── README.md
├── docs/  models/  scripts/  src/  ...
```

| 변경 | 처리 |
|---|---|
| `vision/Dockerfile` → `vision/docker/Dockerfile.vision` | git mv (history 보존) + rename |
| `vision/run.sh` → `vision/docker/run-vision.sh` | git mv + rename + 내용 재작성 (SCRIPT_DIR 패턴) |
| `vision/requirements.lock,txt` → `vision/docker/` | git mv |

### 2. run-vision.sh 재작성 — SCRIPT_DIR 패턴

옛 패턴 (`PROJECT_ROOT = dirname(BASH_SOURCE)`)은 run.sh가 root에 있어야 vision/이 PROJECT_ROOT. docker/ 안으로 이동 시 PROJECT_ROOT가 vision/docker/로 잘못 잡힘.

새 패턴 (asr/pose와 동일):
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # vision/docker/
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"               # vision/
docker build -f "${SCRIPT_DIR}/Dockerfile.vision" -t ... "${SCRIPT_DIR}"   # build context = docker/
docker run -v "${PROJECT_ROOT}:/work" ...                                  # mount = vision/
```

→ build context = `vision/docker/` (Dockerfile + requirements 위치) / mount = `vision/` (소스/모델/docs).

### 3. vision docs 갱신 — 옛 `bash run.sh` 참조 일괄

8 파일 갱신:
- `README.md`
- `SESSION_SUMMARY_2026-06-24.md`
- `docs/00_project_blueprint.md`
- `docs/01_host_environment_setup.md`
- `docs/05_initial_inference_measurement.md`
- `docs/07_official_benchmark.md`
- `docs/09_usage_runbook.md`
- `docs/improvement_monorepo_restructure.md`

PowerShell 일괄 치환:
```
`bash run.sh`        → `bash docker/run-vision.sh`
`bash run.sh --rebuild` → `bash docker/run-vision.sh --rebuild`
`../../run.sh`        → `../../docker/run-vision.sh`
```

잔여 `bash run.sh` 0건 확인.

### 4. ASR/Pose 도커 점검 — 변경 불필요

| 라인 | docker 폴더 | run script | Dockerfile | monorepo 영향 |
|---|---|---|---|---|
| vision | docker/ (이번 신규) | run-vision.sh (이번 신규) | Dockerfile.vision (이번 rename) | ✓ SCRIPT_DIR 패턴으로 강건 |
| asr | docker/ (기존) | run-asr.sh (기존) | Dockerfile.asr (기존) | ✓ **영향 없음** |
| pose | docker/ (기존) | run-pose.sh (기존) | Dockerfile.pose (기존) | ✓ **영향 없음** |

ASR/Pose run script가 이미 SCRIPT_DIR/PROJECT_ROOT 상대경로 패턴 → monorepo sub-folder로 이동해도 자동 강건. mount = `PROJECT_ROOT` (라인 폴더 = asr/ 또는 pose/), build context = `SCRIPT_DIR` (docker/). 코드 변경 X.

### 5. 3 라인 일관 구조

```
vision/docker/Dockerfile.vision  + run-vision.sh
asr/docker/Dockerfile.asr        + run-asr.sh
pose/docker/Dockerfile.pose      + run-pose.sh
```

→ 외부 진입자가 한 라인 docker 패턴 알면 모든 라인 동일하게 운영 가능.

## 검증

| 항목 | 상태 |
|---|---|
| vision/docker/ 신규 폴더 | ✓ 4 파일 (Dockerfile.vision, requirements.lock, requirements.txt, run-vision.sh) |
| SCRIPT_DIR 패턴 일관 | ✓ 3 라인 동일 |
| 옛 `bash run.sh` 잔여 | ✓ 0건 |
| Docker image 이름 | 변경 X (`unoq-yolo-dev:22.04`, `unoq-asr-dev:22.04`, `unoq-pose:22.04`) — rebuild 불필요 |
| Dockerfile COPY 경로 | ✓ 새 build context (docker/)에서 requirements 찾음 — 정상 |

## 실제 docker build/run 검증 — 사용자 측

본 사이클은 **코드 분석으로 확인**. 실제 빌드/실행 검증은 사용자가 디바이스 사용 시:

```bash
# vision
cd /c/Project/unoq-companion-robot/vision && bash docker/run-vision.sh
# asr
cd /c/Project/unoq-companion-robot/asr && bash docker/run-asr.sh
# pose
cd /c/Project/unoq-companion-robot/pose && bash docker/run-pose.sh
```

위 명령 동작 = monorepo 통합 + docker 재구성 성공. 문제 발견 시 백업(`c:\Project\backup-2026-06-29\`)으로 복원 가능.

## 영향

| 항목 | 영향 |
|---|---|
| Docker image (이미 빌드됨) | 변경 X — 이름 유지, rebuild 불필요 |
| 사용자 명령 변경 | `bash run.sh` → `bash docker/run-vision.sh` (vision만) |
| asr/pose 운영 | 변경 없음 — 기존 명령 그대로 |
| 외부 진입자 | 3 라인 일관 패턴으로 학습 비용 ↓ |

## 관련

- monorepo 통합: [`2026-06-29_02_monorepo_restructure.md`](2026-06-29_02_monorepo_restructure.md)
- PTZ/Pose 분리 진로: [`2026-06-29_03_ptz_pose_integration_path_documented.md`](2026-06-29_03_ptz_pose_integration_path_documented.md)
