#!/usr/bin/env bash
# UNO Q 접속 및 디바이스 경로 환경 변수
# (멘토 docs ko/01_source_checked_corrections.md의 안전한 명령 템플릿 채택)
#
# 사용 방법:
#   source scripts/env.sh                                # 기본값 적용
#   UNO_Q_HOST=192.168.1.42 source scripts/env.sh        # 본인 IP로 override
#   UNO_Q_USER=myname source scripts/env.sh              # 사용자명 override
#
# 현재 적용된 값 확인:
#   source scripts/env.sh && env | grep -E '^(UNO_Q_|APP_ROOT)'
#
# 별도 .env 파일 사용 시:
#   # .env 안에 export UNO_Q_HOST=... 작성
#   source .env && source scripts/env.sh

# UNO Q 디바이스 접속 변수
export UNO_Q_USER="${UNO_Q_USER:-arduino}"
export UNO_Q_HOST="${UNO_Q_HOST:-arduino.local}"

# UNO Q 디바이스 측 앱 루트 (멘토 docs 권고 디렉토리 구조)
#   하위: models/, labels/, media/, configs/, logs/
export APP_ROOT="${APP_ROOT:-/opt/unoq-yolo}"

# (참고) 호스트 측 임시 작업 디렉토리
export HOST_TMP="${HOST_TMP:-/tmp/unoq-yolo}"
