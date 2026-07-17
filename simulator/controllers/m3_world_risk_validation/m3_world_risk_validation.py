"""Milestone 3C Webots world-risk validation controller."""

from __future__ import annotations

import csv
import math
from pathlib import Path
import sys

from controller import Supervisor


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from navigation.trajectory_prediction import (  # noqa: E402
    CommandSegment,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
)
from risk_map.trajectory_obstacle_risk import analyze_dual_trajectory_obstacle  # noqa: E402
from simulator.adapters.webots_obstacle_adapter import read_static_box_obstacle  # noqa: E402
from simulator.m3c_config import (  # noqa: E402
    ANALYSIS_TIME_S,
    COMMAND_SCHEDULE,
    OBSTACLE_SPECS,
    PREDICTION_HORIZON_S,
    PREDICTION_STEP_S,
    RISK_PARAMETERS,
    command_for_time,
)


LEFT_WHEEL = "left wheel motor"
RIGHT_WHEEL = "right wheel motor"

CSV_FIELDS = [
    "episode_id",
    "analysis_time_s",
    "prediction_horizon_s",
    "prediction_step_s",
    "obstacle_id",
    "obstacle_def_name",
    "obstacle_center_x",
    "obstacle_center_y",
    "obstacle_size_x",
    "obstacle_size_y",
    "obstacle_min_x",
    "obstacle_max_x",
    "obstacle_min_y",
    "obstacle_max_y",
    "planned_minimum_centerline_distance_m",
    "planned_minimum_clearance_m",
    "planned_closest_time_s",
    "planned_enters_corridor",
    "planned_first_corridor_entry_time_s",
    "planned_corridor_overlap_duration_s",
    "planned_spatial_score",
    "planned_temporal_score",
    "planned_risk_score",
    "state_minimum_centerline_distance_m",
    "state_minimum_clearance_m",
    "state_closest_time_s",
    "state_enters_corridor",
    "state_first_corridor_entry_time_s",
    "state_corridor_overlap_duration_s",
    "state_spatial_score",
    "state_temporal_score",
    "state_risk_score",
    "trajectory_disagreement_m",
    "combined_risk_score",
    "current_robot_x",
    "current_robot_y",
    "current_robot_yaw_rad",
    "current_linear_velocity_m_s",
    "current_angular_velocity_rad_s",
]


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_orientation(orientation) -> float:
    return normalize_angle(math.atan2(orientation[3], orientation[0]))


def future_command_segments(analysis_time_s: float) -> list[CommandSegment]:
    segments: list[CommandSegment] = []
    horizon_end = analysis_time_s + PREDICTION_HORIZON_S
    for phase in COMMAND_SCHEDULE:
        start = max(phase.start_s, analysis_time_s)
        end = min(phase.end_s, horizon_end)
        if end <= start:
            continue
        segments.append(
            CommandSegment(
                start_offset_s=start - analysis_time_s,
                end_offset_s=end - analysis_time_s,
                left_wheel_command_rad_s=phase.left_rad_s,
                right_wheel_command_rad_s=phase.right_rad_s,
            )
        )
    if not segments or segments[-1].end_offset_s < PREDICTION_HORIZON_S:
        start = segments[-1].end_offset_s if segments else 0.0
        segments.append(CommandSegment(start, PREDICTION_HORIZON_S, 0.0, 0.0))
    return segments


def format_float(value: float) -> str:
    return f"{value:.9f}"


def format_optional(value: float | None) -> str:
    if value is None:
        return ""
    return format_float(value)


def format_bool(value: bool) -> str:
    return "true" if value else "false"


class Trace:
    def __init__(self, path: Path):
        self.path = path
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("x", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def write(self, message: str) -> None:
        print(message, flush=True)
        if self.file:
            self.file.write(f"{message}\n")
            self.file.flush()

    def close(self) -> None:
        if self.file and not self.file.closed:
            self.file.flush()
            self.file.close()


class RiskEpisodeLog:
    def __init__(self):
        self.logs_root = PROJECT_ROOT / "data" / "logs" / "m3"
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self.episode_id = self._next_episode_id()
        self.csv_path = self.logs_root / f"risk_validation_{self.episode_id}.csv"
        self.trace_path = self.logs_root / f"risk_validation_{self.episode_id}_trace.txt"
        self.file = self.csv_path.open("x", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=CSV_FIELDS)
        self.writer.writeheader()
        self.rows = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _next_episode_id(self) -> str:
        indices = []
        for path in self.logs_root.glob("risk_validation_episode_*.csv"):
            suffix = path.stem.removeprefix("risk_validation_episode_")
            try:
                indices.append(int(suffix))
            except ValueError:
                pass
        return f"episode_{max(indices, default=0) + 1:04d}"

    def write_row(self, row: dict[str, str]) -> None:
        self.writer.writerow(row)
        self.rows += 1
        self.file.flush()

    def close(self) -> None:
        if not self.file.closed:
            self.file.flush()
            self.file.close()


def result_row(
    *,
    episode_id: str,
    analysis_time_s: float,
    obstacle_def_name: str,
    obstacle,
    result,
    current_x: float,
    current_y: float,
    current_yaw: float,
    current_linear_velocity: float,
    current_angular_velocity: float,
) -> dict[str, str]:
    planned = result.planned_result
    state = result.state_result
    return {
        "episode_id": episode_id,
        "analysis_time_s": format_float(analysis_time_s),
        "prediction_horizon_s": format_float(PREDICTION_HORIZON_S),
        "prediction_step_s": format_float(PREDICTION_STEP_S),
        "obstacle_id": obstacle.obstacle_id,
        "obstacle_def_name": obstacle_def_name,
        "obstacle_center_x": format_float(obstacle.center_x),
        "obstacle_center_y": format_float(obstacle.center_y),
        "obstacle_size_x": format_float(obstacle.size_x),
        "obstacle_size_y": format_float(obstacle.size_y),
        "obstacle_min_x": format_float(obstacle.min_x),
        "obstacle_max_x": format_float(obstacle.max_x),
        "obstacle_min_y": format_float(obstacle.min_y),
        "obstacle_max_y": format_float(obstacle.max_y),
        "planned_minimum_centerline_distance_m": format_float(planned.minimum_centerline_distance_m),
        "planned_minimum_clearance_m": format_float(planned.minimum_clearance_m),
        "planned_closest_time_s": format_float(planned.closest_time_s),
        "planned_enters_corridor": format_bool(planned.enters_corridor),
        "planned_first_corridor_entry_time_s": format_optional(planned.first_corridor_entry_time_s),
        "planned_corridor_overlap_duration_s": format_float(planned.corridor_overlap_duration_s),
        "planned_spatial_score": format_float(planned.spatial_score),
        "planned_temporal_score": format_float(planned.temporal_score),
        "planned_risk_score": format_float(planned.risk_score),
        "state_minimum_centerline_distance_m": format_float(state.minimum_centerline_distance_m),
        "state_minimum_clearance_m": format_float(state.minimum_clearance_m),
        "state_closest_time_s": format_float(state.closest_time_s),
        "state_enters_corridor": format_bool(state.enters_corridor),
        "state_first_corridor_entry_time_s": format_optional(state.first_corridor_entry_time_s),
        "state_corridor_overlap_duration_s": format_float(state.corridor_overlap_duration_s),
        "state_spatial_score": format_float(state.spatial_score),
        "state_temporal_score": format_float(state.temporal_score),
        "state_risk_score": format_float(state.risk_score),
        "trajectory_disagreement_m": format_float(result.trajectory_disagreement_m),
        "combined_risk_score": format_float(result.combined_risk_score),
        "current_robot_x": format_float(current_x),
        "current_robot_y": format_float(current_y),
        "current_robot_yaw_rad": format_float(current_yaw),
        "current_linear_velocity_m_s": format_float(current_linear_velocity),
        "current_angular_velocity_rad_s": format_float(current_angular_velocity),
    }


def main() -> None:
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    self_node = robot.getSelf()

    left_motor = robot.getDevice(LEFT_WHEEL)
    right_motor = robot.getDevice(RIGHT_WHEEL)
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    with RiskEpisodeLog() as log, Trace(log.trace_path) as trace:
        trace.write("m3_world_risk_validation: start")
        trace.write(f"episode_id={log.episode_id} csv={log.csv_path} timestep_ms={timestep}")
        trace.write(
            f"analysis_time_s={ANALYSIS_TIME_S:.3f} horizon_s={PREDICTION_HORIZON_S:.3f} "
            f"step_s={PREDICTION_STEP_S:.3f}"
        )

        while robot.step(timestep) != -1:
            elapsed = robot.getTime()
            phase = command_for_time(elapsed)
            left_motor.setVelocity(phase.left_rad_s)
            right_motor.setVelocity(phase.right_rad_s)

            if elapsed + 1e-12 < ANALYSIS_TIME_S:
                continue

            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

            position = self_node.getPosition()
            orientation = self_node.getOrientation()
            velocity = self_node.getVelocity()
            current_yaw = yaw_from_orientation(orientation)
            current_linear_velocity = math.hypot(velocity[0], velocity[1])
            current_angular_velocity = velocity[5]
            trace.write(
                "current_state "
                f"x={position[0]:.9f} y={position[1]:.9f} yaw={current_yaw:.9f} "
                f"v={current_linear_velocity:.9f} omega={current_angular_velocity:.9f}"
            )

            planned = predict_command_conditioned_trajectory(
                x=position[0],
                y=position[1],
                yaw_rad=current_yaw,
                command_segments=future_command_segments(ANALYSIS_TIME_S),
                horizon_s=PREDICTION_HORIZON_S,
                step_s=PREDICTION_STEP_S,
            )
            state = predict_state_only_trajectory(
                x=position[0],
                y=position[1],
                yaw_rad=current_yaw,
                linear_velocity_m_s=current_linear_velocity,
                angular_velocity_rad_s=current_angular_velocity,
                horizon_s=PREDICTION_HORIZON_S,
                step_s=PREDICTION_STEP_S,
            )
            trace.write(f"planned_points={len(planned)} state_points={len(state)}")

            for spec in OBSTACLE_SPECS:
                obstacle = read_static_box_obstacle(robot, spec.def_name, spec.obstacle_id)
                result = analyze_dual_trajectory_obstacle(planned, state, obstacle, RISK_PARAMETERS)
                log.write_row(
                    result_row(
                        episode_id=log.episode_id,
                        analysis_time_s=elapsed,
                        obstacle_def_name=spec.def_name,
                        obstacle=obstacle,
                        result=result,
                        current_x=position[0],
                        current_y=position[1],
                        current_yaw=current_yaw,
                        current_linear_velocity=current_linear_velocity,
                        current_angular_velocity=current_angular_velocity,
                    )
                )
                trace.write(
                    f"{spec.obstacle_id} "
                    f"planned_clearance={result.planned_result.minimum_clearance_m:.9f} "
                    f"planned_ttc={result.planned_result.first_corridor_entry_time_s} "
                    f"planned_risk={result.planned_result.risk_score:.9f} "
                    f"state_clearance={result.state_result.minimum_clearance_m:.9f} "
                    f"state_ttc={result.state_result.first_corridor_entry_time_s} "
                    f"state_risk={result.state_result.risk_score:.9f} "
                    f"combined_risk={result.combined_risk_score:.9f}"
                )

            trace.write(f"trajectory_disagreement={result.trajectory_disagreement_m:.9f}")
            trace.write(f"csv_rows={log.rows}")
            trace.write("m3_world_risk_validation: complete")
            return

        left_motor.setVelocity(0.0)
        right_motor.setVelocity(0.0)
        trace.write("m3_world_risk_validation: step_returned_minus_one")


if __name__ == "__main__":
    main()
