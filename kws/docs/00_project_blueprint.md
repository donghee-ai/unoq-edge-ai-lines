# UNO Q KWS 라인 청사진 — 모드 스위칭 인터럽트

본 문서는 본 라인의 목적, 입력/출력, 모델/런타임 결정, 합격 기준, Pose 라인 통합 지점을 정의합니다. 외부 진입자가 30분 안에 본 라인의 의도를 파악할 수 있도록 작성.

## 0. 목표

- **입력**: USB UAC (USB Audio Class) 마이크, 16 kHz mono PCM, 1초 슬라이딩 윈도우 (200ms hop)
- **추론**: **INT8 TFLite KWS 모델**, CPU only, `ai-edge-litert` + XNNPACK (pose 라인과 동일 stack)
- **출력**:
  - top-1 라벨 + confidence
  - `ModeEvent` (모드 전환 명령) → **Mode Bus** 로 push
- **사용처 (메인)**: **모드 스위칭 인터럽트** — pose 라인이 실행 중일 때 사용자 발화로 즉시 모드 전환
- **사용처 (보조)**: 헬스케어 봇 명령 (시작/정지/다음 세트 등)
- **Fallback**: 물리 GPIO 버튼 (short-press = 다음 모드, long-press = STOP)
- **합격선**:
  - 디바이스 KWS invoke latency ≤ 50 ms (p95)
  - Pose FPS 하락 ≤ 1 (KWS 병렬 실행 시)
  - RSS 증가 ≤ 30 MB (KWS 프로세스)
  - False trigger rate < 5% (생활 노이즈 30초당 1회 이하)
  - 명령→모드 전환 latency < 500 ms (KWS invoke + mode dispatch)

## 1. 본 라인 위치 (4 라인 종합)

| 라인 | 폴더 | 모델 | 1차 PoC |
|---|---|---|---|
| Vision | [`../vision/`](../../vision/) | YOLOv8n int8 TFLite | 통과 (9.23 FPS) |
| ASR | [`../asr/`](../../asr/) | Whisper Tiny.en TFLite | 통과 (3.18s), **KWS 대체 예정** |
| Pose | [`../pose/`](../../pose/) | MoveNet Thunder INT8 TFLite | 통과 (9.69 FPS) |
| **KWS (본 라인)** | `kws/` | **MLPerf Tiny DS-CNN INT8** (1순위) | ★ **본 사이클 신설** |

네 라인 모두 동일 stack: `ai-edge-litert` + XNNPACK + TFLite int8 → 자원 청사진/디버그/배포 일관.

## 2. 모델/런타임 결정

### 2-1. 채택 — MLPerf Tiny KWS DS-CNN INT8 (1순위)

| 항목 | 값 |
|---|---|
| 출처 | MLPerf Tiny benchmark 공식 참조 모델 (mlcommons/tiny) |
| 저장소 | `https://github.com/mlcommons/tiny/tree/master/benchmark/training/keyword_spotting` |
| 라이선스 | **Apache-2.0** (코드) + **CC BY 4.0** (Speech Commands v2 데이터셋) |
| 상업 사용 | **가능** — Apache-2.0 이 명시적으로 상업 사용 허용 |
| 크기 | ~52 KB (INT8) |
| 입력 | `[1, 49, 10, 1]` int8 — MFCC 49 프레임 × 10 계수 |
| 출력 | `[1, 12]` int8 — 12 클래스 로짓 |
| 클래스 | `["Down","Go","Left","No","Off","On","Right","Stop","Up","Yes","_silence_","_unknown_"]` |
| 양자화 | full INT8 PTQ |
| 디바이스 런타임 | `ai-edge-litert` 2.1.5 + XNNPACK (chipset 비종속) |
| 예상 latency (QRB2210, threads=1) | ~10~20 ms (참조: 벤치마크 데이터로 검증 예정) |

**본 라인 12 클래스 → 모드 매핑 (예시)**:

| KWS 라벨 | 액션 |
|---|---|
| `Up` | → PUSHUP 모드 진입 |
| `Down` | → SQUAT 모드 진입 |
| `Stop` | → IDLE 모드 (현재 카운팅 중지) |
| `Go` | → 카운팅 재개 (현재 모드 유지) |
| `Yes` | 확인 응답 |
| `No` | 취소 응답 |
| `Left` / `Right` | 미사용 (예약, 시연 모드 전환 등) |
| `On` / `Off` | HTTP serve on/off, LED on/off 등 |
| `_silence_` / `_unknown_` | 무시 (필터링) |

### 2-2. 폴백 — Google TFLM MicroSpeech (2순위)

| 항목 | 값 |
|---|---|
| 출처 | `tensorflow/tflite-micro` — `tensorflow/lite/micro/examples/micro_speech` |
| 라이선스 | **Apache-2.0** |
| 상업 사용 | **가능** |
| 크기 | ~18 KB |
| 입력 | `[1, 1960]` int8 (49×40 log-Mel flatten) |
| 출력 | `[1, 4]` int8 — 4 클래스 |
| 클래스 | `["_silence_","_unknown_","yes","no"]` |
| 채택 사유 | DS-CNN 다운로드 실패 시 확실한 fallback (Google 공식 tflite-micro 예제) |

**4 클래스로도 모드 스위칭 가능 (버튼 augmentation)**:
- KWS `yes` = 확인 → 현재 후보 모드 진입
- KWS `no` = 취소 → IDLE 복귀
- 버튼 short-press = 다음 후보 모드 cycle
- 버튼 long-press = STOP

### 2-3. 기각 후보

| 모델 | 기각 사유 |
|---|---|
| Picovoice Porcupine / Snowboy | **비상업 무료** 라이선스 — 본 작품은 상업 사용 조건 명시 |
| Kitt.AI | 프로젝트 종료 (2020) — 유지보수 없음 |
| Qualcomm AI Hub precompiled QNN | X2 Elite 종속 (pose 라인 동일 문제, 별도 issues 참조) |
| openWakeWord (ONNX 전용) | 추가 onnxruntime aarch64 dep — 본 라인은 stack 일관성(TFLite) 우선 |
| Whisper Tiny.en (기존 ASR) | 40 MB, 3.18s e2e — 무거움 + **인터럽트 불가** (30초 청크 처리) |

자세한 라이선스 분석: [`01_model_candidates.md`](01_model_candidates.md).

## 3. 디렉토리 구조

```
kws/
├── docs/
│   ├── 00_project_blueprint.md          청사진 (본 문서)
│   ├── 01_model_candidates.md           모델 후보 + 라이선스 상세
│   ├── 02_quickstart_kws.md             0→30분 진입 절차
│   ├── 03_ssh_to_benchmark_walkthrough.md  SSH→벤치마크 회수 전 과정
│   ├── 04_mode_interrupt_architecture.md   Pose 통합 설계
│   ├── 05_button_wiring.md              GPIO 버튼 배선
│   ├── history/                         작업 과정 기록
│   └── issues/                          트러블슈팅
├── docker/
│   ├── Dockerfile.kws                   Ubuntu 22.04 + ai-edge-litert + sounddevice + librosa
│   ├── requirements-kws.txt
│   └── run-kws.sh                       빌드+진입 한 줄
├── models/                              KWS TFLite 파일 (git 제외)
│   ├── kws_ref_model_ds_cnn_int8.tflite    (1순위 다운로드 후)
│   ├── micro_speech.tflite                 (2순위 fallback)
│   └── labels_12.txt                       (클래스 이름)
├── scripts/
│   ├── download_model.py                모델 다운로드 + SHA256 검증 (다중 URL fallback)
│   ├── inspect_kws.py                   metadata + latency introspection (pose inspect 패턴)
│   ├── infer_mic_kws.py                 실시간 마이크 → top-1 라벨 (단독 실행)
│   ├── benchmark_kws.py                 배치 벤치마크 (JSON 저장, --json 옵션)
│   ├── kws_worker.py                    daemon thread — Mode Bus 로 push
│   ├── button_watcher.py                GPIO 버튼 watcher (sysfs)
│   ├── mode_controller.py               ModeBus + subscription 공유 상태
│   ├── mfcc_frontend.py                 MFCC 전처리 (python_speech_features 또는 librosa)
│   └── labels_12.txt                    12 클래스 라벨
├── benchmarks/                          JSON 측정 결과
└── data/                                golden wav (검증용, git 제외)
```

## 4. 외부 의존성

| 의존 | 호스트 | 디바이스 |
|---|---|---|
| Docker (Ubuntu 22.04) | 본 라인 진입 위해 필수 | X |
| Python 3.10 | 호스트 컨테이너 안 (Dockerfile) | venv-unoq (3.13.5) |
| ai-edge-litert | 2.1.1 (호스트), 2.1.5 (디바이스) | 이미 설치 (pose 공유) |
| sounddevice + PortAudio | 4.x | apt: libportaudio2 필요 |
| python_speech_features | 0.6 | pip 설치 필요 (신규) |
| numpy | 2.1.3 (호스트) | 이미 설치 |
| USB UAC 마이크 | X | 운영 모드에서 사용 |

디바이스 venv-unoq는 vision/ASR/pose 라인과 공유 — 신규 pip: `python_speech_features scipy` 만 추가.

## 5. 운영 모드 (USB 토폴로지)

pose 라인과 동일.

| 모드 | 토폴로지 | 통신 | 본 라인 활용 |
|---|---|---|---|
| **ADB** | PC ↔ USB-C ↔ UNO Q | `adb push/shell` | 모델 push, latency 측정 |
| **SSH** | UNO Q ↔ 허브 ↔ 마이크 + 카메라 | `ssh arduino@<IP>` | 실시간 마이크 KWS + pose 통합 |

## 6. Pose 라인 통합 지점

### 6-1. Pose 코드 진입점

기존: [`../../pose/scripts/infer_camera_pose.py`](../../pose/scripts/infer_camera_pose.py)

신규: **`../../pose/scripts/infer_camera_pose_multimode.py`** — 기존 코드에 `--enable-kws` / `--enable-button` 옵션 추가한 변형.

### 6-2. 통합 아키텍처 (간단)

```
┌──────────────────┐      ┌────────────────┐      ┌───────────────┐
│ Pose main loop   │──poll│  ModeBus       │◀─push│ KWS worker    │
│ (매 프레임)      │      │  (thread-safe) │      │ (daemon)      │
└────────┬─────────┘      └────────────────┘      └───────────────┘
         │                        ▲
         │                        │push
         │              ┌─────────┴──────┐
         │              │ Button watcher │
         │              │ (sysfs GPIO)   │
         │              └────────────────┘
         │
    ┌────▼────────────────────────────────────┐
    │ Mode-specific algorithm                 │
    │  IDLE: skeleton only                    │
    │  SQUAT: infer_camera_pose SquatCounter  │
    │  PUSHUP: elbow-angle counter (신규)     │
    │  SURVEIL: person detect + track only    │
    └─────────────────────────────────────────┘
```

자세한 설계: [`04_mode_interrupt_architecture.md`](04_mode_interrupt_architecture.md).

### 6-3. 프로세스 배치

| 옵션 | 배치 | 장점 | 단점 |
|---|---|---|---|
| **A. 단일 프로세스 (thread)** ★ | Pose main + KWS worker daemon thread 1개 | RAM 절감, 로그 단일화 | Python GIL로 KWS latency 살짝 증가 |
| B. 2 프로세스 + 소켓 IPC | pose.py + kws.py + Unix socket | 격리, 강제 종료 안전 | 코드 복잡 + 소켓 latency |

→ **A. 단일 프로세스 채택** (v0.3.0 진입 사이클 우선 단순화).

## 7. 합격 평가 기준

| 기준 | 합격선 | 측정 방식 |
|---|---|---|
| KWS invoke latency (p95) | ≤ 50 ms | `benchmark_kws.py --runs 100` |
| Pose FPS 하락 (KWS ON) | ≤ 1 | `infer_camera_pose_multimode.py --enable-kws` 5분 측정 |
| RSS 증가 (KWS 추가) | ≤ 30 MB | `/proc/self/status` diff |
| Thermal 증가 | ≤ 2°C | soak 10분 |
| False trigger (생활 노이즈) | ≤ 2/분 | 30초 clean + 30초 노이즈 양측 측정 |
| 명령→모드 전환 latency | ≤ 500 ms | `time.perf_counter` 로그 |

정량 측정은 `benchmarks/*.json` 에 누적. 형식은 pose 라인과 일치.

## 8. 다음 단계

| 우선순위 | 항목 |
|---|---|
| 1 | 모델 다운로드 + 호스트 introspection ([02_quickstart_kws.md](02_quickstart_kws.md) §2~§3) |
| 2 | 디바이스 push + latency 측정 ([03_ssh_to_benchmark_walkthrough.md](03_ssh_to_benchmark_walkthrough.md)) |
| 3 | Pose 통합 스크립트 실행 + 모드 스위칭 검증 |
| 4 | 물리 버튼 배선 + 검증 ([05_button_wiring.md](05_button_wiring.md)) — 사용자 하드웨어 준비 후 |
| 5 | Clean + 생활 노이즈 양쪽 false trigger 측정 |

## 9. 관련

- 후보 결정: [`01_model_candidates.md`](01_model_candidates.md)
- Quickstart: [`02_quickstart_kws.md`](02_quickstart_kws.md)
- SSH→벤치마크 가이드: [`03_ssh_to_benchmark_walkthrough.md`](03_ssh_to_benchmark_walkthrough.md)
- 통합 아키텍처: [`04_mode_interrupt_architecture.md`](04_mode_interrupt_architecture.md)
- ASR 라인 히스토리 (KWS 결정 원본): [`../../asr/docs/history/2026-06-27_02_mentor_meeting_lightweight_model_and_interrupt_decision.md`](../../asr/docs/history/2026-06-27_02_mentor_meeting_lightweight_model_and_interrupt_decision.md)
- Pose 라인 청사진: [`../../pose/docs/00_project_blueprint.md`](../../pose/docs/00_project_blueprint.md)
- 세션 상태: [`../../PROJECT_STATUS_2026-07-01.md`](../../PROJECT_STATUS_2026-07-01.md)
