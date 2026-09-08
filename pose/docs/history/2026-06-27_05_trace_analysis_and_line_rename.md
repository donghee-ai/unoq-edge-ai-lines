# 2026-06-27 — 본 세션 trace 분석 + 폴더/Docker 이름 정리 + 스쿼트 카운터 통합

## 시점
2026-06-27 (e2e 합격 직후 정리 사이클)

## 사건
사용자가 1,320 프레임 전체 trace 콘솔 로그 제공 → 패턴 분석. 동시에 본 라인 이름이 검토 단계 모델명(`unoq-mediapipe-pose`) 그대로라 일관성 정리 결정 — `unoq-pose`로 rename. 스쿼트 카운터 + 표준 스타일 docs 추가.

## 1. Trace 분석 (1,320 frames / 136.2 s)

### 1-1. FPS 안정성 — XNNPACK은 thermal에 거의 둔감

| 구간 | FPS |
|---|---|
| 0~30 (warmup) | 7.92 → 9.81 |
| 40 이후 | **10.5 ~ 11.05 안정** |
| 종료 시점 | 10.95 (thermal +14°C 상승에도 저하 없음) |

→ summary `fps_effective: 9.69`는 시작 워밍업 + 미검출 구간 평균 포함 — **운영 정상 FPS는 10.7~10.9**.

### 1-2. Thermal — plateau 미도달 (선형 ramp)

| 시점 | 온도 | Δ |
|---|---|---|
| frame 10 | 54.5°C | — |
| frame 200 | 60.5°C | +6.0 / 20 s |
| frame 500 | 63.9°C | +3.4 / 30 s |
| frame 1000 | 65.8°C | +1.9 / 50 s |
| **frame 1320** | **68.3°C** | **+2.5 / 32 s, plateau 미도달** |

→ 추세 그대로면 30~60초 더에 70°C 임계 도달 가능. **soak test 필수 — 합격 마진 정량 확보 필요**.

### 1-3. Keypoint 검출률 — 활성 20%만

전체 1,320 프레임 중 무릎 각도 측정 활성 약 **270 프레임 (20.5%)**. 870 프레임 이전(약 87초)은 거의 모두 `L=? R=?` — 사람 미입장 또는 frame out.

활성 구간(870~1140 프레임) 추출 — 실제 자세 측정:

| frame | L° | R° | depth (L) |
|---|---|---|---|
| 920 | 174 | 173 | Standing (양 다리 동시 검출 ★) |
| 950 | **84** | ? | Parallel ★ |
| 1010 | 99 | ? | Parallel |
| 1020 | **67** | 172 | ATG ★ |
| 1100 | **94** | 166 | Parallel ★ |
| 1110 | **69** | ? | ATG ★ |
| 1120 | 172 | 180 | Standing (복귀) |

→ **스쿼트 약 2~3 cycle 실제 수행됨**. 이 trace는 본 라인의 스쿼트 측정 가능성 정량 검증 자료.

### 1-4. 좌우 비대칭 — R 자주 미검출

활성 270 프레임 중 L 검출 ~80%, **R 검출 ~50%만**. 카메라가 좌측 옆모습이라 우측 다리가 자기 신체에 가려진 것으로 추정. 양 다리 동시 검출 빈도 낮음 → 카운터에 `--side better` 옵션 (둘 다 있으면 평균, 한쪽만 있으면 그쪽) 채택 근거.

## 2. 폴더 / Docker 이름 정리

### 2-1. rename 작업

| 변경 | 전 | 후 |
|---|---|---|
| 폴더 | `c:\Project\unoq-mediapipe-pose\` | `c:\Project\pose\` |
| Docker image | `unoq-mediapipe-pose:22.04` | `unoq-pose:22.04` (retag + untag) |
| 컨테이너 이름 | `unoq-mediapipe-pose` | `unoq-pose` |
| 디바이스 경로 | `/home/arduino/pose_test/` | 그대로 (이미 generic) |
| `Dockerfile.pose`, `run-pose.sh`, `requirements-pose.txt` | 파일명 그대로 (`.pose` 일관 식별자), 내부 내용 갱신 | |

### 2-2. 영향 받은 파일 (모두 갱신 완료)

7 마크다운 + 4 Docker/스크립트:
- `SESSION_SUMMARY_2026-06-27.md`
- `docs/01_model_candidates.md`
- `history/2026-06-27_01..04_*.md`
- `issues/2026-06-27_01_*.md`
- `docker/Dockerfile.pose`, `docker/run-pose.sh`, `docker/requirements-pose.txt`, `.env.example`
- `scripts/introspect_onnx.py` (docstring)

`issues/2026-06-27_02_*.md`(rename 트러블슈팅 기록)는 옛 이름 의도적으로 보존.

### 2-3. requirements 정리 — 미사용 패키지 제거

| 제거 | 이유 |
|---|---|
| `mediapipe>=0.10` | 본 라인은 MoveNet TFLite 사용, mediapipe Solutions 미사용 |
| `tensorflow>=2.16,<2.20` + `tf_keras` + `protobuf` | 모델 변환은 외부 (TFHub 직접 다운로드) — TF native PTQ 안 함 |
| `qai-hub` + `qai-hub-models[mediapipe-pose]` | AI Hub QNN ONNX QRB2210 비호환 결론 (`issues/2026-06-27_01`) |
| `torch>=2.1,<2.5` + `torchvision` | qai-hub-models 의존, 본 라인 미사용 |

남은 패키지: `numpy`, `scipy`, `opencv-python`, `pillow`, `ai-edge-litert`, `matplotlib`. Docker 빌드 시간 **≈15 min → ≈3 min** 단축 예상 (다음 rebuild 시 자동).

### 2-4. 비호환 모델 격리

`models/archive/qnn-onnx-x2-elite-incompatible/`로 이동 (5 파일, 5.5 MB):
- `metadata.json`, `pose_detector.onnx`, `pose_landmark_detector.onnx`
- `pose_detector_qairt_context.bin`, `pose_landmark_detector_qairt_context.bin`

`models/` 루트는 사용 모델 `movenet_thunder_int8.tflite` 1개만.

## 3. 스쿼트 카운터 통합

### 3-1. 신규 모듈 — `scripts/squat_counter.py`

상태 머신:
- UP (angle > up_th) ↔ DOWN (angle < down_th)
- UP → DOWN → UP 1 cycle = 1 rep
- hysteresis (down_th < up_th) + min_dwell_ms로 떨림 방지

API:
```python
c = SquatCounter(down_th=100, up_th=140, min_dwell_ms=200)
ev = c.update(angle_deg, now_ms)
# ev = None | ("REP", reps_total, min_angle_at_bottom)
c.snapshot()  # {state, reps, deepest_overall_deg, last_rep_min_deg, ...}
```

`pick_angle(left, right, mode)` 헬퍼:
- `'better'` (기본): 둘 다 있으면 평균, 한쪽만 있으면 그쪽 — 본 trace의 좌우 비대칭 패턴 대응

### 3-2. `infer_camera_pose.py` 통합

신규 옵션:
- `--count` : 카운터 활성화
- `--side {left,right,avg,better}` : 각도 선택 모드
- `--down-th`, `--up-th`, `--min-dwell-ms` : 임계 튜닝

영상 오버레이:
- 우상단 `REPS N [UP/DOWN]` 큰 글자 (rep 발생 시 색상 강조)
- 그 아래 `last min XX°` (마지막 rep의 최저 각도)

HTTP stats JSON에 `squat: { state, reps, deepest_overall_deg, last_rep_min_deg, thresholds_deg }` 추가, 매 rep 시 `last_event: { type, rep_total, min_angle_deg, frame }` 추가.

콘솔에 매 rep 즉시 출력: `  ★ REP #N  bottom=XX°  (state→UP, frame Y)`.

SUMMARY에 `squat_reps`, `deepest_deg`, `last_rep_min` 추가.

## 4. 표준 스타일 docs 추가

[`docs/00_project_blueprint.md`](../docs/00_project_blueprint.md), [`docs/02_quickstart_pose.md`](../docs/02_quickstart_pose.md), [`docs/03_runbook_camera_serve.md`](../docs/03_runbook_camera_serve.md) 3건 신규. 01은 기존 작성 활용. 참고자료(`vision/docs/_private_refs/02_quickstart_*`) 형식 참고.

## 5. ADB push 완료

```
infer_camera_pose.py  22,200 B  (스쿼트 카운터 통합)
squat_counter.py       3,858 B  (신규 모듈)
inspect_movenet_thunder.py  3,888 B  (이전 push 유지)
```

디바이스에서 syntax check OK.

## 6. 자산

신규/갱신:
- `scripts/squat_counter.py` (신규, 96줄)
- `scripts/infer_camera_pose.py` (갱신, 22 KB — 카운터 통합)
- `docs/00_project_blueprint.md` (신규)
- `docs/02_quickstart_pose.md` (신규)
- `docs/03_runbook_camera_serve.md` (신규)
- `docker/*` + `requirements-pose.txt` + `.env.example` (이름/내용 정리)
- `models/archive/qnn-onnx-x2-elite-incompatible/` (격리)
- `issues/2026-06-27_02_powershell_rename_item_created_stray_empty_folder.md` (rename 트러블슈팅)

메모리 갱신:
- `MEMORY.md` 인덱스 (3 라인 1차 PoC 합격 명시)
- `project_unoq_companion_robot.md` (Pose 경로 + 라인 명칭 변경 반영)

## 7. 다음 단계 (재정렬)

| 우선순위 | 항목 | 비고 |
|---|---|---|
| 1 | **Soak test** ≥10 min | trace 분석상 thermal plateau 미도달 — 합격 마진 정량 확보 필수 |
| 2 | **스쿼트 카운터 실측** | 사용자가 실제 옆모습 자세로 측정해서 rep 정확도 검증 |
| 3 | Vision + Pose 동시 운영 자원 청사진 | CPU 합산 286+316=602% 경합 측정 |
| 4 | `--json` benchmark 저장 옵션 (vision 패턴 적용) | 벤치마크 표준 형식 |
| 5 | MCU 트리거 (STM32U585 LED/모터) | rep 이벤트 → 반응 |

## 8. 관련

- 직전 e2e 합격: [`2026-06-27_04_pose_camera_e2e_pass.md`](2026-06-27_04_pose_camera_e2e_pass.md)
- rename 트러블슈팅: [`../issues/2026-06-27_02_powershell_rename_item_created_stray_empty_folder.md`](../issues/2026-06-27_02_powershell_rename_item_created_stray_empty_folder.md)
- USB 토폴로지: [`../../vision/docs/history/2026-06-25_03_usb_topology_decision.md`](../../vision/docs/history/2026-06-25_03_usb_topology_decision.md)
