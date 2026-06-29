# 2026-06-25 — ADB 연결 확정 + Claude 디바이스 직접 접근 가능

## 시점
2026-06-25 (보고 직전, ASR 1차 PoC 시연 자료 준비 시점)

## 사건
사용자가 USB-C로 UNO Q를 Windows PC에 연결 + Arduino IDE 번들 ADB 활성화. Claude (Bash 도구)이 Arduino 번들 adb.exe로 디바이스에 비번 없이 직접 접근 확정.

## 배경
- 기존 워크플로우: SSH + 비번 (`arduino@192.168.0.45`) — Claude sandbox는 비번 prompt 차단으로 사용자가 매번 명령 복붙 + 비번 입력 부담
- ADB로 전환 시도 — 보고 직전 시간에 사용자가 USB 연결 + ADB 활성화
- Arduino IDE 번들 adb 발견 (`/c/Users/A/AppData/Local/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe`)

## 결과

### 확인된 사실
- **Device serial**: `1204329696`
- **adb shell 접근**: `arduino` 유저, 비번 X
- **uname**: `Linux unoq-korea01 7.0.0-g122c2c22d838 ... aarch64` (vision docs/04와 일치)
- **/opt/unoq-yolo/models/**: 4개 모델 파일 (yolov8n_int8.tflite, whisper_tiny_en.tflite, mel_filters.npz, tokenizer.json) 모두 존재
- **venv-unoq**: `/home/arduino/venv-unoq` + Python 3.13.5
- usbipd-win 설치되어 있으나 ADB는 Windows 측 직접 USB로 동작 → usbipd attach 불필요

### USB 디바이스 정보 (usbipd list)
- BUSID `5-1`, VID:PID **2341:0078** ("ADB Interface, USB 직렬 장치(COM5)")
- 2341 = Arduino, 0078 = UNO Q ADB Interface

### 변화 (이전 SSH → ADB)
| 작업 | 이전 (SSH) | 이후 (ADB) |
|---|---|---|
| 인증 | 비번 매번 입력 | 자동 (USB 인증) |
| Claude 자동 실행 | 불가 (sandbox 비번 prompt 차단) | **가능** |
| 명령 | `ssh arduino@... '...'` + 비번 | `adb shell '...'` |
| 파일 전송 | `scp` + 비번 | `adb push/pull` |
| 네트워크 의존 | 같은 LAN | USB 직접 |

### 즉시 가능 (Claude 자동)
- 디바이스 명령 1회 실행 (`adb shell`)
- 파일 전송 (push / pull)
- 프로세스 모니터링 (top, ps)
- ASR 오프라인 추론 (JFK wav, 마이크 X)
- 자료 회수 (JSON, JPEG, wav)

### 여전히 사용자 직접
- 브라우저 영상 확인 (`http://192.168.0.45:8080/`) — LAN/IP 기반, ADB와 무관
- 마이크 발화 (`--record N`) — 사용자가 실제 음성 입력 필요

## 다음 단계
- 보고 시연: 사용자(브라우저 + 마이크 발화) + Claude(자동 측정/회수) 협업 패턴
- 보고 후: ADB 셋업 docs 정리 (운영 표준 문서화)
- ADB 한계 발견 시 issues/ 기록

## 관련
- ASR 라인 동일 워크플로우 확장 가능: [`../../asr/docs/history/`](../../asr/docs/history/)
- 기존 SSH 워크플로우는 LAN 운영용으로 유지 (USB 분리 시 fallback)
- 어떤 도구로 ADB 활성화했는지 (Arduino IDE / Arduino App Lab) 추후 docs 정리 시 추가
