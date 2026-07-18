"""Stable schema helpers for M5E-B manifest and episode metadata."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

from simulator.m5e_config import M5E_EPISODE_PREFIX
from simulator.m5e_scenarios import ScenarioConfig, config_hash


MANIFEST_FIELDS = (
    "split", "scenario_id", "scenario_name", "original_seed", "actual_seed", "replacement_index", "episode_id", "episode_status",
    "snapshot_index", "target_progress", "actual_progress", "simulation_time_s", "webots_step", "frame_path", "frame_sha256",
    "metadata_path", "mask_path", "mask_sha256", "combined_mask_sha256", "robot_x", "robot_y", "robot_yaw", "linear_velocity", "angular_velocity", "planned_yaw_change",
    "state_yaw_change", "trajectory_disagreement_m", "eligible_obstacle_count", "combined_risk_sum", "combined_risk_max",
    "risk_support_pixel_count", "high_risk_pixel_count", "object_union_pixel_count", "partial_visible_count", "outside_count",
    "behind_count", "scenario_validation_passed", "scenario_validation_reasons", "actual_future_trajectory_used",
    "valid_for_calibration", "valid_for_formal",
)


def episode_id(config: ScenarioConfig, original_seed: int | None = None, replacement_index: int = 0) -> str:
    suffix = "" if replacement_index == 0 else f"_replacement{replacement_index:02d}"
    origin = config.seed if original_seed is None else original_seed
    return f"{M5E_EPISODE_PREFIX}_{config.split}_{config.scenario_id.lower()}_seed{origin}_actual{config.seed}{suffix}"


def relative_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(rows: Iterable[dict[str, object]], path: Path) -> None:
    ordered = sorted(rows, key=lambda row: (str(row["split"]), str(row["scenario_id"]), int(row["actual_seed"]), int(row["snapshot_index"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ValueError("M5E manifest schema mismatch")
        return list(reader)


def episode_summary(config: ScenarioConfig, *, original_seed: int, replacement_index: int, status: str, snapshots: list[dict], failure_reason: str | None = None) -> dict:
    return {
        "generator_version": config.generator_version,
        "split": config.split,
        "scenario_id": config.scenario_id,
        "scenario_name": config.scenario_name,
        "duration_seconds": config.duration_seconds,
        "seed": config.seed,
        "config": json.loads(json.dumps(config, default=lambda item: item.__dict__, sort_keys=True)),
        "config_hash": config_hash(config),
        "episode_id": episode_id(config, original_seed, replacement_index),
        "original_seed": original_seed,
        "actual_seed": config.seed,
        "replacement_index": replacement_index,
        "status": status,
        "failure_reason": failure_reason,
        "completed_snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "actual_future_trajectory_used": False,
    }
