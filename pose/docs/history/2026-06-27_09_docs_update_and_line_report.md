# 2026-06-27 — docs 일괄 갱신 + 보고서 작성

## 시점
2026-06-27 (3회 측정 + 알고리즘 설명 사이클 정리)

## 사건
사용자 지침으로 본 사이클 누적 자료를 docs에 반영 + 보고용 단독 문서 작성. 본 라인 docs 구조 완성 (00~05 + history/issues).

## 진행

### 1. docs/00_project_blueprint.md 갱신
- 3 라인 종합 표에 Pose plateau 71.4°C 명시
- **§2-1 측정 누적** 신규 — 3회 측정 (136s/294s/157s) 표로 정리
- thermal plateau 71°C 정량 + 합격 마진 미확보 명시
- **§6 카메라 자세 권장** 신규 — 렌즈 10cm + 위로 20°가 정면 인식 최적
- **§7 알고리즘 한계 + 개선 방향** 신규 — A(방향 인식) / B(머리 낙차) / C(엉덩이 각도) 매트릭스
- §8 다음 단계 후보 재정렬 (알고리즘 통합 우선)
- §9 관련 링크 04, 05 추가

### 2. docs/04_squat_algorithm.md 신규 (320줄)
사용자에게 설명한 알고리즘 내용 정리:
- 4단계 흐름 (입력 → 무릎 각도 → 좌/우 선택 → 상태 머신)
- 각 단계 코드 + 해석
- Hysteresis (down_th=100 < up_th=140) 그림 + 의미
- min_dwell_ms 200ms 떨림 방지
- 검출 누락 강건성 — `update(None)` freeze + 사이클 게이트 메커니즘
- **실측 trace 예** (frame 720~750 #1 rep 동작)
- 좌/우 조합별 처리 (A/A'/B/C 경우)
- 7-1 측면 한계 (perspective 압축) → A 임계 동적 조정
- 7-2 후면 한계 (일직선) → B 머리 낙차
- 7-3 발목 약함 → C 엉덩이 각도 (shoulder-hip-knee)
- §8 A+B+C OR 통합 — MultiSignalCounter 의사 코드
- §9 CLI 옵션 매핑

### 3. docs/03_runbook_camera_serve.md 갱신
- §8 실측 사례 신규 — 3회 측정 표
- 검출 패턴 관찰: 양쪽 동시 검출 드물고 한쪽만 잡힘 빈번 → `--side better` 결정적
- thermal 단기 vs sustained 차이 명시
- §9 관련 링크 04, 05 추가

### 4. docs/05_pose_line_report.md 신규 (보고용 단독)
구조:
1. 모델 선정 — Thunder INT8 채택 4 근거 + AI Hub QNN ONNX 기각 사유
2. 성능 측정 — 3회 디바이스 e2e + thermal plateau + 호스트 baseline + 3 라인 자원 합산
3. 알고리즘 구조 — 4단계 + Hysteresis + 검출 누락 강건성 + 실측 trace
4. 라이선스 — MoveNet Apache-2.0+CC BY 4.0 / 의존성 모두 상업 호환 / vision YOLO AGPL 노트
5. 현재 한계 + 개선 방향 — 측면/후면 단일 신호 한계 + thermal 마진 + 카메라 자세
6. 사용 시나리오 — SSH 라이브 + ADB 회귀 검증
7. 다음 단계 (우선순위)
부록 — 자료 위치 + 코드 위치

본 보고서는 참고자료 인용 없이 본인 측정/결정만 기반 (대외비 워크플로우 준수).

### 5. docs 구조 최종

```
docs/
├── 00_project_blueprint.md      청사진 (목표/모델/3 라인 위치/측정 누적/카메라/알고리즘 한계/다음)
├── 01_model_candidates.md       모델 후보 1/2/3 + 각도 분석
├── 02_quickstart_pose.md        0→30분 진입 절차
├── 03_runbook_camera_serve.md   시나리오별 운영 명령 + 실측 사례
├── 04_squat_algorithm.md        알고리즘 자세 (320줄) ★ 신규
├── 05_pose_line_report.md 보고용 단독 문서 ★ 신규
├── history/  9 파일 (본 history 포함)
└── issues/   5 파일
```

## 결과
- 본 라인 docs 가이드 5개 + 보고서 1개 + 누적 14 파일(history+issues) 완성
- 외부 진입자가 docs/만 보면 가이드 + 측정 + 트러블 + 보고서까지 전부 파악
- 보고용 ZIP 패키지화: `git archive --format=zip HEAD docs/` 한 줄로 완료

## 다음 단계
- A+B+C 다중 신호 카운터 통합 코드 작업 (다음 사이클)
- soak test ≥10 min + threads 3 시도 (합격 마진 확보)

## 관련
- 직전 정리: [`2026-06-27_08_docker_qai_hub_remnants_cleanup.md`](2026-06-27_08_docker_qai_hub_remnants_cleanup.md)
- 본 라인 측정 누적: 2026-06-27_03 → 04 → 06 → 본 history
