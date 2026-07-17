"""Trajectory prediction models for short-horizon e-puck motion."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, List


DEFAULT_STEP_S = 0.032
SUPPORTED_HORIZONS_S = (0.5, 1.0, 2.0)
OMEGA_EPSILON = 1e-9

# Official Webots R2025a e-puck values:
# projects/robots/gctronic/e-puck/controllers/e-puck/e-puck.c
EPUCK_WHEEL_RADIUS_M = 0.02
EPUCK_AXLE_LENGTH_M = 0.052
EPUCK_ROBOT_HALF_WIDTH_M = EPUCK_AXLE_LENGTH_M / 2.0


@dataclass(frozen=True)
class TrajectoryPoint:
    time_offset_s: float
    x: float
    y: float
    yaw_rad: float


@dataclass(frozen=True)
class CommandSegment:
    start_offset_s: float
    end_offset_s: float
    left_wheel_command_rad_s: float
    right_wheel_command_rad_s: float


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def normalize_angle(angle_rad: float) -> float:
    _require_finite("angle_rad", angle_rad)
    return math.atan2(math.sin(angle_rad), math.cos(angle_rad))


def _validate_horizon_step(horizon_s: float, step_s: float) -> None:
    _require_finite("horizon_s", horizon_s)
    _require_finite("step_s", step_s)
    if horizon_s <= 0:
        raise ValueError("horizon_s must be positive")
    if step_s <= 0:
        raise ValueError("step_s must be positive")


def _time_offsets(horizon_s: float, step_s: float) -> List[float]:
    _validate_horizon_step(horizon_s, step_s)
    offsets = []
    step_index = 1
    while True:
        offset = step_index * step_s
        if offset >= horizon_s:
            offsets.append(horizon_s)
            break
        offsets.append(offset)
        step_index += 1
    return offsets


def _integrate_constant_twist(
    x: float,
    y: float,
    yaw_rad: float,
    linear_velocity_m_s: float,
    angular_velocity_rad_s: float,
    dt_s: float,
) -> tuple[float, float, float]:
    if abs(angular_velocity_rad_s) < OMEGA_EPSILON:
        next_x = x + linear_velocity_m_s * math.cos(yaw_rad) * dt_s
        next_y = y + linear_velocity_m_s * math.sin(yaw_rad) * dt_s
        next_yaw = yaw_rad
    else:
        omega = angular_velocity_rad_s
        next_yaw_raw = yaw_rad + omega * dt_s
        radius = linear_velocity_m_s / omega
        next_x = x + radius * (math.sin(next_yaw_raw) - math.sin(yaw_rad))
        next_y = y - radius * (math.cos(next_yaw_raw) - math.cos(yaw_rad))
        next_yaw = next_yaw_raw
    return next_x, next_y, normalize_angle(next_yaw)


def predict_state_only_trajectory(
    *,
    x: float,
    y: float,
    yaw_rad: float,
    linear_velocity_m_s: float,
    angular_velocity_rad_s: float,
    horizon_s: float,
    step_s: float = DEFAULT_STEP_S,
) -> List[TrajectoryPoint]:
    for name, value in (
        ("x", x),
        ("y", y),
        ("yaw_rad", yaw_rad),
        ("linear_velocity_m_s", linear_velocity_m_s),
        ("angular_velocity_rad_s", angular_velocity_rad_s),
    ):
        _require_finite(name, value)

    points = []
    for offset in _time_offsets(horizon_s, step_s):
        px, py, pyaw = _integrate_constant_twist(
            x,
            y,
            yaw_rad,
            linear_velocity_m_s,
            angular_velocity_rad_s,
            offset,
        )
        points.append(TrajectoryPoint(offset, px, py, pyaw))
    return points


def wheel_commands_to_twist(
    left_wheel_command_rad_s: float,
    right_wheel_command_rad_s: float,
    *,
    wheel_radius_m: float = EPUCK_WHEEL_RADIUS_M,
    axle_length_m: float = EPUCK_AXLE_LENGTH_M,
) -> tuple[float, float]:
    for name, value in (
        ("left_wheel_command_rad_s", left_wheel_command_rad_s),
        ("right_wheel_command_rad_s", right_wheel_command_rad_s),
        ("wheel_radius_m", wheel_radius_m),
        ("axle_length_m", axle_length_m),
    ):
        _require_finite(name, value)
    if wheel_radius_m <= 0:
        raise ValueError("wheel_radius_m must be positive")
    if axle_length_m <= 0:
        raise ValueError("axle_length_m must be positive")

    linear_velocity = wheel_radius_m * 0.5 * (right_wheel_command_rad_s + left_wheel_command_rad_s)
    angular_velocity = wheel_radius_m * (right_wheel_command_rad_s - left_wheel_command_rad_s) / axle_length_m
    return linear_velocity, angular_velocity


def _validate_command_segments(segments: Iterable[CommandSegment], horizon_s: float) -> List[CommandSegment]:
    _validate_horizon_step(horizon_s, DEFAULT_STEP_S)
    ordered = list(segments)
    if not ordered:
        raise ValueError("at least one command segment is required")

    previous_end = 0.0
    for index, segment in enumerate(ordered):
        values = (
            ("start_offset_s", segment.start_offset_s),
            ("end_offset_s", segment.end_offset_s),
            ("left_wheel_command_rad_s", segment.left_wheel_command_rad_s),
            ("right_wheel_command_rad_s", segment.right_wheel_command_rad_s),
        )
        for name, value in values:
            _require_finite(f"segment {index} {name}", value)
        if segment.end_offset_s <= segment.start_offset_s:
            raise ValueError(f"segment {index} end_offset_s must be greater than start_offset_s")
        if index == 0 and abs(segment.start_offset_s) > 1e-9:
            raise ValueError("first command segment must start at 0.0")
        if index > 0 and abs(segment.start_offset_s - previous_end) > 1e-9:
            raise ValueError("command segments must be sorted, contiguous, and non-overlapping")
        previous_end = segment.end_offset_s

    if previous_end + 1e-9 < horizon_s:
        raise ValueError("command segments do not cover the requested horizon")
    return ordered


def _segment_for_interval_midpoint(segments: List[CommandSegment], midpoint_s: float) -> CommandSegment:
    for segment in segments:
        if segment.start_offset_s <= midpoint_s < segment.end_offset_s:
            return segment
    if math.isclose(midpoint_s, segments[-1].end_offset_s):
        return segments[-1]
    raise ValueError(f"no command segment covers time {midpoint_s}")


def predict_command_conditioned_trajectory(
    *,
    x: float,
    y: float,
    yaw_rad: float,
    command_segments: Iterable[CommandSegment],
    horizon_s: float,
    step_s: float = DEFAULT_STEP_S,
    wheel_radius_m: float = EPUCK_WHEEL_RADIUS_M,
    axle_length_m: float = EPUCK_AXLE_LENGTH_M,
) -> List[TrajectoryPoint]:
    for name, value in (("x", x), ("y", y), ("yaw_rad", yaw_rad)):
        _require_finite(name, value)
    _validate_horizon_step(horizon_s, step_s)
    segments = _validate_command_segments(command_segments, horizon_s)

    points: List[TrajectoryPoint] = []
    current_x = x
    current_y = y
    current_yaw = normalize_angle(yaw_rad)
    current_time = 0.0

    for target_time in _time_offsets(horizon_s, step_s):
        while current_time + 1e-12 < target_time:
            segment = _segment_for_interval_midpoint(segments, current_time + 1e-12)
            next_boundary = min(target_time, segment.end_offset_s)
            dt = next_boundary - current_time
            linear_velocity, angular_velocity = wheel_commands_to_twist(
                segment.left_wheel_command_rad_s,
                segment.right_wheel_command_rad_s,
                wheel_radius_m=wheel_radius_m,
                axle_length_m=axle_length_m,
            )
            current_x, current_y, current_yaw = _integrate_constant_twist(
                current_x,
                current_y,
                current_yaw,
                linear_velocity,
                angular_velocity,
                dt,
            )
            current_time = next_boundary
        points.append(TrajectoryPoint(target_time, current_x, current_y, current_yaw))
    return points
