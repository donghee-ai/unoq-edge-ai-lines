# 실행 방법 Runbook — 호스트/디바이스 공용

> 본 문서는 자주 쓰는 명령을 모은 실용 가이드입니다.
> 본 프로젝트의 환경/스크립트/규약은 다른 문서(`00`~`07`)에 정의되어 있으며, 본 문서는 그것들을 "어떻게 쓰는가"에 집중합니다.

---

## 결정 요약 (한 화면)

| 작업 | 위치 | 명령 |
|---|---|---|
| 호스트 컨테이너 진입 | 호스트 WSL | `cd /mnt/c/Project/unoq-companion-robot && bash run.sh` |
| 컨테이너 나가기 | 컨테이너 | `exit` |
| 호스트에서 디바이스로 SSH | 호스트 WSL | `ssh arduino@192.168.0.45` |
| 디바이스 venv 활성화 | 디바이스 | `source ~/venv-unoq/bin/activate` |
| 호스트 추론 검증 | 컨테이너 | `python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite` |
| 디바이스 추론 검증 | 디바이스 (venv) | `python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite` |
| 디바이스에 파일 전송 | 호스트 WSL | `scp <src> arduino@192.168.0.45:<dst>` |
| 디바이스에서 파일 회수 | 호스트 WSL | `scp arduino@192.168.0.45:<src> <dst>` |

---

## 1. 환경별 역할 (다시 정리)

```
┌──────────────────────────────────────┐
│  호스트 WSL (Ubuntu 24.04)            │  git, ssh, scp, gh
│  /mnt/c/Project/unoq-companion-robot │
└──────────────────────────────────────┘
        │
        │ bash run.sh (15분 첫 빌드, 5초 재진입)
        ↓
┌──────────────────────────────────────┐
│  Docker 컨테이너 (Ubuntu 22.04)       │  ML 작업 전용
│  /work (마운트, 같은 폴더)             │  TF 2.19, Ultralytics
└──────────────────────────────────────┘

        │ scp (호스트에서 디바이스로)
        ↓
┌──────────────────────────────────────┐
│  UNO Q 디바이스 (192.168.0.45)        │  실행 환경
│  arduino@unoq-korea01                │  ai-edge-litert (venv)
│  /opt/unoq-yolo/                     │
└──────────────────────────────────────┘
```

규약:
- **git/SSH/scp**: 호스트 WSL에서만 (컨테이너 안에서 git은 user 분리 문제로 비권장)
- **모델 export/검증**: 컨테이너 안 (재현성 보장)
- **디바이스 추론**: 디바이스에서 (venv 활성화 필수)

---

## 2. 호스트 PC 작업 패턴

### 2-1. 처음 한 번 (저장소 클론 + 환경 빌드)

```bash
# WSL 셸 안에서
git clone https://github.com/donghee-ai/unoq-companion-robot.git
cd unoq-companion-robot
bash run.sh                  # 첫 빌드 약 15분
# → 컨테이너 진입 (dev@unoq-yolo-dev:/work$)
```

### 2-2. 일상 컨테이너 진입 (1회 빌드 후)

```bash
cd /mnt/c/Project/unoq-companion-robot
bash run.sh                  # 캐시된 이미지로 5초 진입
```

### 2-3. 환경 재빌드 (Dockerfile / requirements.txt 변경 후)

```bash
bash run.sh --rebuild        # 약 15분
```

### 2-4. 컨테이너 안에서 모델 export (1회만 또는 모델 갱신 시)

```bash
mkdir -p models
cd models
python -c "from ultralytics import YOLO; m=YOLO('yolov8n.pt'); \
  m.export(format='tflite', int8=True, imgsz=320, data='coco128.yaml')"
```

생성:
- `models/yolov8n_saved_model/yolov8n_int8.tflite` (3.19 MB) — 메인
- 기타 변종: float32, float16, integer_quant, full_integer_quant

### 2-5. 호스트에서 모델 검증 + latency 측정

```bash
cd /work
python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite
```

또는 JSON 저장:
```bash
python src/validate_model.py models/yolov8n_saved_model/yolov8n_int8.tflite \
  --json /work/benchmarks/host_$(date +%Y%m%d).json
```

---

## 3. UNO Q 디바이스 접속 패턴

### 3-1. SSH 접속

```bash
# 호스트 WSL에서 (컨테이너 아님)
ssh arduino@192.168.0.45
# 비번 입력 (한/영 영어 모드 확인!)
```

성공 시 `arduino@unoq-korea01:~$` 프롬프트.

### 3-2. venv 활성화 (디바이스 진입 직후 매번)

```bash
source ~/venv-unoq/bin/activate
# → 프롬프트 앞에 (venv-unoq) 표시되면 활성화 완료
```

(`~/.bashrc`에 자동 활성화 등록하면 매번 안 쳐도 됨 — `06_device_setup.md` Section 5-4 참조)

### 3-3. 디바이스 추론 실행

```bash
python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite
```

JSON 저장:
```bash
mkdir -p ~/benchmarks
python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite \
  --json ~/benchmarks/device_$(date +%Y%m%d).json
```

### 3-4. 디바이스 종료 (SSH 끊기)

```bash
exit       # 또는 Ctrl+D
```

---

## 4. 파일 전송 패턴

### 4-1. 호스트 → 디바이스 (scp)

```bash
# 호스트 WSL에서
cd /mnt/c/Project/unoq-companion-robot

# 모델 파일
scp models/yolov8n_saved_model/yolov8n_int8.tflite \
    arduino@192.168.0.45:/opt/unoq-yolo/models/

# 스크립트
scp src/validate_model.py arduino@192.168.0.45:~/

# 여러 파일/디렉토리
scp -r src/ arduino@192.168.0.45:~/code/
```

각 scp 호출마다 비번 입력 (한/영 영어 모드).

### 4-2. 디바이스 → 호스트 (결과 회수)

```bash
# 호스트 WSL에서
mkdir -p /mnt/c/Project/unoq-companion-robot/benchmarks
scp arduino@192.168.0.45:~/benchmarks/*.json \
    /mnt/c/Project/unoq-companion-robot/benchmarks/
```

### 4-3. 원격 실행 (SSH 안 들어가고 한 줄로)

```bash
ssh arduino@192.168.0.45 'source ~/venv-unoq/bin/activate && \
    python3 ~/validate_model.py /opt/unoq-yolo/models/yolov8n_int8.tflite'
```

결과가 호스트 셸에 그대로 출력됨. 길면 파일로:
```bash
ssh arduino@192.168.0.45 '...' > /tmp/device_out.log 2>&1
cat /tmp/device_out.log
```

---

## 5. 환경 변수 활용 (scripts/env.sh)

매번 IP/사용자명 타이핑 줄이려면:

```bash
# 호스트 WSL에서
cd /mnt/c/Project/unoq-companion-robot
source scripts/env.sh
# → UNO_Q_USER=arduino, UNO_Q_HOST=arduino.local 기본값 설정

# 본인 디바이스 값으로 override
export UNO_Q_HOST=192.168.0.45
source scripts/env.sh
```

그 다음 모든 명령에서:
```bash
ssh ${UNO_Q_USER}@${UNO_Q_HOST} 'whoami'
scp <file> ${UNO_Q_USER}@${UNO_Q_HOST}:/opt/unoq-yolo/models/
```

영구화는 `.env` 파일 또는 `~/.bashrc` — 자세한 건 `04_uno_q_env_setup.md`.

---

## 6. 디바이스 셋업 자동화 — `scripts/setup_device.sh`

신규 디바이스 또는 환경 재구축 시:

```bash
# 호스트 WSL에서 스크립트 전송 후 원격 실행
scp scripts/setup_device.sh arduino@192.168.0.45:~/
ssh arduino@192.168.0.45 'bash ~/setup_device.sh'
```

스크립트가 자동 수행:
1. apt: `python3-pip`, `python3-venv`
2. `~/venv-unoq` 생성
3. `pip install ai-edge-litert numpy`
4. import 동작 확인
5. `/opt/unoq-yolo/{...}` 디렉토리 생성

**idempotent** — 재실행 안전 (이미 있는 것은 skip).

---

## 7. Git 작업 패턴

호스트 WSL에서만 (컨테이너 아님):

```bash
cd /mnt/c/Project/unoq-companion-robot

# 변경 확인
git status

# 스테이징 + 커밋
git add <files>
git commit -m "Brief description"

# 푸시
git push
```

GitHub 인증은 첫 회 `gh auth login` 한 번만, 이후 자동.

---

## 8. 자주 만나는 함정 + 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 컨테이너 안에서 `git push` 인증 실패 | 컨테이너에 git config / auth 없음 | 호스트 WSL에서 git 작업 |
| `ssh: Permission denied` (즉시 거부) | 사용자명 틀림 | 디바이스 hostname ≠ username 주의. `arduino` 사용 |
| `ssh: Permission denied` (비번 입력 후) | 비번 틀림 또는 한/영 IME 한글 | **한/영 키로 영어 확인** 후 재시도 |
| `ModuleNotFoundError: ai_edge_litert` (디바이스) | venv 활성화 안 됨 | `source ~/venv-unoq/bin/activate` |
| 호스트 컨테이너에서 `python validate_model.py` 실패 | 컨테이너 진입 안 됨 | `bash run.sh`로 진입 먼저 |
| 디바이스 디스크 부족 | 큰 패키지 설치 시 | `df -h /` 확인, 불필요 파일 정리 |

---

## 9. 측정 수집 표준 워크플로우

본 작품의 측정 데이터는 다음 형식으로 일관 수집:

### 9-1. 측정 명령
```bash
# 디바이스에서
python3 ~/validate_model.py /opt/unoq-yolo/models/<MODEL_NAME>.tflite \
  --runs 50 --warmup 5 --threads 4 \
  --json ~/benchmarks/device_<MODEL>_<YYYYMMDD>.json
```

### 9-2. JSON 파일명 규칙
`<host|device>_<model_short_name>_<YYYYMMDD>.json`

예:
- `host_yolov8n_int8_20260623.json`
- `device_yolov8n_int8_20260623.json`
- `device_mediapipe_face_20260701.json` (향후)

### 9-3. 호스트로 회수 + git에 포함 여부
- 회수: `benchmarks/` 폴더로 (`.gitignore`에서 명시적으로 빼야 함)
- git 포함 여부: 검토 후 결정 (현재는 미포함)

---

## 10. 다음 작업 진입 (체크리스트)

본 단계까지 끝나면 다음 진입:

- [ ] `src/postprocess.py` 작성 (NMS + 박스 디코딩)
- [ ] 실제 이미지 추론 (`coco128/images/train2017/*.jpg` 사용)
- [ ] 박스 그려서 PNG 저장 (README 데모 자산)
- [ ] 호스트/디바이스 양쪽에서 end-to-end FPS 측정
- [ ] (향후) 카메라 입력 처리
- [ ] (향후) 얼굴 검출 모델로 전환 (또는 YOLO fine-tuning)
- [ ] (향후) MCU 연동 (LED, 모터)

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성 | 호스트/디바이스 셋업 + 첫 추론까지 완료 후, 실행 가이드 정리 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 대상 | 본인 + 향후 협업자 (멘토 포함) |
| 갱신 시점 | 새 자주-쓰는 명령 추가될 때마다 |
