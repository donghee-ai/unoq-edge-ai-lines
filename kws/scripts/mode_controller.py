"""ModeBus — KWS/Button 이벤트를 pose main loop 로 전달하는 스레드 안전 이벤트 큐.

설계 원칙:
  - **비차단** : pose main loop 는 매 프레임 poll (queue.get_nowait) 하면 됨
  - **최신 우선**: 사용자가 여러 명령 빠르게 발화해도 마지막 명령만 유효
  - **debounce**: KWS 같은 라벨이 짧은 시간 안에 여러 번 감지되면 첫 번째만 반영
  - **관측 가능**: 최근 이벤트 log 유지 (디버그 + benchmark)

Mode set:
  IDLE      - 카운팅 없음, skeleton 만 오버레이
  SQUAT     - 스쿼트 카운터 (기존 squat_counter.SquatCounter)
  PUSHUP    - 팔굽혀펴기 카운터 (elbow 각도, 신규)
  SURVEIL   - 감시 모드 (person 검출 + 좌표 기록)

Event source:
  "kws"     - KWS worker (음성 명령)
  "button"  - GPIO button watcher
  "http"    - 외부 명령 (미구현, 확장 여지)

사용:
  from mode_controller import ModeBus, Mode

  bus = ModeBus(initial=Mode.IDLE)

  # worker thread 에서:
  bus.push(source="kws", label="Down", mapped_mode=Mode.SQUAT)

  # main loop 에서:
  ev = bus.poll()
  if ev:
      new_mode = ev.target_mode
      # ... reconfigure algorithm ...
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Mode(str, Enum):
    """헬스케어 봇 운영 모드."""
    IDLE = "IDLE"
    SQUAT = "SQUAT"
    PUSHUP = "PUSHUP"
    SURVEIL = "SURVEIL"


MODE_CYCLE = [Mode.IDLE, Mode.SQUAT, Mode.PUSHUP, Mode.SURVEIL]


def next_mode(current: Mode) -> Mode:
    """버튼 short-press 시 다음 모드 (cycle)."""
    try:
        idx = MODE_CYCLE.index(current)
    except ValueError:
        return Mode.IDLE
    return MODE_CYCLE[(idx + 1) % len(MODE_CYCLE)]


# KWS 라벨 → 모드 매핑 (12 클래스 DS-CNN 기준)
KWS_TO_MODE_12 = {
    "Down": Mode.SQUAT,       # 아래로 내려가는 운동
    "Up": Mode.PUSHUP,        # 위로 올리는 운동 (푸시업 상단)
    "Stop": Mode.IDLE,
    "Go": None,               # 현재 모드 유지 (카운팅 재개 신호)
    "Yes": None,              # 확인만 (모드 변경 없음)
    "No": Mode.IDLE,          # 취소 → IDLE
    "Left": Mode.SURVEIL,     # 감시 모드
    "Right": None,            # 예약
    "On": None,               # 예약 (HTTP serve on)
    "Off": Mode.IDLE,         # 예약 (HTTP serve off → IDLE)
}

# 4 클래스 MicroSpeech 매핑 (버튼과 augment)
KWS_TO_MODE_4 = {
    "yes": None,   # 확인만 (모드 후보 적용 신호 — main loop 가 처리)
    "no": Mode.IDLE,
}


@dataclass
class ModeEvent:
    """모드 전환 이벤트 하나."""
    source: str                       # "kws" | "button" | "http"
    label: str                        # 원본 라벨 (KWS 라벨 or "short_press" 등)
    target_mode: Optional[Mode]       # None = 모드 변경 없음 (Go/Yes 등)
    confidence: Optional[float] = None
    timestamp_ms: float = field(default_factory=lambda: time.perf_counter() * 1000.0)


class ModeBus:
    """스레드 안전 이벤트 버스 + 현재 모드 상태."""

    def __init__(
        self,
        initial: Mode = Mode.IDLE,
        debounce_ms: float = 800.0,
        history_size: int = 32,
    ):
        self.current_mode: Mode = initial
        self.debounce_ms = debounce_ms
        self._q: "queue.Queue[ModeEvent]" = queue.Queue(maxsize=16)
        self._lock = threading.Lock()
        self._last_by_label: dict[str, float] = {}      # 라벨별 마지막 감지 시각
        self._history: list[ModeEvent] = []
        self._history_size = history_size

        # 통계 (벤치마크 용)
        self.stats = {
            "kws_events": 0,
            "button_events": 0,
            "mode_switches": 0,
            "debounced": 0,
        }

    def push(
        self,
        source: str,
        label: str,
        target_mode: Optional[Mode],
        confidence: Optional[float] = None,
    ) -> bool:
        """이벤트 push. debounce 통과 시 True 반환.

        같은 label 이 debounce_ms 안에 다시 오면 무시 (예: KWS 가 같은 프레임에서 3연속 감지).
        """
        now_ms = time.perf_counter() * 1000.0
        with self._lock:
            last = self._last_by_label.get(label)
            if last is not None and (now_ms - last) < self.debounce_ms:
                self.stats["debounced"] += 1
                return False
            self._last_by_label[label] = now_ms

            ev = ModeEvent(
                source=source,
                label=label,
                target_mode=target_mode,
                confidence=confidence,
                timestamp_ms=now_ms,
            )
            self._history.append(ev)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]

            if source == "kws":
                self.stats["kws_events"] += 1
            elif source == "button":
                self.stats["button_events"] += 1

        # 큐 full 이면 오래된 것 버리고 덮어쓰기
        try:
            self._q.put_nowait(ev)
        except queue.Full:
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            self._q.put_nowait(ev)
        return True

    def poll(self) -> Optional[ModeEvent]:
        """pose main loop 에서 매 프레임 호출. 이벤트 없으면 None."""
        try:
            ev = self._q.get_nowait()
        except queue.Empty:
            return None
        # 모드 갱신
        if ev.target_mode is not None:
            with self._lock:
                if ev.target_mode != self.current_mode:
                    self.stats["mode_switches"] += 1
                    self.current_mode = ev.target_mode
        return ev

    def get_mode(self) -> Mode:
        with self._lock:
            return self.current_mode

    def set_mode(self, mode: Mode) -> None:
        """직접 모드 설정 (초기화 or 외부 CLI 명령)."""
        with self._lock:
            if mode != self.current_mode:
                self.stats["mode_switches"] += 1
                self.current_mode = mode

    def snapshot(self) -> dict:
        """벤치마크/HTTP JSON 용 스냅샷."""
        with self._lock:
            return {
                "current_mode": self.current_mode.value,
                "stats": dict(self.stats),
                "recent_events": [
                    {
                        "source": e.source,
                        "label": e.label,
                        "target_mode": e.target_mode.value if e.target_mode else None,
                        "confidence": round(e.confidence, 3) if e.confidence else None,
                        "t_ms": round(e.timestamp_ms, 1),
                    }
                    for e in self._history[-8:]
                ],
            }


# === CLI 자기검증 ===

def _self_test():
    bus = ModeBus(initial=Mode.IDLE, debounce_ms=100)

    print("Initial:", bus.get_mode())

    ok = bus.push("kws", "Down", Mode.SQUAT, confidence=0.87)
    print(f"push Down → {ok}, mode={bus.get_mode()}")

    ev = bus.poll()
    print(f"poll: {ev}")
    print(f"after poll mode: {bus.get_mode()}")

    # debounce 검증 (같은 라벨 100ms 이내 push)
    ok1 = bus.push("kws", "Up", Mode.PUSHUP)
    ok2 = bus.push("kws", "Up", Mode.PUSHUP)
    print(f"push Up (x2): {ok1}, {ok2}  (두 번째는 debounce → False 기대)")

    print("Cycle:")
    m = Mode.IDLE
    for _ in range(5):
        m = next_mode(m)
        print(f"  → {m}")

    print("Snapshot:", bus.snapshot())


if __name__ == "__main__":
    _self_test()
