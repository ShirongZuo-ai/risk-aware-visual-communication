"""One parameterized Webots controller for M5E-B static-AABB snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback
from typing import TextIO

from controller import Supervisor


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.tile_scoring import FloatMask, ProjectedPolygon  # noqa: E402
from evaluation.region_masks import build_evaluation_regions  # noqa: E402
from perception.camera_projection import project_obstacle_box  # noqa: E402
from risk_map.image_risk_map import bind_projection_to_risk, build_image_risk_masks  # noqa: E402
from risk_map.trajectory_obstacle_risk import analyze_dual_trajectory_obstacle, compute_trajectory_disagreement  # noqa: E402
from scripts.m4d_image_risk_common import encode_masks_json, projection_to_json, yaw_from_orientation  # noqa: E402
from simulator.adapters.webots_camera_adapter import read_camera_snapshot, read_static_box_3d, save_camera_frame  # noqa: E402
from simulator.m5e_config import (  # noqa: E402
    CAMERA_DEVICE_NAME, EXPECTED_CAMERA_HEIGHT_PX, EXPECTED_CAMERA_WIDTH_PX, LEFT_WHEEL_DEVICE_NAME,
    M5E_GENERATOR_VERSION, RIGHT_WHEEL_DEVICE_NAME, RISK_PARAMETERS,
)
from simulator.m5e_dataset_schema import episode_id, episode_summary, relative_path, sha256_file  # noqa: E402
from simulator.m5e_gui_acceptance import gui_acceptance_requested, pause_for_gui_acceptance  # noqa: E402
from simulator.m5e_physics_diagnostics import diagnostics_path, robot_obstacle_relation, roll_pitch_yaw  # noqa: E402
from simulator.m5e_scenarios import M5EObstacleSpec, ScenarioConfig, WheelCommandPhase, config_hash  # noqa: E402
from simulator.m5e_snapshot_protocol import build_trajectories, command_phase_at, next_crossing, reference_progress, yaw_change  # noqa: E402


def _config_from_json(data: dict) -> ScenarioConfig:
    obstacles = tuple(
        M5EObstacleSpec(
            obstacle_id=item["obstacle_id"], role=item["role"], center_world=tuple(item["center_world"]),
            size_xyz=tuple(item["size_xyz"]), orientation=tuple(item["orientation"]),
            display_color=tuple(item["display_color"]), expected_visibility_role=item["expected_visibility_role"],
            expected_risk_role=item["expected_risk_role"],
        )
        for item in data["obstacle_specs"]
    )
    phases = tuple(WheelCommandPhase(**item) for item in data["command_schedule"])
    return ScenarioConfig(
        scenario_id=data["scenario_id"], scenario_name=data["scenario_name"], split=data["split"], seed=int(data["seed"]),
        start_pose=tuple(data["start_pose"]), command_schedule=phases, duration_seconds=float(data["duration_seconds"]),
        trajectory_horizon_s=float(data["trajectory_horizon_s"]), obstacle_specs=obstacles,
        snapshot_progress_targets=tuple(float(value) for value in data["snapshot_progress_targets"]),
        validation_rules=dict(data["validation_rules"]), expected_tags=tuple(data["expected_tags"]),
        generator_version=data.get("generator_version", M5E_GENERATOR_VERSION),
    )


def _read_job() -> tuple[ScenarioConfig, dict]:
    config_path = os.environ.get("M5E_CONFIG_PATH")
    if not config_path:
        raise RuntimeError("M5E_CONFIG_PATH is required")
    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    return _config_from_json(payload["scenario_config"]), payload


def _vrml(spec: M5EObstacleSpec) -> str:
    x, y, z = spec.center_world
    sx, sy, sz = spec.size_xyz
    r, g, b = spec.display_color
    return f'''DEF {spec.obstacle_id} Solid {{
  translation {x:.9f} {y:.9f} {z:.9f}
  rotation 0 0 1 0
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor {r:.6f} {g:.6f} {b:.6f} roughness 0.6 metalness 0 }}
      geometry Box {{ size {sx:.9f} {sy:.9f} {sz:.9f} }}
    }}
  ]
  boundingObject Box {{ size {sx:.9f} {sy:.9f} {sz:.9f} }}
  physics NULL
  locked TRUE
}}'''


def _import_obstacles(robot: Supervisor, specs: tuple[M5EObstacleSpec, ...]) -> None:
    group = robot.getFromDef("M5E_OBSTACLES")
    if group is None:
        raise RuntimeError("M5E_OBSTACLES group is missing")
    children = group.getField("children")
    if children is None:
        raise RuntimeError("M5E_OBSTACLES children field is missing")
    if children.getCount() != 0:
        raise RuntimeError("M5E_OBSTACLES must be empty before parameterized obstacle import")
    for spec in specs:
        children.importMFNodeFromString(-1, _vrml(spec))


def _state(self_node) -> dict[str, float]:
    position = self_node.getPosition()
    orientation = self_node.getOrientation()
    velocity = self_node.getVelocity()
    return {
        "x": float(position[0]), "y": float(position[1]), "z": float(position[2]),
        "yaw_rad": yaw_from_orientation(orientation),
        "linear_velocity_m_s": math.hypot(float(velocity[0]), float(velocity[1])),
        "angular_velocity_rad_s": float(velocity[5]),
    }


def _write_physics_diagnostic(
    handle: TextIO,
    self_node,
    config: ScenarioConfig,
    step_count: int,
    time_s: float,
    phase: WheelCommandPhase,
    crossing,
    obstacle_node_ids: dict[str, int],
) -> None:
    position = self_node.getPosition()
    orientation = self_node.getOrientation()
    velocity = self_node.getVelocity()
    roll, pitch, yaw = roll_pitch_yaw(orientation)
    contacts = self_node.getContactPoints(True)
    contact_node_ids = {int(contact.node_id) for contact in contacts}
    obstacles = {
        spec.obstacle_id: robot_obstacle_relation(position[0], position[1], position[2], spec.center_world, spec.size_xyz)
        for spec in config.obstacle_specs
    }
    record = {
        "webots_step": step_count,
        "simulation_time_s": time_s,
        "command_segment": phase.name,
        "left_wheel_velocity_rad_s": phase.left_rad_s,
        "right_wheel_velocity_rad_s": phase.right_rad_s,
        "snapshot_crossing_index": None if crossing is None else crossing.snapshot_index,
        "robot_pose": {
            "x": float(position[0]),
            "y": float(position[1]),
            "z": float(position[2]),
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
        },
        "robot_velocity": {
            "linear_m_s": math.hypot(float(velocity[0]), float(velocity[1])),
            "angular_rad_s": float(velocity[5]),
        },
        "contact_points": [
            {"point": [float(value) for value in contact.point], "other_node_id": int(contact.node_id)}
            for contact in contacts
        ],
        "obstacle_node_ids": obstacle_node_ids,
        "contacting_obstacle_ids": sorted(
            obstacle_id for obstacle_id, node_id in obstacle_node_ids.items() if node_id in contact_node_ids
        ),
        "obstacles": obstacles,
    }
    handle.write(json.dumps(record, sort_keys=True) + "\n")
    handle.flush()


def _camera_json(camera_snapshot) -> dict:
    return {
        "width_px": camera_snapshot.width_px, "height_px": camera_snapshot.height_px,
        "horizontal_fov_rad": camera_snapshot.horizontal_fov_rad, "vertical_fov_rad": camera_snapshot.intrinsics.vertical_fov_rad,
        "near_clip_m": camera_snapshot.near_clip_m, "fx_px": camera_snapshot.intrinsics.fx_px, "fy_px": camera_snapshot.intrinsics.fy_px,
        "cx_px": camera_snapshot.intrinsics.cx_px, "cy_px": camera_snapshot.intrinsics.cy_px,
        "camera_world_position": list(camera_snapshot.camera_world_position),
        "camera_to_world_rotation": [list(row) for row in camera_snapshot.camera_to_world_rotation],
        "world_to_camera_rotation": [list(row) for row in camera_snapshot.extrinsics.world_to_camera_rotation],
        "world_to_camera_translation": list(camera_snapshot.extrinsics.world_to_camera_translation),
        "device_to_optical_rotation": [list(row) for row in camera_snapshot.extrinsics.device_to_optical_rotation],
        "axis_mapping": "x_optical=-y_device; y_optical=-z_device; z_optical=x_device",
    }


def _trajectory_json(points) -> list[dict[str, float]]:
    return [{"time_offset_s": point.time_offset_s, "x": point.x, "y": point.y, "yaw_rad": point.yaw_rad} for point in points]


def _mask_hash(values) -> str:
    payload = json.dumps(list(values), separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _box_json(box) -> dict:
    return {
        "obstacle_id": box.obstacle_id, "center_x": box.center_x, "center_y": box.center_y, "center_z": box.center_z,
        "size_x": box.size_x, "size_y": box.size_y, "size_z": box.size_z,
    }


def _nearest_trajectory_record(points, closest_time_s: float, center_x: float, center_y: float) -> dict:
    index = min(range(len(points)), key=lambda item: (abs(points[item].time_offset_s - closest_time_s), item))
    point = points[index]
    return {
        "nearest_index": index,
        "nearest_time_s": point.time_offset_s,
        "center_relative_dx_m": center_x - point.x,
        "center_relative_dy_m": center_y - point.y,
        "center_distance_m": math.hypot(center_x - point.x, center_y - point.y),
    }


def _risk_json(result, box, planned, state_trajectory) -> dict:
    planned_result = result.planned_result
    state_result = result.state_result
    return {
        "planned_risk": planned_result.risk_score, "state_risk": state_result.risk_score,
        "combined_risk": result.combined_risk_score, "planned_enters_corridor": planned_result.enters_corridor,
        "state_enters_corridor": state_result.enters_corridor,
        "planned_clearance_m": planned_result.minimum_clearance_m,
        "state_clearance_m": state_result.minimum_clearance_m,
        "planned_ttcf_s": planned_result.first_corridor_entry_time_s,
        "state_ttcf_s": state_result.first_corridor_entry_time_s,
        "planned_overlap_duration_s": planned_result.corridor_overlap_duration_s,
        "state_overlap_duration_s": state_result.corridor_overlap_duration_s,
        "planned_closest_time_s": planned_result.closest_time_s,
        "state_closest_time_s": state_result.closest_time_s,
        "planned_nearest": _nearest_trajectory_record(planned, planned_result.closest_time_s, box.center_x, box.center_y),
        "state_nearest": _nearest_trajectory_record(state_trajectory, state_result.closest_time_s, box.center_x, box.center_y),
    }


def _maximum_lateral_separation(planned, state_trajectory) -> float:
    return max(
        abs(-(state.x - planned_point.x) * math.sin(planned_point.yaw_rad) + (state.y - planned_point.y) * math.cos(planned_point.yaw_rad))
        for planned_point, state in zip(planned, state_trajectory)
    )


def _regions(masks, projections) -> object:
    polygons = tuple(
        ProjectedPolygon(obstacle_id, projection.visibility_status.value, tuple((point.u_px, point.v_px) for point in projection.clipped_polygon))
        for obstacle_id, projection in projections.items()
    )
    return build_evaluation_regions(FloatMask(masks.combined.width_px, masks.combined.height_px, masks.combined.values), polygons)


def _capture(
    robot: Supervisor, config: ScenarioConfig, job: dict, crossing, self_node, camera, step_count: int,
) -> dict:
    root = PROJECT_ROOT / job["output_root"]
    episode_dir = root / "metadata" / "m5e" / config.split / config.scenario_id / job["episode_id"]
    frame_dir = root / "frames" / "m5e" / config.split / config.scenario_id / job["episode_id"]
    mask_dir = root / "masks" / "m5e" / config.split / config.scenario_id / job["episode_id"]
    for directory in (episode_dir, frame_dir, mask_dir):
        directory.mkdir(parents=True, exist_ok=True)
    index = crossing.snapshot_index
    frame_path = frame_dir / f"snapshot_{index}.png"
    metadata_path = episode_dir / f"snapshot_{index}.json"
    masks_path = mask_dir / f"snapshot_{index}_masks.json"
    if any(path.exists() for path in (frame_path, metadata_path, masks_path)):
        raise RuntimeError(f"refusing to overwrite snapshot {index}")
    state = _state(self_node)
    planned, state_trajectory = build_trajectories(config, state, crossing.simulation_time_s)
    disagreement = compute_trajectory_disagreement(planned, state_trajectory)
    camera_snapshot = read_camera_snapshot(robot, camera)
    if (camera_snapshot.width_px, camera_snapshot.height_px) != (EXPECTED_CAMERA_WIDTH_PX, EXPECTED_CAMERA_HEIGHT_PX):
        raise RuntimeError("unexpected M5E camera dimensions")
    boxes = [read_static_box_3d(robot, spec.obstacle_id, spec.obstacle_id) for spec in config.obstacle_specs]
    risks, projections, bound = {}, {}, []
    for box in boxes:
        from scripts.m4d_image_risk_common import obstacle_footprint_from_box
        result = analyze_dual_trajectory_obstacle(planned, state_trajectory, obstacle_footprint_from_box(box), RISK_PARAMETERS)
        projection = project_obstacle_box(box, camera_snapshot.intrinsics, camera_snapshot.extrinsics)
        risks[box.obstacle_id] = result
        projections[box.obstacle_id] = projection
        bound.append(bind_projection_to_risk(projection, result.planned_result.risk_score, result.state_result.risk_score, result.combined_risk_score))
    masks = build_image_risk_masks(camera_snapshot.width_px, camera_snapshot.height_px, bound)
    contributions = {item.obstacle_id: item for item in masks.contributions}
    regions = _regions(masks, projections)
    save_camera_frame(camera, frame_path)
    masks_payload = {
        "episode_id": job["episode_id"], "snapshot_index": index, "snapshot_time_s": crossing.simulation_time_s,
        "masks": encode_masks_json(masks), "contributions": [item.__dict__ | {"visibility_status": item.visibility_status.value} for item in masks.contributions],
    }
    masks_path.write_text(json.dumps(masks_payload, indent=2, sort_keys=True), encoding="utf-8")
    obstacle_records = []
    spec_by_id = {spec.obstacle_id: spec for spec in config.obstacle_specs}
    for box in boxes:
        spec = spec_by_id[box.obstacle_id]
        record = _box_json(box) | {"role": spec.role, "expected_visibility_role": spec.expected_visibility_role, "expected_risk_role": spec.expected_risk_role}
        record |= _risk_json(risks[box.obstacle_id], box, planned, state_trajectory) | projection_to_json(projections[box.obstacle_id])
        contribution = contributions[box.obstacle_id]
        record |= {
            "eligible_for_mask": contribution.eligible_for_mask, "skip_reason": contribution.skip_reason,
            "candidate_pixel_count": contribution.candidate_pixel_count, "planned_written_pixel_count": contribution.planned_written_pixel_count,
            "state_written_pixel_count": contribution.state_written_pixel_count, "combined_written_pixel_count": contribution.combined_written_pixel_count,
        }
        obstacle_records.append(record)
    visibility_counts = {}
    for projection in projections.values():
        visibility_counts[projection.visibility_status.value] = visibility_counts.get(projection.visibility_status.value, 0) + 1
    eligible_records = [record for record in obstacle_records if record["eligible_for_mask"]]
    planned_ranking = sorted(eligible_records, key=lambda item: (-item["planned_risk"], item["obstacle_id"]))
    state_ranking = sorted(eligible_records, key=lambda item: (-item["state_risk"], item["obstacle_id"]))
    metadata = {
        "generator_version": M5E_GENERATOR_VERSION, "episode_id": job["episode_id"], "split": config.split,
        "scenario_id": config.scenario_id, "scenario_name": config.scenario_name, "seed": config.seed,
        "original_seed": job["original_seed"], "replacement_index": job["replacement_index"], "config_hash": config_hash(config),
        "snapshot_index": index, "target_progress": crossing.target_progress, "actual_progress": crossing.actual_progress,
        "progress_error": crossing.actual_progress - crossing.target_progress, "simulation_time_s": crossing.simulation_time_s,
        "webots_step": step_count, "frame_path": relative_path(frame_path, PROJECT_ROOT), "frame_sha256": sha256_file(frame_path),
        "masks_path": relative_path(masks_path, PROJECT_ROOT), "masks_sha256": sha256_file(masks_path),
        "combined_mask_sha256": _mask_hash(masks.combined.values), "camera": _camera_json(camera_snapshot),
        "robot_snapshot_state": state, "command_state": command_phase_at(config, crossing.simulation_time_s).__dict__,
        "wheel_velocities_rad_s": {"left": command_phase_at(config, crossing.simulation_time_s).left_rad_s, "right": command_phase_at(config, crossing.simulation_time_s).right_rad_s},
        "planned_trajectory_points": _trajectory_json(planned), "state_trajectory_points": _trajectory_json(state_trajectory),
        "planned_yaw_change": yaw_change(planned), "state_yaw_change": yaw_change(state_trajectory), "trajectory_disagreement_m": disagreement,
        "maximum_lateral_separation_m": _maximum_lateral_separation(planned, state_trajectory),
        "planned_risk_ranking": [item["obstacle_id"] for item in planned_ranking],
        "state_risk_ranking": [item["obstacle_id"] for item in state_ranking],
        "planned_ranking_margin": None if len(planned_ranking) < 2 else planned_ranking[0]["planned_risk"] - planned_ranking[1]["planned_risk"],
        "state_ranking_margin": None if len(state_ranking) < 2 else state_ranking[0]["state_risk"] - state_ranking[1]["state_risk"],
        "obstacles": obstacle_records, "risk_parameters": RISK_PARAMETERS.__dict__,
        "combined_risk_sum": sum(masks.combined.values), "combined_risk_max": max(masks.combined.values),
        "risk_support_pixel_count": masks.combined.nonzero_pixel_count, "high_risk_pixel_count": regions.high_risk.pixel_count,
        "object_union_pixel_count": regions.eligible_object_union.pixel_count,
        "eligible_obstacle_count": sum(item.eligible_for_mask for item in masks.contributions), "visibility_counts": visibility_counts,
        "actual_future_trajectory_used": False, "status": "captured",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return metadata | {"metadata_path": relative_path(metadata_path, PROJECT_ROOT)}


def _write_summary(job: dict, payload: dict) -> None:
    path = PROJECT_ROOT / job["summary_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    config, job = _read_job()
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    self_node = robot.getSelf()
    self_node.getField("translation").setSFVec3f(list(config.start_pose[:2]) + [0.0])
    self_node.getField("rotation").setSFRotation([0.0, 0.0, 1.0, config.start_pose[2]])
    self_node.resetPhysics()
    _import_obstacles(robot, config.obstacle_specs)
    obstacle_node_ids = {spec.obstacle_id: int(robot.getFromDef(spec.obstacle_id).getId()) for spec in config.obstacle_specs}
    left = robot.getDevice(LEFT_WHEEL_DEVICE_NAME)
    right = robot.getDevice(RIGHT_WHEEL_DEVICE_NAME)
    camera = robot.getDevice(CAMERA_DEVICE_NAME)
    if left is None or right is None or camera is None:
        raise RuntimeError("M5E required robot device is missing")
    left.setPosition(float("inf")); right.setPosition(float("inf")); left.setVelocity(0.0); right.setVelocity(0.0)
    camera.enable(timestep)
    diagnostic_destination = diagnostics_path(os.environ, PROJECT_ROOT)
    diagnostic_handle = None
    if diagnostic_destination is not None:
        diagnostic_destination.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_handle = diagnostic_destination.open("x", encoding="utf-8")
        self_node.enableContactPointsTracking(timestep, True)
    completed, snapshots, step_count = set(), [], 0
    try:
        while robot.step(timestep) != -1:
            step_count += 1
            time_s = robot.getTime()
            phase = command_phase_at(config, time_s)
            left.setVelocity(phase.left_rad_s); right.setVelocity(phase.right_rad_s)
            crossing = next_crossing(config, completed, time_s, step_count)
            if diagnostic_handle is not None:
                _write_physics_diagnostic(
                    diagnostic_handle,
                    self_node,
                    config,
                    step_count,
                    time_s,
                    phase,
                    crossing,
                    obstacle_node_ids,
                )
            if crossing is not None:
                snapshots.append(_capture(robot, config, job, crossing, self_node, camera, step_count))
                completed.add(crossing.snapshot_index)
            if time_s + 1e-12 >= config.duration_seconds:
                break
        left.setVelocity(0.0); right.setVelocity(0.0)
        status = "captured" if len(snapshots) == 4 else "invalid_missing_snapshot"
        reason = None if status == "captured" else f"captured {len(snapshots)} of 4 snapshots"
        _write_summary(job, episode_summary(config, original_seed=job["original_seed"], replacement_index=job["replacement_index"], status=status, snapshots=snapshots, failure_reason=reason))
        print(f"m5e_dataset_generator: status={status} snapshots={len(snapshots)}", flush=True)
        if status != "captured":
            raise RuntimeError(reason)
        if gui_acceptance_requested(os.environ):
            pause_for_gui_acceptance(
                robot,
                config.scenario_id,
                len(snapshots),
                Supervisor.SIMULATION_MODE_PAUSE,
                emit=lambda message: print(message, flush=True),
            )
    except Exception as exc:
        left.setVelocity(0.0); right.setVelocity(0.0)
        _write_summary(job, episode_summary(config, original_seed=job["original_seed"], replacement_index=job["replacement_index"], status="invalid_controller_error", snapshots=snapshots, failure_reason=f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()
        raise
    finally:
        if diagnostic_handle is not None:
            diagnostic_handle.close()


if __name__ == "__main__":
    main()
