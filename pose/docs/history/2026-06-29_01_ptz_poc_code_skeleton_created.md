# 2026-06-29 — PTZ PoC 코드 골격 작성 (Shawn fork)

## 시점
2026-06-29 (멘토 미팅 결과 [2026-06-27 §11] + 기반 결정 [2026-06-27 §12] 후 코드 진입)

## 사건
PTZ 검증 PoC 코드 골격 작성 — Linux측 Python (MoveNet + visibility) + STM32측 Arduino sketch (PID + LED). ShawnHymel/face-expression-detection-robot (MIT) fork.

## 진행

### 신규 폴더 — [`ptz/`](../../ptz/)

```
ptz/
├── README.md                 흐름 + 빌드 + 메인 라인 관계
├── LICENSE                   MIT + 변경 사항 명시
├── app.yaml                  UNO Q App 매니페스트 (web_ui brick + camera device)
├── python/
│   ├── main.py               Linux측 (~270줄) — MoveNet TFLite + visibility + RouterBridge
│   └── requirements.txt      ai-edge-litert + opencv-python-headless + numpy + pillow
└── sketch/
    ├── sketch.ino            STM32측 (~250줄) — track_pose 콜백 + PID + LED visibility 색상
    ├── sketch.yaml           Shawn 원본 그대로
    └── ws2812b-bitbang.h     WS2812B LED 드라이버 (Shawn 원본)
```

### Python 측 핵심 변경 (Shawn YOLO → 본 작품 MoveNet)

| Shawn 원본 | 본 PoC |
|---|---|
| `onnxruntime.InferenceSession` (YOLO) | `ai_edge_litert.Interpreter` (MoveNet Thunder INT8) |
| input 416×416 float32 | input 256×256 uint8 |
| output bounding boxes (xyxy + conf + class) | output [1,1,17,3] (y_norm, x_norm, conf) |
| `get_largest_detection()` | `person_center_normalized()` (어깨+엉덩이 중점) + `visibility_score()` (가중 평균) |
| `Bridge.call("animate_head", x, y, class, score)` | `Bridge.call("track_pose", x, y, visibility, should_track)` |
| 표정 7클래스 (CLASS_ANGRY 등) | 제거 — visibility 단일 신호 |

추가: `should_track = visibility < VISIBILITY_TRACK_TH` (0.7) — stop condition 핵심.

### STM32 측 핵심 변경 (Shawn animate_head → 본 작품 track_pose)

| Shawn 원본 | 본 PoC |
|---|---|
| `Bridge.provide("animate_head", animate_head)` | `Bridge.provide("track_pose", track_pose)` |
| 표정 7클래스 LED 패턴 + history 추적 | **제거** — visibility 단일 색상 (적/노/녹) |
| 매번 PID 실행 | **`if (!should_track) return;`** — STAY 시 target 업데이트 X |
| PID 게인 0.15/0.005/0.005 (Pan) | **동일 — Shawn 검증된 게인 그대로** |
| 데드존 8% / FOV 60°×30° | **동일** |

`set_led_visibility(vis)` — vis < 0.3 적 / 0.3~0.7 노 / ≥0.7 녹. 시각적으로 추적 상태 즉시 확인 가능.

### 라이선스

- 본 PoC 전체 MIT (Shawn 원본 + 본 작품 변경 모두)
- `ptz/LICENSE`에 원본 MIT 텍스트 + 본 작품 변경 사항 명시
- 출처: ShawnHymel/face-expression-detection-robot (2025 Shawn Hymel)

### 신규 docs

- [`docs/09_quickstart_ptz_poc.md`](../09_quickstart_ptz_poc.md) — 빌드 + 실행 + H1~H4 측정 시나리오 + 트러블슈팅

## 현 상태

| 부분 | 상태 |
|---|---|
| Python main.py | ✓ 작성 완료 (~270줄) |
| sketch.ino | ✓ 작성 완료 (~250줄) |
| README + LICENSE + app.yaml + quickstart | ✓ 작성 완료 |
| 3D 프린팅 STL | ✗ 미진행 — Shawn mechanical/ STL 7개 출력 + SU200 호환 확인 필요 |
| 하드웨어 조립 | ✗ 미진행 — SG90 ×2 + WS2812B LED + 마운트 |
| UNO Q에 push + 빌드 검증 | ✗ 미진행 — 사용자 디바이스 측 작업 |
| H1~H4 측정 | ✗ 미진행 — 하드웨어 완성 후 |

## 다음 단계 (사용자 측)

1. Shawn mechanical/ STL 7개 출력 — `git clone https://github.com/ShawnHymel/face-expression-detection-robot && ls mechanical/`
2. SU200 카메라와 `camera-mount.stl` 호환 확인 (필요 시 FreeCAD에서 본 작품용 신규)
3. SG90 ×2 + WS2812B LED ring 12 + 5V 외부 전원 준비
4. 조립 + UNO Q + STM32 연결
5. `ptz/` 폴더 통째로 `~/ArduinoApps/ptz-poc/`에 scp
6. `arduino-app-cli app start` → 로그 + Web UI 확인
7. H1~H4 측정 → `docs/history/2026-06-29_02_*.md` 신규 기록

## 본 작품 메인 라인 영향

**없음** — 본 PoC는 Arduino UNO Q App 별도 폴더. 본 작품 메인 (`scripts/infer_camera_pose.py` + venv-unoq + SSH) 그대로 유지. PoC 측정 중에는 카메라 device 충돌 회피 위해 메인 script 정지 필요.

## 관련

- 멘토 미팅 결정 (PTZ만 진행): [`2026-06-27_11_mentor_meeting_outcomes.md`](2026-06-27_11_mentor_meeting_outcomes.md)
- Shawn 기반 결정: [`2026-06-27_12_ptz_poc_decision_based_on_shawn_project.md`](2026-06-27_12_ptz_poc_decision_based_on_shawn_project.md)
- PoC 정의 + 가설: [`../08_ptz_camera_angle_validation.md`](../08_ptz_camera_angle_validation.md)
- 빌드 + 측정 절차: [`../09_quickstart_ptz_poc.md`](../09_quickstart_ptz_poc.md)
- Shawn 원본: <https://github.com/ShawnHymel/face-expression-detection-robot>
