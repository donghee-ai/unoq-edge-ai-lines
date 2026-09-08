# History — vision 라인 의사결정/진행/마일스톤 실시간 기록

본 작품 vision 라인 (YOLO + 카메라 + 향후 fusion) 진행 중 **의사결정 / 마일스톤 / 자산 추가 / 환경 변경 / 측정 완료 / 리뷰 피드백** 등 일반 진행 사항을 실시간 기록.

## 파일명 규칙

```
<YYYY-MM-DD>_<NN>_<짧은_제목>.md
```

| 부분 | 형식 | 예시 |
|---|---|---|
| 날짜 | `YYYY-MM-DD` (ISO 8601) | `2026-06-25` |
| 일련번호 | 그날의 순번 (`01`, `02`, …) | `01` |
| 짧은 제목 | 영문 lowercase + underscore | `soak_test_8h_started`, `monorepo_migration`, `review_feedback_received` |

전체 예시:
- `2026-06-25_01_workflow_established.md`
- `2026-07-01_01_soak_test_kicked_off.md`
- `2026-07-15_01_monorepo_migration_done.md`

→ 파일명만 봐도 **언제 + 어떤 사건** 즉시 파악 가능.

## 작성 형식 (1 사건 1 파일)

```markdown
# <한 줄 제목>

## 시점
YYYY-MM-DD HH:MM (선택)

## 사건
무엇이 일어났는가 (사실 위주)

## 배경
왜 진행했는가 (있으면)

## 결과
- 산출물 / 결정 / 측정값
- 다음 단계

## 관련
- 관련 issues / history / docs 파일 링크 (선택)
```

## 기록 시점

**일이 생기는 즉시**:
- 의사결정 (모델 변경, 합격선 조정, 라이브러리 결정 등)
- 자산 추가/삭제 (모델 다운로드, 파일 생성/삭제, 벤치 JSON 회수)
- 환경 변경 (Docker rebuild, 디바이스 패키지 설치, 커널/펌웨어 업데이트)
- 측정 완료 시 핵심 수치 (FPS, latency, RSS, temp, accuracy)
- 보고 / 리뷰 피드백 받음
- 작업 시작 / 종료 / 재시작 시점
- 새 워크플로우 / 규칙 채택

## `issues/`와의 구분

| 폴더 | 내용 |
|---|---|
| `issues/` | **문제** / 오류 / 함정 → 진단 / 해결 / 재발 방지 |
| `history/` | **정상 진행** / 의사결정 / 마일스톤 / 결과 |

같은 사건이 둘 다 해당하면 양쪽에 (서로 링크).

## 기존 진행 자산

vision 라인 1차 PoC (~2026-06-23) 결과는 이미 docs/에 정리됨:

| 자산 | 기록 위치 |
|---|---|
| 한 페이지 청사진 | [`../docs/00_project_blueprint.md`](../docs/00_project_blueprint.md) |
| 호스트 환경 셋업 | [`../docs/01_host_environment_setup.md`](../docs/01_host_environment_setup.md) |
| 모델 선택 로그 | [`../docs/02_model_selection_log.md`](../docs/02_model_selection_log.md) |
| 디바이스 셋업 | [`../docs/04_device_setup.md`](../docs/04_device_setup.md) |
| 첫 측정 (host baseline + device) | [`../docs/05_initial_inference_measurement.md`](../docs/05_initial_inference_measurement.md) |
| 후처리 + e2e | [`../docs/06_postprocess_and_e2e.md`](../docs/06_postprocess_and_e2e.md) |
| 공식 100회 벤치 (벤치마크 표준 JSON) | [`../docs/07_official_benchmark.md`](../docs/07_official_benchmark.md) |
| 카메라 실시간 + HTTP serve | [`../docs/08_realtime_camera.md`](../docs/08_realtime_camera.md) |
| 운영 runbook | [`../docs/09_usage_runbook.md`](../docs/09_usage_runbook.md) |
| 코딩/운영 규약 | [`../docs/03_project_conventions.md`](../docs/03_project_conventions.md) |
| Monorepo 통합 개선 방안 | [`../docs/improvement_monorepo_restructure.md`](../docs/improvement_monorepo_restructure.md) |
| 2026-06-24 세션 핸드오프 | [`../SESSION_SUMMARY_2026-06-24.md`](../SESSION_SUMMARY_2026-06-24.md) |

→ 본 폴더는 **향후 진행** 실시간 기록 전용.

## 관련 자산
- [`../issues/`](../issues/) — 이슈/오류/함정
- [`../docs/`](../docs/) — 1차 PoC 통합 정리
- ASR 라인 동일 폴더: [`../../asr/docs/history/`](../../asr/docs/history/)
