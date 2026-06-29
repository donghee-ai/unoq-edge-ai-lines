# 2026-06-27 — PTZ 검증 PoC 결정 (Shawn Hymel 프로젝트 기반)

## 시점
2026-06-27 (멘토 미팅 직후 PTZ 진로 구체화 사이클)

## 사건
멘토 미팅에서 PTZ만 진행하기로 결정 후, 외부 자료 검증 — **ShawnHymel/face-expression-detection-robot** (MIT) 프로젝트가 본 작품 하드웨어 구조와 100% 일치 (Arduino UNO Q + 서보 pan/tilt + LED ring). 본 작품 PTZ 작업을 **검증 PoC**로 정의하고 Shawn 코드 기반으로 진행 결정.

## 핵심 결정

### 1. 본 작업의 정확한 위치 — 검증 PoC, 임시

본 PTZ 작업은 본 작품 핵심 기능이 아니라 **"카메라가 pose 추적용 좋은 각도를 자동으로 찾아갈 수 있는가?" 가설 검증**.

| 항목 | 본 작업 |
|---|---|
| 위치 | 본 작품 메인 라인(Pose v1) 외부 검증 단계 |
| 시간 | 3~4일 (PoC만) |
| 실패 시 영향 | 본 작품 v1 그대로 시연 가능 (PTZ 없이) |
| 성공 시 처리 | v1.2 정식 통합 |

### 2. 가설 (검증 대상)

| # | 가설 |
|---|---|
| H1 | 무릎/엉덩이/발목 visibility 점수가 카메라 각도에 따라 명확히 변동 (≥ 0.3 차) |
| H2 | visibility 기반으로 STM32 PID가 더 좋은 각도로 자동 이동 |
| H3 | 점수 임계 통과 시 자동 정지 (stop condition) |
| H4 | PTZ ON 시 스쿼트 카운팅 정확도 ≥ 20% 향상 |

### 3. Shawn 프로젝트 활용 매핑

| 자산 | 본 작업 처리 |
|---|---|
| `mechanical/` 7개 STL (base, camera-mount, gears, holder, top-with-led-ring, spacers 3종) + FreeCAD 원본 | 그대로 출력, SU200 카메라 호환 검토 |
| `firmware/sketch/sketch.ino` (서보 PID + LED ring) | PID 게인(0.15/0.005/0.005) + 데드존(8%) + FOV(60°/30°) 그대로 |
| `firmware/python/main.py` (RouterBridge 통신) | 통신 골격 그대로, YOLO 추론 → **MoveNet pose로 교체** |
| `firmware/servo-test/` + `neopixel-test/` | 부품 단독 검수 |
| 라이선스 | **MIT** — 출처 표기 + LICENSE 보존 시 자유 사용 |

### 4. 본 작업 변경 부분

#### `python/main.py`
```python
# YOLO → MoveNet 교체
kp = movenet.invoke(letterbox(frame, 256))
person_x, person_y = compute_person_center(kp)
visibility = visibility_score(kp, weights={
    "left_knee": 1.0, "right_knee": 1.0,   # 무릎 가중치 최대
    "left_hip": 0.8, ...
})
should_track = visibility < 0.7
router_bridge.send(person_x, person_y, should_track)
```

#### `sketch.ino` (STM32 펌웨어)
```cpp
if (!should_track) return;   // visibility 임계 통과 시 PID 정지
```

3줄 추가만으로 stop condition 통합.

## 본 사이클 작업 결과

### 신규 docs
- [`docs/08_ptz_camera_angle_validation.md`](../08_ptz_camera_angle_validation.md) — 본 PoC 정의 + 가설 + 검증 기준 + Shawn 활용 매핑

### 갱신 docs
- [`docs/00_project_blueprint.md`](../00_project_blueprint.md) §8-2 — PTZ가 "검증 PoC" 단계임을 명시
- [`docs/06_hardware_housing_design.md`](../06_hardware_housing_design.md) — Shawn `mechanical/` 활용 명시 + PoC와 함께 진행

### Pose 라인 docs 최종 구조
```
docs/
├── 00_project_blueprint.md         §8-2에 PoC 위치 명시
├── 01_model_candidates.md
├── 02_quickstart_pose.md
├── 03_runbook_camera_serve.md
├── 04_squat_algorithm.md
├── 05_mentor_report_pose_line.md
├── 06_hardware_housing_design.md   Shawn 출처 명시
├── 07_versioning.md
├── 08_ptz_camera_angle_validation.md  ★ 신규 — 본 PoC
├── history/  12 파일 (본 history 포함)
└── issues/   5 파일
```

## 다음 단계 (PoC 진행 시)

| 단계 | 시간 |
|---|---|
| 1. STL 호환성 확인 (SU200 카메라 치수) | 0.5일 |
| 2. STL 출력 + SG90 2개 조립 + LED ring | 1~1.5일 |
| 3. `python/main.py` fork — MoveNet 이식 | 0.5일 |
| 4. `sketch.ino` fork — visibility stop 추가 | 0.5일 |
| 5. Arduino UNO Q Apps 통합 + H1~H4 측정 | 1일 |
| **합계** | **3.5~4일** |

PoC 성공 시 v1.2로 정식 통합. 실패 시 본 작품 v1 그대로 시연 + 본 검증 자료는 history로 보존.

## 자료

- Shawn 원본 repo: <https://github.com/ShawnHymel/face-expression-detection-robot> (MIT, 2025 Shawn Hymel)
- 본 작품 PTZ 결정 근거: [`../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md`](../issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md)
- 멘토 미팅 결과 (자율 추적 폐기, PTZ만): [`2026-06-27_11_mentor_meeting_outcomes.md`](2026-06-27_11_mentor_meeting_outcomes.md)

## 본 사이클 의의

- PTZ 작업을 **"본 작품 추가 기능"이 아닌 "검증 PoC"로 명확히 정의** — 실패 안전망 확보
- Shawn 프로젝트 활용으로 **시간 5~8일 → 3~4일 단축**
- Arduino UNO Q + STM32U585 통신 골격(RouterBridge) 검증된 코드 그대로 사용
- 본 작품 v1 베이스라인은 PoC와 무관하게 유지
