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

## 6. 작업 일정 (PoC만)

| 단계 | 시간 |
|---|---|
| STL 호환성 확인 + 출력 + 조립 | 1~2일 |
| `python/main.py` MoveNet 이식 | 0.5일 |
| `sketch.ino` visibility stop 3줄 추가 + PID 게인 튜닝 | 0.5~1일 |
| 통합 + H1~H4 측정 | 1일 |
| **합계 (PoC만)** | **3~4일** |

본 작품 통합 결정 후 추가 작업 (LED 표현 / 다른 모드 통합 등)은 별도.

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
