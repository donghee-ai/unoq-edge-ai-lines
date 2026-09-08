# GPIO 버튼 배선 — KWS 인터럽트 fallback

본 문서는 KWS 가 못 동작할 때 or **명확한 물리 인터럽트**를 원할 때 사용할 GPIO 버튼 배선 + 커널 인터페이스.

## 0. 사용처

- KWS 무반응 (마이크 미준비 / 노이즈 심함) 시 fallback
- 시연 중 확실한 인터럽트 (즉각 반응 보장)
- 조용한 환경에서 사용자가 발화하기 부담스러울 때

`--enable-button` 옵션으로 활성. KWS 와 병행 가능 (둘 다 켜져도 무관).

## 1. 필요 부품

| 부품 | 규격 | 수량 | 대체 |
|---|---|---|---|
| Tactile switch (푸시버튼) | SPST momentary | 1 | breadboard 용 아무 버튼 |
| 저항 | 10 kΩ | 1 | pull-down 용 |
| 점퍼선 | male-male 3개 | 3 | 브레드보드 배선 |
| 브레드보드 (선택) | 400 tie-point | 1 | 납땜 대신 |

총 원가: ~$1 (버튼 + 저항).

## 2. 배선도 (pull-down)

```
    3.3V (UNO Q pin)
     │
     └─── (버튼) ────┬─── GPIO 17 (예)
                     │
                    10 kΩ
                     │
                    GND
```

**동작**:
- 버튼 안 눌림: GPIO 17 = LOW (pull-down 이 GND 로 끌음)
- 버튼 눌림: GPIO 17 = HIGH (3.3V 로 연결)

코드에서 `--gpio-active-high true` (default) 설정.

## 2-1. 대안 배선 (pull-up)

```
    3.3V
     │
    10 kΩ
     │
     ├─── GPIO 17
     │
   (버튼)
     │
    GND
```

**동작 반전**:
- 버튼 안 눌림: HIGH
- 버튼 눌림: LOW

코드에서 `--gpio-active-high false`.

## 3. UNO Q GPIO 핀 선택

UNO Q QRB2210 은 SoM 에 여러 GPIO 노출. 헤더 매핑은 보드 datasheet 참조.

**주의**:
- 3.3V 로직 (5V 인가 X — 손상 위험)
- 특정 핀은 부팅 시 stringing 신호로 사용 (bootstrap) — 부팅 시점 pull 상태 주의
- pin `17` 은 예시 — 실제 핀 번호는 UNO Q pinout 확인 후 결정

디바이스에서 확인:
```bash
ssh arduino@192.168.0.45
sudo gpiodetect
sudo gpioinfo gpiochip0 | head -30
```

## 4. 커널 인터페이스

### 4-1. libgpiod (권장)

Ubuntu 20.04+ / Q Linux 최신 배포판 지원.

```bash
sudo apt install -y gpiod libgpiod-dev python3-libgpiod
```

파이썬 사용:
```bash
python3 -c "import gpiod; print(gpiod.__version__)"
```

권한 (root 없이 사용):
```bash
sudo usermod -aG gpio arduino
# 재로그인 필요
```

### 4-2. sysfs (레거시 fallback)

`button_watcher.py` 는 libgpiod 없으면 sysfs 자동 fallback.

```bash
# 수동 테스트 (line 17 예)
echo 17 | sudo tee /sys/class/gpio/export
echo in | sudo tee /sys/class/gpio/gpio17/direction
echo both | sudo tee /sys/class/gpio/gpio17/edge
cat /sys/class/gpio/gpio17/value
```

sysfs 는 커널 5.x 이후 deprecated — libgpiod 우선.

## 5. 배선 검증 (파이썬 없이)

```bash
ssh arduino@192.168.0.45

# libgpiod 방식 — 상태 모니터
sudo gpiomon -F "%c gpiochip0 %o %e" gpiochip0 17

# 버튼 누르고 뗄 때마다 line event 출력 기대
```

## 6. 파이썬 테스트

```bash
source ~/venv-unoq/bin/activate

# 단독 테스트 (Ctrl+C 로 종료)
python3 - <<'PY'
import sys, time
sys.path.insert(0, '/home/arduino/kws_test/scripts')
from mode_controller import ModeBus, Mode
from button_watcher import ButtonWatcher

bus = ModeBus(initial=Mode.IDLE)
btn = ButtonWatcher(bus, line=17, active_high=True, long_press_ms=1000)
btn.start()
print("눌러보세요 (Ctrl+C 종료)")
try:
    while True:
        time.sleep(0.1)
        ev = bus.poll()
        if ev:
            print(f"event: {ev.source} {ev.label} → mode={bus.get_mode().value}")
except KeyboardInterrupt:
    pass
finally:
    btn.stop()
    print("stats:", btn.snapshot())
PY
```

기대:
- Short press → "event: button short_press → mode=SQUAT" (cycle)
- Long press → "event: button long_press → mode=IDLE"

## 7. Pose 통합 실행

```bash
python3 ~/pose_test/scripts/infer_camera_pose_multimode.py \
    ~/pose_test/models/movenet_thunder_int8.tflite \
    --camera 0 --serve 8080 \
    --initial-mode SQUAT \
    --enable-button --gpio-line 17 --gpio-active-high \
    --gpio-long-press-ms 1000
```

## 8. 트러블슈팅

| 증상 | 점검 + 해결 |
|---|---|
| `Permission denied` on `/sys/class/gpio/export` | `sudo` 또는 `sudo usermod -aG gpio arduino` 후 재로그인 |
| libgpiod 없음 | `sudo apt install python3-libgpiod` (또는 pip 없이 apt 로만) |
| 버튼 누를 때마다 여러 이벤트 (bouncing) | `debounce_ms` 상향 (기본 50 → 100~150) |
| Long press 무반응 | `--gpio-long-press-ms 800` (사용자 체감 튜닝) |
| 반대로 반응 (안 눌러도 short_press) | `--gpio-active-high false` 로 반전 |
| Pull 저항 없음 → floating | 10 kΩ 추가 필수 (LOW/HIGH 판별 불안정) |
| 다른 line 번호로 시도 | `sudo gpioinfo gpiochip0` 로 free line 찾기 |

## 9. 대체안 — MCU 트리거 (미래)

STM32U585 통합 시 (v0.4.0):
- STM32 GPIO 로 버튼 감지 → UART/I2C 로 UNO Q 에 이벤트 전달
- UNO Q 측 `mode_controller` 는 소켓 or serial 리스너 하나 추가
- 배선 단순화 (모든 IO 를 MCU 로 통합)

본 사이클 (v0.3.0) 은 UNO Q 직접 GPIO 사용.

## 10. 관련

- 인터럽트 아키텍처: [`04_mode_interrupt_architecture.md`](04_mode_interrupt_architecture.md)
- Quickstart: [`02_quickstart_kws.md`](02_quickstart_kws.md)
- 버튼 코드: [`../scripts/button_watcher.py`](../scripts/button_watcher.py)
- Pose 통합: [`../../pose/scripts/infer_camera_pose_multimode.py`](../../pose/scripts/infer_camera_pose_multimode.py)
