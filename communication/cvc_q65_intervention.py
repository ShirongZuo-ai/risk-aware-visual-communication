"""Causal paired SEND-now/HOLD intervention for CVC-Q6.5 development."""
from __future__ import annotations

from dataclasses import dataclass

from communication.cvc_q2_allocator import SafetyDecisionValue
from communication.cvc_q3_allocator import ValueLatchState


@dataclass(frozen=True)
class Q65Decision:
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
    branch: str
    probe_step: int | None
    causal_signal: bool
    causal_onset: bool
    candidate_event: bool
    precursor_active: bool
    precursor_consecutive_steps: int


def empty_latch() -> ValueLatchState:
    return ValueLatchState(False, False, False, False, False,
                           None, None, None, None, None)


class OpportunityInterventionScheduler:
    """One adaptive-token intervention plus a protected final reserve.

    Branch S spends at the frozen probe. Branch H preserves the token and
    follows a frozen causal continuation. Discovery never spends before the
    fixed fallback. No branch observes evaluator state or future signals.
    """

    BRANCHES = {"D", "S", "H"}

    def __init__(self, *, total_steps: int, branch: str,
                 probe_step: int | None, min_later_gap_steps: int,
                 candidate_start_step: int, candidate_end_step: int,
                 fallback_step: int, reserve_step: int, context) -> None:
        if branch not in self.BRANCHES:
            raise ValueError("branch must be D, S, or H")
        if branch in {"S", "H"} and probe_step is None:
            raise ValueError("paired branches require a probe step")
        if not 0 < candidate_start_step < candidate_end_step < fallback_step < reserve_step < total_steps:
            raise ValueError("invalid opportunity timing")
        if probe_step is not None and not candidate_start_step <= probe_step <= candidate_end_step:
            raise ValueError("probe is outside candidate window")
        if min_later_gap_steps < 1:
            raise ValueError("later opportunity gap must be positive")
        self.total_steps = total_steps
        self.branch = branch
        self.probe_step = probe_step
        self.min_later_gap_steps = min_later_gap_steps
        self.candidate_start_step = candidate_start_step
        self.candidate_end_step = candidate_end_step
        self.fallback_step = fallback_step
        self.reserve_step = reserve_step
        self.context = context
        self.last_step = -1
        self.sent = 0
        self.spend_step: int | None = None
        self.safety_value_step: int | None = None
        self.precursor_consecutive = 0
        self.previous_signal = False

    def decide(self, step: int, _risk: float,
               value: SafetyDecisionValue) -> Q65Decision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("Q6.5 steps must be consecutive and in range")
        self.last_step = step
        signals = self.context.signals
        if signals is None:
            raise RuntimeError("Q6.5 causal signals must be observed first")
        if value.triggered and self.safety_value_step is None:
            self.safety_value_step = step
        self.precursor_consecutive = (
            self.precursor_consecutive + 1 if signals.precursor_active else 0
        )
        precursor_persistent = self.precursor_consecutive >= 2
        causal_signal = bool(value.triggered or precursor_persistent)
        causal_onset = bool(causal_signal and not self.previous_signal)
        self.previous_signal = causal_signal
        candidate_event = bool(
            causal_onset and self.candidate_start_step <= step <= self.candidate_end_step
        )
        later_eligible = bool(
            self.branch == "H" and self.probe_step is not None
            and step >= self.probe_step + self.min_later_gap_steps
            and candidate_event and self.spend_step is None
        )
        fallback_due = self.spend_step is None and step == self.fallback_step
        before = 3 - self.sent
        if step == 0:
            transmit, role, reason = True, "startup", "initial"
        elif self.branch == "S" and step == self.probe_step:
            transmit, role, reason = True, "adaptive", "send_now_intervention"
            self.spend_step = step
        elif later_eligible:
            transmit, role, reason = True, "adaptive", "next_causal_opportunity"
            self.spend_step = step
        elif fallback_due:
            transmit, role, reason = True, "adaptive", "frozen_late_fallback"
            self.spend_step = step
        elif step == self.reserve_step:
            if self.spend_step is None:
                raise RuntimeError("adaptive token was not reconciled before reserve")
            transmit, role, reason = True, "reserve", "protected_final_reserve"
        else:
            transmit, role = False, "hold"
            reason = "preserved_after_probe" if (
                self.branch == "H" and self.probe_step is not None and step >= self.probe_step
                and self.spend_step is None
            ) else ("spent_hold" if self.spend_step is not None else "common_prefix_hold")
        if transmit:
            self.sent += 1
        state = ("RESERVE" if step >= self.reserve_step else
                 "SPENT" if self.spend_step is not None else
                 "PRESERVED" if self.branch == "H" and self.probe_step is not None
                 and step >= self.probe_step else "OBSERVE")
        return Q65Decision(
            transmit, role, reason, state, False, None,
            self.safety_value_step, self.spend_step, fallback_due,
            step < self.reserve_step, before, 3 - self.sent, empty_latch(),
            self.branch, self.probe_step, causal_signal, causal_onset,
            candidate_event, signals.precursor_active,
            self.precursor_consecutive,
        )


def opportunity_label(send: dict, hold: dict, *, danger_step_tolerance: int = 3,
                      clearance_tolerance_m: float = 0.001,
                      progress_guardrail_m: float = 0.05) -> dict:
    """Frozen lexicographic SEND-minus-HOLD safety label."""
    collision_delta = int(bool(send["collision"])) - int(bool(hold["collision"]))
    danger_delta = int(send["danger_steps"]) - int(hold["danger_steps"])
    clearance_delta = float(send["min_clearance_m"]) - float(hold["min_clearance_m"])
    progress_delta = float(send["goal_progress_m"]) - float(hold["goal_progress_m"])
    if collision_delta < 0:
        label, basis = "helpful", "collision"
    elif collision_delta > 0:
        label, basis = "harmful", "collision"
    elif danger_delta <= -danger_step_tolerance:
        label, basis = "helpful", "danger_steps"
    elif danger_delta >= danger_step_tolerance:
        label, basis = "harmful", "danger_steps"
    elif clearance_delta >= clearance_tolerance_m:
        label, basis = "helpful", "minimum_clearance"
    elif clearance_delta <= -clearance_tolerance_m:
        label, basis = "harmful", "minimum_clearance"
    else:
        label, basis = "neutral", "indifference_band"
    return {
        "label": label, "basis": basis, "collision_delta": collision_delta,
        "danger_steps_delta": danger_delta,
        "min_clearance_delta_m": clearance_delta,
        "goal_progress_delta_m": progress_delta,
        "task_adverse": bool(label == "helpful" and progress_delta < -progress_guardrail_m),
    }
