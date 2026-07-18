"""Independently recompute fixed M5D metrics and fairness invariants."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.image_quality import compute_ssim  # noqa: E402
from evaluation.matched_budget_evaluation import evaluate_fixed_m5c_row  # noqa: E402
from scripts.m5c_allocation_common import sha256_file  # noqa: E402
from scripts.m5d_evaluation_common import (  # noqa: E402
    CSV_FIELDS,
    DEVELOPMENT_BUDGETS,
    M5C_CSV_PATH,
    M5D_CSV_PATH,
    M5D_DECODED_DIR,
    M5D_METADATA_PATH,
    METHOD_ORDER,
    M5C_SOURCE_COMMIT,
    dependency_versions,
    load_fixed_evaluation_inputs,
    metric_cell,
    read_m5c_rows,
)


def read_csv(path: Path = M5D_CSV_PATH) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError("M5D CSV schema mismatch")
        return list(reader)


def validate(path: Path = M5D_CSV_PATH) -> list[str]:
    errors: list[str] = []
    if not path.exists() or not M5D_METADATA_PATH.exists():
        return ["missing M5D output CSV or metadata"]
    try:
        rows = read_csv(path)
        metadata = json.loads(M5D_METADATA_PATH.read_text(encoding="utf-8"))
        source_rgb, m4d_metadata, combined_mask, _polygons, regions = load_fixed_evaluation_inputs()
        m5c_rows = read_m5c_rows()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    expected_keys = {(method, budget) for method in METHOD_ORDER for budget, _ in DEVELOPMENT_BUDGETS}
    keys = {(row.get("method"), row.get("budget_label")) for row in rows}
    if len(rows) != 16 or keys != expected_keys or len(keys) != len(rows):
        return ["M5D CSV must contain exactly 16 unique method-budget rows"]
    expected_frame_hash = sha256_file(PROJECT_ROOT / m4d_metadata["frame_path"])
    expected_m5c_hash = sha256_file(M5C_CSV_PATH)
    if metadata.get("source_frame_sha256") != expected_frame_hash or metadata.get("m5c_csv_sha256") != expected_m5c_hash:
        errors.append("metadata source hash mismatch")
    if metadata.get("m5c_source_commit") != M5C_SOURCE_COMMIT or metadata.get("actual_future_trajectory_used") is not False:
        errors.append("metadata M5C commit or no-future-actual invariant mismatch")
    if metadata.get("row_count") != 16 or metadata.get("high_risk_threshold") != 0.20:
        errors.append("metadata row count or high-risk threshold mismatch")
    if metadata.get("dependencies") != dependency_versions():
        errors.append("metadata dependency version mismatch")
    if metadata.get("source_m5c_rows") != m5c_rows:
        errors.append("metadata fixed M5C evidence rows mismatch")

    m5c_by_key = {(row["method"], row["budget_id"]): row for row in m5c_rows}
    for row in rows:
        label = f"{row['method']}/{row['budget_label']}"
        fixed = m5c_by_key[(row["method"], row["budget_label"])]
        _check_fixed_identity(row, fixed, expected_frame_hash, expected_m5c_hash, errors)
        try:
            result = evaluate_fixed_m5c_row(source_rgb, fixed, combined_mask.values, regions, compute_ssim)
        except ValueError as exc:
            errors.append(f"{label}: independent fixed evaluation failed: {exc}")
            continue
        _compare_metrics(row, result, regions, errors, label)
        _check_decoded_file(row, result.decoded_rgb, source_rgb, errors, label)
    _check_fairness_by_budget(rows, errors)
    return errors


def _check_fixed_identity(row, fixed, frame_hash, m5c_hash, errors):
    label = f"{row['method']}/{row['budget_label']}"
    for field, expected in (("frame_id", "image_risk_validation_episode_0001"), ("frame_hash", frame_hash), ("m5c_csv_sha256", m5c_hash), ("actual_total_bytes", fixed["actual_total_bytes"]), ("unused_bytes", fixed["unused_bytes"]), ("utilization", fixed["utilization"]), ("container_overhead_bytes", "311"), ("actual_future_trajectory_used", "false")):
        if row[field] != expected:
            errors.append(f"{label}: {field} mismatch")
    if row["tile_qualities_json"] != fixed["tile_qualities_json"] or row["tile_payload_bytes_json"] != fixed["tile_jpeg_bytes_json"]:
        errors.append(f"{label}: M5C fixed tile data mismatch")
    config = json.loads(fixed["selected_allocation_json"])
    qualities = tuple(int(value) for value in json.loads(fixed["tile_qualities_json"]))
    expected_config = {
        "q_background": str(config["background_quality"]),
        "q_enhancement": str(config["enhancement_quality"]),
        "top_k": str(config["top_k"]),
        "min_quality": str(min(qualities)),
        "max_quality": str(max(qualities)),
        "unique_quality_count": str(len(set(qualities))),
        "enhanced_tile_count": fixed["enhanced_tile_count"],
    }
    for field, expected in expected_config.items():
        if row[field] != expected:
            errors.append(f"{label}: fixed M5C allocation configuration mismatch for {field}")
    if int(row["actual_total_bytes"]) != int(row["target_bytes"]):
        errors.append(f"{label}: actual bytes must exactly equal target")


def _compare_metrics(row, result, regions, errors, label):
    values = {
        "full_mse": result.full.mse, "full_psnr_db": result.full.psnr_db, "full_ssim": result.full_ssim,
        "risk_sum": result.risk_sum, "risk_weighted_mse": result.risk_weighted.mse, "risk_weighted_psnr_db": result.risk_weighted.psnr_db,
        "risk_weighted_mean_quality": result.diagnostics.risk_weighted_mean_quality,
        "high_risk_tile_count": result.diagnostics.high_risk_tile_count, "high_risk_tile_mean_quality": result.diagnostics.high_risk_tile_mean_quality,
        "high_risk_tile_min_quality": result.diagnostics.high_risk_tile_minimum_quality, "high_risk_tile_max_quality": result.diagnostics.high_risk_tile_maximum_quality,
        "high_risk_tile_payload_bytes": result.diagnostics.high_risk_tile_payload_bytes, "zero_risk_tile_count": result.diagnostics.zero_risk_tile_count,
        "zero_risk_tile_mean_quality": result.diagnostics.zero_risk_tile_mean_quality, "zero_risk_tile_payload_bytes": result.diagnostics.zero_risk_tile_payload_bytes,
    }
    for field, value in values.items():
        if row[field] != metric_cell(value):
            errors.append(f"{label}: {field} mismatch")
    for name, mask in (("object", regions.eligible_object_union), ("risk_support", regions.risk_support), ("high_risk", regions.high_risk), ("background", regions.background)):
        metrics = result.regions[name]
        expected = {f"{name}_pixel_count": str(mask.pixel_count), f"{name}_fraction": metric_cell(mask.fraction), f"{name}_mse": metric_cell(metrics.mse), f"{name}_psnr_db": metric_cell(metrics.psnr_db)}
        for field, value in expected.items():
            if row[field] != value:
                errors.append(f"{label}: {field} mismatch")


def _check_decoded_file(row, expected_rgb, source_rgb, errors, label):
    path = M5D_DECODED_DIR / row["budget_label"] / f"{row['method']}.png"
    if not path.exists():
        errors.append(f"{label}: decoded PNG is missing")
        return
    with Image.open(path) as image:
        decoded = np.asarray(image.convert("RGB"), dtype=np.uint8)
    if decoded.shape != (120, 160, 3) or not np.array_equal(decoded, expected_rgb):
        errors.append(f"{label}: decoded PNG mismatch or wrong RGB dimensions")
    if np.array_equal(decoded, source_rgb):
        errors.append(f"{label}: decoded PNG unexpectedly equals the source frame")


def _check_fairness_by_budget(rows, errors):
    for budget_label, target_bytes in DEVELOPMENT_BUDGETS:
        budget_rows = [row for row in rows if row["budget_label"] == budget_label]
        if len(budget_rows) != 4:
            errors.append(f"{budget_label}: missing methods")
            continue
        if any(int(row["target_bytes"]) != target_bytes or int(row["actual_total_bytes"]) != target_bytes for row in budget_rows):
            errors.append(f"{budget_label}: target/actual byte fairness mismatch")
        if len({row["pillow_version"] for row in budget_rows}) != 1 or len({row["container_overhead_bytes"] for row in budget_rows}) != 1:
            errors.append(f"{budget_label}: backend fairness mismatch")


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("m5d_single_frame_evaluation: validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
