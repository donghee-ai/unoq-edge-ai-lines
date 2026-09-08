# 스쿼트 카운터 알고리즘 가이드

본 문서는 본 라인의 스쿼트 카운팅 알고리즘 자세한 흐름 + 강점/한계 + 개선 방향. 사용처 진입자가 코드 변경 전에 알고리즘 동작 모델을 정확히 알도록 정리.

## 0. 4단계 흐름 한 눈에

```
[1] MoveNet Thunder INT8 출력
    [1, 1, 17, 3]   ← 17 keypoint × (y_norm, x_norm, confidence)
         ↓
[2] 무릎 각도 계산 (좌/우 각각)
    knee_angle(kp, "left"|"right")  → 0~180° 또는 None
         ↓
[3] 좌/우 → 대표 각도 1개
    pick_angle(L, R, mode="better")
         ↓
[4] 상태 머신 (SquatCounter)
    UP ↔ DOWN  /  UP→DOWN→UP 한 사이클 = 1 rep
```

## 1. 단계 [1] — MoveNet 출력

매 카메라 프레임 → 모델 invoke → `[1, 1, 17, 3]` float32 텐서.

| 차원 | 의미 |
|---|---|
| 1 (배치) | 항상 1 |
| 1 (인물) | SinglePose Thunder는 1명만 |
| 17 (keypoint) | COCO 17점 (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles) |
| 3 (채널) | `(y_norm, x_norm, confidence)` — 좌표는 0~1 정규화 |

본 카운팅에 사용하는 6개:

```
11 left_hip       12 right_hip
13 left_knee      14 right_knee
15 left_ankle     16 right_ankle
```

(나머지는 시각화/방향 추정 보조용.)

## 2. 단계 [2] — 무릎 각도 `knee_angle(kp, side)`

```python
def knee_angle(kp, side, conf_th=0.3):
    h, k, a = (11,13,15) if side=="left" else (12,14,16)

    # confidence 게이트 — 3점 중 하나라도 0.3 미만이면 즉시 None
    if min(kp[h,2], kp[k,2], kp[a,2]) < conf_th:
        return None

    # knee를 꼭짓점으로 한 2 벡터
    ba = kp[h, :2] - kp[k, :2]    # knee → hip
    bc = kp[a, :2] - kp[k, :2]    # knee → ankle

    # 사이 각도 (cosine → arccos → degree)
    cos = (ba @ bc) / (|ba|·|bc|)
    return degrees(arccos(clip(cos, -1, 1)))
```

각도 해석:

| 각도 | 자세 |
|---|---|
| **170~180°** | Standing (다리 펴짐) |
| 130~170° | Quarter |
| 100~130° | Half |
| **~90°** | **Parallel** (스쿼트 표준 depth) |
| 30~70° | ATG (full depth) |

## 3. 단계 [3] — `pick_angle(L, R, mode="better")`

```python
def pick_angle(L, R, mode):
    if mode == "left":   return L
    if mode == "right":  return R
    if mode == "avg":    return None if (L is None or R is None) else (L+R)/2
    # "better" — 기본
    if L is not None and R is not None: return (L+R)/2
    return L if L is not None else R    # 한쪽만 검출돼도 그쪽 사용
```

**`better` 모드 채택 이유**: 본 사용처에서 사용자가 옆모습이라 한쪽 다리가 자기 신체에 가려져 자주 None. `avg`(엄격)면 카운팅 거의 안 됨, `better`(관대)면 가능한 신호 모두 활용.

## 4. 단계 [4] — `SquatCounter.update(angle, now_ms)`

### 4-1. 상태 머신 다이어그램

```
                angle < 100° + dwell ≥ 200ms
        UP ──────────────────────────────→ DOWN
         ↑                                   │
         │      angle > 140° + dwell ≥ 200ms │
         │            reps += 1              │
         └───────────────────────────────────┘
```

상태 2개. UP↔DOWN 한 사이클 = 1 rep.

### 4-2. 전환 조건 정확히

```python
# 현재 UP 상태에서
if angle < down_th and (now_ms - last_transition) >= min_dwell_ms:
    state = "DOWN"
    last_transition_ms = now_ms
    min_angle_in_down = angle

# 현재 DOWN 상태에서
if angle < min_angle_in_down:
    min_angle_in_down = angle   # 매 프레임 갱신 (deepest 추적)

if angle > up_th and (now_ms - last_transition) >= min_dwell_ms:
    state = "UP"
    last_transition_ms = now_ms
    reps += 1                   # ← 카운트는 여기서!
    last_rep_min_angle = min_angle_in_down
    min_angle_in_down = None
```

### 4-3. 기본 임계

| 파라미터 | 값 | 의미 |
|---|---|---|
| `down_th` | 100° | 이 미만이면 DOWN 진입 |
| `up_th` | 140° | 이 초과이면 UP 복귀 + REP |
| `min_dwell_ms` | 200 | 상태 전환 후 최소 유지 시간 (떨림 방지) |

CLI에서 변경 가능: `--down-th 110 --up-th 145 --min-dwell-ms 300`

## 5. 핵심 디자인 — Hysteresis (이력 현상)

`down_th < up_th`인 이유:

```
       angle
       180 ┤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ (서있음)
       170 ┤    \                /
       150 ┤━━━━━ \ ━━━━━━━━━━━ /━━━━━━ up_th=140 (이 위 → UP)
       130 ┤       \           /
       110 ┤        \         /         "데드존" — 이 사이에서 떨면
       100 ┤━━━━━━━━━ \ ━━━━ / ━━━━━━━━ down_th=100 (이 아래 → DOWN)
        90 ┤           \    /                  상태 그대로 유지
        70 ┤            \  /
        50 ┤             \/   ← deepest
                          DOWN

만약 단일 임계 (예: 120°)였다면:
  118° → 121° → 119° → 122° 같이 임계 근처에서 떨면 카운트 폭발
  hysteresis로 100~140° 사이는 "이전 상태 유지" → 안정
```

`min_dwell_ms 200ms`도 같은 목적 — transition 직후 짧은 시간 안에 또 transition 안 되도록.

## 6. 강점 — 검출 누락에 강건

매 프레임 독립이 아니라 **마지막 상태를 기억**. 검출 누락된 프레임은 `update(None)` → 즉시 return → 상태 freeze.

### 실제 trace 예 (검출 누락 끼어도 사이클 인식)

```
프레임  좌측    상태       의미
─────────────────────────────────────────
 720   L=130   UP        서있음, 굽힘 시작
 721    ?      UP        검출 누락 → freeze
 722    ?      UP        freeze
 ...
 730   L= 59   DOWN!     임계 100 미만 통과 → DOWN 진입
                         min_angle_in_down = 59
 731    ?      DOWN      freeze (min 그대로)
 732    ?      DOWN      freeze
 733   L= 48   DOWN      min 갱신 → 48 (deepest)
 734    ?      DOWN      freeze
 ...
 745   L=145   ?         ★ 145 > 140 + 200ms 통과
                         → UP 복귀, REP #1, bottom=48°
 746   L=172   UP        이미 UP, reps=1 유지
```

→ 사이에 `?`이 수십 프레임 있어도 **사이클 자체**는 인식됨.

### 검출 누락 처리 — 좌/우 조합별

| 경우 | L | R | pick_angle | counter 동작 |
|---|---|---|---|---|
| A | 130 | None | 130 | 정상 진행 |
| A' | None | 130 | 130 | 정상 진행 |
| B | None | None | **None** | **상태 freeze** (update(None) → 즉시 return) |
| C | 175 | 178 | 176.5 | 정상이지만 임계 못 통과 → UP 그대로 |

본 실측 trace에서 가장 빈번한 패턴은 B(`L=? R=?`) — 후면 자세에서 양쪽 발목 모두 가려짐.

## 7. 한계

### 7-1. 측면 — 더 깊게 굽혀야 카운트

원인: 카메라 시점에서 측면 다리가 **perspective로 압축**됨. 사용자가 실제 90° 굽혀도 카메라가 보는 각도는 ~120° → down_th 100° 통과 못 함.

해결: **방향 인식 + 임계 동적 조정** (A안)

```python
def detect_orientation(kp):
    # 어깨 폭 + nose 검출 여부로 정면/측면/후면 분류
    ...

THRESHOLDS = {
    "front":   (100, 140),
    "side":    (115, 150),   # 측면용 더 관대
    "back":    (125, 150),
    "unknown": (100, 140),
}
```

### 7-2. 후면 — pose 잡지만 카운트 거의 안 됨

원인 2가지:
1. **신호 부족**: hip-knee-ankle 3점이 일직선에 가깝게 보임 → 각도 항상 170~180°. **임계 절대 못 내려감**.
2. **검출 누락**: 사용자 신체에 다리가 가려져 발목 confidence 낮음 → 양쪽 모두 None 빈발.

해결: **다른 차원의 신호 사용** (B안 — 머리 낙차)

```python
class HeadDropCounter:
    """nose y 좌표의 sliding window amplitude.
    어깨 폭으로 정규화 → 카메라 거리 무관.
    사람이 일어났다 앉으면 머리는 카메라 방향과 무관하게 변함."""
```

### 7-3. 발목 검출이 본질적으로 약한 환경

원인: ankle은 frame 끄트머리 위치 + occlusion 빈번.

해결: **엉덩이 각도 보조** (C안 — shoulder-hip-knee, 발목 무관)

```python
def hip_angle(kp, side):
    # shoulder → hip → knee
    s, h, k = (5,11,13) if side=="left" else (6,12,14)
    if min(kp[s,2], kp[h,2], kp[k,2]) < 0.3:
        return None
    ba = kp[s,:2] - kp[h,:2]
    bc = kp[k,:2] - kp[h,:2]
    cos = (ba @ bc) / (|ba|·|bc|)
    return degrees(arccos(clip(cos, -1, 1)))
```

서있음 → ~180°, 스쿼트 → ~90~120° (상체 앞으로 숙임 + 무릎 굽힘).

### 7-3-A. 본 알고리즘과 PTZ — 현재 별개 / 통합 진로

본 알고리즘(`squat_counter.py` + `infer_camera_pose.py`)은 **메인 라인 v1**. PTZ 검증 코드(`ptz/`)는 **현재 별도 프로세스** — 동시 운영 X.

| 단계 | 통합 상태 |
|---|---|
| **현재 (PoC 검증)** | 분리 — PTZ 단독 동작 확인이 PoC 목적. 메인 v1 정지 후 PTZ 측정 |
| **v1.2 (PoC 통과 후)** | 통합 — 카메라 1회 capture + MoveNet 1회 invoke → `squat_counter.update()` + `Bridge.call("track_pose", ...)` 동시 호출 |
| **PoC 실패 시** | 메인 v1 단독 유지. PTZ 코드는 `ptz/` 보관 (확장 토픽) |

통합 시 효과: CPU/메모리 1회 추론으로 절약 + 단일 HTTP UI + 시연 한 흐름.
상세 통합 흐름 + 작업 추정: [`08_ptz_camera_angle_validation.md`](08_ptz_camera_angle_validation.md) §6-A/6-B/6-C

### 7-4. 별도 축 — 카메라/본체 추적으로 신호 부족 일부 해결

본 라인 알고리즘이 신호 부족이라 보완(A/B/C)을 추가하는 게 §7-1~7-3. 그러나 **물리적으로 카메라를 좋은 위치에 두는 것**도 해결책 — 측면/후면 자세에서도 사람이 frame 안 정면에 가깝게 들어오면 무릎 각도 신호 자체가 정확해짐.

| 진로 | 위치 |
|---|---|
| 즉시 (비용 0) | 카메라 위치 무릎~허리 높이 (40~50 cm) |
| **본 작품 마무리** | **PTZ 서보** (위/아래/양옆) — 카메라만 회전, 본체 정지 |
| (폐기, 리뷰 미팅 2026-06-27) | ~본체 자율 추적~ — 본 작품 범위 외 |

자세한 결정 과정: [`issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md), [`history/2026-06-27_11_review_meeting_outcomes.md`](history/2026-06-27_11_review_meeting_outcomes.md)

A/B/C(알고리즘 신호 보완)와 추적(물리 위치 보완)은 **독립적이고 보완 관계**:
- A/B/C는 신호 처리 — STM32 없이 UNO Q 단독으로 즉시 가능
- 추적은 하드웨어 추가 — STM32U585 + 모터/서보 필요
- 둘 다 적용하면 **신호 + 위치 두 축으로 인식 안정성 최대**

## 8. 개선 통합 방안 — A + B + C 신호 OR

```python
class MultiSignalCounter:
    """3개 카운터 OR — 어느 신호든 사이클 인식하면 rep.
    중복 방지 — 마지막 rep 후 min_dwell_ms 안 새 rep 무시."""

    def __init__(self):
        self.knee = SquatCounter(...)        # 무릎 각도
        self.head = HeadDropCounter(...)     # 머리 낙차
        self.hip  = SquatCounter(...)        # 엉덩이 각도 (다른 임계)
        self.last_rep_ms = 0
        self.reps = 0

    def update(self, kp, now_ms):
        orient = detect_orientation(kp)
        knee_th = THRESHOLDS[orient]
        self.knee.down_th, self.knee.up_th = knee_th

        ev_knee = self.knee.update(pick_angle(knee_angle(kp,"left"), knee_angle(kp,"right")))
        ev_head = self.head.update(kp)
        ev_hip  = self.hip.update(pick_angle(hip_angle(kp,"left"), hip_angle(kp,"right")))

        # 셋 중 하나라도 rep 검출 + 중복 방지
        if (ev_knee or ev_head or ev_hip) and (now_ms - self.last_rep_ms > 1000):
            self.reps += 1
            self.last_rep_ms = now_ms
            return "REP", self.reps, ...
```

목표: 정면(무릎 우세) + 측면(엉덩이 우세) + 후면(머리 낙차 우세) 모두 검출.

## 9. CLI 옵션 매핑

```
--count                  카운터 활성화
--side {left,right,avg,better}    좌/우 각도 선택 모드
--down-th N              DOWN 진입 임계 (기본 100°)
--up-th N                UP 복귀 임계 (기본 140°)
--min-dwell-ms N         상태 전환 최소 유지 (기본 200ms)
```

향후 A+B+C 통합 시 추가될 가능성:
```
--mode {knee,head,hip,multi}      신호 모드 (기본 multi)
--auto-orient                     방향 자동 인식 + 임계 동적 조정
```

## 10. 관련

- 청사진: [`00_project_blueprint.md`](00_project_blueprint.md) §7 한계 + 개선
- Quickstart: [`02_quickstart_pose.md`](02_quickstart_pose.md) §6 실행 명령
- 운영 런북: [`03_runbook_camera_serve.md`](03_runbook_camera_serve.md) §2 카운터 시나리오
- 보고: [`05_pose_line_report.md`](05_pose_line_report.md)
- 코드:
  - [`../scripts/squat_counter.py`](../scripts/squat_counter.py) (96줄, 상태 머신)
  - [`../scripts/infer_camera_pose.py`](../scripts/infer_camera_pose.py) (각도 계산 + 통합)
