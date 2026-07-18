"""Shared fixed-evidence IO for Milestone 5D evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import PIL
import skimage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.tile_container import MAGIC, VERSION  # noqa: E402
from evaluation.image_quality import SSIM_PARAMETERS  # noqa: E402
from evaluation.region_masks import HIGH_RISK_THRESHOLD, build_evaluation_regions  # noqa: E402
from scripts.m5c_allocation_common import (  # noqa: E402
    DEVELOPMENT_BUDGETS,
    M5C_CSV_PATH,
    M5C_METADATA_PATH,
    grid_json,
    jpeg_parameters_json,
    load_m4d_evidence,
    pillow_version,
    sha256_file,
)


M5C_SOURCE_COMMIT = "1788688"
M5D_CSV_PATH = PROJECT_ROOT / "data" / "logs" / "m5" / "m5d_single_frame_quality.csv"
M5D_METADATA_PATH = PROJECT_ROOT / "data" / "metadata" / "m5" / "m5d_single_frame_evaluation.json"
M5D_DECODED_DIR = PROJECT_ROOT / "data" / "decoded" / "m5" / "m5d"
METHOD_ORDER = ("uniform", "center_roi", "object_roi", "risk_roi")


CSV_FIELDS = [
    "frame_id", "frame_hash", "m5c_csv_sha256", "method", "budget_label", "target_bytes", "actual_total_bytes", "unused_bytes", "utilization",
    "q_background", "q_enhancement", "top_k", "min_quality", "max_quality", "unique_quality_count", "enhanced_tile_count",
    "full_mse", "full_psnr_db", "full_ssim", "risk_sum", "risk_weighted_mse", "risk_weighted_psnr_db",
    "object_pixel_count", "object_fraction", "object_mse", "object_psnr_db",
    "risk_support_pixel_count", "risk_support_fraction", "risk_support_mse", "risk_support_psnr_db",
    "high_risk_pixel_count", "high_risk_fraction", "high_risk_mse", "high_risk_psnr_db",
    "background_pixel_count", "background_fraction", "background_mse", "background_psnr_db",
    "risk_weighted_mean_quality", "high_risk_tile_count", "high_risk_tile_mean_quality", "high_risk_tile_min_quality", "high_risk_tile_max_quality", "high_risk_tile_payload_bytes",
    "zero_risk_tile_count", "zero_risk_tile_mean_quality", "zero_risk_tile_payload_bytes",
    "minimum_tile_payload_bytes", "maximum_tile_payload_bytes", "total_tile_payload_bytes", "container_overhead_bytes",
    "tile_qualities_json", "tile_payload_bytes_json", "pillow_version", "numpy_version", "scikit_image_version", "container_magic", "container_version", "actual_future_trajectory_used",
]


def read_m5c_rows() -> list[dict[str, str]]:
    with M5C_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = {(method, budget) for method in METHOD_ORDER for budget, _ in DEVELOPMENT_BUDGETS}
    keys = {(row.get("method"), row.get("budget_id")) for row in rows}
    if len(rows) != 16 or keys != expected or len(keys) != len(rows):
        raise ValueError("M5C evidence must contain exactly the fixed 16 method-budget rows")
    metadata = json.loads(M5C_METADATA_PATH.read_text(encoding="utf-8"))
    if metadata.get("actual_future_trajectory_used") is not False or metadata.get("row_count") != 16:
        raise ValueError("M5C metadata no-future-actual or row-count invariant failed")
    return rows


def load_fixed_evaluation_inputs():
    image, metadata, _m4d_rows, combined_mask, polygons = load_m4d_evidence()
    source_rgb = np.asarray(image, dtype=np.uint8)
    regions = build_evaluation_regions(combined_mask, polygons)
    if source_rgb.shape != (120, 160, 3):
        raise ValueError("M4D source must be 160x120 RGB")
    return source_rgb, metadata, combined_mask, polygons, regions


def json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def metric_cell(value: float | int | None) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, float) and value == float("inf"):
        return "inf"
    return repr(value)


def dependency_versions() -> dict[str, str]:
    return {"pillow": pillow_version(), "numpy": np.__version__, "scikit_image": skimage.__version__}


def common_metadata(frame_hash: str, m5c_csv_hash: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "milestone": "5D",
        "evaluation_type": "single_frame_fixed_m5c_matched_budget_quality_evaluation",
        "development_only": True,
        "frame_id": "image_risk_validation_episode_0001",
        "source_frame_path": "data/frames/m4/image_risk_validation_episode_0001.png",
        "source_frame_sha256": frame_hash,
        "m5c_source_commit": M5C_SOURCE_COMMIT,
        "m5c_csv_path": "data/logs/m5/m5c_allocation_validation.csv",
        "m5c_csv_sha256": m5c_csv_hash,
        "m5c_metadata_path": "data/metadata/m5/m5c_allocation_validation.json",
        "m4d_mask_path": "data/masks/m4/image_risk_validation_episode_0001_masks.json",
        "actual_future_trajectory_used": False,
        "methods": list(METHOD_ORDER),
        "development_budgets": [{"budget_label": label, "target_bytes": bytes_value, "bits_per_frame": bytes_value * 8} for label, bytes_value in DEVELOPMENT_BUDGETS],
        "grid": grid_json(),
        "jpeg_parameters": jpeg_parameters_json(),
        "container": {"magic": MAGIC.decode("ascii"), "version": VERSION, "overhead_bytes": 311},
        "dependencies": dependency_versions(),
        "ssim_parameters": SSIM_PARAMETERS,
        "metric_definitions": {
            "full_mse": "mean over all height, width, and RGB channels of squared uint8-to-float error",
            "full_psnr_db": "10 * log10(255^2 / full_mse), positive infinity when MSE is zero",
            "risk_weighted_mse": "sum(combined_float_risk * per_pixel_mean_rgb_squared_error) / sum(combined_float_risk)",
            "risk_weighted_psnr_db": "10 * log10(255^2 / risk_weighted_mse), positive infinity when weighted MSE is zero",
        },
        "region_definitions": {
            "eligible_object_union": "union of pixel-center rasterized eligible M4D clipped polygons",
            "risk_support": "combined_float_risk > 0",
            "high_risk": "combined_float_risk >= 0.20",
            "background": "complement of eligible_object_union",
        },
        "high_risk_threshold": HIGH_RISK_THRESHOLD,
        "source_m5c_rows": rows,
        "not_claimed": ["collision probability", "perception benefit", "navigation benefit", "statistical significance", "general superiority"],
    }


def write_csv(rows: list[dict[str, str]]) -> None:
    M5D_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with M5D_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_metadata(payload: dict[str, Any]) -> None:
    M5D_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    M5D_METADATA_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
