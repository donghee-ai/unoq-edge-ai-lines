# Servo Calibration — 서보 가운데 정렬

본 폴더는 본 작업 PTZ 조립 전에 1회 실행하는 calibration utility. SG90 PAN/TILT 서보를 90° 중립으로 강제 정렬한 후 horn + 기어를 끼우게 함.

## 사용법

1. UNO Q에 SG90 ×2 연결 — [§ 배선](#배선) 참조
2. 본 App 업로드:

   ```bash
   ssh arduino@<UNO_Q_IP> 'mkdir -p ~/ArduinoApps/servo-cal'
   scp -r c:\Project\unoq-companion-robot\pose\ptz\calibration\* arduino@<UNO_Q_IP>:~/ArduinoApps/servo-cal/
   ssh arduino@<UNO_Q_IP> 'arduino-app-cli app start ~/ArduinoApps/servo-cal'
   ```

3. Serial Monitor 115200 baud 열어 상태 메시지 확인
4. 서보가 90°에 도달하면 → horn 끼움 → 자루나사 잠금 → 기어 결합
5. 끝나면 본 작품 sketch (`../sketch/`)로 다시 업로드

## 배선

| 서보 wire | 색상 (일반) | UNO Q 핀 |
|---|---|---|
| Pan signal | 주황/노랑 | **D9** |
| Pan VCC | 빨강 | 5V |
| Pan GND | 갈색/검정 | GND |
| Tilt signal | 주황/노랑 | **D10** |
| Tilt VCC | 빨강 | 5V |
| Tilt GND | 갈색/검정 | GND |

## Serial 명령 (선택, 미세 조정용)

| 입력 | 동작 |
|---|---|
| `+` | 두 서보 +1° |
| `-` | 두 서보 -1° |
| `p+` / `p-` | PAN 서보만 ±1° |
| `t+` / `t-` | TILT 서보만 ±1° |
| `c` | 둘 다 90° 복귀 |
| `s` | 현재 각도 출력 |

## 관련

- 본 작품 PTZ sketch: [`../sketch/`](../sketch/) — calibration 끝나면 이걸로 교체
- 조립 가이드: [`../assembly_guide.html`](../assembly_guide.html)
