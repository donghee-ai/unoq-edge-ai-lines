# PTZ PoC — Pose-based Camera Tracking

본 폴더는 **본 작품 PTZ 검증 PoC** 코드. 본 작품 메인 라인(Pose v1)이 아니라 임시 검증 작업. 자세한 정의 + 가설: [`../docs/08_ptz_camera_angle_validation.md`](../docs/08_ptz_camera_angle_validation.md).

## 검증 가설 (H1~H4)

> "Pose 추적에 더 좋은 카메라 각도를 자동으로 찾아갈 수 있는가?"

| # | 가설 | 측정 |
|---|---|---|
| H1 | visibility 점수가 카메라 각도에 따라 명확히 변동 (≥ 0.3 차) | 각도별 점수 분포 |
| H2 | visibility 기반 STM32 PID가 더 좋은 각도로 자동 이동 | 영상 녹화 추적 |
| H3 | 점수 임계 통과 시 자동 정지 (stop condition) | 시각 관찰 |
| H4 | PTZ ON 시 스쿼트 카운팅 정확도 ≥ 20% 향상 | rep 검출률 비교 |

## 기반 — Shawn Hymel 프로젝트

본 PoC는 다음 프로젝트를 fork:
- **Source**: <https://github.com/ShawnHymel/face-expression-detection-robot>
- **License**: MIT (2025 Shawn Hymel)
- **자세히**: [`LICENSE`](LICENSE)

## 폴더 구조

```
ptz/
├── README.md                 (본 문서)
├── LICENSE                   MIT + 변경 사항 명시
├── app.yaml                  Arduino UNO Q App 매니페스트
├── python/
│   ├── main.py               Linux측 (Cortex-A53) — MoveNet + visibility + RouterBridge.call
│   └── requirements.txt      ai-edge-litert + opencv + numpy + pillow
└── sketch/
    ├── sketch.ino            STM32측 — track_pose 콜백 + PID 서보 + LED ring
    ├── sketch.yaml           Arduino sketch 빌드 매니페스트
    └── ws2812b-bitbang.h     WS2812B LED 드라이버 (Shawn 원본)
```

## 흐름

```
[카메라 640×480 BGR]
       │ Linux측 (Cortex-A53, python/main.py)
       ↓
[letterbox 256×256 uint8]
       ↓
[MoveNet Thunder INT8 invoke] (ai-edge-litert)
       ↓
[17 keypoint (y, x, conf)]
       ├─→ visibility_score (무릎 가중치 1.0, 엉덩이/발목 0.8, 어깨 0.5)
       │        ↓
       │   should_track = visibility < 0.7
       │
       ├─→ person_center (어깨/엉덩이 중점) → x_norm, y_norm (0~1)
       │
       └─→ Web UI 갱신 (annotated frame + stats)
       ↓
[Bridge.call("track_pose", x, y, vis, should_track)]
       │
       │ RouterBridge (UNO Q 내장)
       │
       ↓ STM32측 (M33, sketch/sketch.ino)
[track_pose() 콜백]
   if (!should_track) return;                          ← STOP condition
   if (|x_error| > 0.08)  target_pan = ...             ← 데드존 밖이면 target 업데이트
   if (|y_error| > 0.08)  target_tilt = ...
   set_led_visibility(vis);                            ← LED 색상 (적/노/녹)
       ↓
[loop() — 50ms 주기]
   PID(target - current) → 서보 PWM
```

## 빌드 + 실행

전체 절차: [`../docs/09_quickstart_ptz_poc.md`](../docs/09_quickstart_ptz_poc.md)

빠른 요약:

```bash
# 1. 모델 복사 (Pose v1 자산 활용)
cp ../models/movenet_thunder_int8.tflite python/movenet_thunder_int8.tflite

# 2. UNO Q에 push (SSH)
ssh arduino@<UNO_Q_IP> 'mkdir -p ~/ArduinoApps/ptz-poc'
scp -r ./ arduino@<UNO_Q_IP>:~/ArduinoApps/ptz-poc

# 3. UNO Q에서 실행
ssh arduino@<UNO_Q_IP>
arduino-app-cli app start ~/ArduinoApps/ptz-poc
arduino-app-cli app logs ~/ArduinoApps/ptz-poc

# 4. 브라우저: http://<UNO_Q_IP>/ptz-poc (Web UI brick)
```

## 검증 측정

| 항목 | 합격선 |
|---|---|
| H1 visibility 변동 | 좋은 각도 vs 나쁜 각도 점수차 ≥ 0.3 |
| H2 자동 추적 | 사람 frame 이동 후 5초 내 카메라 중심 |
| H3 stop condition | 임계 통과 후 카메라 정지, 사람 이동 시 재시작 |
| H4 카운팅 향상 | PTZ ON에서 측정 누락 ≥ 20% 감소 |

## 본 작품 메인 라인과의 관계

| 부분 | 본 PoC | Pose v1 (본 작품 메인) |
|---|---|---|
| 추론 모델 | 동일 (MoveNet Thunder INT8) | 동일 |
| 스쿼트 카운팅 | **본 PoC에는 없음** — visibility만 산출 | **본 작품 메인** — `infer_camera_pose.py` + `squat_counter.py` |
| 운영 | Arduino UNO Q Apps | venv-unoq Python script |

본 PoC는 **추적 기능 검증에만 집중**. 본 작품 메인 라인의 스쿼트 카운팅은 [`../scripts/infer_camera_pose.py`](../scripts/infer_camera_pose.py)에서 그대로 운영. PoC 성공 시 v1.2 통합 단계에서 통합 결정.

## 관련

- 본 PoC 정의 + 가설: [`../docs/08_ptz_camera_angle_validation.md`](../docs/08_ptz_camera_angle_validation.md)
- Quickstart: [`../docs/09_quickstart_ptz_poc.md`](../docs/09_quickstart_ptz_poc.md)
- 리뷰 미팅 결과 (PTZ만 진행 결정): [`../docs/history/2026-06-27_11_review_meeting_outcomes.md`](../docs/history/2026-06-27_11_review_meeting_outcomes.md)
- 기반 프로젝트 결정 history: [`../docs/history/2026-06-27_12_ptz_poc_decision_based_on_shawn_project.md`](../docs/history/2026-06-27_12_ptz_poc_decision_based_on_shawn_project.md)
- Pose v1 알고리즘 (PoC와 무관): [`../docs/04_squat_algorithm.md`](../docs/04_squat_algorithm.md)
