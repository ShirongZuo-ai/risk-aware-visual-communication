"""Frozen M6 trajectory-critical obstacle boundary recall (TCOBR)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import cv2
import numpy as np

from evaluation.region_masks import _rasterize_polygon
from navigation.trajectory_prediction import TrajectoryPoint
from perception.camera_models import CameraExtrinsics, CameraIntrinsics, ObstacleBox3D
from perception.camera_projection import project_obstacle_box
from risk_map.geometry import corridor_intervals_for_trajectory
from risk_map.models import ObstacleFootprint
from scripts.m6a_dual_roi import CurrentState, Method, ScheduleEvidence, predict
from scripts.m6a_trusted_artifacts import digest
from simulator.m4d_config import RISK_PARAMETERS
from simulator.m5e_scenarios import generate_scenario


SCHEMA = "m6-tcobr-case-v1"
CANNY_LOW = 50
CANNY_HIGH = 150
MATCH_RADIUS_PX = 1
MIN_PROJECTED_PIXELS = 64
MIN_ORIGINAL_BOUNDARY_EDGES = 16
RECALL_THRESHOLD = 0.50


@dataclass(frozen=True)
class TCOBRInstanceEvidence:
    obstacle_id: str
    critical: bool
    projected_pixel_count: int
    original_boundary_edge_count: int
    matched_boundary_edge_count: int
    boundary_edge_recall: float | None
    eligible: bool
    recalled: bool | None
    exclusion_reason: str | None


@dataclass(frozen=True)
class TCOBRCaseEvidence:
    schema_version: str
    scene: str
    seed: int
    snapshot_id: str
    method: str
    budget: str
    original_sha256: str
    reconstruction_sha256: str
    geometry_digest: str
    eligible_count: int
    recalled_count: int
    tcobr: float | None
    instances: tuple[TCOBRInstanceEvidence, ...]
    evidence_sha256: str


def camera_context_from_snapshot(snapshot) -> dict:
    """Canonical camera evidence from the accepted M4 Webots adapter."""
    return {
        "intrinsics": asdict(snapshot.intrinsics),
        "extrinsics": asdict(snapshot.extrinsics),
        "camera_world_position": list(snapshot.camera_world_position),
        "camera_to_world_rotation": [list(row) for row in snapshot.camera_to_world_rotation],
    }


def _camera_models(context: dict) -> tuple[CameraIntrinsics, CameraExtrinsics]:
    if not isinstance(context, dict) or set(context) != {
        "intrinsics", "extrinsics", "camera_world_position", "camera_to_world_rotation"
    }:
        raise ValueError("invalid TCOBR camera context")
    intrinsics = CameraIntrinsics(**context["intrinsics"])
    extrinsics = CameraExtrinsics(
        tuple(tuple(float(v) for v in row) for row in context["extrinsics"]["world_to_camera_rotation"]),
        tuple(float(v) for v in context["extrinsics"]["world_to_camera_translation"]),
        tuple(tuple(float(v) for v in row) for row in context["extrinsics"]["device_to_optical_rotation"]),
    )
    if intrinsics.width_px != 160 or intrinsics.height_px != 120:
        raise ValueError("TCOBR requires the frozen 160x120 camera")
    return intrinsics, extrinsics


def _trajectory(value) -> tuple[TrajectoryPoint, ...]:
    points = tuple(value)
    if not points:
        raise ValueError("empty TCOBR trajectory")
    return points


def _boundary_mask(polygon: tuple[tuple[float, float], ...], width: int, height: int) -> tuple[np.ndarray, int]:
    filled = np.zeros((height, width), dtype=np.uint8)
    pixels = _rasterize_polygon(polygon, width, height)
    for u, v in pixels:
        filled[v, u] = 1
    eroded = cv2.erode(filled, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return (filled & (1 - eroded)).astype(bool), len(pixels)


def _obstacle_box(spec) -> ObstacleBox3D:
    return ObstacleBox3D(spec.obstacle_id, *spec.center_world, *spec.size_xyz)


def evaluate_tcobr_case(
    *,
    scene: str,
    seed: int,
    snapshot_id: str,
    method: str,
    budget: str,
    original: np.ndarray,
    reconstruction: np.ndarray,
    state: CurrentState,
    schedule: ScheduleEvidence,
    snapshot_time_s: float,
    camera_context: dict,
    original_sha256: str,
    reconstruction_sha256: str,
) -> TCOBRCaseEvidence:
    """Evaluate one reconstruction using a method-independent critical set."""
    if method not in {Method.STATE_ONLY_RISK_ROI.value, Method.COMMAND_CONDITIONED_RISK_ROI.value}:
        raise ValueError("unfrozen TCOBR method")
    if original.shape != (120, 160, 3) or reconstruction.shape != original.shape:
        raise ValueError("invalid TCOBR image shape")
    intrinsics, extrinsics = _camera_models(camera_context)
    planned = _trajectory(predict(Method.COMMAND_CONDITIONED_RISK_ROI, state, schedule=schedule, snapshot_time_s=snapshot_time_s))
    state_only = _trajectory(predict(Method.STATE_ONLY_RISK_ROI, state))
    scene_config = generate_scenario(scene, "formal", seed)
    original_edges = cv2.Canny(cv2.cvtColor(original, cv2.COLOR_RGB2GRAY), CANNY_LOW, CANNY_HIGH) > 0
    reconstructed_edges = cv2.Canny(cv2.cvtColor(reconstruction, cv2.COLOR_RGB2GRAY), CANNY_LOW, CANNY_HIGH) > 0
    matched_edges = cv2.dilate(reconstructed_edges.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), iterations=1) > 0
    instances: list[TCOBRInstanceEvidence] = []
    geometry_items = []
    for spec in sorted(scene_config.obstacle_specs, key=lambda item: item.obstacle_id):
        box = _obstacle_box(spec)
        footprint = ObstacleFootprint(spec.obstacle_id, box.center_x, box.center_y, box.size_x, box.size_y)
        planned_hit = bool(corridor_intervals_for_trajectory(planned, footprint, RISK_PARAMETERS.corridor_radius_m, RISK_PARAMETERS.geometry_tolerance_m))
        state_hit = bool(corridor_intervals_for_trajectory(state_only, footprint, RISK_PARAMETERS.corridor_radius_m, RISK_PARAMETERS.geometry_tolerance_m))
        critical = planned_hit or state_hit
        projection = project_obstacle_box(box, intrinsics, extrinsics)
        polygon = tuple((point.u_px, point.v_px) for point in projection.clipped_polygon)
        boundary, projected_count = _boundary_mask(polygon, 160, 120)
        original_count = int(np.count_nonzero(original_edges & boundary))
        matched_count = int(np.count_nonzero(original_edges & boundary & matched_edges))
        recall = matched_count / original_count if original_count else None
        eligible = critical and projected_count >= MIN_PROJECTED_PIXELS and original_count >= MIN_ORIGINAL_BOUNDARY_EDGES
        reason = None
        if not critical:
            reason = "not_trajectory_critical"
        elif projected_count < MIN_PROJECTED_PIXELS:
            reason = "projected_pixels_below_64"
        elif original_count < MIN_ORIGINAL_BOUNDARY_EDGES:
            reason = "original_boundary_edges_below_16"
        recalled = (recall >= RECALL_THRESHOLD) if eligible else None
        instances.append(TCOBRInstanceEvidence(spec.obstacle_id, critical, projected_count, original_count, matched_count, recall, eligible, recalled, reason))
        geometry_items.append({"obstacle_id": spec.obstacle_id, "critical": critical, "polygon": polygon})
    eligible_count = sum(item.eligible for item in instances)
    recalled_count = sum(item.recalled is True for item in instances)
    tcobr = recalled_count / eligible_count if eligible_count else None
    base = {
        "schema_version": SCHEMA, "scene": scene, "seed": seed, "snapshot_id": snapshot_id,
        "method": method, "budget": budget, "original_sha256": original_sha256,
        "reconstruction_sha256": reconstruction_sha256, "geometry_digest": digest(geometry_items),
        "eligible_count": eligible_count, "recalled_count": recalled_count, "tcobr": tcobr,
        "instances": [asdict(item) for item in instances],
    }
    return TCOBRCaseEvidence(**base, evidence_sha256=digest(base))


def validate_tcobr_evidence(evidence: dict | TCOBRCaseEvidence) -> dict:
    value = asdict(evidence) if isinstance(evidence, TCOBRCaseEvidence) else dict(evidence)
    supplied = value.pop("evidence_sha256", None)
    if value.get("schema_version") != SCHEMA or supplied != digest(value):
        raise ValueError("invalid TCOBR canonical evidence")
    eligible = value.get("eligible_count")
    recalled = value.get("recalled_count")
    if not isinstance(eligible, int) or not isinstance(recalled, int) or not 0 <= recalled <= eligible:
        raise ValueError("invalid TCOBR counts")
    expected = recalled / eligible if eligible else None
    if value.get("tcobr") != expected or (expected is not None and not math.isfinite(expected)):
        raise ValueError("invalid TCOBR value")
    value["evidence_sha256"] = supplied
    return value
