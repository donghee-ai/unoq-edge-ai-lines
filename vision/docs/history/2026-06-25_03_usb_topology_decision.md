# 2026-06-25 — USB 토폴로지 제약으로 운영 모드 분리 (ADB / SSH 이중 워크플로우)

## 시점
2026-06-25 (보고 직전, ADB 셋업 시도 직후)

## 사건
USB 허브를 통한 ADB + 카메라/마이크 동시 사용 시도 실패 ([`../issues/2026-06-25_01_adb_lost_when_through_hub.md`](../issues/2026-06-25_01_adb_lost_when_through_hub.md), [`../issues/2026-06-25_02_adb_billboard_device_only_via_hub.md`](../issues/2026-06-25_02_adb_billboard_device_only_via_hub.md)). 사용자 토폴로지 분석 결론으로 **시나리오별 모드 분리** 결정.

## 배경

USB 토폴로지 제약:
- 허브 메인 → PC 연결: 허브의 모든 디바이스 (UNO Q, 카메라, 마이크) 모두 PC의 USB device. UNO Q가 카메라/마이크 host 못 됨.
- 허브 메인 → UNO Q 연결: 카메라/마이크는 UNO Q의 device. PC와 USB 통신 끊김 (ADB 불가).

→ **카메라/마이크 활용 + PC ADB 동시 불가** (UNO Q USB-C 1포트 한계).

## 결정 — 모드 분리

| 모드 | 토폴로지 | 통신 | 사용 |
|---|---|---|---|
| **ADB** | PC ←USB-C→ UNO Q (직접 1:1) | `adb shell / push / pull` | Claude 자동화. 카메라/마이크 X 작업 (모델 검증 / 벤치 / wav 추론 / 자료 회수) |
| **SSH** | UNO Q ←USB→ (허브) ←카메라/마이크. PC는 LAN | `ssh arduino@192.168.0.45` | 카메라 실시간 + HTTP serve + 마이크 발화 시연 |

## 작업별 모드 매핑

| 작업 | 모드 |
|---|---|
| 벤치 (validate / benchmark / `--input wav`) | **ADB** |
| 자료 회수 (JSON / JPEG / wav / 로그) | **ADB** |
| 디바이스 의존성 설치 / 환경 점검 | **ADB** |
| Vision 카메라 + HTTP serve 시연 | **SSH** |
| ASR 마이크 녹음 + 인식 시연 | **SSH** |
| Soak test (장시간 카메라 + 마이크) | **SSH** |

## 결과
- 보고 시연: SSH 모드 그대로 진행 (이미 검증 완료)
- Claude 자동화 활용: ADB 모드로 사전/사후 측정 + 자료 회수
- 사용자 부담 줄이기 위해 **ADB 우선 사용 가능한 작업은 항상 ADB 선호**

## 다음 단계
- 보고 후: ADB 모드 docs 정리 (운영 표준 문서화)
- 향후 작업 시 사용자가 모드 명시: "ADB 모드"  vs "운영 모드 (SSH)"
- 메모리 갱신 — Claude이 작업 종류 따라 자동으로 ADB / SSH 선택

## 관련
- 허브 호환성 함정: [`../issues/2026-06-25_01_adb_lost_when_through_hub.md`](../issues/2026-06-25_01_adb_lost_when_through_hub.md), [`../issues/2026-06-25_02_adb_billboard_device_only_via_hub.md`](../issues/2026-06-25_02_adb_billboard_device_only_via_hub.md)
- ADB 셋업 마일스톤: [`2026-06-25_02_adb_connection_established.md`](2026-06-25_02_adb_connection_established.md)
- ASR 라인에도 동일 패턴 적용 검토 필요
