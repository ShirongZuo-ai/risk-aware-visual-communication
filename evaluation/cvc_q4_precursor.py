"""Causal, decision-space precursor primitives for the CVC-Q4 diagnostic.

This module consumes only the two planner views already computed at sender time:
the receiver-held plan and the shadow plan from the current decoded image.  It
does not accept evaluator geometry, contact, clearance, or navigation outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from time import perf_counter_ns
from typing import Iterable, Mapping, Sequence

import numpy as np


HARD_CLEARANCE_M = 0.025
PREFERRED_CLEARANCE_M = 0.075
SOFT_SCALE_M = PREFERRED_CLEARANCE_M - HARD_CLEARANCE_M


@dataclass(frozen=True)
class DecisionSpaceSignals:
    stale_action_margin_m: float
    best_current_margin_m: float
    safety_decision_gap_m: float
    safe_count: int
    candidate_count: int
    safe_fraction: float
    aggregate_positive_slack_m: float
    soft_feasibility_mass: float
    lower_quartile_margin_m: float
    held_action_id: str
    current_selected_action_id: str
    stable_no_change: bool


@dataclass(frozen=True)
class TrendEstimate:
    slope_per_s: float
    r_squared: float
    residual_scale: float
    sign_consistency: float
    sample_count: int
    span_s: float


def _candidate_map(planner: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    candidates = planner.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("planner requires a non-empty candidate list")
    result: dict[str, Mapping[str, object]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or "action_id" not in candidate:
            raise ValueError("invalid planner candidate")
        action = str(candidate["action_id"])
        if action in result:
            raise ValueError("duplicate action_id")
        result[action] = candidate
    return result


def decision_space_signals(
    held_planner: Mapping[str, object],
    current_planner: Mapping[str, object],
) -> DecisionSpaceSignals:
    """Recover Q4 signals without using evaluator-only information.

    ``M_stale`` is the current conservative margin of the exact action selected
    by the held planner.  ``M_best_current`` is the maximum conservative margin
    among CURRENT hard-feasible candidates.  The gap is their difference.
    """
    held = _candidate_map(held_planner)
    current = _candidate_map(current_planner)
    if held.keys() != current.keys():
        raise ValueError("held/current candidate identities differ")
    held_action = str(held_planner.get("selected_action_id"))
    current_action = str(current_planner.get("selected_action_id"))
    if held_action not in current or current_action not in current:
        raise ValueError("selected action is absent from candidate set")

    stale = float(current[held_action]["conservative_min_clearance_m"])
    margins = np.asarray(
        [float(candidate["conservative_min_clearance_m"]) for candidate in current.values()],
        dtype=np.float64,
    )
    if np.isnan(margins).any():
        raise ValueError("NaN candidate margin")
    safe_candidates = [
        candidate for candidate in current.values() if bool(candidate.get("hard_feasible"))
    ]
    if safe_candidates:
        best = max(float(candidate["conservative_min_clearance_m"])
                   for candidate in safe_candidates)
    else:
        best = float(np.max(margins))
    gap = best - stale
    safe_count = len(safe_candidates)
    finite_margins = margins[np.isfinite(margins)]
    if finite_margins.size == 0:
        positive_slack = math.inf
        soft_mass = 1.0
        lower_quartile = math.inf
    else:
        clipped = np.where(np.isfinite(margins), margins, PREFERRED_CLEARANCE_M + 20 * SOFT_SCALE_M)
        positive_slack = float(np.mean(np.maximum(clipped - HARD_CLEARANCE_M, 0.0)))
        logits = np.clip((clipped - HARD_CLEARANCE_M) / SOFT_SCALE_M, -60.0, 60.0)
        soft_mass = float(np.mean(1.0 / (1.0 + np.exp(-logits))))
        lower_quartile = float(np.quantile(clipped, 0.25))

    held_safe = tuple(str(value) for value in held_planner.get("safe_action_ids", ()))
    current_safe = tuple(str(value) for value in current_planner.get("safe_action_ids", ()))
    stable = (
        held_action == current_action
        and held_safe == current_safe
        and str(held_planner.get("selected_safety_class")) == "preferred_safe"
        and str(current_planner.get("selected_safety_class")) == "preferred_safe"
    )
    return DecisionSpaceSignals(
        stale_action_margin_m=stale,
        best_current_margin_m=best,
        safety_decision_gap_m=gap,
        safe_count=safe_count,
        candidate_count=len(current),
        safe_fraction=safe_count / len(current),
        aggregate_positive_slack_m=positive_slack,
        soft_feasibility_mass=soft_mass,
        lower_quartile_margin_m=lower_quartile,
        held_action_id=held_action,
        current_selected_action_id=current_action,
        stable_no_change=stable,
    )


def causal_trend(
    values: Sequence[float],
    *,
    step_s: float,
    method: str = "ols",
) -> TrendEstimate:
    """Fit a trend to the supplied past-through-current window only."""
    y = np.asarray(values, dtype=np.float64)
    if y.ndim != 1 or y.size < 3 or step_s <= 0.0:
        raise ValueError("at least three ordered samples and positive step_s required")
    if not np.isfinite(y).all():
        return TrendEstimate(math.nan, math.nan, math.nan, math.nan, int(y.size),
                             float((y.size - 1) * step_s))
    x, pair_i, pair_j = _trend_geometry(int(y.size), float(step_s))
    pair_slopes = (y[pair_j] - y[pair_i]) / (x[pair_j] - x[pair_i])
    if method == "ols":
        centered_x = x - float(np.mean(x))
        slope = float(np.sum(centered_x * (y - float(np.mean(y)))) /
                      np.sum(centered_x * centered_x))
    elif method == "theil_sen":
        slope = float(np.median(pair_slopes))
    elif method == "median_adjacent":
        slope = float(np.median(np.diff(y) / step_s))
    else:
        raise ValueError(f"unknown trend method: {method}")
    intercept = float(np.median(y - slope * x)) if method != "ols" else float(np.mean(y) - slope * np.mean(x))
    residuals = y - (intercept + slope * x)
    ss_res = float(np.sum(residuals * residuals))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r_squared = 1.0 if ss_tot <= 1e-24 and ss_res <= 1e-24 else (
        math.nan if ss_tot <= 1e-24 else 1.0 - ss_res / ss_tot
    )
    residual_scale = float(1.4826 * np.median(np.abs(residuals - np.median(residuals))))
    if slope == 0.0:
        sign_consistency = float(np.mean(np.abs(pair_slopes) <= 1e-15))
    else:
        sign_consistency = float(np.mean(np.sign(pair_slopes) == np.sign(slope)))
    return TrendEstimate(slope, r_squared, residual_scale, sign_consistency,
                         int(y.size), float((y.size - 1) * step_s))


@lru_cache(maxsize=32)
def _trend_geometry(sample_count: int, step_s: float):
    x = np.arange(sample_count, dtype=np.float64) * step_s
    pair_i, pair_j = np.triu_indices(sample_count, 1)
    return x, pair_i, pair_j


def rolling_causal_trends(
    values: Sequence[float],
    *,
    window_samples: int,
    step_s: float,
    method: str,
) -> list[TrendEstimate | None]:
    if window_samples < 3:
        raise ValueError("window_samples must be at least three")
    result: list[TrendEstimate | None] = [None] * len(values)
    for index in range(window_samples - 1, len(values)):
        result[index] = causal_trend(
            values[index - window_samples + 1:index + 1], step_s=step_s, method=method
        )
    return result


def abnormal_tail_threshold(
    baseline_slopes: Iterable[float],
    *,
    tail: str,
    quantile: float = 0.01,
) -> float:
    """Return a strictly positive magnitude from a normal-variation tail."""
    values = np.asarray([value for value in baseline_slopes if math.isfinite(value)], dtype=np.float64)
    if values.size < 20 or not 0.0 < quantile < 0.5:
        raise ValueError("insufficient baseline or invalid quantile")
    if tail == "negative":
        threshold = -float(np.quantile(values, quantile))
    elif tail == "positive":
        threshold = float(np.quantile(values, 1.0 - quantile))
    else:
        raise ValueError("tail must be negative or positive")
    return max(threshold, float(np.finfo(np.float64).eps))


def event_onsets(events: Sequence[bool]) -> list[int]:
    return [index for index, value in enumerate(events)
            if value and (index == 0 or not events[index - 1])]


def future_event_labels(events: Sequence[bool], horizon_steps: int) -> list[bool]:
    """Label strictly future event onsets; the current sample is never included."""
    if horizon_steps < 1:
        raise ValueError("positive horizon required")
    onsets = event_onsets(events)
    return [any(index < onset <= index + horizon_steps for onset in onsets)
            for index in range(len(events))]


def precursor_leads(
    precursor: Sequence[bool],
    events: Sequence[bool],
    *,
    max_lead_steps: int,
    step_s: float,
) -> list[float | None]:
    if len(precursor) != len(events) or max_lead_steps < 1 or step_s <= 0.0:
        raise ValueError("invalid aligned precursor/event series")
    result: list[float | None] = []
    for onset in event_onsets(events):
        prior = [index for index in range(max(0, onset - max_lead_steps), onset)
                 if precursor[index]]
        result.append(None if not prior else float((onset - min(prior)) * step_s))
    return result


def binary_diagnostic(precursor: Sequence[bool], labels: Sequence[bool]) -> dict[str, float | int]:
    if len(precursor) != len(labels) or not precursor:
        raise ValueError("aligned non-empty series required")
    tp = sum(bool(p and y) for p, y in zip(precursor, labels))
    fp = sum(bool(p and not y) for p, y in zip(precursor, labels))
    fn = sum(bool(not p and y) for p, y in zip(precursor, labels))
    tn = len(precursor) - tp - fp - fn
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "active_fraction": (tp + fp) / len(precursor),
    }


def profile_call(callable_, repetitions: int = 1000) -> dict[str, float | int]:
    if repetitions < 1:
        raise ValueError("positive repetitions required")
    timings: list[float] = []
    for _ in range(repetitions):
        start = perf_counter_ns()
        callable_()
        timings.append((perf_counter_ns() - start) / 1_000_000.0)
    values = np.asarray(timings, dtype=np.float64)
    return {
        "repetitions": repetitions,
        "mean_ms": float(np.mean(values)),
        "p95_ms": float(np.quantile(values, 0.95)),
        "max_ms": float(np.max(values)),
        "deadline_misses_32ms": int(np.sum(values > 32.0)),
    }
