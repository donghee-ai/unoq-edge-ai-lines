# UNO Q Device Setup and TFLite Runtime Installation

본 문서는 UNO Q 디바이스의 SSH 연결 확립, 사양 실측, TFLite 런타임 선택 및 설치 결정을 정리합니다. 단일 책임 — 디바이스 준비 단계의 환경 / 의사결정 / 절차 기록.

## 0. 핵심 결정

| 항목 | 결정 / 결과 |
|---|---|
| **디바이스 SSH 사용자** | `arduino` (hostname `unoq-korea01`과 별개) |
| **디바이스 IP** | `192.168.0.45` (DHCP, 동일 LAN) |
| **디바이스 OS / Python** | Debian aarch64 (kernel 7.0) / Python 3.13.5 |
| **디바이스 SoC** | QRB2210 (soc_id 524) — 가정 정확히 일치 |
| **TFLite 런타임 사전 설치** | 없음 (`tflite_runtime`, `tensorflow` 둘 다 미설치) |
| **Qualcomm `gst-ai-object-detection`** | 없음 (PATH에 없음) |
| **채택 런타임** | `ai-edge-litert` (pip + venv 경유) |
| **시스템 Python 오염 방지** | venv 사용 (`~/venv-unoq`) |
| **추론 코드 호환성** | 3단 import 폴백 (ai_edge_litert → tflite_runtime → tensorflow.lite) |

## 1. SSH 사용자 정보

디바이스 측 `id` 결과:

- 사용자명 / 호스트명: `arduino` / `unoq-korea01` (별개).
- UID / GID: 1000 / 1000.
- 그룹: `arduino, adm, dialout, sudo, audio, video, users, netdev, bluetooth, docker, sysupgrade, render, input, gpiod`.

본 작품 관련 그룹:

| 그룹 | 권한 |
|---|---|
| `sudo` | 시스템 명령 가능 |
| `docker` | 디바이스에서 컨테이너 실행 가능 (필요 시) |
| `gpiod` | LED / 모터 GPIO 제어 권한 (작품에 핵심) |
| `video`, `render` | 카메라 및 그래픽 출력 가능 |

## 2. 디바이스 사양 (실측)

### 2-1. 하드웨어

| 항목 | 값 | 출처 |
|---|---|---|
| **Kernel** | Linux 7.0.0-g122c2c22d838 SMP PREEMPT | `uname -a` |
| **Architecture** | aarch64 (ARM64) | 동상 |
| **SoC** | QRB2210 (soc_id 524) | `/sys/devices/soc0/{soc_id,machine}` |
| **CPU 코어** | 4 | `nproc` |
| **RAM** | 3.6 GB total / 2.4 GB 가용 | `free -h` |
| **Storage (/)** | 9.8 GB total / 2.9 GB 가용 (69% used) | `df -h /` |

### 2-2. 소프트웨어

| 항목 | 값 |
|---|---|
| Python | 3.13.5 (`/usr/bin/python3`) |
| pip | 미설치 (`No module named pip`) |
| `tflite_runtime` | 미설치 |
| `tensorflow` | 미설치 |
| `gst-ai-object-detection` | PATH에 없음 |

### 2-3. 그래픽 / GPU 관련

| 항목 | 값 | 의미 |
|---|---|---|
| `/dev/dri/card0`, `renderD128` | 존재 | DRM / KMS 그래픽 스택 사용 가능 |
| `/dev/kgsl*` | 없음 | Qualcomm GPU 메모리 디바이스 미노출 → OpenCL / Adreno 가속 어려울 가능성 |

GPU delegate 시도는 후순위. CPU 단독 경로가 안정적이며 본인 기대치(8~15 FPS)에 충분할 가능성.

## 3. 멘토 docs 검토 결과 (pip 접근 정당성)

본 단계 진입 전, 멘토 패키지 docs 중 디바이스 측 런타임 관련 부분 정독.

### 3-1. 멘토 docs의 가정

- 디바이스에 `tflite_runtime` (또는 `tensorflow`) 사전 설치되어 있음을 전제.
- 설치 방법은 명시되지 않음.
- 사용 코드 패턴: `try: import tflite_runtime.interpreter; except ImportError: import tensorflow.lite`.

### 3-2. 본인 디바이스 현실과의 차이

- 사전 설치된 런타임 없음 → 본인이 설치해야 함.
- 멘토가 가정한 사전 설치 도구들 (`gst-ai-object-detection`, `benchmark_model`) 모두 없음.

### 3-3. pip 접근 적합성 평가

| 항목 | 적합성 |
|---|---|
| pip 사용 | OK — 멘토 docs가 설치 방법을 명시하지 않으므로 충돌 없음 |
| venv 사용 | 권장 — Debian 12+ PEP 668 정책상 시스템 Python 직접 수정 차단 |
| 런타임 패키지 선택 | `ai-edge-litert` 권장 — Python 3.13 / aarch64 환경에서 `tflite-runtime` 대비 호환성 우수 |
| 멘토 코드 패턴 적용 | 가능 (import 폴백 패턴에 `ai_edge_litert.interpreter` 추가하여 3단 폴백) |

### 3-4. 결론

pip + venv + ai-edge-litert 채택. 멘토 docs의 정신(TFLite 사용)에 충실하며, Python 3.13 + aarch64 + Debian 12+ 환경 제약에 부합.

## 4. 런타임 선택 — `ai-edge-litert` vs `tflite-runtime`

| 측면 | `tflite-runtime` | `ai-edge-litert` |
|---|---|---|
| 제공처 | TensorFlow 팀 (legacy) | Google AI Edge (modern 대체) |
| 패키지 크기 | ~3 MB | ~17 MB |
| Python 3.13 지원 (aarch64) | 불확실 / 제한적 | 지원 |
| 향후 유지보수 | 점진적 EOL 예고 | 활발 |
| 호스트 컨테이너 일치 | 없음 (호스트는 tensorflow.lite) | 호스트 requirements.lock에 `ai-edge-litert==2.1.5` 포함됨 (양측 통일 가능) |
| 채택 | 호환성 위험 | 채택 |

호스트와 디바이스 양측이 `ai_edge_litert` 동일 import를 쓸 수 있어 코드 일관성도 확보.

## 5. 설치 절차 — `scripts/setup_device.sh`로 자동화

본 절차는 `scripts/setup_device.sh` 스크립트 하나로 묶어 재현성 확보.

### 5-1. 스크립트 실행

#### 방법 A: 호스트에서 전송 후 일괄 실행

```bash
# 호스트 WSL에서
scp scripts/setup_device.sh arduino@192.168.0.45:~/
ssh arduino@192.168.0.45 'bash ~/setup_device.sh'
```

#### 방법 B: SSH 들어간 상태에서 직접

```bash
# 호스트에서 한 번 전송
scp scripts/setup_device.sh arduino@192.168.0.45:~/

# 디바이스 SSH 셸에서
bash ~/setup_device.sh
```

스크립트는 idempotent — 재실행해도 안전 (이미 있는 건 skip, 없는 것만 설치).

### 5-2. 스크립트가 수행하는 5단계

| Phase | 작업 |
|---|---|
| Phase 1 | `python3-pip`, `python3-venv` apt 설치 (없을 때만) |
| Phase 2 | `~/venv-unoq` 가상환경 생성 (없을 때만) |
| Phase 3 | `pip install ai-edge-litert numpy` (venv 안에) |
| Phase 4 | import 동작 확인 (`ai_edge_litert.Interpreter`, `numpy`) |
| Phase 5 | `/opt/unoq-yolo/{models,labels,media,configs,logs}` 디렉토리 생성 + chown |

각 phase 시작 시 콘솔에 `==> Phase N: ...` 출력 → 어디까지 진행됐는지 명확.

### 5-3. 수동 실행 (스크립트 없이) — 참고용

스크립트 없이 한 줄씩 칠 경우:

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv
python3 -m venv ~/venv-unoq
source ~/venv-unoq/bin/activate
pip install --upgrade pip
pip install ai-edge-litert numpy
python3 -c "from ai_edge_litert.interpreter import Interpreter; print('LiteRT OK')"
sudo mkdir -p /opt/unoq-yolo/{models,labels,media,configs,logs}
sudo chown -R arduino:arduino /opt/unoq-yolo
```

(스크립트가 위와 동일한 작업 수행)

### 5-4. 자동 활성화 (선택)

매 SSH 진입 시 venv 자동 활성화하려면 `~/.bashrc` 마지막에:

```bash
echo '[ -f ~/venv-unoq/bin/activate ] && source ~/venv-unoq/bin/activate' >> ~/.bashrc
```

이렇게 하면 매번 `source ~/venv-unoq/bin/activate` 안 쳐도 자동.

## 6. 알려진 한계 및 후속 작업

### 6-1. 본 단계의 한계

- 설치 절차 검증 미완 — pip 설치 + venv + ai-edge-litert까지 실행해야 확정.
- Camera (`/dev/video*`) 존재 여부 미확인 — 별도 점검 필요.
- 카메라 드라이버 / Wayland 셋업 미확인 — 시각 출력 시 추가 작업 가능.

### 6-2. 후속 작업 진행 상태

| 단계 | 상태 |
|---|---|
| pip + venv + ai-edge-litert 설치 (`scripts/setup_device.sh` 또는 수동) | 완료 |
| 호스트에서 `yolov8n_int8.tflite` scp로 `/opt/unoq-yolo/models/`에 전송 | 완료 |
| `src/validate_model.py`에 3단 import 폴백 추가 (`ai_edge_litert` 우선) | 완료 |
| 디바이스 첫 latency 실측 (별도 문서 05) | 완료 |
| 디바이스 측정 결과 합격선 통과 (별도 문서 05) | 완료 |
