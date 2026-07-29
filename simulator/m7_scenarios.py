"""Deterministic, outcome-blind scene definitions for the M7 v1 corpus."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random

from evaluation.region_masks import _rasterize_polygon
from navigation.trajectory_prediction import (
    CommandSegment,
    TrajectoryPoint,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
    wheel_commands_to_twist,
)
from perception.camera_models import CameraExtrinsics, CameraIntrinsics, ObstacleBox3D
from perception.camera_projection import project_obstacle_box
from risk_map.geometry import corridor_intervals_for_trajectory
from risk_map.models import ObstacleFootprint
from scripts.m6a_trusted_artifacts import digest
from simulator.adapters.webots_camera_adapter import DEVICE_TO_OPTICAL_ROTATION
from simulator.m3c_config import RISK_PARAMETERS
from simulator.m5e_scenarios import M5EObstacleSpec, WheelCommandPhase


M7_SCENE_GENERATOR_VERSION = "m7-v1-scenes-1.0"
SCENE_IDS = ("M7C1", "M7C2", "M7C3", "M7C4", "M7C5", "M7C6", "M7G1", "M7G2")
CRITICAL_SCENES = frozenset(SCENE_IDS[:6])
GENERALIZATION_SCENES = frozenset(SCENE_IDS[6:])
SNAPSHOT_TIMES_S = (1.216, 2.688, 4.192, 5.408)


@dataclass(frozen=True)
class M7ScenarioConfig:
    scenario_id: str
    scenario_name: str
    split: str
    seed: int
    start_pose: tuple[float, float, float]
    command_schedule: tuple[WheelCommandPhase, ...]
    duration_seconds: float
    trajectory_horizon_s: float
    obstacle_specs: tuple[M5EObstacleSpec, ...]
    event_obstacle_ids: tuple[str, ...]
    event_snapshot_ids: tuple[str, ...]
    scene_role: str
    generator_version: str = M7_SCENE_GENERATOR_VERSION


def _schedule(scene: str) -> tuple[WheelCommandPhase, ...]:
    if scene in {"M7C1", "M7G1"}:
        return (WheelCommandPhase("straight", 0.0, 6.0, 2.0, 2.0),)
    if scene in {"M7C2", "M7G2"}:
        return (
            WheelCommandPhase("approach", 0.0, 2.0, 2.0, 2.0),
            WheelCommandPhase("left_arc", 2.0, 6.0, 1.0, 2.0),
        )
    if scene == "M7C3":
        return (
            WheelCommandPhase("approach", 0.0, 2.0, 2.0, 2.0),
            WheelCommandPhase("right_arc", 2.0, 6.0, 2.0, 1.0),
        )
    if scene == "M7C4":
        return (
            WheelCommandPhase("left_arc", 0.0, 3.0, 1.0, 2.0),
            WheelCommandPhase("right_arc", 3.0, 6.0, 2.0, 1.0),
        )
    if scene == "M7C5":
        return (
            WheelCommandPhase("straight", 0.0, 3.0, 2.0, 2.0),
            WheelCommandPhase("right_arc", 3.0, 6.0, 2.0, 1.0),
        )
    if scene == "M7C6":
        return (
            WheelCommandPhase("right_arc", 0.0, 2.0, 2.0, 1.0),
            WheelCommandPhase("left_arc", 2.0, 4.0, 1.0, 2.0),
            WheelCommandPhase("straight", 4.0, 6.0, 2.0, 2.0),
        )
    raise ValueError("unknown M7 scene")


def _integrate_pose(schedule: tuple[WheelCommandPhase, ...], time_s: float) -> tuple[float, float, float, float, float]:
    x = y = yaw = elapsed = 0.0
    linear = angular = 0.0
    for phase in schedule:
        if elapsed >= time_s:
            break
        end = min(time_s, phase.end_s)
        dt = end - max(elapsed, phase.start_s)
        if dt <= 0:
            continue
        linear, angular = wheel_commands_to_twist(phase.left_rad_s, phase.right_rad_s)
        if abs(angular) < 1e-12:
            x += linear * math.cos(yaw) * dt
            y += linear * math.sin(yaw) * dt
        else:
            next_yaw = yaw + angular * dt
            radius = linear / angular
            x += radius * (math.sin(next_yaw) - math.sin(yaw))
            y -= radius * (math.cos(next_yaw) - math.cos(yaw))
            yaw = math.atan2(math.sin(next_yaw), math.cos(next_yaw))
        elapsed = end
    current = next(item for item in schedule if item.start_s <= time_s < item.end_s or math.isclose(time_s, item.end_s) and item is schedule[-1])
    linear, angular = wheel_commands_to_twist(current.left_rad_s, current.right_rad_s)
    return x, y, yaw, linear, angular


def _command_segments(schedule: tuple[WheelCommandPhase, ...]) -> tuple[CommandSegment, ...]:
    return tuple(CommandSegment(item.start_s, item.end_s, item.left_rad_s, item.right_rad_s) for item in schedule)


def _obstacle(scene: str, name: str, role: str, center: tuple[float, float], size: tuple[float, float, float], color: tuple[float, float, float], *, risk: str) -> M5EObstacleSpec:
    return M5EObstacleSpec(
        obstacle_id=f"M7_{scene}_{name}", role=role,
        center_world=(center[0], center[1], size[2] / 2.0), size_xyz=size,
        orientation=(0.0, 0.0, 1.0, 0.0), display_color=color,
        expected_visibility_role="geometrically_visible", expected_risk_role=risk,
    )


def _critical_obstacle(scene: str, seed: int, schedule: tuple[WheelCommandPhase, ...]) -> M5EObstacleSpec:
    x, y, yaw, linear, angular = _integrate_pose(schedule, SNAPSHOT_TIMES_S[0])
    planned = predict_command_conditioned_trajectory(
        x=x, y=y, yaw_rad=yaw, command_segments=_command_segments(schedule), horizon_s=2.0, step_s=0.032
    )
    endpoint = planned[-1]
    jitter = random.Random(seed * 97 + SCENE_IDS.index(scene)).uniform(-0.001, 0.001)
    # The disagreement scene turns through enough yaw that its outer-normal
    # event would leave the frozen 0.84-rad camera frustum.  Its predeclared
    # event is mirrored to the inner normal; this choice is scene geometry,
    # fixed before any RGB or codec outcome exists.
    lateral = (0.043 + jitter) * (-1.0 if scene == "M7C4" else 1.0)
    forward = 0.020
    cx = endpoint.x + forward * math.cos(endpoint.yaw_rad) - lateral * math.sin(endpoint.yaw_rad)
    cy = endpoint.y + forward * math.sin(endpoint.yaw_rad) + lateral * math.cos(endpoint.yaw_rad)
    return _obstacle(scene, "CRITICAL", "predeclared_trajectory_critical", (cx, cy), (0.060, 0.020, 0.080), (0.90, 0.18, 0.12), risk="critical")


def _context_obstacle(scene: str, seed: int, *, generalization: bool) -> M5EObstacleSpec:
    jitter = random.Random(seed * 131 + SCENE_IDS.index(scene)).uniform(-0.002, 0.002)
    if generalization:
        center = (0.36 + jitter, 0.145 if scene == "M7G1" else -0.145)
        size = (0.080, 0.050, 0.080)
        role, risk = "visible_low_risk_generalization", "low"
    else:
        center = (0.42 + jitter, -0.145 if SCENE_IDS.index(scene) % 2 else 0.145)
        size = (0.070, 0.050, 0.070)
        role, risk = "visible_context_distractor", "context"
    return _obstacle(scene, "CONTEXT", role, center, size, (0.15, 0.38, 0.88), risk=risk)


def generate_m7_scenario(scene: str, seed: int) -> M7ScenarioConfig:
    if scene not in SCENE_IDS:
        raise ValueError("unknown M7 scene")
    if seed not in {710000 + (SCENE_IDS.index(scene) + 1) * 100 + offset for offset in range(2)}:
        raise ValueError("seed is not registered for this M7 scene")
    schedule = _schedule(scene)
    generalization = scene in GENERALIZATION_SCENES
    obstacles = (_context_obstacle(scene, seed, generalization=True),) if generalization else (
        _critical_obstacle(scene, seed, schedule),
        _context_obstacle(scene, seed, generalization=False),
    )
    value = M7ScenarioConfig(
        scene, {
            "M7C1":"straight_visible_critical", "M7C2":"left_turn_visible_critical",
            "M7C3":"right_turn_visible_critical", "M7C4":"trajectory_disagreement_visible_critical",
            "M7C5":"late_turn_visible_critical", "M7C6":"s_curve_visible_critical",
            "M7G1":"straight_low_risk_generalization", "M7G2":"turn_low_risk_generalization",
        }[scene], "development", seed, (0.0, 0.0, 0.0), schedule, 6.0, 2.0,
        obstacles, () if generalization else (obstacles[0].obstacle_id,), () if generalization else ("0",),
        "low_risk_generalization" if generalization else "visible_trajectory_critical",
    )
    validate_m7_scenario(value)
    return value


def _projection(spec: M5EObstacleSpec, pose: tuple[float, float, float, float, float]) -> int:
    x, y, yaw, _, _ = pose
    c, s = math.cos(yaw), math.sin(yaw)
    rotation = ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
    intrinsics = CameraIntrinsics.from_horizontal_fov(160, 120, 0.84, 0.005)
    extrinsics = CameraExtrinsics.from_camera_pose_in_world(rotation, (x, y, 0.03), DEVICE_TO_OPTICAL_ROTATION)
    box = ObstacleBox3D(spec.obstacle_id, *spec.center_world, *spec.size_xyz)
    projected = project_obstacle_box(box, intrinsics, extrinsics)
    polygon = tuple((point.u_px, point.v_px) for point in projected.clipped_polygon)
    return len(_rasterize_polygon(polygon, 160, 120))


def geometric_event_evidence(config: M7ScenarioConfig) -> dict:
    schedule = _command_segments(config.command_schedule)
    observations = []
    for index, timestamp in enumerate(SNAPSHOT_TIMES_S):
        pose = _integrate_pose(config.command_schedule, timestamp)
        x, y, yaw, linear, angular = pose
        planned = tuple(predict_command_conditioned_trajectory(x=x, y=y, yaw_rad=yaw, command_segments=schedule, horizon_s=2.0, step_s=0.032))
        state = tuple(predict_state_only_trajectory(x=x, y=y, yaw_rad=yaw, linear_velocity_m_s=linear, angular_velocity_rad_s=angular, horizon_s=2.0, step_s=0.032))
        for spec in config.obstacle_specs:
            footprint = ObstacleFootprint(spec.obstacle_id, spec.center_world[0], spec.center_world[1], spec.size_xyz[0], spec.size_xyz[1])
            planned_hit = bool(corridor_intervals_for_trajectory(planned, footprint, RISK_PARAMETERS.corridor_radius_m, RISK_PARAMETERS.geometry_tolerance_m))
            state_hit = bool(corridor_intervals_for_trajectory(state, footprint, RISK_PARAMETERS.corridor_radius_m, RISK_PARAMETERS.geometry_tolerance_m))
            observations.append({
                "snapshot_id": str(index), "timestamp_s": timestamp, "obstacle_id": spec.obstacle_id,
                "planned_corridor_intersection": planned_hit, "state_corridor_intersection": state_hit,
                "trajectory_critical": planned_hit or state_hit, "clipped_projected_pixels": _projection(spec, pose),
            })
    declared = [item for item in observations if item["obstacle_id"] in config.event_obstacle_ids and item["snapshot_id"] in config.event_snapshot_ids]
    if config.scene_role == "visible_trajectory_critical":
        passed = bool(declared) and all(item["trajectory_critical"] and item["clipped_projected_pixels"] >= 64 for item in declared)
    else:
        passed = not any(item["trajectory_critical"] for item in observations)
    evidence = {
        "schema_version": "m7-v1-geometric-event-precheck-v1", "scene": config.scenario_id,
        "seed": config.seed, "scene_role": config.scene_role,
        "declared_event_obstacle_ids": list(config.event_obstacle_ids),
        "declared_event_snapshot_ids": list(config.event_snapshot_ids),
        "uses_rgb_or_codec_outcomes": False, "observations": observations, "passed": passed,
    }
    evidence["evidence_sha256"] = digest(evidence)
    if not passed:
        raise ValueError("M7 geometric event precheck failed")
    return evidence


def evaluator_only_geometry(config: M7ScenarioConfig) -> dict:
    value = {
        "schema_version": "m7-v1-evaluator-only-obstacle-geometry-v1",
        "scene": config.scenario_id, "seed": config.seed,
        "obstacles": [asdict(item) for item in config.obstacle_specs],
        "event_obstacle_ids": list(config.event_obstacle_ids),
        "event_snapshot_ids": list(config.event_snapshot_ids),
        "availability": "evaluator-only; forbidden to sender and allocator",
    }
    value["geometry_sha256"] = digest(value)
    return value


def validate_m7_scenario(config: M7ScenarioConfig) -> None:
    if config.scenario_id not in SCENE_IDS or config.split != "development" or config.duration_seconds != 6.0 or config.trajectory_horizon_s != 2.0:
        raise ValueError("invalid M7 scenario identity")
    if config.scene_role not in {"visible_trajectory_critical", "low_risk_generalization"}:
        raise ValueError("invalid M7 scene role")
    if not config.obstacle_specs or len({item.obstacle_id for item in config.obstacle_specs}) != len(config.obstacle_specs):
        raise ValueError("invalid M7 obstacles")
    previous = 0.0
    for phase in config.command_schedule:
        if phase.start_s != previous or phase.end_s <= phase.start_s:
            raise ValueError("invalid M7 schedule")
        previous = phase.end_s
    if previous != config.duration_seconds:
        raise ValueError("incomplete M7 schedule")


def canonical_scene(config: M7ScenarioConfig) -> dict:
    return asdict(config)
