"""CVC-Q2 causal Risk-ARM and hierarchical Safety-Decision-Value-SPEND policy."""
from __future__ import annotations

from dataclasses import dataclass
import math

from navigation.cvc_q1_local_planner import PlannerDecision, action_id


SAFETY_RANK = {"hard_unsafe": 0, "hard_safe": 1, "preferred_safe": 2}


@dataclass(frozen=True)
class SafetyValueThresholds:
    safe_set_contraction_fraction: float = 1.0 / 3.0
    matched_margin_deterioration_m: float = 0.01
    numerical_tolerance: float = 1e-9

    def __post_init__(self) -> None:
        if not 0.0 < self.safe_set_contraction_fraction <= 1.0:
            raise ValueError("invalid safe-set contraction fraction")
        if self.matched_margin_deterioration_m <= 0 or self.numerical_tolerance <= 0:
            raise ValueError("invalid Q2 numerical tolerance")


@dataclass(frozen=True)
class SafetyDecisionValue:
    triggered: bool
    priority: int | None
    primary_reason: str | None
    reasons: tuple[str, ...]
    safety_class_deterioration: bool
    moving_safe_set_collapse: bool
    safety_forced_action_change: bool
    action_changed: bool
    safe_set_changed: bool
    safe_actions_removed: tuple[str, ...]
    safe_actions_added: tuple[str, ...]
    held_safe_count: int
    current_safe_count: int
    held_moving_safe_count: int
    current_moving_safe_count: int
    safe_set_contraction_fraction: float
    matched_held_action_margin_deterioration_m: float | None
    matched_margin_state: str


@dataclass(frozen=True)
class Q2Decision:
    transmit: bool
    packet_role: str
    reason: str
    state: str
    armed_this_step: bool
    arm_step: int | None
    safety_value_step: int | None
    spend_step: int | None
    deadline_due: bool
    reserve_locked: bool
    tokens_before: int
    tokens_after: int


def _moving_safe_ids(decision: PlannerDecision, tolerance: float) -> set[str]:
    return {action_id(item.action) for item in decision.evaluations
            if item.hard_feasible and item.action.linear_m_s > tolerance}


def _evaluation_by_id(decision: PlannerDecision) -> dict[str, object]:
    return {action_id(item.action): item for item in decision.evaluations}


def evaluate_safety_decision_value(
    held: PlannerDecision,
    current: PlannerDecision,
    thresholds: SafetyValueThresholds = SafetyValueThresholds(),
) -> SafetyDecisionValue:
    """Evaluate one transparent event hierarchy without physical outcomes."""
    held_safe, current_safe = set(held.safe_action_ids), set(current.safe_action_ids)
    removed, added = held_safe - current_safe, current_safe - held_safe
    held_moving = _moving_safe_ids(held, thresholds.numerical_tolerance)
    current_moving = _moving_safe_ids(current, thresholds.numerical_tolerance)
    held_action = action_id(held.selected.action)
    current_action = action_id(current.selected.action)
    action_changed = held_action != current_action
    deterioration = SAFETY_RANK[current.selected.safety_class] < SAFETY_RANK[held.selected.safety_class]
    moving_collapse = bool(held_moving) and not current_moving
    forced_action = action_changed and held_action not in current_safe
    contraction = len(removed) / max(1, len(held_safe))

    held_eval = _evaluation_by_id(held)[held_action]
    current_eval = _evaluation_by_id(current)[held_action]
    held_margin = held_eval.conservative_min_clearance_m
    current_margin = current_eval.conservative_min_clearance_m
    if math.isinf(held_margin) and math.isfinite(current_margin):
        margin_drop, margin_state = None, "became_bounded"
        large_margin_drop = True
    elif math.isfinite(held_margin) and math.isinf(current_margin):
        margin_drop, margin_state, large_margin_drop = None, "became_unbounded", False
    elif math.isfinite(held_margin) and math.isfinite(current_margin):
        margin_drop = held_margin - current_margin
        margin_state = "finite"
        large_margin_drop = margin_drop >= thresholds.matched_margin_deterioration_m
    else:
        margin_drop, margin_state, large_margin_drop = 0.0, "both_unbounded", False

    reasons: list[str] = []
    priority: int | None = None
    if deterioration:
        reasons.append("safety_class_deterioration")
        priority = 1
    if moving_collapse:
        reasons.append("moving_safe_set_collapse")
        priority = 1
    if forced_action:
        reasons.append("held_action_became_unsafe")
        priority = 2 if priority is None else priority
    if contraction >= thresholds.safe_set_contraction_fraction and large_margin_drop:
        reasons.append("large_contraction_and_margin_deterioration")
        priority = 3 if priority is None else priority
    return SafetyDecisionValue(
        triggered=bool(reasons), priority=priority, primary_reason=reasons[0] if reasons else None,
        reasons=tuple(reasons), safety_class_deterioration=deterioration,
        moving_safe_set_collapse=moving_collapse, safety_forced_action_change=forced_action,
        action_changed=action_changed, safe_set_changed=held_safe != current_safe,
        safe_actions_removed=tuple(sorted(removed)), safe_actions_added=tuple(sorted(added)),
        held_safe_count=len(held_safe), current_safe_count=len(current_safe),
        held_moving_safe_count=len(held_moving), current_moving_safe_count=len(current_moving),
        safe_set_contraction_fraction=contraction,
        matched_held_action_margin_deterioration_m=margin_drop,
        matched_margin_state=margin_state,
    )


class RiskArmedSafetyValueAllocator:
    """One startup, one armed Safety-Value/deadline spend, and one reserve."""

    def __init__(self, total_steps: int, risk_threshold: float, deadline_steps: int, reserve_step: int) -> None:
        if not 1 <= deadline_steps < reserve_step < total_steps:
            raise ValueError("invalid Q2 timing")
        if not 0.0 < risk_threshold < 1.0:
            raise ValueError("invalid Q2 risk threshold")
        self.total_steps = total_steps
        self.risk_threshold = risk_threshold
        self.deadline_steps = deadline_steps
        self.reserve_step = reserve_step
        self.adaptive_fallback_step = reserve_step - 1
        self.previous_risk: float | None = None
        self.arm_step: int | None = None
        self.safety_value_step: int | None = None
        self.spend_step: int | None = None
        self.sent = 0
        self.last_step = -1

    def decide(self, step: int, risk: float, value: SafetyDecisionValue) -> Q2Decision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("Q2 steps must be consecutive and in range")
        if not 0.0 <= risk <= 1.0:
            raise ValueError("risk must be in [0,1]")
        self.last_step = step
        crossing = self.previous_risk is not None and self.previous_risk < self.risk_threshold <= risk
        self.previous_risk = risk
        armed_this_step = False
        if self.arm_step is None and crossing and self.spend_step is None:
            self.arm_step, armed_this_step = step, True
        if value.triggered and self.safety_value_step is None:
            self.safety_value_step = step
        deadline_due = (self.arm_step is not None and self.spend_step is None and
                        step - self.arm_step >= self.deadline_steps)
        before = 3 - self.sent
        if step == 0:
            transmit, role, reason = True, "startup", "initial"
        elif self.spend_step is None and self.arm_step is not None and value.triggered:
            transmit, role, reason = True, "adaptive", f"safety_value:{value.primary_reason}"
            self.spend_step = step
        elif self.spend_step is None and deadline_due:
            transmit, role, reason = True, "adaptive", "arm_deadline"
            self.spend_step = step
        elif self.spend_step is None and step == self.adaptive_fallback_step:
            transmit, role, reason = True, "adaptive", "unarmed_fallback"
            self.spend_step = step
        elif step == self.reserve_step:
            if self.spend_step is None:
                raise RuntimeError("Q2 adaptive packet missing before reserve")
            transmit, role, reason = True, "reserve", "protected_reserve"
        else:
            transmit, role = False, "hold"
            reason = "normal_hold" if self.arm_step is None else ("armed_wait" if self.spend_step is None else "spent_hold")
        if transmit:
            self.sent += 1
        state = ("RESERVE" if step >= self.reserve_step else
                 "SPENT" if self.spend_step is not None else
                 "ARMED" if self.arm_step is not None else "NORMAL")
        return Q2Decision(
            transmit, role, reason, state, armed_this_step, self.arm_step,
            self.safety_value_step, self.spend_step, deadline_due, step < self.reserve_step,
            before, 3 - self.sent,
        )
