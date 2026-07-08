"""팔굽혀펴기 카운터 — 팔꿈치 각도 시계열 → rep 카운팅 상태 머신.

squat_counter.py 와 대칭 구조:
  UP(팔 폄, elbow > up_th) ↔ DOWN(굽힘, elbow < down_th)
  UP → DOWN → UP 한 사이클 = 1 rep.

기본 임계 (푸시업 표준):
  down_th = 90°   (팔꿈치 굽힘 표준)
  up_th   = 160°  (팔 폄 hysteresis)

pick_angle 은 squat_counter 것 재활용 가능.
"""
from dataclasses import dataclass
from typing import Optional, Tuple
import time


@dataclass
class PushupCounter:
    down_th: float = 90.0
    up_th: float = 160.0
    min_dwell_ms: float = 200.0

    state: str = "UP"
    reps: int = 0
    last_transition_ms: float = 0.0
    min_angle_in_down: Optional[float] = None

    deepest_overall: Optional[float] = None
    last_rep_min_angle: Optional[float] = None

    def update(self, angle_deg: Optional[float], now_ms: Optional[float] = None) -> Optional[Tuple[str, int, float]]:
        if angle_deg is None:
            return None
        if now_ms is None:
            now_ms = time.perf_counter() * 1000.0

        if self.state == "UP":
            if angle_deg < self.down_th and (now_ms - self.last_transition_ms) >= self.min_dwell_ms:
                self.state = "DOWN"
                self.last_transition_ms = now_ms
                self.min_angle_in_down = angle_deg
            return None

        # DOWN
        if self.min_angle_in_down is None or angle_deg < self.min_angle_in_down:
            self.min_angle_in_down = angle_deg
            if self.deepest_overall is None or angle_deg < self.deepest_overall:
                self.deepest_overall = angle_deg

        if angle_deg > self.up_th and (now_ms - self.last_transition_ms) >= self.min_dwell_ms:
            self.state = "UP"
            self.last_transition_ms = now_ms
            self.reps += 1
            self.last_rep_min_angle = self.min_angle_in_down
            min_now = self.min_angle_in_down if self.min_angle_in_down is not None else angle_deg
            self.min_angle_in_down = None
            return ("REP", self.reps, min_now)
        return None

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "reps": self.reps,
            "deepest_overall_deg": round(self.deepest_overall, 1) if self.deepest_overall is not None else None,
            "last_rep_min_deg": round(self.last_rep_min_angle, 1) if self.last_rep_min_angle is not None else None,
            "current_down_min_deg": round(self.min_angle_in_down, 1) if self.min_angle_in_down is not None else None,
            "thresholds_deg": {"down": self.down_th, "up": self.up_th},
        }
