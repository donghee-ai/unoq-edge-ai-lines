#!/usr/bin/env bash
# UNO Q 디바이스 측 셋업 스크립트 (idempotent — 재실행 안전)
#
# 목적:
#   - pip + venv 설치
#   - ~/venv-unoq 가상환경 생성
#   - ai-edge-litert + numpy 설치
#   - /opt/unoq-yolo/{models,labels,media,configs,logs} 디렉토리 생성
#
# 사용 — 두 가지 방법:
#
#   방법 A: 호스트에서 스크립트 전송 후 디바이스에서 실행
#     scp scripts/setup_device.sh arduino@192.168.0.45:~/
#     ssh arduino@192.168.0.45 'bash ~/setup_device.sh'
#
#   방법 B: 이미 SSH 들어간 상태에서 직접 실행
#     # (호스트에서 한 번 전송 후) bash ~/setup_device.sh
#
# 전제 조건:
#   - UNO Q에 SSH로 로그인 가능
#   - sudo 권한 있는 사용자
#   - 인터넷 연결 (apt + pip 다운로드)
#   - 디스크 여유 약 200 MB

set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/unoq-yolo}"
VENV_DIR="${VENV_DIR:-$HOME/venv-unoq}"

echo "============================================================"
echo "UNO Q 디바이스 셋업"
echo "  사용자:    $(whoami)"
echo "  호스트:    $(hostname)"
echo "  Python:    $(python3 --version)"
echo "  venv 위치: $VENV_DIR"
echo "  앱 루트:   $APP_ROOT"
echo "============================================================"
echo ""

# === Phase 1: 시스템 패키지 (pip + venv) ===
echo "==> Phase 1: apt 패키지 (python3-pip, python3-venv)"
if python3 -m pip --version >/dev/null 2>&1; then
    echo "    pip 이미 설치됨, skip"
else
    sudo apt update
    sudo apt install -y python3-pip python3-venv
fi
echo ""

# === Phase 2: venv 생성 ===
echo "==> Phase 2: venv 생성 ($VENV_DIR)"
if [ -d "$VENV_DIR" ]; then
    echo "    venv 이미 존재, skip"
else
    python3 -m venv "$VENV_DIR"
fi
echo ""

# === Phase 3: Python 패키지 설치 ===
echo "==> Phase 3: ai-edge-litert + numpy 설치"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install ai-edge-litert numpy
echo ""

# === Phase 4: 동작 확인 ===
echo "==> Phase 4: import 동작 확인"
python3 -c "from ai_edge_litert.interpreter import Interpreter; print('    [OK] ai_edge_litert')"
python3 -c "import numpy; print('    [OK] numpy', numpy.__version__)"
echo ""

# === Phase 5: /opt/unoq-yolo 디렉토리 ===
echo "==> Phase 5: $APP_ROOT 디렉토리 구조 생성"
sudo mkdir -p "$APP_ROOT"/{models,labels,media,configs,logs}
sudo chown -R "$USER:$USER" "$APP_ROOT"
ls -la "$APP_ROOT"
echo ""

# === 완료 ===
echo "============================================================"
echo "셋업 완료"
echo ""
echo "다음 사용 시 venv 활성화:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "매 SSH 진입 시 자동 활성화 원하면 (선택):"
echo "  echo '[ -f $VENV_DIR/bin/activate ] && source $VENV_DIR/bin/activate' >> ~/.bashrc"
echo ""
echo "모델 파일 위치:"
echo "  $APP_ROOT/models/"
echo "============================================================"
