# 세션 요약 — 2026-06-24 (ko/ 멘토 정리본 + 카메라 운영 측정)

> 2026-06-23 첫 세션(환경 셋업 → 9.23 FPS 합격)의 후속 세션. 카메라 실시간 측정 추가 + docs 양식 통일 + 멘토 보고용 한국어 정리본(`docs/ko/`) 10개 신규 작성 + 문서 구조 재편(청사진 신규 + 시퀀스 재정렬).

> 세션 종료 시점 결론: ko/를 단일 트랙으로 채택. `docs/ko/*` → `docs/*`로 통합, 옛 본인 트랙 `docs/00~09`는 git history에만 보존(2개 커밋 분리: "병행 상태 보존" + "ko/ 채택"). 본문 내 `docs/` 표현은 통합 후 위치(루트)를 의미. 본문 historical 기록은 보존됨.

---

## 0. 한 줄 결론

**카메라 실시간 YOLO 운영 측정 완료(8.29 FPS, thermal 70.8°C 임계 1도 초과 발견) + 멘토 보고용 `docs/` 10개 한국어 정리본 신규 트랙 완성 + docs/ 본인 트랙도 양식/번호 정리. 다음 세션은 soak test, 얼굴 검출(MediaPipe Face), 또는 MCU 연동 중 선택.**

---

## 1. 시작 시점 vs 종료 시점

| 영역 | 세션 시작 (2026-06-24 초) | 세션 종료 |
|---|---|---|
| docs/ 폴더 구조 | `danny/` 11개 + `ko/`(멘토 번역본) | `docs/` 9개(번호 재정렬 후) + `docs/mentor/` 9개 + `docs/` 10개(신규 멘토 보고 트랙) |
| 카메라 측정 | 단일 이미지 e2e 9.23 FPS만 | 카메라 100f 8.52 FPS + 운영 2184f 8.29 FPS + temp 70.8°C 발견 |
| `src/` | 4개 (validate, postprocess, infer_image, benchmark_e2e) | 5개 (+ `infer_camera.py`, `--serve 8080` HTTP MJPEG 포함) |
| 문서 양식 | ✅ 이모지 + `**굵게**` 다수 | 양식 통일 (이모지 텍스트 대체, 굵게 표 라벨에만, 멘토 양식 따라감) |
| `.gitignore` | `docs/mentor/` 누락 | 추가됨 (대외비 보호) |
| `.markdownlint.jsonc` | 없음 | 추가됨 (한국어/표 환경 룰 조정) |
| 멘토 인용 처리 | 사용자가 직접 처리 영역 | 보존 결정 (자급자족 변환 후 복원) |

---

## 2. 시간순 작업 흐름

### Phase A — docs/ 구조 정리 (이전 세션 마무리)

1. 폴더 리네임: `danny/` → `docs/`, `ko/` → `docs/mentor/`
2. 02 (export_environment_fix) → 00 (environment_setup) 흡수 통합
3. 04 (env_setup) → 02 (project_conventions)에 env.sh 사용법 흡수 통합
4. 11개 → 9개 (00~08) 재번호
5. inter-doc 인용 정리 → 각 문서 self-contained
6. `.gitignore`에 `docs/mentor/` 추가 + README 갱신 + 메모리 갱신
7. `markdownlint-cli2 --fix` 적용 + `.markdownlint.jsonc` 설정

### Phase B — 카메라 작업

1. `src/infer_camera.py` 작성 (카메라 + YOLO 실시간 + rolling FPS + 단계별 latency)
2. 멘토 06 권고 점검 후 보강: dropped_frames 카운트, 카메라 reconnect, RSS/온도 모니터링, JSON 출력 (`--json`), 멘토 06 형식 준수
3. `--serve PORT` HTTP MJPEG 라이브 스트리밍 추가 (DEBUG ONLY, 로컬 LAN)
4. 100프레임 측정 → 8.52 FPS, 59.2°C, 4기준 합격 (단시간)
5. 2184프레임 / 285초 운영 측정 (`--serve 8080` 동시) → 8.29 FPS, **temp 70.8°C** (합격선 1도 초과 — 첫 thermal margin 경고)
6. docs/09_realtime_camera.md 작성 + 운영 측정 Section 3-3 추가
7. 카메라 트러블슈팅 함정 5종 기록 (uvcvideo reload, pkill self-kill, nested SSH, /tmp 누적, video 인덱스)

### Phase C — 양식 통일 작업

1. 가이드라인 도출: 이모지 → 텍스트(통과/수집/임계 도달), `**` 위치 = 멘토 mentor/00 패턴(표 첫 컬럼 라벨만)
2. docs/08, 09 양식 정리 시범 → 사용자가 "멘토 인용 보존" + "이모지 대체" 명시
3. 멘토 인용 자급자족 변환 작업 → 사용자 재지시로 복원
4. `.markdownlint.jsonc`로 본 프로젝트 환경에 맞지 않는 룰 5종 비활성화

### Phase D — `docs/` 신규 트랙 (멘토 보고 전용)

1. `docs/` 빈 폴더 발견 → 사용자 의사 확인 (멘토용 한국어 정리본 병행 결정)
2. 멘토 양식 가이드라인 확정 (영문 키워드 제목, `>` 부제 X, 메타 표 X, 굵게 거의 X, 본문 0굵게)
3. 9개 docs/* → 멘토 양식으로 ko/0~8 작성 (구 docs/03+05 → ko/03 통합)
4. 사용자 피드백 반영: 멘토 인용 보존, 이모지는 대체, 04의 SSH 1-1/1-2 트러블슈팅 제거 + 표 끝 파이프 누락 lint 수정
5. 시퀀스 재정렬: device_setup이 측정 앞으로, runbook이 끝으로 → 00~08
6. 청사진 신규 작성 (00_project_blueprint.md) + 기존 9개 +1 밀기 → 최종 00~09 10개
7. inter-doc 인용 정확히 갱신 + 검증

### Phase E — 사이드 작업 (사용자 질문 답변)

- "스토리지 2.9 GB 가용" 의미 설명 (A/B 슬롯, modem firmware 등 단계별 손실 + 사전 설치 시스템 차지)
- "환경 셋업이 4 GB UNO Q 변종..." 한 줄 의미 설명
- "비번 함정/호스트명 파악 빼도 되나" 답변 후 04 Section 1 단순화
- "다른 사람이 받고 실행 가능?" 평가 → 70% (청사진/사전 조건 누락 지적) → 사용자 청사진 신규 작성 결정

---

## 3. 최종 `docs/` 구조 (10개, 멘토 보고용)

| 번호 | 파일명 | 역할 | 비고 |
|---|---|---|---|
| 00 | `00_project_blueprint.md` | **청사진**: UNO Q 스펙 + 모델 선택 + 데이터셋 + YOLOv8 아키텍처 + 합격 4기준 + 진행 흐름 + 사전 조건 | 신규 작성, 외부 진입자가 한 페이지로 전체 파악 |
| 01 | `01_host_environment_setup.md` | Docker 호스트 환경 빌드 | 구 docs/00 양식 정리 |
| 02 | `02_model_selection_log.md` | 모델 선택 자세한 의사결정 로그 | 구 docs/01 |
| 03 | `03_project_conventions.md` | 코딩 / 디렉토리 / 보안 규약 | 구 docs/02 |
| 04 | `04_device_setup.md` | UNO Q SSH + 사양 + 런타임 선택 + `setup_device.sh` | 구 docs/04, Section 1 단순화 (트러블슈팅 제거) |
| 05 | `05_initial_inference_measurement.md` | 호스트 baseline + 디바이스 첫 측정 (통합) | **구 docs/03 + docs/05 통합** |
| 06 | `06_postprocess_and_e2e.md` | 후처리 모듈 + 함정(정규화 좌표, cv2 cold start) + e2e 9.3 FPS 합격 | 구 docs/07 |
| 07 | `07_official_benchmark.md` | 공식 100회 벤치마크 9.23 FPS | 구 docs/08 |
| 08 | `08_realtime_camera.md` | 카메라 100f 8.52 FPS + 운영 2184f 8.29 FPS + thermal 70.8°C | 구 docs/09 |
| 09 | `09_usage_runbook.md` | 자주 쓰는 명령 모음 (참조용 끝) | 구 docs/06 |

**적용된 멘토 양식 규칙**:

- 영문 키워드 제목 (예: "Project Blueprint — UNO Q Real-time YOLOv8 Detection")
- `>` blockquote 부제 X, 일반 한 줄 텍스트
- 결정 요약 / 변경 이력 / 작성 정보 표 모두 제거
- 본문 산문 굵게 0개 (멘토 mentor/01~08 패턴)
- 표 첫 컬럼 라벨만 굵게 (mentor/00 패턴), 그것도 핵심 결정 표에만
- 이모지(✅ ❌ ⚠️ 🎯 🔴 🟡 🟢) 모두 텍스트로 대체 (통과/수집/임계 도달 등)
- 코드 블록 언어 명시 (text, bash, python, dockerfile, diff)
- 멘토 인용("멘토 docs 06 형식" 등) 보존
- sub-numbering `### NN-1` 유지

---

## 4. 현재 `docs/` (본인 개발용) 구조 (9개)

| 번호 | 파일 |
|---|---|
| 00 | `00_environment_setup.md` (Docker + lock 도입 경위) |
| 01 | `01_model_selection_log.md` |
| 02 | `02_project_conventions.md` |
| 03 | `03_host_validation_results.md` |
| 04 | `04_device_setup.md` |
| 05 | `05_device_first_inference.md` |
| 06 | `06_usage_runbook.md` |
| 07 | `07_postprocess_and_e2e.md` |
| 08 | `08_official_benchmark.md` |
| 09 | `09_realtime_camera.md` |

docs/는 historical / 개발용으로 그대로 보존. ko/와 병행 운영. 향후 갱신은 ko/와 docs/ 각자 자유.

---

## 5. 측정 결과 종합 (멘토 06 형식)

### 5-1. 핵심 수치 (디바이스)

| 측정 시나리오 | 측정 도구 | frames | FPS mean | p50 / p95 (ms) | max_rss_mb | max_temp_c | 합격 |
|---|---|---|---|---|---|---|---|
| 디바이스 첫 inference (warm) | `validate_model.py` | 50 | 9.88 | 94 / 129 | n/a | n/a | 통과 |
| 단일 이미지 e2e 공식 벤치 | `benchmark_e2e.py` | 100 | **9.23** | 105 / 132 | 100.8 | 60.5°C | 통과 |
| 카메라 100프레임 | `infer_camera.py` | 100 | 8.52 | 109 / 146 | 107.8 | 59.2°C | 통과 |
| **카메라 운영 285초** (`--serve`) | `infer_camera.py --serve 8080` | 2184 | **8.29** | 116 / 156 | 116.9 | **70.8°C** | **임계 1도 초과** |

### 5-2. JSON 자료 위치

- `benchmarks/host_e2e_20260623.json` — 호스트 100회
- `benchmarks/device_e2e_20260623.json` — 디바이스 100회
- `~/benchmarks/cam_serve_20260623_<HHMMSS>.json` — 디바이스 카메라 운영 (회수 안 함)

### 5-3. 합격 4기준 (멘토 06)

| 기준 | 임계 | 단일 e2e | 카메라 운영 |
|---|---|---|---|
| FPS mean | ≥ 8 | 9.23 OK | 8.29 OK (여유 0.29) |
| p95 FPS | ≥ 6 | 7.53 OK | 6.42 OK |
| max RSS | ≪ 2.4 GB | 100.8 MB | 116.9 MB |
| max temp | ≤ 70°C | 60.5°C | **70.8°C (1도 초과)** |

---

## 6. 핵심 발견 / 함정 (이번 세션 추가)

| # | 발견 | 영향 | 대응 |
|---|---|---|---|
| 9 | **카메라 운영 285초에 thermal 70.8°C 도달** | 합격선 1도 초과, 장시간 운영 시 throttle 우려 | soak test (8h+) 우선순위 / 방열판 / frame cap |
| 10 | **HTTP `--serve` 추가 부담** | RSS +9 MB, FPS -2.7% | 분리 측정으로 정량화 필요 |
| 11 | **inference 시간 +6.5%** (100f → 2184f 비교) | thermal throttle 시작 신호 가능 | 첫 100 vs 후반 분리 측정 |
| 12 | **uvcvideo 미바인딩** (`/dev/video*` 없음, `lsusb`엔 카메라 보임) | 카메라 인식 실패 | `sudo modprobe -r uvcvideo; sudo modprobe uvcvideo` |
| 13 | **`pkill -f infer_camera.py` self-kill** | 자기 ssh 명령줄 매칭 → 즉시 중단 | pkill 옵션 빼고 실행 |
| 14 | **Nested SSH** (디바이스 셸 안에서 또 ssh) | 명령이 두 번째 ssh 인자가 아닌 다음 줄로 처리됨 | `exit` 두 번 |

기존 함정 8개(첫 세션 발견) + 이번 6개 = 총 14개. 메모리 `project_unoq_known_traps.md`에 추가 갱신 권장.

---

## 7. 만들어진 / 변경된 자산

### 7-1. 코드

- `src/infer_camera.py` — 카메라 실시간 추론 + 멘토 06 권고 준수 + `--serve 8080` HTTP MJPEG (DEBUG ONLY)

### 7-2. 문서 (`docs/` 신규 10개)

- 00 `project_blueprint` — 청사진 (한 페이지 overview)
- 01 ~ 09: 위 Section 3 표 참조

### 7-3. 설정

- `.gitignore` — `docs/mentor/` 추가
- `.markdownlint.jsonc` — 한국어 / 표 환경 룰 비활성화 5종

### 7-4. 환경 정리

- `scripts/env.sh` — 멘토 인용 제거, ko/ 옛 경로 갱신
- `src/postprocess.py` docstring — `danny/03` → `docs/02`
- `requirements.txt` 코멘트 — 멘토 인용 자급자족 형태로
- README — `infer_camera.py`, `.markdownlint.jsonc`, `docs/09` 반영
- `SESSION_SUMMARY_2026-06-23.md` 헤더 — 후속 변경 안내 추가

---

## 8. 다음 단계 (우선순위)

### 8-1. 시급

- [ ] **Soak test 8h+** — thermal plateau / throttle 거동 확인 (운영 측정의 70.8°C 후속)
- [ ] **`--serve` 부담 분리 측정** — `--serve` 없이 같은 길이 운영 측정으로 차이 정량화 (30분 작업)
- [ ] **cam_serve_*.json 호스트 회수** — 디바이스 `~/benchmarks/`에 있는 JSON

### 8-2. 본 작품 핵심

- [ ] **얼굴 검출 모델 결정** (MediaPipe Face 권장 — 표정 추론에 직결, Apache-2.0 라이선스)
- [ ] **표정 추론 L1/L2** (FaceMesh 468 landmark + 규칙 기반)
- [ ] **MCU 연동** (STM32U585 + LED + 모터 PWM, JSON-like 메시지 + heartbeat)
- [ ] App Lab vs systemd 결정

### 8-3. 운영 안정성

- [ ] Watchdog policy (heartbeat 1s, no-heartbeat 5s restart, no-camera 10s reinit)
- [ ] Golden image set (20~100장 + 기대 검출 IoU)
- [ ] Camera reconnect 실측 검증 (USB unplug / replug 10회)

### 8-4. Public 전환 (작품 완성 후)

- [ ] LICENSE 추가 (Apache-2.0 권장)
- [ ] SSH key 인증 전환 + 기본 비번 변경
- [ ] 멘토 인용 redact (Public 전환 시점)
- [ ] README 데모 GIF / 영상 임베드

---

## 9. 다음 세션 진입 가이드

### 9-1. 컨텍스트 복원 순서

1. **본 문서**(`SESSION_SUMMARY_2026-06-24.md`) — 이번 세션 종합
2. **`SESSION_SUMMARY_2026-06-23.md`** — 첫 세션(환경 ~ 9.23 FPS 합격)
3. **`docs/00_project_blueprint.md`** — 작품 청사진 한 페이지
4. **`docs/09_usage_runbook.md`** — 자주 쓰는 명령 모음
5. 메모리 시스템 (`C:\Users\A\.claude\projects\c--Project\memory\`) — 자동 로드됨

### 9-2. 자주 쓰는 명령 (호스트 WSL에서)

```bash
# 컨테이너 진입
cd /mnt/c/Project/unoq-companion-robot && bash run.sh

# 디바이스 카메라 + 라이브 디버그 + JSON + JPEG 자동 저장
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
    mkdir -p ~/benchmarks && \
    python3 ~/infer_camera.py /opt/unoq-yolo/models/yolov8n_int8.tflite \
        --camera 0 --serve 8080 \
        --json ~/benchmarks/cam_serve_$(date +%Y%m%d_%H%M%S).json \
        --save-dir /tmp/unoq-yolo/cam-debug --save-every 60 \
        --print-every 50'

# 브라우저: http://192.168.0.45:8080/
# 종료: Ctrl+C

# 자료 회수
scp 'arduino@192.168.0.45:~/benchmarks/cam_serve_*.json' benchmarks/
scp 'arduino@192.168.0.45:/tmp/unoq-yolo/cam-debug/*.jpg' test_camera_output/

# 카메라 진단 (안 보일 때)
ssh arduino@192.168.0.45 'ls -la /dev/video* 2>/dev/null; lsusb | grep -iE "cam|video|uvc"'
ssh arduino@192.168.0.45 'sudo modprobe -r uvcvideo; sleep 1; sudo modprobe uvcvideo; sleep 2; ls /dev/video*'
```

### 9-3. 메모리 갱신 권장 사항

다음 세션 진입 시 이 사항들도 메모리에 반영 권장:

- 카메라 운영 측정 thermal 70.8°C 발견 (`project_unoq_known_traps.md`에 추가)
- `docs/` 10개 트랙 존재 (멘토 보고 전용) + 청사진 00 신규
- `src/infer_camera.py` + `--serve 8080` 옵션
- soak test가 다음 최우선

---

## 10. 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-24 |
| 위치 | 프로젝트 루트 (`C:\Project\unoq-companion-robot\SESSION_SUMMARY_2026-06-24.md`) |
| 용도 | 세션 종료 시 컨텍스트 핸드오프 + 다른 창에서 이어 작업용 |
| 관련 자산 | `docs/` 10개, `src/infer_camera.py`, `benchmarks/*.json`, README |
| 다음 갱신 | 다음 세션 종료 시 새 `SESSION_SUMMARY_<날짜>.md` 작성 권장 |
