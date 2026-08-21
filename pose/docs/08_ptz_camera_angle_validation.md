# PTZ 카메라 각도 검증 PoC

본 문서는 **본 작품 메인 컨셉(헬스케어 봇 + pose 측정)이 아닌 검증 단계** 작업의 정의 + 진행 계획 + 검증 기준 정리.

## 0. 본 작업의 정확한 위치

> **본 작업은 본 작품 핵심 기능 추가가 아니라, "카메라가 pose 추적에 적합한 각도를 자동으로 찾아갈 수 있는가?"에 대한 검증 PoC (Proof of Concept)**

| 항목 | 본 작업 |
|---|---|
| 위치 | **임시 검증 단계** — 본 작품 메인 라인(Pose v1) 외부 |
| 목적 | "pose 검출 품질이 좋은 카메라 각도를 자동 탐색 가능한가?" 가설 검증 |
| 본 작품 메인 영향 | 검증 결과에 따라 결정 — 성공 시 통합, 실패 시 카메라 수동 위치 조정으로 fallback |
| 결정 시점 | PoC 측정 후 |

본 작업이 실패해도 본 작품(헬스케어 봇 + 스쿼트 카운팅)은 **v1 베이스라인 그대로 시연 가능**. 본 작업은 그 위에 추가 가치.

## 1. 가설

| # | 가설 | 검증 방법 |
|---|---|---|
| H1 | 무릎/엉덩이/발목 keypoint의 가시성 점수(visibility score)가 카메라 각도에 따라 명확히 변동 | 다양한 각도에서 측정 → 점수 분포 차이 정량 |
| H2 | 가시성 점수 기반으로 STM32 PID가 더 좋은 각도로 자동 이동 | 사람이 frame 변경 시 카메라 추적 동작 관찰 |
| H3 | 점수 임계 통과 시 자동 정지 (stop condition) — 무한 추적 방지 | 임계 통과 후 카메라 정지 + 사람 이동 시 재시작 |
| H4 | 본 알고리즘이 본 라인 스쿼트 카운팅에 측정 정확도 향상 효과 | PTZ ON / OFF 비교 측정 (rep 검출률, deepest 정확도) |

## 2. 기반 — ShawnHymel/face-expression-detection-robot

본 PoC는 검증 시간 단축 위해 검증된 외부 자료 기반.

| 자산 | 출처 | 본 작업 활용 |
|---|---|---|
| **mechanical/ — 7개 STL** | ShawnHymel/face-expression-detection-robot (MIT) | **그대로 출력** + SU200 카메라 호환 검토 |
| **firmware/sketch/sketch.ino** (서보 PID + LED ring) | 동일 출처 | **PID 게인 + 데드존 그대로**, 표정 LED 7클래스만 제거 |
| **firmware/python/main.py** (RouterBridge 통신) | 동일 출처 | **통신 골격 그대로**, YOLO 추론 부분만 MoveNet으로 교체 |
| firmware/servo-test / neopixel-test | 동일 출처 | 부품 단독 검수 |
| FreeCAD 원본 (`spacers.FCStd`) | 동일 출처 | 카메라 치수 미스 시 수정 |

라이선스: **MIT** (출처 표기 + LICENSE 보존 시 자유 사용/수정/배포).

## 3. 본 작업 변경 부분 (Shawn 원본 → 본 작업)

### 3-1. python/main.py — 모델 + 신호 교체

```python
# Shawn 원본
results = yolo_model(frame)           # YOLOv8-nano 얼굴 + 표정
face_x, face_y = get_face_center(results)
expression = classify(results)
router_bridge.send(face_x, face_y, expression)

# ↓ 본 작업 변경
kp = movenet.invoke(letterbox(frame, 256))   # MoveNet Thunder INT8
person_x, person_y = compute_person_center(kp)   # 어깨/엉덩이 중점

visibility = visibility_score(kp, weights={
    "left_knee": 1.0,  "right_knee": 1.0,    # ★ 무릎 가중치 최대
    "left_hip": 0.8,   "right_hip": 0.8,
    "left_ankle": 0.8, "right_ankle": 0.8,
    "left_shoulder": 0.5, "right_shoulder": 0.5,
    "nose": 0.3,
})

should_track = visibility < 0.7   # 임계 통과 시 추적 정지
router_bridge.send(person_x, person_y, should_track)

# 스쿼트 카운터는 본 작품 그대로 (별도 — PTZ와 무관)
counter.update(knee_angle(kp))
```

### 3-2. sketch.ino — visibility stop 추가

```cpp
// Shawn 원본 — 매 프레임 PID 실행
if (DEBUG) Serial.println("PID step");
pan_servo.write(pid_pan(target_x));
tilt_servo.write(pid_tilt(target_y));

// ↓ 본 작업 변경 (3줄 추가)
if (!should_track) {
    return;   // PID 정지, 서보 현재 위치 유지
}
// 나머지 PID 코드 그대로
```

### 3-3. LED 표현 교체 (선택)

- Shawn 원본: 표정 7 클래스 색상 (angry/happy/...)
- 본 작업: rep 카운트 색상 (UP=흰색 / DOWN=파란색 / REP 완료=초록 깜빡) 또는 visibility 점수 시각화

## 4. 검증 기준 (성공/실패 정의)

| 측정 | 합격선 | 측정 방법 |
|---|---|---|
| **H1 — visibility 변동 폭** | 좋은 각도 vs 나쁜 각도 점수차 ≥ 0.3 | 다양한 자세에서 점수 기록 |
| **H2 — 자동 추적 동작** | 사람이 frame 한쪽으로 이동 후 5초 내 카메라가 따라가 frame 중심에 위치 | 영상 녹화 + 추적 정확도 |
| **H3 — stop condition** | 점수 임계 통과 후 카메라 정지, 사람 이동 시 재시작 | 시각 관찰 |
| **H4 — 스쿼트 카운팅 정확도 향상** | PTZ ON vs OFF에서 측정 누락 비율 비교 — PTZ ON에서 ≥ 20% 향상 | rep 검출률 + deepest 정확도 |

H1·H2·H3 모두 통과 = **PoC 검증 성공**. H4까지 통과 = 본 작품 통합 가치 확정.

## 5. 검증 결과별 본 작품 통합 결정

| 결과 | 본 작품 v1.x 통합 결정 |
|---|---|
| **모두 성공** | **v1.2 정식 통합** — PTZ가 본 작품 마무리 기능 |
| H1~H3 성공 + H4 부족 | 통합 보류 — 추적 동작은 확인했지만 측정 정확도 향상이 약함 |
| H1·H2만 성공 | 추적 로직 보완 (PID 게인 튜닝 등) 후 재검증 |
| 전체 실패 | **본 작품에서 PTZ 제외** — 카메라 수동 위치 조정(3안)만 시연. mechanical/STL은 다른 모드 시연용으로 보관 |

검증 실패해도 본 작품 핵심(헬스케어 봇 + 스쿼트 카운팅 v1)은 그대로 시연 가능.

## 6. 작업 일정 — 통합 우선 진로 (2026-06-29 변경)

### 6-0. 진로 변경 요약

직전 계획: 분리 PoC (`pose/ptz/`)에서 H1~H4 검증 → 성공 시 본 작품 통합 (v0.2.0).

**본 결정 (2026-06-29)**: 분리 PoC 단계 생략 — `pose/scripts/infer_camera_pose.py`에 처음부터 직접 통합, `ENABLE_PTZ` 토글로 PTZ ON/OFF. 분리의 "실패 시 무손상" 가치도 토글로 보장.

상세 결정 기록: [`history/2026-06-29_06_ptz_pragmatic_poc_pivot.md`](history/2026-06-29_06_ptz_pragmatic_poc_pivot.md)

### 6-1. 통합 일정

| 단계 | 시간 | 비고 |
|---|---|---|
| SG90 서보 2개 + 5V 어댑터 주문 + 배송 | 2~5일 | critical path |
| STL 7개 출력 (배송과 병렬) | 1~2일 | Shawn 원본 그대로, FreeCAD 수정 생략 |
| 서보 + 카메라 조립 (camera-mount 안 맞으면 데모용으로 테이프 고정) | 0.5일 | |
| `pose/ptz/python/main.py`의 helper 함수 → `pose/scripts/ptz_helpers.py`로 추출 | 0.3일 | HW 무관, 즉시 가능 |
| `infer_camera_pose.py`에 `visibility_score` + `Bridge.call("track_pose")` + `ENABLE_PTZ` 토글 추가 | 0.5일 | HW 무관, 즉시 가능 |
| STM32 `sketch.ino` 빌드 + Arduino App Lab 업로드 + RouterBridge 연결 확인 | 0.5일 | |
| H1~H4 측정 (PTZ ON/OFF 토글로 직접 비교) | 1일 | |
| **합계 (배송 제외)** | **4일** | 분리 PoC 대비 1~2일 절약 |

### 6-2. 분리 PoC 대비 차이

| 항목 | 분리 PoC (직전 계획) | 통합 우선 (본 결정) |
|---|---|---|
| MoveNet invoke | 2회 (분리 App마다 1회) | **1회** (공유) |
| 카메라 점유 | 동시 불가 — App 전환 필요 | 단일 프로세스로 자연 해결 |
| 본 작품 메인 무손상 | 자동 보장 | `ENABLE_PTZ = False` 토글로 보장 |
| H4 측정 (카운팅 향상) | 별도 비교 측정 | 토글로 즉시 비교 |
| 작업 시간 | 5~7일 | 4일 |
| 펌웨어 | 동일 | 동일 |
| 시연 | App 전환 | 단일 진입점 |

## 6-A. 현재 — PTZ와 메인 라인(Pose v1) 별개 시스템

본 PoC는 메인 라인 v1과 **완전히 분리된 별도 프로세스**. 동시 운영 불가능.

### 현재 두 시스템 비교

| 항목 | 메인 라인 (Pose v1) | PTZ PoC |
|---|---|---|
| 파일 | `scripts/infer_camera_pose.py` | `ptz/python/main.py` |
| 운영 방식 | venv-unoq + SSH script | Arduino UNO Q App |
| 카메라 | `cv2.VideoCapture(0)` | 동일 — `cv2.VideoCapture(0)` |
| 모델 | MoveNet Thunder INT8 | 동일 |
| 출력 | 스쿼트 rep 카운트 + HTTP MJPEG (8080) | visibility + STM32 서보 명령 |
| 스쿼트 카운터 | ✓ `squat_counter.py` 사용 | ✗ 본 PoC는 추적만 |

### 동시 운영 불가능 — 3 이유

1. **카메라 device 충돌** — `/dev/video0`을 두 프로세스가 동시 점유 X
2. **모델 추론 2회 = CPU 낭비** — 같은 keypoint를 둘 다 계산
3. **운영 환경 다름** — 한쪽은 venv-unoq SSH script, 다른 한쪽은 Arduino UNO Q Apps

→ PoC 측정 시 메인 script 정지 필수 (`docs/09_quickstart_ptz_poc.md §9`).

### 왜 지금 분리 운영이 맞는가

| 단계 | 분리/통합 |
|---|---|
| **현재 (PoC 검증)** | **별개가 맞음** — PTZ 단독 동작 확인이 목적. 통합 시 "PTZ 자체 문제 vs 카운터 충돌" 분리 진단 불가 |
| 통합 (PoC 통과 후 v1.2) | 한 프로세스로 합침 |

## 6-B. 통합 진로 (PoC 통과 시 v1.2)

PoC 검증 성공 시 한 프로세스로 합침:

```
v1.2 통합본 (예상):
  ┌──────────────────────────────────────┐
  │ 카메라 1회 capture                    │
  │   ↓                                  │
  │ MoveNet invoke (1회)                  │
  │   ↓                                  │
  │ keypoint [17, 3]                     │
  │   ├─→ squat_counter.update()         │ ← 스쿼트 rep
  │   ├─→ visibility_score()             │
  │   │     ↓                            │
  │   │   Bridge.call("track_pose", ...) │ ← 서보 PTZ
  │   ├─→ skeleton draw + 오버레이        │
  │   └─→ HTTP MJPEG serve               │
  └──────────────────────────────────────┘
```

### 통합 시 가치

- 카메라 1회, 모델 1회 → **CPU/메모리 절약** (현재 분리 운영 시 2배 비용)
- 카운터 + PTZ **동시 동작** — 한 시연 흐름에서 둘 다
- 단일 HTTP UI로 둘 다 모니터링
- 본 작품 메인 라인 v1.2로 정식 통합

### 통합 작업 시간 추정 (PoC 통과 가정)

| 단계 | 시간 |
|---|---|
| 메인 `infer_camera_pose.py`에 `visibility_score()` + `Bridge.call("track_pose", ...)` 추가 | 0.5일 |
| Arduino UNO Q App 통합 (또는 SSH script 패턴 유지) 결정 | 0.5일 |
| HTTP UI 통합 (squat stats + PTZ stats 한 페이지) | 0.5일 |
| 통합 테스트 + 디버깅 | 0.5일 |
| **합계** | **2일** |

### 통합 시 시연 시나리오

- **카운터 + PTZ 동시 동작** 단일 데모
- 사용자 자세 인식 → 카운터 카운트 + 사용자가 frame 옆으로 가면 카메라 자동 추적
- 단일 프로세스 + 단일 HTTP UI

## 6-C. PoC 실패 시 — 메인 v1 단독 진로

PoC 검증 실패 (H1~H4 미충족) 시:
- 본 PoC 코드는 `pose/ptz/` 안 보관 — 향후 확장 토픽
- 메인 라인 v1 그대로 시연 (카메라 고정, 사용자가 정면 위치)
- 멘토 보고: "추적 검증 시도 + 결과 정량 + 미통합 사유" 명시

본 작품 핵심 기능(스쿼트 카운팅 + 자세 측정)은 어느 경우든 v1으로 시연 가능.

## 7. 자료 위치

### 본 작업 fork 폴더 (계획)
- `scripts/ptz/` — Shawn 코드 fork + 본 작업 변경
  - `python/main.py` (본 작업 변경판)
  - `sketch/sketch.ino` (본 작업 변경판)
  - `app.yaml` (UNO Q Apps 매니페스트)
  - `LICENSE` (MIT, Shawn 원본 포함)
- `mechanical/` — STL 그대로
- `docs/08_ptz_camera_angle_validation.md` — 본 문서

### Shawn 원본 자료
- Repo: <https://github.com/ShawnHymel/face-expression-detection-robot>
- License: MIT (2025 Shawn Hymel)

### 본 작품 기존 자산 (변경 없음)
- `scripts/infer_camera_pose.py` — Pose v1 그대로
- `scripts/squat_counter.py` — Pose v1 그대로
- `models/movenet_thunder_int8.tflite` — Pose v1 그대로

## 8. 본 작업이 본 작품 시연에서 차지하는 위치

| 시연 시나리오 | 본 작업 활용 |
|---|---|
| **v1 베이스라인** (현재) — 카메라 고정, 사람이 카메라 frame 안에 정면으로 위치 | PTZ 없이 시연 가능 |
| **v1.x (PoC 통과 시)** — PTZ ON, 사람 위치 자동 추적 | 본 작업이 핵심 |
| **시연 강조 모드** — 시연자가 frame을 의도적으로 벗어남 → 카메라가 따라가는 모습 | 본 작업 효과 가시화 |
| **감시 모드** (시연 추가) | PTZ + visibility로 사람 위치 추적 → 본 작업 활용 가능 |

## 9. 관련

- 추적 진로 결정 (1안 폐기, PTZ만 유지): [`history/2026-06-27_11_mentor_meeting_outcomes.md`](history/2026-06-27_11_mentor_meeting_outcomes.md)
- 카메라 한계 분석 (출발점): [`issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md)
- 하우징 디자인: [`06_hardware_housing_design.md`](06_hardware_housing_design.md)
- 버전관리 (v1 베이스라인): [`07_versioning.md`](07_versioning.md)
- 본 작품 메인 알고리즘 (PTZ와 독립): [`04_squat_algorithm.md`](04_squat_algorithm.md)
- 멘토 보고: [`05_mentor_report_pose_line.md`](05_mentor_report_pose_line.md)
