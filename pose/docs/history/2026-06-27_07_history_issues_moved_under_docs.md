# 2026-06-27 — 3 라인 모두 history/ + issues/ → docs/ 하위로 이동 (구조 통합)

## 시점
2026-06-27 (스쿼트 카운터 실측 직후 정리 사이클)

## 사건
사용자 지침으로 본 작품 3 라인 모두 `history/` + `issues/` 두 폴더를 **`docs/` 하위로 이동**. 가이드 + 트러블슈팅 + 마일스톤이 한 폴더(`docs/`)에 통합되어 외부 진입자 + 참고자료 가독성 향상.

## 진행

### 1. 폴더 이동 (PowerShell `Move-Item`)

| 라인 | 이동 전 | 이동 후 |
|---|---|---|
| unoq-pose | `history/` 6 + `issues/` 5 | `docs/history/` + `docs/issues/` |
| unoq-companion-robot | `history/` 4 + `issues/` 3 | `docs/history/` + `docs/issues/` |
| unoq-asr | `history/` 3 + `issues/` 1 | `docs/history/` + `docs/issues/` |

총 22 파일, 6 폴더 이동. 옛 root `history/` `issues/` 폴더 모두 제거됨.

### 2. 내부 참조 일괄 갱신

58 .md 파일 검사, 12 파일 갱신:

| 패턴 | 변경 |
|---|---|
| `unoq-X/history/` (cross-line) | → `unoq-X/docs/history/` |
| `unoq-X/issues/` (cross-line) | → `unoq-X/docs/issues/` |
| `unoq-X\history\` (Windows path) | → `unoq-X\docs\history\` |
| docs/ 직속 파일 안 `../history/<YYYY>` | → `history/<YYYY>` (같은 docs/ 자식 직접 가리킴) |
| docs/ 직속 파일 안 `../issues/<YYYY>` | → `issues/<YYYY>` |
| 디렉토리 트리 다이어그램 (`├── history/`) | → `docs/` 안에 history/, issues/ 표시 |

자기 폴더 안 참조 (docs/history/A.md → docs/history/B.md, 또는 docs/history/X.md → docs/issues/Y.md)는 `../issues/` 그대로 OK — 같은 docs/ 안 형제 폴더 가리킴.

### 3. 메모리 갱신

`~/.claude/projects/c--Project/memory/`:
- `feedback_issues_history_workflow.md` — 표준 위치 `docs/issues/`, `docs/history/`로 변경 명시. 2026-06-25 채택 시점 (root 직속)에서 2026-06-27 이동 사실 보존.
- (`project_unoq_companion_robot.md`는 이전 사이클에서 이미 폴더 경로 갱신 완료)

## 결과

### 변경 전
```
pose/
├── docs/             (가이드만)
├── history/          (작업 과정 — root 직속)
├── issues/           (트러블슈팅 — root 직속)
├── ...
```

### 변경 후
```
pose/
├── docs/             (모든 문서 통합)
│   ├── 00_*..03_*.md
│   ├── history/
│   ├── issues/
│   └── (_private_refs/, standard_style/ — 라인별 참고자료)
├── ...
```

장점:
- **외부 진입자 1뷰**: docs/만 보면 가이드 + 마일스톤 + 함정 모두 파악
- **보고 ZIP 패키지화 단순**: `git archive --format=zip HEAD docs/`로 가이드/이슈/히스토리 한 번에
- **일관성**: 3 라인 동일 구조

### 단점
- 옛 path 외부 참조(예전 ZIP에서 push된 링크) 깨짐 — 본 작품 outside 영향 X (private 단독 진행)
- 본 history 자체가 옛 `history/` 이동 사건 기록이라는 점이 약간 메타. OK (재발/추적 가치).

## 자산

신규/이동:
- `docs/history/` (6 파일, 본 history 포함)
- `docs/issues/` (5 파일)
- `docs/00_project_blueprint.md` (디렉토리 트리 갱신)
- `SESSION_SUMMARY_2026-06-27.md` (트리 표기 갱신)
- 동일 패턴 unoq-companion-robot, unoq-asr 라인에 적용

메모리:
- `feedback_issues_history_workflow.md` 갱신 (표준 위치 docs/ 하위)

## 다음 단계

- 4안(HeadDropCounter + 자동 모드 전환) 진행 — 사용자 의도 (B) "책상 위 카메라 + 머리 낙차로 보조 카운팅" 해석 확인 대기 중
- thermal soak 환기 개선 / threads 감소 시도 (issues/2026-06-27_04 해결)
- 카메라 위치 조정 시도 (issues/2026-06-27_05 — 3안 단기 적용)

## 관련

- 워크플로우 메모리: `~/.claude/projects/c--Project/memory/feedback_issues_history_workflow.md`
- 직전 카운터 실측: [`2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md`](2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md)
- 폴더 rename 사이클: [`2026-06-27_05_trace_analysis_and_line_rename.md`](2026-06-27_05_trace_analysis_and_line_rename.md)
