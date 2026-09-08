# 2026-06-25 — issues/ + history/ 실시간 기록 워크플로우 확립

## 시점
2026-06-25 (보고 직전, ASR 1차 PoC 완료 직후)

## 사건
사용자 지침으로 `asr/docs/issues/` + `asr/docs/history/` 두 폴더 신규 생성. 일이 생길 때마다 즉시 마크다운으로 실시간 기록하는 워크플로우 채택.

## 배경
본 작품 ASR 1차 PoC 진행 중 발견 사항이 많아짐 (이슈 8건, 의사결정 ~15건). `docs/03_implementation_log.md`는 1차 PoC 종료 후 통합 정리한 정적 자산이라, **진행 중 실시간 기록**할 위치가 별도로 필요. 시간 지나면 잊혀지는 사건 보존 + 보고/피드백 추적 + 재발 방지 원칙.

## 결과
- `asr/docs/issues/` 폴더 신규 + `README.md` 작성 (작성 규칙)
- `asr/docs/history/` 폴더 신규 + `README.md` 작성 (작성 규칙)
- 본 파일 — 첫 history 기록
- 메모리 (auto memory)에 워크플로우 저장 → 향후 세션도 자동 따라감

## 워크플로우 핵심 규칙

| 항목 | 내용 |
|---|---|
| 폴더 | `asr/docs/issues/` (문제), `asr/docs/history/` (진행) |
| 파일명 | `<YYYY-MM-DD>_<NN>_<짧은_제목>.md` |
| 단위 | **1 사건 1 파일** (배치 X, 즉시 기록) |
| issues 대상 | 오류 / 함정 / 의외 동작 / 호환 문제 |
| history 대상 | 의사결정 / 마일스톤 / 자산 / 환경 변경 / 측정 / 리뷰어 |

## 다음 단계
- 보고 시연 직후 → 보고 결과 history 기록
- 향후 ASR 작업 중 이슈/진행 즉시 실시간 기록
- 보고 후 ADB 셋업 추진 (현 SSH 워크플로우 → ADB 전환 검토)

## 관련
- 워크플로우 메모리 저장: `~/.claude/projects/c--Project/memory/feedback_issues_history_workflow.md`
- 기존 정적 자산: [`../docs/03_implementation_log.md`](../docs/03_implementation_log.md)
