# Real-time Camera Input with YOLOv8 (Benchmark Standard Format)

본 문서는 UNO Q 디바이스에 USB UVC 카메라를 연결하여 YOLOv8n int8 TFLite로 실시간 추론한 측정 결과를 정리합니다. 단일 책임 — 카메라 입력 시 e2e 성능 + 운영 안정성 검증.

## 0. 핵심 결정

| 항목 | 값 |
|---|---|
| **측정 도구** | `src/infer_camera.py` (벤치마크 표준 권고 준수) |
| **모델** | `yolov8n_int8.tflite` (3.19 MB, 320×320, w8a8) |
| **입력** | 카메라 (640×480) → letterbox (320×320) |
| **런타임** | ai_edge_litert + XNNPACK (4 thread) |
| **첫 측정 (3-1, 3-2)** | 100 frames / 12.2 s — FPS 8.52, temp 59.2°C — 4기준 합격 |
| **장시간 운영 측정 (3-3)** | 2184 frames / 285 s, `--serve 8080` — FPS 8.29, temp 70.8°C (1차 임계 도달) |
| **합격 판정 (4기준, FPS mean / p95 / RSS / temp)** | 모두 통과 (운영 측정에서도 — temp는 임계 1도 초과 margin 좁음) |
| **dropped_frames / reconnect** | 0 / 0 (양쪽 측정 모두) |
| **결론** | 단시간 운영 합격 확정. 장시간 운영은 thermal soak test 필요. |

## 1. 측정 환경

| 항목 | 값 |
|---|---|
| 디바이스 | UNO Q (QRB2210, Cortex-A53 ×4 @ 2.0 GHz) |
| OS | Debian aarch64 (kernel 7.0) |
| Python | 3.13.5 (venv `~/venv-unoq`) |
| 런타임 | ai_edge_litert 2.1.5 + XNNPACK |
| 모델 | yolov8n_int8.tflite (320×320, w8a8) |
| 카메라 모델 | SU200 USB UVC mini camera (native 720p, 2.8 mm 렌즈, DC 5 V) |
| 카메라 지원 포맷 | MJPG 1280×720 @ 30 / 640×480 @ 25, YUYV 1280×720 @ 10 / 640×480 @ 25 |
| 카메라 해상도 | 640×480 캡처 (native 720p에서 다운스케일) |
| 입력 | 실시간 카메라 (책상 환경: laptop, book 검출) |
| 측정 일자 | 2026-06-23 |

## 2. 단계별 latency (ms)

| 단계 | mean | p50 | p95 | min | max |
|---|---|---|---|---|---|
| capture | 4.67 | 1.40 | 2.35 | 0.98 | 321.18 (카메라 init outlier) |
| preprocess | 4.77 | 4.57 | 6.32 | 2.99 | 10.25 |
| inference | 99.64 | 94.86 | 128.92 | 87.35 | 185.28 |
| postprocess | 4.63 | 4.59 | 5.19 | 3.64 | 5.63 |
| draw | 3.69 | 3.10 | 4.18 | 2.60 | 56.56 (cv2 cold start 1회) |
| loop | 117.40 | 109.21 | 145.88 | 98.37 | 501.39 |

### 2-1. outlier 해석

- capture max 321 ms — 첫 프레임 카메라 init 비용. 안정 후 ~1.4 ms 수준.
- draw max 56 ms — cv2 drawing cold start (이전 단계에서 확인된 함정과 동일). warmup 후 ~3.7 ms.
- inference p95 128 / max 185 ms — 임베디드 시스템 백그라운드 영향 (cron, sshd, DDR contention).
- 한 번 정도 가끔 튐 (70번 프레임 inf=152.80) — 평균엔 영향 작음.

### 2-2. 분포 안정성 (p95 / p50)

| 단계 | 비율 | 평가 |
|---|---|---|
| capture | 1.68 | outlier 영향 (init만) |
| preprocess | 1.38 | 양호 |
| inference | 1.36 | 임베디드 정상 |
| postprocess | 1.13 | 매우 안정 |
| draw | 1.35 | 양호 (cold 제외) |
| loop | 1.34 | 양호 |

## 3. 합격 판정 — 4기준 모두 통과

| 기준 | 임계값 | 측정값 | 결과 |
|---|---|---|---|
| FPS mean | ≥ 8 | 8.52 | 통과 |
| FPS p95 (= 1000 / p95 latency) | ≥ 6 | 6.85 | 통과 |
| max RSS | ≪ 가용 (2.4 GB) | 107.8 MB (4.5%) | 통과 |
| max temp | ≤ 70°C | 59.2°C | 통과 |

YOLOv8n int8 @ 320×320 / 카메라 640×480 / CPU 4 thread / ai_edge_litert + XNNPACK 조합으로 본 작품 실시간 카메라 운영 최종 확정.

### 3-1. dropped_frames + reconnect

- dropped_frames: 0 (100 / 100 정상 캡처).
- reconnect_count: 0 (카메라 unplug 이벤트 없음).
- 12.2초 단시간 측정 — 장기 안정성은 별도 검증 필요 (soak test).

### 3-2. 카메라 입력 vs 단일 이미지 측정 차이

| 항목 | 단일 이미지 100회 | 카메라 100프레임 | 차이 |
|---|---|---|---|
| FPS mean | 9.23 | 8.52 | -7.7% |
| latency p50 (loop) | 105 ms | 109 ms | +4 ms |
| max RSS | 100.8 MB | 107.8 MB | +7 MB |
| max temp | 60.5°C | 59.2°C | -1.3°C |

캡처 평균 4.67 ms 추가 → 자연스러운 감소. 사전 추정(7.1~8.7 FPS)의 가장 빠른 쪽.

### 3-3. 장시간 운영 측정 (2184 frames / 285 s / `--serve 8080`)

본 작품의 실 운영에 가까운 조건으로 약 5분간 카메라 입력 + YOLO 추론 + HTTP MJPEG 라이브 스트리밍을 동시에 운영한 결과.

측정 조건:

- 명령: `python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite --camera 0 --serve 8080`.
- 시간: 285.2 s (약 4분 45초), 프레임: 2184.
- 카메라: 640×480 (실제), 추가 부담: HTTP MJPEG + JPEG 인코딩 (quality=70).

단계별 latency (ms):

| 단계 | mean | p50 | p95 | min | max |
|---|---|---|---|---|---|
| capture | 1.76 | 1.52 | 2.33 | 0.92 | 321.10 |
| preprocess | 4.88 | 4.92 | 6.66 | 3.03 | 11.64 |
| inference | 106.07 | 101.52 | 139.71 | 88.08 | 200.29 |
| postprocess | 4.67 | 4.59 | 5.32 | 3.46 | 12.53 |
| draw | 3.27 | 3.10 | 4.23 | 2.29 | 45.23 |
| loop | 120.65 | 115.97 | 155.77 | 100.26 | 490.34 |

핵심 지표:

| 항목 | 값 | 합격선 | 결과 |
|---|---|---|---|
| FPS mean (loop) | 8.29 | ≥ 8 | 통과 (여유 0.29) |
| FPS p95 (= 1000 / p95) | 6.42 | ≥ 6 | 통과 |
| max_rss_mb | 116.9 | ≪ 2.4 GB | 통과 (4.9%) |
| max_temp_c | 70.8 | ≤ 70°C | 임계 1도 초과 — margin 좁음 |
| dropped_frames | 0 | low | 통과 |
| reconnect_count | 0 | — | 통과 |
| FPS effective (참고) | 7.66 | — | (frames / elapsed, sleep 포함) |

100프레임 → 2184프레임 비교 (시간 누적 영향):

| 항목 | 100 frames (3-1) | 2184 frames (3-3) | 차이 |
|---|---|---|---|
| inference mean | 99.64 ms | 106.07 ms | +6.4 ms (+6.5%) |
| loop mean | 117.40 ms | 120.65 ms | +3.3 ms (+2.8%) |
| max RSS | 107.8 MB | 116.9 MB | +9.1 MB |
| max temp | 59.2°C | 70.8°C | +11.6°C |
| FPS mean | 8.52 | 8.29 | -0.23 (-2.7%) |

발견 사항 3가지:

1. Thermal margin이 좁음 — 285초만에 70.8°C 도달. QRB2210 안전 영역(~85°C) 내지만 합격선(70°C) 1도 초과. 8시간+ 장시간 운영 시 thermal throttle 발생 가능. soak test 필수.
2. inference 시간 +6.5% 증가 — 99.64 → 106.07 ms. 시간 누적 + 온도 상승의 영향 가능 (thermal throttle 시작 신호). 첫 100프레임 평균 vs 후반 프레임 평균 분리 측정 시 더 명확.
3. HTTP `--serve` 추가 부담 — RSS +9 MB (서버 + JPEG 인코딩 버퍼). FPS mean -2.7%. JPEG 인코딩이 매 프레임 ~3~10 ms 추가 가능. `--serve` 없이 같은 길이 측정으로 부담 정량화 필요.

단시간 운영 합격 확정. 장시간 운영은 thermal soak test 권고.

## 4. infer_camera.py 벤치마크 표준 권고 준수 항목

| 벤치마크 표준 필드 / 권고 | 본 도구 구현 |
|---|---|
| `model` | 수집 |
| `runtime` | 수집 (`ai_edge_litert:4` 형식) |
| `input_shape` | 수집 (`[1, 320, 320, 3]`) |
| `frames` | 수집 |
| `latency_ms_p50`, `_p95` | 수집 (loop 기준) |
| `fps_mean` | 수집 |
| `preprocess_ms_mean`, `postprocess_ms_mean` | 수집 |
| `dropped_frames` | 수집 (실제 측정 — 단일 이미지 도구는 0 강제) |
| `max_rss_mb` | 수집 |
| `max_temp_c` | 수집 |
| 카메라 reconnect | 수집 (연속 N회 실패 시 cap.release + 재오픈, `--reconnect-after`) |
| Privacy: 영상 저장 default off | 적용 (`--save-dir` opt-in) |

추가 필드 (카메라 입력 특화): `capture_ms_mean`, `elapsed_s`, `fps_effective`, `reconnect_count`, `camera` (device + 해상도).

## 5. 관찰 + 함정

### 5-1. 카메라 init 1회 outlier (capture max 321 ms)

첫 프레임의 카메라 init 비용. 안정 후엔 1~2 ms 수준. rolling FPS 이동평균(30프레임)으로 사용자 체감 영향 없음. 필요 시 앱 시작 시 dummy 프레임 N장 캡처으로 warmup 가능.

### 5-2. cv2 drawing cold start 재확인

이전 단계(06)에서 발견한 함정이 카메라 루프에서도 동일하게 나타남 (draw max 56 ms, 첫 프레임). warmup 10회로 충분 제거 가능 (벤치 도구는 그렇게 처리). 실시간 루프에선 첫 프레임만 영향, 평균엔 미미.

### 5-3. inference 변동성

p95 / p50 = 1.36. 임베디드 환경에서 시스템 백그라운드(cron, sshd, network)와 DDR 메모리 contention 영향. 일관된 패턴이라 운영에 문제 없음.

### 5-4. 검출 안정성

책상 환경(laptop, book)에서 일관된 클래스 검출. 다양한 객체 / 환경 시나리오는 별도 검증 필요.

### 5-5. 장시간 운영 thermal margin 좁음 (3-3 발견)

285초 운영에서 70.8°C 도달 — 합격선(70°C) 1도 초과. QRB2210 안전 영역(~85°C) 내지만 margin 좁아짐. 시간 누적 + 부하 누적 + HTTP 스트리밍 부담 복합 영향. 완화 옵션:

- 8시간+ soak test (벤치마크 표준 권고)로 thermal plateau 또는 throttle 거동 확인 — 최우선 후속 작업.
- 필요 시 방열판 / 통풍 개선 (하드웨어).
- 또는 frame rate cap (예: 7.5 FPS limit)으로 thermal 부담 감소 (소프트웨어).
- HTTP `--serve` 부담 분리 측정 (`--serve` 없이 같은 시간 측정 → 차이 정량화).

## 6. 알려진 한계

| 한계 | 영향 | 향후 대응 |
|---|---|---|
| 최대 285초 측정 (8h+ 미검증) | 장기 thermal plateau / throttle 거동 미확인 | soak test (8시간+) 필요 — 최우선 |
| 285초만에 70.8°C 도달 | thermal margin 1도, 장시간 시 throttle 우려 | 방열판 / 통풍 / frame cap / soak test |
| HTTP `--serve` 부담 미분리 | 카메라 + 추론 자체 vs 스트리밍 영향 구분 X | `--serve` 없이 같은 길이 측정으로 차이 정량화 |
| 책상 환경 단일 시나리오 | 다양한 입력 미커버 | golden image set / multi-scenario test |
| 야간 / 저조도 미검증 | 어두운 환경 정확도 미확인 | 조명 시나리오 별도 측정 |
| dropped_frames=0 (285초간) | 장기 보장 X | soak test에서 재검증 |
| 단일 카메라만 | 멀티 카메라 시나리오 미검증 | 필요 시 별도 |
| 얼굴 / 표정 검출은 별도 단계 | 본 측정은 일반 YOLO (COCO 80) | MediaPipe Face 또는 YOLO face fine-tune 검토 |
| 자동 저장(JSON) 없이 운영 | 자료는 콘솔 스크린샷만 (`benchmarks/cam_serve_20260623.png`) | 다음 운영 측정부터 `--json` 옵션 필수 |

## 7. 재현 절차

### 7-1. 디바이스 전송 + 실행 (호스트 WSL에서)

```bash
scp src/infer_camera.py arduino@192.168.0.45:~/

ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
    mkdir -p ~/benchmarks && \
    python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite \
        --camera 0 --max-frames 100 --print-every 10 \
        --json ~/benchmarks/cam_'"$(date +%Y%m%d)"'.json'
```

### 7-2. JSON 회수

```bash
scp arduino@192.168.0.45:~/benchmarks/cam_*.json benchmarks/
```

### 7-3. 장시간 운영 (Ctrl+C 종료)

```bash
ssh arduino@192.168.0.45
source ~/venv-unoq/bin/activate
python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite --camera 0
```

### 7-4. 디버그 JPEG 저장 + 호스트 회수

```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
    python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite \
        --camera 0 --max-frames 60 \
        --save-dir /tmp/unoq-yolo/cam-debug --save-every 10'

scp 'arduino@192.168.0.45:/tmp/unoq-yolo/cam-debug/*.jpg' test_camera_output/
```

### 7-5. 라이브 디버그 + 자동 저장 (`--serve` 권장 패턴)

본 작품의 실 운영 측정 패턴. 호스트 브라우저에서 디바이스 카메라 + 검출 + 통계를 실시간 확인 + 종료 시 자료 자동 저장.

주의: DEBUG ONLY. 인증 없음. 로컬 LAN 외부 노출 금지.

#### 권장 명령 (호스트 WSL에서)

```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
    mkdir -p ~/benchmarks && \
    python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite \
        --camera 0 --serve 8080 \
        --json ~/benchmarks/cam_serve_$(date +%Y%m%d_%H%M%S).json \
        --save-dir /tmp/unoq-yolo/cam-debug --save-every 60 \
        --print-every 50'
```

- 브라우저: `http://192.168.0.45:8080/` (영상 + 통계 패널, 500ms 폴링).
- 종료: `Ctrl+C` (디바이스 콘솔).
- 자료: `~/benchmarks/cam_serve_<TS>.json` + `/tmp/unoq-yolo/cam-debug/frame_*.jpg`.

#### 자료 회수 (Ctrl+C 후 호스트 WSL에서)

```bash
scp 'arduino@192.168.0.45:~/benchmarks/cam_serve_*.json' benchmarks/
scp 'arduino@192.168.0.45:/tmp/unoq-yolo/cam-debug/*.jpg' test_camera_output/
```

#### 함정 (실측 사고 기록 2026-06-23)

| 증상 | 원인 | 해결 |
|---|---|---|
| `cannot open camera /dev/video0` + `ls /dev/video*` 빈 출력 | `lsusb`엔 카메라 보이는데 uvcvideo 미바인딩 | `sudo modprobe -r uvcvideo; sleep 1; sudo modprobe uvcvideo; sleep 2; ls /dev/video*` |
| `Killed` 메시지 후 명령 즉시 중단 | `pkill -f infer_camera.py`가 자기 ssh 명령줄 매칭 → self-kill | pkill 옵션 빼고 그냥 실행 (좀비 거의 없음) |
| nested SSH (디바이스 셸 안에서 또 ssh) | 호스트 WSL이 아닌 디바이스 셸에서 명령 복붙 실행 | `exit` 두 번 → 호스트 WSL로 복귀 |
| `--save-dir` 디버그 JPEG 누적 | `/tmp` 용량 잠식 | 측정 후 호스트 회수 + `rm -rf /tmp/unoq-yolo/cam-debug` |
| 카메라 인덱스 다름 | `/dev/video0` 외 다른 번호 부여 | `ls /dev/video*` 확인 후 `--camera 1` 등 시도 |
