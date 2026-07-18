"""Independent integrity and scenario-rule validator for M5E-B datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from perception.camera_projection import project_obstacle_box
from risk_map.models import RiskParameters
from risk_map.image_risk_map import bind_projection_to_risk, build_image_risk_masks
from risk_map.trajectory_obstacle_risk import analyze_dual_trajectory_obstacle
from simulator.m5e_config import EXPECTED_CAMERA_HEIGHT_PX, EXPECTED_CAMERA_WIDTH_PX, EXPECTED_HORIZONTAL_FOV_RAD, EXPECTED_NEAR_CLIP_M, SNAPSHOT_PROGRESS_TOLERANCE, primary_seed, primary_seed_indices
from simulator.m5e_scenarios import config_hash, generate_scenario
from simulator.m5e_dataset_schema import MANIFEST_FIELDS
from simulator.m5e_snapshot_protocol import reference_progress
from scripts.m5e_dataset_common import episode_manifest_path, load_json, read_manifest, resolve_output_root, sha256_file
from scripts.m4d_image_risk_common import camera_models_from_metadata, decode_masks_json, obstacle_footprint_from_box, trajectories_from_metadata
from perception.camera_models import ObstacleBox3D
from evaluation.region_masks import _rasterize_polygon
from compression.tiled_jpeg import DEFAULT_M5_GRID


RISK_TOLERANCE = 1e-9


def _mask_arrays(payload: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    masks = decode_masks_json(payload["masks"])
    return (
        np.asarray(masks.planned.values, dtype=float).reshape(masks.planned.height_px, masks.planned.width_px),
        np.asarray(masks.state.values, dtype=float).reshape(masks.state.height_px, masks.state.width_px),
        np.asarray(masks.combined.values, dtype=float).reshape(masks.combined.height_px, masks.combined.width_px),
    )


def _combined_mask_hash(values: tuple[float, ...]) -> str:
    payload = json.dumps(list(values), separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _boxes(metadata: dict[str, Any]) -> list[ObstacleBox3D]:
    return [
        ObstacleBox3D(item["obstacle_id"], float(item["center_x"]), float(item["center_y"]), float(item["center_z"]),
                      float(item["size_x"]), float(item["size_y"]), float(item["size_z"]))
        for item in metadata["obstacles"]
    ]


def _eligible(record: dict[str, Any]) -> bool:
    return bool(record["eligible_for_mask"])


def _highest(records: list[dict[str, Any]], channel: str) -> dict[str, Any]:
    return max(records, key=lambda item: (float(item[f"{channel}_risk"]), item["obstacle_id"]))


def _area(record: dict[str, Any]) -> float:
    return float(record["candidate_pixel_count"])


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _channel_masks(metadata: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _mask_arrays(load_json(PROJECT_ROOT / metadata["masks_path"]))


def _risk_centroid_u(metadata: dict[str, Any]) -> float:
    combined = _channel_masks(metadata)[2]
    total = float(combined.sum())
    _assert(total > 0.0, "combined mask has zero risk mass")
    columns = np.arange(combined.shape[1], dtype=float)
    return float((combined * columns[np.newaxis, :]).sum() / total)


def _polygon_tile_ids(record: dict[str, Any]) -> set[int]:
    polygon = tuple((float(point[0]), float(point[1])) for point in record["clipped_polygon"])
    return {
        (v // DEFAULT_M5_GRID.tile_height_px) * DEFAULT_M5_GRID.columns + (u // DEFAULT_M5_GRID.tile_width_px)
        for u, v in _rasterize_polygon(polygon, EXPECTED_CAMERA_WIDTH_PX, EXPECTED_CAMERA_HEIGHT_PX)
    }


def _validate_snapshot(summary: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    metadata_path = PROJECT_ROOT / snapshot["metadata_path"]
    metadata = load_json(metadata_path)
    _assert(metadata["scenario_id"] == summary["scenario_id"], "scenario ID differs between summary and metadata")
    _assert(abs(float(metadata["actual_progress"]) - float(metadata["target_progress"])) <= SNAPSHOT_PROGRESS_TOLERANCE + 1e-12, "snapshot progress tolerance exceeded")
    _assert(abs(reference_progress(generate_scenario(summary["scenario_id"], summary["split"], int(summary["seed"])), float(metadata["simulation_time_s"])) - float(metadata["target_progress"])) <= SNAPSHOT_PROGRESS_TOLERANCE + 1e-12, "reference progress mismatch")
    camera = metadata["camera"]
    _assert((camera["width_px"], camera["height_px"]) == (EXPECTED_CAMERA_WIDTH_PX, EXPECTED_CAMERA_HEIGHT_PX), "unexpected camera resolution")
    _assert(abs(camera["horizontal_fov_rad"] - EXPECTED_HORIZONTAL_FOV_RAD) < 1e-12 and abs(camera["near_clip_m"] - EXPECTED_NEAR_CLIP_M) < 1e-12, "unexpected camera calibration")
    frame_path = PROJECT_ROOT / metadata["frame_path"]
    _assert(frame_path.exists() and frame_path.stat().st_size > 0, "missing or empty frame")
    _assert(sha256_file(frame_path) == metadata["frame_sha256"], "frame hash mismatch")
    with Image.open(frame_path) as frame:
        _assert(frame.size == (EXPECTED_CAMERA_WIDTH_PX, EXPECTED_CAMERA_HEIGHT_PX), "frame dimensions mismatch")
        _assert(frame.convert("RGB").getbbox() is not None, "frame contains no RGB content")
    mask_path = PROJECT_ROOT / metadata["masks_path"]
    _assert(sha256_file(mask_path) == metadata["masks_sha256"], "mask file hash mismatch")
    mask_payload = load_json(mask_path)
    planned, state, combined = _mask_arrays(mask_payload)
    for name, mask in (("planned", planned), ("state", state), ("combined", combined)):
        _assert(mask.shape == (EXPECTED_CAMERA_HEIGHT_PX, EXPECTED_CAMERA_WIDTH_PX), f"{name} mask shape mismatch")
        _assert(np.isfinite(mask).all() and (mask >= 0).all() and (mask <= 1).all(), f"{name} mask outside [0, 1]")
    _assert(np.allclose(combined, np.maximum(planned, state), atol=RISK_TOLERANCE, rtol=0.0), "combined mask is not pixelwise max")
    decoded_masks = decode_masks_json(mask_payload["masks"])
    _assert(_combined_mask_hash(decoded_masks.combined.values) == metadata["combined_mask_sha256"], "combined mask hash mismatch")
    intrinsics, extrinsics = camera_models_from_metadata(metadata)
    planned_trajectory, state_trajectory = trajectories_from_metadata(metadata)
    bindings = []
    for box, record in zip(_boxes(metadata), metadata["obstacles"]):
        risk = analyze_dual_trajectory_obstacle(
            planned_trajectory,
            state_trajectory,
            obstacle_footprint_from_box(box),
            RiskParameters(**metadata["risk_parameters"]),
        )
        _assert(abs(risk.planned_result.risk_score - record["planned_risk"]) <= RISK_TOLERANCE, "planned world-risk recomputation mismatch")
        _assert(abs(risk.state_result.risk_score - record["state_risk"]) <= RISK_TOLERANCE, "state world-risk recomputation mismatch")
        _assert(abs(risk.combined_risk_score - record["combined_risk"]) <= RISK_TOLERANCE, "combined world-risk recomputation mismatch")
        projection = project_obstacle_box(box, intrinsics, extrinsics)
        _assert(projection.visibility_status.value == record["visibility_status"], "projection visibility recomputation mismatch")
        bindings.append((record, projection, risk))
    recomputed = build_image_risk_masks(
        width_px=EXPECTED_CAMERA_WIDTH_PX,
        height_px=EXPECTED_CAMERA_HEIGHT_PX,
        obstacles=tuple(
            bind_projection_to_risk(projection, risk.planned_result.risk_score, risk.state_result.risk_score, risk.combined_risk_score)
            for _, projection, risk in bindings
        ),
    )
    _assert(np.allclose(planned.ravel(), recomputed.planned.values, atol=RISK_TOLERANCE, rtol=0.0), "planned mask recomputation mismatch")
    _assert(np.allclose(state.ravel(), recomputed.state.values, atol=RISK_TOLERANCE, rtol=0.0), "state mask recomputation mismatch")
    _assert(np.allclose(combined.ravel(), recomputed.combined.values, atol=RISK_TOLERANCE, rtol=0.0), "combined mask recomputation mismatch")
    _assert(metadata["actual_future_trajectory_used"] is False, "future actual trajectory leakage flag is false")
    _assert(metadata["eligible_obstacle_count"] > 0 and metadata["combined_risk_max"] > 0, "snapshot lacks eligible positive risk")
    return metadata


def _validate_scenario_rules(summary: dict[str, Any], metadata_by_snapshot: list[dict[str, Any]]) -> None:
    scenario = summary["scenario_id"]
    snapshot = metadata_by_snapshot[2]
    records = snapshot["obstacles"]
    eligible = [record for record in records if _eligible(record)]
    _assert(eligible, f"{scenario}: no eligible obstacle at snapshot 2")
    risk_max = _highest(eligible, "combined")
    cx = snapshot["camera"]["width_px"] / 2.0
    if scenario == "S1":
        _assert(abs(snapshot["planned_trajectory_points"][0]["yaw_rad"]) <= 0.10, "S1: planned yaw is not straight")
        _assert(risk_max["combined_risk"] >= 0.20 and risk_max["planned_enters_corridor"], "S1: conflict is not high planned risk")
        _assert(abs(_risk_centroid_u(snapshot) - cx) <= 12.0, "S1: risk-weighted mask centroid is not centered")
        _assert(snapshot["trajectory_disagreement_m"] < 0.03, "S1: trajectory disagreement too high")
    elif scenario == "S2":
        largest = max(eligible, key=lambda item: (_area(item), item["obstacle_id"]))
        _assert(largest["obstacle_id"] != risk_max["obstacle_id"], "S2: largest object is risk maximum")
        _assert(_area(largest) >= 2.0 * _area(risk_max), "S2: distractor is not sufficiently larger")
        _assert(not largest["planned_enters_corridor"] and not largest["state_enters_corridor"], "S2: distractor enters a trajectory")
        _assert(risk_max["planned_enters_corridor"] and risk_max["combined_risk"] >= 0.20, "S2: conflict lacks high planned risk")
    elif scenario == "S3":
        _assert(snapshot["planned_yaw_change"] >= 0.30, "S3: insufficient left turn")
        _assert(risk_max["combined_risk"] >= 0.20 and _risk_centroid_u(snapshot) <= cx - 12.0, "S3: left conflict condition failed")
    elif scenario == "S4":
        _assert(snapshot["planned_yaw_change"] <= -0.30, "S4: insufficient right turn")
        _assert(risk_max["combined_risk"] >= 0.20 and _risk_centroid_u(snapshot) >= cx + 12.0, "S4: right conflict condition failed")
    elif scenario == "S5":
        _assert(0.03 <= snapshot["trajectory_disagreement_m"] <= 0.12, "S5: disagreement outside target band")
        planned_max = _highest(eligible, "planned")
        state_max = _highest(eligible, "state")
        _assert(planned_max["obstacle_id"] != state_max["obstacle_id"], "S5: planned/state maxima are not different")
        _assert(planned_max["planned_risk"] >= 0.10 and state_max["state_risk"] >= 0.10, "S5: channel risks too weak")
        _assert(planned_max["planned_written_pixel_count"] > 0 and state_max["state_written_pixel_count"] > 0, "S5: channel contribution is absent")
        planned_margin = planned_max["planned_risk"] - max(item["planned_risk"] for item in eligible if item["obstacle_id"] != planned_max["obstacle_id"])
        state_margin = state_max["state_risk"] - max(item["state_risk"] for item in eligible if item["obstacle_id"] != state_max["obstacle_id"])
        _assert(planned_margin > 1e-9 and state_margin > 1e-9, "S5: risk ranking margin is not positive")
        planned_mask, state_mask, _ = _channel_masks(snapshot)
        _assert(not np.array_equal(planned_mask, state_mask), "S5: planned and state masks are identical")
    elif scenario == "S6":
        low_large = max(eligible, key=lambda item: (_area(item), item["obstacle_id"]))
        _assert(0.0 < low_large["combined_risk"] < 0.10, "S6: large distractor is not low risk")
        _assert(_area(low_large) >= 3.0 * _area(risk_max), "S6: distractor is not sufficiently larger")
        _assert(risk_max["combined_risk"] >= 0.20, "S6: small conflict is not high risk")
        _assert(low_large["combined_written_pixel_count"] > 0 and risk_max["combined_written_pixel_count"] > 0, "S6: objects do not both contribute pixels")
        _assert(bool(_polygon_tile_ids(low_large) & _polygon_tile_ids(risk_max)), "S6: no tile receives pixels from both polygons")
    elif scenario == "S7":
        partial = next(record for record in records if record["expected_visibility_role"] == "partially_visible")
        _assert(partial["visibility_status"] == "partially_visible" and partial["combined_risk"] > 0, "S7: partial obstacle invalid")
        _assert(partial["combined_written_pixel_count"] > 0 and partial["truncation_fraction"] > 0.0, "S7: partial object is not safely clipped")
        projected = partial["projected_polygon"]
        _assert(any(point[0] < 0.0 or point[0] > EXPECTED_CAMERA_WIDTH_PX - 1 or point[1] < 0.0 or point[1] > EXPECTED_CAMERA_HEIGHT_PX - 1 for point in projected), "S7: unclipped polygon does not cross an image boundary")
    elif scenario == "S8":
        for item in metadata_by_snapshot:
            item_eligible = [record for record in item["obstacles"] if _eligible(record)]
            _assert(item_eligible, "S8: every snapshot needs an eligible visible obstacle")
            _assert(all(0.0 < record["combined_risk"] < 0.10 for record in item_eligible), "S8: risk must remain below threshold at every snapshot")
    else:
        raise ValueError(f"unknown scenario {scenario}")
    if scenario in {"S1", "S2", "S5", "S6", "S7"}:
        peak = max(float(record["planned_risk"]) for record in snapshot["obstacles"] if _eligible(record))
        earlier = [
            max(float(record["planned_risk"]) for record in item["obstacles"] if _eligible(record))
            for item in metadata_by_snapshot[:2]
        ]
        _assert(peak + 1e-12 >= max(earlier), f"{scenario}: planned risk peak occurs before snapshot 2")


def validate_episode(summary_file: Path) -> dict[str, Any]:
    summary = load_json(summary_file)
    _assert(summary["status"] == "captured", "episode controller did not complete capture")
    expected = generate_scenario(summary["scenario_id"], summary["split"], int(summary["seed"]))
    _assert(config_hash(expected) == summary["config_hash"], "config hash is not reproducible")
    _assert(len(summary["snapshots"]) == 4, "episode does not contain four snapshots")
    metadata = [_validate_snapshot(summary, item) for item in summary["snapshots"]]
    _validate_scenario_rules(summary, metadata)
    return summary


def _summary_files(output_root: Path, split: str) -> list[Path]:
    return sorted((output_root / "metadata" / "m5e" / split).glob("*/*/episode_summary.json"))


def _validate_split_identity(summaries: list[dict[str, Any]], split: str) -> None:
    _assert(all(item["split"] == split for item in summaries), "episode split mismatch")
    expected_per_scenario = len(primary_seed_indices(split))
    expected = {
        (scenario_id, primary_seed(split, int(scenario_id[1:]), seed_index))
        for scenario_id in (f"S{index}" for index in range(1, 9))
        for seed_index in primary_seed_indices(split)
    }
    observed = {(item["scenario_id"], int(item["original_seed"])) for item in summaries}
    _assert(observed == expected, "accepted episodes do not match frozen primary seed set")
    _assert(all(int(item["replacement_index"]) >= 0 for item in summaries), "replacement index is invalid")
    _assert(len(summaries) == 8 * expected_per_scenario, "complete dataset episode count mismatch")


def validate_dataset(output_root: Path, split: str = "smoke", require_manifest: bool = True, require_complete: bool = True) -> list[dict[str, Any]]:
    summary_files = _summary_files(output_root, split)
    raw_summaries = [load_json(path) for path in summary_files]
    summaries = [validate_episode(path) for path, raw in zip(summary_files, raw_summaries) if raw.get("status") == "captured"]
    _assert(summaries, "no episode summaries found")
    if require_complete:
        _validate_split_identity(summaries, split)
        _assert({item["scenario_id"] for item in summaries} == {f"S{index}" for index in range(1, 9)}, "complete smoke dataset scenario set mismatch")
        _assert(sum(item["completed_snapshot_count"] for item in summaries) == len(summaries) * 4, "complete dataset snapshot count mismatch")
    if require_manifest:
        rows = read_manifest(output_root)
        _assert(len(rows) == len(summaries) * 4, "manifest row count mismatch")
        _assert(tuple(rows[0].keys()) == MANIFEST_FIELDS, "manifest schema mismatch")
        identities = {(row["scenario_id"], row["episode_id"], row["snapshot_index"]) for row in rows}
        _assert(len(identities) == len(rows), "manifest contains duplicate snapshots")
        _assert(all(row["scenario_validation_passed"] == "true" for row in rows), "manifest contains failed scenario")
        expected_calibration = str(split == "calibration").lower()
        expected_formal = str(split == "formal").lower()
        _assert(all(row["valid_for_calibration"] == expected_calibration and row["valid_for_formal"] == expected_formal for row in rows), "manifest split eligibility flags are incorrect")
        episode_manifest = load_json(episode_manifest_path(output_root))
        _assert(episode_manifest["split"] == split, "episode manifest split mismatch")
        _assert(episode_manifest["episode_count"] >= len(summaries), "episode manifest omits accepted episodes")
        accepted_ids = {item["episode_id"] for item in summaries}
        recorded_ids = {item["episode_id"] for item in episode_manifest["episodes"] if item["status"] == "captured"}
        _assert(accepted_ids <= recorded_ids, "episode manifest is missing an accepted episode")
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data")
    parser.add_argument("--split", default="smoke", choices=("smoke", "calibration", "formal"))
    parser.add_argument("--skip-manifest", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    output_root = resolve_output_root(args.output_root)
    try:
        summaries = validate_dataset(output_root, args.split, require_manifest=not args.skip_manifest, require_complete=not args.allow_partial)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"M5E dataset validation failed: {error}")
        return 1
    print(f"M5E dataset validation passed: episodes={len(summaries)} snapshots={len(summaries) * 4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
