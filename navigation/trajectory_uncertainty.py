"""Empirical residual corridor utilities for trajectory predictions."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, List, Mapping

from navigation.trajectory_prediction import EPUCK_ROBOT_HALF_WIDTH_M


DEFAULT_SAFETY_MARGIN_M = 0.01
DEFAULT_QUANTILE = 0.9
MIN_SAMPLES = 5


@dataclass(frozen=True)
class ErrorSample:
    method: str
    horizon_s: float
    motion_category: str
    time_offset_s: float
    position_error_m: float
    lateral_error_m: float | None = None


@dataclass(frozen=True)
class CorridorStats:
    method: str
    horizon_s: float
    sample_count: int
    position_error_p50_m: float | None
    position_error_p90_m: float | None
    position_error_p95_m: float | None
    corridor_radius_m: float | None
    status: str


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def position_error(predicted_x: float, predicted_y: float, actual_x: float, actual_y: float) -> float:
    for name, value in (
        ("predicted_x", predicted_x),
        ("predicted_y", predicted_y),
        ("actual_x", actual_x),
        ("actual_y", actual_y),
    ):
        _require_finite(name, value)
    return math.hypot(predicted_x - actual_x, predicted_y - actual_y)


def lateral_error(
    predicted_x: float,
    predicted_y: float,
    actual_x: float,
    actual_y: float,
    reference_yaw_rad: float,
) -> float:
    for name, value in (
        ("predicted_x", predicted_x),
        ("predicted_y", predicted_y),
        ("actual_x", actual_x),
        ("actual_y", actual_y),
        ("reference_yaw_rad", reference_yaw_rad),
    ):
        _require_finite(name, value)
    dx = actual_x - predicted_x
    dy = actual_y - predicted_y
    left_normal_x = -math.sin(reference_yaw_rad)
    left_normal_y = math.cos(reference_yaw_rad)
    return dx * left_normal_x + dy * left_normal_y


def quantile(values: Iterable[float], q: float) -> float:
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    sorted_values = sorted(values)
    if not sorted_values:
        raise ValueError("cannot compute quantile of empty data")
    for value in sorted_values:
        _require_finite("quantile value", value)
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    weight = index - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def corridor_radius(
    prediction_error_quantile_m: float,
    *,
    robot_half_width_m: float = EPUCK_ROBOT_HALF_WIDTH_M,
    safety_margin_m: float = DEFAULT_SAFETY_MARGIN_M,
) -> float:
    for name, value in (
        ("prediction_error_quantile_m", prediction_error_quantile_m),
        ("robot_half_width_m", robot_half_width_m),
        ("safety_margin_m", safety_margin_m),
    ):
        _require_finite(name, value)
    if prediction_error_quantile_m < 0:
        raise ValueError("prediction_error_quantile_m must be non-negative")
    if robot_half_width_m <= 0:
        raise ValueError("robot_half_width_m must be positive")
    if safety_margin_m < 0:
        raise ValueError("safety_margin_m must be non-negative")
    return robot_half_width_m + prediction_error_quantile_m + safety_margin_m


def summarize_corridors(
    samples: Iterable[ErrorSample],
    *,
    horizons_s: Iterable[float],
    methods: Iterable[str],
    quantile_for_radius: float = DEFAULT_QUANTILE,
    min_samples: int = MIN_SAMPLES,
    robot_half_width_m: float = EPUCK_ROBOT_HALF_WIDTH_M,
    safety_margin_m: float = DEFAULT_SAFETY_MARGIN_M,
) -> List[CorridorStats]:
    all_samples = list(samples)
    summaries: List[CorridorStats] = []
    for method in methods:
        for horizon in horizons_s:
            values = [
                sample.position_error_m
                for sample in all_samples
                if sample.method == method and math.isclose(sample.horizon_s, horizon)
            ]
            if len(values) < min_samples:
                summaries.append(CorridorStats(method, horizon, len(values), None, None, None, None, "insufficient_data"))
                continue
            p50 = quantile(values, 0.5)
            p90 = quantile(values, 0.9)
            p95 = quantile(values, 0.95)
            radius = corridor_radius(
                quantile(values, quantile_for_radius),
                robot_half_width_m=robot_half_width_m,
                safety_margin_m=safety_margin_m,
            )
            summaries.append(CorridorStats(method, horizon, len(values), p50, p90, p95, radius, "ok"))
    return summaries


def group_position_errors_by_phase(samples: Iterable[ErrorSample]) -> Mapping[tuple[str, float, str], List[float]]:
    grouped: dict[tuple[str, float, str], List[float]] = {}
    for sample in samples:
        _require_finite("position_error_m", sample.position_error_m)
        if sample.position_error_m < 0:
            raise ValueError("position_error_m must be non-negative")
        key = (sample.method, sample.horizon_s, sample.motion_category)
        grouped.setdefault(key, []).append(sample.position_error_m)
    return grouped
