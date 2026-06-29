# 2026-06-29 — semver 채택 + v0.1.0 첫 GitHub release 베이스라인

## 시점
2026-06-29 (monorepo 통합 + docker 일관 패턴 직후, 첫 GitHub release 준비)

## 사건
본 작품 버전관리를 **표준 semver(MAJOR.MINOR.PATCH)**로 채택. 옛 비표준 tag (`v1`, `v1-monorepo`) 정리하고 **`v0.1.0`을 첫 GitHub release 베이스라인**으로 부여.

## 결정 근거

### 왜 0.1.0인가 — v1.0.0이 아닌 이유

| 평가 항목 | 현재 상태 |
|---|---|
| 3 라인 1차 PoC 합격 | ✓ (vision 9.23 FPS, ASR 3.18 s, Pose 9.69 FPS + 13 rep) |
| Monorepo 통합 | ✓ |
| docs 정비 | ✓ |
| 멘토 미팅 결정 반영 | ✓ |
| **PTZ 하드웨어 측정** | **✗** (코드만, 검증 미실시) |
| **하우징 시제품** | **✗** |
| **ASR KWS 교체** | **✗** (멘토 결정만, 미실시) |
| **시연 영상 / 포트폴리오 README** | **✗** |

→ 약 7/11 완료. semver `1.0.0`은 "stable, 시연 가능"이라는 의미라 본 작품 마감 시점이 정통. 현재는 "활발한 개발 중, breaking 가능"의 `0.x.y` 영역.

**사용자 판단**: "처음 GitHub 올리는거고 + PTZ 통합 남아있으니 0.1.0이 맞다"

### 왜 단일 버전 패턴(A)인가

monorepo 안 라인별 진척 차이 있지만 (vision 거의 동결 / ASR 교체 예정 / Pose 활발), **본 작품은 단일 작품(UNO Q 교감로봇)**으로 시연/평가.

| 패턴 | 본 작품 평가 |
|---|---|
| **A. 단일 버전 ★** | 작품 전체 `v0.1.0` 1개. 라인별 milestone은 history로 추적 |
| B. 라인별 독립 | 도구 의존 (Lerna/Nx) + 복잡 — 본 작품 과함 |
| C. 하이브리드 | tag 4개+ 관리 부담 — 단일 시연에 불필요 |

라인별 진척 추적은 **각 라인 `docs/history/` 폴더**가 잘 처리 — git tag는 작품 전체 release에만.

## 작업

### 1. 옛 tag 정리

```bash
git tag -d v1               # 옛 vision merge commit
git tag -d v1-monorepo      # 옛 monorepo 통합 commit
```

### 2. v0.1.0 신규 tag (annotated, 상세 메시지)

```bash
git tag -a v0.1.0 -m "v0.1.0: 첫 GitHub release — 3 라인 PoC + monorepo (2026-06-29)
...
다음 release 후보:
- v0.2.0: PTZ PoC 검증 + A+B+C 다중 신호 카운터
- v0.3.0: ASR KWS 교체
- v0.4.0: 하우징 + STM32 통합
- v1.0.0: 본 작품 마감 (시연 가능)"
```

### 3. docs/07_versioning.md 전면 갱신

- 옛 "v1 베이스라인 (2026-06-27 동결)" 표기 → **v0.1.0 (현재) → ... → v1.0.0 (본 작품 마감)** semver 매핑
- 단일 버전 패턴(A) 선택 근거 + 라인별 vs 통합 비교
- 옛 tag 정리 사실 명시
- 본 작품 마감(v1.0.0) 정의 = "시연 가능 stable"

## 향후 버전 매핑

| 버전 | 시점 | 주요 변경 |
|---|---|---|
| **v0.1.0** ★ | **2026-06-29 (현재)** | 첫 GitHub release |
| v0.2.0 | 다음 사이클 | PTZ PoC 검증 + Pose A+B+C 다중 신호 카운터 |
| v0.3.0 | 후속 | ASR Whisper → KWS 교체 |
| v0.4.0 | 후속 | 하우징 시제품 + STM32 통합 |
| **v1.0.0** | **본 작품 마감** | 첫 stable release — 시연 가능 |
| v1.1.0 | 마감 후 | 감시 모드 등 시연 보조 |

## 영향

### 본 작품 메인 라인
- **변경 없음** — 코드/모델/docs 그대로
- 단지 tag 이름 변경 (`v1` → `v0.1.0`)
- 향후 release 시 semver 따름

### 멘토/포트폴리오 보고
- "v0.1.0 첫 GitHub release" — 학생 작품 정직 표기
- 본 작품 마감 시 "v1.0.0 stable release"로 자연스럽게 승격
- 채용 담당자 / 다른 학생에게 익숙한 표준 형식

## 미진행 — push

본 사이클 = 로컬 tag 정리만. GitHub push는 별도 사용자 결정:

```bash
# 모든 변경 + 새 tag push
git push origin main --tags

# 또는 옛 tag 삭제도 origin에 반영
git push origin :v1 :v1-monorepo
git push origin --tags
```

옛 tag(`v1`, `v1-monorepo`)는 origin에 push 안 됐으므로 그쪽엔 영향 없음.

## 관련

- 직전 docker 일관: [`2026-06-29_04_vision_docker_folder_restructure_and_3_lines_check.md`](2026-06-29_04_vision_docker_folder_restructure_and_3_lines_check.md)
- monorepo 통합: [`2026-06-29_02_monorepo_restructure.md`](2026-06-29_02_monorepo_restructure.md)
- 멘토 미팅 결정: [`2026-06-27_11_mentor_meeting_outcomes.md`](2026-06-27_11_mentor_meeting_outcomes.md)
- 갱신된 가이드: [`../07_versioning.md`](../07_versioning.md)
