"""Causal feature extraction and grouped evaluation for CVC-Q6.5."""
from __future__ import annotations

import math
from statistics import mean
from time import perf_counter_ns
from typing import Sequence

import numpy as np
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             brier_score_loss, precision_score, recall_score,
                             roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from evaluation.cvc_q4_precursor import decision_space_signals
from communication.cvc_q6_scheduler import compute_q6_signals


FEATURE_NAMES = (
    "r0", "r1", "r1_delta_1", "r1_slope_8", "r1_range_8",
    "soft_feasibility_mass", "soft_mass_delta_1", "precursor_active",
    "precursor_fraction_8", "safety_value_triggered", "safe_set_changed",
    "action_changed", "held_safe_count", "current_safe_count",
    "safe_set_fraction", "held_selected_margin", "current_selected_margin",
    "held_action_margin_in_current", "held_current_margin_gap",
    "held_image_age_s", "steps_to_fallback_fraction",
    "recent_action_change_fraction", "recent_wheel_change_fraction",
)


def finite_margin(value: object, cap: float = 1.0) -> float:
    number = float(value)
    if math.isnan(number):
        return 0.0
    if math.isinf(number):
        return cap if number > 0 else -cap
    return max(-cap, min(cap, number))


def _selected_margin(planner: dict) -> float:
    selected = str(planner["selected_action_id"])
    item = next(row for row in planner["candidates"] if str(row["action_id"]) == selected)
    return finite_margin(item["conservative_min_clearance_m"])


def _action_margin(planner: dict, action: str) -> float:
    item = next(row for row in planner["candidates"] if str(row["action_id"]) == action)
    return finite_margin(item["conservative_min_clearance_m"])


def _slope(values: Sequence[float], step_s: float = .032) -> float:
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=float) * step_s
    return float(np.polyfit(x, np.asarray(values, dtype=float), 1)[0])


def extract_causal_features(rows: Sequence[dict], probe_step: int,
                            fallback_step: int = 217) -> dict[str, float]:
    """Extract only sender/pre-decision and past runtime quantities.

    The evaluator subtree and the receiver/action produced at probe_step are
    intentionally never accessed.
    """
    if not 1 <= probe_step < len(rows):
        raise ValueError("probe step must have a non-empty causal history")
    row = rows[probe_step]
    q6_history = []
    soft_prefix: list[float] = []
    for item in rows[:probe_step + 1]:
        signal = compute_q6_signals(
            item["counterfactual"]["held_planner"],
            item["counterfactual"]["current_planner"],
            item["counterfactual"]["current_obstacles"], soft_prefix,
        )
        q6_history.append(signal)
        soft_prefix.append(signal.soft_feasibility_mass)
    history = rows[max(0, probe_step - 7):probe_step + 1]
    past = rows[max(0, probe_step - 8):probe_step]
    r1_history = [float(item.r1_score) for item in q6_history[-len(history):]]
    soft_history = [float(decision_space_signals(
        item["counterfactual"]["held_planner"],
        item["counterfactual"]["current_planner"],
    ).soft_feasibility_mass) for item in history]
    held = row["counterfactual"]["held_planner"]
    current = row["counterfactual"]["current_planner"]
    signals = decision_space_signals(held, current)
    held_action = str(held["selected_action_id"])
    held_margin = _selected_margin(held)
    current_margin = _selected_margin(current)
    held_in_current = _action_margin(current, held_action)
    past_actions = [str(item["runtime"]["planner"]["selected_action_id"]) for item in past]
    action_changes = sum(a != b for a, b in zip(past_actions, past_actions[1:]))
    wheel_pairs = [(float(item["runtime"]["wheel_left_rad_s"]),
                    float(item["runtime"]["wheel_right_rad_s"])) for item in past]
    wheel_changes = sum(abs(a[0]-b[0]) > 1e-9 or abs(a[1]-b[1]) > 1e-9
                        for a, b in zip(wheel_pairs, wheel_pairs[1:]))
    held_count = len(held["safe_action_ids"])
    current_count = len(current["safe_action_ids"])
    return {
        "r0": float(q6_history[-1].r0_score),
        "r1": float(q6_history[-1].r1_score),
        "r1_delta_1": r1_history[-1] - r1_history[-2] if len(r1_history) > 1 else 0.0,
        "r1_slope_8": _slope(r1_history),
        "r1_range_8": max(r1_history) - min(r1_history),
        "soft_feasibility_mass": float(signals.soft_feasibility_mass),
        "soft_mass_delta_1": soft_history[-1] - soft_history[-2] if len(soft_history) > 1 else 0.0,
        "precursor_active": float(bool(row["policy_state"]["precursor_active"])),
        "precursor_fraction_8": mean(float(bool(item["policy_state"]["precursor_active"])) for item in history),
        "safety_value_triggered": float(bool(row["safety_value"]["triggered"])),
        "safe_set_changed": float(bool(row["safety_value"]["safe_set_changed"])),
        "action_changed": float(bool(row["safety_value"]["action_changed"])),
        "held_safe_count": float(held_count), "current_safe_count": float(current_count),
        "safe_set_fraction": current_count / max(1, held_count),
        "held_selected_margin": held_margin, "current_selected_margin": current_margin,
        "held_action_margin_in_current": held_in_current,
        "held_current_margin_gap": current_margin - held_margin,
        "held_image_age_s": float(row["counterfactual"]["held_image_age_before_decision_ms"]) / 1000.0,
        "steps_to_fallback_fraction": (fallback_step - probe_step) / fallback_step,
        "recent_action_change_fraction": action_changes / max(1, len(past_actions)-1),
        "recent_wheel_change_fraction": wheel_changes / max(1, len(wheel_pairs)-1),
    }


def models() -> dict[str, object]:
    return {
        "logistic_l2_c0.1": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=.1, class_weight="balanced", max_iter=2000, random_state=20260818)),
        ]),
        "logistic_l2_c1": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=20260818)),
        ]),
        "tree_depth2": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", DecisionTreeClassifier(max_depth=2, min_samples_leaf=3,
                                             class_weight="balanced", random_state=20260818)),
        ]),
    }


def grouped_leave_family_out(X: np.ndarray, y: np.ndarray, families: Sequence[str],
                             estimator: object) -> dict:
    family_array = np.asarray(families)
    probability = np.full(len(y), np.nan)
    prediction = np.zeros(len(y), dtype=int)
    per_family = {}
    for family in sorted(set(families)):
        test = family_array == family
        train = ~test
        if len(set(y[train])) < 2:
            raise RuntimeError(f"training fold for {family} lacks both classes")
        fitted = clone(estimator).fit(X[train], y[train])
        probability[test] = fitted.predict_proba(X[test])[:, 1]
        prediction[test] = (probability[test] >= .5).astype(int)
        yt, yp = y[test], probability[test]
        per_family[family] = {
            "count": int(test.sum()), "helpful": int(yt.sum()),
            "average_precision": float(average_precision_score(yt, yp)) if 0 < yt.sum() < len(yt) else None,
            "recall": float(recall_score(yt, prediction[test], zero_division=0)),
            "precision": float(precision_score(yt, prediction[test], zero_division=0)),
            "predicted_send": int(prediction[test].sum()),
        }
    mixed_ap = [row["average_precision"] for row in per_family.values() if row["average_precision"] is not None]
    return {
        "pooled_auprc": float(average_precision_score(y, probability)),
        "pooled_auroc": float(roc_auc_score(y, probability)),
        "family_macro_auprc_mixed_families": float(mean(mixed_ap)) if mixed_ap else None,
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "brier": float(brier_score_loss(y, probability)),
        "false_send_nonhelpful": int(((prediction == 1) & (y == 0)).sum()),
        "false_hold_helpful": int(((prediction == 0) & (y == 1)).sum()),
        "probabilities": probability.tolist(), "predictions": prediction.tolist(),
        "per_family": per_family,
    }


def fitted_runtime_ms(estimator: object, X: np.ndarray, repeats: int = 1000) -> dict:
    samples = []
    for index in range(repeats):
        row = X[index % len(X):index % len(X) + 1]
        start = perf_counter_ns()
        estimator.predict_proba(row)
        samples.append((perf_counter_ns() - start) / 1_000_000)
    return {"mean_ms": float(np.mean(samples)), "p95_ms": float(np.percentile(samples, 95)),
            "maximum_ms": float(np.max(samples)), "repeats": repeats}
