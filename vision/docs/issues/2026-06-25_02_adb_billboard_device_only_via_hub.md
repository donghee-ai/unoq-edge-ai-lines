# 2026-06-25 — ADB, USB 허브 경유 시 "Billboard Device"만 등록 (데이터 X)

## 증상
USB 구조: UNO Q ↔ USB 허브 ↔ PC + (허브에 카메라/마이크 같이 물림).

`usbipd list` 결과:
- 이전 (PC 직접 연결): BUSID 5-1, **2341:0078 "ADB Interface, USB 직렬 장치(COM5)"** ← ADB 정상
- 지금 (허브 경유): BUSID 5-1, **2f61:2404 "Billboard Device"** ← **데이터 인터페이스 미등록**

`adb devices`: 빈 목록.

## 원인
"Billboard Device" (VID 2f61) = USB-C Power Delivery 협상 시 등록되는 메타 장치. **실제 USB 데이터 인터페이스 (ADB / 시리얼) 미등록**.

후보 (확률 순):
1. **USB-C 케이블이 데이터 라인 미지원** (충전 전용 케이블, 같은 모양이라도 USB 2.0 D+/D- 핀 X)
2. 허브의 데이터 패스가 alt mode로 빠짐 (USB-C 허브 호환성)
3. UNO Q 측 ADB 모드 비활성 (가능성 낮음 — 이전 동작)

## 해결
보고 코앞 → SSH fallback으로 진행 (LAN 연결은 살아 있음, 이전 시연 검증 완료).

근본 해결 (보고 후):
1. PC에 직접 USB-C 연결 (검증됨)
2. 데이터 라인 지원 USB-C 케이블로 교체 ("USB 3.x" 또는 "10 Gbps" 표기)
3. powered USB 허브 (외부 전원 + USB-C 데이터 통과)

## 재발 방지
- 허브 사용 시 **데이터 라인 명시 케이블** + powered hub 필수
- 운영 환경 (허브 + 다중 디바이스)에서는 SSH가 더 안정적
- USB-C는 같은 모양이라도 데이터 지원 천차만별 — **항상 케이블 자체 검증** 필요
- 향후 운영 docs에 "허브 호환성" 절 추가

## 관련
- 이전 issue (허브 시 디바이스 자체 미인식): [`2026-06-25_01_adb_lost_when_through_hub.md`](2026-06-25_01_adb_lost_when_through_hub.md)
- ADB 셋업 history: [`../history/2026-06-25_02_adb_connection_established.md`](../history/2026-06-25_02_adb_connection_established.md)
