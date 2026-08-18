import json
from pathlib import Path

from communication.cvc_q6_scheduler import (
    CONTROL_STEP_S, M9B_RISK_THRESHOLD, Q5_LEVEL_THRESHOLD,
    Q5_SLOPE_THRESHOLD_PER_S, Q5_WINDOW_SAMPLES, PrecursorScheduler,
    Q6CausalContext, Q6Signals,
)
from evaluation.cvc_q5_support import StageASafetyValue


ROOT = Path(__file__).resolve().parents[1]


def no_value(current_safe=15, held_safe=15):
    return StageASafetyValue(False, None, None, (), False, False, False, 0.0,
                             0.0, "finite", held_safe, current_safe, 10, 10)


def value():
    return StageASafetyValue(True, 2, "held_action_became_unsafe",
                             ("held_action_became_unsafe",), False, False, True,
                             0.2, .02, "finite", 15, 12, 10, 8)


def signals(*, risk=.1, precursor=False):
    return Q6Signals(.2, -risk, -.2, risk, .6 if precursor else .9,
                     -.2 if precursor else 0.0, precursor, 12, .04)


def scheduler(variant="value_confirmed", policy="A1", validity=5,
              fallback=10, reserve=11):
    context = Q6CausalContext()
    return context, PrecursorScheduler(total_steps=12, policy=policy, variant=variant,
        prepare_validity_steps=validity, fallback_step=fallback,
        reserve_step=reserve, context=context)


def step(context, alloc, index, sig, val):
    context.signals = sig
    return alloc.decide(index, 0.0, val)


def test_frozen_constants_are_exact():
    assert Q5_LEVEL_THRESHOLD == 0.6543448254639964
    assert Q5_SLOPE_THRESHOLD_PER_S == 0.11876628431105299
    assert Q5_WINDOW_SAMPLES == 8 and CONTROL_STEP_S == .032
    assert M9B_RISK_THRESHOLD == -0.010434420641870626


def test_value_confirmed_requires_arm_prepare_and_value():
    context, alloc = scheduler()
    decisions = []
    for index in range(8):
        decisions.append(step(context, alloc, index, signals(risk=.1, precursor=index >= 4),
                              value() if index == 6 else no_value()))
    assert decisions[2].arm_step == 2
    assert decisions[4].latch.activated_this_step
    assert decisions[6].transmit and decisions[6].reason.startswith("prepared_safety_value")
    assert sum(item.transmit for item in decisions) == 2  # startup + adaptive so far


def test_prepare_expires_and_falls_back_without_double_spend():
    context, alloc = scheduler(validity=2)
    decisions = []
    for index in range(12):
        decisions.append(step(context, alloc, index,
                              signals(risk=.1, precursor=index == 3), no_value()))
    assert decisions[6].prepare_expired_this_step
    assert [i for i, item in enumerate(decisions) if item.transmit] == [0, 10, 11]
    assert decisions[10].reason == "armed_fallback"
    assert decisions[11].reason == "protected_reserve"


def test_persistent_variant_rejects_one_step_and_spends_on_second():
    context, alloc = scheduler("persistent_precursor")
    decisions = []
    for index in range(8):
        decisions.append(step(context, alloc, index,
                              signals(risk=.1, precursor=index in (4, 5)), no_value()))
    assert not decisions[4].transmit
    assert decisions[5].transmit and decisions[5].reason == "prepared_persistent_precursor"


def test_safe_set_variant_uses_causal_contraction():
    context, alloc = scheduler("safe_set_contraction")
    decisions = []
    for index in range(8):
        val = no_value(current_safe=14, held_safe=15) if index == 5 else no_value()
        decisions.append(step(context, alloc, index,
                              signals(risk=.1, precursor=index >= 4), val))
    assert decisions[5].transmit and decisions[5].reason == "prepared_safe_set_contraction"


def test_q6_sources_contain_no_evaluator_dependency():
    for relative in ("communication/cvc_q6_scheduler.py",
                     "simulator/controllers/cvc_q6_runner/cvc_q6_runner.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert '"evaluator"' not in source and "getContactPoints" not in source


def test_q6_config_is_exact_72k_and_screening_is_development():
    cfg = json.loads((ROOT / "config/cvc_q6_development.json").read_text())
    assert cfg["communication"]["packet_count"] * cfg["communication"]["packet_bytes"] == 72_000
    assert not cfg["independent_validation_eligible"]


def test_generation2_repairs_hard_arm_starvation_but_keeps_value_confirmation():
    context, alloc = scheduler("opportunity_confirmed")
    decisions = []
    for index in range(8):
        event = value() if index == 6 else no_value()
        decisions.append(step(context, alloc, index,
                              signals(risk=-10.0, precursor=index == 4), event))
    assert decisions[6].transmit
    assert decisions[6].reason == "prepared_safety_value:held_action_became_unsafe"
    assert decisions[6].arm_step is None


def test_final_generation_spends_on_two_sample_opportunity_without_arm_or_value():
    context, alloc = scheduler("opportunity_persistent")
    decisions = []
    for index in range(8):
        decisions.append(step(context, alloc, index,
                              signals(risk=-10.0, precursor=index in (4, 5)), no_value()))
    assert not decisions[4].transmit
    assert decisions[5].transmit
    assert decisions[5].reason == "prepared_persistent_precursor"
    assert decisions[5].arm_step is None
