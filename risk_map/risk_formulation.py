"""Interpretable risk score formulas."""

from __future__ import annotations

from dataclasses import dataclass
import math

from risk_map.models import require_finite


@dataclass(frozen=True)
class RiskScoreComponents:
    spatial_score: float
    temporal_score: float
    risk_score: float
    relevant_time_s: float


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def spatial_score(clearance_m: float, sigma_distance_m: float) -> float:
    require_finite("clearance_m", clearance_m)
    require_finite("sigma_distance_m", sigma_distance_m)
    if sigma_distance_m <= 0:
        raise ValueError("sigma_distance_m must be positive")
    if clearance_m <= 0:
        return 1.0
    return _clamp_unit(math.exp(-clearance_m / sigma_distance_m))


def temporal_score(relevant_time_s: float, tau_time_s: float) -> float:
    require_finite("relevant_time_s", relevant_time_s)
    require_finite("tau_time_s", tau_time_s)
    if relevant_time_s < 0:
        raise ValueError("relevant_time_s must be non-negative")
    if tau_time_s <= 0:
        raise ValueError("tau_time_s must be positive")
    return _clamp_unit(math.exp(-relevant_time_s / tau_time_s))


def compute_risk_score(
    *,
    clearance_m: float,
    closest_time_s: float,
    first_entry_time_s: float | None,
    sigma_distance_m: float,
    tau_time_s: float,
) -> RiskScoreComponents:
    relevant_time = first_entry_time_s if first_entry_time_s is not None else closest_time_s
    require_finite("relevant_time_s", relevant_time)
    s_score = spatial_score(clearance_m, sigma_distance_m)
    t_score = temporal_score(relevant_time, tau_time_s)
    return RiskScoreComponents(s_score, t_score, _clamp_unit(s_score * t_score), relevant_time)


def combine_risk_scores(planned_risk: float, state_risk: float) -> float:
    require_finite("planned_risk", planned_risk)
    require_finite("state_risk", state_risk)
    if planned_risk < 0 or planned_risk > 1 or state_risk < 0 or state_risk > 1:
        raise ValueError("risk scores must be in [0, 1]")
    return max(planned_risk, state_risk)
