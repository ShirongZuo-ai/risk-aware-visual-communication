"""Run the Milestone 5B Uniform tiled-JPEG quality sweep."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
import sys

from PIL import Image
import PIL


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compression.budget_matcher import match_uniform_quality_to_budget  # noqa: E402
from compression.tile_container import HEADER_BYTES, INDEX_ENTRY_BYTES, container_overhead_bytes, deserialize_tiled_frame  # noqa: E402
from compression.tiled_jpeg import (  # noqa: E402
    DEFAULT_M5_GRID,
    JPEG_FORMAT,
    JPEG_OPTIMIZE,
    JPEG_PROGRESSIVE,
    JPEG_QUALITY_MAX,
    JPEG_QUALITY_MIN,
    JPEG_SUBSAMPLING,
    decode_tiles_to_rgb,
    encode_uniform_tiled_jpeg,
)


DEFAULT_FRAME_PATH = PROJECT_ROOT / "data" / "frames" / "m4" / "image_risk_validation_episode_0001.png"
CSV_PATH = PROJECT_ROOT / "data" / "logs" / "m5" / "m5b_uniform_quality_sweep.csv"
METADATA_PATH = PROJECT_ROOT / "data" / "metadata" / "m5" / "m5b_uniform_pilot.json"
PLOT_PATH = PROJECT_ROOT / "results" / "m5_compression" / "m5b_uniform_payload_curve.png"

CSV_FIELDS = [
    "quality",
    "total_bytes",
    "tile_jpeg_bytes",
    "container_overhead_bytes",
    "min_tile_payload_bytes",
    "mean_tile_payload_bytes",
    "max_tile_payload_bytes",
    "encode_time_ms",
    "decode_time_ms",
    "decoded_width_px",
    "decoded_height_px",
    "decoded_mode",
    "deterministic_repeat",
    "container_round_trip",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_relative_or_string(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_source_frame(path: Path) -> Image.Image:
    if not path.exists():
        raise FileNotFoundError(f"missing source frame: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != (DEFAULT_M5_GRID.frame_width_px, DEFAULT_M5_GRID.frame_height_px):
        raise ValueError(f"source frame must be {DEFAULT_M5_GRID.frame_width_px}x{DEFAULT_M5_GRID.frame_height_px}")
    return image


def sweep_uniform_quality(image: Image.Image) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    expected_overhead = container_overhead_bytes(DEFAULT_M5_GRID)
    for quality in range(JPEG_QUALITY_MIN, JPEG_QUALITY_MAX + 1):
        start = perf_counter()
        encoded = encode_uniform_tiled_jpeg(image, quality, DEFAULT_M5_GRID)
        encode_time_ms = (perf_counter() - start) * 1000.0

        repeat = encode_uniform_tiled_jpeg(image, quality, DEFAULT_M5_GRID)
        deterministic_repeat = repeat.container_bytes == encoded.container_bytes

        parsed = deserialize_tiled_frame(encoded.container_bytes)
        container_round_trip = parsed.container_bytes == encoded.container_bytes and tuple(
            tile.jpeg_payload for tile in parsed.tiles
        ) == tuple(tile.jpeg_payload for tile in encoded.tiles)

        start = perf_counter()
        decoded = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
        decode_time_ms = (perf_counter() - start) * 1000.0

        tile_bytes = encoded.tile_payload_bytes
        if encoded.container_overhead_bytes != expected_overhead:
            raise ValueError("container overhead does not match deterministic header/index size")
        rows.append(
            {
                "quality": quality,
                "total_bytes": encoded.total_bytes,
                "tile_jpeg_bytes": sum(tile_bytes),
                "container_overhead_bytes": encoded.container_overhead_bytes,
                "min_tile_payload_bytes": min(tile_bytes),
                "mean_tile_payload_bytes": sum(tile_bytes) / len(tile_bytes),
                "max_tile_payload_bytes": max(tile_bytes),
                "encode_time_ms": encode_time_ms,
                "decode_time_ms": decode_time_ms,
                "decoded_width_px": decoded.width,
                "decoded_height_px": decoded.height,
                "decoded_mode": decoded.mode,
                "deterministic_repeat": str(deterministic_repeat).lower(),
                "container_round_trip": str(container_round_trip).lower(),
            }
        )
    return rows


def suggest_development_budgets(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_quality = {int(row["quality"]): int(row["total_bytes"]) for row in rows}
    preferred = [5, 25, 50, 80]
    selected: list[tuple[str, int, int]] = []
    used_bytes: set[int] = set()
    for label, quality in zip(("severe", "low", "medium", "high"), preferred):
        target = by_quality[quality]
        if target in used_bytes:
            continue
        selected.append((label, quality, target))
        used_bytes.add(target)

    if len(selected) < 4:
        unique = []
        seen = set()
        for row in rows:
            total = int(row["total_bytes"])
            if total not in seen:
                unique.append((int(row["quality"]), total))
                seen.add(total)
        if len(unique) < 4:
            raise ValueError("uniform sweep produced fewer than four unique payload sizes")
        positions = [0, round((len(unique) - 1) * 0.33), round((len(unique) - 1) * 0.66), len(unique) - 1]
        labels = ("severe", "low", "medium", "high")
        selected = []
        used_bytes.clear()
        for label, position in zip(labels, positions):
            quality, target = unique[position]
            if target in used_bytes:
                continue
            selected.append((label, quality, target))
            used_bytes.add(target)
    budgets = []
    for label, quality, target in selected[:4]:
        match = match_uniform_quality_to_budget(load_source_frame(DEFAULT_FRAME_PATH), target, DEFAULT_M5_GRID)
        budgets.append(
            {
                "budget_id": label,
                "target_bytes": target,
                "bits_per_frame": target * 8,
                "source_uniform_quality": quality,
                "matched_quality": match.quality,
                "matched_total_bytes": match.actual_total_bytes,
                "utilization": match.utilization,
                "development_only": True,
            }
        )
    return budgets


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_metadata(frame_path: Path, rows: list[dict[str, object]], budgets: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_values = [int(row["total_bytes"]) for row in rows]
    metadata = {
        "milestone": "5B",
        "pilot_type": "uniform_tiled_jpeg_quality_sweep",
        "development_only": True,
        "source_frame_path": project_relative_or_string(frame_path),
        "source_frame_sha256": sha256_file(frame_path),
        "pillow_version": PIL.__version__,
        "bit_exact_scope": "Stable only within the same Pillow/libjpeg environment; rerun budget matching across environments.",
        "grid": {
            "frame_width_px": DEFAULT_M5_GRID.frame_width_px,
            "frame_height_px": DEFAULT_M5_GRID.frame_height_px,
            "tile_width_px": DEFAULT_M5_GRID.tile_width_px,
            "tile_height_px": DEFAULT_M5_GRID.tile_height_px,
            "columns": DEFAULT_M5_GRID.columns,
            "rows": DEFAULT_M5_GRID.rows,
            "tile_count": DEFAULT_M5_GRID.tile_count,
            "tile_id_rule": "tile_id = tile_row * columns + tile_column",
        },
        "jpeg_parameters": {
            "format": JPEG_FORMAT,
            "quality_min": JPEG_QUALITY_MIN,
            "quality_max": JPEG_QUALITY_MAX,
            "progressive": JPEG_PROGRESSIVE,
            "optimize": JPEG_OPTIMIZE,
            "subsampling": JPEG_SUBSAMPLING,
        },
        "container": {
            "magic": "RAVCJT1",
            "version": 1,
            "endianness": "big",
            "header_bytes": HEADER_BYTES,
            "index_entry_bytes": INDEX_ENTRY_BYTES,
            "index_entries": DEFAULT_M5_GRID.tile_count,
            "overhead_bytes": container_overhead_bytes(DEFAULT_M5_GRID),
        },
        "quality_range": {
            "min_quality": JPEG_QUALITY_MIN,
            "max_quality": JPEG_QUALITY_MAX,
            "min_total_bytes": min(total_values),
            "max_total_bytes": max(total_values),
        },
        "development_budgets": budgets,
        "budget_generation_rule": "Use actual container bytes at representative Uniform qualities 5, 25, 50, and 80 when unique; otherwise use spread unique payload quantiles. These are development budgets only.",
        "outputs": {
            "csv": str(CSV_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "metadata": str(METADATA_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "plot": str(PLOT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        },
    }
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def write_payload_curve(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    qualities = [int(row["quality"]) for row in rows]
    totals = [int(row["total_bytes"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(qualities, totals, marker=".", linewidth=1.2)
    ax.set_title("M5B Uniform tiled-JPEG payload sweep")
    ax.set_xlabel("Uniform JPEG quality")
    ax.set_ylabel("Actual container bytes / frame")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_pilot(frame_path: Path = DEFAULT_FRAME_PATH) -> dict[str, object]:
    image = load_source_frame(frame_path)
    rows = sweep_uniform_quality(image)
    budgets = suggest_development_budgets(rows)
    write_csv(rows, CSV_PATH)
    write_metadata(frame_path, rows, budgets, METADATA_PATH)
    write_payload_curve(rows, PLOT_PATH)
    return {
        "csv": str(CSV_PATH),
        "metadata": str(METADATA_PATH),
        "plot": str(PLOT_PATH),
        "rows": len(rows),
        "min_total_bytes": min(int(row["total_bytes"]) for row in rows),
        "max_total_bytes": max(int(row["total_bytes"]) for row in rows),
        "development_budgets": budgets,
    }


def main() -> int:
    frame_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FRAME_PATH
    if not frame_path.is_absolute():
        frame_path = PROJECT_ROOT / frame_path
    result = run_pilot(frame_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("m5b_uniform_pilot: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
