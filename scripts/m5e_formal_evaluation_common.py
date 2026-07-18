"""Shared helpers for M5E-D multi-scene formal offline quality evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.budget_matcher import choose_best_under_budget, enumerate_uniform_quality_candidates
from compression.spatial_allocation import SpatialBudgetMatch, build_tile_cache, match_spatial_allocations_to_budgets
from compression.tile_container import MAGIC, VERSION, deserialize_tiled_frame
from compression.tile_scoring import FloatMask, METHOD_CENTER, METHOD_OBJECT, METHOD_RISK, METHOD_UNIFORM, ProjectedPolygon
from compression.tiled_jpeg import DEFAULT_M5_GRID, decode_tiles_to_rgb
from evaluation.image_quality import UndefinedMetricError, compute_error_metrics, compute_masked_error_metrics, compute_risk_weighted_metrics, compute_ssim
from evaluation.region_masks import HIGH_RISK_THRESHOLD, build_evaluation_regions
from evaluation.matched_budget_evaluation import tile_allocation_diagnostics
from scripts.m4d_image_risk_common import decode_masks_json
from scripts.m5c_allocation_common import grid_json, jpeg_parameters_json, pillow_version
from scripts.m5d_evaluation_common import dependency_versions, json_cell, metric_cell
from scripts.m5e_calibration_common import METHOD_ORDER, calibration_paths, frame_id, score_maps_for_row, sha256_json
from scripts.m5e_dataset_common import load_json, read_manifest, relative_to_project, resolve_output_root, sha256_file
from simulator.m5e_config import SCENARIO_IDS, primary_seed, primary_seed_indices


FORMAL_PROTOCOL_VERSION = "m5e-d-formal-quality-v1"
EXPECTED_COMMON_INTERVAL = {"L_common": 31240, "U_common": 35779}
EXPECTED_FROZEN_BUDGETS = {"severe": 31466, "low": 32374, "medium": 33509, "high": 34871}
EXPECTED_FORMAL_EPISODES = 64
EXPECTED_FORMAL_FRAMES = 256
EXPECTED_FORMAL_RECONSTRUCTIONS = EXPECTED_FORMAL_FRAMES * len(METHOD_ORDER) * len(EXPECTED_FROZEN_BUDGETS)
FORMAL_BUDGET_LABELS = tuple(EXPECTED_FROZEN_BUDGETS)

ALLOCATION_FIELDS = [
    "frame_id", "scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index", "snapshot_index",
    "method", "budget_label", "target_bytes", "actual_total_bytes", "unused_bytes", "utilization",
    "selected_allocation_json", "tile_qualities_json", "tile_payload_bytes_json", "candidate_count",
    "feasible_candidate_count", "deterministic_tie_break", "allocation_identity_sha256",
    "source_frame_sha256", "mask_sha256", "combined_mask_sha256", "config_hash", "metadata_normalized_sha256",
    "actual_future_trajectory_used",
]

METRIC_FIELDS = [
    "frame_id", "scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index", "snapshot_index",
    "method", "budget_label", "target_bytes", "actual_total_bytes", "unused_bytes", "utilization",
    "allocation_identity_sha256", "container_sha256", "reconstruction_sha256", "container_path", "decoded_png_path",
    "source_frame_sha256", "mask_sha256", "combined_mask_sha256", "config_hash", "metadata_normalized_sha256",
    "q_background", "q_enhancement", "top_k", "min_quality", "max_quality", "unique_quality_count", "enhanced_tile_count",
    "full_mse", "full_psnr_db", "full_ssim", "risk_sum", "risk_weighted_mse", "risk_weighted_psnr_db",
    "object_pixel_count", "object_fraction", "object_mse", "object_psnr_db",
    "risk_support_pixel_count", "risk_support_fraction", "risk_support_mse", "risk_support_psnr_db",
    "high_risk_pixel_count", "high_risk_fraction", "high_risk_mse", "high_risk_psnr_db",
    "background_pixel_count", "background_fraction", "background_mse", "background_psnr_db",
    "risk_weighted_mean_quality", "high_risk_tile_count", "high_risk_tile_mean_quality", "high_risk_tile_min_quality",
    "high_risk_tile_max_quality", "high_risk_tile_payload_bytes", "zero_risk_tile_count", "zero_risk_tile_mean_quality",
    "zero_risk_tile_payload_bytes", "minimum_tile_payload_bytes", "maximum_tile_payload_bytes", "total_tile_payload_bytes",
    "container_overhead_bytes", "tile_qualities_json", "tile_payload_bytes_json", "pillow_version", "numpy_version",
    "scikit_image_version", "container_magic", "container_version", "actual_future_trajectory_used",
]


def formal_paths(output_root: Path) -> dict[str, Path]:
    root = output_root / "formal_evaluation"
    return {
        "root": root,
        "allocation_csv": root / "m5e_d_formal_allocations.csv",
        "allocation_json": root / "m5e_d_formal_allocations.json",
        "metrics_csv": root / "m5e_d_formal_quality_metrics.csv",
        "metrics_json": root / "m5e_d_formal_quality_metrics.json",
        "run_metadata": root / "m5e_d_formal_evaluation_metadata.json",
        "validation_summary": root / "m5e_d_formal_validation_summary.json",
        "containers": root / "containers",
        "decoded": root / "decoded",
    }


def expected_result_count(frame_count: int) -> int:
    return int(frame_count) * len(METHOD_ORDER) * len(EXPECTED_FROZEN_BUDGETS)


def load_frozen_budget_manifest(calibration_root: Path | str = Path("data/m5e_calibration")) -> dict[str, Any]:
    root = resolve_output_root(str(calibration_root)) if not isinstance(calibration_root, Path) else calibration_root
    if not root.is_absolute():
        root = resolve_output_root(str(root))
    manifest = load_json(calibration_paths(root)["budget_manifest"])
    validate_frozen_budget_manifest(manifest)
    return manifest


def validate_frozen_budget_manifest(manifest: dict[str, Any]) -> None:
    if int(manifest.get("L_common")) != EXPECTED_COMMON_INTERVAL["L_common"]:
        raise ValueError("unexpected L_common in frozen budget manifest")
    if int(manifest.get("U_common")) != EXPECTED_COMMON_INTERVAL["U_common"]:
        raise ValueError("unexpected U_common in frozen budget manifest")
    if "budgets" in manifest:
        budgets = {key: int(value) for key, value in manifest["budgets"].items()}
    else:
        budgets = {label: int(manifest.get(f"{label}_bytes")) for label in EXPECTED_FROZEN_BUDGETS}
    if budgets != EXPECTED_FROZEN_BUDGETS:
        raise ValueError("frozen budget values differ from M5E-C")
    if manifest.get("actual_future_trajectory_used") is not False:
        raise ValueError("frozen budget manifest must exclude actual future trajectory")


def formal_rows(output_root: Path, *, allow_subset: bool = False) -> list[dict[str, str]]:
    rows = [row for row in read_manifest(output_root) if row["split"] == "formal"]
    if not allow_subset and len(rows) != EXPECTED_FORMAL_FRAMES:
        raise ValueError(f"formal manifest must contain exactly {EXPECTED_FORMAL_FRAMES} rows")
    if not rows:
        raise ValueError("formal manifest is empty")
    keys = [frame_id(row) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("formal manifest contains duplicate frame IDs")
    for row in rows:
        if row["valid_for_formal"] != "true" or row["valid_for_calibration"] != "false":
            raise ValueError("formal split eligibility flags are invalid")
        if row["actual_future_trajectory_used"] != "false":
            raise ValueError("formal rows must not use actual future trajectory")
    return sorted(rows, key=lambda row: (row["scenario_id"], int(row["original_seed"]), int(row["snapshot_index"])))


def normalize_metadata_for_hash(metadata: dict[str, Any]) -> dict[str, Any]:
    ignored = {"frame_path", "csv_path", "masks_path"}

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if key not in ignored}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return normalize(metadata)


def metadata_normalized_sha256(metadata: dict[str, Any]) -> str:
    return sha256_json(normalize_metadata_for_hash(metadata))


def row_risk_and_regions(row: dict[str, str], metadata: dict[str, Any]) -> tuple[FloatMask, Any]:
    masks = load_json(PROJECT_ROOT / row["mask_path"])
    decoded = decode_masks_json(masks["masks"])
    combined = FloatMask(decoded.combined.width_px, decoded.combined.height_px, decoded.combined.values, "row-major")
    polygons = tuple(
        ProjectedPolygon(
            item["obstacle_id"],
            item["visibility_status"],
            tuple((float(point[0]), float(point[1])) for point in item["clipped_polygon"]),
        )
        for item in metadata["obstacles"]
    )
    return combined, build_evaluation_regions(combined, polygons)


def allocation_identity_sha256(method: str, budget_label: str, target_bytes: int, actual_total_bytes: int, allocation: dict[str, int], qualities: Iterable[int]) -> str:
    return sha256_json(
        {
            "method": method,
            "budget_label": budget_label,
            "target_bytes": target_bytes,
            "actual_total_bytes": actual_total_bytes,
            "selected_allocation": allocation,
            "tile_qualities": list(qualities),
        }
    )


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _config_json(config) -> dict[str, int]:
    return {
        "background_quality": int(config.background_quality),
        "enhancement_quality": int(config.enhancement_quality),
        "top_k": int(config.top_k),
    }


def _region_metric_cells(source: np.ndarray, decoded: np.ndarray, mask: Iterable[bool]) -> tuple[str, str]:
    try:
        metrics = compute_masked_error_metrics(source, decoded, mask)
    except UndefinedMetricError:
        return "undefined", "undefined"
    return metric_cell(metrics.mse), metric_cell(metrics.psnr_db)


def _quality_summary(method: str, allocation: dict[str, int], qualities: tuple[int, ...]) -> dict[str, str]:
    if method == METHOD_UNIFORM:
        q_background = allocation["quality"]
        q_enhancement = allocation["quality"]
        top_k = 0
    else:
        q_background = allocation["background_quality"]
        q_enhancement = allocation["enhancement_quality"]
        top_k = allocation["top_k"]
    return {
        "q_background": str(q_background),
        "q_enhancement": str(q_enhancement),
        "top_k": str(top_k),
        "min_quality": str(min(qualities)),
        "max_quality": str(max(qualities)),
        "unique_quality_count": str(len(set(qualities))),
        "enhanced_tile_count": str(sum(quality == q_enhancement for quality in qualities)) if method != METHOD_UNIFORM else "48",
    }


def _write_table(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _row_prefix(row: dict[str, str]) -> dict[str, str]:
    return {
        "frame_id": frame_id(row),
        "scenario_id": row["scenario_id"],
        "episode_id": row["episode_id"],
        "original_seed": row["original_seed"],
        "actual_seed": row["actual_seed"],
        "replacement_index": row["replacement_index"],
        "snapshot_index": row["snapshot_index"],
    }


def _decode_container(container_bytes: bytes, source_shape: tuple[int, ...]) -> np.ndarray:
    parsed = deserialize_tiled_frame(container_bytes)
    decoded_image = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
    decoded_rgb = np.asarray(decoded_image, dtype=np.uint8)
    if decoded_rgb.shape != source_shape:
        raise ValueError("decoded image shape differs from source")
    return decoded_rgb


def _artifact_path(root: Path, row: dict[str, str], method: str, budget_label: str, suffix: str) -> Path:
    return root / row["scenario_id"] / row["episode_id"] / f"snapshot{int(row['snapshot_index']):02d}_{method}_{budget_label}{suffix}"


def evaluate_formal_rows(
    rows: Iterable[dict[str, str]],
    budgets: dict[str, int],
    *,
    output_root: Path | None = None,
    write_artifacts: bool = True,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    allocation_rows: list[dict[str, str]] = []
    metric_rows: list[dict[str, str]] = []
    versions = dependency_versions()
    paths = formal_paths(output_root) if output_root is not None else None
    budget_items = tuple((label, int(budgets[label])) for label in FORMAL_BUDGET_LABELS)
    for row in rows:
        image, metadata, score_maps = score_maps_for_row(row)
        if image.size != (DEFAULT_M5_GRID.frame_width_px, DEFAULT_M5_GRID.frame_height_px):
            raise ValueError("formal source frame dimensions do not match frozen grid")
        source_rgb = np.asarray(image, dtype=np.uint8)
        combined, regions = row_risk_and_regions(row, metadata)
        cache = build_tile_cache(image)
        uniform_candidates = enumerate_uniform_quality_candidates(image)
        matches: dict[str, list[Any]] = {METHOD_UNIFORM: []}
        for _, target in budget_items:
            candidate, encoded = choose_best_under_budget(uniform_candidates, target)
            matches[METHOD_UNIFORM].append((candidate, encoded))
        for method in (METHOD_CENTER, METHOD_OBJECT, METHOD_RISK):
            matches[method] = list(match_spatial_allocations_to_budgets(score_maps[method], cache, (target for _, target in budget_items)))

        metadata_hash = metadata_normalized_sha256(metadata)
        for method in METHOD_ORDER:
            for budget_index, (budget_label, target) in enumerate(budget_items):
                match = matches[method][budget_index]
                if method == METHOD_UNIFORM:
                    candidate, encoded = match
                    actual = int(candidate.actual_total_bytes)
                    allocation = {"quality": int(candidate.quality)}
                    qualities = tuple(int(value) for value in encoded.qualities)
                    tile_payload_bytes = tuple(int(value) for value in encoded.tile_payload_bytes)
                    container_bytes = encoded.container_bytes
                    candidate_count = len(uniform_candidates)
                    feasible_candidate_count = sum(1 for candidate_item, _ in uniform_candidates if candidate_item.actual_total_bytes <= target)
                    tie_break = "max_actual_bytes, higher_uniform_quality"
                    overhead = encoded.container_overhead_bytes
                else:
                    spatial: SpatialBudgetMatch = match
                    actual = int(spatial.actual_total_bytes)
                    allocation = _config_json(spatial.selected_config)
                    qualities = tuple(int(value) for value in spatial.qualities)
                    tile_payload_bytes = tuple(int(value) for value in spatial.tile_payload_bytes)
                    container_bytes = spatial.container_bytes
                    candidate_count = int(spatial.candidate_count)
                    feasible_candidate_count = int(spatial.feasible_candidate_count)
                    tie_break = spatial.deterministic_tie_break
                    overhead = spatial.container_overhead_bytes
                if actual > target:
                    raise AssertionError("matched allocation exceeds frozen target")

                decoded_rgb = _decode_container(container_bytes, source_rgb.shape)
                allocation_hash = allocation_identity_sha256(method, budget_label, target, actual, allocation, qualities)
                container_hash = _hash_bytes(container_bytes)
                reconstruction_hash = _hash_bytes(decoded_rgb.tobytes())
                container_path = ""
                decoded_path = ""
                if write_artifacts:
                    if paths is None:
                        raise ValueError("output_root is required when write_artifacts is true")
                    container_file = _artifact_path(paths["containers"], row, method, budget_label, ".ravcjt")
                    decoded_file = _artifact_path(paths["decoded"], row, method, budget_label, ".png")
                    container_file.parent.mkdir(parents=True, exist_ok=True)
                    decoded_file.parent.mkdir(parents=True, exist_ok=True)
                    container_file.write_bytes(container_bytes)
                    Image.fromarray(decoded_rgb, mode="RGB").save(decoded_file)
                    container_path = relative_to_project(container_file)
                    decoded_path = relative_to_project(decoded_file)

                full = compute_error_metrics(source_rgb, decoded_rgb)
                risk_weighted, risk_sum = compute_risk_weighted_metrics(source_rgb, decoded_rgb, combined.values)
                diagnostics = tile_allocation_diagnostics(qualities, tile_payload_bytes, combined.values)
                object_mse, object_psnr = _region_metric_cells(source_rgb, decoded_rgb, regions.eligible_object_union.values)
                support_mse, support_psnr = _region_metric_cells(source_rgb, decoded_rgb, regions.risk_support.values)
                high_mse, high_psnr = _region_metric_cells(source_rgb, decoded_rgb, regions.high_risk.values)
                background_mse, background_psnr = _region_metric_cells(source_rgb, decoded_rgb, regions.background.values)
                prefix = _row_prefix(row)
                allocation_row = {
                    **prefix,
                    "method": method,
                    "budget_label": budget_label,
                    "target_bytes": str(target),
                    "actual_total_bytes": str(actual),
                    "unused_bytes": str(target - actual),
                    "utilization": repr(actual / target),
                    "selected_allocation_json": json_cell(allocation),
                    "tile_qualities_json": json_cell(list(qualities)),
                    "tile_payload_bytes_json": json_cell(list(tile_payload_bytes)),
                    "candidate_count": str(candidate_count),
                    "feasible_candidate_count": str(feasible_candidate_count),
                    "deterministic_tie_break": tie_break,
                    "allocation_identity_sha256": allocation_hash,
                    "source_frame_sha256": row["frame_sha256"],
                    "mask_sha256": row["mask_sha256"],
                    "combined_mask_sha256": row["combined_mask_sha256"],
                    "config_hash": metadata["config_hash"],
                    "metadata_normalized_sha256": metadata_hash,
                    "actual_future_trajectory_used": "false",
                }
                quality_summary = _quality_summary(method, allocation, qualities)
                metric_rows.append(
                    {
                        **prefix,
                        "method": method,
                        "budget_label": budget_label,
                        "target_bytes": str(target),
                        "actual_total_bytes": str(actual),
                        "unused_bytes": str(target - actual),
                        "utilization": repr(actual / target),
                        "allocation_identity_sha256": allocation_hash,
                        "container_sha256": container_hash,
                        "reconstruction_sha256": reconstruction_hash,
                        "container_path": container_path,
                        "decoded_png_path": decoded_path,
                        "source_frame_sha256": row["frame_sha256"],
                        "mask_sha256": row["mask_sha256"],
                        "combined_mask_sha256": row["combined_mask_sha256"],
                        "config_hash": metadata["config_hash"],
                        "metadata_normalized_sha256": metadata_hash,
                        **quality_summary,
                        "full_mse": metric_cell(full.mse),
                        "full_psnr_db": metric_cell(full.psnr_db),
                        "full_ssim": metric_cell(compute_ssim(source_rgb, decoded_rgb)),
                        "risk_sum": metric_cell(risk_sum),
                        "risk_weighted_mse": metric_cell(risk_weighted.mse),
                        "risk_weighted_psnr_db": metric_cell(risk_weighted.psnr_db),
                        "object_pixel_count": str(regions.eligible_object_union.pixel_count),
                        "object_fraction": repr(regions.eligible_object_union.fraction),
                        "object_mse": object_mse,
                        "object_psnr_db": object_psnr,
                        "risk_support_pixel_count": str(regions.risk_support.pixel_count),
                        "risk_support_fraction": repr(regions.risk_support.fraction),
                        "risk_support_mse": support_mse,
                        "risk_support_psnr_db": support_psnr,
                        "high_risk_pixel_count": str(regions.high_risk.pixel_count),
                        "high_risk_fraction": repr(regions.high_risk.fraction),
                        "high_risk_mse": high_mse,
                        "high_risk_psnr_db": high_psnr,
                        "background_pixel_count": str(regions.background.pixel_count),
                        "background_fraction": repr(regions.background.fraction),
                        "background_mse": background_mse,
                        "background_psnr_db": background_psnr,
                        "risk_weighted_mean_quality": metric_cell(diagnostics.risk_weighted_mean_quality),
                        "high_risk_tile_count": str(diagnostics.high_risk_tile_count),
                        "high_risk_tile_mean_quality": metric_cell(diagnostics.high_risk_tile_mean_quality),
                        "high_risk_tile_min_quality": metric_cell(diagnostics.high_risk_tile_minimum_quality),
                        "high_risk_tile_max_quality": metric_cell(diagnostics.high_risk_tile_maximum_quality),
                        "high_risk_tile_payload_bytes": str(diagnostics.high_risk_tile_payload_bytes),
                        "zero_risk_tile_count": str(diagnostics.zero_risk_tile_count),
                        "zero_risk_tile_mean_quality": metric_cell(diagnostics.zero_risk_tile_mean_quality),
                        "zero_risk_tile_payload_bytes": str(diagnostics.zero_risk_tile_payload_bytes),
                        "minimum_tile_payload_bytes": str(min(tile_payload_bytes)),
                        "maximum_tile_payload_bytes": str(max(tile_payload_bytes)),
                        "total_tile_payload_bytes": str(sum(tile_payload_bytes)),
                        "container_overhead_bytes": str(overhead),
                        "tile_qualities_json": json_cell(list(qualities)),
                        "tile_payload_bytes_json": json_cell(list(tile_payload_bytes)),
                        "pillow_version": versions["pillow"],
                        "numpy_version": versions["numpy"],
                        "scikit_image_version": versions["scikit_image"],
                        "container_magic": MAGIC.decode("ascii"),
                        "container_version": str(VERSION),
                        "actual_future_trajectory_used": "false",
                    }
                )
                allocation_rows.append(allocation_row)
    sort_key = lambda item: (item["scenario_id"], int(item["original_seed"]), int(item["snapshot_index"]), METHOD_ORDER.index(item["method"]), FORMAL_BUDGET_LABELS.index(item["budget_label"]))
    return sorted(allocation_rows, key=sort_key), sorted(metric_rows, key=sort_key)


def write_formal_evaluation(
    output_root: Path,
    calibration_root: Path,
    *,
    allow_subset: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    paths = formal_paths(output_root)
    if paths["metrics_csv"].exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing formal evaluation: {paths['metrics_csv']}")
    manifest = load_frozen_budget_manifest(calibration_root)
    rows = formal_rows(output_root, allow_subset=allow_subset)
    allocations, metrics = evaluate_formal_rows(rows, EXPECTED_FROZEN_BUDGETS, output_root=output_root, write_artifacts=True)
    _write_table(paths["allocation_csv"], ALLOCATION_FIELDS, allocations)
    _write_table(paths["metrics_csv"], METRIC_FIELDS, metrics)
    paths["allocation_json"].write_text(json.dumps(allocations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["metrics_json"].write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    over_budget = sum(1 for row in metrics if int(row["actual_total_bytes"]) > int(row["target_bytes"]))
    metadata = {
        "milestone": "5E-D",
        "protocol_version": FORMAL_PROTOCOL_VERSION,
        "evaluation_type": "multi_scene_formal_offline_quality_evaluation",
        "development_only": False,
        "formal_statistics_deferred_to": "M5E-E",
        "formal_dataset_root": relative_to_project(output_root),
        "calibration_budget_manifest": relative_to_project(calibration_paths(calibration_root)["budget_manifest"]),
        "frozen_common_interval": EXPECTED_COMMON_INTERVAL,
        "frozen_budgets": EXPECTED_FROZEN_BUDGETS,
        "scenario_count": len({row["scenario_id"] for row in rows}),
        "episode_count": len({row["episode_id"] for row in rows}),
        "frame_count": len(rows),
        "method_count": len(METHOD_ORDER),
        "budget_count": len(EXPECTED_FROZEN_BUDGETS),
        "reconstruction_count": len(metrics),
        "expected_reconstruction_count": expected_result_count(len(rows)),
        "over_budget_count": over_budget,
        "methods": list(METHOD_ORDER),
        "budget_labels": list(FORMAL_BUDGET_LABELS),
        "grid": grid_json(),
        "jpeg_parameters": jpeg_parameters_json(),
        "container": {"magic": MAGIC.decode("ascii"), "version": VERSION},
        "dependencies": dependency_versions(),
        "high_risk_threshold": HIGH_RISK_THRESHOLD,
        "actual_future_trajectory_used": False,
        "not_claimed": ["navigation benefit", "closed-loop safety", "statistical significance", "general superiority"],
        "frozen_budget_manifest_sha256": sha256_file(calibration_paths(calibration_root)["budget_manifest"]),
        "source_frame_count_by_scenario": {scenario_id: sum(1 for row in rows if row["scenario_id"] == scenario_id) for scenario_id in SCENARIO_IDS},
        "subset": allow_subset and len(rows) != EXPECTED_FORMAL_FRAMES,
    }
    paths["run_metadata"].write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def ensure_formal_seed_schedule(rows: Iterable[dict[str, str]], *, allow_subset: bool = False) -> None:
    values = list(rows)
    expected = {
        (scenario_id, str(primary_seed("formal", scenario_index, seed_index)))
        for scenario_index, scenario_id in enumerate(SCENARIO_IDS, start=1)
        for seed_index in primary_seed_indices("formal")
    }
    seen = {(row["scenario_id"], row["original_seed"]) for row in values}
    if allow_subset:
        if not seen.issubset(expected):
            raise ValueError("formal rows contain seeds outside the formal schedule")
    elif seen != expected:
        raise ValueError("formal rows do not match the 64-episode formal seed schedule")
    calibration = {
        primary_seed("calibration", scenario_index, seed_index)
        for scenario_index in range(1, 9)
        for seed_index in primary_seed_indices("calibration")
    }
    formal = {int(seed) for _, seed in seen}
    if formal & calibration or any(seed < 200000 for seed in formal):
        raise ValueError("formal rows overlap calibration/smoke seed ranges")


def compare_rows_exact(left: list[dict[str, str]], right: list[dict[str, str]], fields: list[str]) -> list[str]:
    errors: list[str] = []
    if len(left) != len(right):
        return [f"row count differs: {len(left)} != {len(right)}"]
    for index, (actual, expected) in enumerate(zip(left, right)):
        for field in fields:
            if actual.get(field) != expected.get(field):
                errors.append(f"row {index} field {field}: {actual.get(field)!r} != {expected.get(field)!r}")
                if len(errors) >= 20:
                    return errors
    return errors
