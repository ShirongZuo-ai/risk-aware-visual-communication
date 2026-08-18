"""CVC-P4 single-adaptive-spend allocators with a protected reserve token."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReserveFamily = Literal["fixed_late", "release_time", "minimum_separation", "fixed_final"]


@dataclass(frozen=True)
class ReserveSpec:
    family: ReserveFamily
    threshold: float = 0.14
    fixed_late_step: int | None = None
    release_step: int | None = None
    fallback_step: int | None = None
    separation_steps: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError("invalid threshold")
        if self.family in ("fixed_late", "fixed_final") and self.fixed_late_step is None:
            raise ValueError("fixed reserve requires fixed_late_step")
        if self.family == "release_time" and (self.release_step is None or self.fallback_step is None):
            raise ValueError("release reserve requires release and fallback")
        if self.family == "minimum_separation" and self.separation_steps is None:
            raise ValueError("minimum separation requires separation_steps")


@dataclass(frozen=True)
class ReserveDecision:
    transmit: bool
    packet_role: str
    reason: str
    adaptive_trigger_event: bool
    tokens_before: int
    tokens_after: int
    reserve_locked: bool


class SingleAdaptiveReserveAllocator:
    """Startup + exactly one adaptive spend + one protected reserve."""

    def __init__(self, total_steps: int, spec: ReserveSpec) -> None:
        if total_steps < 4:
            raise ValueError("horizon too short")
        self.total_steps = total_steps
        self.spec = spec
        self.sent = 0
        self.previous_risk: float | None = None
        self.adaptive_step: int | None = None
        self.reserve_step: int | None = None
        self.last_step = -1
        if spec.family in ("fixed_late", "fixed_final"):
            self.adaptive_deadline = int(spec.fixed_late_step) - 1
        elif spec.family == "release_time":
            self.adaptive_deadline = int(spec.release_step) - 1
        else:
            self.adaptive_deadline = total_steps - int(spec.separation_steps) - 1
        if not 1 <= self.adaptive_deadline < total_steps - 1:
            raise ValueError("adaptive deadline leaves no protected reserve")

    def _reserve_due(self, step: int, risk: float, crossing: bool) -> bool:
        if self.adaptive_step is None:
            return False
        if self.spec.family in ("fixed_late", "fixed_final"):
            return step == int(self.spec.fixed_late_step)
        if self.spec.family == "minimum_separation":
            return step == self.adaptive_step + int(self.spec.separation_steps)
        release, fallback = int(self.spec.release_step), int(self.spec.fallback_step)
        return step >= release and ((step == release and risk >= self.spec.threshold) or crossing or step == fallback)

    def decide(self, step: int, risk: float) -> ReserveDecision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("steps must be consecutive and in range")
        if not 0.0 <= risk <= 1.0:
            raise ValueError("risk must be in [0,1]")
        self.last_step = step
        crossing = self.previous_risk is not None and self.previous_risk < self.spec.threshold <= risk
        self.previous_risk = risk
        before = 3 - self.sent
        if step == 0:
            send, role, reason = True, "startup", "initial"
        elif self.adaptive_step is None and (crossing or step == self.adaptive_deadline):
            send, role = True, "adaptive"
            reason = "risk_threshold" if crossing else "adaptive_deadline"
            self.adaptive_step = step
        elif self.reserve_step is None and self._reserve_due(step, risk, crossing):
            send, role, reason = True, "reserve", f"reserve_{self.spec.family}"
            self.reserve_step = step
        else:
            send, role, reason = False, "hold", "reserve_hold"
        if send:
            self.sent += 1
        reserve_locked = self.reserve_step is None and not self._reserve_due(step, risk, crossing)
        return ReserveDecision(send, role, reason, crossing, before, 3 - self.sent, reserve_locked)


def p4_uniform_schedule(late_step: int) -> tuple[int, int, int]:
    if late_step < 2:
        raise ValueError("late step too early")
    return (0, late_step // 2, late_step)
