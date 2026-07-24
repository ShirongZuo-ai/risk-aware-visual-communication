"""Pre-motion M6-A v2 scene initialization and safe temporary-world wiring.

This module is deliberately Webots-import-free.  The actual Supervisor is passed
in by the controller entry; tests use a small fake Supervisor instead.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import tempfile
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_manifest_authority import load_and_validate_m6a_manifest
from scripts.run_m6a_one_identity import load_v2_runtime_config
from simulator.m5e_scenarios import generate_scenario


BASE_WORLD = PROJECT_ROOT / "simulator/worlds/m5e_dataset_generator.wbt"
BASE_WORLD_SHA256 = "52F79BF99E84D5264BB18AE9CDF05B976B4089AB4EA9A4018CD76A2A76D3863A"
CONTROLLER_NAME = "m6a_trusted_runtime"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(config: dict) -> dict:
    _, payload = load_and_validate_m6a_manifest(Path(config["v2_manifest_path"]), Path(config["v2_lock_path"]))
    matches = [item for item in payload["records"] if item["source_record_sha256"] == config["source_record_sha256"]]
    if len(matches) != 1 or matches[0]["identity"]["split"] not in {"pilot", "calibration", "formal"}:
        raise ValueError("runtime config does not identify one frozen source")
    return matches[0]


def _scene_geometry(record: dict):
    """Reuse M5E's sole geometry primitive with the v2 record's exact scene/seed.

    M5E's existing primitive requires one of its historical split labels, but
    its geometry is a function only of scene and seed.  `formal` is used only
    to obtain that split-invariant geometry; the v2 identity remains pilot and
    no M5 data or split mapping is used.
    """
    identity = record["identity"]
    config = generate_scenario(identity["scenario_id"], "formal", identity["seed"])
    frozen = record["scene_config"]
    expected_schedule = [asdict(item) for item in config.command_schedule]
    if (frozen["scene_id"], frozen["seed"], frozen["initial_pose"], frozen["schedule"], frozen["duration_s"]) != (
        config.scenario_id, config.seed, list(config.start_pose), expected_schedule, str(config.duration_seconds)
    ):
        raise ValueError("M5E primitive geometry does not match the frozen v2 record")
    return config


def _vrml(spec) -> str:
    x, y, z = spec.center_world
    sx, sy, sz = spec.size_xyz
    r, g, b = spec.display_color
    return f'''DEF {spec.obstacle_id} Solid {{
  translation {x:.9f} {y:.9f} {z:.9f}
  rotation 0 0 1 0
  children [
    DEF {spec.obstacle_id}_SHAPE Shape {{
      appearance PBRAppearance {{ baseColor {r:.6f} {g:.6f} {b:.6f} roughness 0.6 metalness 0 }}
      geometry Box {{ size {sx:.9f} {sy:.9f} {sz:.9f} }}
    }}
  ]
  boundingObject Box {{ size {sx:.9f} {sy:.9f} {sz:.9f} }}
  physics NULL
  locked TRUE
}}'''


def _obstacle_state(supervisor, spec) -> dict:
    node = supervisor.getFromDef(spec.obstacle_id)
    shape = supervisor.getFromDef(f"{spec.obstacle_id}_SHAPE")
    if node is None or shape is None:
        raise ValueError(f"missing initialized obstacle DEF: {spec.obstacle_id}")
    geometry = shape.getField("geometry").getSFNode()
    translation = tuple(float(x) for x in node.getField("translation").getSFVec3f())
    rotation = tuple(float(x) for x in node.getField("rotation").getSFRotation())
    size = tuple(float(x) for x in geometry.getField("size").getSFVec3f())
    actual = {"obstacle_id": spec.obstacle_id, "center_world": [round(x, 9) for x in translation], "size_xyz": [round(x, 9) for x in size], "orientation": [round(x, 9) for x in rotation]}
    expected = {"obstacle_id": spec.obstacle_id, "center_world": [round(x, 9) for x in spec.center_world], "size_xyz": [round(x, 9) for x in spec.size_xyz], "orientation": [round(x, 9) for x in spec.orientation]}
    if actual != expected:
        raise ValueError(f"obstacle read-back mismatch: {spec.obstacle_id}")
    return actual


@dataclass(frozen=True)
class SceneInitializationEvidence:
    source_record_sha256: str
    seed: int
    frozen_scene_config_sha256: str
    applied_scene_config_sha256: str
    obstacle_state_sha256: str
    initial_pose_sha256: str
    scene_initialized_before_motion: bool
    actual_future_usage: int = 0
    combined_mask_usage: int = 0


@dataclass(frozen=True)
class TemporaryWorldEvidence:
    source_world_path: str
    source_world_sha256: str
    temporary_world_path: str
    temporary_world_sha256: str
    controller_wiring_sha256: str
    allowed_changes: tuple[str, ...]
    scene_geometry_authority: str
    scene_initialized_before_motion: bool


def initialize_v2_scene_before_motion(runtime_config: dict, supervisor) -> SceneInitializationEvidence:
    """Apply exactly one frozen v2 scene before camera, motors, or snapshots exist."""
    load_v2_runtime_config(runtime_config)
    record = _record(runtime_config)
    scene = _scene_geometry(record)
    robot = supervisor.getFromDef(runtime_config["robot_def"])
    group = supervisor.getFromDef("M5E_OBSTACLES")
    if robot is None or group is None:
        raise ValueError("required M6-A robot or obstacle group DEF is missing")
    children = group.getField("children")
    if children is None or children.getCount() != 0:
        raise ValueError("obstacle group must be empty before the sole scene initialization")
    translation = robot.getField("translation")
    rotation = robot.getField("rotation")
    if translation is None or rotation is None:
        raise ValueError("robot pose fields are missing")
    translation.setSFVec3f([scene.start_pose[0], scene.start_pose[1], 0.0])
    rotation.setSFRotation([0.0, 0.0, 1.0, scene.start_pose[2]])
    if hasattr(robot, "resetPhysics"):
        robot.resetPhysics()
    applied_pose = [float(x) for x in translation.getSFVec3f()] + [float(x) for x in rotation.getSFRotation()]
    expected_pose = [scene.start_pose[0], scene.start_pose[1], 0.0, 0.0, 0.0, 1.0, scene.start_pose[2]]
    if applied_pose != expected_pose:
        raise ValueError("initial pose read-back mismatch")
    for spec in scene.obstacle_specs:
        children.importMFNodeFromString(-1, _vrml(spec))
    states = [_obstacle_state(supervisor, spec) for spec in scene.obstacle_specs]
    frozen_digest = record["scene_config_sha256"]
    if frozen_digest != digest(record["scene_config"]):
        raise ValueError("frozen scene-config digest mismatch")
    return SceneInitializationEvidence(record["source_record_sha256"], scene.seed, frozen_digest, digest(record["scene_config"]), digest(states), digest(applied_pose), True)


def _safe_temporary_target(target: Path) -> None:
    resolved = target.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root not in resolved.parents or resolved.exists() or resolved == BASE_WORLD.resolve():
        raise ValueError("temporary world target must be a new path under the system temporary directory")
    lowered = {part.lower() for part in resolved.parts}
    if {"m5", "data", "pilot"} & lowered:
        raise ValueError("temporary world target is in a protected output path")


def materialize_m6a_temporary_world(runtime_config: dict, target_world_path: str | Path) -> TemporaryWorldEvidence:
    """Atomically wire a controller into an immutable base world; geometry remains runtime-owned."""
    load_v2_runtime_config(runtime_config)
    record = _record(runtime_config)
    source = (PROJECT_ROOT / record["source_world_path"]).resolve()
    if source != BASE_WORLD.resolve() or _sha256(source).upper() != BASE_WORLD_SHA256 or runtime_config.get("source_world_sha256", "").upper() != BASE_WORLD_SHA256:
        raise ValueError("base world path or hash mismatch")
    target = Path(target_world_path)
    _safe_temporary_target(target)
    original = source.read_text(encoding="utf-8")
    old = '  controller "m5e_dataset_generator"'
    new = f'  controller "{CONTROLLER_NAME}"'
    if original.count(old) != 1 or original.count('  supervisor TRUE') != 1:
        raise ValueError("base world wiring structure is not the frozen expected structure")
    materialized = original.replace(old, new)
    if materialized.replace(new, old) != original or '  supervisor TRUE' not in materialized:
        raise ValueError("unknown temporary-world transformation")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(materialized, encoding="utf-8", newline="")
        temporary.replace(target)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return TemporaryWorldEvidence(str(source), _sha256(source), str(target.resolve()), _sha256(target), digest({"controller": CONTROLLER_NAME, "supervisor": True}), ("controller:m5e_dataset_generator->m6a_trusted_runtime", "supervisor:TRUE (preserved)"), "controller_pre_motion_v2_source_record", True)
