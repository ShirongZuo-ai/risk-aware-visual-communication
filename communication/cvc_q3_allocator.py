"""Causal CVC-Q3 temporal repair with a bounded Safety-Value latch."""
from __future__ import annotations

from dataclasses import dataclass

from communication.cvc_q2_allocator import SafetyDecisionValue


@dataclass(frozen=True)
class ValueLatchState:
    pending: bool
    activated_this_step: bool
    updated_this_step: bool
    expired_this_step: bool
    consumed_this_step: bool
    first_event_step: int | None
    latest_event_step: int | None
    priority: int | None
    primary_reason: str | None
    age_steps: int | None


class SafetyValueLatch:
    """Persist a causal value event for a fixed inclusive validity window."""

    def __init__(self, validity_steps: int) -> None:
        if validity_steps < 1:
            raise ValueError("validity_steps must be positive")
        self.validity_steps = validity_steps
        self.first_event_step: int | None = None
        self.latest_event_step: int | None = None
        self.priority: int | None = None
        self.primary_reason: str | None = None
        self.last_step = -1

    @property
    def pending(self) -> bool:
        return self.latest_event_step is not None

    def _clear(self) -> None:
        self.first_event_step = None
        self.latest_event_step = None
        self.priority = None
        self.primary_reason = None

    def observe(self, step: int, value: SafetyDecisionValue, *, accept_event: bool = True) -> ValueLatchState:
        if step != self.last_step + 1:
            raise ValueError("latch steps must be consecutive")
        self.last_step = step
        expired = bool(self.pending and step - self.latest_event_step > self.validity_steps)
        if expired:
            self._clear()
        activated = False
        updated = False
        if accept_event and value.triggered:
            activated = not self.pending
            updated = self.pending
            if activated:
                self.first_event_step = step
            self.latest_event_step = step
            if self.priority is None or (value.priority is not None and value.priority < self.priority):
                self.priority = value.priority
                self.primary_reason = value.primary_reason
        return self.state(activated_this_step=activated, updated_this_step=updated,
                          expired_this_step=expired)

    def consume(self) -> ValueLatchState:
        before = self.state(consumed_this_step=True)
        self._clear()
        return before

    def state(self, *, activated_this_step: bool = False, updated_this_step: bool = False,
              expired_this_step: bool = False, consumed_this_step: bool = False) -> ValueLatchState:
        return ValueLatchState(
            pending=self.pending,
            activated_this_step=activated_this_step,
            updated_this_step=updated_this_step,
            expired_this_step=expired_this_step,
            consumed_this_step=consumed_this_step,
            first_event_step=self.first_event_step,
            latest_event_step=self.latest_event_step,
            priority=self.priority,
            primary_reason=self.primary_reason,
            age_steps=(self.last_step - self.latest_event_step if self.pending else None),
        )


@dataclass(frozen=True)
class Q3Decision:
    transmit: bool
    packet_role: str
    reason: str
    state: str
    armed_this_step: bool
    arm_step: int | None
    safety_value_step: int | None
    spend_step: int | None
    fallback_due: bool
    reserve_locked: bool
    tokens_before: int
    tokens_after: int
    latch: ValueLatchState


class TemporalRepairAllocator:
    """Startup, one late value/fallback packet, and a final protected reserve.

    A Safety Value event is latched whether it occurs before or after ARM.  An
    eligible pending event spends the single adaptive token immediately after
    ARM.  Otherwise the adaptive token is held until the fixed late fallback.
    The final reserve is never available to the adaptive transition.
    """

    def __init__(self, total_steps: int, risk_threshold: float, validity_steps: int,
                 fallback_step: int, reserve_step: int) -> None:
        if not 1 <= validity_steps < total_steps:
            raise ValueError("invalid Q3 value validity")
        if not 1 < fallback_step < reserve_step < total_steps:
            raise ValueError("invalid Q3 fallback/reserve timing")
        if not 0.0 < risk_threshold < 1.0:
            raise ValueError("invalid Q3 risk threshold")
        self.total_steps = total_steps
        self.risk_threshold = risk_threshold
        self.fallback_step = fallback_step
        self.reserve_step = reserve_step
        self.latch = SafetyValueLatch(validity_steps)
        self.previous_risk: float | None = None
        self.arm_step: int | None = None
        self.safety_value_step: int | None = None
        self.spend_step: int | None = None
        self.sent = 0
        self.last_step = -1

    def decide(self, step: int, risk: float, value: SafetyDecisionValue) -> Q3Decision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("Q3 steps must be consecutive and in range")
        if not 0.0 <= risk <= 1.0:
            raise ValueError("risk must be in [0,1]")
        self.last_step = step
        latch_state = self.latch.observe(step, value, accept_event=self.spend_step is None)
        if value.triggered and self.safety_value_step is None:
            self.safety_value_step = step
        crossing = self.previous_risk is not None and self.previous_risk < self.risk_threshold <= risk
        self.previous_risk = risk
        armed_this_step = False
        if self.arm_step is None and crossing and self.spend_step is None:
            self.arm_step, armed_this_step = step, True
        fallback_due = self.spend_step is None and step == self.fallback_step
        before = 3 - self.sent
        if step == 0:
            transmit, role, reason = True, "startup", "initial"
        elif self.spend_step is None and self.arm_step is not None and self.latch.pending:
            reason = f"safety_value_latch:{self.latch.primary_reason}"
            transmit, role = True, "adaptive"
            self.spend_step = step
            latch_state = self.latch.consume()
        elif fallback_due:
            transmit, role = True, "adaptive"
            reason = "armed_late_fallback" if self.arm_step is not None else "unarmed_late_fallback"
            self.spend_step = step
            if self.latch.pending:
                latch_state = self.latch.consume()
        elif step == self.reserve_step:
            if self.spend_step is None:
                raise RuntimeError("Q3 adaptive packet missing before reserve")
            transmit, role, reason = True, "reserve", "protected_final_reserve"
        else:
            transmit, role = False, "hold"
            if self.spend_step is not None:
                reason = "spent_hold"
            elif self.arm_step is not None:
                reason = "armed_value_wait"
            elif self.latch.pending:
                reason = "value_pending_wait_for_arm"
            else:
                reason = "normal_hold"
        if transmit:
            self.sent += 1
        state = ("RESERVE" if step >= self.reserve_step else
                 "SPENT" if self.spend_step is not None else
                 "VALUE_PENDING" if self.latch.pending else
                 "ARMED" if self.arm_step is not None else "NORMAL")
        return Q3Decision(
            transmit=transmit,
            packet_role=role,
            reason=reason,
            state=state,
            armed_this_step=armed_this_step,
            arm_step=self.arm_step,
            safety_value_step=self.safety_value_step,
            spend_step=self.spend_step,
            fallback_due=fallback_due,
            reserve_locked=step < self.reserve_step,
            tokens_before=before,
            tokens_after=3 - self.sent,
            latch=latch_state,
        )
