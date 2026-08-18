from __future__ import annotations

from scripts.analyze_cvc_p6_development import age_summary, cumulative_step, result_case


def test_cumulative_step_uses_nonnegative_signal_mass() -> None:
    assert cumulative_step([0.0, 1.0, 1.0, 2.0], 0.25) == 1


def test_result_case_keeps_mechanism_and_task_separate() -> None:
    a0 = {"collisions": 0, "task_successes": 1}
    assert result_case(False, a0, {"collisions": 0, "task_successes": 4})[0] == "CASE D"
    assert result_case(True, a0, {"collisions": 0, "task_successes": 4})[0] == "CASE A"
    assert result_case(True, a0, {"collisions": 0, "task_successes": 1})[0] == "CASE B"
    assert result_case(True, a0, {"collisions": 1, "task_successes": 0})[0] == "CASE C"


def test_age_summary_uses_logged_receiver_age() -> None:
    rows = [{"step": step, "receiver": {"image_age_ms": age},
             "evaluator": {"clearance_m": clearance}}
            for step, (age, clearance) in enumerate(((0, .5), (32, .3), (0, .1)))]
    summary = age_summary(rows)
    assert summary["overall_mean_ms"] == 32 / 3
    assert summary["pre_danger_endpoint_reason"] == "first_clearance_below_0.12m"
