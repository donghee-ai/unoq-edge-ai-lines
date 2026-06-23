# UNO Q 접속 환경 변수 설정 가이드

> 본 문서는 `scripts/env.sh`의 사용법, 본인 환경 값을 등록하는 3가지 방법, 그리고 권장 방식을 정리합니다.
> 환경별 차이를 환경 변수로 분리하는 표준 패턴을 본 프로젝트에 적용한 결과입니다.

---

## 결정 요약 (한 화면)

| 항목 | 내용 |
|---|---|
| 메커니즘 | `scripts/env.sh`가 4개 환경 변수를 export. `${VAR:-default}` 문법으로 본인 값이 있으면 그걸 사용, 없으면 기본값 |
| 본 단계 (UNO Q 미연결) | 아무것도 안 함. env.sh 기본값(`arduino`, `arduino.local`) 그대로 둠 |
| UNO Q 연결 후 권장 등록 방법 | **방법 2: `.env` 파일** (영구, 프로젝트 단위) |
| 기본값 출처 | Arduino UNO Q 공식 문서 및 Edge Impulse 문서의 App Lab 초기 설정 관례 |

---

## 1. env.sh가 하는 일

`scripts/env.sh`는 4개의 환경 변수를 정의합니다.

| 변수 | 기본값 | 의미 |
|---|---|---|
| `UNO_Q_USER` | `arduino` | UNO Q SSH 사용자명 |
| `UNO_Q_HOST` | `arduino.local` | UNO Q 호스트명 또는 IP |
| `APP_ROOT` | `/opt/unoq-yolo` | UNO Q 측 앱 루트 디렉토리 |
| `HOST_TMP` | `/tmp/unoq-yolo` | 호스트 측 임시 작업 디렉토리 |

핵심 문법:
```bash
export UNO_Q_USER="${UNO_Q_USER:-arduino}"
```
- `${VAR:-default}` = "VAR가 이미 설정돼 있으면 그 값, 없으면 default"
- 따라서 본인이 다른 값을 export한 상태에서 `source scripts/env.sh`를 호출하면 본인 값이 유지됨

작동 흐름:
```text
[기본 경로]
source scripts/env.sh
   ↓
환경 변수 비어있음
   ↓
default(arduino, arduino.local 등)이 적용됨

[override 경로]
export UNO_Q_HOST=192.168.0.42
source scripts/env.sh
   ↓
환경 변수에 이미 값 존재
   ↓
기존 값(192.168.0.42) 유지됨
```

---

## 2. 본인 값 등록 방법 3가지

### 방법 1: 셸에 직접 export (1회용)

```bash
export UNO_Q_USER=danny
export UNO_Q_HOST=192.168.0.42
source scripts/env.sh
```

- 장점: 즉시 적용, 파일 작성 불필요
- 단점: 터미널 종료 시 사라짐
- 용도: 빠른 테스트, 임시 작업

### 방법 2: `.env` 파일 (영구, 프로젝트 단위) — 권장

```bash
cat > .env <<'EOF'
export UNO_Q_USER=danny
export UNO_Q_HOST=192.168.0.42
EOF
```

매 셸에서 사용:
```bash
source .env && source scripts/env.sh
```

- 장점: 본인 값이 파일로 보관됨, 프로젝트 폴더 내에서 응집
- 단점: 매 셸마다 두 번의 source 명령
- 주의: `.env`는 **git에 절대 커밋 X** (개인 환경 + 가끔 비밀 포함). `.gitignore`에 `.env` 명시 필수

### 방법 3: `~/.bashrc` 자동 적용

WSL의 `~/.bashrc` 파일 마지막에 export 명령 추가하면 새 셸 열 때마다 자동 적용:

```bash
cat >> ~/.bashrc <<'EOF'

# UNO Q 프로젝트 자동 환경 설정
export UNO_Q_USER=danny
export UNO_Q_HOST=192.168.0.42
EOF

source ~/.bashrc
```

- 장점: 가장 편함, 자동 적용
- 단점: 본인 컴퓨터에만 적용 (협업자와 공유 안 됨). 다른 프로젝트 작업 시에도 같은 변수가 살아있음 (드물게 충돌 가능)
- 용도: 본인 작업 환경 고정, 다른 프로젝트와 변수 이름 충돌 없을 때

---

## 3. 권장 진행 순서

| 단계 | 권장 방법 | 이유 |
|---|---|---|
| 지금 (UNO Q 미연결) | 아무것도 안 함 | env.sh 기본값으로 충분 |
| UNO Q 도착, 첫 연결 시도 | 방법 1 (export) | 빠르게 값 확인 |
| 작업 본격 시작 | 방법 2 (.env) | 표준, 프로젝트 응집, 다른 컴퓨터에서도 동일 패턴 |
| 본인 전용 컴퓨터에서 장기 작업 | 방법 3 (.bashrc) | 가장 편함 |

대부분의 실무 패턴은 **방법 2 (.env 파일)** 입니다. 다른 도구(Python `dotenv`, Docker `--env-file` 등)도 같은 .env 파일을 읽도록 표준화되어 있어 호환성 좋음.

---

## 4. UNO Q 사용자명 / IP 알아내는 법 (참고)

UNO Q 도착 후 다음 절차로 정보 확보:

```bash
# 1. App Lab 초기 설정 시 정한 사용자명 확인 (보통 'arduino')

# 2. 호스트명으로 IP 탐지
ping arduino.local
# 응답 있으면 그게 본인 보드. IP는 ping 출력에서 확인 가능

# 3. mDNS 안 되면 라우터 관리 페이지 또는 ARP로 확인
arp -a | grep -i arduino
```

---

## 5. 메커니즘 테스트 (UNO Q 없이도 가능)

env.sh의 override 패턴이 작동하는지만 확인:

```bash
cd /mnt/c/Project/unoq-companion-robot

# 기본값 확인
source scripts/env.sh
echo $UNO_Q_USER         # arduino

# Override 동작 확인
export UNO_Q_USER=testuser
source scripts/env.sh
echo $UNO_Q_USER         # testuser

# 원상복구
unset UNO_Q_USER
source scripts/env.sh
echo $UNO_Q_USER         # arduino
```

세 결과가 예상대로 나오면 메커니즘 정상.

---

## 6. 다른 도구와의 관계

같은 "환경 변수로 환경별 차이 처리" 패턴은 산업 표준이며 다음 도구들에서 동일 사상으로 작동:

| 도구 | 동일 패턴의 구현 |
|---|---|
| Python | `python-dotenv` 패키지 (`.env` 파일 자동 로드) |
| Node.js | `dotenv` 패키지 |
| Docker | `-e VAR=value` 또는 `--env-file .env` |
| GitHub Actions | `secrets` / `vars` 정의 |
| Kubernetes | `ConfigMap` / `Secret` |

향후 본 프로젝트가 Docker Compose나 CI로 확장될 때 동일 `.env`를 읽도록 가능.

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성 | `scripts/env.sh` 생성 후 사용법 별도 문서로 분리 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 관련 파일 | `scripts/env.sh` |
| 상위 규약 문서 | `danny/03_project_conventions.md` Section 1-1 |
| 적용 시점 | UNO Q 디바이스 연결 단계부터 (현 시점 미적용) |
