# 2026-06-27 — Sustained 운영 thermal plateau 71.4°C — 합격선 70°C 1.4°C 초과

## 증상

294.5 s sustained (2,813 frames, 스쿼트 카운터 ON) 실측 종료 시 `temp_peak_c: 71.4°C` 기록. 합격선(≤ 70°C) 초과.

## 측정 경로

| 시점 (s) | 온도 (°C) | 비고 |
|---|---|---|
| 0~50 | 54.5 → 63.0 | 선형 ramp (이전 단기 측정과 일치) |
| 100 | 65.8 | |
| 225 | 70.2 | **★ 70°C 첫 진입** |
| 250 | 70.5 | |
| 270 | 71.1 | |
| 295 | **71.4 (peak)** | 종료 |

275~295 s 사이 70.2~71.1°C 사이 진동 — **plateau가 71°C 근처에서 형성**되는 것으로 보임. 더 길게 측정해야 확정.

## 영향

- **합격선 초과 — 정직 보고 필요**.
- FPS / CPU / RSS는 안정 유지 (10.6~10.8 FPS, 285~300%, 95 MB) — **명확한 thermal throttle 흔적은 없음**.
- 단발 측정(136 s = 68.6°C)과 sustained 측정(295 s = 71.4°C) 차이 = **+2.8°C/180 s 추가 ramp**.

## 비교 (3 라인)

| 라인 | thermal peak | 측정 시간 |
|---|---|---|
| Vision YOLOv8n int8 | 70.8°C | (이전 측정 기준) |
| **Pose Thunder int8 (단기)** | 68.6°C | 136 s |
| **Pose Thunder int8 (sustained + 스쿼트)** | **71.4°C** | **295 s** |

Pose가 sustained에서 vision보다 0.6°C 높음. 입력 256<320으로 모델은 가벼우나 카메라 + serve + 후처리 + counter 부담 누적.

## 원인 (추정)

- QRB2210 + Cortex-A53 ×4 약 78% 사용 → 4 코어 모두 활성 누적 발열
- HTTP MJPEG serve 추가 부하 (JPEG 인코딩 + socket I/O)
- 케이스/방열 — UNO Q는 passive 방열만, 적절 환기 가정

## 해결 후보

| 방안 | 효과 추정 | 비용 |
|---|---|---|
| **1. 측정 환경 환기 개선** (테이블 위 공기 흐름) | -1~3°C | 0 |
| 2. CPU threads 4→3 감소 | -2~4°C, FPS 일부 하락 | 코드만 |
| 3. 카메라 해상도 640→480 또는 320 | -1~2°C, FPS 약간 향상 | 코드만 |
| 4. JPEG quality 70→50 또는 serve 미사용 (DEBUG 시 외) | -1~2°C | 코드만 |
| 5. Frame skip (매 N 프레임만 invoke) | -3~5°C, FPS 절반 | 코드 |
| 6. 외부 cooling (heatsink/fan) | -5~10°C | 하드웨어 |

## 권장 진로

1. **즉시**: 환기 개선 + 동일 측정 재수행 → plateau 정량 확정
2. **합격 마진 필요 시**: threads 3 또는 JPEG quality 50으로 -2~3°C 확보 시도
3. **장기**: passive heatsink (작은 알루미늄 방열판) — 단독 진행 부담 낮음

## 재발 방지

- thermal soak는 **반드시 5분 이상** 측정해야 plateau 보임 (단기 측정만으론 ramp 단계 → 합격 오판 가능)
- vision/ASR 라인 측정에도 동일 — 모든 라인 sustained 측정 권장

## 관련

- 본 측정 history: [`../history/2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md`](../history/2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md)
- 단기 e2e 측정 (136 s): [`../history/2026-06-27_04_pose_camera_e2e_pass.md`](../history/2026-06-27_04_pose_camera_e2e_pass.md)
- 합격 기준 (4 기준): [`../docs/00_project_blueprint.md`](../docs/00_project_blueprint.md)
