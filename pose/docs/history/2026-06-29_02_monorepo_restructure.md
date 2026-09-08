# 2026-06-29 — Monorepo 통합 (vision/asr/pose sub-folders)

## 시점
2026-06-29 (PTZ PoC 코드 골격 직후, 본 작품 전체 구조 통합)

## 사건
3 라인(vision/asr/pose)을 각자 별도 폴더로 운영하던 평행 구조 → **단일 monorepo**로 통합. 기존 vision 레포(`donghee-ai/unoq-companion-robot`)를 작품 루트로 활용, asr/pose를 sub-folder로 통합.

## 결정 근거

| 가치 | 효과 |
|---|---|
| 본 작품 = 'UNO Q 교감로봇' 단일 작품 정체성 | 라인은 sub-system, 작품은 하나 |
| 단일 URL (포트폴리오/보고) | `donghee-ai/unoq-companion-robot` 하나로 모든 라인 접근 |
| cross-line 참조 깔끔 | `pose/docs/.../...` → `../../vision/docs/...` 자연스러움 |
| 통합 versioning | 작품 전체 v1 / v1-monorepo / 향후 v1.x |
| git history 보존 | vision은 git mv로 옛 commit 유지 |
| 백업 안전망 | `c:\Project\backup-2026-06-29\` 평행 폴더 보존 |

## 작업 결과

### 폴더 구조
```
c:\Project\unoq-companion-robot\          ← monorepo 루트
├── .git/
├── vision/    (578 파일) — 구 unoq-companion-robot 자료, YOLOv8n int8
├── asr/       (36 파일)  — 구 unoq-asr, Whisper Tiny.en TFLite
└── pose/      (51 파일)  — 구 unoq-pose, MoveNet Thunder INT8 + 스쿼트 카운터 + ptz/
```

### git tag

| tag | commit | 의미 |
|---|---|---|
| `v1` | `3fbfd8f` (옛 merge) | vision-only 시점 (2026-06-23 합격 측정) |
| **`v1-monorepo`** | `e231a61` | 본 통합 사이클 (3 라인 단일 레포) |

후속 tag 후보:
- `v1.1-ptz-poc` — PTZ 검증 결과 따라
- `v2` — ASR KWS 교체 / 하우징 통합 등

### 파일 변경

| 작업 | 결과 |
|---|---|
| 백업 | `c:\Project\backup-2026-06-29\` (3 폴더 통째, 총 136 MB) |
| vision git mv | benchmarks/, docs/, scripts/, src/ 등 (history 보존) |
| asr/pose cp | git 미추적이라 단순 복사, monorepo에 git add |
| cross-line refs (md) | 29 파일 — `unoq-X/` → `X/` 일괄 |
| cross-line refs (py/sh/yaml) | 7 파일 — 동일 |
| 절대 경로 (WSL + Windows) | asr/pose만 갱신 (`/mnt/c/Project/unoq-asr` → `/mnt/c/Project/unoq-companion-robot/asr` 등) |
| 메모리 갱신 | `project_unoq_companion_robot.md`, `feedback_issues_history_workflow.md`, `reference_unoq_github.md` |

### 의도적 보존 (변경 X)

| 항목 | 이유 |
|---|---|
| `unoq-asr-dev`, `unoq-pose:22.04` 등 Docker image 이름 | 실제 image tag, 변경 시 rebuild 필요 |
| `unoq-mediapipe-pose` 옛 폴더명 | rename 함정 기록 (issues/2026-06-27_02) |
| 라인 정체성 표현 ("unoq-asr 모듈") | 라인명, 경로 아님 |
| vision/docs 안 `/mnt/c/Project/unoq-companion-robot` | monorepo 루트와 이름 동일, 의미 호환 |

## GitHub push 미진행

본 사이클은 **로컬 commit + tag만**. GitHub `donghee-ai/unoq-companion-robot` 레포에 push는 사용자 결정 후 별도 진행.

push 명령 (준비됨):
```bash
cd /c/Project/unoq-companion-robot
git push origin main --tags
```

## 백업 정리 결정 보류

`c:\Project\backup-2026-06-29\` (136 MB)는 안전망. monorepo 안정 확인 후 정리 결정.

## 본 작품 메인 라인 영향

**없음** — 모든 라인 코드/모델/docs 그대로. 폴더 위치만 monorepo 안 sub-folder로 이동. 디바이스(UNO Q)는 영향 없음 (디바이스 측 path는 `/home/arduino/...` 그대로).

## 다음 단계

| # | 작업 |
|---|---|
| 1 | GitHub push (`git push origin main --tags`) — 사용자 결정 후 |
| 2 | 작품 전체 README v1 작성 (monorepo 루트, 3 라인 소개) |
| 3 | 작품 통합 docs (`docs/00_project_blueprint.md` 작품 루트 레벨) |
| 4 | 백업 정리 (`c:\Project\backup-2026-06-29\`) — 안정 확인 후 |
| 5 | Pose 라인 PTZ PoC 진행 또는 다른 라인 작업 |

## 관련

- PTZ PoC 코드 골격 (직전): [`2026-06-29_01_ptz_poc_code_skeleton_created.md`](2026-06-29_01_ptz_poc_code_skeleton_created.md)
- 리뷰 미팅 결과 (monorepo 결정 영향): [`2026-06-27_11_review_meeting_outcomes.md`](2026-06-27_11_review_meeting_outcomes.md)
- 버전관리 가이드: [`../07_versioning.md`](../07_versioning.md)
- 사전 검토 (vision 라인에 있었던): `../../vision/docs/improvement_monorepo_restructure.md` (참고)
