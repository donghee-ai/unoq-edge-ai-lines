# 2026-06-27 — 카메라/본체 추적 진로 결정 (2안 PTZ 선행 → 1안 자율 추적 확장)

## 시점
2026-06-27 (docs 최종 갱신 사이클)

## 사건
issues/05의 측면/후면 인식 한계 해결 진로를 사용자와 함께 정리. 풀 자율주행 vs 단순 정지 둘 사이에서 **stop condition 기반 제한적 자율 추적**으로 좁힘. 단계적 진행 — **2안(PTZ) 선행, 1안(본체 자율) 확장**.

## 결정 요약

| 단계 | 안 | 부담 | 본 작품 위치 |
|---|---|---|---|
| 즉시 | 3안 카메라 위치 조정 | 비용 0 | 다음 측정 |
| **마무리 1단계** | **2안 PTZ 서보** | $15, 0.5~1일 | 본체 정지로 안전 + STM32U585 인프라 구축 |
| **마무리 2단계** | **1안 Stop condition 본체 추적** | +$30, +1.5~2일 | 2안 위에 모터 + IMU 추가 |
| 범위 외 | 풀 자율주행 (회피 + 매핑) | 매우 큼 | 확장 토픽 분리 |

### 1안 알고리즘 핵심 — "필요한 거 다 보이면 멈춤"

```python
def is_ready(kp, conf_th=0.5):
    return all(kp[KP[n], 2] >= 0.5 for n in REQUIRED_KP)

if left_ready(kp) or right_ready(kp):
    send_motor("STAY")
else:
    send_motor(seek_direction(kp))
```

- **bang-bang 제어** (on/off만, PID 아님)
- 좌/우 분리 — 한쪽 다리만 다 보여도 STAY
- 이동 결정 3 룰 (미검출/다리 일부/중심점 치우침)
- 안전 4 메커니즘 (가상 펜스 30 cm × 30 cm, 5 cm/s, 5초 무탐색 정지, 사람 미검출 시 유지)

### 1안 + 2안 인프라 공유

| 자산 | 2안 구축 | 1안 재활용 |
|---|---|---|
| STM32U585 PWM 펌웨어 | 서보 2채널 | 모터 PWM 채널 추가 |
| UART 명령 프로토콜 | `SERVO_PAN/TILT N` | `MOTOR_YAW/FORWARD N` 추가 |
| UNO Q 추적 알고리즘 골격 | `is_ready()` + decision tree | 동일 함수 + 본체 명령 분기만 추가 |
| visibility / stop condition | PTZ 서보 STAY | 본체 STAY |

→ 2안에서 펌웨어/통신/알고리즘 골격을 만들고, 1안은 **모터/IMU 하드웨어 추가만**. 어느 시점에 멈춰도 가치 있음.

## 본 라인 알고리즘 신호 보완(A/B/C)과의 관계

| 축 | 처리 |
|---|---|
| A/B/C 다중 신호 OR (방향 인식 + 머리 낙차 + 엉덩이 각도) | **신호 처리** — UNO Q 단독, 즉시 진행 가능 |
| 2안 + 1안 추적 | **물리 위치 보완** — STM32 + 하드웨어 |

→ **독립적이고 보완 관계**. 둘 다 적용하면 정면/측면/후면 모든 사용처에서 인식 안정성 최대.

## docs 갱신 (본 사이클)

| 파일 | 갱신 |
|---|---|
| `docs/00_project_blueprint.md` §8 | §8-1 소프트웨어 + §8-2 하드웨어 통합으로 이중 분리 |
| `docs/04_squat_algorithm.md` §7 | §7-4 신규 — "물리적으로 카메라 좋은 위치 두기" 별도 축 + A/B/C와 독립·보완 관계 명시 |
| `docs/05_mentor_report_pose_line.md` §5-4 | 단기/중기/장기 표를 단계별 부담/효과 표로 갱신 + 1·2단계 인프라 공유 명시 |
| `docs/05_mentor_report_pose_line.md` §7 | §7-1 소프트웨어 + §7-2 하드웨어 단계로 분리 + 5→6→7 단계적 진행 명시 |
| `docs/issues/2026-06-27_05_*.md` | 1안 내용을 stop condition 자율 추적으로 교체 + 2안 ★ 선행 / 1안 ★ 확장 표기 + 권장 진로 표 재정렬 (이전 사이클에 진행) |

## 결정 도움 필요 항목 (사용자에게 확인 대기)

| # | 항목 |
|---|---|
| 1 | 본 작품 마감 시한 |
| 2 | 모터/서보/IMU/엔코더 하드웨어 보유 여부 |
| 3 | 본 작품 다른 라인(vision MCU, ASR 마무리, 표정/음성 통합) 남은 작업량 |
| 4 | 본체 chassis (UNO Q + 바퀴 form factor) 보유 여부 |

답변에 따라:
- 마감 여유 + 하드웨어 보유 → **1안까지 풀 진행**
- 마감 임박 또는 하드웨어 미보유 → **2안만 진행 + 1안은 확장 토픽**
- 본 작품 다른 우선순위 큼 → 본 라인 마무리 + 추적은 사후

## 다음 단계 (단기)

알고리즘 신호 보완 측 — UNO Q 단독 작업이라 하드웨어 무관 즉시 가능:
- A+B+C 다중 신호 카운터 구현 (코드 작성 + ADB push + 측정)

하드웨어 측 — 사용자 결정 후:
- 2안 PTZ 시작 (서보 mount + STM32 PWM 펌웨어 + UART 정의 + UNO Q 추적 알고리즘)

## 관련

- 직전 docs 갱신 사이클: [`2026-06-27_09_docs_update_and_mentor_report.md`](2026-06-27_09_docs_update_and_mentor_report.md)
- 본 결정 근거: [`../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md)
- 알고리즘 신호 보완: [`../04_squat_algorithm.md`](../04_squat_algorithm.md) §7~8
