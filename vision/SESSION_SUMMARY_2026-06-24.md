# Session Summary — 2026-06-24

본 세션은 멘토 인계 준비를 중심으로 한 메타 작업 세션. 코드 변경 없음, 문서/설정/메타데이터 보강 중심.

## 0. 세션 결정 요약

| 항목 | 결과 |
|---|---|
| 주제 | 멘토 인계 준비 (압축 / Collaborator / md only 결정) + 카메라 사양 보강 |
| 신규 코드 | 없음 |
| 변경 파일 | `README.md`, `docs/08_realtime_camera.md`, `.gitignore` |
| 추적 해제 | `.markdownlint.jsonc` (로컬 에디터 설정) |
| 신규 커밋 | 6건 |
| 미해결 작업 | 메모리 파일 갱신 (docs 경로 변경 반영), soak test, 멘토 GitHub 핸들 수신 후 Collaborator 초대 |

## 1. 작업 항목

### 1-1. README 하드웨어 표기 정정

기존 표기가 옵션 범위로 모호 → 실제 디바이스 사양으로 확정.

| 항목 | Before | After |
|---|---|---|
| RAM / 저장소 | 2~4 GB LPDDR4 / 16~32 GB eMMC | 4 GB LPDDR4 / 32 GB eMMC |

참고: [docs/00_project_blueprint.md:17-18](docs/00_project_blueprint.md#L17-L18)에는 RAM 4 GB / eMMC 16 GB (root `/` 9.8 GB 할당, 가용 2.9 GB)로 측정값 그대로 보존. 실제 사양과 측정 파티션 차이는 별개 문서 항목으로 유지.

### 1-2. `docs/` 폴더 이름 유지 결정

"가이드" 한국어 이름으로 변경 검토 → `docs/` 유지로 결정.

| 근거 | 내용 |
|---|---|
| 컨벤션 | GitHub/OSS 표준 (README.md 옆 `docs/`) |
| 내용 범위 | 가이드뿐 아니라 의사결정 로그 + 측정 보고 + 청사진 — 영문 `docs/`가 더 포괄적 |
| 링크 안정성 | 한글 폴더는 URL 인코딩 발생, 외부 링크 가독성 저하 |

### 1-3. `.markdownlint.jsonc` 추적 해제

로컬 에디터 린트 설정 → gitignore 추가 + 인덱스 제거.

```diff
# .gitignore
+ # === 로컬 에디터 설정 (개인 취향, 공유 불필요) ===
+ .markdownlint.jsonc
```

`git rm --cached .markdownlint.jsonc`로 인덱스에서 제거, 파일 자체는 로컬에 보존 (VSCode 린트 계속 동작).

### 1-4. 멘토 인계 방법 정리

| 방법 | 적합한 상황 | 비고 |
|---|---|---|
| GitHub Collaborator 초대 | 멘토 GitHub 계정 있음 + 지속 검토 | 권장. 멘토 GitHub 핸들 또는 가입 이메일 필요 |
| ZIP 전송 | 일회성 / 멘토 GitHub 없음 | 단발성 — 후속 업데이트 매번 다시 보내야 함 |
| Public 전환 | 최종 발표 / 공개 시점 | 현 단계엔 부적합 (LICENSE, 비밀 정보 점검 미완) |

본 세션 결정: 멘토 GitHub 핸들 받기 전 1차 검토는 **md만 ZIP 전송**으로 진행.

### 1-5. 압축 방법 안내

`git archive` 사용 (트래킹된 파일만 자동 선별 → `docs/mentor/`, `SESSION_SUMMARY*`, `.markdownlint.jsonc` 자동 제외).

| 시나리오 | 명령 |
|---|---|
| 전체 (코드 + 문서 + Docker) | `git archive --format=zip HEAD -o unoq-full-<DATE>.zip` |
| md만 (멘토 1차 검토) | `git archive --format=zip HEAD -o unoq-docs-<DATE>.zip README.md docs/` |

탐색기 우클릭 압축 비추천 — `docs/mentor/` 같이 포함되어 대외비 노출 위험.

### 1-6. 도커 환경 점검

지금 상태에서 멘토가 환경 그대로 재현 가능한지 확인 → **그대로 가능**.

| 파일 | 역할 | 상태 |
|---|---|---|
| `Dockerfile` | Ubuntu 22.04 + Python + OpenCV deps + non-root user + requirements.lock 자동 설치 | 준비됨 |
| `run.sh` | 원샷 빌드+실행, 이미지 없으면 빌드 / 있으면 재사용, `--rebuild`로 강제 재빌드 | 준비됨 |
| `requirements.lock` | 94 패키지 byte-exact 핀 | 준비됨 |

멘토 측 실행: 압축 풀고 `bash run.sh` 한 줄로 컨테이너 진입.

전제: Docker (Desktop or Engine) + bash 셸 (Windows는 WSL2 / Git Bash) + 디스크 약 5 GB.

### 1-7. 카메라 사양 보강

기존 `USB UVC, 640×480 캡처` 한 줄 → 실제 사양으로 분리.

#### 사양 확정

- 모델: SU200 USB UVC mini camera
- 렌즈: 2.8 mm
- 전원: DC 5 V
- native 해상도: 720p

#### `v4l2-ctl --list-formats-ext`로 검증한 지원 포맷

| Pixel format | 1280×720 | 640×480 |
|---|---|---|
| MJPG | 30 fps | 25 fps |
| YUYV | 10 fps | 25 fps |

#### 반영 위치

- [README.md](README.md) 하드웨어 사양 표: `카메라` 행 추가
- [docs/08_realtime_camera.md](docs/08_realtime_camera.md) Section 1 측정 환경: 카메라 모델 / 지원 포맷 / 해상도 3행

### 1-8. 카메라 노드 진단 (1회성 학습)

`v4l2-ctl --list-formats-ext -d /dev/video0` 출력에서 의외의 결과 확인:

| 출력 패턴 | 정체 |
|---|---|
| `Type: Video Capture` (single-plane) + MJPG/YUYV | USB UVC 카메라 (정상) |
| `Type: Video Capture Multiplanar` + NV12/Q08C | Qualcomm 카메라 ISP / CSI 백엔드 (M2M) |
| `Type: Video Capture Multiplanar` + H264/HEVC | Qualcomm Venus 비디오 인코더 (카메라 아님) |

SU200 USB가 분리된 상태에선 `/dev/video0`, `/dev/video1`가 Qualcomm Venus 인코더(qcom-venus)로 노출됨 — UVC가 아님. USB 재연결 + uvcvideo 재로드 시 정상 UVC 노드로 노출.

본 진단 내용은 [docs/08](docs/08_realtime_camera.md) 본문에는 반영하지 않기로 결정 (사용자 의사 — 스펙만 유지). 본 세션 요약에만 학습 기록 보존.

### 1-9. 카메라 병목 정량 검증

8.29 FPS (실측 e2e) vs 카메라 native 25 fps (640×480 한계) = **33%만 사용**. capture latency 1.4 ms 평균.

→ 카메라는 충분히 여유, 추론(CPU)이 명백한 병목. 이미 [docs/05](docs/05_initial_inference_measurement.md), [docs/07](docs/07_official_benchmark.md)에서 도출된 결론이지만 v4l2 출력으로 정량 검증됨.

본 분석도 [docs/08](docs/08_realtime_camera.md) 본문에는 반영하지 않음 (사용자 결정).

## 2. 커밋 목록

| 커밋 | 내용 |
|---|---|
| `eca047d` | README: 카메라 실시간 + thermal 70.8°C + 신규 docs 구조 반영 |
| `20df2cb` | gitignore: .markdownlint.jsonc 추적 해제 (로컬 에디터 설정) |
| `16bd53d` | docs/08: 카메라 사양 명시 (SU200 720p, 2.8mm, DC 5V) |
| `6ac84a9` | README: 하드웨어 사양에 카메라 행 추가 (SU200 720p) |
| `20e849f` | docs/08: 카메라 진단 보강 (v4l2 정량 검증 + Venus 코덱 함정) |
| `80c60ab` | docs/08: 카메라 스펙만 남기고 분석/진단 섹션 제거 (20e849f 일부 롤백) |

## 3. 함정 / 사건 기록

| 사건 | 원인 | 해결 |
|---|---|---|
| RAM/저장소 옵션 범위 표기 | 사양 범위로 적어 모호 | 실제 디바이스 값으로 확정 |
| `git commit`이 "not a git repository"로 실패 | Bash 명령에서 `cd /c/Project/unoq-companion-robot` 누락 | `cd` 프리픽스 명시 후 재시도 성공 |
| `.markdownlint.jsonc`가 이미 트래킹 중 | 이전 add 흔적 — gitignore만 추가하면 효과 없음 | `git rm --cached` + gitignore 추가 동시 처리 |
| `v4l2-ctl -d /dev/video0`가 NV12/Q08C만 노출 | SU200 USB 분리 상태, video0/1이 Qualcomm Venus 인코더 노드였음 | USB 재연결 + uvcvideo 재로드 후 정상 UVC 노드로 노출 |
| 카메라 진단 섹션 docs에 일단 추가 → 사용자가 "스펙만"으로 회수 요청 | 분석/함정/진단 섹션은 docs/08 본문 범위 초과 판단 | 80c60ab에서 롤백, 스펙 3행만 유지 |

## 4. 학습 / 메모

### 4-1. v4l2-ctl 진단 명령

```bash
# 노드 능력
v4l2-ctl --list-formats-ext -d /dev/videoN

# 드라이버 정체 확인 (uvcvideo면 USB UVC, qcom-venus면 코덱 노드)
v4l2-ctl --all -d /dev/videoN | head -5
```

### 4-2. uvcvideo 재로드 (USB 인식 끊김 복구)

```bash
sudo modprobe -r uvcvideo
sudo modprobe uvcvideo
sleep 2
ls /dev/video*
```

### 4-3. git archive로 안전한 멘토용 ZIP

```bash
# md만
git archive --format=zip HEAD -o unoq-docs-2026-06-24.zip README.md docs/

# 결과 검증 (mentor / SESSION 문자열이 없어야 함)
unzip -l unoq-docs-2026-06-24.zip | grep -E "mentor|SESSION" && echo "WARN: leak"
```

## 5. 다음 작업 후보

| 우선순위 | 항목 | 비고 |
|---|---|---|
| 1 | 멘토 GitHub 핸들 받고 Collaborator 초대 또는 1차 ZIP 전송 | 본 세션 결과물 기반 |
| 2 | Soak test 8h+ (thermal plateau 확인) | docs/08 운영 측정에서 thermal 70.8°C — 임계 1°C 초과 |
| 3 | `--serve` 부담 분리 측정 (30분 작업) | HTTP MJPEG 서빙이 thermal에 미친 영향 분리 |
| 4 | 메모리 파일 갱신 (docs/00~08 → 00~09 경로 반영) | `~/.claude/projects/c--Project/memory/` 하위 파일 |
| 5 | 얼굴 검출 / 표정 추론 파이프라인 | MediaPipe Face 우선 검토 |
| 6 | MCU 연동 (STM32U585 + LED / 모터) | YOLO 검출 결과 → 반응 트리거 |

## 6. 미해결 사항

- `.gitignore`에 `SESSION_SUMMARY*.md` 패턴이 명시되지 않음 — 현재 트래킹은 안 되고 있지만 `git add .` 같은 광범위 add 시 실수로 포함될 수 있음. 명시 추가 검토 필요.
- README의 `한국어 + 영문 키워드 제목` 일관성 — 일부 섹션 헤더 한국어, 일부 영문. 통일 여부는 멘토 양식 가이드라인에 명시 안 됨.
- docs/00 청사진의 eMMC 16 GB (측정값) vs 실 사양 32 GB — 한 곳에 주석 추가 검토 가능 (본 세션은 미반영).
