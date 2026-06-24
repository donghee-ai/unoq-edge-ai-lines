# Docker 개발 환경 셋업 - Arduino UNO Q YOLO 프로젝트

> 본 문서는 본 프로젝트의 호스트 PC 개발 환경(Docker 컨테이너)을 정의 및 재현하기 위한 절차를 기록합니다. 본 환경은 모델 변환/검증/실험 용도이며, UNO Q 디바이스 자체에서 동작하는 환경은 별도 문서에서 다룹니다.

---

## 핵심 전제 - 반드시 먼저 읽으세요

| 항목 | 내용 |
|------|------|
| **호스트 OS** | Windows 11 + WSL2 (Ubuntu 24.04) |
| **호스트 셸** | WSL2 안의 bash (PowerShell에서 `wsl`로 진입) |
| **컨테이너 OS** | Ubuntu 22.04 |
| **컨테이너 Python** | 3.10.12 |
| **AI 런타임** | TFLite (LiteRT) 경유, TensorFlow 핀 |
| **사용 목적** | 호스트 PC에서의 모델 변환, 검증, 벤치마크 (디바이스 추론 X) |
| **공유 방식** | 5개 텍스트 파일(Dockerfile, requirements.txt/lock, .dockerignore, run.sh) git 푸시 → `bash run.sh`로 byte-exact 재현 |

### 왜 도커인가

> **여러 작업자의 컴퓨터에서 글자 그대로 동일한 환경을 보장하기 위함입니다.**

호스트 환경(WSL Ubuntu 24.04 + conda base)의 상태와 독립적으로 동작하므로, 호스트의 누적된 패키지 오염이 프로젝트에 영향을 주지 않습니다. 또한 협업자 측에서 동일한 4개 파일을 받아 `bash run.sh` 한 줄로 재현 가능합니다.

---

## 아키텍처 개요

```text
[Windows 11 호스트]
   |
   +-- [WSL2: Ubuntu 24.04]   <-- 본 프로젝트 작업 셸
         |
         +-- Docker Desktop (29.5.3) (WSL Integration ON)
               |
               +-- [컨테이너: ubuntu:22.04]   <-- 모든 Python 작업
                     +-- user: dev (UID/GID = 호스트와 동일)
                     +-- WORKDIR: /work  <-- 호스트 프로젝트 폴더 마운트
                     +-- Python 3.10 + TF + Ultralytics + OpenCV
```

---

## 디렉토리 구조

```text
C:\Project\
└── unoq-companion-robot/                <-- 프로젝트 루트 (git 대상)
    ├── Dockerfile                       <-- 환경 정의
    ├── requirements.txt                 <-- 의도 표현 (15개 패키지)
    ├── requirements.lock                <-- byte-exact 설치 (94 패키지, pip freeze 결과)
    ├── .dockerignore                    <-- 빌드 컨텍스트 위생
    ├── run.sh                           <-- 원샷 빌드+실행 스크립트
    └── docs/
        └── 00_environment_setup.md      <-- 본 문서
```

---

## 파일별 역할

| 파일 | 역할 | git 커밋 대상 |
|------|------|---|
| `Dockerfile` | 컨테이너 이미지 정의 (베이스, 시스템 패키지, 유저, Python 설치) | O |
| `requirements.txt` | pip 의도 표현 (사람이 읽는 형태) | O |
| `requirements.lock` | byte-exact 설치 (`pip freeze` 결과, 94 패키지) | O |
| `.dockerignore` | 빌드 컨텍스트에서 제외할 경로 패턴 | O (없으면 빌드만 느려짐) |
| `run.sh` | `docker build` + `docker run` 원샷 wrapper | O |
| `docs/*.md` | 작업/의사결정 기록 | O (선택) |

---

## 워크플로우 (호스트 PC 셋업)

### STEP 1 - 사전 준비

| 항목 | 확인 명령 | 기대 결과 |
|------|----------|----------|
| WSL2 동작 | `wsl -l -v` (PowerShell) | `Ubuntu` STATE=Running, VERSION=2 |
| Docker 동작 | `docker --version` (WSL bash) | `Docker version 2x.x.x` |
| Docker-WSL 통합 | `docker ps` (WSL bash) | 에러 없이 컨테이너 목록 표시 |

### STEP 2 - 프로젝트 디렉토리 생성

```bash
# WSL bash에서
mkdir -p /mnt/c/Project/unoq-companion-robot
cd /mnt/c/Project/unoq-companion-robot
```

> 이 위치를 선택한 이유: Windows fs(`/mnt/c/...`)에 두면 Windows IDE(VS Code 등)에서 자연스럽게 편집 가능. Docker 마운트 I/O 속도가 약간 느리지만 본 프로젝트의 병목은 아님. 필요 시 추후 WSL 홈(`~/`)으로 이전 가능.

### STEP 3 - 4개 파일 작성

`requirements.txt`, `.dockerignore`, `Dockerfile`, `run.sh`를 순서대로 작성합니다.

```bash
chmod +x run.sh
```

### STEP 4 - 빌드 + 컨테이너 진입

```bash
bash run.sh
```

첫 빌드는 시스템 패키지(약 300 MB) + Python 패키지(약 1.5 GB) 다운로드가 발생하여 **10~15분** 소요됩니다. 이후 캐시 활용으로 재진입은 5초 이내.

진입 성공 시 프롬프트 변화:

```
(base) a@DESKTOP-...:/mnt/c/Project/unoq-companion-robot$   <-- 호스트
                                  ↓ bash run.sh
dev@unoq-yolo-dev:/work$                                     <-- 컨테이너 내부
```

### STEP 5 - Smoke Test (검증)

컨테이너 안에서:

```bash
whoami                        # dev
pwd                           # /work
ls                            # Dockerfile, requirements.txt, run.sh
python --version              # Python 3.10.12
python -c "import tensorflow as tf, ultralytics, cv2, numpy; \
print('TF', tf.__version__); print('Ultralytics', ultralytics.__version__); \
print('OpenCV', cv2.__version__); print('NumPy', numpy.__version__)"
```

각 라이브러리 버전이 깨끗하게 출력되면 환경 정상.

---

## 컨테이너 사용 패턴

### 진입

```bash
cd /mnt/c/Project/unoq-companion-robot
bash run.sh
```

### 강제 재빌드 (Dockerfile/requirements.txt 변경 후)

```bash
bash run.sh --rebuild
```

### 종료

컨테이너 내부에서:

```bash
exit       # 또는 Ctrl+D
```

`--rm` 옵션으로 실행되므로 종료 시 컨테이너는 자동 삭제되며, 이미지는 보존됩니다.

### 추가 셸 열기 (이미 실행 중인 컨테이너에)

Docker Desktop GUI → Containers → `unoq-yolo-dev` → 터미널 아이콘 클릭

---

## 협업자 측 재현 절차

본 저장소를 받은 협업자는 동일 환경 재현을 위해 다음만 실행:

```bash
git clone <repo_url>
cd unoq-companion-robot
bash run.sh
```

전제 조건:

- Docker (Desktop 또는 Engine)
- bash 셸

호스트 OS는 무관 (Linux, macOS, Windows+WSL2 모두 동작).

---

## 알려진 경고 메시지 (무시 가능)

빌드 직후 첫 Python import 시 다음과 유사한 메시지가 출력됩니다. **모두 informational이며 동작에 영향 없습니다.**

| 메시지 | 원인 | 대응 |
|--------|------|------|
| `Could not find cuda drivers... GPU will not be used` | NVIDIA GPU 미사용 환경 | 정상. 본 환경은 CPU 전용 |
| `To enable AVX2 FMA, in other operations, rebuild TensorFlow...` | 사전 빌드 wheel의 표준 안내 | 정상. 빌드 시간 절약 vs 성능의 trade-off |
| `Could not find TensorRT` | NVIDIA TensorRT 미설치 | 정상. 의존하지 않음 |
| `/home/dev/.config/Ultralytics is not writable` | Ultralytics가 `/tmp/Ultralytics`로 폴백 | 정상. 향후 디렉토리 권한 부여로 제거 예정 |

---

## 알려진 한계 및 향후 개선

| 항목 | 현 상태 | 개선 방향 |
|------|--------|----------|
| GPU 가속 | 미사용 (CPU 전용) | 호스트 NVIDIA GPU가 있을 경우 `--gpus all` 추가 검토 |
| 모델 캐시 위치 | 컨테이너 임시 (`/tmp`) | named volume 또는 호스트 마운트로 영속화 |
| 카메라 패스스루 | 미설정 | UNO Q 디바이스에서 직접 추론하므로 호스트 환경에선 불필요 |
| 멀티 사용자 UID | `1000:1000` 고정 가정 | 향후 build-arg 기본값 동적 처리 (현재 `id -u`로 매핑) |

---

## 환경 진화 — `requirements.lock` 도입 경위

본 환경은 초기 `requirements.txt` 핀(`tensorflow==2.13.0`)만으로는 재현성이 부족하여 사고를 한 번 겪었습니다. 그 결과 transitive deps 사전 핀 + byte-exact lock 파일을 도입했습니다. 본 섹션은 그 사고/해결/학습을 압축 기록합니다.

### 사고 요약

YOLOv8n TFLite export 시도 중 두 단계 실패:

| 단계 | 원인 |
|---|---|
| 1차 실패 | Ultralytics export가 AutoUpdate로 핀된 환경 침범 (`tf_keras<=2.19.0` 요구가 TF 2.19, numpy 2.1, keras 3.12 강제 업그레이드). 같은 프로세스 안에서 TF 2.13 / TF 2.19 모듈 충돌 → `KerasTensor` 비호환 에러 |
| 2차 실패 | 디스크상 numpy 2.1.3 상태에서 torch 2.1.x(numpy 1.x ABI 빌드) import 시 `RuntimeError: Numpy is not available` (ABI 비호환) |

근본 원인: Ultralytics가 export 단계에서 누락 deps를 `pip install --user`로 자동 설치 → 기존 핀 침범 + mid-process 패키지 교체로 모듈 일관성 붕괴.

### 해결 — `requirements.txt` 핀 확장 + lock 파일 도입

`requirements.txt`를 의도 표현으로 유지하되, **AutoUpdate가 침범할 transitive deps를 모두 사전 핀**:

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
| `requirements.txt` | 의도 표현 ("TF 2.19, ultralytics 필요해") | 사람 |
| `requirements.lock` | byte-exact 설치 (94 패키지 동결) | Docker / pip |

### Lock 파일 갱신 시점

의도적으로 의존성 업그레이드할 때만:

1. `requirements.txt` 갱신
2. `bash run.sh --rebuild`
3. 컨테이너 안에서 `pip freeze > requirements.lock`
4. 커밋

Lock 파일은 직접 손으로 편집하지 않음 (생성 결과물).

### 학습 포인트 — Python 패키징 함정 3개

1. **상위 도구의 AutoUpdate**가 핀된 환경을 침범 (Ultralytics → tf_keras → TF/numpy 연쇄 업그레이드)
2. **사전 컴파일 wheel의 ABI 호환성**, 특히 numpy 메이저 버전(1.x vs 2.x) 경계 — torch 2.1.x는 numpy <2에 묶임
3. **mid-process 패키지 교체** 시 모듈 import 일관성 깨짐 — TF 2.13/2.19 동시 메모리 거주 → `KerasTensor` 에러

방어: 모든 transitive deps를 lock 파일로 사전 핀 → AutoUpdate 차단 + byte-exact 재현성.

---

## 빠른 참조 커맨드

```bash
# 호스트(WSL)에서 진입
cd /mnt/c/Project/unoq-companion-robot && bash run.sh

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

---

## 다음 단계

본 문서가 다루는 범위는 **호스트 PC 개발 환경 셋업**까지입니다. 이후 단계는 별도 문서로 분리합니다.

| 다음 문서 | 내용 |
|------|------|
| Git 초기화, `.gitignore`, 첫 커밋, GitHub 연결 | (별도 작업) |
| 모델 선택 의사결정 | 01 |
| 호스트 모델 검증 | 03 |
| UNO Q 디바이스 셋업 + 추론 | 04, 05 |
| End-to-end 측정 + 공식 벤치마크 | 07, 08 |

---

## 부록 - 파일 전체 내용

본 문서 시점의 환경 정의 파일들은 프로젝트 루트(`../`)에 위치합니다. 변경 이력은 git log를 참조하세요.

- `../Dockerfile`
- `../requirements.txt` (의도 표현)
- `../requirements.lock` (byte-exact 설치, 94 패키지)
- `../.dockerignore`
- `../run.sh`

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성 — Docker 호스트 환경 셋업 + 4 파일 정의 + smoke test | 빌드 성공 (약 13.5분) |
| 2026-06-23 | "환경 진화 — Lock 파일 도입" 섹션 흡수 (구 02 통합) — 환경 정의의 단일 SoT 완성 | 02 통합 / 중복 정리 |

---

## 작성 정보

| 항목 | 값 |
|------|-----|
| 작성일 | 2026-06-23 |
| 작성 시점 빌드 결과 | 성공 (총 빌드 시간 약 13.5분) |
| 검증 환경 | Windows 11 + WSL2 Ubuntu 24.04 + Docker Desktop 4.78.0 |
| 적용 범위 | 호스트 Docker 컨테이너 환경 (디바이스 환경은 04 참조) |
