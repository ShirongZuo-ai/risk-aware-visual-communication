"""CVC-Q6 causal R0/R1 ARM -> Q5 PREPARE -> decision-value SPEND logic."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from communication.cvc_q2_allocator import SafetyDecisionValue
from communication.cvc_q3_allocator import ValueLatchState
from evaluation.cvc_q4_precursor import decision_space_signals, rolling_causal_trends
from navigation.trajectory_prediction import predict_state_only_trajectory


Q5_LEVEL_THRESHOLD = 0.6543448254639964
Q5_SLOPE_THRESHOLD_PER_S = 0.11876628431105299
Q5_WINDOW_SAMPLES = 8
CONTROL_STEP_S = 0.032
M9B_RISK_THRESHOLD = -0.010434420641870626
M9B_DEBOUNCE_STEPS = 3
RISK_HORIZON_S = 2.0
ROBOT_RADIUS_M = 0.037


@dataclass(frozen=True)
class Q6Signals:
    r0_clearance_m: float
    r1_clearance_m: float
    r0_score: float
    r1_score: float
    soft_feasibility_mass: float
    soft_mass_slope_per_s: float | None
    precursor_active: bool
    safe_count: int
    stale_action_margin_m: float


def _conservative_clearance(x: float, y: float, obstacles: Sequence[object]) -> float:
    if not obstacles:
        return 10.0
    def field(item: object, name: str) -> float:
        return float(item[name]) if isinstance(item, Mapping) else float(getattr(item, name))
    return min(
        math.hypot(x - field(item, "x_m"), y - field(item, "y_m"))
        - ROBOT_RADIUS_M - field(item, "radius_m")
        - field(item, "range_uncertainty_m")
        for item in obstacles
    )


def _selected_action(held_planner: Mapping[str, object]) -> tuple[float, float]:
    selected = held_planner.get("selected_action")
    if not isinstance(selected, Mapping):
        selected_id = str(held_planner["selected_action_id"])
        candidates = held_planner["candidates"]
        selected = next(item["action"] for item in candidates if item["action_id"] == selected_id)
    return float(selected["linear_m_s"]), float(selected["angular_rad_s"])


def compute_q6_signals(
    held_planner: Mapping[str, object],
    current_planner: Mapping[str, object],
    current_obstacles: Sequence[object],
    soft_history: Sequence[float],
) -> Q6Signals:
    """Compute exact Q5 precursor plus visual-state M9 R0/R1 without evaluator truth."""
    decision = decision_space_signals(held_planner, current_planner)
    history = [*soft_history, decision.soft_feasibility_mass]
    slope = None
    if len(history) >= Q5_WINDOW_SAMPLES:
        trend = rolling_causal_trends(
            history[-Q5_WINDOW_SAMPLES:], window_samples=Q5_WINDOW_SAMPLES,
            step_s=CONTROL_STEP_S, method="ols",
        )[-1]
        assert trend is not None
        slope = trend.slope_per_s
    precursor = bool(
        decision.soft_feasibility_mass <= Q5_LEVEL_THRESHOLD
        and slope is not None and slope < -Q5_SLOPE_THRESHOLD_PER_S
    )
    r0 = _conservative_clearance(0.0, 0.0, current_obstacles)
    linear, angular = _selected_action(held_planner)
    trajectory = predict_state_only_trajectory(
        x=0.0, y=0.0, yaw_rad=0.0, linear_velocity_m_s=linear,
        angular_velocity_rad_s=angular, horizon_s=RISK_HORIZON_S,
        step_s=CONTROL_STEP_S,
    )
    r1 = min([r0, *(_conservative_clearance(point.x, point.y, current_obstacles)
                     for point in trajectory)])
    return Q6Signals(r0, r1, -r0, -r1, decision.soft_feasibility_mass,
                     slope, precursor, decision.safe_count,
                     decision.stale_action_margin_m)


class Q6CausalContext:
    def __init__(self) -> None:
        self.soft_history: list[float] = []
        self.signals: Q6Signals | None = None

    def observe(self, held: Mapping[str, object], current: Mapping[str, object],
                current_obstacles: Sequence[object]) -> Q6Signals:
        self.signals = compute_q6_signals(held, current, current_obstacles, self.soft_history)
        self.soft_history.append(self.signals.soft_feasibility_mass)
        return self.signals


@dataclass(frozen=True)
class Q6Decision:
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
    variant: str
    selected_risk_name: str
    selected_risk_score: float
    r0_clearance_m: float
    r1_clearance_m: float
    precursor_active: bool
    precursor_consecutive_steps: int
    soft_feasibility_mass: float
    soft_mass_slope_per_s: float | None
    prepare_step: int | None
    prepare_latest_step: int | None
    prepare_age_steps: int | None
    prepare_expired_this_step: bool


class PrecursorScheduler:
    """One startup, one adaptive PREPARE/SPEND packet, one protected reserve."""

    VARIANTS = {"value_confirmed", "persistent_precursor", "safe_set_contraction",
                "opportunity_confirmed", "opportunity_persistent"}

    def __init__(self, *, total_steps: int, policy: str, variant: str,
                 prepare_validity_steps: int, fallback_step: int,
                 reserve_step: int, context: Q6CausalContext) -> None:
        if policy not in ("A0", "A1") or variant not in self.VARIANTS:
            raise ValueError("invalid Q6 policy or variant")
        if not 1 <= prepare_validity_steps < fallback_step < reserve_step < total_steps:
            raise ValueError("invalid Q6 timing")
        self.total_steps, self.policy, self.variant = total_steps, policy, variant
        self.prepare_validity_steps = prepare_validity_steps
        self.fallback_step, self.reserve_step, self.context = fallback_step, reserve_step, context
        self.last_step = -1
        self.sent = 0
        self.arm_step: int | None = None
        self.safety_value_step: int | None = None
        self.spend_step: int | None = None
        self.prepare_step: int | None = None
        self.prepare_latest_step: int | None = None
        self.risk_consecutive = 0
        self.precursor_consecutive = 0

    def _latch_state(self, step: int, *, activated: bool = False,
                     expired: bool = False, consumed: bool = False) -> ValueLatchState:
        pending = self.prepare_latest_step is not None
        return ValueLatchState(
            pending=pending, activated_this_step=activated,
            updated_this_step=bool(pending and not activated and not expired and not consumed),
            expired_this_step=expired, consumed_this_step=consumed,
            first_event_step=self.prepare_step, latest_event_step=self.prepare_latest_step,
            priority=None, primary_reason="q5_precursor" if pending else None,
            age_steps=step - self.prepare_latest_step if pending else None,
        )

    def decide(self, step: int, _legacy_risk: float,
               value: SafetyDecisionValue) -> Q6Decision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("Q6 steps must be consecutive and in range")
        self.last_step = step
        signals = self.context.signals
        if signals is None:
            raise RuntimeError("Q6 causal signals were not observed before scheduling")
        score = signals.r0_score if self.policy == "A0" else signals.r1_score
        self.risk_consecutive = self.risk_consecutive + 1 if score >= M9B_RISK_THRESHOLD else 0
        armed_this_step = False
        if self.arm_step is None and self.risk_consecutive >= M9B_DEBOUNCE_STEPS:
            self.arm_step = step
            armed_this_step = True
        if value.triggered and self.safety_value_step is None:
            self.safety_value_step = step
        self.precursor_consecutive = self.precursor_consecutive + 1 if signals.precursor_active else 0

        expired = bool(self.prepare_latest_step is not None
                       and step - self.prepare_latest_step > self.prepare_validity_steps)
        if expired:
            self.prepare_step = self.prepare_latest_step = None
        activated = False
        if signals.precursor_active and self.spend_step is None:
            activated = self.prepare_latest_step is None
            if activated:
                self.prepare_step = step
            self.prepare_latest_step = step
        latch = self._latch_state(step, activated=activated, expired=expired)

        prepared = self.prepare_latest_step is not None
        hard_arm_required = self.variant not in ("opportunity_confirmed", "opportunity_persistent")
        eligible = prepared and self.spend_step is None and (
            self.arm_step is not None or not hard_arm_required
        )
        if self.variant in ("value_confirmed", "opportunity_confirmed"):
            spend_condition = eligible and value.triggered
            spend_reason = f"prepared_safety_value:{value.primary_reason}"
        elif self.variant in ("persistent_precursor", "opportunity_persistent"):
            spend_condition = eligible and self.precursor_consecutive >= 2
            spend_reason = "prepared_persistent_precursor"
        else:
            spend_condition = eligible and (value.triggered or value.current_safe_count < value.held_safe_count)
            spend_reason = (f"prepared_safety_value:{value.primary_reason}" if value.triggered
                            else "prepared_safe_set_contraction")
        fallback_due = self.spend_step is None and step == self.fallback_step
        before = 3 - self.sent
        if step == 0:
            transmit, role, reason = True, "startup", "initial"
        elif spend_condition:
            transmit, role, reason = True, "adaptive", spend_reason
            self.spend_step = step
            latch = self._latch_state(step, consumed=True)
            self.prepare_step = self.prepare_latest_step = None
        elif fallback_due:
            transmit, role = True, "adaptive"
            reason = "armed_fallback" if self.arm_step is not None else "unarmed_fallback"
            self.spend_step = step
            if prepared:
                latch = self._latch_state(step, consumed=True)
                self.prepare_step = self.prepare_latest_step = None
        elif step == self.reserve_step:
            if self.spend_step is None:
                raise RuntimeError("Q6 adaptive packet missing before protected reserve")
            transmit, role, reason = True, "reserve", "protected_reserve"
        else:
            transmit, role = False, "hold"
            reason = ("spent_hold" if self.spend_step is not None else
                      "prepared_wait" if prepared else
                      "armed_wait" if self.arm_step is not None else "normal_hold")
        if transmit:
            self.sent += 1
        state = ("RESERVE" if step >= self.reserve_step else
                 "SPENT" if self.spend_step is not None else
                 "PREPARED" if self.prepare_latest_step is not None else
                 "ARMED" if self.arm_step is not None else "NORMAL")
        return Q6Decision(
            transmit, role, reason, state, armed_this_step, self.arm_step,
            self.safety_value_step, self.spend_step, fallback_due,
            step < self.reserve_step, before, 3 - self.sent, latch,
            self.variant, "R0" if self.policy == "A0" else "R1", score,
            signals.r0_clearance_m, signals.r1_clearance_m,
            signals.precursor_active, self.precursor_consecutive,
            signals.soft_feasibility_mass, signals.soft_mass_slope_per_s,
            self.prepare_step, self.prepare_latest_step,
            step - self.prepare_latest_step if self.prepare_latest_step is not None else None,
            expired,
        )
