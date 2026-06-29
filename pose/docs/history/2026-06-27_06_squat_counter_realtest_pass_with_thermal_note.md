# 2026-06-27 — 스쿼트 카운터 실측 합격 (13 rep / 294.5 s), thermal 71.4°C 초과 노트

## 시점
2026-06-27 (스쿼트 카운터 통합 직후, USB host controller 복구 후 재실행)

## 사건
USB 호스트 컨트롤러 복구(issues/2026-06-27_03 해결: 허브 전체 분리/재연결로 xhci 재registration) → SSH 모드 카메라 + HTTP serve + 스쿼트 카운터 sustained 측정. **13 rep 자동 카운팅 + bottom 각도 정확**, 단 thermal plateau 71.4°C(합격선 1.4°C 초과).

## 측정 (2,813 frames / 294.5 s)

### 합격/비합격

| 기준 | 합격선 | 측정 | 평가 |
|---|---|---|---|
| fps_effective | ≥ 8 | 9.55 | ✓ |
| dropped | 0 | 0 | ✓ |
| cpu_peak | 4 코어 여유 | 311% (코어 78%) | ✓ |
| rss_peak | ≪ 2.4 GB | 95.5 MB | ✓ |
| **temp_peak** | **≤ 70°C** | **71.4°C** | **⚠ +1.4°C 초과** |
| squat_reps | (목표 없음) | **13 자동 카운팅** | ✓ 정확 |
| deepest_deg | (목표 없음) | 34.9° (ATG) | ✓ |

### 13 rep bottom 각도

```
#1  48°    #2  39°    #3  63°    #4  35°    #5  40°
#6  42°    #7  53°    #8  65°    #9  43°    #10 40°
#11 57°    #12 37°    #13 28°  ← deepest
```

대부분 ATG(50° 이하), 일관된 깊이. **스쿼트 깊이 측정 가능성 정량 확인 완료**.

## Thermal ramp 정량

| 시점 (s) | 온도 (°C) | Δ |
|---|---|---|
| 0 (start) | 54.5 | — |
| 50 | 63.0 | +8.5 (선형 빠른 ramp) |
| 100 | 65.8 | +2.8 |
| 200 | 69.2 | +3.4 |
| **225** | **70.2** | ★ 70°C 첫 진입 |
| 250 | 70.5 | |
| 270 | 71.1 | plateau 진입 |
| **295 (end)** | **71.4 (peak)** | plateau 형성 |

→ plateau 약 71°C 근처 (이전 단기 측정 68.6°C는 plateau 미도달 상태였음 확정). 이슈 기록: [`../issues/2026-06-27_04_thermal_plateau_71c_exceeds_70_margin.md`](../issues/2026-06-27_04_thermal_plateau_71c_exceeds_70_margin.md).

## 카메라 시야각 관찰 (사용자 보고)

- **정면**: keypoint 인식 우수, 좌/우 무릎 각도 안정 측정
- **측면 / 후면**: 카메라가 사람보다 훨씬 낮은 위치 (바닥 근처) → vertical viewing angle 부족 → keypoint 미검출 빈번
- **중요 발견 — "하반신만 나와도 충분히 잘 작동함"**: MoveNet이 부분 신체로도 hip-knee-ankle 추정 가능. 카메라 배치 자유도 ↑.

상세 분석 + 개선 방안: [`../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md).

### 개선 방안 평가

| 안 | 복잡도 | 본 작품 적합도 |
|---|---|---|
| 1안 자율주행 정면 추적 | 매우 높음 | ✗ 범위 외 |
| **2안 PTZ (서보 2축, 사람 방향 PID)** | 중간 | **✓ 본 작품 마무리에 권장 — STM32U585 + 서보 펌웨어 통합** |
| **3안 카메라 위치 변경 (사람 높이)** | 매우 낮음 (물리 배치) | **✓ 단기 즉시** |

## 합격 평가 — 조건부 통과

- 4개 정량 기준 중 3개 통과 (FPS / CPU / RSS / dropped 안정)
- thermal 1개 초과 (71.4°C)
- 명확한 throttle 흔적은 없음 (FPS 안정 유지) — soft fail
- **스쿼트 카운팅 핵심 기능 정확 동작** — 본 작품 사용처 합격

→ **본 작품 범위에서는 조건부 합격**. thermal 정량 보고 + 환기/threads 감소 등 마진 확보 진행 권장.

## 자산
- 본 trace 콘솔 출력 (사용자가 메시지로 제공) — 본 history에 핵심 수치 집약
- `scripts/infer_camera_pose.py` + `scripts/squat_counter.py` (변경 없음 — 통합 코드 검증)
- 13 rep 검출 + bottom 각도 분포 → 본 라인 알고리즘 검증 자료

## 다음 단계 (재정렬)

| 우선순위 | 항목 | 비고 |
|---|---|---|
| 1 | 카메라 위치 조정 (3안) + 동일 측정 | 측면/후면 인식률 향상 확인 |
| 2 | thermal 해결 시도 (환기 / threads 3 / JPEG quality 50) | 합격 마진 1~3°C 확보 |
| 3 | 사용자 위치 → 서보 PTZ 명령 산출 알고리즘 설계 | 2안 사전 작업 |
| 4 | Vision + Pose 동시 운영 자원 청사진 | 멘토 보고용 |
| 5 | `--json` benchmark 저장 옵션 | 멘토 06 형식 |
| 6 | MCU 트리거 (STM32U585) + 서보 PTZ 통합 | 본 작품 마무리 |

## 관련

- 직전 USB 복구: [`../issues/2026-06-27_03_mic_disconnect_killed_xhci_usb_controller.md`](../issues/2026-06-27_03_mic_disconnect_killed_xhci_usb_controller.md)
- 카운터 통합: [`2026-06-27_05_trace_analysis_and_line_rename.md`](2026-06-27_05_trace_analysis_and_line_rename.md)
- thermal 함정: [`../issues/2026-06-27_04_thermal_plateau_71c_exceeds_70_margin.md`](../issues/2026-06-27_04_thermal_plateau_71c_exceeds_70_margin.md)
- 카메라 시야각 함정: [`../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md)
