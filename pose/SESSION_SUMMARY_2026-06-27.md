# Session Summary — 2026-06-27

> **본 세션 최종 결과 (멘토 미팅 후 확정)**:
> 1. Pose 라인 완전 정착 — MoveNet Thunder INT8 TFLite, e2e 9.6 FPS, 스쿼트 카운터 실측 13 rep, **v1 베이스라인 동결**
> 2. AI Hub QNN ONNX(X2 Elite 종속) 비호환 결론 → TFLite 우회 진로 확정
> 3. 폴더 `unoq-mediapipe-pose` → `unoq-pose` rename + Docker tag 재태깅 + 미사용 의존 제거
> 4. history/issues를 docs/ 하위로 통합 (3 라인 모두)
> 5. 멘토 미팅 결정 5건: PTZ만 (자율 추적 폐기) / 하우징 디자인 / v1 동결 / ASR 가벼운 모델 / 시연 모드 다양화 (메인=헬스케어)

본 세션 시작 시점에는 vision/ASR 자원 측정 + ADB 셋업 + MediaPipe Pose 환경 구축 + qai-hub 인증 시도 + ONNX 다운로드 결정까지였음. 그 이후 ONNX 비호환 발견 → MoveNet TFLite 우회 → 카운터 통합 → 측정 누적 → docs 정비 → 멘토 미팅까지 진행 완료.

## 0. 세션 결정 요약 (본 세션 종료 시점)

| 항목 | 결과 |
|---|---|
| Pose 라인 모델 | **MoveNet Thunder INT8 TFLite** (Apache-2.0 + CC BY 4.0, 6.80 MB) |
| Pose 측정 (3회 누적) | e2e 9.55~9.69 FPS, CPU 311~316%, RSS ~95 MB, thermal plateau ~71°C |
| 스쿼트 카운터 | 실측 9~13 rep, deepest 28~66°, 카운팅 정확 |
| AI Hub QNN ONNX | **비호환 확정** (X2 Elite HTP 의존, QRB2210 미적용) → TFLite 우회 |
| 폴더 정리 | `unoq-mediapipe-pose` → `unoq-pose`, Docker tag 재태깅, 미사용 의존 제거 |
| docs 구조 | `docs/` 통합 (00~07 + history 11 + issues 5) — history/issues를 docs/ 하위로 |
| **멘토 미팅 결정** | (1) PTZ만, 자율 추적 폐기 / (2) 하우징 디자인 (귀엽거나/드래곤 + 파랑·흰색) / (3) v1 베이스라인 동결 / (4) ASR 가벼운 모델 교체 + 인터럽트 / (5) 시연 모드 다양화 (메인=헬스케어, 서브=감시) |
| **v1 베이스라인** | **2026-06-27 동결** — 3 라인 모두. 후속 변경은 v1.1 / v2 부여 |
| 다음 첫 작업 (다음 세션) | (1) A+B+C 다중 신호 카운터 통합 / (2) PTZ 펌웨어 시작 / (3) ASR KWS 후보 검토 |

## 1. 본 세션 진행 시간선

| # | 작업 | 결과 |
|---|---|---|
| 1 | vision 카메라 100 frames CPU/RSS 측정 (HTTP serve 포함) | **CPU 286% / RSS 102 MB** |
| 2 | ASR Whisper JFK wav 1 invoke CPU/RSS | **CPU 212% / RSS 357 MB** |
| 3 | issues/ + history/ 워크플로우 채택 (asr + companion-robot 양 라인) | README + 첫 기록 완료 |
| 4 | ADB 셋업 — Arduino IDE 번들 adb 발견 (`/c/Users/A/AppData/Local/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe`) | Device serial `1204329696`, 비번 X |
| 5 | USB 토폴로지 함정 (허브 경유 시 "Billboard Device"만 등록, 데이터 X) | issues 2건 기록 |
| 6 | USB 토폴로지 이중 모드 결정 — ADB(PC 직접) + SSH(허브+카메라/마이크) | history 기록 |
| 7 | MediaPipe Pose Qualcomm AI Hub 검토 + 채택 (lite, 2-stage, w8a8) | qai-hub-models GitHub + AI Hub 페이지 분석 |
| 8 | `pose/` 폴더 생성 + Docker 작성 + 빌드 | 4.31 GB image 빌드 완료 |
| 9 | qai-hub 인증 시도 — 토큰 노출 + .env CRLF/newline 문제로 실패 | issues 후속 기록 필요 |
| 10 | 사용자가 페이지에서 직접 ONNX (w8a8) 다운로드 결정 | 다운로드 진행 중 (세션 종료 시점) |

## 2. 본 작품 3 라인 현재 상태

| 라인 | 폴더 | 모델 | 디바이스 검증 | 1차 PoC 합격선 |
|---|---|---|---|---|
| **Vision** | `c:\Project\vision\` | YOLOv8n int8 TFLite (3.19 MB) | **e2e 9.23 FPS, CPU 286%/RSS 102 MB ★** | 통과 (4 기준) |
| **ASR (Audio)** | `c:\Project\asr\` | Whisper Tiny.en TFLite (40 MB) | **e2e 3.18초 / 6단어 중 5정확 / CPU 212%/RSS 357 MB ★** | 통과 (4+1 기준) |
| **Pose (신규)** | `c:\Project\pose\` | MoveNet Thunder int8 TFLite (6.80 MB, AI Hub QNN ONNX 비호환 후 전환) | **e2e 9.69 FPS, CPU 316%/RSS 95 MB/68.6°C ★** | 통과 (4 기준) — 좌/우 무릎 각도 실시간 |

## 3. 핵심 자산 매트릭스

### Docker images (3개)

```
unoq-yolo-dev:22.04         13.0 GB   (vision)
unoq-asr-dev:22.04          4.78 GB   (ASR)
unoq-pose:22.04   4.31 GB   (pose, 본 세션 신규)
```

### unoq-pose 폴더 구조 (본 세션 신규)

```
pose/
├── .gitignore                    models/data/benchmarks/Python/editor 제외
├── docker/
│   ├── Dockerfile.pose           Ubuntu 22.04 + Python 3.10 + ai-edge-litert + opencv (최소 의존성)
│   ├── requirements-pose.txt
│   ├── .dockerignore
│   └── run-pose.sh               빌드+진입 한 줄, --rebuild 옵션
├── models/                       ← ONNX 다운로드 위치 (비어있음)
├── src/ data/ benchmarks/ scripts/  (빈 폴더)
└── docs/                         가이드 + 트러블슈팅 + 히스토리 통합
    ├── issues/                   워크플로우 적용됨 (README + 첫 기록)
    └── history/                  워크플로우 적용됨
```

### 디바이스 venv-unoq 추가 패키지 (본 세션 변경 없음 — 디바이스 그대로)

```
ai-edge-litert 2.1.5
numpy 2.5.0
opencv-python-headless 4.13.0.92
sounddevice 0.5.5 (이전 세션)
scipy 1.18.0 (이전 세션)
tokenizers (이전 세션, ASR용)
soundfile (이전 세션, ASR용)

다음 세션 신규 설치 예정:
  onnxruntime (pose ONNX 추론용, ADB로 pip install)
```

## 4. 본 세션 측정 자료 (실측)

### Vision YOLO (HTTP serve + 카메라 100 frames)

```json
{
  "elapsed_s": 13.60,
  "user_s": 34.92,
  "system_s": 1.56,
  "percent_cpu": 268,
  "max_rss_kb": 101056,
  "fps_mean_estimated": 7.35,
  "command": "infer_camera.py --camera 0 --max-frames 100 (no --serve)"
}
```

### Vision YOLO (HTTP serve + camera, top 실시간)

```
%CPU 286.1, RSS 104664 KB (≈102 MB), VIRT 1112376 KB, S=R, %MEM 2.8
```

### ASR Whisper JFK wav 1 invoke

```json
{
  "elapsed_s": 5.77,
  "user_s": 11.87,
  "system_s": 0.39,
  "percent_cpu": 212,
  "max_rss_kb": 365476,
  "model": "whisper_tiny_en.tflite",
  "invoke_ms": 2884,
  "transcribe_total_ms": 3547
}
```

### 동시 운영 자원 청사진 (실측 합산)

| 시나리오 | CPU% | RSS MB | 합격 평가 |
|---|---|---|---|
| vision continuous (serve) | 286 | 102 | OK |
| ASR burst (1회 invoke) | 212 | 357 | OK |
| 동시 burst | 498 | 459 | CPU 경합 → 이벤트 기반 필수 |
| 5분 평균 (이벤트 기반, 1분에 2회 발화) | 311 | 459 max | **OK (4 core 78%)** |

## 5. 발견된 함정 (본 세션, 다음 세션 재발 방지)

| 함정 | 원인 | 해결 |
|---|---|---|
| ADB 허브 경유 시 "Billboard Device"만 등록 | USB-C 케이블 데이터 라인 X 또는 허브 호환성 | PC 직접 연결 (`vision/docs/issues/2026-06-25_02_*.md`) |
| Claude Bash 환경 = Git Bash (WSL 아님) | PATH가 `/c/Users/A`, `/mingw64/bin` 등 Windows | `wsl bash -c '...'`로 호출 또는 명시적 .exe 사용 |
| Arduino 번들 adb 위치 발견 | platform-tools / Android Studio 미설치이지만 Arduino IDE 번들 사용 가능 | `/c/Users/A/AppData/Local/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe` |
| docker --env-file이 .env 마지막 줄 newline 부재 시 무시 | .env 마지막에 `\n` 없음 → 변수 인식 X | `echo "" >> .env` 또는 `sed -i -e '$a\' .env` |
| docker --env-file CRLF 혼용 라인 처리 변동 | Windows 에디터로 .env 작성 시 CRLF 첫 줄 + LF 토큰 줄 | LF only로 통일 (`unix2dos` 또는 nano LF 모드) |
| qai-hub mount 권한 (root:root) | 호스트 `~/.qai_hub` 폴더 root 소유로 컨테이너 dev 못 씀 | mount 제거 + entrypoint에서 직접 client.ini 작성 (✓ 적용됨) |
| 컨테이너 HOME 환경변수 `/home/a` (호스트 HOME) | --env-file이 HOME 자동 전달 | `-e HOME=/home/dev` 명시 (✓ 적용됨) |
| qai-hub list-devices 실패 ("Failed to authenticate") | 토큰 잘못/만료 + 위 .env 문제 복합 | **토큰 재발급 + .env 깨끗 작성 필요** |

### ⚠️ 보안 — 토큰 노출

본 세션 진단 중 hex dump에 토큰 일부 노출됨:

→ **다음 세션 시작 시 즉시 revoke + 새 토큰 발급** (https://workbench.aihub.qualcomm.com/account/).

## 6. 다음 세션 즉시 진입 — ONNX Pose 검증

사용자가 본 세션 종료 직전 페이지에서 다운로드 진행 중:
- `pose_detector.onnx` (w8a8)
- `pose_landmark_detector.onnx` (w8a8)
- ONNX Runtime, Snapdragon X2 Elite CRD (또는 아무 device, .onnx는 칩셋 무관)

**저장 위치**: `c:\Project\pose\models\`

### 첫 명령 — ONNX 파일 확인 + introspection (Claude 자동)

```bash
# 1. 다운로드 확인
ls -la c:/Project/pose/models/

# 2. (압축이면) 풀기
# unzip ...

# 3. 호스트 introspection
wsl bash -c 'cd /mnt/c/Project/unoq-companion-robot/pose && \
  docker run --rm -e HOME=/home/dev -v "$PWD:/work" --entrypoint bash \
  unoq-pose:22.04 -c "
    python3 -c \"
import onnx
for f in [\\\"models/pose_detector.onnx\\\", \\\"models/pose_landmark_detector.onnx\\\"]:
    m = onnx.load(f)
    print(f\\\"=== {f} ===\\\")
    print(\\\"inputs:\\\", [(i.name, [d.dim_value for d in i.type.tensor_type.shape.dim]) for i in m.graph.input])
    print(\\\"outputs:\\\", [(o.name, [d.dim_value for d in o.type.tensor_type.shape.dim]) for o in m.graph.output])
\"
  "'
```

### Phase 다음 (다운로드 후 30분 사이클)

| # | 작업 | 누가 |
|---|---|---|
| 1 | 다운로드 파일 위치 / 형식 확인 | 사용자 (1줄 안내) |
| 2 | 호스트 introspection (onnx, input/output shape) | Claude 자동 |
| 3 | 호스트 onnxruntime로 dummy invoke + latency | Claude 자동 |
| 4 | 디바이스 onnxruntime 설치 (`adb shell pip install onnxruntime`) | Claude (ADB) |
| 5 | ADB push (2 onnx) | Claude |
| 6 | 디바이스 onnxruntime invoke + latency 측정 | Claude |
| 7 | 결과 비교 (호스트 vs 디바이스, feature 일치) | Claude |
| 8 | history 기록 | Claude |

전제: ADB 동작 (`adb devices`에 `1204329696` 표시) 또는 SSH fallback (`ssh arduino@192.168.0.45`).

## 7. 결정 보류 사항 (다음 세션 또는 향후)

| 항목 | 결정 시점 |
|---|---|
| qai-hub 토큰 재발급 | 다음 세션 시작 시 (또는 ONNX 직접 다운로드면 불필요) |
| MediaPipe Pose 단독 검증 후 vision YOLO + Pose 동시 운영 thermal soak | Phase 3 (다음 세션 또는 그 이후) |
| Vision + ASR + Pose 3개 fusion 코드 | Phase 4 (멘토 보고 후) |
| monorepo 통합 (vision + asr + pose) | 개선방안 docs 참조, Public 전환 시점 |
| 디바이스 측 `/opt/unoq-yolo/` → `/opt/unoq-companion/` rename | monorepo 통합 시점 |
| Vision YOLO 라이선스 AGPL → 상업 호환 모델 교체 | Public 전환 / 상업화 시점 |
| ADB 셋업 docs 정리 (운영 표준 문서) | 본 작품 안정화 후 |

## 8. 본 세션 신규 자산 위치

### docs / 코드
- 본 세션은 docs 신규 작성 X (이전 세션의 docs가 ASR 완료 + monorepo 개선방안 등 충분)
- 새 폴더 `pose/` 전체 (Docker 5개 파일 + 빈 폴더 7개)

### history / issues (양 라인 기록)
- `vision/docs/history/2026-06-25_02_adb_connection_established.md`
- `vision/docs/history/2026-06-25_03_usb_topology_decision.md`
- `vision/docs/issues/2026-06-25_01_adb_lost_when_through_hub.md`
- `vision/docs/issues/2026-06-25_02_adb_billboard_device_only_via_hub.md`
- `asr/docs/history/2026-06-25_01_workflow_established.md`
- `vision/docs/history/2026-06-25_01_workflow_established.md`

### 메모리 갱신
- `feedback_issues_history_workflow.md` 신규 (양 라인 적용 완료)
- `MEMORY.md` 인덱스 갱신

## 9. 환경 호환성 매트릭스 (3 라인 비교)

| 환경 | Python | numpy | ai-edge-litert | TF | mediapipe | torch | qai-hub-models |
|---|---|---|---|---|---|---|---|
| 호스트 unoq-yolo-dev | 3.10.12 | 1.26.4 | (없음, tf.lite 사용) | 2.19.1 | X | X | X |
| 호스트 unoq-asr-dev | 3.10.12 | 2.1.3 | 2.1.5 | 2.19.1 | X | X | X |
| **호스트 unoq-pose** | **3.10.12** | **2.1.3** | **2.1.1** ⚠️ | **2.19.1** | **0.10.35** | **2.4.1** | **0.48.0** |
| 디바이스 venv-unoq | 3.13.5 | 2.5.0 | 2.1.5 | X | X | X | X |

⚠️ pose 호스트의 ai-edge-litert 2.1.1 vs 디바이스 2.1.5 — minor 차이 (TFLite ABI 동일 보장). 본 작품 진행에 영향 없음.

## 10. 멘토 보고용 한 줄 (3 라인 종합)

> **Arduino UNO Q (QRB2210 Cortex-A53 ×4 CPU) 위 — vision YOLOv8n int8 (HTTP serve 운영, CPU 286%/RSS 102 MB) + ASR Whisper Tiny.en (이벤트 기반, e2e 3.18s/RSS 357 MB) 1차 PoC 합격 + 자유발화 영어 6단어 중 5정확. MediaPipe Pose w8a8 ONNX 환경 (4.31 GB Docker) 구축 완료, 검증 진입 직전. 양 라인 issues/history 실시간 기록 워크플로우 채택. ADB 셋업으로 자동화 워크플로우 확보 (PC 직접 연결 시). 동시 운영 자원 청사진 정량 (vision continuous + ASR/Pose burst).**

## 11. 다음 세션 시작 시 첫 답변에 포함시킬 것

다음 세션 시작 시 사용자에게:

1. **본 SESSION_SUMMARY 읽음을 알림**
2. **ONNX 파일 다운로드 상태 확인** (`ls c:/Project/pose/models/`)
3. **ADB 동작 재확인** (`adb devices` — UNO Q PC 직접 연결 상태)
4. **즉시 자동 진행** — 호스트 introspection부터 시작 (위 §6 첫 명령)

이전 세션 모든 컨텍스트는 본 파일 + 양 라인의 docs/00 청사진 + history/issues로 완전 복원 가능.

## 한 줄 마무리

> **본 세션 = 자원 측정 + ADB + MediaPipe Pose 환경 셋업. 다음 세션 시작 = ONNX 파일 검증 → 호스트 추론 → ADB push → 디바이스 추론 → 결과 회수.**
