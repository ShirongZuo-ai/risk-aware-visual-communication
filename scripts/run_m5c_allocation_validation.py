"""Generate the Milestone 5C allocation-only validation matrix."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.budget_matcher import match_uniform_quality_to_budget  # noqa: E402
from compression.spatial_allocation import (  # noqa: E402
    DEFAULT_ALLOCATION_SEARCH_SPACE,
    SpatialBudgetMatch,
    build_tile_cache,
    match_spatial_allocations_to_budgets,
)
from compression.tile_container import MAGIC, VERSION, deserialize_tiled_frame  # noqa: E402
from compression.tile_scoring import center_roi_scores, object_roi_scores, risk_roi_scores, uniform_score_map  # noqa: E402
from compression.tiled_jpeg import DEFAULT_M5_GRID, decode_tiles_to_rgb  # noqa: E402
from scripts.m5c_allocation_common import (  # noqa: E402
    CSV_FIELDS,
    DEVELOPMENT_BUDGETS,
    M5C_CONTAINER_DIR,
    load_m4d_evidence,
    grid_json,
    jpeg_parameters_json,
    json_cell,
    pillow_version,
    sha256_file,
    write_csv,
    write_metadata,
)


def _uniform_row(image: Image.Image, budget_id: str, target_bytes: int, frame_hash: str) -> tuple[dict[str, str], bytes, Image.Image]:
    match = match_uniform_quality_to_budget(image, target_bytes, DEFAULT_M5_GRID)
    parsed = deserialize_tiled_frame(match.encoded_frame.container_bytes)
    decoded = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
    row = _base_row("uniform", budget_id, target_bytes, frame_hash)
    row.update(
        {
            "actual_total_bytes": str(match.actual_total_bytes),
            "unused_bytes": str(match.unused_bytes),
            "utilization": repr(match.utilization),
            "selected_allocation_json": json_cell({"background_quality": match.quality, "enhancement_quality": match.quality, "top_k": 0, "matcher": "m5b_uniform"}),
            "tile_scores_json": json_cell(list(uniform_score_map().scores)),
            "tile_qualities_json": json_cell(list(match.encoded_frame.qualities)),
            "tile_jpeg_bytes_json": json_cell(list(match.tile_payload_bytes)),
            "container_overhead_bytes": str(match.container_overhead_bytes),
            "unique_quality_count": "1",
            "minimum_quality": str(match.quality),
            "maximum_quality": str(match.quality),
            "enhanced_tile_count": "0",
            "candidate_count": str(len(match.candidates)),
            "feasible_candidate_count": str(sum(candidate.actual_total_bytes <= target_bytes for candidate in match.candidates)),
            "decode_width_px": str(decoded.width),
            "decode_height_px": str(decoded.height),
            "decode_mode": decoded.mode,
        }
    )
    return row, match.encoded_frame.container_bytes, decoded


def _spatial_row(match: SpatialBudgetMatch, budget_id: str, frame_hash: str) -> tuple[dict[str, str], bytes, Image.Image]:
    parsed = deserialize_tiled_frame(match.container_bytes)
    decoded = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
    row = _base_row(match.method, budget_id, match.target_bytes, frame_hash)
    row.update(
        {
            "actual_total_bytes": str(match.actual_total_bytes),
            "unused_bytes": str(match.unused_bytes),
            "utilization": repr(match.utilization),
            "selected_allocation_json": json_cell({
                "background_quality": match.selected_config.background_quality,
                "enhancement_quality": match.selected_config.enhancement_quality,
                "top_k": match.selected_config.top_k,
                "tie_break": match.deterministic_tie_break,
            }),
            "tile_scores_json": json_cell(list(match.score_map.scores)),
            "tile_qualities_json": json_cell(list(match.qualities)),
            "tile_jpeg_bytes_json": json_cell(list(match.tile_payload_bytes)),
            "container_overhead_bytes": str(match.container_overhead_bytes),
            "unique_quality_count": str(match.unique_quality_count),
            "minimum_quality": str(min(match.qualities)),
            "maximum_quality": str(max(match.qualities)),
            "enhanced_tile_count": str(sum(quality == match.selected_config.enhancement_quality for quality in match.qualities)),
            "candidate_count": str(match.candidate_count),
            "feasible_candidate_count": str(match.feasible_candidate_count),
            "decode_width_px": str(decoded.width),
            "decode_height_px": str(decoded.height),
            "decode_mode": decoded.mode,
        }
    )
    return row, match.container_bytes, decoded


def _base_row(method: str, budget_id: str, target_bytes: int, frame_hash: str) -> dict[str, str]:
    return {
        "frame_id": "image_risk_validation_episode_0001",
        "frame_hash": frame_hash,
        "method": method,
        "budget_id": budget_id,
        "target_bytes": str(target_bytes),
        "actual_total_bytes": "",
        "unused_bytes": "",
        "utilization": "",
        "grid_json": json_cell(grid_json()),
        "jpeg_parameters_json": json_cell(jpeg_parameters_json()),
        "pillow_version": pillow_version(),
        "container_magic": MAGIC.decode("ascii"),
        "container_version": str(VERSION),
        "selected_allocation_json": "",
        "tile_scores_json": "",
        "tile_qualities_json": "",
        "tile_jpeg_bytes_json": "",
        "container_overhead_bytes": "",
        "unique_quality_count": "",
        "minimum_quality": "",
        "maximum_quality": "",
        "enhanced_tile_count": "",
        "candidate_count": "",
        "feasible_candidate_count": "",
        "actual_future_trajectory_used": "false",
        "decode_width_px": "",
        "decode_height_px": "",
        "decode_mode": "",
    }


def run_validation() -> tuple[list[dict[str, str]], dict]:
    image, metadata, _csv_rows, mask, polygons = load_m4d_evidence()
    frame_hash = sha256_file(PROJECT_ROOT / metadata["frame_path"])
    cache = build_tile_cache(image)
    score_maps = {
        "center_roi": center_roi_scores((float(metadata["camera"]["cx_px"]), float(metadata["camera"]["cy_px"]))),
        "object_roi": object_roi_scores(polygons),
        "risk_roi": risk_roi_scores(mask),
    }
    target_values = tuple(target for _, target in DEVELOPMENT_BUDGETS)
    spatial_matches = {
        method: match_spatial_allocations_to_budgets(score_map, cache, target_values, DEFAULT_ALLOCATION_SEARCH_SPACE)
        for method, score_map in score_maps.items()
    }
    rows: list[dict[str, str]] = []
    artifacts: list[tuple[str, str, bytes, Image.Image]] = []
    for index, (budget_id, target_bytes) in enumerate(DEVELOPMENT_BUDGETS):
        row, container, decoded = _uniform_row(image, budget_id, target_bytes, frame_hash)
        rows.append(row)
        artifacts.append(("uniform", budget_id, container, decoded))
        for method in ("center_roi", "object_roi", "risk_roi"):
            row, container, decoded = _spatial_row(spatial_matches[method][index], budget_id, frame_hash)
            rows.append(row)
            artifacts.append((method, budget_id, container, decoded))
    _write_artifacts(artifacts)
    metadata_output = {
        "milestone": "5C",
        "validation_type": "single_frame_spatial_allocation_only",
        "development_only": True,
        "frame_id": "image_risk_validation_episode_0001",
        "source_frame_path": metadata["frame_path"],
        "source_frame_sha256": frame_hash,
        "m4d_csv_path": "data/logs/m4/image_risk_validation_episode_0001.csv",
        "m4d_metadata_path": "data/metadata/m4/image_risk_validation_episode_0001.json",
        "combined_float_mask_path": "data/masks/m4/image_risk_validation_episode_0001_masks.json",
        "actual_future_trajectory_used": False,
        "pillow_version": pillow_version(),
        "grid": grid_json(),
        "jpeg_parameters": jpeg_parameters_json(),
        "container": {"magic": MAGIC.decode("ascii"), "version": VERSION, "overhead_bytes": 311},
        "development_budgets": [{"budget_id": budget_id, "target_bytes": target, "bits_per_frame": target * 8} for budget_id, target in DEVELOPMENT_BUDGETS],
        "center_roi": {"principal_point_px": [metadata["camera"]["cx_px"], metadata["camera"]["cy_px"]], "sigma_normalized": 0.5},
        "spatial_search_space": {"background_quality": [1, 94], "enhancement_quality": [2, 95], "constraint": "enhancement_quality > background_quality", "top_k": [1, 48]},
        "selection_rule": "max_actual_bytes, then higher_enhancement_quality, higher_background_quality, smaller_top_k, lexicographic_config",
        "methods": ["uniform", "center_roi", "object_roi", "risk_roi"],
        "row_count": len(rows),
        "not_evaluated": ["PSNR", "SSIM", "risk-weighted PSNR", "perception", "navigation", "best method"],
    }
    return rows, metadata_output


def _write_artifacts(artifacts: list[tuple[str, str, bytes, Image.Image]]) -> None:
    M5C_CONTAINER_DIR.mkdir(parents=True, exist_ok=True)
    for method, budget_id, container, decoded in artifacts:
        (M5C_CONTAINER_DIR / f"{method}_{budget_id}.ravcjt").write_bytes(container)
        decoded.save(M5C_CONTAINER_DIR / f"{method}_{budget_id}.png", format="PNG")


def main() -> int:
    rows, metadata = run_validation()
    write_csv(rows)
    write_metadata(metadata)
    print(f"m5c_allocation_validation: rows={len(rows)}")
    print("m5c_allocation_validation: complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
