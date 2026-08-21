# Calibration App 자동 배포 + 실행 스크립트
#
# 사용법:
#   1. UNO Q IP 확인 (라우터 또는 ADB 사용 시 `adb shell ip addr`)
#   2. 본 스크립트 같은 폴더(calibration/)에서 PowerShell 실행:
#        .\deploy.ps1 -UnoIP 192.168.0.45
#   3. SSH 비번 입력 (몇 번 물어봄)
#   4. 자동으로:
#       - 폴더 push (SCP)
#       - 기존 App 정지 (있다면)
#       - 새 App 시작 (빌드 + 업로드)
#       - 로그 표시
#
# 옵션:
#   -UnoIP <IP>      UNO Q IP (필수)
#   -User <name>     SSH 사용자 (기본: arduino)
#   -AppName <name>  App 이름 (기본: calibration)
#   -NoLogs          시작 후 로그 안 띄움

param(
    [Parameter(Mandatory=$true)]
    [string]$UnoIP,

    [string]$User = "arduino",
    [string]$AppName = "calibration",
    [switch]$NoLogs
)

$ErrorActionPreference = "Stop"

# 현재 스크립트 위치 = 배포할 소스 폴더
$LocalDir = $PSScriptRoot
$RemoteDir = "~/ArduinoApps/$AppName"
$Target = "${User}@${UnoIP}"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " Calibration App 배포 + 실행" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Source : $LocalDir"
Write-Host "  Target : $Target : $RemoteDir"
Write-Host "  App    : $AppName"
Write-Host ""

# 1. 원격 폴더 생성
Write-Host "[1/5] 원격 폴더 생성..." -ForegroundColor Yellow
ssh $Target "mkdir -p $RemoteDir"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ SSH 접속 실패. IP / 비번 / 네트워크 확인" -ForegroundColor Red
    exit 1
}

# 2. 파일 전송 (sketch + python + app.yaml)
Write-Host "[2/5] 파일 전송 (SCP)..." -ForegroundColor Yellow
scp -r "$LocalDir\app.yaml" "$LocalDir\README.md" "$LocalDir\sketch" "$LocalDir\python" "${Target}:${RemoteDir}/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ 파일 전송 실패" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ 전송 완료" -ForegroundColor Green

# 3. 기존 App 정지 (있으면)
Write-Host "[3/5] 기존 App 정지 (있다면)..." -ForegroundColor Yellow
ssh $Target "arduino-app-cli app stop $RemoteDir 2>/dev/null; true"

# 4. App 시작 — 빌드 + 업로드 자동
Write-Host "[4/5] App 시작 (빌드 + 업로드, 1~2분 소요)..." -ForegroundColor Yellow
ssh $Target "arduino-app-cli app start $RemoteDir"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ App 시작 실패 — 로그 확인:" -ForegroundColor Red
    ssh $Target "arduino-app-cli app logs $RemoteDir --tail 30"
    exit 1
}
Write-Host "  ✅ App 시작 완료" -ForegroundColor Green

# 5. 로그 보기 (선택)
if (-not $NoLogs) {
    Write-Host "[5/5] 로그 표시 (Ctrl+C로 종료, App은 계속 실행됨)" -ForegroundColor Yellow
    Write-Host ""
    ssh $Target "arduino-app-cli app logs $RemoteDir"
} else {
    Write-Host "[5/5] 로그 표시 건너뜀 (-NoLogs)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "수동 로그 명령:" -ForegroundColor Cyan
    Write-Host "  ssh $Target `"arduino-app-cli app logs $RemoteDir`""
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " 완료" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "정지하려면:" -ForegroundColor Yellow
Write-Host "  ssh $Target `"arduino-app-cli app stop $RemoteDir`""
Write-Host ""
