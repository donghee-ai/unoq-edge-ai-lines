# 2026-06-27 — Pose 라인 카메라 e2e 실측 합격 (9.69 FPS, 68.6°C)

## 시점
2026-06-27 (Thunder INT8 invoke-only 합격 직후, SSH 모드 카메라 라이브 측정)

## 사건
USB 토폴로지 SSH 모드 전환(허브 + 카메라) → MoveNet Thunder INT8 + 실시간 카메라 + HTTP MJPEG serve + 자원 모니터링 1,320 프레임 (136.2초) 측정. **4 기준 모두 통과**.

## 진행

1. `scripts/infer_camera_pose.py` 신규 작성 (vision/infer_camera.py 패턴 적용 + Pose 특화):
   - 모델 로딩 (`ai_edge_litert`)
   - 카메라 letterbox 256×256 uint8 + invoke
   - 후처리: keypoint 좌표 정규화 해제 + 좌/우 무릎 각도 (hip-knee-ankle)
   - 시각화: skeleton + keypoint dot + 좌/우 무릎 각도 + depth state 오버레이
   - HTTP serve (vision과 동일 패턴) + stats.json에 CPU%/RAM/온도 추가
   - CPU% 계산: `os.times()` 차분 / wall-time (psutil 없음 안전)
2. ADB로 push (PC 직결 모드)
3. USB 토폴로지 SSH 모드 전환 (사용자 직접 — 허브 + 카메라)
4. SSH 진입 + `python3 infer_camera_pose.py movenet_thunder_int8.tflite --camera 0 --serve 8080 --print-every 10` 실행
5. 사용자가 브라우저 `http://192.168.0.45:8080/` 접속하여 실시간 디버그
6. Ctrl+C로 정상 종료, SUMMARY 회수

## 측정값 (1,320 frames / 136.2 s)

| 항목 | 측정 | 합격선 | 평가 |
|---|---|---|---|
| fps_effective | **9.69** | ≥ 8 | ✓ (21% 여유) |
| dropped_frames | **0** | — | ✓ (카메라 캡처 손실 X) |
| cpu_peak_pct (process) | **316.3** | — | 4 코어 활용 (코어당 79.1%, 21% 여유) |
| rss_peak_mb | **95.0** | ≪ 2.4 GB (총 4 GB) | ✓ |
| temp_peak_c | **68.6** | ≤ 70 | ✓ (1.4°C margin) |
| invoke (이전 측정) | 80.3 ms (p50) | — | (e2e 103 ms 추가 23 ms = 캡처/letterbox/후처리/draw/HTTP) |

### 시간 분해 (추정)

```
e2e 103 ms = invoke 80 ms + (캡처 + letterbox + 후처리 + draw + JPEG encode + HTTP serve) 23 ms
```

invoke가 78% — vision YOLO와 동일하게 추론이 명확한 병목. 카메라 native 25 fps(640×480 MJPG) 대비 추론 9.69 FPS = 38.8% 사용으로 카메라 여유 충분.

## vision YOLO와 직접 비교 (3 라인 동시 측정 가능 자료)

| 항목 | vision YOLOv8n int8 | Pose Thunder int8 | 차이 |
|---|---|---|---|
| 모델 크기 | 3.19 MB | 6.80 MB | +3.61 MB |
| 입력 해상도 | 320×320 | 256×256 | -1024 px |
| FPS e2e | 9.23 | 9.69 | +0.46 (5% 빠름) |
| CPU% (peak) | 286 | 316.3 | +30.3 (10% 더 점유) |
| RSS (peak) | 102 MB | 95.0 MB | -7 MB |
| Temp (peak) | 70.8°C | 68.6°C | -2.2°C |

→ Pose가 입력 해상도가 작아 e2e 약간 빠름, RSS 더 적음, thermal 더 낮음. CPU 점유는 약간 더 높음.

## 합격 의의

- **3 라인(vision/ASR/Pose) 모두 1차 PoC 통과** — Pose는 e2e 측정까지 완료 (vision/ASR과 동급 절차)
- AI Hub QNN 비호환 → MoveNet TFLite로 우회 한 사이클 만에 합격
- 무릎 각도(좌/우) 실시간 출력 + depth state(Standing/Quarter/Half/Parallel/ATG) 분류 동작 확인
- **HTTP MJPEG 디버그 + JSON stats 페이지**로 시각 검증 + 정량 데이터 동시 회수 가능
- vision/ASR 라인과 stack 100% 일치 (`ai-edge-litert` + XNNPACK + TFLite int8)

## 미수집 / 미확인 (다음 후보)

| 항목 | 비고 |
|---|---|
| **soak test** (≥ 10 min, 가능하면 30 min+) | 본 측정 136s만 — thermal plateau 미확인 (68.6°C는 ramp 단계일 가능성) |
| **각도 정확도 검증** | 좌/우 차이, 정지 자세 분산, 실제 측정 vs goniometer |
| **스쿼트 카운터** | 90° 통과 이벤트 카운팅 (사용처 즉시 활용) |
| **vision + Pose 동시 운영 자원 청사진** | CPU 합산 286+316 = 602% (4코어 max 400) → 경합 발생, 측정 필요 |
| **MCU 트리거** (STM32U585 LED/모터) | knee angle/depth state → 반응 시그널 |
| **JSON benchmark 저장** (`--json` 옵션 미구현) | vision에 있는 벤치마크 표준 형식 JSON 출력 추가 가능 |

## 자산

- `scripts/infer_camera_pose.py` (498줄) — 디바이스 `/home/arduino/pose_test/scripts/`에도 push 완료
- `docs/01_model_candidates.md` (1/2/3순위 + 각도 분석)
- 본 측정 raw — `(venv-unoq) ... SUMMARY` 콘솔 출력만 (JSON 저장 미수집)

## 보고용 한 줄 갱신안

> Arduino UNO Q (QRB2210 Cortex-A53 ×4 CPU only) 위 — **vision YOLOv8n int8 (e2e 9.23 FPS / 70.8°C) + ASR Whisper Tiny.en (e2e 3.18 s, 6/7 정확) + Pose MoveNet Thunder int8 (e2e 9.69 FPS / 68.6°C, 좌/우 무릎 각도 실시간 측정) 3 라인 1차 PoC 합격**. 양 라인 issues/history 실시간 기록, ADB+SSH 이중 워크플로우, HTTP MJPEG 라이브 디버그 + JSON stats 구축.

## 관련

- 다운로드 결정: [`../docs/01_model_candidates.md`](../docs/01_model_candidates.md)
- 디바이스 invoke-only: [`2026-06-27_03_movenet_thunder_int8_device_pass.md`](2026-06-27_03_movenet_thunder_int8_device_pass.md)
- AI Hub 우회 결론: [`2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md`](2026-06-27_02_onnx_vs_tflite_compatibility_analysis.md)
- USB 토폴로지: [`../../vision/docs/history/2026-06-25_03_usb_topology_decision.md`](../../vision/docs/history/2026-06-25_03_usb_topology_decision.md)
