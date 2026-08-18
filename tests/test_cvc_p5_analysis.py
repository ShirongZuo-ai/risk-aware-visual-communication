from __future__ import annotations

from scripts.analyze_cvc_p5_timing import cumulative_quantile_step, lagged_correlation, median_summary, timing_category


def test_cumulative_signal_quantile_uses_signal_only() -> None:
    assert cumulative_quantile_step([0, 1, 1, 2], 0.25) == 1
    assert cumulative_quantile_step([0, 1, 1, 2], 0.50) == 2
    assert cumulative_quantile_step([0, 0], 0.25) is None


def test_positive_cross_correlation_lag_means_signal_follows_risk() -> None:
    risk = [0.0] * 5 + [1.0, 0.5] + [0.0] * 13
    signal = [0.0] * 8 + [1.0, 0.5] + [0.0] * 10
    result = lagged_correlation(risk, signal, 6)
    assert result["peak"]["lag_steps"] == 3


def test_timing_category_is_quantile_based() -> None:
    assert timing_category(3, 5, 10) == "before"
    assert timing_category(7, 5, 10) == "during"
    assert timing_category(12, 5, 10) == "after"


def test_median_summary_retains_distribution_endpoints() -> None:
    assert median_summary([3.0, 1.0, 2.0]) == {
        "values": [3.0, 1.0, 2.0], "median": 2.0, "minimum": 1.0, "maximum": 3.0,
    }
