"""GPIO 버튼 watcher — sysfs (또는 libgpiod) 기반, daemon thread.

두 가지 백엔드 시도 (우선순위):

  1. **libgpiod** (권장, 커널 신규 인터페이스)
     - Q Linux/Debian 최신 배포판에서 지원
     - `python3-gpiod` 설치 후 `import gpiod`
     - line event (edge trigger) — 폴링 없음, CPU 절감

  2. **sysfs GPIO** (레거시, `/sys/class/gpio/`)
     - 커널 5.x 이후 deprecated 되나 여전히 동작
     - poll(2) 방식 — edge trigger
     - libgpiod 없을 때 fallback

Fallback fallback (없음):
  하드웨어 미준비 시 이 파일 import 만 되고 start() 호출 시 no-op (에러 없음).

동작:
  - Short press (< long_press_ms) → next_mode(current) 로 cycle push
  - Long press (>= long_press_ms) → Mode.IDLE (강제 STOP)

배선 (예):
  Vcc(3.3V) ─── button ─── GPIO pin ─── (pull-down 10kΩ) ─── GND
  → 눌리지 않은 상태: LOW / 눌린 상태: HIGH  (active_high=True)

  또는 (pull-up 방식):
  Vcc ─── (pull-up 10kΩ) ─── GPIO pin ─── button ─── GND
  → 눌리지 않은 상태: HIGH / 눌린 상태: LOW  (active_high=False)
"""
from __future__ import annotations

import os
import select
import threading
import time
from pathlib import Path
from typing import Optional

from mode_controller import Mode, ModeBus, next_mode

# libgpiod 시도
try:
    import gpiod
    _HAS_GPIOD = True
except ImportError:
    _HAS_GPIOD = False


class ButtonWatcher:
    """GPIO 버튼 → ModeBus."""

    def __init__(
        self,
        bus: ModeBus,
        chip: str = "gpiochip0",
        line: int = 17,
        active_high: bool = True,
        long_press_ms: float = 1000.0,
        debounce_ms: float = 50.0,
    ):
        self.bus = bus
        self.chip = chip
        self.line = line
        self.active_high = active_high
        self.long_press_ms = long_press_ms
        self.debounce_ms = debounce_ms

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._backend: str = "none"

        # sysfs 경로 (fallback)
        self._sysfs_export = "/sys/class/gpio/export"
        self._sysfs_unexport = "/sys/class/gpio/unexport"
        self._sysfs_gpio_dir: Optional[str] = None

        self.stats = {
            "short_press": 0,
            "long_press": 0,
            "errors": 0,
        }

    # === libgpiod backend ===

    def _try_libgpiod(self) -> bool:
        if not _HAS_GPIOD:
            return False
        try:
            chip = gpiod.Chip(self.chip)
            line = chip.get_line(self.line)
            line.request(
                consumer="unoq-kws-btn",
                type=gpiod.LINE_REQ_EV_BOTH_EDGES,
                # active_high 는 request flags 로 조절할 수도 있음 (bias 등)
            )
            self._gpiod_chip = chip
            self._gpiod_line = line
            self._backend = "libgpiod"
            return True
        except Exception as e:
            print(f"[button] libgpiod init failed: {e}")
            return False

    def _loop_libgpiod(self):
        pressed_start_ms: Optional[float] = None
        last_edge_ms: float = 0.0
        while not self._stop_evt.is_set():
            try:
                if not self._gpiod_line.event_wait(sec=0, nsec=200_000_000):
                    continue
                ev = self._gpiod_line.event_read()
                now_ms = time.perf_counter() * 1000.0
                if (now_ms - last_edge_ms) < self.debounce_ms:
                    continue
                last_edge_ms = now_ms
                is_rising = (ev.type == gpiod.LineEvent.RISING_EDGE)
                pressed = is_rising if self.active_high else (not is_rising)
                if pressed:
                    pressed_start_ms = now_ms
                else:
                    if pressed_start_ms is not None:
                        dur = now_ms - pressed_start_ms
                        pressed_start_ms = None
                        self._fire_event(dur)
            except Exception as e:
                self.stats["errors"] += 1
                print(f"[button] libgpiod loop error: {e}")
                time.sleep(0.1)

    # === sysfs backend ===

    def _try_sysfs(self) -> bool:
        try:
            gpio_dir = f"/sys/class/gpio/gpio{self.line}"
            if not Path(gpio_dir).exists():
                with open(self._sysfs_export, "w") as f:
                    f.write(str(self.line))
                time.sleep(0.1)
            with open(f"{gpio_dir}/direction", "w") as f:
                f.write("in")
            with open(f"{gpio_dir}/edge", "w") as f:
                f.write("both")
            self._sysfs_gpio_dir = gpio_dir
            self._backend = "sysfs"
            return True
        except Exception as e:
            print(f"[button] sysfs init failed: {e}")
            return False

    def _read_value(self) -> int:
        with open(f"{self._sysfs_gpio_dir}/value") as f:
            return int(f.read().strip())

    def _loop_sysfs(self):
        pressed_start_ms: Optional[float] = None
        last_edge_ms: float = 0.0
        value_path = f"{self._sysfs_gpio_dir}/value"
        try:
            fd = os.open(value_path, os.O_RDONLY | os.O_NONBLOCK)
        except Exception as e:
            print(f"[button] sysfs open failed: {e}")
            return
        poller = select.poll()
        poller.register(fd, select.POLLPRI | select.POLLERR)
        try:
            # 초기 상태 읽기 (polling 이 edge 만 트리거하므로 한 번 flush)
            os.lseek(fd, 0, os.SEEK_SET)
            os.read(fd, 8)
            while not self._stop_evt.is_set():
                events = poller.poll(200)  # 200ms timeout
                if not events:
                    continue
                os.lseek(fd, 0, os.SEEK_SET)
                raw = os.read(fd, 8).decode().strip()
                if not raw:
                    continue
                val = int(raw)
                now_ms = time.perf_counter() * 1000.0
                if (now_ms - last_edge_ms) < self.debounce_ms:
                    continue
                last_edge_ms = now_ms
                pressed = (val == 1) if self.active_high else (val == 0)
                if pressed:
                    pressed_start_ms = now_ms
                else:
                    if pressed_start_ms is not None:
                        dur = now_ms - pressed_start_ms
                        pressed_start_ms = None
                        self._fire_event(dur)
        finally:
            try:
                os.close(fd)
            except Exception:
                pass

    # === 공통 ===

    def _fire_event(self, duration_ms: float):
        if duration_ms >= self.long_press_ms:
            self.stats["long_press"] += 1
            self.bus.push(
                source="button",
                label="long_press",
                target_mode=Mode.IDLE,
            )
        else:
            self.stats["short_press"] += 1
            current = self.bus.get_mode()
            target = next_mode(current)
            self.bus.push(
                source="button",
                label="short_press",
                target_mode=target,
            )

    def start(self):
        if self._thread is not None:
            return
        if self._try_libgpiod():
            loop = self._loop_libgpiod
        elif self._try_sysfs():
            loop = self._loop_sysfs
        else:
            print("[button] no backend available — running as no-op")
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=loop, name="button-watcher", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._backend == "libgpiod":
            try:
                self._gpiod_line.release()
                self._gpiod_chip.close()
            except Exception:
                pass
        elif self._backend == "sysfs":
            # unexport (에러 무시 — 다음 실행에서 재사용)
            try:
                with open(self._sysfs_unexport, "w") as f:
                    f.write(str(self.line))
            except Exception:
                pass

    def snapshot(self) -> dict:
        return {
            "backend": self._backend,
            "chip": self.chip,
            "line": self.line,
            "active_high": self.active_high,
            "long_press_ms": self.long_press_ms,
            "stats": dict(self.stats),
        }


# === CLI 자기검증 ===

def _self_test():
    """실제 GPIO 없이도 import + 초기화 성공만 확인."""
    bus = ModeBus()
    w = ButtonWatcher(bus, line=17)
    print(f"libgpiod available: {_HAS_GPIOD}")
    print(f"module loaded, snapshot: {w.snapshot()}")


if __name__ == "__main__":
    _self_test()
