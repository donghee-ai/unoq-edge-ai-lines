# 버전관리 (작품 전체)

본 문서는 본 작품 전체(monorepo)의 semver 버전 부여 규칙 + 현재 베이스라인 + 계획된 후속 버전. 2026-06-29 monorepo 통합 + 단일 버전 패턴(A) 채택.

## 0. 현재 — v0.1.0 (2026-06-29 첫 GitHub release)

`MAJOR.MINOR.PATCH` semver 표준.

| 항목 | v0.1.0 시점 상태 |
|---|---|
| 구조 | Monorepo — `vision/`, `asr/`, `pose/` sub-folders |
| **Vision** | YOLOv8n int8 TFLite, e2e 9.23 FPS, thermal 70.8°C |
| **ASR** | Whisper Tiny.en TFLite, e2e 3.18 s, 6/7 단어 정확 |
| **Pose** | MoveNet Thunder INT8 TFLite, e2e 9.69 FPS, 13 rep 카운팅 |
| 디바이스 | Arduino UNO Q (QRB2210, Cortex-A53 ×4) |
| docs | 라인별 가이드 + history 19 + issues 5 + 보고서 1 |
| 진행 안 됨 | PTZ 하드웨어 측정, 하우징, ASR KWS 교체, 시연 영상 |

→ semver 0.x = "활발한 개발 중, breaking 가능". 본 작품 마감(1.0.0)까지 추가 진행 예정.

## 1. semver 적용 규칙 (본 작품)

| 변경 | MAJOR | MINOR | PATCH |
|---|---|---|---|
| 모델 교체 (Whisper → KWS 등), 입출력 형식 변경, 디바이스 변경 | **+1** | reset 0 | reset 0 |
| 새 기능 추가 — PTZ 통합, 다중 신호 카운터, 새 모드 | — | **+1** | reset 0 |
| 버그 수정 / 함정 fix / docs 갱신 / 측정 누적 | — | — | **+1** |

`v1.0.0` 도달 = 본 작품 마감 = 시연 가능 stable. 그 전까지 `v0.x.y`.

## 2. 계획된 후속 버전 (단일 버전 패턴 A)

| 버전 | 시점 | 주요 변경 |
|---|---|---|
| **v0.1.0** ★ | **2026-06-29 (현재)** | 첫 GitHub release — 3 라인 PoC + monorepo + docs |
| v0.2.0 | 다음 사이클 | PTZ PoC 검증 + Pose A+B+C 다중 신호 카운터 |
| v0.3.0 | 후속 | ASR Whisper → KWS 교체 + 인터럽트 |
| v0.4.0 | 후속 | 하우징 시제품 + STM32U585 통합 |
| **v1.0.0** | **본 작품 마감 — 시연 가능** | 첫 stable release |
| v1.1.0 | 마감 후 | 감시 모드 등 시연 보조 모드 |

## 3. 단일 vs 라인별 버전 — 본 작품은 단일

monorepo 안 라인별 진척 차이가 있지만, **본 작품은 단일 작품(UNO Q 교감로봇)**으로 시연/평가. 작품 전체 단일 버전.

| 패턴 | 본 작품 |
|---|---|
| **A. 단일 버전** ★ | `v0.1.0` 1개. 라인별 milestone은 `docs/history/`에 누적 |
| B. 라인별 독립 | 본 작품 부적합 — 도구 의존 + 복잡 |
| C. 하이브리드 (root + sub-tag) | 본 작품 부적합 — 작품 단일 시연 |

라인별 진척 추적:
- Vision: `vision/docs/history/` — 거의 동결 (v1 시점 변경 없음)
- ASR: `asr/docs/history/` — 활성 (KWS 교체 결정)
- Pose: `pose/docs/history/` — 가장 활발 (PTZ PoC 진행)

## 4. git tag 부여

```bash
# 신규 release 시
cd /c/Project/unoq-companion-robot
git tag -a v0.X.Y -m "v0.X.Y: 변경 요약 ..."
git push origin --tags
```

annotated tag (`-a`) 권장 — release 메시지 보존.

## 5. 동결 자료 (v0.1.0)

본 시점 자료는 git tag로 자동 동결. 별도 ZIP 백업 권장 (선택):

```powershell
cd C:\Project\unoq-companion-robot
git archive --format=zip v0.1.0 -o ..\unoq-companion-robot-v0.1.0.zip
```

추가 백업: `c:\Project\backup-2026-06-29\` (monorepo 직전 평행 3 폴더)

## 6. 옛 tag 정리 (2026-06-29)

옛 비표준 tag 정리됨:
- ~`v1`~ (옛 vision merge commit) — 삭제 (v0.1.0이 새 베이스라인)
- ~`v1-monorepo`~ (monorepo 통합 commit) — 삭제 (역시 v0.1.0에 포함)

## 7. 다른 라인과의 동기

모든 라인(vision/asr/pose) 동시에 v0.1.0 시점. 후속 release도 작품 전체 동기.

## 8. 관련

- 본 사이클 history (semver 채택): [`history/2026-06-29_05_*`](history/) (작성 예정)
- 리뷰 미팅 (v1 베이스라인 결정 원본): [`history/2026-06-27_11_review_meeting_outcomes.md`](history/2026-06-27_11_review_meeting_outcomes.md)
- 본 작품 청사진: [`00_project_blueprint.md`](00_project_blueprint.md)
- 보고서: [`05_pose_line_report.md`](05_pose_line_report.md)
