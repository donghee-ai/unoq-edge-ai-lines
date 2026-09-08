# 2026-06-29 — PTZ PoC 실용 진로 결정 (통합 우선 + STL 축소 + 즉석 카메라 고정)

## 시점

2026-06-29 (v0.1.0 release 직후, 2주 마감 일정 검토 중)

## 사건

PTZ 트랙(v0.2.0) 진행 방식을 PoC 형태 그대로 vs 통합 우선으로 검토.
사용자가 실용주의 진로 확정 — 데모 시연이 목적이라 분리 PoC + FreeCAD 작업 단계 모두 생략.

## 1. 결정 — 통합 우선 진로

### 1-1. 분리 PoC 단계 생략

| 직전 계획 | 본 결정 |
|---|---|
| `pose/ptz/` 단독 App에서 H1~H4 검증 → 성공 시 본 작품 통합 (`infer_camera_pose.py`) | **처음부터 `infer_camera_pose.py`에 직접 통합**. `ENABLE_PTZ` 토글로 PTZ ON/OFF |

근거:
- MoveNet은 분리 App 안에도 이미 내장되어 있어 "MoveNet 없어서 못 도는 것"이 아님
- 분리 PoC는 "실패 시 본 작품 무손상" 보장이 핵심 가치인데, 통합 코드도 토글 한 줄로 같은 효과
- 통합하면 MoveNet 2회 invoke → 1회로 절약 (단일 프로세스, 단일 카메라 점유)
- 2주 마감 압박 — 분리 작업 1~2일 절약

### 1-2. 통합 코드 진입점

`pose/scripts/infer_camera_pose.py`에 다음 추가:

```python
# 새 import (pose/ptz/python/main.py에서 함수 그대로)
from ptz_helpers import visibility_score, person_center_normalized

ENABLE_PTZ = True  # 토글 — False면 PTZ 비활성, 카운팅만

while True:
    frame = capture()
    kp = movenet.invoke(letterbox(frame, 256))   # 1회 invoke

    # 카운팅 라인 (기존)
    angle = knee_angle(kp, side="better")
    rep_event = counter.update(angle, time.time() * 1000)

    # PTZ 라인 (신규)
    if ENABLE_PTZ:
        vis = visibility_score(kp)
        x_n, y_n = person_center_normalized(kp, h, w)
        should_track = vis < 0.7
        if x_n is not None:
            Bridge.call("track_pose", x_n, y_n, vis, should_track)
```

`pose/ptz/python/main.py`의 helper 함수(`visibility_score`, `person_center_normalized`, `letterbox_square`, `unletterbox_kp`)는 `pose/scripts/ptz_helpers.py`로 추출하여 양쪽이 import.

STM32 측 `sketch.ino`는 **그대로 사용** — 변경 없음.

## 2. 결정 — STL 7개 다 출력 + FreeCAD 수정만 생략 + 카메라 테이프 고정

### 2-1. FreeCAD 작업 생략

사용자 결정: PoC 데모 확인이 목적이라 `camera-mount.stl`을 SU200 치수에 맞춰 FreeCAD에서 재작성하는 단계 폐기. 출력 결과가 SU200과 안 맞으면 데모용으로 테이프 고정 정도로 처리. 정식 v1.x 통합 시 SU200 전용 mount STL 신규 작성 검토.

### 2-2. 출력할 STL — Shawn 원본 7개 다

| STL | 출력? | 비고 |
|---|---|---|
| `base.stl` | 필수 | 바닥 받침 |
| `holder.stl` | 필수 | 서보 고정 프레임 |
| `gears.stl` | 필수 | tilt 회전 기어 |
| `top-with-led-ring.stl` | 출력 | LED 생략 시에도 평면 top 역할 |
| `camera-mount.stl` | 출력 | SU200 비호환 시 데모용으로 테이프 고정 |
| `spacers-*.stl` (3종) | 출력 | 높이 맞춤 |

→ **출력 7개 다 진행**. 보드 시간 + 필라멘트는 PoC 일정에 큰 부담 X.

## 3. 결정 — 최소 부품 셋

| 부품 | 수량 | 비고 |
|---|---|---|
| **SG90 서보** | **2** | pan + tilt. 토크 부족 시 MG90S 백업 |
| 외부 5V 어댑터 (≥1A) | 1 | UNO Q 5V 핀 전류 부족 — 필수 |
| 점퍼 와이어 (암-수, 암-암) | ~10 | 서보 3선 ×2 + LED 3선 |
| 양면테이프 (or 마스킹테이프) | 1 | 카메라 데모용 고정 |
| 3D 프린팅 STL | 7 | Shawn 원본 그대로 (§2-2) |
| WS2812B LED ring (선택) | 1 | 시연 보강. 없어도 회전 동작 OK |

LED ring 생략 시 `sketch.ino`의 `set_led_visibility()` 호출만 주석 처리하면 됨.

## 4. 업데이트된 PTZ 트랙 일정

| 작업 | 일수 |
|---|---|
| 부품 주문 + 배송 | 2~5일 (critical path) |
| STL 4~5개 출력 (배송과 병렬) | 1~2일 |
| 서보 + 카메라 즉석 조립 | 0.5일 |
| `ptz_helpers.py` 추출 + `infer_camera_pose.py` 통합 | 1일 |
| STM32 sketch.ino 빌드 + 업로드 | 0.5일 |
| H1~H4 측정 (PTZ ON/OFF 토글로 비교) | 1일 |
| **합계 (배송 제외)** | **4일** |

→ **부품 주문이 가장 먼저** 해야 할 작업. 배송 기간 동안 STL 출력 + 코드 통합 진행.

## 5. 영향

### 5-1. 본 라인 (Pose)

- `pose/scripts/infer_camera_pose.py`에 PTZ 코드 통합 — `ENABLE_PTZ` 토글
- `pose/scripts/ptz_helpers.py` 신규 (함수 추출)
- `pose/ptz/python/main.py`는 그대로 보존 — fork 출처 표기 + 비교 검증용

### 5-2. docs

- `docs/08_ptz_camera_angle_validation.md` §6 작업 일정 — 통합 진로 반영 갱신
- `docs/09_quickstart_ptz_poc.md` §0 사전 조건 + §1 3D 프린팅 — 부품/STL 최소 셋 반영 갱신

### 5-3. v0.2.0 진입 시점

부품 도착 ~ STL 출력 ~ 코드 통합 병렬 가능 — **부품 주문 후 작업 시작**.

## 6. 트레이드오프

| 항목 | 분리 PoC | 통합 우선 (본 결정) |
|---|---|---|
| 본 작품 메인 무손상 | 자동 보장 | `ENABLE_PTZ = False` 토글로 보장 |
| MoveNet invoke | 2회 (분리 App마다 1회) | 1회 (공유) |
| 카메라 점유 | 동시 불가 | 단일 프로세스 — 자연 해결 |
| 작업 시간 | 5~7일 | 4일 |
| H4 측정 (카운팅 정확도 향상) | 별도 비교 측정 필요 | 토글로 직접 비교 가능 |
| 펌웨어 | 동일 | 동일 |
| 시연 | App 전환 필요 | 단일 진입점 |

통합 우선의 단점 X — 분리의 모든 장점을 토글로 재현 가능.

## 7. 다음 작업

| # | 작업 | 트리거 |
|---|---|---|
| 1 | **SG90 서보 2개 + 5V 어댑터 주문** | 즉시 (critical path) |
| 2 | STL 4~5개 출력 시작 | 부품 주문 직후 |
| 3 | `ptz_helpers.py` 추출 (현 main.py에서 함수만) | 즉시 가능 — HW 무관 |
| 4 | `infer_camera_pose.py`에 통합 코드 추가 (`ENABLE_PTZ` 토글) | 즉시 가능 — HW 무관 |
| 5 | STM32 sketch.ino 빌드 + Arduino App Lab 업로드 | 부품 도착 후 |
| 6 | H1~H4 측정 + 결과 history 기록 | 조립 완료 후 |

## 관련

- 기반 코드 골격: [`2026-06-29_01_ptz_poc_code_skeleton_created.md`](2026-06-29_01_ptz_poc_code_skeleton_created.md)
- 통합 진로 직전 분석: [`2026-06-29_03_ptz_pose_integration_path_documented.md`](2026-06-29_03_ptz_pose_integration_path_documented.md)
- 리뷰 미팅 PTZ 진행 결정: [`2026-06-27_11_review_meeting_outcomes.md`](2026-06-27_11_review_meeting_outcomes.md)
- PoC 정의 + 가설 H1~H4: [`../08_ptz_camera_angle_validation.md`](../08_ptz_camera_angle_validation.md)
- 부품 + 실행 절차: [`../09_quickstart_ptz_poc.md`](../09_quickstart_ptz_poc.md)
