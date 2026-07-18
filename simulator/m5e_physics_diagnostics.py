"""Pure geometry helpers for optional M5E Webots physics diagnostics."""

from __future__ import annotations

import math
from pathlib import Path
from collections.abc import Mapping, Sequence


PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE = "M5E_PHYSICS_DIAGNOSTICS_PATH"
EPUCK_BODY_RADIUS_M = 0.037
EPUCK_BODY_BOTTOM_OFFSET_M = 0.0025
EPUCK_BODY_TOP_OFFSET_M = 0.0475


def diagnostics_path(environment: Mapping[str, str], project_root: Path) -> Path | None:
    value = environment.get(PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE)
    if not value:
        return None
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE} must be project-relative")
    resolved = (project_root / relative).resolve()
    if project_root.resolve() not in resolved.parents:
        raise ValueError(f"{PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE} must remain inside the project")
    return resolved


def roll_pitch_yaw(orientation: Sequence[float]) -> tuple[float, float, float]:
    if len(orientation) != 9:
        raise ValueError("orientation must contain nine row-major values")
    pitch = math.asin(max(-1.0, min(1.0, -float(orientation[6]))))
    roll = math.atan2(float(orientation[7]), float(orientation[8]))
    yaw = math.atan2(float(orientation[3]), float(orientation[0]))
    return roll, pitch, yaw


def robot_obstacle_relation(
    robot_x: float,
    robot_y: float,
    robot_z: float,
    obstacle_center: Sequence[float],
    obstacle_size: Sequence[float],
) -> dict[str, object]:
    cx, cy, cz = (float(value) for value in obstacle_center)
    sx, sy, sz = (float(value) for value in obstacle_size)
    obstacle_min = (cx - sx * 0.5, cy - sy * 0.5, cz - sz * 0.5)
    obstacle_max = (cx + sx * 0.5, cy + sy * 0.5, cz + sz * 0.5)
    robot_min = (
        robot_x - EPUCK_BODY_RADIUS_M,
        robot_y - EPUCK_BODY_RADIUS_M,
        robot_z + EPUCK_BODY_BOTTOM_OFFSET_M,
    )
    robot_max = (
        robot_x + EPUCK_BODY_RADIUS_M,
        robot_y + EPUCK_BODY_RADIUS_M,
        robot_z + EPUCK_BODY_TOP_OFFSET_M,
    )
    dx = max(obstacle_min[0] - robot_x, 0.0, robot_x - obstacle_max[0])
    dy = max(obstacle_min[1] - robot_y, 0.0, robot_y - obstacle_max[1])
    center_to_aabb_m = math.hypot(dx, dy)
    z_overlap = robot_min[2] <= obstacle_max[2] and robot_max[2] >= obstacle_min[2]
    aabb_overlap = z_overlap and all(
        robot_min[index] <= obstacle_max[index] and robot_max[index] >= obstacle_min[index]
        for index in range(2)
    )
    cylinder_box_overlap = z_overlap and center_to_aabb_m <= EPUCK_BODY_RADIUS_M
    return {
        "center_to_aabb_m": center_to_aabb_m,
        "body_surface_clearance_m": center_to_aabb_m - EPUCK_BODY_RADIUS_M,
        "aabb_overlap": aabb_overlap,
        "cylinder_box_overlap": cylinder_box_overlap,
        "robot_aabb_min": robot_min,
        "robot_aabb_max": robot_max,
        "obstacle_aabb_min": obstacle_min,
        "obstacle_aabb_max": obstacle_max,
    }
