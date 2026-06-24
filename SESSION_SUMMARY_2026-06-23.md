# 세션 요약 — 2026-06-23

> Arduino UNO Q (QRB2210) 교감로봇 프로젝트, 환경 셋업부터 공식 벤치마크 9.23 FPS 합격 확정까지 한 세션의 모든 작업 + 의사결정 + 측정 기록.

> ⚠ **이후 구조 변경 (2026-06-23 후속 작업으로 갱신됨)**:
> - 폴더: `danny/` → `docs/`, `ko/` → `docs/mentor/`
> - 문서 통합: 11개 → 9개 (구 02 `export_environment_fix`는 00에 흡수, 구 04 `uno_q_env_setup`은 03 → 현재 02에 흡수)
> - 번호 재정렬: 00~08 (결번 없음). 매핑: 구 05→03 / 06→04 / 07→05 / 08→06 / 09→07 / 10→08
> - 신규 단계: `docs/09_realtime_camera.md` + `src/infer_camera.py` (`--serve 8080` HTTP MJPEG 라이브 디버그). 운영 측정에서 thermal **70.8°C 임계 1도 초과** 발견
> - `.markdownlint.jsonc` 추가 (한국어/표 환경 룰 조정)
> - 본 문서 본문은 첫 세션 시점 기록(11개 docs 기준) — 일부 경로/번호는 historical로 보존

---

## 0. 한 줄 결론

**Docker 호스트 환경 + UNO Q 디바이스 환경 + YOLO 모델 export + 후처리 파이프라인 + 공식 벤치마크까지 완료. UNO Q에서 end-to-end 9.23 FPS / 60.5°C / 100 MB 실측 — 본 작품 합격선(8 FPS) 통과.**

---

## 1. 시작 시점 vs 종료 시점

| 영역 | 세션 시작 | 세션 종료 |
|---|---|---|
| 호스트 개발 환경 | 없음 | Docker (Ubuntu 22.04 + Python 3.10 + TF 2.19) + requirements.lock byte-exact |
| 모델 자산 | 없음 | yolov8n_int8.tflite (3.19 MB) export 완료 |
| 디바이스 셋업 | 없음 | venv + ai-edge-litert + numpy + opencv 설치, `/opt/unoq-yolo/` 구조 |
| 추론 코드 | 없음 | validate_model.py + infer_image.py + postprocess.py + benchmark_e2e.py |
| 측정 데이터 | 없음 | 호스트/디바이스 100회 측정 JSON (멘토 06 형식) |
| 문서 | 없음 | danny/ 11개 + README + SESSION_SUMMARY |
| Git/GitHub | 없음 | Private 레포 `donghee-ai/unoq-companion-robot`, 4 commits, ~3,500 라인 |
| 합격 판정 | 미정 | ✅ 4기준 모두 통과 (FPS, 분포, 메모리, 온도) |

---

## 2. 작업 환경 — 3계층

```
호스트 WSL (Windows 11 + Ubuntu 24.04)
   └─ git, ssh, scp, gh CLI
        │ bash run.sh
        ▼
Docker 컨테이너 (Ubuntu 22.04 + Python 3.10)
   └─ TF 2.19 + Ultralytics + opencv + ai_edge_litert
        │ scp model + scripts
        ▼
UNO Q 디바이스 (QRB2210, Cortex-A53 ×4 @ 2.0 GHz, 4 GB RAM)
   └─ venv + ai-edge-litert 2.1.5 + numpy 2.5.0 + opencv 4.13
        └─ /opt/unoq-yolo/{models,labels,media,configs,logs}
```

### 호스트 → 디바이스 연결 정보
- IP: `192.168.0.45`
- SSH 사용자: `arduino` (호스트명 `unoq-korea01`과 별개)
- venv: `/home/arduino/venv-unoq`
- 인증: 비번 (Public 전환 시 SSH key 검토)

---

## 3. 진행 흐름 (시간순)

### Phase 1 — Docker 호스트 환경 셋업
1. WSL2 Ubuntu 24.04 확인, Docker Desktop 통합 확인
2. 프로젝트 폴더 `C:\Project\unoq-companion-robot\` 생성
3. 4개 파일 작성: `Dockerfile`, `requirements.txt`, `.dockerignore`, `run.sh`
4. 첫 빌드 13분, 컨테이너 진입 (`dev@unoq-yolo-dev:/work$`)
5. smoke test (TF, Ultralytics, OpenCV, NumPy import 확인)

### Phase 2 — YOLO 모델 Export (트러블슈팅 포함)
1. 1차 시도: AutoUpdate가 환경 깨뜨림 (TF 2.13 → 2.19 강제, KerasTensor 에러)
2. 2차 시도: numpy ABI 비호환 (torch 1.x 빌드 vs numpy 2.x)
3. **해결**: requirements.txt를 TF 2.19 스택으로 갱신 + 컨테이너 재빌드
4. Export 성공 → `models/yolov8n_saved_model/yolov8n_int8.tflite` (3.19 MB)
5. **추가**: `pip freeze > requirements.lock` 으로 94 패키지 byte-exact 핀
6. `Dockerfile` 갱신: lock 우선 설치로 변경

### Phase 3 — 호스트 검증 (STEP 3)
1. `src/validate_model.py` 작성 (TFLite Interpreter + 50회 벤치)
2. 호스트 측정: **12.5 ms / 80 FPS** (baseline)
3. Input/output shape 확인: `[1,320,320,3]` → `[1,84,2100]`
4. Int8 모델이지만 입출력은 float32 (Ultralytics 표준 동작)

### Phase 4 — Git + GitHub
1. `.gitignore` 작성 (model files, datasets, secrets, IDE)
2. `git init` + 첫 커밋 + GitHub Private 레포 생성
3. 초기 noreply 이메일로 commit author 설정
4. mentor docs 인용 refs 모두 redact (총 5개 danny 파일)
5. `gh auth login`으로 push 인증 → 푸시 성공

### Phase 5 — UNO Q 디바이스 셋업 (STEP 4)
1. SSH 사용자명 트러블슈팅 (hostname ≠ username, 한/영 IME 함정)
2. 디바이스 진단: QRB2210, 4 GB RAM, Python 3.13.5, TFLite 미설치, gst-ai 미설치
3. `scripts/setup_device.sh` (idempotent) 작성
4. pip + venv + ai-edge-litert + numpy 설치
5. `/opt/unoq-yolo/{...}` 디렉토리 생성

### Phase 6 — 디바이스 첫 추론 (STEP 5)
1. 모델 + validate_model.py scp 전송
2. 디바이스 첫 측정: **101.27 ms / 9.88 FPS** (순수 inference)
3. 멘토 가이드 합격선 잠정 통과

### Phase 7 — 후처리 모듈 (STEP 7) + 실제 이미지 추론 (STEP 8)
1. `src/postprocess.py` 작성: decode + NMS + scale + draw + COCO 80
2. `src/infer_image.py` 작성: 전체 파이프라인 + 단계별 latency
3. 호스트 Ultralytics 비교 테스트 → "4 bowls, 1 broccoli" 검출 확인
4. 디바이스 첫 e2e 실행 → **bbox 좌표 깨짐** (`[0, 0, 1, 0]`)
5. **버그 1 발견**: Ultralytics int8 TFLite는 **정규화 좌표 [0,1]** 출력 (PyTorch/ONNX는 픽셀 좌표)
6. 수정: `decode_yolov8`에 input_size 파라미터 추가 → 정규화 픽셀 변환
7. 재실행 → 정상 좌표 확인 (bowl 박스가 음식 위치)
8. 단계 분리 측정 → **draw가 60ms 차지** (의심)
9. **함정 2 발견**: cv2 drawing 첫 호출 cold start. 5회 연속 측정으로 검증 (steady ~3.7 ms)
10. 결론: 실시간 루프 e2e ≈ 108 ms = 9.3 FPS

### Phase 8 — 공식 벤치마크 (멘토 06 형식)
1. `src/benchmark_e2e.py` 작성: 100회 반복 + 단계별 통계 + RSS/온도 모니터링
2. 호스트 측정: **73 FPS / 13.7 ms / 123 MB** (ai_edge_litert 사용)
3. 디바이스 측정: **9.23 FPS / 108 ms / 100 MB / 60.5°C** ← 본 작품 진짜 값
4. 멘토 형식 JSON 저장 (호스트 + 디바이스)
5. 합격 4기준 모두 통과 확정

### Phase 9 — 문서화
1. 매 단계마다 `danny/NN_xxx.md` 작성 (총 11개)
2. README 진행 상황 + 성능 표 갱신
3. 본 SESSION_SUMMARY 작성

---

## 4. 만들어진 자산

### 4-1. 코드 (`src/`, `scripts/`)
| 파일 | 라인 | 역할 |
|---|---|---|
| `src/validate_model.py` | ~205 | TFLite 모델 검증 + 50회 latency |
| `src/postprocess.py` | ~190 | YOLOv8 decode + NMS + scale + draw + COCO 라벨 |
| `src/infer_image.py` | ~210 | 전체 파이프라인 + 단계별 latency 측정 |
| `src/benchmark_e2e.py` | ~260 | 멘토 06 형식 벤치마크 (100회 + RSS + 온도) |
| `scripts/env.sh` | ~30 | UNO Q 접속 환경 변수 |
| `scripts/setup_device.sh` | ~80 | UNO Q 디바이스 셋업 idempotent 자동화 |

### 4-2. 환경 정의
| 파일 | 역할 |
|---|---|
| `Dockerfile` | Ubuntu 22.04 + Python + apt deps + non-root user + requirements.lock 설치 |
| `requirements.txt` | 사람 친화적 의도 (15개 패키지) |
| `requirements.lock` | byte-exact 재현 (94 패키지, `pip freeze` 결과) |
| `.dockerignore` | 빌드 컨텍스트 정리 |
| `.gitignore` | 모델/데이터셋/캐시/IDE/secrets/runs/test 제외 |
| `run.sh` | 원샷 빌드+실행 (idempotent, --rebuild 옵션) |

### 4-3. 측정 데이터 (`benchmarks/`)
| 파일 | 환경 | 핵심 수치 |
|---|---|---|
| `host_e2e_20260623.json` | 호스트 Docker | FPS 73.09, p50/p95 13.5/14.8, RSS 123 MB |
| `device_e2e_20260623.json` | UNO Q | FPS 9.23, p50/p95 105/132, RSS 100.8 MB, 온도 60.5°C |

### 4-4. 문서 (`danny/` 11개)
| 번호 | 제목 | 핵심 내용 |
|---|---|---|
| 00 | 환경 셋업 | Docker 호스트 환경 |
| 01 | 모델 선택 로그 | YOLO vs MediaPipe 의사결정 트리 |
| 02 | Export 환경 충돌 해결 | requirements.lock 도입 경위 |
| 03 | 프로젝트 규약 | 코딩/명령어/디렉토리/보안/문서 8개 영역 |
| 04 | UNO Q env 변수 사용법 | scripts/env.sh 운영 |
| 05 | 호스트 검증 결과 | 12.5 ms / 80 FPS baseline |
| 06 | 디바이스 셋업 | SSH, 사양, 런타임 선택 (ai-edge-litert) |
| 07 | 디바이스 첫 추론 | 101 ms / 9.88 FPS 순수 inference |
| 08 | 실행 방법 Runbook | 호스트/디바이스 공용 명령 가이드 |
| 09 | 후처리 + e2e | postprocess 작성 + 정규화 버그 + cv2 cold start |
| 10 | 공식 벤치마크 | 호스트 vs 디바이스 100회 + 4기준 합격 |

### 4-5. README + 본 문서
- `README.md` — 프로젝트 첫인상, 사양, 빠른 시작, 진행 상황, 성능 표
- `SESSION_SUMMARY_2026-06-23.md` — 본 문서 (전체 세션 요약)

---

## 5. 측정 데이터 — 멘토 보고용 한 화면

### 호스트 baseline (참고)
| 단계 | mean | p50 | p95 |
|---|---|---|---|
| preprocess | 1.23 ms | 1.20 | 1.43 |
| inference | 10.25 ms | 10.19 | 11.32 |
| postprocess | 0.94 ms | 0.91 | 1.12 |
| draw | 0.91 ms | 0.89 | 1.04 |
| **total** | **13.68 ms** | **13.54** | **14.84** |
| FPS | 73.09 | | |
| RSS | 123.2 MB | | |

### UNO Q (본 작품 운영 환경)
| 단계 | mean | p50 | p95 |
|---|---|---|---|
| preprocess | 5.42 ms | 6.04 | 6.59 |
| inference | 93.28 ms | 90.71 | 120.21 |
| postprocess | 5.08 ms | 5.08 | 5.60 |
| draw | 3.90 ms | 3.88 | 4.17 |
| **total** | **108.36 ms** | **105.02** | **132.74** |
| **FPS** | **9.23** ✅ | | |
| RSS | 100.8 MB | | |
| max temp | **60.5°C** | | |

### 합격 4기준
| 기준 | 임계 | 측정 | 결과 |
|---|---|---|---|
| FPS | ≥ 8 | 9.23 | ✅ |
| p95 FPS | ≥ 6 | 7.53 | ✅ |
| RSS | ≪ 2.4 GB | 100.8 MB (4%) | ✅ |
| Temp | ≤ 70°C | 60.5°C | ✅ |

→ **YOLOv8n int8 / 320×320 / CPU 4 thread / ai_edge_litert + XNNPACK 채택 확정.**

---

## 6. 핵심 발견 + 함정

| # | 발견 | 영향 | 해결 |
|---|---|---|---|
| 1 | Ultralytics AutoUpdate가 핀된 환경 침범 | TF/numpy 강제 업그레이드 → KerasTensor 에러, numpy ABI 비호환 | requirements.lock으로 모든 transitive deps 사전 핀 |
| 2 | torch 2.1.x는 numpy <2 ABI에 묶임 | numpy 2.x 깔리면 torch 즉시 깨짐 | numpy 1.26.4 또는 torch 2.12+ 사용 |
| 3 | 호스트명 ≠ SSH 사용자명 | `unoq-korea01` 사용자 없음, `arduino`가 진짜 | SSH 사용자 명시적 확인 |
| 4 | 한/영 IME 한글 모드에서 SSH 비번 실패 | 영문 비번이 한글 자모로 전송 | 비번 입력 직전 IME 영어 확인 |
| 5 | UNO Q에 TFLite 런타임 사전 설치 X | 멘토 가정과 다름 | `ai-edge-litert` pip 설치 (Python 3.13 호환) |
| 6 | UNO Q에 cv2 사전 설치 X | infer_image.py 첫 실행 실패 | `pip install opencv-python-headless` |
| 7 | **Ultralytics int8 TFLite는 정규화 좌표 [0,1] 출력** | 박스 좌표가 [0,0,1,0]로 깨짐 | decode_yolov8에 input_size 곱하기 |
| 8 | **cv2 drawing 첫 호출 cold start (~60ms)** | 단일 이미지 e2e가 5.5 FPS로 보임 | warmup 후 steady ~4 ms — 실시간 루프엔 영향 거의 없음 |

---

## 7. 멘토 docs 채택 사항 (Confidentiality 정리)

### 7-1. 멘토 docs는 대외비
- 멘토 패키지(`unoq_yolo_markdown_package/`)는 본인에게 개인 전달, 외부 공개 X
- 본인 danny docs에는 **mentor docs 파일명/섹션 인용 금지** (redact 완료)
- 내부 JIRA/CR 번호 절대 노출 X

### 7-2. 멘토 docs에서 가져온 원칙 (출처 표기 없이 채택)
- 환경 변수 표준화 (UNO_Q_USER, UNO_Q_HOST, APP_ROOT)
- `/opt/unoq-yolo/{models,labels,media,configs,logs}` 디렉토리 구조
- `setenforce 0` 제품 이미지 제거
- q-offset/q-scale hard-code 금지 → `get_input_details()` 자동 추출
- GPU delegate optional flag (CPU 기본)
- 30 FPS hard requirement 잡지 않음 (8~15 FPS 목표)
- `requirements.lock` 사용
- 벤치마크 JSON 형식 (06 Section 3)
- "사실 / 인용 / 추측" 분리 작성

### 7-3. 멘토 docs와의 의도적 차이
- 디바이스에 venv 사용 (멘토는 시스템 Python 가정)
- ai-edge-litert 채택 (멘토 코드는 tflite_runtime 우선, 호환성 위해 3단 폴백 도입)
- 본 작품은 face-based 교감로봇 (멘토 docs는 일반 객체 검출)

---

## 8. 다음 단계 (우선순위 순)

### 8-1. 즉시 / 짧은 작업
- [ ] 카메라 점검: `ls /dev/video* && lsusb | grep -i cam`
- [ ] 카메라 없으면 USB UVC 웹캠 (Logitech C270, C920 등) 준비
- [ ] `src/infer_camera.py` 작성 (있으면 즉시 시작 가능)

### 8-2. 본 작품 핵심 (얼굴 + 표정)
- [ ] 얼굴 검출 모델 결정:
  - 옵션 A: YOLO 일반 → 'person' 클래스만 사용
  - 옵션 B: YOLO 얼굴 fine-tuning (WIDER FACE 학습)
  - 옵션 C: MediaPipe Face (Apache-2.0, face_detector + 468 landmark)
- [ ] 채택 모델로 디바이스 측정 + 합격선 재확인
- [ ] 표정 추론 L1/L2 (FaceMesh landmark + 규칙 기반)

### 8-3. 하드웨어 통합
- [ ] STM32U585 MCU sketch 작성 (LED, 모터 PWM)
- [ ] Python ↔ MCU 메시지 프로토콜 (JSON-like, heartbeat)
- [ ] App Lab 앱 구조로 통합 (또는 systemd 서비스)

### 8-4. 운영 안정성
- [ ] soak test (8시간 카메라 + 추론, 메모리 누수, 온도 추이)
- [ ] watchdog 정책 (heartbeat 5s timeout 등)
- [ ] golden image set (20~100장 fixed test images)

### 8-5. Public 전환 준비
- [ ] git 이메일을 noreply로 변경 (현재 노출 안 되지만 명시 권장)
- [ ] LICENSE 추가 (Apache-2.0 권장)
- [ ] README 데모 GIF 임베드 (annotated 영상)
- [ ] Public 전환 + 사내 잡지/Qualcomm 보고

---

## 9. 미해결 / TODO

### 9-1. 측정/검증
- [ ] 카메라 입력 시 e2e FPS (현재는 단일 이미지 100회)
- [ ] dropped_frames 실측 (카메라 입력 시)
- [ ] 장시간(8시간+) 운영 시 온도/메모리 추이
- [ ] 본인 얼굴 + 책상 배경으로 도메인 검증

### 9-2. 코드/문서
- [ ] `src/postprocess.py`에 unit test (확인된 4 검출 케이스)
- [ ] benchmarks/ 폴더 git 정책 결정 (현재 포함됨 — 시간 흐르면 늘어남)
- [ ] `requirements.lock` 갱신 시점 정책 (Ultralytics 업데이트 시 등)
- [ ] danny docs 영문 mirroring (Qualcomm 영문 임직원 대비)

### 9-3. 보안/배포 (Public 전환 시)
- [ ] SSH key 인증으로 전환 (비번 차단)
- [ ] 비밀번호 변경
- [ ] `setenforce 0` 사용 흔적 점검
- [ ] License 명시
- [ ] noreply 이메일 적용 확인

---

## 10. 빠른 참조 — 자주 쓰는 명령

### 호스트 컨테이너 진입
```bash
cd /mnt/c/Project/unoq-companion-robot
bash run.sh
```

### 호스트 추론 / 벤치마크 (컨테이너 안에서)
```bash
python src/infer_image.py models/yolov8n_saved_model/yolov8n_int8.tflite datasets/coco128/images/train2017/000000000009.jpg
python src/benchmark_e2e.py models/yolov8n_saved_model/yolov8n_int8.tflite datasets/coco128/images/train2017/000000000009.jpg --runs 100 --warmup 10 --json benchmarks/host_e2e_$(date +%Y%m%d).json
```

### 디바이스 SSH (호스트 WSL에서)
```bash
ssh arduino@192.168.0.45
source ~/venv-unoq/bin/activate
```

### 디바이스 추론 (한 줄 원격, 호스트 WSL에서)
```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && python3 ~/infer_image.py /opt/unoq-yolo/models/yolov8n_int8.tflite /opt/unoq-yolo/media/000000000009.jpg'
```

### 디바이스 벤치마크 (한 줄 원격)
```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && mkdir -p ~/benchmarks && python3 ~/benchmark_e2e.py /opt/unoq-yolo/models/yolov8n_int8.tflite /opt/unoq-yolo/media/000000000009.jpg --runs 100 --warmup 10 --json ~/benchmarks/device_e2e_'"$(date +%Y%m%d)"'.json'
```

### 파일 전송
```bash
# 호스트 → 디바이스
scp src/infer_image.py arduino@192.168.0.45:~/
scp datasets/coco128/images/train2017/000000000009.jpg arduino@192.168.0.45:/opt/unoq-yolo/media/

# 디바이스 → 호스트 (결과 회수)
scp arduino@192.168.0.45:~/benchmarks/*.json /mnt/c/Project/unoq-companion-robot/benchmarks/
```

### Git
```bash
git status
git add -A
git commit -m "..."
git push
git log --oneline -5
```

### 디바이스 디스크/메모리 확인
```bash
ssh arduino@192.168.0.45 'df -h /; free -h | head -2'
```

---

## 11. GitHub 정보

- **레포**: https://github.com/donghee-ai/unoq-companion-robot (Private)
- **현재 commits**: 4 (Initial / Host validation / STEP 4-5 device / Official benchmark)
- **Author**: DongHee Kim <128051904+donghee-ai@users.noreply.github.com> (noreply)
- **License**: 미설정 (Public 전환 시 Apache-2.0 권장)

---

## 12. 마무리 메모

- 본 세션은 **0에서 시작해 멘토에게 한 사이클 보고 가능한 수준까지** 완료한 단일 세션
- 핵심 마일스톤: Docker 환경 / 모델 export / 호스트 검증 / 디바이스 셋업 / 디바이스 추론 / 후처리 모듈 / 공식 벤치마크 / 4기준 합격 판정
- 다음 세션 진입 시 본 문서(헤더의 갱신 안내 포함) + `docs/00`~`09` 읽으면 컨텍스트 복원
- 본 문서는 단발성 세션 요약, 향후 작업으로 outdated 될 수 있음 (마지막 갱신 2026-06-23)

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 위치 | 프로젝트 루트 (`C:\Project\unoq-companion-robot\SESSION_SUMMARY_2026-06-23.md`) |
| 용도 | 세션 종료 시 컨텍스트 핸드오프 + 멘토 보고 자산 |
| 다음 갱신 시점 | 없음 (단발 세션 요약). 새 세션은 새 SESSION_SUMMARY_<날짜>.md 권장 |
