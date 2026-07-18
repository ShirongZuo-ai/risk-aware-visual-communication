"""Milestone 4D Webots image-risk validation controller."""

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

from perception.camera_projection import project_obstacle_box  # noqa: E402
from risk_map.image_risk_map import bind_projection_to_risk, build_image_risk_masks  # noqa: E402
from risk_map.trajectory_obstacle_risk import analyze_dual_trajectory_obstacle, compute_trajectory_disagreement  # noqa: E402
from scripts.m4d_image_risk_common import (  # noqa: E402
    future_command_segments,
    metadata_for_snapshot,
    obstacle_footprint_from_box,
    optional_float_to_csv,
    point_rows,
    projection_to_json,
    yaw_from_orientation,
)
from simulator.adapters.webots_camera_adapter import (  # noqa: E402
    read_camera_snapshot,
    read_static_box_3d,
    save_camera_frame,
    write_metadata_json,
)
from simulator.m3c_config import command_for_time  # noqa: E402
from simulator.m4d_config import (  # noqa: E402
    CAMERA_DEVICE_NAME,
    EPISODE_PREFIX,
    EXPECTED_CAMERA_HEIGHT_PX,
    EXPECTED_CAMERA_WIDTH_PX,
    LEFT_WHEEL_DEVICE_NAME,
    M4_FRAME_DIR,
    M4_LOG_DIR,
    M4_MASK_DIR,
    M4_METADATA_DIR,
    OBSTACLE_SPECS,
    PREDICTION_HORIZON_S,
    PREDICTION_STEP_S,
    RISK_PARAMETERS,
    RIGHT_WHEEL_DEVICE_NAME,
    SNAPSHOT_TIME_S,
)
from navigation.trajectory_prediction import predict_command_conditioned_trajectory, predict_state_only_trajectory  # noqa: E402


CSV_FIELDS = [
    "episode_id",
    "snapshot_time_s",
    "obstacle_id",
    "obstacle_def_name",
    "role",
    "expected_visibility",
    "actual_visibility",
    "planned_clearance_m",
    "state_clearance_m",
    "planned_ttcf_s",
    "state_ttcf_s",
    "planned_closest_time_s",
    "state_closest_time_s",
    "planned_spatial_factor",
    "state_spatial_factor",
    "planned_temporal_factor",
    "state_temporal_factor",
    "planned_risk",
    "state_risk",
    "combined_risk",
    "projected_polygon",
    "clipped_polygon",
    "bbox",
    "projected_area_px",
    "truncation_fraction",
    "eligible_for_mask",
    "skip_reason",
    "candidate_pixel_count",
    "planned_written_pixel_count",
    "state_written_pixel_count",
    "combined_written_pixel_count",
    "target_rgb",
    "auto_color_validation",
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


def _format_float(value: float) -> str:
    return f"{value:.9f}"


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _bbox_json(projection) -> str:
    if projection.bounding_box is None:
        return ""
    return _json([round(value, 6) for value in projection.bounding_box])


def _stop_wheels(robot: Supervisor) -> None:
    for device_name in (LEFT_WHEEL_DEVICE_NAME, RIGHT_WHEEL_DEVICE_NAME):
        motor = robot.getDevice(device_name)
        if motor is None:
            raise RuntimeError(f"Missing wheel motor: {device_name}")
        motor.setPosition(float("inf"))
        motor.setVelocity(0.0)


def _mask_json(masks) -> dict:
    return {
        "planned": {"width": masks.planned.width_px, "height": masks.planned.height_px, "layout": "row-major", "values": list(masks.planned.values)},
        "state": {"width": masks.state.width_px, "height": masks.state.height_px, "layout": "row-major", "values": list(masks.state.values)},
        "combined": {"width": masks.combined.width_px, "height": masks.combined.height_px, "layout": "row-major", "values": list(masks.combined.values)},
    }


def main() -> None:
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    self_node = robot.getSelf()
    _stop_wheels(robot)
    camera = robot.getDevice(CAMERA_DEVICE_NAME)
    if camera is None:
        raise RuntimeError(f"Missing Camera device: {CAMERA_DEVICE_NAME}")
    camera.enable(timestep)

    log_dir = PROJECT_ROOT / M4_LOG_DIR
    frame_dir = PROJECT_ROOT / M4_FRAME_DIR
    metadata_dir = PROJECT_ROOT / M4_METADATA_DIR
    mask_dir = PROJECT_ROOT / M4_MASK_DIR
    for path in (log_dir, frame_dir, metadata_dir, mask_dir):
        path.mkdir(parents=True, exist_ok=True)

    episode_id = _next_episode_id(log_dir)
    csv_path = log_dir / f"{EPISODE_PREFIX}_{episode_id}.csv"
    frame_path = frame_dir / f"{EPISODE_PREFIX}_{episode_id}.png"
    metadata_path = metadata_dir / f"{EPISODE_PREFIX}_{episode_id}.json"
    masks_path = mask_dir / f"{EPISODE_PREFIX}_{episode_id}_masks.json"

    print("m4d_image_risk_validation: start", flush=True)
    print(f"episode_id={episode_id} timestep_ms={timestep}", flush=True)

    while robot.step(timestep) != -1:
        elapsed = robot.getTime()
        phase = command_for_time(elapsed)
        left_motor = robot.getDevice(LEFT_WHEEL_DEVICE_NAME)
        right_motor = robot.getDevice(RIGHT_WHEEL_DEVICE_NAME)
        left_motor.setPosition(float("inf"))
        right_motor.setPosition(float("inf"))
        left_motor.setVelocity(phase.left_rad_s)
        right_motor.setVelocity(phase.right_rad_s)

        if elapsed + 1e-12 < SNAPSHOT_TIME_S:
            continue

        _stop_wheels(robot)
        position = self_node.getPosition()
        orientation = self_node.getOrientation()
        velocity = self_node.getVelocity()
        snapshot_state = {
            "x": float(position[0]),
            "y": float(position[1]),
            "z": float(position[2]),
            "yaw_rad": yaw_from_orientation(orientation),
            "linear_velocity_m_s": math.hypot(float(velocity[0]), float(velocity[1])),
            "angular_velocity_rad_s": float(velocity[5]),
        }
        planned = predict_command_conditioned_trajectory(
            x=snapshot_state["x"],
            y=snapshot_state["y"],
            yaw_rad=snapshot_state["yaw_rad"],
            command_segments=future_command_segments(elapsed),
            horizon_s=PREDICTION_HORIZON_S,
            step_s=PREDICTION_STEP_S,
        )
        state = predict_state_only_trajectory(
            x=snapshot_state["x"],
            y=snapshot_state["y"],
            yaw_rad=snapshot_state["yaw_rad"],
            linear_velocity_m_s=snapshot_state["linear_velocity_m_s"],
            angular_velocity_rad_s=snapshot_state["angular_velocity_rad_s"],
            horizon_s=PREDICTION_HORIZON_S,
            step_s=PREDICTION_STEP_S,
        )
        trajectory_disagreement = compute_trajectory_disagreement(planned, state)

        snapshot = read_camera_snapshot(robot, camera)
        if snapshot.width_px != EXPECTED_CAMERA_WIDTH_PX or snapshot.height_px != EXPECTED_CAMERA_HEIGHT_PX:
            raise RuntimeError(f"Unexpected camera size: {snapshot.width_px}x{snapshot.height_px}")
        save_camera_frame(camera, frame_path)

        boxes = [read_static_box_3d(robot, spec.def_name, spec.obstacle_id) for spec in OBSTACLE_SPECS]
        risks = {}
        projections = {}
        bound_risks = []
        for box in boxes:
            result = analyze_dual_trajectory_obstacle(planned, state, obstacle_footprint_from_box(box), RISK_PARAMETERS)
            projection = project_obstacle_box(box, snapshot.intrinsics, snapshot.extrinsics)
            risks[box.obstacle_id] = result
            projections[box.obstacle_id] = projection
            bound_risks.append(bind_projection_to_risk(projection, result.planned_result.risk_score, result.state_result.risk_score, result.combined_risk_score))

        masks = build_image_risk_masks(snapshot.width_px, snapshot.height_px, bound_risks)
        contribution_by_id = {item.obstacle_id: item for item in masks.contributions}

        masks_payload = {
            "episode_id": episode_id,
            "snapshot_time_s": elapsed,
            "quantization_rule": "uint8 = round(255 * risk_value)",
            "masks": _mask_json(masks),
            "contributions": [item.__dict__ | {"visibility_status": item.visibility_status.value} for item in masks.contributions],
        }
        masks_path.write_text(json.dumps(masks_payload, indent=2, sort_keys=True), encoding="utf-8")

        with csv_path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for spec in OBSTACLE_SPECS:
                result = risks[spec.obstacle_id]
                projection = projections[spec.obstacle_id]
                contribution = contribution_by_id[spec.obstacle_id]
                writer.writerow(
                    {
                        "episode_id": episode_id,
                        "snapshot_time_s": _format_float(elapsed),
                        "obstacle_id": spec.obstacle_id,
                        "obstacle_def_name": spec.def_name,
                        "role": spec.role,
                        "expected_visibility": spec.expected_visibility.value,
                        "actual_visibility": projection.visibility_status.value,
                        "planned_clearance_m": _format_float(result.planned_result.minimum_clearance_m),
                        "state_clearance_m": _format_float(result.state_result.minimum_clearance_m),
                        "planned_ttcf_s": optional_float_to_csv(result.planned_result.first_corridor_entry_time_s),
                        "state_ttcf_s": optional_float_to_csv(result.state_result.first_corridor_entry_time_s),
                        "planned_closest_time_s": _format_float(result.planned_result.closest_time_s),
                        "state_closest_time_s": _format_float(result.state_result.closest_time_s),
                        "planned_spatial_factor": _format_float(result.planned_result.spatial_score),
                        "state_spatial_factor": _format_float(result.state_result.spatial_score),
                        "planned_temporal_factor": _format_float(result.planned_result.temporal_score),
                        "state_temporal_factor": _format_float(result.state_result.temporal_score),
                        "planned_risk": _format_float(result.planned_result.risk_score),
                        "state_risk": _format_float(result.state_result.risk_score),
                        "combined_risk": _format_float(result.combined_risk_score),
                        "projected_polygon": _json(point_rows(projection.projected_polygon)),
                        "clipped_polygon": _json(point_rows(projection.clipped_polygon)),
                        "bbox": _bbox_json(projection),
                        "projected_area_px": _format_float(projection.projected_area_px),
                        "truncation_fraction": _format_float(projection.truncation_fraction),
                        "eligible_for_mask": "true" if contribution.eligible_for_mask else "false",
                        "skip_reason": contribution.skip_reason or "",
                        "candidate_pixel_count": str(contribution.candidate_pixel_count),
                        "planned_written_pixel_count": str(contribution.planned_written_pixel_count),
                        "state_written_pixel_count": str(contribution.state_written_pixel_count),
                        "combined_written_pixel_count": str(contribution.combined_written_pixel_count),
                        "target_rgb": _json(spec.target_rgb),
                        "auto_color_validation": "true" if spec.auto_color_validation else "false",
                    }
                )
            handle.flush()

        metadata = metadata_for_snapshot(
            episode_id=episode_id,
            snapshot_time_s=elapsed,
            frame_path=_project_relative(frame_path),
            csv_path=_project_relative(csv_path),
            masks_path=_project_relative(masks_path),
            snapshot_state=snapshot_state,
            planned=planned,
            state=state,
            obstacle_boxes=boxes,
            camera_snapshot=snapshot,
            trajectory_disagreement_m=trajectory_disagreement,
        )
        metadata["projections"] = {obstacle_id: projection_to_json(projection) for obstacle_id, projection in projections.items()}
        write_metadata_json(metadata_path, metadata)

        print(
            "current_state "
            f"x={snapshot_state['x']:.9f} y={snapshot_state['y']:.9f} yaw={snapshot_state['yaw_rad']:.9f} "
            f"v={snapshot_state['linear_velocity_m_s']:.9f} omega={snapshot_state['angular_velocity_rad_s']:.9f}",
            flush=True,
        )
        print(f"snapshot_time_s={elapsed:.3f}", flush=True)
        print(f"planned_points={len(planned)} state_points={len(state)}", flush=True)
        print(f"trajectory_disagreement={trajectory_disagreement:.9f}", flush=True)
        print(f"obstacle_rows={len(OBSTACLE_SPECS)} eligible_obstacles={sum(1 for c in masks.contributions if c.eligible_for_mask)}", flush=True)
        print(
            f"planned_nonzero_pixels={masks.planned.nonzero_pixel_count} "
            f"state_nonzero_pixels={masks.state.nonzero_pixel_count} "
            f"combined_nonzero_pixels={masks.combined.nonzero_pixel_count}",
            flush=True,
        )
        print(f"frame_saved={frame_path}", flush=True)
        print(f"float_masks_saved={masks_path}", flush=True)
        print(f"csv_saved={csv_path}", flush=True)
        print(f"metadata_saved={metadata_path}", flush=True)
        print("m4d_image_risk_validation: complete", flush=True)
        return

    _stop_wheels(robot)
    print("m4d_image_risk_validation: step_returned_minus_one", flush=True)


if __name__ == "__main__":
    main()
