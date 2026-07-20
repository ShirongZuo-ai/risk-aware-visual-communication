"""Method-independent snapshot selection and command-rollout helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from navigation.trajectory_prediction import CommandSegment, TrajectoryPoint, predict_command_conditioned_trajectory, predict_state_only_trajectory
from simulator.m5e_scenarios import ScenarioConfig, WheelCommandPhase


@dataclass(frozen=True)
class SnapshotCrossing:
    snapshot_index: int
    target_progress: float
    actual_progress: float
    simulation_time_s: float
    webots_step: int


def reference_progress(config: ScenarioConfig, simulation_time_s: float) -> float:
    return min(1.0, max(0.0, simulation_time_s / config.duration_seconds))


def command_phase_at(config: ScenarioConfig, simulation_time_s: float) -> WheelCommandPhase:
    for phase in config.command_schedule:
        if phase.start_s <= simulation_time_s < phase.end_s:
            return phase
    return WheelCommandPhase("stop", config.duration_seconds, float("inf"), 0.0, 0.0)


def future_command_segments(config: ScenarioConfig, simulation_time_s: float) -> list[CommandSegment]:
    horizon_end = simulation_time_s + config.trajectory_horizon_s
    segments: list[CommandSegment] = []
    for phase in config.command_schedule:
        start = max(phase.start_s, simulation_time_s)
        end = min(phase.end_s, horizon_end)
        if end > start:
            segments.append(CommandSegment(start - simulation_time_s, end - simulation_time_s, phase.left_rad_s, phase.right_rad_s))
    covered = segments[-1].end_offset_s if segments else 0.0
    if covered < config.trajectory_horizon_s:
        segments.append(CommandSegment(covered, config.trajectory_horizon_s, 0.0, 0.0))
    return segments


def next_crossing(config: ScenarioConfig, completed_indices: set[int], simulation_time_s: float, webots_step: int) -> SnapshotCrossing | None:
    progress = reference_progress(config, simulation_time_s)
    for index, target in enumerate(config.snapshot_progress_targets):
        if index not in completed_indices and progress + 1e-12 >= target:
            return SnapshotCrossing(index, target, progress, simulation_time_s, webots_step)
    return None


def build_trajectories(config: ScenarioConfig, snapshot_state: dict[str, float], simulation_time_s: float) -> tuple[list[TrajectoryPoint], list[TrajectoryPoint]]:
    planned = predict_command_conditioned_trajectory(
        x=snapshot_state["x"], y=snapshot_state["y"], yaw_rad=snapshot_state["yaw_rad"],
        command_segments=future_command_segments(config, simulation_time_s),
        horizon_s=config.trajectory_horizon_s, step_s=0.032,
    )
    state = predict_state_only_trajectory(
        x=snapshot_state["x"], y=snapshot_state["y"], yaw_rad=snapshot_state["yaw_rad"],
        linear_velocity_m_s=snapshot_state["linear_velocity_m_s"], angular_velocity_rad_s=snapshot_state["angular_velocity_rad_s"],
        horizon_s=config.trajectory_horizon_s, step_s=0.032,
    )
    return planned, state


def yaw_change(points: Iterable[TrajectoryPoint]) -> float:
    values = list(points)
    if not values:
        raise ValueError("trajectory must not be empty")
    return math.atan2(math.sin(values[-1].yaw_rad - values[0].yaw_rad), math.cos(values[-1].yaw_rad - values[0].yaw_rad))
