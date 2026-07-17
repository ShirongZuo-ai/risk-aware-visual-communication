"""Trajectory-to-obstacle conflict analysis."""

from __future__ import annotations

import math
from typing import Iterable

from navigation.trajectory_prediction import TrajectoryPoint
from risk_map.geometry import (
    corridor_intervals_for_trajectory,
    polyline_to_aabb_closest,
    summarize_corridor_intervals,
    validate_trajectory,
)
from risk_map.models import (
    DualTrajectoryRiskResult,
    ObstacleFootprint,
    RiskParameters,
    TrajectoryConflictResult,
    TrajectorySource,
    require_finite,
)
from risk_map.risk_formulation import combine_risk_scores, compute_risk_score


def _validated_for_parameters(
    trajectory: Iterable[TrajectoryPoint],
    parameters: RiskParameters,
) -> list[TrajectoryPoint]:
    points = validate_trajectory(trajectory)
    max_time = points[-1].time_offset_s
    if max_time > parameters.maximum_horizon_s + parameters.geometry_tolerance_m:
        raise ValueError("trajectory exceeds maximum_horizon_s")
    return points


def analyze_trajectory_obstacle(
    trajectory: Iterable[TrajectoryPoint],
    obstacle: ObstacleFootprint,
    trajectory_source: TrajectorySource,
    parameters: RiskParameters,
) -> TrajectoryConflictResult:
    if not isinstance(trajectory_source, TrajectorySource):
        raise ValueError("trajectory_source must be a TrajectorySource")
    points = _validated_for_parameters(trajectory, parameters)
    closest = polyline_to_aabb_closest(points, obstacle, parameters.geometry_tolerance_m)
    clearance = closest.distance_m - parameters.corridor_radius_m
    intervals = corridor_intervals_for_trajectory(
        points,
        obstacle,
        parameters.corridor_radius_m,
        parameters.geometry_tolerance_m,
    )
    interval_summary = summarize_corridor_intervals(intervals)
    enters = clearance <= parameters.geometry_tolerance_m or interval_summary.first_entry_time_s is not None
    first_entry_time = interval_summary.first_entry_time_s if enters else None
    overlap_duration = interval_summary.overlap_duration_s if enters else 0.0
    if enters and first_entry_time is None:
        first_entry_time = closest.closest_time_s
    scores = compute_risk_score(
        clearance_m=clearance,
        closest_time_s=closest.closest_time_s,
        first_entry_time_s=first_entry_time,
        sigma_distance_m=parameters.sigma_distance_m,
        tau_time_s=parameters.tau_time_s,
    )
    return TrajectoryConflictResult(
        obstacle_id=obstacle.obstacle_id,
        trajectory_source=trajectory_source,
        minimum_centerline_distance_m=closest.distance_m,
        minimum_clearance_m=clearance,
        closest_time_s=closest.closest_time_s,
        enters_corridor=enters,
        first_corridor_entry_time_s=first_entry_time,
        corridor_overlap_duration_s=overlap_duration,
        spatial_score=scores.spatial_score,
        temporal_score=scores.temporal_score,
        risk_score=scores.risk_score,
    )


def interpolate_trajectory_position(
    trajectory: Iterable[TrajectoryPoint],
    time_offset_s: float,
) -> tuple[float, float]:
    require_finite("time_offset_s", time_offset_s)
    points = validate_trajectory(trajectory)
    if time_offset_s < points[0].time_offset_s or time_offset_s > points[-1].time_offset_s:
        raise ValueError("time_offset_s is outside trajectory range")
    for index, point in enumerate(points):
        if math.isclose(time_offset_s, point.time_offset_s, abs_tol=1e-12):
            return point.x, point.y
        if index == len(points) - 1:
            break
        next_point = points[index + 1]
        if point.time_offset_s <= time_offset_s <= next_point.time_offset_s:
            dt = next_point.time_offset_s - point.time_offset_s
            if dt == 0.0:
                return point.x, point.y
            ratio = (time_offset_s - point.time_offset_s) / dt
            return (
                point.x + ratio * (next_point.x - point.x),
                point.y + ratio * (next_point.y - point.y),
            )
    raise ValueError("time_offset_s is outside trajectory range")


def compute_trajectory_disagreement(
    planned_trajectory: Iterable[TrajectoryPoint],
    state_trajectory: Iterable[TrajectoryPoint],
) -> float:
    planned = validate_trajectory(planned_trajectory)
    state = validate_trajectory(state_trajectory)
    start = max(planned[0].time_offset_s, state[0].time_offset_s)
    end = min(planned[-1].time_offset_s, state[-1].time_offset_s)
    if start > end:
        raise ValueError("trajectories have no common time range")
    sample_times = sorted(
        {
            point.time_offset_s
            for point in planned + state
            if start <= point.time_offset_s <= end
        }
        | {start, end}
    )
    if not sample_times:
        raise ValueError("trajectories have no common sample times")
    max_distance = 0.0
    for time_offset in sample_times:
        planned_x, planned_y = interpolate_trajectory_position(planned, time_offset)
        state_x, state_y = interpolate_trajectory_position(state, time_offset)
        max_distance = max(max_distance, math.hypot(planned_x - state_x, planned_y - state_y))
    return max_distance


def analyze_dual_trajectory_obstacle(
    planned_trajectory: Iterable[TrajectoryPoint],
    state_trajectory: Iterable[TrajectoryPoint],
    obstacle: ObstacleFootprint,
    parameters: RiskParameters,
) -> DualTrajectoryRiskResult:
    planned_points = validate_trajectory(planned_trajectory)
    state_points = validate_trajectory(state_trajectory)
    planned_result = analyze_trajectory_obstacle(planned_points, obstacle, TrajectorySource.PLANNED, parameters)
    state_result = analyze_trajectory_obstacle(state_points, obstacle, TrajectorySource.STATE, parameters)
    disagreement = compute_trajectory_disagreement(planned_points, state_points)
    combined = combine_risk_scores(planned_result.risk_score, state_result.risk_score)
    return DualTrajectoryRiskResult(
        obstacle_id=obstacle.obstacle_id,
        planned_result=planned_result,
        state_result=state_result,
        trajectory_disagreement_m=disagreement,
        combined_risk_score=combined,
    )
