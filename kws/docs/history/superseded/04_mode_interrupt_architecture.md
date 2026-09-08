# 모드 스위칭 인터럽트 아키텍처

본 문서는 **Pose 실행 중 KWS/버튼 이벤트로 즉시 모드를 전환** 하는 설계. 진짜 CPU 인터럽트 (하드웨어 IRQ) 가 아닌 **협력적 인터럽트** (매 프레임 poll) 방식.

## 0. 왜 협력적 인터럽트인가

pose main loop 는 XNNPACK invoke 중 GIL 을 놓고 native 코드로 실행되지만, Python 레벨 코드는 여전히 GIL 하나. 진짜 preemption 은 Python 만으로는 어려움. 대안:

| 방식 | 장점 | 단점 |
|---|---|---|
| **A. 협력적 poll** ★ | GIL 걱정 X, 단순, 5~50ms 안 latency | Python loop 100% 응답 아님 (invoke 중엔 대기) |
| B. 별도 프로세스 + signal | 진짜 preempt 가능 | 프로세스 간 IPC 오버헤드, KWS state 공유 어려움 |
| C. asyncio | 통합 이벤트 루프 | pose invoke 는 sync 라 실효 없음 |

→ **A 채택**. 매 프레임 (~100ms) `bus.poll()` 로 이벤트 소비 → **최악 latency = 1 프레임 (~100~120ms)**. 충분.

## 1. 컴포넌트

```
                ┌────────────────────────────────┐
                │ pose main loop                  │
                │   (infer_camera_pose_multimode) │
                │                                 │
                │   while True:                   │
                │     ev = bus.poll() ← ★ IRQ 점  │
                │     if ev: handle_mode_change() │
                │     frame_bgr = cap.read()      │
                │     invoke MoveNet              │
                │     process_by_mode(...)        │
                │     draw + http update          │
                └───────┬─────────────────────────┘
                        │
                        │ poll (non-block)
                        │
                ┌───────▼────────────┐
                │  ModeBus           │
                │   - queue.Queue    │  ← push (thread-safe)
                │   - current_mode   │
                │   - debounce dict  │
                │   - history[]      │
                │   - stats{}        │
                └────▲──────────▲────┘
                     │          │
                     │ push     │ push
                     │          │
     ┌───────────────┴──┐    ┌──┴─────────────────┐
     │  KWSWorker        │    │  ButtonWatcher     │
     │  (daemon thread)  │    │  (daemon thread)   │
     │                   │    │                    │
     │  ┌─────────────┐  │    │  gpiod line event  │
     │  │ mic callback│  │    │  or sysfs poll fd  │
     │  │ (PortAudio) │  │    │                    │
     │  └──────┬──────┘  │    │  edge detect →     │
     │         │ ring     │    │   short/long press │
     │         ▼ buffer   │    │                    │
     │  MFCC frontend    │    │                    │
     │         │         │    │                    │
     │         ▼         │    │                    │
     │  TFLite invoke    │    │                    │
     │  (KWS DS-CNN)     │    │                    │
     │         │         │    │                    │
     │  softmax + top-1  │    │                    │
     │         │         │    │                    │
     │  conf > threshold?│    │                    │
     └─────────┼─────────┘    └────────────────────┘
               │
               └──> bus.push("kws", label, target_mode)
```

## 2. Thread 배치

| Thread | 역할 | 우선순위 | CPU 소비 |
|---|---|---|---|
| main | pose loop (frame + MoveNet invoke + draw + http) | user | ~3 코어 (invoke) |
| kws-worker | 200ms hop 마다 MFCC + KWS invoke | user | ~15~30 ms/hop → ~15% 1 코어 |
| kws-audio-cb | PortAudio 콜백 (마이크 read) | user | 무시 |
| button-watcher | libgpiod event_wait or sysfs poll | user | 무시 (idle wait) |
| http-server | MJPEG stream + stats.json | daemon | 낮음 |

**전체 CPU 예상**: pose ~316% + kws ~20% + 나머지 ~5% = **~340%** (4코어 400% 대비 15% 여유).

## 3. Latency 예산

이벤트 발생 → 모드 전환 완료까지:

| 구간 | 예상 시간 | 비고 |
|---|---|---|
| 마이크 → ring buffer | 20~40 ms | PortAudio blocksize=200ms 안에 즉시 |
| ring → MFCC frontend | 5~15 ms | python_speech_features |
| TFLite invoke (DS-CNN) | 15~30 ms | 1 thread, XNNPACK |
| softmax + threshold | < 1 ms | numpy |
| ModeBus push + debounce | < 1 ms | queue.put_nowait |
| pose loop poll (worst case) | 0~100 ms | 프레임 주기 |
| 모드 처리 (reset counter) | < 1 ms | dataclass 재생성 |
| **합계 (worst)** | **~150 ms** | 목표 ≤ 500 ms 여유 있음 |
| **합계 (typical)** | **~100 ms** | 인간이 반응으로 느끼는 임계 (~100ms) 근사 |

## 4. Debounce 정책

| 이벤트 소스 | Debounce | 이유 |
|---|---|---|
| KWS 같은 라벨 반복 | 800 ms (ModeBus 기본) | 마이크 stream 슬라이딩 윈도우로 같은 발화가 3~5 hop 걸쳐 감지됨 |
| KWS 다른 라벨 | 0 (즉시 반영) | 사용자가 "stop go" 처럼 빠르게 전환 가능 |
| 버튼 edge | 50 ms (하드웨어 debounce) | 물리 접점 튐 억제 |
| 모드 재진입 (같은 모드) | 무시 | ev.target_mode == current_mode 면 카운터 리셋 안 함 |

## 5. Mode 정의 + 전환 표

| 모드 | 코드 (`Mode` enum) | 카운터 | 시각화 오버레이 |
|---|---|---|---|
| IDLE | `Mode.IDLE` | 없음 | skeleton + FPS |
| SQUAT | `Mode.SQUAT` | SquatCounter (기존) | 좌/우 무릎 각도 + REPS |
| PUSHUP | `Mode.PUSHUP` | PushupCounter (신규, `pose/scripts/pushup_counter.py`) | 좌/우 팔꿈치 각도 + REPS |
| SURVEIL | `Mode.SURVEIL` | 없음 (감시) | nose 위치 log |

### KWS 라벨 → 모드 매핑 (12 클래스)

```python
KWS_TO_MODE_12 = {
    "Down":  Mode.SQUAT,     # 아래로 내려가는 운동
    "Up":    Mode.PUSHUP,    # 위로 미는 운동
    "Stop":  Mode.IDLE,      # 인터럽트 (핵심)
    "Go":    None,           # 현재 모드 유지 (재개 신호)
    "Yes":   None,           # 확인 (모드 변경 X)
    "No":    Mode.IDLE,      # 취소 → IDLE
    "Left":  Mode.SURVEIL,   # 감시 모드
    "Right": None,           # 예약
    "On":    None,           # 예약
    "Off":   Mode.IDLE,      # 예약 (전원 off 은유)
}
```

### 버튼 → 모드 매핑

| 이벤트 | 액션 |
|---|---|
| Short press (< 1s) | `next_mode(current)` — cycle: IDLE → SQUAT → PUSHUP → SURVEIL → IDLE |
| Long press (≥ 1s) | `Mode.IDLE` — 즉시 STOP |

## 6. 스레드 안전성

`ModeBus` 내부:
- `queue.Queue(maxsize=16)` — thread-safe put_nowait / get_nowait
- `threading.Lock()` — current_mode, stats, history, debounce dict 보호
- push 는 queue full 이면 오래된 것 버리고 새 것 넣음 (최신 우선)

**GIL 하 안전**. pose main loop 가 100ms 안 안 놓쳐도 최악 4개까지 queue 저장, 이후 drop.

## 7. 실패 처리

| 실패 | 처리 |
|---|---|
| KWS worker start 실패 (마이크 없음) | print warning + kws_worker=None, pose 는 정상 진행 |
| Button watcher 실패 (GPIO 권한 없음) | print warning + button_watcher=None, pose + kws 는 정상 진행 |
| KWS invoke error | log + skip hop, 다음 iteration 재시도 |
| ModeBus queue full | 오래된 이벤트 drop (최신 우선 정책) |
| 카운터 reset 실패 | 없음 (dataclass 재생성만) |

## 8. 확장 여지

| 확장 | 방법 |
|---|---|
| HTTP 명령 인터럽트 | Handler 에 POST `/mode` 추가 → `bus.push("http", ..., mode)` |
| 원격 (UDP/MQTT) | 별도 worker + `bus.push` |
| Signal (SIGUSR1) 로 IDLE | `signal.signal(SIGUSR1, lambda ...: bus.set_mode(IDLE))` |
| 다른 KWS vocab | `push_map` 파라미터로 전달 (KWSWorker 생성자) |
| Whisper fallback (자연 발화) | 별도 worker (지금 ASR 라인) + queue |

## 9. 벤치마크 항목 (합격 판정)

| 항목 | 측정 방법 | 합격선 |
|---|---|---|
| KWS invoke p95 | `benchmark_kws.py --runs 100` | ≤ 50 ms |
| Pose FPS 하락 | `--enable-kws` on/off 각 5분 측정 diff | ≤ 1 FPS |
| RSS 증가 | pose 단독 vs 통합 시 diff | ≤ 30 MB |
| Thermal 증가 | soak 10분 | ≤ 2°C |
| 모드 전환 latency | KWS event timestamp → mode_switch stats delta | ≤ 500 ms |
| False trigger (clean) | 30s 조용한 방 | 0 |
| False trigger (생활 노이즈) | 30s 배경 (TV + 대화) | ≤ 2 |
| True trigger (명확 발화) | 각 명령 10회 | ≥ 8 (accuracy ≥ 80%) |

## 10. 관련

- 청사진: [`00_project_blueprint.md`](00_project_blueprint.md)
- 모델 후보: [`01_model_candidates.md`](01_model_candidates.md)
- Quickstart: [`02_quickstart_kws.md`](02_quickstart_kws.md)
- 버튼 배선: [`05_button_wiring.md`](05_button_wiring.md)
- 통합 스크립트: [`../../pose/scripts/infer_camera_pose_multimode.py`](../../pose/scripts/infer_camera_pose_multimode.py)
- KWS 워커: [`../scripts/kws_worker.py`](../scripts/kws_worker.py)
- Mode Bus: [`../scripts/mode_controller.py`](../scripts/mode_controller.py)
