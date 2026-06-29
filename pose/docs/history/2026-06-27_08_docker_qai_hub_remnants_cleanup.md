# 2026-06-27 — Docker qai-hub 잔여물 + 미사용 apt 패키지 정리 (옵션 A1)

## 시점
2026-06-27 (폴더 통합 직후 마무리 사이클)

## 사건
사용자 점검 요청 → 본 라인의 docker/ 환경에서 qai-hub 인프라와 미사용 시스템 패키지 잔여물 제거. 옵션 A1 채택 (모두 제거, 향후 필요 시 재추가).

## 제거된 항목

### 1. qai-hub 인프라 (본 라인 미사용)
- `docker/entrypoint.sh` 삭제 (24줄, QAI_HUB_API_TOKEN → client.ini 자동 작성)
- `.env`, `.env.example` 삭제 (QAI_HUB_API_TOKEN 템플릿)
- `Dockerfile.pose`의 `COPY entrypoint.sh` + `ENTRYPOINT` 라인 제거 → 단순 `CMD ["bash"]`
- `run-pose.sh`의 `--env-file` 분기 제거 (`.env` 자동 로드 로직 X)
- `.gitignore`의 `.env*`, `~/.qai_hub/` 항목 제거

### 2. 시스템 apt 패키지 (본 라인 미사용 확정)
점검 결과 — `scripts/`와 `requirements-pose.txt` 검색 0건 매칭:

| 패키지 | 본 라인 사용처 |
|---|---|
| `ffmpeg` | 0건 — `cv2.VideoCapture(int)` 카메라 인덱스만, `cv2.imencode('.jpg')` JPEG만. 비디오 파일 입출력 코드 X. opencv-python wheel은 자체 포함. |
| `git` | 0건 — `requirements`에 git+ 패키지 없음, 런타임 git clone 없음 |
| `build-essential` | 0건 — requirements 모든 패키지 manylinux prebuilt wheel 사용 |

→ Dockerfile.pose `RUN apt-get install` 라인에서 3 패키지 모두 제거.

### 3. 보존 패키지 (확실히 사용)
- `python3.10`, `python3-pip`, `python3.10-venv` — base runtime
- `libgl1-mesa-glx`, `libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1` — opencv-python 의존
- `wget`, `curl` — 모델 다운로드 (TFHub MoveNet)
- `ca-certificates` — HTTPS

### 4. docs 갱신
- `docs/00_project_blueprint.md` 디렉토리 트리에서 `.env`, `.env.example`, `entrypoint.sh` 줄 제거
- `SESSION_SUMMARY_2026-06-27.md` 동일 부분 갱신
- `Dockerfile.pose` 줄 설명을 "qai-hub/torch/tf 제거"에서 "최소 의존성"으로 단순화

## 비교 — vision/asr 라인과 차이

본 라인(unoq-pose) 정리 결과 vs 다른 라인:

| 항목 | unoq-pose | unoq-companion-robot | unoq-asr |
|---|---|---|---|
| `ffmpeg` | **제거** | 보유 | 보유 (audio format conversion) |
| `git` | **제거** | 보유 | 보유 |
| `entrypoint.sh` qai-hub | **제거** | 없음 (애초 무 의존) | 없음 |
| `.env` / `.env.example` | **제거** | 없음 | 없음 |

vision/asr가 ffmpeg + git 보유한 이유는 옛 패턴 + ASR audio 처리. 본 라인은 카메라 라이브 + JPEG serve만이라 미사용 확정. **stack 차이 의도적**, 본 라인 docs/00에 명시.

## 영향

### 빌드 시간
- 이전: ~3 min (qai-hub 제거 후)
- 본 정리 후 예상: ~2 min (apt 추가 3패키지 제거)

### Docker image 크기
- 이전: 4.31 GB virtual / 13.8 GB on disk
- ffmpeg(~80 MB) + git(~50 MB) + build-essential(~150 MB) 제거 → 약 280 MB 감소 예상
- 다음 rebuild 시 자동 반영

### 사용성
- `bash docker/run-pose.sh` 한 줄로 컨테이너 진입 변화 없음
- `.env` 안 만들어도 경고 메시지 없음 (qai-hub WARN 제거)
- 향후 비디오 파일 입력 필요 시 Dockerfile에 `ffmpeg` 한 줄 추가 + rebuild

## 자산

수정/삭제:
- `docker/Dockerfile.pose` — 정리 (1830 B)
- `docker/run-pose.sh` — 정리 (1413 B)
- `docker/entrypoint.sh` — **삭제**
- `.env` — **삭제**
- `.env.example` — **삭제**
- `.gitignore` — 정리 (Secrets 섹션 제거)
- `docs/00_project_blueprint.md` — 디렉토리 트리 갱신
- `SESSION_SUMMARY_2026-06-27.md` — 동일

## 미정 — 다음 결정 후보 (보류)

| 항목 | 결정 시점 |
|---|---|
| 4안 HeadDropCounter + auto mode 전환 | 사용자 해석 (B) 확인 후 즉시 진행 가능 |
| Docker rebuild 실제 진행 (현 이미지는 옛 빌드 그대로) | 다음 컨테이너 진입 시 자동, 또는 즉시 `--rebuild` |
| ffmpeg 재추가 (`--video file.mp4` 입력 추가 시) | 필요 시점에 1줄 추가 |

## 관련
- 직전 폴더 통합: [`2026-06-27_07_history_issues_moved_under_docs.md`](2026-06-27_07_history_issues_moved_under_docs.md)
- 본 라인 이름 정리: [`2026-06-27_05_trace_analysis_and_line_rename.md`](2026-06-27_05_trace_analysis_and_line_rename.md)
- QNN ONNX 비호환 결론 (qai-hub 우회 사유): [`../issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md`](../issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md)
