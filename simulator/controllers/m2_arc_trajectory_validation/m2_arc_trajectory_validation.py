"""Milestone 2R forward-arc validation controller."""

import csv
import math
import os
from pathlib import Path

from controller import Supervisor


LEFT_WHEEL = "left wheel motor"
RIGHT_WHEEL = "right wheel motor"

STRAIGHT_UNTIL = 4.0
LEFT_ARC_UNTIL = 8.0
RIGHT_ARC_UNTIL = 12.0
STOP_UNTIL = 16.0

CSV_FIELDS = [
    "episode_id",
    "sim_time_s",
    "sim_time_ms",
    "motion_phase",
    "robot_x",
    "robot_y",
    "robot_z",
    "yaw_rad",
    "linear_velocity_m_s",
    "angular_velocity_rad_s",
    "left_wheel_command_rad_s",
    "right_wheel_command_rad_s",
]


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_orientation(orientation):
    return normalize_angle(math.atan2(orientation[3], orientation[0]))


def command_for_time(elapsed_seconds):
    if elapsed_seconds < STRAIGHT_UNTIL:
        return "stable_straight", 2.0, 2.0
    if elapsed_seconds < LEFT_ARC_UNTIL:
        return "stable_forward_left_arc", 1.0, 2.0
    if elapsed_seconds < RIGHT_ARC_UNTIL:
        return "stable_forward_right_arc", 2.0, 1.0
    return "stable_stop", 0.0, 0.0


class Trace:
    def __init__(self):
        trace_path = os.environ.get("M2_ARC_VALIDATION_TRACE")
        self.path = Path(trace_path) if trace_path else None
        self.file = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.file = self.path.open("w", encoding="utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def write(self, message):
        print(message, flush=True)
        if self.file:
            self.file.write(f"{message}\n")
            self.file.flush()

    def close(self):
        if self.file and not self.file.closed:
            self.file.flush()
            self.file.close()


class EpisodeLog:
    def __init__(self, controller_path):
        self.project_root = controller_path.resolve().parents[3]
        self.logs_root = self.project_root / "data" / "logs" / "m2"
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self.episode_id = self._next_episode_id()
        self.csv_path = self.logs_root / f"trajectory_validation_{self.episode_id}.csv"
        self.file = self.csv_path.open("x", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=CSV_FIELDS)
        self.writer.writeheader()
        self.file.flush()
        self.rows = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _next_episode_id(self):
        indices = []
        for path in self.logs_root.glob("trajectory_validation_episode_*.csv"):
            suffix = path.stem.removeprefix("trajectory_validation_episode_")
            try:
                indices.append(int(suffix))
            except ValueError:
                pass
        return f"episode_{max(indices, default=0) + 1:04d}"

    def write_row(self, elapsed, phase, position, yaw, velocity, left_speed, right_speed):
        self.writer.writerow(
            {
                "episode_id": self.episode_id,
                "sim_time_s": f"{elapsed:.6f}",
                "sim_time_ms": int(round(elapsed * 1000.0)),
                "motion_phase": phase,
                "robot_x": f"{position[0]:.9f}",
                "robot_y": f"{position[1]:.9f}",
                "robot_z": f"{position[2]:.9f}",
                "yaw_rad": f"{yaw:.9f}",
                "linear_velocity_m_s": f"{math.hypot(velocity[0], velocity[1]):.9f}",
                "angular_velocity_rad_s": f"{velocity[5]:.9f}",
                "left_wheel_command_rad_s": f"{left_speed:.6f}",
                "right_wheel_command_rad_s": f"{right_speed:.6f}",
            }
        )
        self.rows += 1
        self.file.flush()

    def close(self):
        self.file.flush()
        self.file.close()


def main():
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    self_node = robot.getSelf()

    left_motor = robot.getDevice(LEFT_WHEEL)
    right_motor = robot.getDevice(RIGHT_WHEEL)
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    with Trace() as trace, EpisodeLog(Path(__file__)) as log:
        trace.write("m2_arc_trajectory_validation: start")
        trace.write(f"episode_id={log.episode_id} csv={log.csv_path} timestep_ms={timestep}")
        trace.write(
            "sequence: 0-4s straight left=2 right=2; "
            "4-8s forward-left-arc left=1 right=2; "
            "8-12s forward-right-arc left=2 right=1; 12-16s stop"
        )

        previous_phase = None
        while robot.step(timestep) != -1:
            elapsed = robot.getTime()
            phase, left_speed, right_speed = command_for_time(elapsed)
            if phase != previous_phase:
                trace.write(
                    f"phase={phase} t={elapsed:.3f}s "
                    f"left={left_speed:.2f} right={right_speed:.2f}"
                )
                previous_phase = phase

            left_motor.setVelocity(left_speed)
            right_motor.setVelocity(right_speed)

            position = self_node.getPosition()
            orientation = self_node.getOrientation()
            velocity = self_node.getVelocity()
            log.write_row(
                elapsed,
                phase,
                position,
                yaw_from_orientation(orientation),
                velocity,
                left_speed,
                right_speed,
            )

            if elapsed >= STOP_UNTIL:
                left_motor.setVelocity(0.0)
                right_motor.setVelocity(0.0)
                trace.write(f"csv_rows={log.rows}")
                trace.write("m2_arc_trajectory_validation: complete")
                break


if __name__ == "__main__":
    main()
