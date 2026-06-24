# 프로젝트 코딩 및 운영 규약 - Arduino UNO Q 교감로봇

> 본 문서는 본 프로젝트의 코드/명령어/배포/문서 작성 규약을 한 곳에 모아둡니다.
> 임베디드 AI 프로젝트에서 흔히 권장되는 패턴들을 본 프로젝트의 정식 규약으로 채택한 결과입니다.

---

## 결정 요약 (한 화면)

| 영역 | 규약 | 채택 상태 |
|---|---|---|
| 명령어 사용자 | `<UNO_Q_USER>` 변수, 기본 `arduino` | 채택 (UNO Q 연결 단계에서 적용) |
| 디바이스 디렉토리 | `/opt/unoq-yolo/{models,labels,media,configs,logs}` | 채택 (배포 단계에서 적용) |
| 보안 | `setenforce 0` 제품 이미지에서 제거 | 채택 |
| 모델 출처 표현 | AI Hub는 "소스 후보", 실행은 TFLite 로컬 검증 | 적용 중 |
| 라이선스 | 모든 모델/라이브러리의 라이선스 명시 | 적용 중 |
| 추론 메타데이터 | q-offsets/q-scales hard-code 금지, `get_input_details()` 자동 추출 | 코드 작성 시 적용 |
| GPU delegate | CPU 기본, GPU optional feature flag | 코드 설계 시 적용 |
| 성능 기대치 | 30 FPS hard requirement 잡지 않음. 8~15 FPS 목표 | 적용 중 |

---

## 1. 명령어 및 스크립트 규약

### 1-1. UNO Q 접속 변수 표준화

UNO Q에 접속하는 모든 명령은 사용자명/호스트를 하드코딩하지 않고 환경 변수로 처리합니다.

**구현**: 프로젝트 루트의 `scripts/env.sh` 파일에 기본값 정의. UNO Q 관련 작업 전 source.

정의된 변수:

| 변수 | 기본값 | 의미 |
|---|---|---|
| `UNO_Q_USER` | `arduino` | UNO Q SSH 사용자 (Arduino App Lab 초기 설정 관례) |
| `UNO_Q_HOST` | `arduino.local` | UNO Q 호스트명/IP |
| `APP_ROOT` | `/opt/unoq-yolo` | UNO Q 측 앱 루트 디렉토리 |
| `HOST_TMP` | `/tmp/unoq-yolo` | 호스트 측 임시 작업 디렉토리 |

기본값 출처: Arduino UNO Q 공식 문서 + Edge Impulse 문서의 App Lab 초기 설정 관례 (`UNO_Q_USER=arduino`). 실제 사용자명이 다르면 본인 값으로 override.

#### Override 메커니즘

핵심 문법:

```bash
export UNO_Q_USER="${UNO_Q_USER:-arduino}"
```

`${VAR:-default}`는 "VAR가 이미 설정돼 있으면 그 값, 없으면 default". 즉 본인 값을 미리 export한 상태에서 `source scripts/env.sh` 호출하면 본인 값 유지.

#### 본인 값 등록 3가지 방법

| 방법 | 명령 | 장점 | 단점 |
|---|---|---|---|
| 1. 1회용 export | `export UNO_Q_HOST=192.168.0.42; source scripts/env.sh` | 즉시 적용 | 터미널 종료 시 사라짐 |
| 2. `.env` 파일 (권장) | `echo 'export UNO_Q_HOST=192.168.0.42' > .env` → `source .env && source scripts/env.sh` | 영구, 프로젝트 단위 응집 | 매 셸마다 두 번 source. `.gitignore`에 `.env` 필수 |
| 3. `~/.bashrc` | WSL `~/.bashrc` 마지막에 `export UNO_Q_HOST=192.168.0.42` 추가 | 가장 편함, 자동 적용 | 본인 컴퓨터에만 적용. 다른 프로젝트와 변수 이름 충돌 가능 |

권장: 작업 본격 시작 시 **방법 2 (.env 파일)** — Python `dotenv`, Docker `--env-file` 등 다른 도구와도 같은 표준.

사용 예:

```bash
source scripts/env.sh
ssh ${UNO_Q_USER}@${UNO_Q_HOST} "ls ${APP_ROOT}/models"
scp model.tflite ${UNO_Q_USER}@${UNO_Q_HOST}:${APP_ROOT}/models/
```

### 1-2. 셸 스크립트 안전 기본값

새로 작성하는 `.sh` 스크립트는 다음 헤더로 시작:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

이유:

- `set -e`: 명령 실패 시 즉시 중단
- `set -u`: 미정의 변수 참조 시 에러
- `set -o pipefail`: 파이프 중간 명령 실패도 감지

---

## 2. 디바이스 디렉토리 구조

### 2-1. UNO Q 측 표준 트리

`/opt/` 루트에 파일을 흩지 않고 다음 구조 사용:

```text
/opt/unoq-yolo/
├── models/          (.tflite, .onnx 등 모델 파일)
├── labels/          (클래스 라벨 텍스트)
├── media/           (테스트 비디오, 이미지)
├── configs/         (JSON, YAML 설정 파일)
└── logs/            (앱 실행 로그, 벤치마크 결과)
```

소유권: `${UNO_Q_USER}` 유저 단독 소유
권한: 디렉토리 `755`, 파일 `644`, 비밀 파일 `600`

### 2-2. 초기 셋업 명령

```bash
ssh ${UNO_Q_USER}@${UNO_Q_HOST} \
  "sudo mkdir -p ${APP_ROOT}/{models,labels,media,configs,logs} && \
   sudo chown -R ${UNO_Q_USER}:${UNO_Q_USER} ${APP_ROOT}"
```

### 2-3. 임시 파일

`/opt`와 `/tmp`는 같은 "흩뿌리는 곳"이 아닙니다 — **각각 의미가 다르며 정리 의무도 다름**.

| 경로 | 의미 | 영속성 | 정리 의무 |
|---|---|---|---|
| `/opt/unoq-yolo/` | 본 앱의 영구 자산 | 영구 | **필수 — 구조화 엄격** |
| `/tmp/` | 일시 작업 공간 | 일시 (재부팅 시 사라짐 가능) | **약함 — 시스템 자동 정리** |

규약:

- 임시 파일/실험 출력은 `/tmp/unoq-yolo/` 하위에 둠
  - 시스템이 자동 정리하므로 영구성을 가정하지 않음
  - 그러나 본인 프로젝트 이름의 서브디렉토리에 모아 두어 작업 중 추적 가능
- 디버그 출력은 날짜/실험명으로 더 세분: `/tmp/unoq-yolo/debug-YYYY-MM-DD/`, `/tmp/unoq-yolo/bench-001/`
- `/tmp/` 루트에 파일 직접 두지 않음 (다른 프로세스/사용자와 섞임)
- `/opt/` 루트에는 절대 임시 파일 두지 않음 (영구 자산 디렉토리)

한 줄 원칙: **"어디에 두든 본인 프로젝트 이름 들어간 서브디렉토리 안. `/opt`는 영구 자산, `/tmp`는 일시 작업."**

---

## 3. 보안 규약 (개발/제품 분리)

### 3-1. `setenforce 0` 사용 제한

일부 공개 자료나 예제 코드에서 `setenforce 0`이 사용되는 경우가 있으나, 본 프로젝트에서는:

- **개발 환경 (본인 책상)**: 부득이한 경우에만 일시 사용, 매번 수동 입력
- **제품/배포 이미지**: 절대 사용 금지. 원인 권한/SELinux 정책을 정확히 수정

### 3-2. 비밀 관리

- SSH 비밀번호 로그인 비활성, SSH key 사용
- API 토큰/패스워드는 git 저장소에 절대 커밋 금지
- 비밀 파일은 `${APP_ROOT}/configs/secrets.env` 등 단일 위치, 권한 `600`
- `.gitignore`에 `*.env`, `secrets.*` 명시

### 3-3. 사용자 비밀번호 변경

UNO Q의 기본 비밀번호는 첫 접속 시 즉시 변경.

---

## 4. 모델 및 라이선스 규약

### 4-1. 모델 도입 절차

새 모델을 본 프로젝트에 도입할 때 다음을 `01_model_selection_log.md`에 기록:

- 모델 이름 및 버전
- 라이선스
- 데이터셋 라이선스 (학습에 사용된 경우)
- 채택 사유
- 알려진 한계

### 4-2. 라이선스 처리

| 라이선스 | 처리 |
|---|---|
| Apache-2.0, MIT, BSD | 상업 배포 자유, 본 작품에 우선 검토 |
| AGPL-3.0 (예: YOLOv8) | **본 작품 시연 단계에 한정 사용**. 상업/공개 배포 전 Ultralytics 상용 라이선스 또는 대체 모델로 전환 검토 |
| GPL-3.0 | 동일 처리 |
| Custom / Proprietary | 사전에 사용 범위 확인 |

### 4-3. AI Hub 표현 규약

- "AI Hub에서 다운로드함" 같은 단정적 표현 지양
- 정확한 표현: "AI Hub에서 export 시도하였으나 QRB2210 미지원 확인, 따라서 [대체 경로] 사용" 등 의사결정 흐름 명시
- 출처/한계/대안을 함께 적는 정확성 원칙

---

## 5. 추론 코드 규약

### 5-1. 메타데이터 자동 추출

q-offsets, q-scales, input shape, output shape 등 모델 메타데이터는 **절대 코드에 hard-code 하지 않음**.

```python
# 금지
SCALE = 3.093529462814331
OFFSET = 21.0

# 권장
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
scale, offset = input_details[0]['quantization']
```

이유: 모델 파일마다 quantization 값이 다를 수 있어, hard-code 시 모델 교체할 때마다 코드 수정 필요.

### 5-2. 후처리 분리

raw 모델 출력은 그대로 사용하지 않고, 다음 단계로 분리된 모듈에서 처리:

1. dequantize (필요 시)
2. reshape/transpose
3. confidence threshold
4. class filter
5. coordinate scaling (입력 해상도 → 원본 해상도)
6. NMS
7. class label mapping

해당 모듈: `src/postprocess.py` (예정)

### 5-3. GPU delegate 정책

```python
# 권장 인터페이스
def load_interpreter(model_path, num_threads=4, enable_gpu=False):
    if enable_gpu:
        try:
            # GPU delegate 시도
            ...
        except Exception:
            # 명시적 fallback (silent 금지)
            log.warning("GPU delegate failed, falling back to CPU")
    # CPU 기본 경로
    ...
```

원칙:

- **CPU가 기본**: GPU는 명시적 opt-in
- **silent fail 금지**: GPU delegate 실패 시 로그로 명확히 알림
- **fallback은 fail-safe**: GPU 실패해도 CPU로 동작은 보장

---

## 6. 성능 기대치 규약

### 6-1. 목표 FPS

본 프로젝트는 30 FPS를 hard requirement로 잡지 않습니다.

| 단계 | 목표 |
|---|---|
| 1차 PoC | 5~8 FPS (작동 확인) |
| 2차 시연 | 8~15 FPS (자연스러운 인터랙션) |
| 욕심 | 15+ FPS (부드러움) |

### 6-2. 부족 시 대응 순서

표준 최적화 순서:

1. 입력 해상도 축소 (320 → 256 → 192)
2. 더 작은 모델 (n → s 만 → 그보다 작은 변종)
3. frame skipping
4. ROI crop
5. event-driven inference
6. (마지막) 하드웨어 상향

### 6-3. 측정 표준

성능은 다음 지표로 일관 측정/보고:

- latency p50, p95 (ms)
- FPS mean
- max RSS (MB)
- max temperature (°C)

JSON 포맷은 본 프로젝트 벤치마크 문서에서 별도 정의.

---

## 7. 문서 작성 규약

### 7-1. 문서 디렉토리

- 본 프로젝트 자체 문서는 모두 `docs/` 폴더에 작성
- 멘토/외부 자료의 한국어 정리는 `docs/mentor/` 하위에 보관 (외부 공개 X)
- 외부 자료/참고 자료는 본 저장소에 직접 포함하지 않음 (필요 시 링크로 참조)

### 7-2. 파일명

- `NN_제목.md` 형식 (NN은 2자리 숫자)
- 시간순으로 번호 부여 (`00_`, `01_`, ...)
- 영문 소문자 + 언더스코어

### 7-3. 의사결정 문서 구조

의사결정을 다루는 문서(`01_model_selection_log.md` 등)는 다음 섹션 필수:

- 결정 요약 (한 화면 표)
- 채택 근거
- 알려진 한계 / 위험
- 변경 이력

### 7-4. 사실/추측 분리

본인이 직접 검증한 내용과 외부 출처 인용을 구분:

- 검증: "본 환경에서 측정 결과 X 확인"
- 인용: "[출처 URL]에 따르면 ..."
- 추측: "...일 가능성 높음 (실측 필요)"

### 7-5. 표 우선

본문 산문은 최소화, 가능하면 표/코드 블록으로 표현.

---

## 8. Git 및 협업 규약

### 8-1. 커밋 메시지

- 짧은 한 줄 요약 + 빈 줄 + 상세 (필요 시)
- 영문 또는 한국어 통일 (프로젝트 시작 시점에 결정 후 일관 유지)

### 8-2. `.gitignore` 기본 제외

- `*.tflite`, `*.pt`, `*.onnx` 등 모델 파일 (별도 배포 채널)
- `datasets/` (auto-download되는 학습 데이터)
- `.env`, `secrets.*` (비밀)
- `__pycache__/`, `.venv/`, IDE 임시 파일

### 8-3. 모델/대용량 파일

git에 커밋하지 않고, 다운로드 스크립트(`scripts/download_models.sh`)로 재현. 모델 source URL은 `01_model_selection_log.md`의 관련 링크 섹션에서 관리.

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성 | 임베디드 AI 프로젝트 권장 사항을 본 프로젝트 규약으로 채택 |
| 2026-06-23 | Section 2-3 보완 | `/opt`와 `/tmp`의 의미 차이 + 임시 파일도 프로젝트 서브디렉토리 안에 두기 명시 |
| 2026-06-23 | Section 1-1 구현 반영 | `scripts/env.sh` 파일 생성. 변수 표 형식으로 정리 |
| 2026-06-23 | Section 1-1에 04 (env.sh 사용법 가이드) 흡수 — override 메커니즘 + 본인 값 등록 3방법 통합 | 04 통합 / 중복 정리 |
| 2026-06-23 | Section 7-1 `danny/` → `docs/` (폴더명 변경) + `docs/mentor/` 명시 | 폴더 리네이밍 반영 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 적용 범위 | 본 프로젝트 전체 (`C:\Project\unoq-companion-robot\`) |
| 갱신 주기 | 새 규약 추가/변경 시 즉시 |
| 우선순위 | 본 문서의 규약이 코드/스크립트와 충돌할 경우, 본 문서 우선 (코드를 본 문서에 맞춰 수정) |
