# 2026-07-02 — KWS 라인 신설 + 모드 스위칭 인터럽트 스캐폴딩

## 시점

2026-07-02 (PROJECT_STATUS_2026-07-01 다음 사이클 진입)

## 사건

**목표**: pose 실행 중 KWS/버튼으로 모드 전환 가능하게 만들기.

배경: 
- ASR 라인 (Whisper 40MB) 은 **인터럽트 불가** (30초 청크 처리)
- 멘토 미팅 (2026-06-27) 에서 **KWS 로 교체 + 인터럽트** 결정
- 본 사이클에서 KWS 라인을 **v0.3.0 트랙** 으로 신설, pose 라인과 동시 실행 가능하도록 통합

## 진행

### 1. 모델 선정 — 라이선스 최우선

사용자 명시 요건: **"절대 라이센스 문제가 있어서는 안 됨"** — 상업 사용 가능 라이선스만.

후보 필터 결과:
- ✅ MLPerf Tiny DS-CNN INT8 — Apache-2.0 + CC BY 4.0, 52KB, 12 클래스 → **1순위**
- ✅ Google TFLM MicroSpeech — Apache-2.0, 18KB, 4 클래스 → **2순위 fallback**
- ✅ Silicon Labs MLTK — Apache-2.0, 다양 vocab → 3순위 예비
- ❌ Picovoice Porcupine — Non-Commercial → **기각**
- ❌ Snowboy — EOL → **기각**

상세: [`../01_model_candidates.md`](../01_model_candidates.md).

### 2. 인터럽트 아키텍처

**협력적 인터럽트** (매 프레임 `bus.poll()`) 채택. 진짜 CPU IRQ 대신 ~100ms latency 로 실용적 반응.

```
KWSWorker (daemon) → ModeBus.push → pose loop poll → mode switch
ButtonWatcher (daemon) → ModeBus.push → pose loop poll → mode switch
```

- KWS: 200ms hop 슬라이딩 윈도우, MFCC + int8 invoke, confidence > 0.60 만 push
- Button: libgpiod (권장) or sysfs GPIO fallback, short/long press 구분
- ModeBus: `queue.Queue` + debounce 800ms + 통계 stats

상세: [`../04_mode_interrupt_architecture.md`](../04_mode_interrupt_architecture.md).

### 3. Mode 4개 정의

- `IDLE`: 카운팅 없음
- `SQUAT`: 기존 SquatCounter (무릎 각도)
- `PUSHUP`: 신규 PushupCounter (팔꿈치 각도) — `pose/scripts/pushup_counter.py` 신설
- `SURVEIL`: 감시 (person 위치 로그)

### 4. 신규 파일 (본 사이클 산출물)

```
kws/                                     ← 신규 라인 루트
├── README.md
├── docker/
│   ├── Dockerfile.kws
│   ├── requirements-kws.txt
│   └── run-kws.sh
├── docs/
│   ├── 00_project_blueprint.md
│   ├── 01_model_candidates.md
│   ├── 02_quickstart_kws.md
│   ├── 03_ssh_to_benchmark_walkthrough.md    ★ 사용자 요청 (SSH→벤치마크 전 과정)
│   ├── 04_mode_interrupt_architecture.md
│   ├── 05_button_wiring.md
│   ├── history/
│   │   └── 2026-07-02_01_kws_line_created.md  (본 파일)
│   └── issues/
└── scripts/
    ├── labels_12.txt                        MLPerf DS-CNN 12 클래스
    ├── labels_4.txt                         MicroSpeech 4 클래스
    ├── download_model.py                    다중 URL fallback + SHA256
    ├── inspect_kws.py                       introspection + latency
    ├── mfcc_frontend.py                     MFCC (ds_cnn) + log-Mel (micro_speech)
    ├── mode_controller.py                   ModeBus + Mode enum + 매핑
    ├── kws_worker.py                        마이크 → KWS → ModeBus
    ├── button_watcher.py                    GPIO 버튼 → ModeBus (libgpiod + sysfs)
    ├── infer_mic_kws.py                     KWS 단독 실행 CLI
    └── benchmark_kws.py                     latency + wav-verify + JSON 저장

pose/scripts/
    ├── pushup_counter.py                    신규 — 팔굽혀펴기 카운터
    └── infer_camera_pose_multimode.py       신규 — pose + kws + button 통합
```

### 5. 결정 사항

| # | 결정 | 근거 |
|---|---|---|
| 1 | MLPerf Tiny DS-CNN INT8 (1순위) | 라이선스 + 어휘(12) + stack 일치 |
| 2 | TFLM MicroSpeech (2순위 fallback) | 확실한 URL + Apache-2.0 |
| 3 | 협력적 poll 방식 인터럽트 | Python GIL 하 단순 + 실용 latency (~100ms) |
| 4 | Mode 4개 (IDLE/SQUAT/PUSHUP/SURVEIL) | 사용처 (헬스케어 봇 + 감시) 커버 |
| 5 | 원본 `infer_camera_pose.py` 보존 + `_multimode.py` 신규 | 회귀 안전 (v0.1.0 재현 가능) |
| 6 | 버튼 hw 미준비 — 사용자 요청 시 배선 | 사용자 명시 |
| 7 | KWS threads=1, pose threads=3 | 4코어 분할 (경합 최소) |

### 6. 벤치마크 형식 — pose 라인 계승

`benchmarks/*.json` 형식은 pose 라인 (`--json` 옵션 계승) + KWS 고유 필드:
- `frontend_ms` (MFCC 계산 시간)
- `invoke_ms` (TFLite invoke)
- `wav_verify` (accuracy, per-file 결과)
- `mode_bus.stats` (mode_switches, kws_events, button_events, debounced)

### 7. 미해결 (다음 진입 시점)

| # | 항목 | 차단 사유 |
|---|---|---|
| 1 | 실기기 latency 실측 미완 | 사용자가 아직 실행 안 함 |
| 2 | 자동 모델 다운로드 URL 검증 | `download_model.py` 는 다중 fallback 이지만 URL rot 가능성 |
| 3 | 버튼 하드웨어 미준비 | 사용자 요청 시 배선 |
| 4 | 한국어 명령 미지원 | 영어 KWS 만 제공 (자체 훈련 파이프라인 문서만 준비) |
| 5 | 통합 스크립트 자동 JSON SUMMARY | 현재 수동 로그 tee — 후속 개선 |
| 6 | Soak 10분 thermal 측정 | 하드웨어 안정성 확인 필요 |
| 7 | Wav-verify golden set | Speech Commands v2 test set 서브셋 push 필요 |

### 8. 진입점 (다음 세션)

1. `PROJECT_STATUS_2026-07-01.md` + 본 파일 읽기 (5 분)
2. `kws/docs/03_ssh_to_benchmark_walkthrough.md` 따라 실측 (30~40 분)
3. 결과를 `kws/benchmarks/` 에 누적 + 본 폴더 history 신규 파일에 기록
4. Pose+KWS 통합 5분 measurement → PROJECT_STATUS_2026-07-02.md 갱신

## 자산

- [`../../README.md`](../../README.md) — 라인 진입점
- [`../00_project_blueprint.md`](../00_project_blueprint.md) — 청사진
- [`../03_ssh_to_benchmark_walkthrough.md`](../03_ssh_to_benchmark_walkthrough.md) — 실측 매뉴얼

## 관련

- ASR 라인 결정 원본: [`../../../asr/docs/history/2026-06-27_02_mentor_meeting_lightweight_model_and_interrupt_decision.md`](../../../asr/docs/history/2026-06-27_02_mentor_meeting_lightweight_model_and_interrupt_decision.md)
- Pose 라인 청사진: [`../../../pose/docs/00_project_blueprint.md`](../../../pose/docs/00_project_blueprint.md)
- Pose 통합 스크립트: [`../../../pose/scripts/infer_camera_pose_multimode.py`](../../../pose/scripts/infer_camera_pose_multimode.py)
- 이전 사이클 상태: [`../../../PROJECT_STATUS_2026-07-01.md`](../../../PROJECT_STATUS_2026-07-01.md)
- 3 트랙 제약 memory: `~/.claude/projects/c--Project/memory/project_unoq_next_cycle_constraints.md`
