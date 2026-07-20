"""Shared evidence loading and serialization helpers for Milestone 5C."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

from PIL import Image
import PIL


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.tile_scoring import FloatMask, ProjectedPolygon  # noqa: E402
from compression.tiled_jpeg import (  # noqa: E402
    DEFAULT_M5_GRID,
    JPEG_FORMAT,
    JPEG_OPTIMIZE,
    JPEG_PROGRESSIVE,
    JPEG_QUALITY_MAX,
    JPEG_QUALITY_MIN,
    JPEG_SUBSAMPLING,
)


FRAME_PATH = PROJECT_ROOT / "data" / "frames" / "m4" / "image_risk_validation_episode_0001.png"
CSV_PATH = PROJECT_ROOT / "data" / "logs" / "m4" / "image_risk_validation_episode_0001.csv"
METADATA_PATH = PROJECT_ROOT / "data" / "metadata" / "m4" / "image_risk_validation_episode_0001.json"
MASKS_PATH = PROJECT_ROOT / "data" / "masks" / "m4" / "image_risk_validation_episode_0001_masks.json"
DEVELOPMENT_BUDGETS = (
    ("severe", 31348),
    ("low", 32105),
    ("medium", 32729),
    ("high", 33959),
)
M5C_CSV_PATH = PROJECT_ROOT / "data" / "logs" / "m5" / "m5c_allocation_validation.csv"
M5C_METADATA_PATH = PROJECT_ROOT / "data" / "metadata" / "m5" / "m5c_allocation_validation.json"
M5C_CONTAINER_DIR = PROJECT_ROOT / "data" / "compression" / "m5" / "m5c_selected_containers"


CSV_FIELDS = [
    "frame_id", "frame_hash", "method", "budget_id", "target_bytes", "actual_total_bytes", "unused_bytes", "utilization",
    "grid_json", "jpeg_parameters_json", "pillow_version", "container_magic", "container_version",
    "selected_allocation_json", "tile_scores_json", "tile_qualities_json", "tile_jpeg_bytes_json",
    "container_overhead_bytes", "unique_quality_count", "minimum_quality", "maximum_quality", "enhanced_tile_count",
    "candidate_count", "feasible_candidate_count", "actual_future_trajectory_used", "decode_width_px", "decode_height_px", "decode_mode",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing evidence file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_m4d_evidence() -> tuple[Image.Image, dict[str, Any], list[dict[str, str]], FloatMask, tuple[ProjectedPolygon, ...]]:
    metadata = read_json(METADATA_PATH)
    masks_payload = read_json(MASKS_PATH)
    if metadata.get("frame_path") != "data/frames/m4/image_risk_validation_episode_0001.png":
        raise ValueError("M4D metadata frame path is not the accepted official evidence")
    sources = metadata.get("trajectory_sources")
    if not isinstance(sources, dict) or sources.get("actual_future_trajectory_used") is not False:
        raise ValueError("M4D evidence must explicitly declare actual_future_trajectory_used=false")
    camera = metadata.get("camera")
    if not isinstance(camera, dict) or camera.get("width_px") != 160 or camera.get("height_px") != 120:
        raise ValueError("M4D camera schema must be 160x120")
    if masks_payload.get("episode_id") != "episode_0001":
        raise ValueError("M4D masks must be from image_risk_validation_episode_0001")
    combined = masks_payload.get("masks", {}).get("combined")
    if not isinstance(combined, dict):
        raise ValueError("M4D combined float mask is missing")
    mask = FloatMask(
        int(combined.get("width", -1)),
        int(combined.get("height", -1)),
        tuple(combined.get("values", ())),
        str(combined.get("layout", "")),
    )
    if (mask.width_px, mask.height_px) != (160, 120):
        raise ValueError("M4D combined mask dimensions must be 160x120")
    projections = metadata.get("projections")
    if not isinstance(projections, dict):
        raise ValueError("M4D metadata projections are missing")
    polygons = []
    for obstacle_id in sorted(projections):
        item = projections[obstacle_id]
        polygons.append(
            ProjectedPolygon(
                obstacle_id,
                str(item.get("visibility_status", "")),
                tuple((float(point[0]), float(point[1])) for point in item.get("clipped_polygon", ())),
            )
        )
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 9:
        raise ValueError("M4D official CSV must contain nine obstacle rows")
    if not FRAME_PATH.exists():
        raise FileNotFoundError(f"missing M4D frame: {FRAME_PATH}")
    with Image.open(FRAME_PATH) as opened:
        image = opened.convert("RGB")
    if image.size != (DEFAULT_M5_GRID.frame_width_px, DEFAULT_M5_GRID.frame_height_px):
        raise ValueError("M4D source frame dimensions do not match the frozen M5 grid")
    return image, metadata, rows, mask, tuple(polygons)


def grid_json() -> dict[str, int | str]:
    return {
        "frame_width_px": DEFAULT_M5_GRID.frame_width_px,
        "frame_height_px": DEFAULT_M5_GRID.frame_height_px,
        "tile_width_px": DEFAULT_M5_GRID.tile_width_px,
        "tile_height_px": DEFAULT_M5_GRID.tile_height_px,
        "columns": DEFAULT_M5_GRID.columns,
        "rows": DEFAULT_M5_GRID.rows,
        "tile_count": DEFAULT_M5_GRID.tile_count,
        "tile_id_rule": "tile_id = tile_row * columns + tile_column",
    }


def jpeg_parameters_json() -> dict[str, int | bool | str]:
    return {
        "format": JPEG_FORMAT,
        "quality_min": JPEG_QUALITY_MIN,
        "quality_max": JPEG_QUALITY_MAX,
        "progressive": JPEG_PROGRESSIVE,
        "optimize": JPEG_OPTIMIZE,
        "subsampling": JPEG_SUBSAMPLING,
    }


def json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def write_csv(rows: list[dict[str, str]], path: Path = M5C_CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_metadata(payload: dict[str, Any], path: Path = M5C_METADATA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_finite_probability_sequence(values: list[float] | tuple[float, ...]) -> None:
    for value in values:
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError("scores must be finite probabilities in [0, 1]")


def pillow_version() -> str:
    return PIL.__version__
