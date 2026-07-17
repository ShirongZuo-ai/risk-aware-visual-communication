"""Minimal fixed-sequence e-puck motion, camera capture, and CSV logger."""

import csv
import math
import os
from pathlib import Path

from controller import Supervisor


CAMERA = "camera"
LEFT_WHEEL = "left wheel motor"
RIGHT_WHEEL = "right wheel motor"

STRAIGHT_UNTIL = 1.2
LEFT_TURN_UNTIL = 2.2
RIGHT_TURN_UNTIL = 3.2
STOP_UNTIL = 3.7
MIN_FRAMES = 100

STRAIGHT_SPEED = 2.0
TURN_SPEED = 1.5
IMAGE_QUALITY = 100
CSV_FIELDS = [
    "episode_id",
    "frame_index",
    "sim_time_s",
    "sim_time_ms",
    "image_path",
    "motion_phase",
    "robot_x",
    "robot_y",
    "robot_z",
    "yaw_rad",
    "linear_velocity_m_s",
    "angular_velocity_rad_s",
    "left_wheel_command_rad_s",
    "right_wheel_command_rad_s",
    "camera_width",
    "camera_height",
]


class ValidationTrace:
    def __init__(self):
        trace_path = (
            os.environ.get("M1D_VALIDATION_TRACE")
            or os.environ.get("M1C_VALIDATION_TRACE")
            or os.environ.get("M1B_VALIDATION_TRACE")
        )
        self.path = Path(trace_path) if trace_path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def write(self, message):
        print(message, flush=True)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(f"{message}\n")


class EpisodeWriter:
    def __init__(self, controller_path):
        self.project_root = controller_path.resolve().parents[3]
        self.frames_root = self.project_root / "data" / "frames" / "m1d"
        self.logs_root = self.project_root / "data" / "logs" / "m1d"
        self.frames_root.mkdir(parents=True, exist_ok=True)
        self.logs_root.mkdir(parents=True, exist_ok=True)

        self.episode_id = self._next_episode_id()
        self.output_dir = self.frames_root / self.episode_id
        self.output_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.logs_root / f"{self.episode_id}.csv"
        self.csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=CSV_FIELDS)
        self.csv_writer.writeheader()
        self.csv_file.flush()
        self.frame_count = 0

    def _next_episode_id(self):
        used_indices = set()
        for path in self.frames_root.glob("episode_*"):
            if path.is_dir():
                used_indices.add(self._episode_index(path.name))
        for path in self.logs_root.glob("episode_*.csv"):
            used_indices.add(self._episode_index(path.stem))
        used_indices.discard(None)
        next_index = max(used_indices, default=0) + 1
        return f"episode_{next_index:04d}"

    @staticmethod
    def _episode_index(name):
        prefix = "episode_"
        if not name.startswith(prefix):
            return None
        try:
            return int(name[len(prefix):])
        except ValueError:
            return None

    def save_frame_and_row(
        self,
        camera,
        elapsed_seconds,
        phase,
        left_speed,
        right_speed,
        position,
        yaw,
        linear_velocity,
        angular_velocity,
        camera_width,
        camera_height,
    ):
        frame_index = self.frame_count
        time_ms = int(round(elapsed_seconds * 1000.0))
        frame_path = self.output_dir / f"frame_{frame_index:06d}_t{time_ms:07d}.png"
        result = camera.saveImage(str(frame_path), IMAGE_QUALITY)
        if result != 0:
            raise RuntimeError(f"camera.saveImage failed for {frame_path} with code {result}")

        image_path = frame_path.relative_to(self.project_root).as_posix()
        self.csv_writer.writerow(
            {
                "episode_id": self.episode_id,
                "frame_index": frame_index,
                "sim_time_s": f"{elapsed_seconds:.6f}",
                "sim_time_ms": time_ms,
                "image_path": image_path,
                "motion_phase": phase,
                "robot_x": f"{position[0]:.9f}",
                "robot_y": f"{position[1]:.9f}",
                "robot_z": f"{position[2]:.9f}",
                "yaw_rad": f"{yaw:.9f}",
                "linear_velocity_m_s": f"{linear_velocity:.9f}",
                "angular_velocity_rad_s": f"{angular_velocity:.9f}",
                "left_wheel_command_rad_s": f"{left_speed:.6f}",
                "right_wheel_command_rad_s": f"{right_speed:.6f}",
                "camera_width": camera_width,
                "camera_height": camera_height,
            }
        )
        self.csv_file.flush()
        self.frame_count += 1

    def close(self):
        self.csv_file.flush()
        self.csv_file.close()


def command_for_time(elapsed_seconds):
    if elapsed_seconds < STRAIGHT_UNTIL:
        return "straight", STRAIGHT_SPEED, STRAIGHT_SPEED
    if elapsed_seconds < LEFT_TURN_UNTIL:
        return "left_turn", -TURN_SPEED, TURN_SPEED
    if elapsed_seconds < RIGHT_TURN_UNTIL:
        return "right_turn", TURN_SPEED, -TURN_SPEED
    return "stop", 0.0, 0.0


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_orientation(orientation):
    # Webots returns a row-major 3x3 orientation matrix. The e-puck forward
    # axis is local +X, so yaw around world +Z is atan2(row1_col0, row0_col0).
    return normalize_angle(math.atan2(orientation[3], orientation[0]))


def ground_speed_from_velocity(velocity):
    return math.hypot(velocity[0], velocity[1])


def main():
    trace = ValidationTrace()
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    episode = EpisodeWriter(Path(__file__))
    self_node = robot.getSelf()

    camera = robot.getDevice(CAMERA)
    camera.enable(timestep)
    camera_width = camera.getWidth()
    camera_height = camera.getHeight()

    left_motor = robot.getDevice(LEFT_WHEEL)
    right_motor = robot.getDevice(RIGHT_WHEEL)
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    trace.write("minimal_epuck_motion: start")
    trace.write(
        "sequence: 0.0-1.2s straight, 1.2-2.2s left_turn, "
        "2.2-3.2s right_turn, 3.2s+ stop"
    )
    trace.write(
        f"camera={CAMERA} width={camera_width} height={camera_height} "
        f"sampling_period_ms={timestep} output={episode.output_dir}"
    )
    trace.write(
        f"episode_id={episode.episode_id} csv={episode.csv_path} "
        "ground_plane=x_y vertical_axis=z yaw=atan2(orientation[3],orientation[0])"
    )

    previous_phase = None

    try:
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
            yaw = yaw_from_orientation(orientation)
            linear_velocity = ground_speed_from_velocity(velocity)
            angular_velocity = velocity[5]

            episode.save_frame_and_row(
                camera,
                elapsed,
                phase,
                left_speed,
                right_speed,
                position,
                yaw,
                linear_velocity,
                angular_velocity,
                camera_width,
                camera_height,
            )

            if elapsed >= STOP_UNTIL and episode.frame_count >= MIN_FRAMES:
                left_motor.setVelocity(0.0)
                right_motor.setVelocity(0.0)
                trace.write(f"frames_saved={episode.frame_count}")
                trace.write(f"csv_rows={episode.frame_count}")
                trace.write("minimal_epuck_motion: complete")
                break
    finally:
        episode.close()

    robot.cleanup()


if __name__ == "__main__":
    main()
