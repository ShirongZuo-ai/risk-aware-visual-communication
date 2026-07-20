"""Pure-Python calibration helpers for frozen M5E common byte budgets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.budget_matcher import choose_best_under_budget, enumerate_uniform_quality_candidates
from compression.spatial_allocation import (
    DEFAULT_ALLOCATION_SEARCH_SPACE,
    SpatialAllocationConfig,
    build_tile_cache,
    iter_spatial_allocation_candidates,
    match_spatial_allocations_to_budgets,
)
from compression.tile_container import MAGIC, VERSION
from compression.tile_scoring import (
    METHOD_CENTER,
    METHOD_OBJECT,
    METHOD_RISK,
    METHOD_UNIFORM,
    FloatMask,
    ProjectedPolygon,
    center_roi_scores,
    object_roi_scores,
    risk_roi_scores,
)
from compression.tiled_jpeg import DEFAULT_M5_GRID
from scripts.m4d_image_risk_common import decode_masks_json
from scripts.m5e_dataset_common import load_json, read_manifest, resolve_output_root


CALIBRATION_PROTOCOL_VERSION = "m5e-c-common-budget-v1"
METHOD_ORDER = (METHOD_UNIFORM, METHOD_CENTER, METHOD_OBJECT, METHOD_RISK)
BUDGET_PERCENTAGES = (("severe", 0.05), ("low", 0.25), ("medium", 0.50), ("high", 0.80))


@dataclass(frozen=True)
class CandidateEndpoint:
    actual_total_bytes: int
    allocation: dict[str, int]


@dataclass(frozen=True)
class FeasibleRange:
    frame_id: str
    scenario_id: str
    episode_id: str
    snapshot_index: int
    method: str
    minimum: CandidateEndpoint
    maximum: CandidateEndpoint
    candidate_count: int
    source_frame_sha256: str
    mask_sha256: str
    config_hash: str


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def calibration_paths(output_root: Path) -> dict[str, Path]:
    root = output_root / "calibration"
    return {
        "root": root,
        "ranges": root / "feasible_ranges.json",
        "ranges_csv": root / "feasible_ranges.csv",
        "budget_manifest": root / "frozen_budget_manifest.json",
        "allocations": root / "matched_allocations.json",
        "allocation_csv": root / "matched_allocations.csv",
    }


def frame_id(row: dict[str, str]) -> str:
    return f"{row['episode_id']}_snapshot{int(row['snapshot_index']):02d}"


def calibration_rows(output_root: Path) -> list[dict[str, str]]:
    rows = read_manifest(output_root)
    selected = [row for row in rows if row["split"] == "calibration"]
    if len(selected) != 64:
        raise ValueError("calibration manifest must contain exactly 64 rows")
    if any(row["valid_for_calibration"] != "true" or row["valid_for_formal"] != "false" for row in selected):
        raise ValueError("calibration manifest split eligibility flags are invalid")
    return selected


def score_maps_for_row(row: dict[str, str]) -> tuple[Image.Image, dict[str, Any], dict[str, Any]]:
    metadata = load_json(PROJECT_ROOT / row["metadata_path"])
    masks = load_json(PROJECT_ROOT / row["mask_path"])
    with Image.open(PROJECT_ROOT / row["frame_path"]) as opened:
        image = opened.convert("RGB")
    decoded = decode_masks_json(masks["masks"])
    combined = FloatMask(
        decoded.combined.width_px,
        decoded.combined.height_px,
        decoded.combined.values,
        "row-major",
    )
    polygons = tuple(
        ProjectedPolygon(
            item["obstacle_id"],
            item["visibility_status"],
            tuple((float(point[0]), float(point[1])) for point in item["clipped_polygon"]),
        )
        for item in metadata["obstacles"]
    )
    return image, metadata, {
        METHOD_CENTER: center_roi_scores((metadata["camera"]["cx_px"], metadata["camera"]["cy_px"])),
        METHOD_OBJECT: object_roi_scores(polygons),
        METHOD_RISK: risk_roi_scores(combined),
    }


def _endpoint(total: int, allocation: dict[str, int]) -> CandidateEndpoint:
    return CandidateEndpoint(int(total), allocation)


def _range_for_uniform(image: Image.Image) -> tuple[CandidateEndpoint, CandidateEndpoint, int]:
    candidates = enumerate_uniform_quality_candidates(image)
    minimum, _ = min(candidates, key=lambda pair: (pair[0].actual_total_bytes, pair[0].quality))
    maximum, _ = max(candidates, key=lambda pair: (pair[0].actual_total_bytes, pair[0].quality))
    return (
        _endpoint(minimum.actual_total_bytes, {"quality": minimum.quality}),
        _endpoint(maximum.actual_total_bytes, {"quality": maximum.quality}),
        len(candidates),
    )


def _config_json(config: SpatialAllocationConfig) -> dict[str, int]:
    return {
        "background_quality": config.background_quality,
        "enhancement_quality": config.enhancement_quality,
        "top_k": config.top_k,
    }


def _config_key(config: SpatialAllocationConfig) -> tuple[int, int, int]:
    return (config.background_quality, config.enhancement_quality, config.top_k)


def _range_for_spatial(score_map, cache) -> tuple[CandidateEndpoint, CandidateEndpoint, int]:
    minimum: tuple[int, SpatialAllocationConfig] | None = None
    maximum: tuple[int, SpatialAllocationConfig] | None = None
    count = 0
    for total, config in iter_spatial_allocation_candidates(score_map, cache, DEFAULT_ALLOCATION_SEARCH_SPACE):
        count += 1
        candidate = (total, config)
        if minimum is None or (total, _config_key(config)) < (minimum[0], _config_key(minimum[1])):
            minimum = candidate
        if maximum is None or (total, _config_key(config)) > (maximum[0], _config_key(maximum[1])):
            maximum = candidate
    if minimum is None or maximum is None:
        raise ValueError("frozen spatial allocation candidate space is empty")
    return _endpoint(minimum[0], _config_json(minimum[1])), _endpoint(maximum[0], _config_json(maximum[1])), count


def calculate_feasible_ranges(rows: Iterable[dict[str, str]]) -> list[FeasibleRange]:
    ranges: list[FeasibleRange] = []
    for row in rows:
        image, metadata, score_maps = score_maps_for_row(row)
        if image.size != (DEFAULT_M5_GRID.frame_width_px, DEFAULT_M5_GRID.frame_height_px):
            raise ValueError("calibration source frame dimensions do not match frozen grid")
        cache = build_tile_cache(image)
        for method in METHOD_ORDER:
            if method == METHOD_UNIFORM:
                minimum, maximum, count = _range_for_uniform(image)
            else:
                minimum, maximum, count = _range_for_spatial(score_maps[method], cache)
            ranges.append(
                FeasibleRange(
                    frame_id=frame_id(row),
                    scenario_id=row["scenario_id"],
                    episode_id=row["episode_id"],
                    snapshot_index=int(row["snapshot_index"]),
                    method=method,
                    minimum=minimum,
                    maximum=maximum,
                    candidate_count=count,
                    source_frame_sha256=row["frame_sha256"],
                    mask_sha256=row["mask_sha256"],
                    config_hash=metadata["config_hash"],
                )
            )
    if len(ranges) != 64 * len(METHOD_ORDER):
        raise ValueError("feasible range matrix is incomplete")
    return sorted(ranges, key=lambda item: (item.scenario_id, item.episode_id, item.snapshot_index, METHOD_ORDER.index(item.method)))


def range_json(item: FeasibleRange) -> dict[str, Any]:
    return {
        "frame_id": item.frame_id,
        "scenario_id": item.scenario_id,
        "episode_id": item.episode_id,
        "snapshot_index": item.snapshot_index,
        "method": item.method,
        "minimum_actual_bytes": item.minimum.actual_total_bytes,
        "maximum_actual_bytes": item.maximum.actual_total_bytes,
        "minimum_allocation": item.minimum.allocation,
        "maximum_allocation": item.maximum.allocation,
        "candidate_count": item.candidate_count,
        "source_frame_sha256": item.source_frame_sha256,
        "mask_sha256": item.mask_sha256,
        "config_hash": item.config_hash,
        "codec_version": "tiled-jpeg-pillow-12.3.0",
        "container_version": f"{MAGIC.decode('ascii')}-v{VERSION}",
    }


def common_interval(ranges: Iterable[FeasibleRange]) -> tuple[int, int, FeasibleRange, FeasibleRange]:
    values = tuple(ranges)
    lower_witness = max(values, key=lambda item: (item.minimum.actual_total_bytes, item.frame_id, item.method))
    upper_witness = min(values, key=lambda item: (item.maximum.actual_total_bytes, item.frame_id, item.method))
    lower = lower_witness.minimum.actual_total_bytes
    upper = upper_witness.maximum.actual_total_bytes
    if lower >= upper:
        raise ValueError(f"common feasible interval is empty: [{lower}, {upper}]")
    return lower, upper, lower_witness, upper_witness


def frozen_budgets(lower: int, upper: int) -> dict[str, int]:
    if lower >= upper:
        raise ValueError("common interval must be nonempty")
    span = upper - lower
    values = {label: lower + math.floor(fraction * span) for label, fraction in BUDGET_PERCENTAGES}
    if list(values.values()) != sorted(values.values()) or len(set(values.values())) != 4:
        raise ValueError("frozen budgets are not strictly increasing")
    if any(value < lower or value > upper for value in values.values()):
        raise ValueError("frozen budget lies outside common interval")
    return values


def match_all_budgets(rows: Iterable[dict[str, str]], budgets: dict[str, int]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    targets = tuple(budgets.values())
    labels = tuple(budgets)
    for row in rows:
        image, metadata, score_maps = score_maps_for_row(row)
        cache = build_tile_cache(image)
        uniform_candidates = enumerate_uniform_quality_candidates(image)
        matches: dict[str, list[Any]] = {METHOD_UNIFORM: []}
        for target in targets:
            candidate, encoded = choose_best_under_budget(uniform_candidates, target)
            matches[METHOD_UNIFORM].append((candidate, encoded))
        for method in (METHOD_CENTER, METHOD_OBJECT, METHOD_RISK):
            matches[method] = list(match_spatial_allocations_to_budgets(score_maps[method], cache, targets))
        for method in METHOD_ORDER:
            for label, target, match in zip(labels, targets, matches[method]):
                if method == METHOD_UNIFORM:
                    candidate, encoded = match
                    actual = candidate.actual_total_bytes
                    allocation = {"quality": candidate.quality}
                    qualities = list(encoded.qualities)
                    candidate_count = len(uniform_candidates)
                    tie_break = "max_actual_bytes, higher_uniform_quality"
                else:
                    actual = match.actual_total_bytes
                    allocation = _config_json(match.selected_config)
                    qualities = list(match.qualities)
                    candidate_count = match.candidate_count
                    tie_break = match.deterministic_tie_break
                if actual > target:
                    raise AssertionError("matched allocation exceeds frozen target")
                records.append({
                    "frame_id": frame_id(row), "scenario_id": row["scenario_id"], "episode_id": row["episode_id"],
                    "snapshot_index": int(row["snapshot_index"]), "method": method, "budget_id": label,
                    "target_bytes": target, "actual_total_bytes": actual, "unused_bytes": target - actual,
                    "utilization": actual / target, "selected_allocation": allocation, "tile_qualities": qualities,
                    "candidate_count": candidate_count, "deterministic_tie_break": tie_break,
                    "source_frame_sha256": row["frame_sha256"], "mask_sha256": row["mask_sha256"],
                    "config_hash": metadata["config_hash"], "actual_future_trajectory_used": False,
                })
    if len(records) != 64 * len(METHOD_ORDER) * len(budgets):
        raise ValueError("matched allocation matrix is incomplete")
    return sorted(records, key=lambda item: (item["scenario_id"], item["episode_id"], item["snapshot_index"], METHOD_ORDER.index(item["method"]), list(budgets).index(item["budget_id"])))


def records_hash(records: Any) -> str:
    return sha256_json(records)


def output_root_from_argument(value: str) -> Path:
    return resolve_output_root(value)
