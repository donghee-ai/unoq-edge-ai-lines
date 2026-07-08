# Calibration App 정지 스크립트
#
# 사용법:
#   .\stop.ps1 -UnoIP 192.168.0.45

param(
    [Parameter(Mandatory=$true)]
    [string]$UnoIP,

    [string]$User = "arduino",
    [string]$AppName = "calibration"
)

$Target = "${User}@${UnoIP}"
$RemoteDir = "~/ArduinoApps/$AppName"

Write-Host ""
Write-Host "Calibration App 정지 중..." -ForegroundColor Yellow
ssh $Target "arduino-app-cli app stop $RemoteDir"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 정지 완료" -ForegroundColor Green
} else {
    Write-Host "❌ 정지 실패 (이미 정지 상태일 수 있음)" -ForegroundColor Red
}
Write-Host ""
