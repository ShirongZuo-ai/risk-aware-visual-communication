from __future__ import annotations

from communication.cvc_q2_allocator import SafetyDecisionValue, evaluate_safety_decision_value
from communication.cvc_q3_allocator import SafetyValueLatch, TemporalRepairAllocator
from navigation.cvc_q1_local_planner import LocalObstacleEstimate, plan_local_action


def plan(obstacles=()):
    return plan_local_action(obstacles, 0.0, near_slowdown_range_m=.35)


def no_value() -> SafetyDecisionValue:
    same = plan()
    return evaluate_safety_decision_value(same, same)


def safety_value() -> SafetyDecisionValue:
    return evaluate_safety_decision_value(
        plan(), plan((LocalObstacleEstimate(.12, 0, .04, .055),)))


def test_latch_activation_persistence_and_update() -> None:
    latch = SafetyValueLatch(3)
    assert not latch.observe(0, no_value()).pending
    activated = latch.observe(1, safety_value())
    assert activated.pending and activated.activated_this_step
    assert latch.observe(2, no_value()).pending
    updated = latch.observe(3, safety_value())
    assert updated.pending and updated.updated_this_step
    assert updated.first_event_step == 1 and updated.latest_event_step == 3


def test_latch_validity_window_expiration_is_inclusive() -> None:
    latch = SafetyValueLatch(2)
    latch.observe(0, safety_value())
    assert latch.observe(1, no_value()).pending
    assert latch.observe(2, no_value()).pending
    expired = latch.observe(3, no_value())
    assert expired.expired_this_step and not expired.pending


def test_latch_consume_resets_all_event_state() -> None:
    latch = SafetyValueLatch(5)
    latch.observe(0, safety_value())
    consumed = latch.consume()
    assert consumed.consumed_this_step and consumed.pending
    assert not latch.pending
    state = latch.state()
    assert state.first_event_step is None and state.latest_event_step is None


def test_safety_value_event_after_arm_genuinely_causes_send() -> None:
    allocator = TemporalRepairAllocator(12, .14, 3, 10, 11)
    decisions = []
    for step in range(5):
        value = safety_value() if step == 3 else no_value()
        risk = .1 if step == 0 else .15
        decisions.append(allocator.decide(step, risk, value))
    assert decisions[1].armed_this_step and not decisions[1].transmit
    assert decisions[3].transmit
    assert decisions[3].reason.startswith("safety_value_latch:")
    assert decisions[3].latch.consumed_this_step


def test_prearm_transient_value_persists_until_arm_then_sends() -> None:
    allocator = TemporalRepairAllocator(12, .14, 3, 10, 11)
    rows = [
        allocator.decide(0, .10, no_value()),
        allocator.decide(1, .11, safety_value()),
        allocator.decide(2, .15, no_value()),
    ]
    assert rows[1].state == "VALUE_PENDING" and not rows[1].transmit
    assert rows[2].armed_this_step and rows[2].transmit
    assert rows[2].reason.startswith("safety_value_latch:")


def test_expired_prearm_value_does_not_send_on_late_arm() -> None:
    allocator = TemporalRepairAllocator(12, .14, 2, 10, 11)
    values = [no_value(), safety_value(), no_value(), no_value(), no_value()]
    risks = [.1, .1, .1, .1, .15]
    rows = [allocator.decide(step, risk, values[step]) for step, risk in enumerate(risks)]
    assert rows[4].armed_this_step and not rows[4].transmit


def test_late_fallback_and_final_reserve_are_protected() -> None:
    allocator = TemporalRepairAllocator(12, .14, 3, 10, 11)
    rows = [allocator.decide(step, .1, no_value()) for step in range(12)]
    sends = [(step, row.packet_role, row.reason) for step, row in enumerate(rows) if row.transmit]
    assert sends == [(0, "startup", "initial"), (10, "adaptive", "unarmed_late_fallback"),
                     (11, "reserve", "protected_final_reserve")]
    assert rows[10].tokens_after == 1 and rows[11].tokens_after == 0


def test_one_shot_consumption_prevents_repeated_value_spend() -> None:
    allocator = TemporalRepairAllocator(12, .14, 3, 10, 11)
    rows = []
    for step in range(12):
        risk = .1 if step == 0 else .15
        value = safety_value() if step in (2, 4, 6) else no_value()
        rows.append(allocator.decide(step, risk, value))
    adaptive = [row for row in rows if row.packet_role == "adaptive" and row.transmit]
    assert len(adaptive) == 1 and adaptive[0].reason.startswith("safety_value_latch:")
    assert sum(row.transmit for row in rows) == 3
    assert not rows[6].latch.pending


def test_r0_r1_share_identical_scheduler_code_and_replay_is_deterministic() -> None:
    def replay():
        allocator = TemporalRepairAllocator(12, .14, 3, 10, 11)
        risks = [.1, .11, .15, .16, .17, .18, .1, .1, .1, .1, .1, .1]
        return [allocator.decide(step, risk, safety_value() if step == 4 else no_value())
                for step, risk in enumerate(risks)]
    assert replay() == replay()
