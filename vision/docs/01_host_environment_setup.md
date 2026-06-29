# Docker Host Environment Setup

이 문서는 본 프로젝트의 호스트 PC 개발 환경(Docker 컨테이너)을 정의하고 재현하는 절차를 정리합니다. 모델 변환/검증/벤치마크 전용이며 UNO Q 디바이스 환경은 별도 문서로 분리됩니다.

## 0. 핵심 전제

| 항목 | 내용 |
|---|---|
| **호스트 OS** | Windows 11 + WSL2 (Ubuntu 24.04) |
| **호스트 셸** | WSL2 안의 bash |
| **컨테이너 OS** | Ubuntu 22.04 |
| **컨테이너 Python** | 3.10.12 |
| **AI 런타임** | TFLite (LiteRT), TensorFlow 핀 |
| **사용 목적** | 모델 변환, 검증, 벤치마크 (디바이스 추론은 별도) |
| **공유 방식** | 5개 텍스트 파일(Dockerfile, requirements.txt/lock, .dockerignore, run.sh) git 푸시 → `bash docker/run-vision.sh`로 byte-exact 재현 |

## 1. 왜 Docker인가

호스트 환경(WSL Ubuntu 24.04 + conda)의 상태와 독립적으로 동작합니다. 호스트 패키지 오염이 프로젝트에 영향을 주지 않고, 협업자 측에서 동일한 5개 파일을 받아 `bash docker/run-vision.sh` 한 줄로 재현할 수 있습니다.

## 2. 아키텍처

```text
[Windows 11 호스트]
   |
   +-- [WSL2: Ubuntu 24.04]   <-- 작업 셸
         |
         +-- Docker Desktop (29.5.3) (WSL Integration ON)
               |
               +-- [컨테이너: ubuntu:22.04]
                     +-- user: dev (UID/GID = 호스트 동일)
                     +-- WORKDIR: /work
                     +-- Python 3.10 + TF + Ultralytics + OpenCV
```

## 3. 디렉토리 구조

```text
vision/
├── Dockerfile             환경 정의
├── requirements.txt       의도 표현 (15 패키지)
├── requirements.lock      byte-exact 설치 (94 패키지)
├── .dockerignore          빌드 컨텍스트 위생
├── run.sh                 원샷 빌드+실행
└── docs/                  의사결정 로그
```

## 4. 파일별 역할

| 파일 | 역할 |
|---|---|
| `Dockerfile` | 컨테이너 이미지 정의 |
| `requirements.txt` | pip 의도 표현 (사람이 읽음) |
| `requirements.lock` | byte-exact 설치 (Docker가 읽음) |
| `.dockerignore` | 빌드 컨텍스트 제외 패턴 |
| `run.sh` | `docker build` + `docker run` 원샷 |
| `docs/*.md` | 작업/의사결정 기록 |

## 5. 호스트 셋업 워크플로우

### 5-1. 사전 준비

| 항목 | 확인 명령 | 기대 결과 |
|---|---|---|
| WSL2 동작 | `wsl -l -v` (PowerShell) | `Ubuntu` STATE=Running, VERSION=2 |
| Docker 동작 | `docker --version` (WSL bash) | `Docker version 2x.x.x` |
| Docker-WSL 통합 | `docker ps` (WSL bash) | 에러 없이 컨테이너 목록 |

### 5-2. 프로젝트 디렉토리 생성

```bash
mkdir -p /mnt/c/Project/unoq-companion-robot
cd /mnt/c/Project/unoq-companion-robot
```

### 5-3. 빌드 + 컨테이너 진입

```bash
bash docker/run-vision.sh
```

첫 빌드는 시스템 패키지 + Python 패키지 다운로드로 10~15분. 이후 캐시 활용으로 재진입은 5초 이내.

진입 성공 시 프롬프트 변화:

```text
(base) a@DESKTOP-...:/mnt/c/Project/unoq-companion-robot$
                                  ↓ bash docker/run-vision.sh
dev@unoq-yolo-dev:/work$
```

### 5-4. Smoke Test

```bash
whoami                        # dev
pwd                           # /work
python --version              # Python 3.10.12
python -c "import tensorflow as tf, ultralytics, cv2, numpy; \
print('TF', tf.__version__); print('Ultralytics', ultralytics.__version__); \
print('OpenCV', cv2.__version__); print('NumPy', numpy.__version__)"
```

각 라이브러리 버전이 깨끗하게 출력되면 환경 정상.

## 6. 사용 패턴

### 진입

```bash
cd /mnt/c/Project/unoq-companion-robot
bash docker/run-vision.sh
```

### 강제 재빌드 (Dockerfile / requirements 변경 후)

```bash
bash docker/run-vision.sh --rebuild
```

### 종료

```bash
exit                          # 또는 Ctrl+D
```

`--rm` 옵션으로 컨테이너 자동 삭제, 이미지는 보존됩니다.

## 7. 협업자 재현

```bash
git clone <repo_url>
cd unoq-companion-robot
bash docker/run-vision.sh
```

전제 조건: Docker (Desktop 또는 Engine), bash 셸. 호스트 OS 무관 (Linux, macOS, Windows+WSL2).

## 8. 알려진 경고 메시지 (무시 가능)

| 메시지 | 원인 | 대응 |
|---|---|---|
| `Could not find cuda drivers... GPU will not be used` | NVIDIA GPU 미사용 | 정상. 본 환경 CPU 전용 |
| `To enable AVX2 FMA, rebuild TensorFlow...` | 사전 빌드 wheel 표준 안내 | 정상. 빌드 시간 절약 trade-off |
| `Could not find TensorRT` | NVIDIA TensorRT 미설치 | 정상. 의존하지 않음 |
| `/home/dev/.config/Ultralytics is not writable` | Ultralytics가 `/tmp/Ultralytics`로 폴백 | 정상 |

## 9. 알려진 한계

| 항목 | 현 상태 | 개선 방향 |
|---|---|---|
| GPU 가속 | 미사용 (CPU 전용) | 호스트 NVIDIA GPU가 있으면 `--gpus all` 검토 |
| 모델 캐시 위치 | 컨테이너 임시 (`/tmp`) | named volume 또는 호스트 마운트 |
| 카메라 패스스루 | 미설정 | UNO Q에서 직접 추론하므로 호스트엔 불필요 |
| 멀티 사용자 UID | `1000:1000` 고정 가정 | build-arg 동적 처리 (현재 `id -u` 매핑) |

## 10. Lock 파일 도입 경위

본 환경은 초기 `requirements.txt` 핀(`tensorflow==2.13.0`)만으로는 재현성이 부족하여 사고를 한 번 겪었습니다. transitive deps 사전 핀 + byte-exact lock 파일을 도입한 경위를 압축 기록합니다.

### 10-1. 사고 요약

YOLOv8n TFLite export 시도 중 두 단계 실패:

| 단계 | 원인 |
|---|---|
| 1차 실패 | Ultralytics export가 AutoUpdate로 핀된 환경 침범 (`tf_keras<=2.19.0` 요구가 TF 2.19, numpy 2.1, keras 3.12 강제 업그레이드). TF 2.13 / TF 2.19 모듈 충돌 → `KerasTensor` 비호환 에러 |
| 2차 실패 | 디스크상 numpy 2.1.3 + torch 2.1.x(numpy 1.x ABI 빌드) → `RuntimeError: Numpy is not available` |

근본 원인: Ultralytics가 export 단계에서 누락 deps를 `pip install --user`로 자동 설치 → 기존 핀 침범 + mid-process 패키지 교체로 모듈 일관성 붕괴.

### 10-2. 해결 — requirements.txt 핀 확장 + lock 파일

`requirements.txt`를 의도 표현으로 유지하되, AutoUpdate가 침범할 transitive deps를 모두 사전 핀:

```diff
- tensorflow==2.13.0
+ # Core scientific
+ numpy==1.26.4
+ # TensorFlow / Keras stack
+ tensorflow==2.19.1
+ tf_keras==2.19.0
+ keras==3.12.2
+ ai-edge-litert
+ protobuf>=5,<6
+ # Ultralytics + ONNX 변환 도구 체인
+ ultralytics
+ onnx, onnxruntime, onnxslim, onnx2tf, onnx_graphsurgeon, sng4onnx
```

| 패키지 | 핀 버전 | 근거 |
|---|---|---|
| numpy | 1.26.4 | torch 2.1.x(<2) + TF 2.19(>=1.26) 교집합 |
| tensorflow | 2.19.1 | Ultralytics 요구 tf_keras 2.19.0과 짝 |
| protobuf | >=5,<6 | TF 2.19 호환, 미래 6.x 변경 차단 |

export 성공 시점에 byte-exact lock 파일 생성:

```bash
pip freeze > requirements.lock     # 94 패키지 동결
```

`Dockerfile`은 실제 설치 출처를 `requirements.lock`으로 변경:

```dockerfile
COPY requirements.txt requirements.lock /tmp/
RUN pip3 install --user -r /tmp/requirements.lock
```

| 파일 | 용도 | 누가 읽나 |
|---|---|---|
| `requirements.txt` | 의도 표현 | 사람 |
| `requirements.lock` | byte-exact 설치 (94 패키지 동결) | Docker / pip |

### 10-3. Lock 파일 갱신 시점

의도적으로 의존성 업그레이드할 때만:

1. `requirements.txt` 갱신
2. `bash docker/run-vision.sh --rebuild`
3. 컨테이너 안에서 `pip freeze > requirements.lock`
4. 커밋

Lock 파일은 직접 손으로 편집하지 않습니다 (생성 결과물).

### 10-4. 학습 포인트

1. 상위 도구의 AutoUpdate가 핀된 환경을 침범 (Ultralytics → tf_keras → TF/numpy 연쇄 업그레이드).
2. 사전 컴파일 wheel의 ABI 호환성, 특히 numpy 메이저 버전(1.x vs 2.x) 경계 — torch 2.1.x는 numpy <2에 묶임.
3. mid-process 패키지 교체 시 모듈 import 일관성 깨짐 — TF 2.13 / TF 2.19 동시 메모리 거주 → `KerasTensor` 에러.

방어: 모든 transitive deps를 lock 파일로 사전 핀 → AutoUpdate 차단 + byte-exact 재현성 확보.

## 11. 빠른 참조 커맨드

```bash
# 호스트(WSL)에서 진입
cd /mnt/c/Project/unoq-companion-robot && bash docker/run-vision.sh

# 컨테이너 안에서 Python 버전/패키지 확인
python --version
pip list | head -20

# 컨테이너 안에서 마운트 확인
mount | grep work
ls -la /work

# 호스트에서 이미지 확인
docker images | grep unoq-yolo-dev

# 호스트에서 이미지 제거 (강제 재빌드 전)
docker rmi unoq-yolo-dev:22.04
```

## 12. 다음 문서

| 문서 | 내용 |
|---|---|
| 01 | 모델 선택 의사결정 |
| 03 | 호스트 모델 검증 |
| 04, 05 | UNO Q 디바이스 셋업 + 추론 |
| 07, 08 | End-to-end 측정 + 공식 벤치마크 |
| 09 | 카메라 실시간 추론 |

## 부록 — 파일 위치

본 문서 시점의 환경 정의 파일들은 프로젝트 루트(`../../`)에 위치합니다. 변경 이력은 git log 참조.

- `../../Dockerfile`
- `../../requirements.txt` (의도 표현)
- `../../requirements.lock` (byte-exact 설치, 94 패키지)
- `../../.dockerignore`
- `../../docker/run-vision.sh`
