"""스쿼트 카운터 — 무릎 각도 시계열 → rep 카운팅 상태 머신.

설계:
  UP(서 있음, angle > up_th) ↔ DOWN(앉음, angle < down_th)
  UP → DOWN → UP 한 사이클 = 1 rep.

함정 방지:
  - min_dwell_ms: 상태 전환 후 최소 유지 시간 — 떨림(jitter)으로 인한 false positive 방지
  - hysteresis: down_th < up_th (90° / 140° 기본) — 임계 사이 진동에서 카운트 폭발 차단
  - 좌/우 분리 가능: side='left'|'right'|'avg'|'better' — better는 매 프레임 conf 높은 쪽 선택

사용:
  from squat_counter import SquatCounter
  c = SquatCounter(down_th=100, up_th=140, min_dwell_ms=200)
  ev = c.update(angle_deg, now_ms)
  # ev = None | ("REP", reps_total, min_angle_at_bottom)
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class SquatCounter:
    down_th: float = 100.0
    up_th: float = 140.0
    min_dwell_ms: float = 200.0

    state: str = "UP"
    reps: int = 0
    last_transition_ms: float = 0.0
    min_angle_in_down: Optional[float] = None

    # 통계 (요약용)
    deepest_overall: Optional[float] = None
    last_rep_min_angle: Optional[float] = None

    def update(self, angle_deg: Optional[float], now_ms: Optional[float] = None) -> Optional[Tuple[str, int, float]]:
        """각도 1샘플로 상태 갱신. rep 완료 시 ("REP", reps_total, min_angle_at_bottom) 반환."""
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


def pick_angle(left: Optional[float], right: Optional[float], mode: str = "better") -> Optional[float]:
    """좌/우 각도 → 1개 대표 각도.
    mode:
      'left'   : 좌측만
      'right'  : 우측만
      'avg'    : 좌/우 평균 (둘 다 있을 때만, 한쪽 None이면 None)
      'better' : 둘 중 정의된 쪽, 둘 다면 평균
    """
    if mode == "left":
        return left
    if mode == "right":
        return right
    if mode == "avg":
        if left is None or right is None:
            return None
        return (left + right) / 2.0
    # better
    if left is not None and right is not None:
        return (left + right) / 2.0
    return left if left is not None else right
