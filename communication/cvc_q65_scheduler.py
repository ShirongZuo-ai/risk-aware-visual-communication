"""Budget-aware online scheduler for the frozen Q6.5 opportunity model."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from communication.cvc_q2_allocator import SafetyDecisionValue
from communication.cvc_q3_allocator import ValueLatchState
from communication.cvc_q65_predictor import FrozenOpportunityPredictor
from evaluation.cvc_q4_precursor import decision_space_signals


def _empty_latch() -> ValueLatchState:
    return ValueLatchState(False, False, False, False, False, None, None, None, None, None)


def _finite(value: object, cap: float = 1.0) -> float:
    number = float(value)
    if math.isnan(number): return 0.0
    if math.isinf(number): return cap if number > 0 else -cap
    return max(-cap, min(cap, number))


def _selected_margin(plan: Mapping[str, object]) -> float:
    selected = str(plan["selected_action_id"])
    row = next(item for item in plan["candidates"] if str(item["action_id"]) == selected)
    return _finite(row["conservative_min_clearance_m"])


def _action_margin(plan: Mapping[str, object], action: str) -> float:
    row = next(item for item in plan["candidates"] if str(item["action_id"]) == action)
    return _finite(row["conservative_min_clearance_m"])


def _slope(values: list[float], step_s: float = .032) -> float:
    if len(values) < 2: return 0.0
    xs = [index * step_s for index in range(len(values))]
    xbar, ybar = sum(xs)/len(xs), sum(values)/len(values)
    denominator = sum((x-xbar)**2 for x in xs)
    return sum((x-xbar)*(y-ybar) for x,y in zip(xs,values))/denominator if denominator else 0.0


class OnlineFeatureState:
    def __init__(self, q6_context) -> None:
        self.q6_context = q6_context
        self.held: Mapping[str, object] | None = None
        self.current: Mapping[str, object] | None = None
        self.value: SafetyDecisionValue | None = None
        self.r1_history: list[float] = []
        self.precursor_history: list[bool] = []
        self.actual_action_history: list[str] = []
        self.actual_wheel_history: list[tuple[float,float]] = []

    def observe(self, held: Mapping[str, object], current: Mapping[str, object],
                value: SafetyDecisionValue, previous_actual=None) -> None:
        self.held, self.current, self.value = held, current, value
        signals = self.q6_context.signals
        if signals is None: raise RuntimeError("Q6 signals unavailable")
        self.r1_history.append(float(signals.r1_score))
        self.precursor_history.append(bool(signals.precursor_active))
        if previous_actual is not None:
            selected = previous_actual.selected
            self.actual_action_history.append(
                f"v{selected.action.linear_m_s:+.3f}_w{selected.action.angular_rad_s:+.3f}")
            self.actual_wheel_history.append((float(selected.wheel_left_rad_s),float(selected.wheel_right_rad_s)))

    def features(self, step: int, last_send_step: int, fallback_step: int) -> dict[str,float]:
        if self.held is None or self.current is None or self.value is None:
            raise RuntimeError("online feature state was not observed")
        signals = self.q6_context.signals
        r1 = self.r1_history[-8:]
        soft = self.q6_context.soft_history[-8:]
        precursor = self.precursor_history[-8:]
        held, current, value = self.held, self.current, self.value
        decision = decision_space_signals(held,current)
        held_action = str(held["selected_action_id"])
        actions = self.actual_action_history[-8:]
        wheels = self.actual_wheel_history[-8:]
        action_changes = sum(a != b for a,b in zip(actions,actions[1:]))
        wheel_changes = sum(abs(a[0]-b[0])>1e-9 or abs(a[1]-b[1])>1e-9 for a,b in zip(wheels,wheels[1:]))
        held_count,current_count=len(held["safe_action_ids"]),len(current["safe_action_ids"])
        held_margin,current_margin=_selected_margin(held),_selected_margin(current)
        return {
            "r0":float(signals.r0_score),"r1":float(signals.r1_score),
            "r1_delta_1":r1[-1]-r1[-2] if len(r1)>1 else 0.0,"r1_slope_8":_slope(r1),
            "r1_range_8":max(r1)-min(r1),"soft_feasibility_mass":float(decision.soft_feasibility_mass),
            "soft_mass_delta_1":soft[-1]-soft[-2] if len(soft)>1 else 0.0,
            "precursor_active":float(signals.precursor_active),
            "precursor_fraction_8":sum(precursor)/len(precursor),
            "safety_value_triggered":float(value.triggered),"safe_set_changed":float(value.safe_set_changed),
            "action_changed":float(value.action_changed),"held_safe_count":float(held_count),
            "current_safe_count":float(current_count),"safe_set_fraction":current_count/max(1,held_count),
            "held_selected_margin":held_margin,"current_selected_margin":current_margin,
            "held_action_margin_in_current":_action_margin(current,held_action),
            "held_current_margin_gap":current_margin-held_margin,
            "held_image_age_s":(step-last_send_step)*.032,
            "steps_to_fallback_fraction":(fallback_step-step)/fallback_step,
            "recent_action_change_fraction":action_changes/max(1,len(actions)-1),
            "recent_wheel_change_fraction":wheel_changes/max(1,len(wheels)-1),
        }


@dataclass(frozen=True)
class UtilityDecision:
    transmit: bool; packet_role: str; reason: str; state: str
    armed_this_step: bool; arm_step: int|None; safety_value_step: int|None
    spend_step: int|None; fallback_due: bool; reserve_locked: bool
    tokens_before: int; tokens_after: int; latch: ValueLatchState
    opportunity_evaluated: bool; opportunity_probability: float|None
    opportunity_positive: bool; candidate_event: bool; candidate_reason: str|None


class OpportunityValueScheduler:
    def __init__(self, *, total_steps:int, predictor:FrozenOpportunityPredictor,
                 feature_state:OnlineFeatureState, candidate_start_step:int=24,
                 candidate_end_step:int=180, clock_steps=(80,144),
                 fallback_step:int=217, reserve_step:int=218) -> None:
        self.total_steps=total_steps; self.predictor=predictor; self.feature_state=feature_state
        self.candidate_start_step=candidate_start_step; self.candidate_end_step=candidate_end_step
        self.clock_steps=tuple(clock_steps); self.fallback_step=fallback_step; self.reserve_step=reserve_step
        self.last_step=-1; self.last_send_step=0; self.sent=0; self.spend_step=None
        self.safety_value_step=None; self.previous_signal=False; self.precursor_consecutive=0

    def decide(self,step:int,_risk:float,value:SafetyDecisionValue)->UtilityDecision:
        if step!=self.last_step+1: raise ValueError("utility scheduler steps must be consecutive")
        self.last_step=step
        signals=self.feature_state.q6_context.signals
        if signals is None: raise RuntimeError("causal signals unavailable")
        if value.triggered and self.safety_value_step is None:self.safety_value_step=step
        self.precursor_consecutive=self.precursor_consecutive+1 if signals.precursor_active else 0
        causal=bool(value.triggered or self.precursor_consecutive>=2)
        onset=causal and not self.previous_signal; self.previous_signal=causal
        candidate=bool(self.candidate_start_step<=step<=self.candidate_end_step and (onset or step in self.clock_steps))
        candidate_reason=("causal_event_onset" if onset else "fixed_clock" if step in self.clock_steps else None)
        probability=None; positive=False
        if candidate and self.spend_step is None:
            probability=self.predictor.probability(self.feature_state.features(step,self.last_send_step,self.fallback_step))
            positive=probability>=self.predictor.threshold
        fallback=self.spend_step is None and step==self.fallback_step
        before=3-self.sent
        if step==0: transmit,role,reason=True,"startup","initial"
        elif candidate and positive:
            transmit,role,reason=True,"adaptive","opportunity_value_positive"; self.spend_step=step
        elif fallback:
            transmit,role,reason=True,"adaptive","frozen_late_fallback"; self.spend_step=step
        elif step==self.reserve_step:
            if self.spend_step is None: raise RuntimeError("adaptive token missing")
            transmit,role,reason=True,"reserve","protected_final_reserve"
        else: transmit,role,reason=False,"hold","opportunity_negative_hold" if candidate else "normal_hold"
        if transmit:self.sent+=1;self.last_send_step=step
        state="RESERVE" if step>=self.reserve_step else "SPENT" if self.spend_step is not None else "SEARCH"
        return UtilityDecision(transmit,role,reason,state,False,None,self.safety_value_step,self.spend_step,
                               fallback,step<self.reserve_step,before,3-self.sent,_empty_latch(),
                               candidate,probability,positive,candidate,candidate_reason)
