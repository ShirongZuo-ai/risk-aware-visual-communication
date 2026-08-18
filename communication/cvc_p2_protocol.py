"""CVC-P2 causal temporal/spatial mechanisms with exact episode quotas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image

from communication.cvc_p2_perception import VisualObstacle, detect_red_obstacle
from compression.tiled_jpeg import DEFAULT_M5_GRID, TileGrid


Mechanism = Literal["U0", "T", "S", "TS"]
RiskSignal = Literal["NONE", "R0", "R1"]


@dataclass(frozen=True)
class CausalDecision:
    transmit: bool
    qualities: tuple[int, ...]
    reason: str
    roi_tile_ids: tuple[int, ...]


class ExactQuotaScheduler:
    """Causal schedule with a known horizon and exact transmission quota.

    It never uses future risks or evaluator state. Forced reconciliation depends
    only on the declared horizon/quota and guarantees equal episode wire cost.
    """

    def __init__(self, total_steps: int, transmissions: int, adaptive: bool) -> None:
        if not 1 <= transmissions <= total_steps:
            raise ValueError("transmissions must be in [1, total_steps]")
        self.total_steps = total_steps
        self.transmissions = transmissions
        self.adaptive = adaptive
        self.sent = 0
        self.last_send_step = -total_steps

    def decide(self, step: int, risk: float) -> tuple[bool, str]:
        if not 0 <= step < self.total_steps or not 0.0 <= risk <= 1.0:
            raise ValueError("invalid causal scheduling input")
        remaining_steps = self.total_steps - step
        remaining_sends = self.transmissions - self.sent
        if remaining_sends <= 0:
            return False, "quota_exhausted"
        if step == 0:
            send, reason = True, "initial"
        elif remaining_sends == remaining_steps:
            send, reason = True, "quota_reconcile"
        elif not self.adaptive:
            # Evenly distribute the exact quota without floating-point drift.
            send = ((step + 1) * self.transmissions // self.total_steps) > (step * self.transmissions // self.total_steps)
            reason = "uniform" if send else "uniform_hold"
        else:
            uniform_gap = max(1, self.total_steps // self.transmissions)
            age = step - self.last_send_step
            urgency = risk >= 0.16 and age >= max(1, uniform_gap // 3)
            stale = age >= max(2, 2 * uniform_gap)
            send = urgency or stale
            reason = "risk" if urgency else ("max_age" if stale else "adaptive_hold")
        if send:
            self.sent += 1
            self.last_send_step = step
        return send, reason


def roi_tiles(obstacle: VisualObstacle, grid: TileGrid = DEFAULT_M5_GRID) -> tuple[int, ...]:
    """Map a decoded-image component bbox to a one-tile-expanded causal ROI."""
    if not obstacle.detected or obstacle.bbox_xyxy is None:
        return ()
    x0, y0, x1, y1 = obstacle.bbox_xyxy
    c0 = max(0, x0 // grid.tile_width_px - 1)
    c1 = min(grid.columns - 1, max(0, (x1 - 1) // grid.tile_width_px) + 1)
    r0 = max(0, y0 // grid.tile_height_px - 1)
    r1 = min(grid.rows - 1, max(0, (y1 - 1) // grid.tile_height_px) + 1)
    return tuple(row * grid.columns + col for row in range(r0, r1 + 1) for col in range(c0, c1 + 1))


def spatial_qualities(image: Image.Image, mechanism: Mechanism, risk: float,
                      grid: TileGrid = DEFAULT_M5_GRID) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if mechanism not in ("S", "TS"):
        return (34,) * grid.tile_count, ()
    obstacle = detect_red_obstacle(image)
    roi = roi_tiles(obstacle, grid)
    if not roi:
        return (34,) * grid.tile_count, ()
    roi_set = set(roi)
    high = 82 if risk >= 0.16 else 62
    low = 7 if risk >= 0.16 else 18
    return tuple(high if tile_id in roi_set else low for tile_id in range(grid.tile_count)), roi


def predictive_risk(current: float, previous: float, bearing: float | None) -> float:
    """Causal image-space constant-growth risk with centrality projection."""
    growth = max(0.0, current - previous)
    centrality = 1.0 - min(1.0, abs(float(bearing or 0.0)))
    return min(1.0, max(current, current + 6.0 * growth * (0.5 + 0.5 * centrality)))
