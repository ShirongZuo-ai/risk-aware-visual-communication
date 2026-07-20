"""Validate Milestone 5B Uniform tiled-JPEG pilot outputs."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys

from PIL import Image
import PIL


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.budget_matcher import match_uniform_quality_to_budget  # noqa: E402
from compression.tile_container import container_overhead_bytes, deserialize_tiled_frame  # noqa: E402
from compression.tiled_jpeg import DEFAULT_M5_GRID, JPEG_QUALITY_MAX, JPEG_QUALITY_MIN, decode_tiles_to_rgb, encode_uniform_tiled_jpeg  # noqa: E402
from scripts.run_m5b_uniform_pilot import CSV_FIELDS, CSV_PATH, DEFAULT_FRAME_PATH, METADATA_PATH, PLOT_PATH, sha256_file  # noqa: E402


def fail(message: str) -> None:
    raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        fail(f"missing CSV: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            fail(f"CSV schema mismatch: {reader.fieldnames}")
        return list(reader)


def finite_float(row: dict[str, str], field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        fail(f"{field} is not finite")
    return value


def validate(csv_path: Path = CSV_PATH, metadata_path: Path = METADATA_PATH) -> dict[str, object]:
    rows = read_csv(csv_path)
    expected_qualities = list(range(JPEG_QUALITY_MIN, JPEG_QUALITY_MAX + 1))
    qualities = [int(row["quality"]) for row in rows]
    if qualities != expected_qualities:
        fail("quality sweep must cover every integer quality from 1 to 95 exactly once")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["pillow_version"] != PIL.__version__:
        fail("metadata Pillow version does not match runtime")
    if metadata["source_frame_sha256"] != sha256_file(PROJECT_ROOT / metadata["source_frame_path"]):
        fail("source frame hash mismatch")
    if metadata["grid"]["tile_count"] != DEFAULT_M5_GRID.tile_count:
        fail("metadata grid tile count mismatch")
    if not metadata.get("development_only"):
        fail("metadata must mark budgets as development_only")

    image = Image.open(DEFAULT_FRAME_PATH).convert("RGB")
    if image.size != (DEFAULT_M5_GRID.frame_width_px, DEFAULT_M5_GRID.frame_height_px):
        fail("source image dimensions mismatch")
    expected_overhead = container_overhead_bytes(DEFAULT_M5_GRID)
    for row in rows:
        quality = int(row["quality"])
        encoded = encode_uniform_tiled_jpeg(image, quality, DEFAULT_M5_GRID)
        parsed = deserialize_tiled_frame(encoded.container_bytes)
        decoded = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
        repeat = encode_uniform_tiled_jpeg(image, quality, DEFAULT_M5_GRID)
        tile_sum = sum(encoded.tile_payload_bytes)
        if int(row["total_bytes"]) != encoded.total_bytes:
            fail(f"quality {quality}: total bytes mismatch")
        if int(row["tile_jpeg_bytes"]) != tile_sum:
            fail(f"quality {quality}: tile bytes mismatch")
        if int(row["container_overhead_bytes"]) != expected_overhead:
            fail(f"quality {quality}: overhead mismatch")
        if encoded.total_bytes != tile_sum + expected_overhead:
            fail(f"quality {quality}: total bytes does not include full container")
        if int(row["min_tile_payload_bytes"]) != min(encoded.tile_payload_bytes):
            fail(f"quality {quality}: min tile bytes mismatch")
        if abs(finite_float(row, "mean_tile_payload_bytes") - tile_sum / DEFAULT_M5_GRID.tile_count) > 1e-9:
            fail(f"quality {quality}: mean tile bytes mismatch")
        if int(row["max_tile_payload_bytes"]) != max(encoded.tile_payload_bytes):
            fail(f"quality {quality}: max tile bytes mismatch")
        if decoded.size != (DEFAULT_M5_GRID.frame_width_px, DEFAULT_M5_GRID.frame_height_px) or decoded.mode != "RGB":
            fail(f"quality {quality}: decoded image mismatch")
        if row["decoded_mode"] != "RGB" or int(row["decoded_width_px"]) != 160 or int(row["decoded_height_px"]) != 120:
            fail(f"quality {quality}: CSV decoded fields mismatch")
        if row["deterministic_repeat"] != "true" or repeat.container_bytes != encoded.container_bytes:
            fail(f"quality {quality}: deterministic repeat failed")
        if row["container_round_trip"] != "true" or parsed.container_bytes != encoded.container_bytes:
            fail(f"quality {quality}: container round-trip failed")
        finite_float(row, "encode_time_ms")
        finite_float(row, "decode_time_ms")

    total_values = [int(row["total_bytes"]) for row in rows]
    budgets = metadata["development_budgets"]
    if len(budgets) < 4:
        fail("expected at least four development budgets")
    matched_qualities = []
    for budget in budgets:
        if not budget.get("development_only"):
            fail("budget must be marked development_only")
        target = int(budget["target_bytes"])
        if target < min(total_values) or target > max(total_values):
            fail(f"budget outside feasible range: {target}")
        match = match_uniform_quality_to_budget(image, target, DEFAULT_M5_GRID)
        if match.actual_total_bytes > target:
            fail("matcher exceeded budget")
        if not any(value <= target for value in total_values):
            fail("budget has no legal candidate")
        if int(budget["matched_quality"]) != match.quality:
            fail("metadata matched quality mismatch")
        if int(budget["matched_total_bytes"]) != match.actual_total_bytes:
            fail("metadata matched bytes mismatch")
        matched_qualities.append(match.quality)
    if len(set(matched_qualities)) < 4:
        fail("development budgets all collapse to fewer than four matched qualities")
    if not PLOT_PATH.exists():
        fail(f"missing payload curve plot: {PLOT_PATH}")
    return {
        "rows": len(rows),
        "min_total_bytes": min(total_values),
        "max_total_bytes": max(total_values),
        "development_budgets": budgets,
        "matched_qualities": matched_qualities,
        "pillow_version": PIL.__version__,
    }


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_PATH
    metadata_path = Path(sys.argv[2]) if len(sys.argv) > 2 else METADATA_PATH
    if not csv_path.is_absolute():
        csv_path = PROJECT_ROOT / csv_path
    if not metadata_path.is_absolute():
        metadata_path = PROJECT_ROOT / metadata_path
    try:
        result = validate(csv_path, metadata_path)
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    print("m5b_uniform_pilot_validator: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
