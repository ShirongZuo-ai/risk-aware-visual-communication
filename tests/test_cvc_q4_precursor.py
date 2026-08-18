from __future__ import annotations

import math

import pytest

from evaluation.cvc_q4_precursor import (
    abnormal_tail_threshold,
    binary_diagnostic,
    causal_trend,
    decision_space_signals,
    event_onsets,
    future_event_labels,
    precursor_leads,
    profile_call,
    rolling_causal_trends,
)


def _planner(margins, *, selected="a", safe=("a", "b"), safety_class="preferred_safe"):
    return {
        "selected_action_id": selected,
        "selected_safety_class": safety_class,
        "safe_action_ids": list(safe),
        "candidates": [
            {"action_id": key, "conservative_min_clearance_m": margin,
             "hard_feasible": key in safe}
            for key, margin in zip(("a", "b", "c"), margins)
        ],
    }


def test_stale_margin_gap_and_contraction_are_current_information_only():
    held = _planner((0.30, 0.25, 0.01), selected="a")
    current = _planner((0.04, 0.20, 0.01), selected="b")
    signals = decision_space_signals(held, current)
    assert signals.stale_action_margin_m == pytest.approx(0.04)
    assert signals.best_current_margin_m == pytest.approx(0.20)
    assert signals.safety_decision_gap_m == pytest.approx(0.16)
    assert signals.safe_count == 2
    assert signals.safe_fraction == pytest.approx(2 / 3)
    assert 0.0 < signals.soft_feasibility_mass < 1.0
    assert not signals.stable_no_change


def test_unbounded_candidates_remain_well_defined():
    planner = _planner((math.inf, math.inf, math.inf), safe=("a", "b", "c"))
    signals = decision_space_signals(planner, planner)
    assert math.isinf(signals.stale_action_margin_m)
    assert math.isnan(signals.safety_decision_gap_m)
    assert signals.soft_feasibility_mass == 1.0


@pytest.mark.parametrize("method", ["ols", "theil_sen", "median_adjacent"])
def test_causal_slope_recovers_linear_trend(method):
    trend = causal_trend([1.0, 0.9, 0.8, 0.7], step_s=0.1, method=method)
    assert trend.slope_per_s == pytest.approx(-1.0)
    assert trend.sign_consistency == 1.0
    assert trend.span_s == pytest.approx(0.3)


def test_rolling_slope_never_uses_future_sample():
    original = rolling_causal_trends([0, 1, 2, 3, 4, 5], window_samples=4,
                                     step_s=1.0, method="ols")
    changed = rolling_causal_trends([0, 1, 2, 3, 4, -999], window_samples=4,
                                    step_s=1.0, method="ols")
    assert original[4] == changed[4]
    assert original[5] != changed[5]


def test_nonzero_tail_threshold_is_reproducible():
    baseline = [-0.03 + index * 0.001 for index in range(100)]
    first = abnormal_tail_threshold(baseline, tail="negative", quantile=0.01)
    second = abnormal_tail_threshold(baseline, tail="negative", quantile=0.01)
    assert first > 0.0
    assert first == second
    assert abnormal_tail_threshold([-x for x in baseline], tail="positive", quantile=0.01) > 0.0


def test_future_labels_onsets_leads_and_false_precursors():
    events = [False, False, False, True, True, False]
    precursor = [False, True, False, False, False, True]
    assert event_onsets(events) == [3]
    assert future_event_labels(events, 2) == [False, True, True, False, False, False]
    assert precursor_leads(precursor, events, max_lead_steps=3, step_s=0.1) == [pytest.approx(0.2)]
    metrics = binary_diagnostic(precursor, future_event_labels(events, 2))
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1


def test_runtime_profiler_reports_deadline_accounting():
    profile = profile_call(lambda: causal_trend([0.4, 0.3, 0.2, 0.1], step_s=0.1), 20)
    assert profile["repetitions"] == 20
    assert profile["mean_ms"] >= 0.0
    assert 0 <= profile["deadline_misses_32ms"] <= 20


def test_evaluator_fields_cannot_enter_signal_api():
    planner = _planner((0.3, 0.2, 0.1))
    with pytest.raises(TypeError):
        decision_space_signals(planner, planner, evaluator={"clearance_m": 0.0})


def test_deterministic_signal_and_trend_replay():
    held = _planner((0.30, 0.20, 0.01), selected="a")
    current = _planner((0.12, 0.25, 0.01), selected="b")
    assert decision_space_signals(held, current) == decision_space_signals(held, current)
    assert causal_trend([0.8, 0.7, 0.6, 0.5], step_s=0.032) == causal_trend(
        [0.8, 0.7, 0.6, 0.5], step_s=0.032
    )


def test_protected_q1_q2_q3_m9_evidence_is_unchanged():
    from scripts.analyze_cvc_q4 import protected_evidence

    evidence = protected_evidence()
    assert evidence["all_match"]
    assert evidence["q3_changed_inputs"] == []
