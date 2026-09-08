# 2026-06-27 — 카메라 바닥 배치 시 측면/후면 keypoint 검출률 저하

## 증상

스쿼트 측정 중 카메라 정면 자세에서는 인식 우수, **측면/후면 자세에서는 keypoint 검출 실패 빈도 ↑** (`L=? R=?` 콘솔에 빈번).

## 원인

카메라가 사람 신체 대비 **상당히 낮은 위치 (바닥 근처)**에 있음. 결과:
- **Vertical viewing angle 부족**: 사람의 hip / knee / ankle이 카메라 시야에서 정상 비례가 아닌 perspective distortion 형태로 보임
- 측면 자세: 한쪽 다리 occlusion + 사람 신체 일부가 frame 밖
- 후면 자세: 정면 keypoint(nose/eyes/shoulders)가 안 보이므로 MoveNet의 global pose estimation 신뢰도 ↓ → confidence 임계 미달 → keypoint 무효

## 측정 trace 패턴

활성 keypoint 검출 구간에서 정면 자세는 L+R 둘 다 ~170° (Standing), 90° 이하 (Squat) 명확 분리. 측면/후면 자세 들어가면 활성 비율 급감.

## 본 사용처 발견 — "하반신만 나와도 OK"

추가 관찰: 사용자가 명시한 대로 **상반신 미포함 자세에서도 hip-knee-ankle 추정 가능**. MoveNet이 부분 신체로도 동작.

→ 카메라 배치 자유도 ↑. 정면 전신을 강요할 필요 없음.

## 해결 후보

### 1안 — Stop condition 기반 제한적 자율 추적 (✗ 2026-06-27 리뷰 미팅에서 폐기)

**상태**: **본 작품 범위 외**로 결정 (리뷰 미팅 2026-06-27, [`../history/2026-06-27_11_review_meeting_outcomes.md`](../history/2026-06-27_11_review_meeting_outcomes.md))
- PTZ(2안)만으로 충분 — 본체 이동 불필요
- 모터/바퀴/IMU/엔코더 부담 회피
- 본 작품 컨셉(헬스케어 봇 + 시연 추가 모드) 마무리에 더 집중

아래 내용은 결정 과정 기록 보존용 — 미래 확장 토픽 참고.

**전제**: 2안(PTZ) 펌웨어/통신 인프라가 먼저 구축되어 있을 것. 1안은 그 위에 본체 이동 추가.

**핵심 아이디어**: "필요한 keypoint가 모두 보이면 더 움직일 필요 없다". 그래디언트 추적/PID 아닌 **bang-bang 제어** (on/off만). 의도가 단순해서 알고리즘 30줄로 끝남.

```python
REQUIRED_KP = [
    "left_hip",  "right_hip",
    "left_knee", "right_knee",
    "left_ankle","right_ankle",
]

def is_ready(kp, conf_th=0.5):
    return all(kp[KP[n], 2] >= conf_th for n in REQUIRED_KP)
# 또는 좌/우 분리 — 한쪽 다리만 다 보여도 카운팅 가능
def left_ready(kp):  return all(kp[KP[n], 2] >= 0.5 for n in ["left_hip","left_knee","left_ankle"])
def right_ready(kp): return all(kp[KP[n], 2] >= 0.5 for n in ["right_hip","right_knee","right_ankle"])

if left_ready(kp) or right_ready(kp):
    send_motor("STAY")           # ★ 정지 (카운팅 가능 상태)
else:
    send_motor(seek_direction(kp))  # 보일 때까지만 이동
```

**이동 결정 — 단순 3 룰 decision tree**:

| 상황 | 동작 |
|---|---|
| 사람 미검출 (모든 keypoint conf < 0.3) | 마지막 본 방향으로 천천히 회전, 5초 안에 못 찾으면 STAY |
| 사람 검출, 다리 일부 안 보임 | 살짝 후진 (~20 cm) — frame에 다리 다 들어오도록 |
| 사람 중심점이 frame 한쪽에 치우침 | 그 방향으로 본체 회전 |

**안전 메커니즘** (제한적 자율 → 충돌 부담 최소):

| 메커니즘 | 효과 |
|---|---|
| 가상 펜스 30 cm × 30 cm (IMU + 엔코더 odometry) | 시작점 기준 작은 영역 안에서만 이동 |
| 최대 속도 ~5 cm/s | 충돌 시 손상 최소 |
| 5초 안에 carving 안 되면 STAY | 무한 탐색 방지 |
| 사람 미검출 시 마지막 위치 유지 | 잘못된 방향 이동 차단 |

**하드웨어 부담**:
- 모터 2 ($15) + 드라이버 ($5) + IMU BMI160 ($5) + 작은 바퀴/캐스터 ($5) ≈ **$30**
- 서보 PTZ는 본 안에선 불필요 (본체 회전 + 후진으로 충분)

**작업 시간 (예상)**:
- UNO Q 알고리즘 ~30줄 (stop condition + 3룰) — 0.5일
- STM32U585 펌웨어 ~200줄 (PWM + IMU yaw + 엔코더 + UART 명령 처리) — 1~2일
- 통합 + 디버깅 — 1일
- **합계 2~3일** — 본 작품 마무리 안 가능

**본 작품 컨셉과 정합**: "필요한 거 다 보이면 멈춤" = **자연스러운 인터랙션 행동**. 추적 강박 X.

### 2안 — PTZ (서보 카메라 각도 조절) ★ 본 작품 선행

- 17 keypoint의 어깨 + 엉덩이 좌표로 사람 방향 + 중심 위치 추정
- 서보 2축 (pan/tilt) → **카메라만 회전, 본체는 정지** (충돌 위험 0)
- STM32U585 + 서보 PWM 펌웨어 추가 (~50줄) + UART 명령 처리
- 사람이 frame 중심 + 정면 향하도록 PID 추적 (또는 같은 stop condition 적용 가능)
- 1안의 인프라 (펌웨어 / UART / 추적 알고리즘 골격)를 먼저 구축하는 단계
- **하드웨어**: 서보 2 ($10) + 마운트 ($5) ≈ $15
- **작업**: 0.5~1일 — 본 작품 마무리 1단계 진입점

### 3안 — 카메라 위치 변경 (사람 높이) ★ 단기 즉시
- 책상 / 작은 삼각대 / UNO Q 위에 올려서 무릎 ~허리 높이 (40~50 cm)
- 약간 아래로 기울임 → 하반신 + 상체 일부 frame
- **즉시 효과, 비용 0**

## 권장 진로 (2026-06-27 리뷰 미팅 후 확정)

| 시점 | 안 | 산출 |
|---|---|---|
| 다음 측정 | **3안** | 카메라 높이 조정 + 동일 측정 → 측면/후면 인식률 향상 확인 (즉시, 비용 0) |
| **본 작품 마무리** | **2안 ★** | **PTZ 서보 추적** (위/아래/양옆) — STM32U585 PWM 펌웨어 + UART 명령 + UNO Q 추적 알고리즘. 본체 정지 |
| 범위 외 (폐기) | ~1안~ | ~본체 자율 추적~ — 2026-06-27 리뷰 미팅에서 본 작품 범위 외로 결정 |

## 영향

- **본 사용처 본 측정 13 rep 카운팅에는 무관** — 정면 자세 측정만 잘 되면 충분
- 다양한 운동 시나리오 / 사용자 자유 위치 / 교감 인터랙션 품질 — 1안(stop condition 추적)으로 해결
- 본 작품 컨셉(교감로봇) 자연스러움 ↑ — "사람을 잘 보는 위치로 자발적 이동" = 관심 표현 행동

## 관련

- 본 측정 결과: [`../history/2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md`](../history/2026-06-27_06_squat_counter_realtest_pass_with_thermal_note.md)
- 모델 후보 분석 (각도 측정 keypoint 분석): [`../docs/01_model_candidates.md`](../docs/01_model_candidates.md) §3
