from __future__ import annotations

from communication.cvc_q2_allocator import (
    RiskArmedSafetyValueAllocator,
    SafetyDecisionValue,
    SafetyValueThresholds,
    evaluate_safety_decision_value,
)
from navigation.cvc_q1_local_planner import LocalObstacleEstimate, plan_local_action


def decision(obstacles=()):
    return plan_local_action(obstacles, 0.0, near_slowdown_range_m=.35)


def empty_value() -> SafetyDecisionValue:
    same = decision()
    return evaluate_safety_decision_value(same, same)


def test_identical_decisions_have_no_value() -> None:
    value = empty_value()
    assert not value.triggered
    assert not value.safe_set_changed
    assert not value.action_changed


def test_visual_distractor_outside_path_does_not_trigger() -> None:
    held = decision((LocalObstacleEstimate(.7, .5, .04, .055),))
    current = decision((LocalObstacleEstimate(.65, .45, .04, .055),))
    value = evaluate_safety_decision_value(held, current)
    assert not value.triggered
    assert held.selected.action == current.selected.action


def test_moving_safe_set_collapse_is_priority_one() -> None:
    held = decision()
    current = decision((LocalObstacleEstimate(.12, 0, .04, .055),))
    value = evaluate_safety_decision_value(held, current)
    assert value.triggered and value.priority == 1
    assert value.moving_safe_set_collapse
    assert value.current_moving_safe_count == 0


def test_safety_forced_action_change_triggers() -> None:
    held = decision()
    current = decision((LocalObstacleEstimate(.18, .03, .04, .055),))
    value = evaluate_safety_decision_value(held, current)
    assert value.triggered
    assert value.safety_forced_action_change


def test_margin_tolerance_rejects_small_change() -> None:
    thresholds = SafetyValueThresholds(matched_margin_deterioration_m=.01)
    held = decision((LocalObstacleEstimate(.6, 0, .04, .055),))
    current = decision((LocalObstacleEstimate(.595, 0, .04, .055),))
    value = evaluate_safety_decision_value(held, current, thresholds)
    assert not value.triggered


def test_risk_alone_arms_without_sending() -> None:
    allocator = RiskArmedSafetyValueAllocator(312, .14, 47, 249)
    assert allocator.decide(0, .10, empty_value()).transmit
    decision1 = allocator.decide(1, .15, empty_value())
    assert decision1.armed_this_step and not decision1.transmit


def test_deadline_and_protected_reserve() -> None:
    allocator = RiskArmedSafetyValueAllocator(312, .14, 47, 249)
    rows = []
    for step in range(250):
        risk = .10 if step == 0 else .15
        rows.append(allocator.decide(step, risk, empty_value()))
    sends = [(index, row.packet_role, row.reason) for index, row in enumerate(rows) if row.transmit]
    assert sends == [(0, "startup", "initial"), (48, "adaptive", "arm_deadline"),
                     (249, "reserve", "protected_reserve")]


def test_r0_r1_allocators_have_identical_code_path_for_identical_risk() -> None:
    left = RiskArmedSafetyValueAllocator(312, .14, 47, 249)
    right = RiskArmedSafetyValueAllocator(312, .14, 47, 249)
    values = [empty_value()] * 5
    risks = [.1, .12, .15, .16, .17]
    assert [left.decide(i, risk, values[i]) for i, risk in enumerate(risks)] == [
        right.decide(i, risk, values[i]) for i, risk in enumerate(risks)]
