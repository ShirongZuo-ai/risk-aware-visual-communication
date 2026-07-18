"""Milestone 4C Webots camera-projection validation controller."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys

from controller import Supervisor


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from perception.camera_models import ProjectedObstacle  # noqa: E402
from perception.camera_projection import project_obstacle_box  # noqa: E402
from simulator.adapters.webots_camera_adapter import (  # noqa: E402
    read_camera_snapshot,
    read_static_box_3d,
    save_camera_frame,
    write_metadata_json,
)
from simulator.m4c_config import (  # noqa: E402
    CAMERA_DEVICE_NAME,
    EPISODE_PREFIX,
    EXPECTED_CAMERA_HEIGHT_PX,
    EXPECTED_CAMERA_WIDTH_PX,
    LEFT_WHEEL_DEVICE_NAME,
    M4_FRAME_DIR,
    M4_LOG_DIR,
    M4_METADATA_DIR,
    OBSTACLE_SPECS,
    RIGHT_WHEEL_DEVICE_NAME,
    SNAPSHOT_TIME_S,
)


CSV_FIELDS = [
    "episode_id",
    "snapshot_time_s",
    "frame_path",
    "obstacle_id",
    "obstacle_def_name",
    "role",
    "expected_visibility",
    "actual_visibility",
    "camera_width_px",
    "camera_height_px",
    "horizontal_fov_rad",
    "vertical_fov_rad",
    "fx_px",
    "fy_px",
    "cx_px",
    "cy_px",
    "near_clip_m",
    "camera_world_x",
    "camera_world_y",
    "camera_world_z",
    "camera_pose_matrix",
    "camera_to_world_rotation",
    "world_to_camera_rotation",
    "world_to_camera_translation",
    "device_to_optical_rotation",
    "obstacle_center_x",
    "obstacle_center_y",
    "obstacle_center_z",
    "obstacle_size_x",
    "obstacle_size_y",
    "obstacle_size_z",
    "target_rgb",
    "auto_color_validation",
    "projected_polygon",
    "clipped_polygon",
    "bbox_min_u",
    "bbox_min_v",
    "bbox_max_u",
    "bbox_max_v",
    "minimum_depth_m",
    "maximum_depth_m",
    "projected_area_px",
    "truncation_fraction",
]


def _project_relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _next_episode_id(log_dir: Path) -> str:
    indices = []
    for path in log_dir.glob(f"{EPISODE_PREFIX}_episode_*.csv"):
        suffix = path.stem.removeprefix(f"{EPISODE_PREFIX}_episode_")
        try:
            indices.append(int(suffix))
        except ValueError:
            pass
    return f"episode_{max(indices, default=0) + 1:04d}"


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.9f}"


def _point_rows(points) -> list[list[float]]:
    return [[round(point.u_px, 6), round(point.v_px, 6), round(point.depth_m, 9)] for point in points]


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _projection_row(
    *,
    episode_id: str,
    snapshot_time_s: float,
    frame_path: Path,
    spec,
    obstacle,
    projection: ProjectedObstacle,
    snapshot,
) -> dict[str, str]:
    bbox = projection.bounding_box
    return {
        "episode_id": episode_id,
        "snapshot_time_s": _format_float(snapshot_time_s),
        "frame_path": _project_relative(frame_path),
        "obstacle_id": obstacle.obstacle_id,
        "obstacle_def_name": spec.def_name,
        "role": spec.role,
        "expected_visibility": spec.expected_visibility.value,
        "actual_visibility": projection.visibility_status.value,
        "camera_width_px": str(snapshot.width_px),
        "camera_height_px": str(snapshot.height_px),
        "horizontal_fov_rad": _format_float(snapshot.horizontal_fov_rad),
        "vertical_fov_rad": _format_float(snapshot.intrinsics.vertical_fov_rad),
        "fx_px": _format_float(snapshot.intrinsics.fx_px),
        "fy_px": _format_float(snapshot.intrinsics.fy_px),
        "cx_px": _format_float(snapshot.intrinsics.cx_px),
        "cy_px": _format_float(snapshot.intrinsics.cy_px),
        "near_clip_m": _format_float(snapshot.near_clip_m),
        "camera_world_x": _format_float(snapshot.camera_world_position[0]),
        "camera_world_y": _format_float(snapshot.camera_world_position[1]),
        "camera_world_z": _format_float(snapshot.camera_world_position[2]),
        "camera_pose_matrix": _json([round(value, 9) for value in snapshot.camera_pose_matrix]),
        "camera_to_world_rotation": _json(snapshot.camera_to_world_rotation),
        "world_to_camera_rotation": _json(snapshot.extrinsics.world_to_camera_rotation),
        "world_to_camera_translation": _json(snapshot.extrinsics.world_to_camera_translation),
        "device_to_optical_rotation": _json(snapshot.extrinsics.device_to_optical_rotation),
        "obstacle_center_x": _format_float(obstacle.center_x),
        "obstacle_center_y": _format_float(obstacle.center_y),
        "obstacle_center_z": _format_float(obstacle.center_z),
        "obstacle_size_x": _format_float(obstacle.size_x),
        "obstacle_size_y": _format_float(obstacle.size_y),
        "obstacle_size_z": _format_float(obstacle.size_z),
        "target_rgb": _json(spec.target_rgb),
        "auto_color_validation": "true" if spec.auto_color_validation else "false",
        "projected_polygon": _json(_point_rows(projection.projected_polygon)),
        "clipped_polygon": _json(_point_rows(projection.clipped_polygon)),
        "bbox_min_u": _format_float(bbox[0] if bbox else None),
        "bbox_min_v": _format_float(bbox[1] if bbox else None),
        "bbox_max_u": _format_float(bbox[2] if bbox else None),
        "bbox_max_v": _format_float(bbox[3] if bbox else None),
        "minimum_depth_m": _format_float(projection.minimum_depth_m),
        "maximum_depth_m": _format_float(projection.maximum_depth_m),
        "projected_area_px": _format_float(projection.projected_area_px),
        "truncation_fraction": _format_float(projection.truncation_fraction),
    }


def _stop_wheels(robot: Supervisor) -> None:
    for device_name in (LEFT_WHEEL_DEVICE_NAME, RIGHT_WHEEL_DEVICE_NAME):
        motor = robot.getDevice(device_name)
        if motor is None:
            raise RuntimeError(f"Missing wheel motor: {device_name}")
        motor.setPosition(float("inf"))
        motor.setVelocity(0.0)


def main() -> None:
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    _stop_wheels(robot)
    camera = robot.getDevice(CAMERA_DEVICE_NAME)
    if camera is None:
        raise RuntimeError(f"Missing Camera device: {CAMERA_DEVICE_NAME}")
    camera.enable(timestep)

    log_dir = PROJECT_ROOT / M4_LOG_DIR
    frame_dir = PROJECT_ROOT / M4_FRAME_DIR
    metadata_dir = PROJECT_ROOT / M4_METADATA_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    episode_id = _next_episode_id(log_dir)
    csv_path = log_dir / f"{EPISODE_PREFIX}_{episode_id}.csv"
    frame_path = frame_dir / f"{EPISODE_PREFIX}_{episode_id}.png"
    metadata_path = metadata_dir / f"{EPISODE_PREFIX}_{episode_id}.json"

    print("m4_camera_projection_validation: start", flush=True)
    print(f"episode_id={episode_id} timestep_ms={timestep}", flush=True)

    while robot.step(timestep) != -1:
        _stop_wheels(robot)
        if robot.getTime() + 1e-12 < SNAPSHOT_TIME_S:
            continue

        snapshot = read_camera_snapshot(robot, camera)
        if snapshot.width_px != EXPECTED_CAMERA_WIDTH_PX or snapshot.height_px != EXPECTED_CAMERA_HEIGHT_PX:
            raise RuntimeError(f"Unexpected camera size: {snapshot.width_px}x{snapshot.height_px}")
        save_camera_frame(camera, frame_path)

        rows: list[dict[str, str]] = []
        projections: list[ProjectedObstacle] = []
        with csv_path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for spec in OBSTACLE_SPECS:
                obstacle = read_static_box_3d(robot, spec.def_name, spec.def_name)
                projection = project_obstacle_box(obstacle, snapshot.intrinsics, snapshot.extrinsics)
                projections.append(projection)
                row = _projection_row(
                    episode_id=episode_id,
                    snapshot_time_s=robot.getTime(),
                    frame_path=frame_path,
                    spec=spec,
                    obstacle=obstacle,
                    projection=projection,
                    snapshot=snapshot,
                )
                writer.writerow(row)
                rows.append(row)
            handle.flush()

        metadata = {
            "episode_id": episode_id,
            "snapshot_time_s": robot.getTime(),
            "frame_path": _project_relative(frame_path),
            "csv_path": _project_relative(csv_path),
            "camera_width_px": snapshot.width_px,
            "camera_height_px": snapshot.height_px,
            "horizontal_fov_rad": snapshot.horizontal_fov_rad,
            "vertical_fov_rad": snapshot.intrinsics.vertical_fov_rad,
            "near_clip_m": snapshot.near_clip_m,
            "camera_world_position": snapshot.camera_world_position,
            "camera_to_world_rotation": snapshot.camera_to_world_rotation,
            "obstacle_rows": len(rows),
            "visibility_by_role": {row["role"]: row["actual_visibility"] for row in rows},
        }
        write_metadata_json(metadata_path, metadata)
        print(
            "camera "
            f"width={snapshot.width_px} height={snapshot.height_px} "
            f"fov={snapshot.horizontal_fov_rad:.9f} near={snapshot.near_clip_m:.9f}",
            flush=True,
        )
        print(
            "camera_world_pose "
            f"x={snapshot.camera_world_position[0]:.9f} "
            f"y={snapshot.camera_world_position[1]:.9f} "
            f"z={snapshot.camera_world_position[2]:.9f}",
            flush=True,
        )
        print(f"snapshot_time_s={robot.getTime():.3f}", flush=True)
        print(f"obstacle_rows={len(rows)}", flush=True)
        print(f"frame_saved={frame_path}", flush=True)
        print(f"projection_csv_saved={csv_path}", flush=True)
        print(f"metadata_saved={metadata_path}", flush=True)
        print("m4_camera_projection_validation: complete", flush=True)
        return

    print("m4_camera_projection_validation: step_returned_minus_one", flush=True)


if __name__ == "__main__":
    main()
