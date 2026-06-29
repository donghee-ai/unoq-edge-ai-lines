# 2026-06-29 — PTZ와 메인 라인(Pose v1) 통합 진로 명시 (docs 갱신)

## 시점
2026-06-29 (PTZ PoC 코드 골격 + monorepo 통합 직후, docs 일관성 정리)

## 사건
PTZ PoC가 메인 라인 v1과 **현재 별개 시스템**임을 docs에 명확히 + 통합 진로 (v1.2) 명시. 사용자 질문 "ptz랑 pose랑 별개야?" 답변을 docs에 영구 기록.

## 핵심 명시

### 현재 — 별개 두 시스템

| 항목 | 메인 라인 (Pose v1) | PTZ PoC |
|---|---|---|
| 파일 | `scripts/infer_camera_pose.py` | `ptz/python/main.py` |
| 운영 | venv-unoq + SSH script | Arduino UNO Q App |
| 카메라 | `cv2.VideoCapture(0)` | 동일 |
| 모델 | MoveNet Thunder INT8 (TFLite) | 동일 |
| 출력 | 스쿼트 rep + HTTP MJPEG | visibility + STM32 서보 |
| 동시 운영 | **불가능** (카메라 device 충돌) |

### 통합 진로 (PoC 통과 시 v1.2)

한 프로세스:
```
카메라 1회 capture → MoveNet 1회 invoke → keypoint [17,3]
  ├─→ squat_counter.update()       (스쿼트 rep)
  ├─→ visibility_score()
  │     ↓ Bridge.call("track_pose", ...)   (서보 PTZ)
  ├─→ skeleton draw
  └─→ HTTP MJPEG serve
```

통합 작업 추정: **2일** (PoC 통과 가정).

### PoC 실패 시 — 메인 v1 단독

PTZ 코드는 `ptz/` 보관 (확장 토픽). 메인 v1 그대로 시연.

## docs 갱신 위치

| 파일 | 추가/변경 |
|---|---|
| `docs/08_ptz_camera_angle_validation.md` | **§6-A 신규** (현재 별개) / **§6-B 신규** (통합 진로) / **§6-C 신규** (PoC 실패 시 진로) |
| `docs/05_mentor_report_pose_line.md` | §7-2 표에 PoC + v1.2 통합 단계 추가 / **§7-2-A 신규** 통합 진로 요약 |
| `docs/04_squat_algorithm.md` | **§7-3-A 신규** 본 알고리즘과 PTZ 관계 명시 + 통합 시점 표 |

## 본 사이클 의의

- 사용자 질문 → docs로 영구 기록 (향후 외부 진입자 동일 질문 자동 답)
- "PoC 통과 시 v1.2 통합" 진로 명시 → 본 작품 마무리 단계 일정 명확
- 통합 시 코드 변경 위치/시간 추정 → 본 작품 계획 정량

## 관련

- 직전 monorepo 통합: [`2026-06-29_02_monorepo_restructure.md`](2026-06-29_02_monorepo_restructure.md)
- PoC 코드 골격: [`2026-06-29_01_ptz_poc_code_skeleton_created.md`](2026-06-29_01_ptz_poc_code_skeleton_created.md)
- PoC 정의: [`../08_ptz_camera_angle_validation.md`](../08_ptz_camera_angle_validation.md) §6-A/6-B/6-C
