"""Evaluate the fixed 16 M5C allocations without selecting new candidates."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.image_quality import compute_ssim  # noqa: E402
from evaluation.matched_budget_evaluation import evaluate_fixed_m5c_row  # noqa: E402
from scripts.m5c_allocation_common import sha256_file  # noqa: E402
from scripts.m5d_evaluation_common import (  # noqa: E402
    DEVELOPMENT_BUDGETS,
    M5C_CSV_PATH,
    M5D_DECODED_DIR,
    METHOD_ORDER,
    common_metadata,
    dependency_versions,
    json_cell,
    load_fixed_evaluation_inputs,
    metric_cell,
    read_m5c_rows,
    write_csv,
    write_metadata,
)


def evaluate_rows() -> tuple[list[dict[str, str]], dict, dict[tuple[str, str], Image.Image]]:
    source_rgb, metadata, combined_mask, _polygons, regions = load_fixed_evaluation_inputs()
    m5c_rows = read_m5c_rows()
    m5c_by_key = {(row["method"], row["budget_id"]): row for row in m5c_rows}
    frame_hash = sha256_file(PROJECT_ROOT / metadata["frame_path"])
    m5c_hash = sha256_file(M5C_CSV_PATH)
    rows: list[dict[str, str]] = []
    decoded_images: dict[tuple[str, str], Image.Image] = {}
    for budget_label, target_bytes in DEVELOPMENT_BUDGETS:
        for method in METHOD_ORDER:
            fixed_row = m5c_by_key[(method, budget_label)]
            result = evaluate_fixed_m5c_row(source_rgb, fixed_row, combined_mask.values, regions, compute_ssim)
            config = json.loads(fixed_row["selected_allocation_json"])
            qualities = tuple(int(value) for value in json.loads(fixed_row["tile_qualities_json"]))
            tile_bytes = tuple(int(value) for value in json.loads(fixed_row["tile_jpeg_bytes_json"]))
            if result.container_bytes != (PROJECT_ROOT / "data" / "compression" / "m5" / "m5c_selected_containers" / f"{method}_{budget_label}.ravcjt").read_bytes():
                raise ValueError("M5C saved container differs from fixed-quality reconstruction")
            row = _result_row(method, budget_label, target_bytes, frame_hash, m5c_hash, fixed_row, config, qualities, tile_bytes, result, regions)
            rows.append(row)
            decoded_images[(method, budget_label)] = Image.fromarray(result.decoded_rgb, mode="RGB")
    metadata_output = common_metadata(frame_hash, m5c_hash, m5c_rows)
    metadata_output["row_count"] = len(rows)
    metadata_output["results"] = rows
    return rows, metadata_output, decoded_images


def _result_row(method, budget_label, target_bytes, frame_hash, m5c_hash, fixed_row, config, qualities, tile_bytes, result, regions):
    diagnostics = result.diagnostics
    values = {
        "frame_id": "image_risk_validation_episode_0001", "frame_hash": frame_hash, "m5c_csv_sha256": m5c_hash,
        "method": method, "budget_label": budget_label, "target_bytes": str(target_bytes), "actual_total_bytes": fixed_row["actual_total_bytes"], "unused_bytes": fixed_row["unused_bytes"], "utilization": fixed_row["utilization"],
        "q_background": str(config["background_quality"]), "q_enhancement": str(config["enhancement_quality"]), "top_k": str(config["top_k"]),
        "min_quality": str(min(qualities)), "max_quality": str(max(qualities)), "unique_quality_count": str(len(set(qualities))), "enhanced_tile_count": fixed_row["enhanced_tile_count"],
        "full_mse": metric_cell(result.full.mse), "full_psnr_db": metric_cell(result.full.psnr_db), "full_ssim": metric_cell(result.full_ssim),
        "risk_sum": metric_cell(result.risk_sum), "risk_weighted_mse": metric_cell(result.risk_weighted.mse), "risk_weighted_psnr_db": metric_cell(result.risk_weighted.psnr_db),
        "risk_weighted_mean_quality": metric_cell(diagnostics.risk_weighted_mean_quality), "high_risk_tile_count": str(diagnostics.high_risk_tile_count),
        "high_risk_tile_mean_quality": metric_cell(diagnostics.high_risk_tile_mean_quality), "high_risk_tile_min_quality": metric_cell(diagnostics.high_risk_tile_minimum_quality), "high_risk_tile_max_quality": metric_cell(diagnostics.high_risk_tile_maximum_quality), "high_risk_tile_payload_bytes": str(diagnostics.high_risk_tile_payload_bytes),
        "zero_risk_tile_count": str(diagnostics.zero_risk_tile_count), "zero_risk_tile_mean_quality": metric_cell(diagnostics.zero_risk_tile_mean_quality), "zero_risk_tile_payload_bytes": str(diagnostics.zero_risk_tile_payload_bytes),
        "minimum_tile_payload_bytes": str(min(tile_bytes)), "maximum_tile_payload_bytes": str(max(tile_bytes)), "total_tile_payload_bytes": str(sum(tile_bytes)), "container_overhead_bytes": fixed_row["container_overhead_bytes"],
        "tile_qualities_json": json_cell(list(qualities)), "tile_payload_bytes_json": json_cell(list(tile_bytes)),
        "pillow_version": dependency_versions()["pillow"], "numpy_version": dependency_versions()["numpy"], "scikit_image_version": dependency_versions()["scikit_image"], "container_magic": "RAVCJT1", "container_version": "1", "actual_future_trajectory_used": "false",
    }
    for name, mask in (("object", regions.eligible_object_union), ("risk_support", regions.risk_support), ("high_risk", regions.high_risk), ("background", regions.background)):
        metrics = result.regions[name]
        values[f"{name}_pixel_count"] = str(mask.pixel_count)
        values[f"{name}_fraction"] = metric_cell(mask.fraction)
        values[f"{name}_mse"] = metric_cell(metrics.mse)
        values[f"{name}_psnr_db"] = metric_cell(metrics.psnr_db)
    return values


def _write_decoded(decoded_images: dict[tuple[str, str], Image.Image]) -> None:
    for (method, budget_label), image in decoded_images.items():
        directory = M5D_DECODED_DIR / budget_label
        directory.mkdir(parents=True, exist_ok=True)
        image.save(directory / f"{method}.png", format="PNG")


def main() -> int:
    rows, metadata, decoded = evaluate_rows()
    write_csv(rows)
    write_metadata(metadata)
    _write_decoded(decoded)
    print(f"m5d_single_frame_evaluation: rows={len(rows)}")
    print("m5d_single_frame_evaluation: complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
