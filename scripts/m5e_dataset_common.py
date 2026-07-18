"""Shared deterministic path and manifest helpers for the M5E-B smoke dataset."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulator.m5e_config import M5E_GENERATOR_VERSION
from simulator.m5e_dataset_schema import MANIFEST_FIELDS, episode_id, read_manifest as _read_manifest, write_manifest as _write_manifest
from simulator.m5e_scenarios import ScenarioConfig, config_dict, config_hash


def resolve_output_root(output_root: str) -> Path:
    path = Path(output_root)
    if path.is_absolute():
        raise ValueError("output root must be relative to the repository root")
    resolved = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT not in resolved.parents and resolved != PROJECT_ROOT:
        raise ValueError("output root must remain within the repository root")
    return resolved


def relative_to_project(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def episode_directory(output_root: Path, config: ScenarioConfig, original_seed: int | None = None, replacement_index: int = 0) -> Path:
    return output_root / "metadata" / "m5e" / config.split / config.scenario_id / episode_id(
        config, original_seed, replacement_index
    )


def summary_path(output_root: Path, config: ScenarioConfig, original_seed: int | None = None, replacement_index: int = 0) -> Path:
    return episode_directory(output_root, config, original_seed, replacement_index) / "episode_summary.json"


def job_path(output_root: Path, config: ScenarioConfig, original_seed: int | None = None, replacement_index: int = 0) -> Path:
    return output_root / "metadata" / "m5e" / "_jobs" / f"{episode_id(config, original_seed, replacement_index)}.json"


def write_job(
    output_root: Path,
    config: ScenarioConfig,
    original_seed: int | None = None,
    replacement_index: int = 0,
) -> Path:
    origin = config.seed if original_seed is None else original_seed
    destination = job_path(output_root, config, origin, replacement_index)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generator_version": M5E_GENERATOR_VERSION,
        "output_root": relative_to_project(output_root),
        "summary_path": relative_to_project(summary_path(output_root, config, origin, replacement_index)),
        "replacement_index": replacement_index,
        "scenario_config": config_dict(config),
        "config_hash": config_hash(config),
        "episode_id": episode_id(config, origin, replacement_index),
        "original_seed": origin,
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(output_root: Path) -> Path:
    return output_root / "logs" / "m5" / "m5e_dataset_manifest.csv"


def manifest_row(summary: dict[str, Any], snapshot: dict[str, Any], scenario_validation_passed: bool) -> dict[str, str]:
    metadata = load_json(PROJECT_ROOT / snapshot["metadata_path"])
    visibility = metadata["visibility_counts"]
    state = metadata["robot_snapshot_state"]
    return {
        "split": summary["split"],
        "scenario_id": summary["scenario_id"],
        "scenario_name": summary["scenario_name"],
        "original_seed": str(summary["original_seed"]),
        "actual_seed": str(summary["actual_seed"]),
        "replacement_index": str(summary["replacement_index"]),
        "episode_id": summary["episode_id"],
        "episode_status": summary["status"],
        "snapshot_index": str(metadata["snapshot_index"]),
        "target_progress": f"{metadata['target_progress']:.9f}",
        "actual_progress": f"{metadata['actual_progress']:.9f}",
        "simulation_time_s": f"{metadata['simulation_time_s']:.9f}",
        "webots_step": str(metadata["webots_step"]),
        "frame_path": metadata["frame_path"],
        "frame_sha256": metadata["frame_sha256"],
        "metadata_path": snapshot["metadata_path"],
        "mask_path": metadata["masks_path"],
        "mask_sha256": metadata["masks_sha256"],
        "combined_mask_sha256": metadata["combined_mask_sha256"],
        "robot_x": f"{state['x']:.9f}", "robot_y": f"{state['y']:.9f}", "robot_yaw": f"{state['yaw_rad']:.9f}",
        "linear_velocity": f"{state['linear_velocity_m_s']:.9f}", "angular_velocity": f"{state['angular_velocity_rad_s']:.9f}",
        "planned_yaw_change": f"{metadata['planned_yaw_change']:.9f}", "state_yaw_change": f"{metadata['state_yaw_change']:.9f}",
        "trajectory_disagreement_m": f"{metadata['trajectory_disagreement_m']:.9f}",
        "eligible_obstacle_count": str(metadata["eligible_obstacle_count"]),
        "combined_risk_sum": f"{metadata['combined_risk_sum']:.12f}",
        "combined_risk_max": f"{metadata['combined_risk_max']:.12f}",
        "risk_support_pixel_count": str(metadata["risk_support_pixel_count"]),
        "high_risk_pixel_count": str(metadata["high_risk_pixel_count"]),
        "object_union_pixel_count": str(metadata["object_union_pixel_count"]),
        "partial_visible_count": str(visibility.get("partially_visible", 0)),
        "outside_count": str(visibility.get("outside_frustum", 0)),
        "behind_count": str(visibility.get("behind_camera", 0)),
        "scenario_validation_passed": str(scenario_validation_passed).lower(),
        "scenario_validation_reasons": "",
        "actual_future_trajectory_used": "false",
        "valid_for_calibration": "false",
        "valid_for_formal": "false",
    }


def write_manifest(output_root: Path, rows: Iterable[dict[str, str]]) -> Path:
    destination = manifest_path(output_root)
    _write_manifest(rows, destination)
    return destination


def read_manifest(output_root: Path) -> list[dict[str, str]]:
    return _read_manifest(manifest_path(output_root))


def episode_manifest_path(output_root: Path) -> Path:
    return output_root / "metadata" / "m5e" / "m5e_episode_manifest.json"


def write_episode_manifest(output_root: Path, summaries: Iterable[dict[str, Any]]) -> Path:
    destination = episode_manifest_path(output_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    episodes = sorted(
        (
            {
                "scenario_id": item["scenario_id"], "episode_id": item["episode_id"],
                "original_seed": item["original_seed"], "actual_seed": item["actual_seed"],
                "replacement_index": item["replacement_index"], "status": item["status"],
                "config_hash": item["config_hash"], "completed_snapshot_count": item["completed_snapshot_count"],
                "actual_future_trajectory_used": item["actual_future_trajectory_used"],
            }
            for item in summaries
        ),
        key=lambda item: (item["scenario_id"], item["replacement_index"], item["actual_seed"]),
    )
    payload = {"generator_version": M5E_GENERATOR_VERSION, "split": "smoke", "episode_count": len(episodes), "episodes": episodes}
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
