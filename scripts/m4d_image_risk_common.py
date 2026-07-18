"""Shared helpers for Milestone 4D image-risk validation."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from navigation.trajectory_prediction import (  # noqa: E402
    CommandSegment,
    TrajectoryPoint,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
)
from perception.camera_models import (  # noqa: E402
    CameraExtrinsics,
    CameraIntrinsics,
    ObstacleBox3D,
    ProjectedObstacle,
    ProjectedPoint,
    VisibilityStatus,
)
from perception.camera_projection import project_obstacle_box  # noqa: E402
from risk_map.image_risk_map import (  # noqa: E402
    ImageRiskMasks,
    Mask2D,
    ProjectedObstacleRisk,
    bind_projection_to_risk,
    build_image_risk_masks,
)
from risk_map.models import ObstacleFootprint, RiskParameters  # noqa: E402
from risk_map.trajectory_obstacle_risk import (  # noqa: E402
    analyze_dual_trajectory_obstacle,
    compute_trajectory_disagreement,
)
from simulator.m4d_config import (  # noqa: E402
    COMMAND_SCHEDULE,
    EXPECTED_CAMERA_HEIGHT_PX,
    EXPECTED_CAMERA_WIDTH_PX,
    OBSTACLE_SPECS,
    PREDICTION_HORIZON_S,
    PREDICTION_STEP_S,
    RISK_PARAMETERS,
)


FLOAT_TOLERANCE = 1e-8


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_orientation(orientation: Sequence[float]) -> float:
    return normalize_angle(math.atan2(float(orientation[3]), float(orientation[0])))


def future_command_segments(analysis_time_s: float) -> list[CommandSegment]:
    segments: list[CommandSegment] = []
    horizon_end = analysis_time_s + PREDICTION_HORIZON_S
    for phase in COMMAND_SCHEDULE:
        start = max(phase.start_s, analysis_time_s)
        end = min(phase.end_s, horizon_end)
        if end <= start:
            continue
        segments.append(CommandSegment(start - analysis_time_s, end - analysis_time_s, phase.left_rad_s, phase.right_rad_s))
    if not segments or segments[-1].end_offset_s < PREDICTION_HORIZON_S:
        start = segments[-1].end_offset_s if segments else 0.0
        segments.append(CommandSegment(start, PREDICTION_HORIZON_S, 0.0, 0.0))
    return segments


def build_trajectories(snapshot_state: dict[str, float], analysis_time_s: float) -> tuple[list[TrajectoryPoint], list[TrajectoryPoint]]:
    planned = predict_command_conditioned_trajectory(
        x=snapshot_state["x"],
        y=snapshot_state["y"],
        yaw_rad=snapshot_state["yaw_rad"],
        command_segments=future_command_segments(analysis_time_s),
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
    return planned, state


def obstacle_footprint_from_box(box: ObstacleBox3D) -> ObstacleFootprint:
    return ObstacleFootprint(box.obstacle_id, box.center_x, box.center_y, box.size_x, box.size_y)


def _trajectory_to_json(points: Iterable[TrajectoryPoint]) -> list[dict[str, float]]:
    return [
        {
            "time_offset_s": point.time_offset_s,
            "x": point.x,
            "y": point.y,
            "yaw_rad": point.yaw_rad,
        }
        for point in points
    ]


def _trajectory_from_json(items: Iterable[dict[str, float]]) -> list[TrajectoryPoint]:
    return [TrajectoryPoint(float(item["time_offset_s"]), float(item["x"]), float(item["y"]), float(item["yaw_rad"])) for item in items]


def point_rows(points: Iterable[ProjectedPoint]) -> list[list[float]]:
    return [[round(point.u_px, 6), round(point.v_px, 6), round(point.depth_m, 9)] for point in points]


def points_from_rows(rows: Iterable[Sequence[float]], width_px: int, height_px: int) -> tuple[ProjectedPoint, ...]:
    points: list[ProjectedPoint] = []
    for row in rows:
        u, v, depth = float(row[0]), float(row[1]), float(row[2])
        points.append(ProjectedPoint(u, v, depth, 0.0 <= u <= width_px - 1 and 0.0 <= v <= height_px - 1))
    return tuple(points)


def bbox_to_json(bbox: tuple[float, float, float, float] | None) -> list[float] | None:
    if bbox is None:
        return None
    return [round(value, 6) for value in bbox]


def projection_to_json(projection: ProjectedObstacle) -> dict:
    return {
        "obstacle_id": projection.obstacle_id,
        "visibility_status": projection.visibility_status.value,
        "projected_polygon": point_rows(projection.projected_polygon),
        "clipped_polygon": point_rows(projection.clipped_polygon),
        "bounding_box": bbox_to_json(projection.bounding_box),
        "minimum_depth_m": projection.minimum_depth_m,
        "maximum_depth_m": projection.maximum_depth_m,
        "projected_area_px": projection.projected_area_px,
        "truncation_fraction": projection.truncation_fraction,
    }


def projection_from_json(data: dict, width_px: int, height_px: int) -> ProjectedObstacle:
    bbox = data["bounding_box"]
    return ProjectedObstacle(
        obstacle_id=data["obstacle_id"],
        visibility_status=VisibilityStatus(data["visibility_status"]),
        projected_polygon=points_from_rows(data["projected_polygon"], width_px, height_px),
        clipped_polygon=points_from_rows(data["clipped_polygon"], width_px, height_px),
        bounding_box=None if bbox is None else tuple(float(value) for value in bbox),  # type: ignore[arg-type]
        minimum_depth_m=data["minimum_depth_m"],
        maximum_depth_m=data["maximum_depth_m"],
        projected_area_px=float(data["projected_area_px"]),
        truncation_fraction=float(data["truncation_fraction"]),
    )


def mask_to_json(mask: Mask2D) -> dict:
    return {"width": mask.width_px, "height": mask.height_px, "values": list(mask.values), "layout": "row-major"}


def mask_from_json(data: dict) -> Mask2D:
    if data.get("layout") != "row-major":
        raise ValueError("mask layout must be row-major")
    return Mask2D(int(data["width"]), int(data["height"]), tuple(float(value) for value in data["values"]))


def encode_masks_json(masks: ImageRiskMasks) -> dict:
    return {
        "planned": mask_to_json(masks.planned),
        "state": mask_to_json(masks.state),
        "combined": mask_to_json(masks.combined),
    }


def decode_masks_json(data: dict) -> ImageRiskMasks:
    planned = mask_from_json(data["planned"])
    state = mask_from_json(data["state"])
    combined = mask_from_json(data["combined"])
    return ImageRiskMasks(planned, state, combined, ())


def quantize_mask_value(value: float) -> int:
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError("mask value must be finite and in [0, 1]")
    return int(round(255.0 * value))


def polygon_json(value: str) -> list[tuple[float, float]]:
    if not value:
        return []
    return [(float(item[0]), float(item[1])) for item in json.loads(value)]


def optional_float_to_csv(value: float | None) -> str:
    return "" if value is None else f"{value:.9f}"


def parse_optional_float(value: str) -> float | None:
    if value == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("optional float is not finite")
    return parsed


def exact_join_risk_projection(
    risks_by_id: dict[str, object],
    projections_by_id: dict[str, ProjectedObstacle],
) -> list[tuple[str, object, ProjectedObstacle]]:
    if len(risks_by_id) != len(set(risks_by_id)):
        raise ValueError("duplicate risk IDs")
    if len(projections_by_id) != len(set(projections_by_id)):
        raise ValueError("duplicate projection IDs")
    risk_ids = set(risks_by_id)
    projection_ids = set(projections_by_id)
    if risk_ids != projection_ids:
        missing_risk = sorted(projection_ids - risk_ids)
        missing_projection = sorted(risk_ids - projection_ids)
        raise ValueError(f"ID mismatch missing_risk={missing_risk} missing_projection={missing_projection}")
    return [(obstacle_id, risks_by_id[obstacle_id], projections_by_id[obstacle_id]) for obstacle_id in risks_by_id]


def visibility_eligible(status: str | VisibilityStatus) -> bool:
    value = VisibilityStatus(status)
    return value in {
        VisibilityStatus.FULLY_VISIBLE,
        VisibilityStatus.PARTIALLY_VISIBLE,
        VisibilityStatus.INTERSECTS_NEAR_PLANE,
    }


def nonzero_pixels(mask: Mask2D) -> set[tuple[int, int]]:
    pixels = set()
    for v in range(mask.height_px):
        for u in range(mask.width_px):
            if mask.get(u, v) > FLOAT_TOLERANCE:
                pixels.add((u, v))
    return pixels


def exclusive_pixels(target_pixels: set[tuple[int, int]], other_pixel_sets: Iterable[set[tuple[int, int]]]) -> set[tuple[int, int]]:
    exclusive = set(target_pixels)
    for pixels in other_pixel_sets:
        exclusive -= pixels
    return exclusive


def overlap_pixels(left: set[tuple[int, int]], right: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return left & right


def role_config_complete() -> bool:
    ids = [spec.obstacle_id for spec in OBSTACLE_SPECS]
    roles = [spec.role for spec in OBSTACLE_SPECS]
    defs = [spec.def_name for spec in OBSTACLE_SPECS]
    return len(ids) == len(set(ids)) == len(roles) == len(set(roles)) == len(defs) == len(set(defs))


def assert_no_future_actual_leakage(metadata: dict) -> None:
    source = metadata.get("trajectory_sources", {})
    if source.get("actual_future_trajectory_used") is not False:
        raise ValueError("metadata must state that actual future trajectory was not used")
    text = json.dumps(metadata, sort_keys=True).lower()
    forbidden = ("future_actual_position", "future_actual_velocity", "future_actual_yaw")
    found = [token for token in forbidden if token in text]
    if found:
        raise ValueError(f"metadata contains forbidden future-actual fields: {found}")


def compute_snapshot_products(
    *,
    snapshot_state: dict[str, float],
    analysis_time_s: float,
    obstacle_boxes: Sequence[ObstacleBox3D],
    intrinsics: CameraIntrinsics,
    extrinsics: CameraExtrinsics,
    risk_parameters: RiskParameters = RISK_PARAMETERS,
) -> tuple[list[TrajectoryPoint], list[TrajectoryPoint], dict[str, object], dict[str, ProjectedObstacle], ImageRiskMasks]:
    planned, state = build_trajectories(snapshot_state, analysis_time_s)
    risks: dict[str, object] = {}
    projections: dict[str, ProjectedObstacle] = {}
    bound: list[ProjectedObstacleRisk] = []
    for box in obstacle_boxes:
        footprint = obstacle_footprint_from_box(box)
        result = analyze_dual_trajectory_obstacle(planned, state, footprint, risk_parameters)
        projection = project_obstacle_box(box, intrinsics, extrinsics)
        risks[box.obstacle_id] = result
        projections[box.obstacle_id] = projection
    for obstacle_id, risk_result, projection in exact_join_risk_projection(risks, projections):
        bound.append(
            bind_projection_to_risk(
                projection,
                risk_result.planned_result.risk_score,
                risk_result.state_result.risk_score,
                risk_result.combined_risk_score,
            )
        )
    masks = build_image_risk_masks(intrinsics.width_px, intrinsics.height_px, bound)
    return planned, state, risks, projections, masks


def metadata_for_snapshot(
    *,
    episode_id: str,
    snapshot_time_s: float,
    frame_path: str,
    csv_path: str,
    masks_path: str,
    snapshot_state: dict[str, float],
    planned: Sequence[TrajectoryPoint],
    state: Sequence[TrajectoryPoint],
    obstacle_boxes: Sequence[ObstacleBox3D],
    camera_snapshot,
    trajectory_disagreement_m: float,
) -> dict:
    return {
        "episode_id": episode_id,
        "snapshot_time_s": snapshot_time_s,
        "frame_path": frame_path,
        "csv_path": csv_path,
        "masks_path": masks_path,
        "camera": {
            "width_px": camera_snapshot.width_px,
            "height_px": camera_snapshot.height_px,
            "horizontal_fov_rad": camera_snapshot.horizontal_fov_rad,
            "vertical_fov_rad": camera_snapshot.intrinsics.vertical_fov_rad,
            "near_clip_m": camera_snapshot.near_clip_m,
            "fx_px": camera_snapshot.intrinsics.fx_px,
            "fy_px": camera_snapshot.intrinsics.fy_px,
            "cx_px": camera_snapshot.intrinsics.cx_px,
            "cy_px": camera_snapshot.intrinsics.cy_px,
            "camera_world_position": camera_snapshot.camera_world_position,
            "camera_to_world_rotation": camera_snapshot.camera_to_world_rotation,
            "world_to_camera_rotation": camera_snapshot.extrinsics.world_to_camera_rotation,
            "world_to_camera_translation": camera_snapshot.extrinsics.world_to_camera_translation,
            "device_to_optical_rotation": camera_snapshot.extrinsics.device_to_optical_rotation,
            "axis_mapping": "x_optical=-y_device; y_optical=-z_device; z_optical=x_device",
        },
        "robot_snapshot_state": snapshot_state,
        "planned_trajectory_points": _trajectory_to_json(planned),
        "state_trajectory_points": _trajectory_to_json(state),
        "future_command_schedule": [
            {
                "start_offset_s": segment.start_offset_s,
                "end_offset_s": segment.end_offset_s,
                "left_wheel_command_rad_s": segment.left_wheel_command_rad_s,
                "right_wheel_command_rad_s": segment.right_wheel_command_rad_s,
            }
            for segment in future_command_segments(snapshot_time_s)
        ],
        "trajectory_sources": {
            "state_trajectory_source": "state-only constant-twist from current Webots snapshot state",
            "planned_trajectory_source": "command-conditioned rollout from pre-existing future wheel command schedule",
            "actual_future_trajectory_used": False,
        },
        "risk_parameters": {
            "corridor_radius_m": RISK_PARAMETERS.corridor_radius_m,
            "sigma_distance_m": RISK_PARAMETERS.sigma_distance_m,
            "tau_time_s": RISK_PARAMETERS.tau_time_s,
            "maximum_horizon_s": RISK_PARAMETERS.maximum_horizon_s,
            "geometry_tolerance_m": RISK_PARAMETERS.geometry_tolerance_m,
        },
        "mask_dimensions": {"width_px": EXPECTED_CAMERA_WIDTH_PX, "height_px": EXPECTED_CAMERA_HEIGHT_PX, "layout": "row-major"},
        "trajectory_disagreement_m": trajectory_disagreement_m,
        "obstacle_3d_boxes": [
            {
                "obstacle_id": box.obstacle_id,
                "center_x": box.center_x,
                "center_y": box.center_y,
                "center_z": box.center_z,
                "size_x": box.size_x,
                "size_y": box.size_y,
                "size_z": box.size_z,
            }
            for box in obstacle_boxes
        ],
        "obstacle_2d_footprints": [
            {
                "obstacle_id": box.obstacle_id,
                "center_x": box.center_x,
                "center_y": box.center_y,
                "size_x": box.size_x,
                "size_y": box.size_y,
            }
            for box in obstacle_boxes
        ],
    }


def obstacle_boxes_from_metadata(metadata: dict) -> list[ObstacleBox3D]:
    return [
        ObstacleBox3D(
            item["obstacle_id"],
            float(item["center_x"]),
            float(item["center_y"]),
            float(item["center_z"]),
            float(item["size_x"]),
            float(item["size_y"]),
            float(item["size_z"]),
        )
        for item in metadata["obstacle_3d_boxes"]
    ]


def camera_models_from_metadata(metadata: dict) -> tuple[CameraIntrinsics, CameraExtrinsics]:
    camera = metadata["camera"]
    intrinsics = CameraIntrinsics(
        int(camera["width_px"]),
        int(camera["height_px"]),
        float(camera["fx_px"]),
        float(camera["fy_px"]),
        float(camera["cx_px"]),
        float(camera["cy_px"]),
        float(camera["near_clip_m"]),
    )
    extrinsics = CameraExtrinsics(
        tuple(tuple(float(value) for value in row) for row in camera["world_to_camera_rotation"]),
        tuple(float(value) for value in camera["world_to_camera_translation"]),
        tuple(tuple(float(value) for value in row) for row in camera["device_to_optical_rotation"]),
    )
    return intrinsics, extrinsics


def trajectories_from_metadata(metadata: dict) -> tuple[list[TrajectoryPoint], list[TrajectoryPoint]]:
    return _trajectory_from_json(metadata["planned_trajectory_points"]), _trajectory_from_json(metadata["state_trajectory_points"])

