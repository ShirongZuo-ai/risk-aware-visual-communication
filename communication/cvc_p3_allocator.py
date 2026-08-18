"""CVC-P3 causal risk-to-transmission allocators.

The module has no simulator or evaluator imports.  Every decision depends only
on the current causal risk sample, causal allocator state, the declared horizon,
and a fixed packet quota.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AllocatorFamily = Literal["threshold", "derivative", "integral", "hazard_bucket"]


@dataclass(frozen=True)
class AllocatorSpec:
    family: AllocatorFamily
    threshold: float | None = None
    derivative_threshold: float | None = None
    integral_threshold: float | None = None
    hazard_thresholds: tuple[float, ...] = ()
    dt_s: float = 0.032
    minimum_gap_steps: int = 1

    def __post_init__(self) -> None:
        if self.dt_s <= 0 or self.minimum_gap_steps < 1:
            raise ValueError("invalid allocator timing")
        if self.family == "threshold" and self.threshold is None:
            raise ValueError("threshold allocator requires threshold")
        if self.family == "derivative" and self.derivative_threshold is None:
            raise ValueError("derivative allocator requires derivative_threshold")
        if self.family == "integral" and self.integral_threshold is None:
            raise ValueError("integral allocator requires integral_threshold")
        if self.family == "hazard_bucket" and not self.hazard_thresholds:
            raise ValueError("hazard allocator requires thresholds")
        values = [value for value in (
            self.threshold, self.derivative_threshold, self.integral_threshold
        ) if value is not None]
        values.extend(self.hazard_thresholds)
        if any(value <= 0 for value in values):
            raise ValueError("allocator thresholds must be positive")
        if tuple(sorted(self.hazard_thresholds)) != self.hazard_thresholds:
            raise ValueError("hazard thresholds must be sorted")


@dataclass(frozen=True)
class ActuationDecision:
    transmit: bool
    reason: str
    trigger_event: bool
    trigger_value: float
    tokens_before: int
    tokens_after: int


class CausalRiskAllocator:
    """Exact-quota causal allocator with immediately available packet tokens.

    A startup frame is mandatory because the receiver cannot hold an image it
    has never decoded.  Risk-triggered packets can then be spent without future
    debt.  Any unused quota is reconciled only when the remaining horizon has
    exactly as many steps as remaining packets.
    """

    def __init__(self, total_steps: int, transmissions: int, spec: AllocatorSpec) -> None:
        if total_steps < 2 or not 2 <= transmissions <= total_steps:
            raise ValueError("invalid horizon/quota")
        self.total_steps = total_steps
        self.transmissions = transmissions
        self.spec = spec
        self.sent = 0
        self.last_send_step = -total_steps
        self.previous_risk: float | None = None
        self.integral = 0.0
        self.previous_bucket = 0
        self.last_step = -1

    def _trigger(self, risk: float) -> tuple[bool, float]:
        previous = self.previous_risk
        if previous is None:
            self.previous_risk = risk
            self.previous_bucket = sum(risk >= value for value in self.spec.hazard_thresholds)
            return False, 0.0
        if self.spec.family == "threshold":
            threshold = float(self.spec.threshold)
            event, value = previous < threshold <= risk, risk
        elif self.spec.family == "derivative":
            rise = risk - previous
            event, value = rise >= float(self.spec.derivative_threshold), rise
        elif self.spec.family == "integral":
            self.integral += risk * self.spec.dt_s
            event, value = self.integral >= float(self.spec.integral_threshold), self.integral
            if event:
                self.integral -= float(self.spec.integral_threshold)
        else:
            bucket = sum(risk >= value for value in self.spec.hazard_thresholds)
            event, value = bucket > self.previous_bucket, float(bucket)
            self.previous_bucket = bucket
        self.previous_risk = risk
        return event, value

    def decide(self, step: int, risk: float) -> ActuationDecision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("steps must be consecutive and inside the horizon")
        if not 0.0 <= risk <= 1.0:
            raise ValueError("risk must be in [0, 1]")
        self.last_step = step
        trigger, trigger_value = self._trigger(risk)
        before = self.transmissions - self.sent
        remaining_steps = self.total_steps - step
        remaining_packets = before
        if remaining_packets <= 0:
            send, reason = False, "quota_exhausted"
        elif step == 0:
            send, reason = True, "initial"
        elif remaining_packets == remaining_steps:
            send, reason = True, "quota_reconcile"
        elif trigger and step - self.last_send_step >= self.spec.minimum_gap_steps:
            send, reason = True, f"risk_{self.spec.family}"
        else:
            send, reason = False, "causal_hold"
        if send:
            self.sent += 1
            self.last_send_step = step
        return ActuationDecision(send, reason, trigger, trigger_value, before, self.transmissions - self.sent)


def uniform_schedule(total_steps: int, transmissions: int) -> tuple[int, ...]:
    """Deterministic startup-plus-even schedule with an exact packet count."""
    if total_steps < 2 or not 2 <= transmissions <= total_steps:
        raise ValueError("invalid horizon/quota")
    if transmissions == 2:
        return (0, total_steps // 2)
    return tuple(round(index * (total_steps - 1) / (transmissions - 1)) for index in range(transmissions))
