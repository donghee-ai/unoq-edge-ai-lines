# 2026-06-25 — ADB 연결, USB 허브 경유 시 디바이스 인식 X

## 증상
PC에 직접 연결 시 ADB OK (`1204329696	device`). USB 허브에 옮겨 물리면 디바이스 자체가 Windows usbipd list에서 사라짐 (BUSID 5-1, VID:PID 2341:0078 "ADB Interface" 미인식). `adb devices` 빈 목록 출력.

## 원인 (후보, 미확정)
- 허브 전력 부족 (UNO Q + 카메라 + 마이크 동시 USB 부담 큼)
- 허브가 ADB 다중 인터페이스 enumeration 실패
- USB-C 케이블이 데이터 전송 미지원 (충전 전용)
- 허브 포트 손상

## 해결
보고 코앞 시간 압박 → 가장 확실한 방법:
1. **허브 빼고 PC에 직접 연결** (이전 동작 확정됨)
2. 또는 SSH fallback (`ssh arduino@192.168.0.45`) — LAN 연결 살아 있으면

## 재발 방지
- ADB 안정성 필요한 작업은 **PC 직접 연결** 또는 **powered hub** 사용
- 운영 환경(허브 다중 디바이스)에서는 SSH가 더 안정적
- 향후 ADB 셋업 docs 정리 시 "허브 호환성 점검" 절 추가

## 관련
- ADB 셋업 history: [`../history/2026-06-25_02_adb_connection_established.md`](../history/2026-06-25_02_adb_connection_established.md)
- 진단 명령:
  ```
  /c/Program\ Files/usbipd-win/usbipd list | grep -E "2341|ADB"
  /c/Users/A/AppData/Local/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe devices
  ```
