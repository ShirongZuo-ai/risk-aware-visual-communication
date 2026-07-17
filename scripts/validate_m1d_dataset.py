"""Validate Milestone 1D image/CSV alignment using only the standard library."""

import argparse
import csv
import math
import struct
import sys
from pathlib import Path


REQUIRED_FIELDS = [
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

NUMERIC_FIELDS = [
    "sim_time_s",
    "sim_time_ms",
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


def fail(message):
    print(f"FAIL: {message}")
    return 1


def ok(message):
    print(f"OK: {message}")


def find_project_root():
    return Path(__file__).resolve().parents[1]


def latest_csv(project_root):
    logs_root = project_root / "data" / "logs" / "m1d"
    candidates = sorted(logs_root.glob("episode_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No episode CSV found in {logs_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_png_size(path):
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a valid PNG")
    ihdr_len = struct.unpack(">I", data[8:12])[0]
    chunk_type = data[12:16]
    if ihdr_len != 13 or chunk_type != b"IHDR":
        raise ValueError(f"{path} has no valid IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def finite_float(value, field, row_index):
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_index}: {field} is not numeric: {value!r}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"row {row_index}: {field} is not finite: {value!r}")
    return parsed


def angle_delta(a, b):
    return math.atan2(math.sin(b - a), math.cos(b - a))


def validate(csv_path):
    project_root = find_project_root()
    csv_path = csv_path.resolve()
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            return fail(f"missing CSV fields: {missing}")
        rows = list(reader)

    if not rows:
        return fail("CSV has no data rows")
    ok(f"CSV rows: {len(rows)}")

    episode_ids = {row["episode_id"] for row in rows}
    if len(episode_ids) != 1:
        return fail(f"expected one episode_id, found {sorted(episode_ids)}")
    episode_id = next(iter(episode_ids))
    ok(f"episode_id: {episode_id}")

    frame_indices = []
    sim_times = []
    phases = set()
    image_paths = []
    numeric_rows = []

    for row_index, row in enumerate(rows):
        try:
            frame_index = int(row["frame_index"])
        except ValueError:
            return fail(f"row {row_index}: frame_index is not an int")
        frame_indices.append(frame_index)

        numeric = {}
        for field in NUMERIC_FIELDS:
            try:
                numeric[field] = finite_float(row[field], field, row_index)
            except ValueError as exc:
                return fail(str(exc))
        numeric_rows.append(numeric)
        sim_times.append(numeric["sim_time_s"])
        phases.add(row["motion_phase"])

        image_path = Path(row["image_path"])
        if image_path.is_absolute():
            return fail(f"row {row_index}: image_path is absolute: {image_path}")
        if "Downloads" in image_path.parts:
            return fail(f"row {row_index}: image_path contains Downloads: {image_path}")
        resolved_image = project_root / image_path
        if not resolved_image.exists():
            return fail(f"row {row_index}: missing image {image_path}")
        if resolved_image.stat().st_size == 0:
            return fail(f"row {row_index}: zero-byte image {image_path}")
        try:
            width, height = read_png_size(resolved_image)
        except ValueError as exc:
            return fail(str(exc))
        if (width, height) != (160, 120):
            return fail(f"row {row_index}: image size is {width}x{height}, expected 160x120")
        if (numeric["camera_width"], numeric["camera_height"]) != (160.0, 120.0):
            return fail(f"row {row_index}: CSV camera size mismatch")
        image_paths.append(resolved_image)

    expected_indices = list(range(len(rows)))
    if frame_indices != expected_indices:
        return fail("frame_index values are not continuous from 0")
    ok("frame_index continuous from 0")

    if any(b <= a for a, b in zip(sim_times, sim_times[1:])):
        return fail("sim_time_s is not strictly increasing")
    ok("sim_time_s strictly increasing")

    frame_files = sorted((project_root / "data" / "frames" / "m1d" / episode_id).glob("frame_*.png"))
    if len(frame_files) != len(rows):
        return fail(f"image count {len(frame_files)} != CSV row count {len(rows)}")
    if sorted(image_paths) != frame_files:
        return fail("CSV image paths do not exactly match episode frame files")
    ok(f"image count matches CSV row count: {len(frame_files)}")

    required_phases = {"straight", "left_turn", "right_turn", "stop"}
    if not required_phases.issubset(phases):
        return fail(f"missing motion phases: {sorted(required_phases - phases)}")
    ok("all motion phases present")

    straight_rows = [(row, numeric) for row, numeric in zip(rows, numeric_rows) if row["motion_phase"] == "straight"]
    left_rows = [(row, numeric) for row, numeric in zip(rows, numeric_rows) if row["motion_phase"] == "left_turn"]
    right_rows = [(row, numeric) for row, numeric in zip(rows, numeric_rows) if row["motion_phase"] == "right_turn"]
    stop_rows = [(row, numeric) for row, numeric in zip(rows, numeric_rows) if row["motion_phase"] == "stop"]

    sx0, sy0 = straight_rows[0][1]["robot_x"], straight_rows[0][1]["robot_y"]
    sx1, sy1 = straight_rows[-1][1]["robot_x"], straight_rows[-1][1]["robot_y"]
    straight_distance = math.hypot(sx1 - sx0, sy1 - sy0)
    if straight_distance <= 0.005:
        return fail(f"straight phase displacement too small: {straight_distance:.6f} m")
    ok(f"straight phase displacement: {straight_distance:.6f} m")

    left_yaw_delta = angle_delta(left_rows[0][1]["yaw_rad"], left_rows[-1][1]["yaw_rad"])
    right_yaw_delta = angle_delta(right_rows[0][1]["yaw_rad"], right_rows[-1][1]["yaw_rad"])
    if abs(left_yaw_delta) <= 0.02:
        return fail(f"left_turn yaw change too small: {left_yaw_delta:.6f} rad")
    if abs(right_yaw_delta) <= 0.02:
        return fail(f"right_turn yaw change too small: {right_yaw_delta:.6f} rad")
    ok(f"left_turn yaw delta: {left_yaw_delta:.6f} rad")
    ok(f"right_turn yaw delta: {right_yaw_delta:.6f} rad")

    left_avg_angular = sum(row[1]["angular_velocity_rad_s"] for row in left_rows) / len(left_rows)
    right_avg_angular = sum(row[1]["angular_velocity_rad_s"] for row in right_rows) / len(right_rows)
    if left_avg_angular * right_avg_angular >= 0:
        return fail(
            "left_turn and right_turn angular velocity averages do not have opposite signs: "
            f"{left_avg_angular:.6f}, {right_avg_angular:.6f}"
        )
    ok(f"turn angular velocity signs oppose: left={left_avg_angular:.6f}, right={right_avg_angular:.6f}")

    tail = stop_rows[-10:] if len(stop_rows) >= 10 else stop_rows
    max_tail_linear = max(row[1]["linear_velocity_m_s"] for row in tail)
    max_tail_angular = max(abs(row[1]["angular_velocity_rad_s"]) for row in tail)
    if max_tail_linear > 0.03 or max_tail_angular > 0.25:
        return fail(
            "stop phase tail did not settle near zero: "
            f"linear={max_tail_linear:.6f}, angular={max_tail_angular:.6f}"
        )
    ok(f"stop tail near zero: linear<={max_tail_linear:.6f}, angular<={max_tail_angular:.6f}")

    ok("validation passed")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", help="CSV path; defaults to latest data/logs/m1d/episode_*.csv")
    args = parser.parse_args()

    project_root = find_project_root()
    try:
        csv_path = Path(args.csv_path) if args.csv_path else latest_csv(project_root)
    except FileNotFoundError as exc:
        return fail(str(exc))

    print(f"Validating {csv_path}")
    return validate(csv_path)


if __name__ == "__main__":
    sys.exit(main())
