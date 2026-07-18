"""Draw a Milestone 4C projection overlay on the saved RGB frame."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulator.m4c_config import M4_LOG_DIR, M4_RESULTS_DIR, obstacle_spec_by_role  # noqa: E402


def _latest_csv() -> Path:
    candidates = sorted((PROJECT_ROOT / M4_LOG_DIR).glob("projection_validation_episode_*.csv"))
    if not candidates:
        raise FileNotFoundError("No M4C projection CSV found")
    return candidates[-1]


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _parse_polygon(value: str) -> list[tuple[float, float]]:
    if not value:
        return []
    return [(float(item[0]), float(item[1])) for item in json.loads(value)]


def _bbox(row: dict[str, str]) -> tuple[float, float, float, float] | None:
    if not row["bbox_min_u"]:
        return None
    return (float(row["bbox_min_u"]), float(row["bbox_min_v"]), float(row["bbox_max_u"]), float(row["bbox_max_v"]))


def draw_overlay(csv_path: Path, output_path: Path) -> None:
    rows = _load_rows(csv_path)
    if not rows:
        raise ValueError("CSV has no rows")
    frame_path = PROJECT_ROOT / rows[0]["frame_path"]
    image = Image.open(frame_path).convert("RGB")
    scale = 3
    legend_height = 126
    overlay = Image.new("RGB", (image.width * scale, image.height * scale + legend_height), (12, 12, 12))
    overlay.paste(image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST), (0, 0))
    draw = ImageDraw.Draw(overlay)
    specs = obstacle_spec_by_role()
    font = ImageFont.load_default()
    cx = float(rows[0]["cx_px"]) * scale
    cy = float(rows[0]["cy_px"]) * scale
    draw.line([(cx - 4, cy), (cx + 4, cy)], fill=(255, 255, 255), width=1)
    draw.line([(cx, cy - 4), (cx, cy + 4)], fill=(255, 255, 255), width=1)

    legend_rows: list[tuple[int, str, tuple[int, int, int]]] = []
    for index, row in enumerate(rows, start=1):
        role = row["role"]
        spec = specs[role]
        color = spec.target_rgb
        polygon = [(u * scale, v * scale) for u, v in _parse_polygon(row["clipped_polygon"])]
        if len(polygon) >= 3:
            draw.line(polygon + [polygon[0]], fill=color, width=3)
        bbox = _bbox(row)
        if bbox is not None:
            scaled_bbox = tuple(value * scale for value in bbox)
            draw.rectangle(scaled_bbox, outline=color, width=2)
            label_x = max(2.0, min(image.width * scale - 12.0, scaled_bbox[0]))
            label_y = max(2.0, min(image.height * scale - 12.0, scaled_bbox[1] - 12.0))
            draw.rectangle((label_x - 1, label_y - 1, label_x + 10, label_y + 9), fill=(0, 0, 0))
            draw.text((label_x, label_y), str(index), fill=color, font=font)
        legend_rows.append((index, f"{role}: {row['actual_visibility']}", color))

    legend_y = image.height * scale + 4
    draw.text((4, legend_y), "M4C projection overlay: geometry outlines/bboxes only; not an image risk map", fill=(255, 255, 255), font=font)
    draw.text((4, legend_y + 12), "white cross = principal point", fill=(255, 255, 255), font=font)
    for item_index, (index, label, color) in enumerate(legend_rows):
        column = item_index // 5
        row_index = item_index % 5
        x = 4 + column * 230
        y = legend_y + 28 + row_index * 18
        draw.rectangle((x, y + 2, x + 8, y + 10), fill=color)
        draw.text((x + 12, y), f"{index}. {label}", fill=(230, 230, 230), font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / M4_RESULTS_DIR / "projection_overlay.png")
    args = parser.parse_args()
    csv_path = args.csv_path or _latest_csv()
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    draw_overlay(csv_path, output_path)
    print(f"projection_overlay={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
