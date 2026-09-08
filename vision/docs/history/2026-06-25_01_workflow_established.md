# 2026-06-25 — vision 라인에도 issues/ + history/ 워크플로우 적용

## 시점
2026-06-25 (ASR 라인 적용 직후, 보고 직전)

## 사건
사용자 지침으로 vision 라인 (`vision/`)에도 `issues/` + `history/` 두 폴더 신규 생성. ASR 라인 (`asr/`)에 먼저 적용된 동일 워크플로우를 vision 라인에 확장.

## 배경
- ASR 라인에서 같은 워크플로우 적용 후 작동 검증 ([`../../asr/docs/history/2026-06-25_01_workflow_established.md`](../../asr/docs/history/2026-06-25_01_workflow_established.md))
- vision 라인은 1차 PoC 합격선 통과 후 안정화 단계. 그러나 향후 작업 (soak test, monorepo 통합, fusion 추가, ADB 셋업 등)에서 신규 사건 발생 예정
- 양 라인 일관된 기록 패턴으로 보고 / 핸드오프 / 재발 방지 표준화

## 결과
- `vision/docs/issues/` 폴더 신규 + `README.md` (작성 규칙 + 기존 함정 docs 링크 매핑)
- `vision/docs/history/` 폴더 신규 + `README.md` (작성 규칙 + 기존 자산 docs 링크 매핑)
- 본 파일 — 첫 history 기록
- 메모리 (auto memory) `feedback_issues_history_workflow.md`는 ASR 적용 시 이미 저장, 본 사건으로 양 라인 적용 확정

## 워크플로우 핵심 규칙 (ASR 라인과 동일)

| 항목 | 내용 |
|---|---|
| 폴더 | `vision/docs/issues/` (문제), `vision/docs/history/` (진행) |
| 파일명 | `<YYYY-MM-DD>_<NN>_<짧은_영문_제목>.md` |
| 단위 | **1 사건 1 파일** (배치 X, 즉시 기록) |
| issues 대상 | 오류 / 함정 / 의외 동작 / 호환 문제 |
| history 대상 | 의사결정 / 마일스톤 / 자산 / 환경 변경 / 측정 / 리뷰어 |

## 다음 단계 (vision 라인)
- 보고 시연 후 결과 history 기록
- soak test 8h+ 시작 시 history 기록 (vision docs/08 §3-3에서 thermal 70.8°C 관찰됨)
- monorepo 통합 시점에 마이그레이션 history 기록
- ADB 셋업 시 history 기록 (보고 후 추진 예정)

## 관련
- ASR 라인 동일 셋업: [`../../asr/docs/history/2026-06-25_01_workflow_established.md`](../../asr/docs/history/2026-06-25_01_workflow_established.md)
- 워크플로우 메모리: `~/.claude/projects/c--Project/memory/feedback_issues_history_workflow.md`
