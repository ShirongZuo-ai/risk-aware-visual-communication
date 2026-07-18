"""Generate Milestone 4D image-risk mask diagnostics."""

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

from scripts.m4d_image_risk_common import mask_from_json, quantize_mask_value  # noqa: E402
from simulator.m4d_config import M4_LOG_DIR, M4_RESULTS_DIR, obstacle_spec_by_id  # noqa: E402


def _latest_csv() -> Path:
    candidates = sorted((PROJECT_ROOT / M4_LOG_DIR).glob("image_risk_validation_episode_*.csv"))
    if not candidates:
        raise FileNotFoundError("No M4D image-risk CSV found")
    return candidates[-1]


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _polygon(row: dict[str, str]) -> list[tuple[float, float]]:
    if not row["clipped_polygon"]:
        return []
    return [(float(item[0]), float(item[1])) for item in json.loads(row["clipped_polygon"])]


def _save_mask_png(mask, path: Path) -> None:
    image = Image.new("L", (mask.width_px, mask.height_px), 0)
    pixels = image.load()
    for v in range(mask.height_px):
        for u in range(mask.width_px):
            pixels[u, v] = quantize_mask_value(mask.get(u, v))
    image.save(path)


def _heat_color(value: float) -> tuple[int, int, int]:
    q = quantize_mask_value(value)
    return (q, max(0, q - 80), 255 - q)


def _overlay(frame: Image.Image, mask, rows: list[dict[str, str]], channel: str, path: Path) -> None:
    base = frame.convert("RGBA")
    heat = Image.new("RGBA", base.size, (0, 0, 0, 0))
    pix = heat.load()
    for v in range(mask.height_px):
        for u in range(mask.width_px):
            value = mask.get(u, v)
            if value > 0:
                r, g, b = _heat_color(value)
                pix[u, v] = (r, g, b, 120)
    composed = Image.alpha_composite(base, heat)
    scale = 3
    legend_h = 145
    output = Image.new("RGB", (composed.width * scale, composed.height * scale + legend_h), (12, 12, 12))
    output.paste(composed.convert("RGB").resize((composed.width * scale, composed.height * scale), Image.Resampling.NEAREST), (0, 0))
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default()
    specs = obstacle_spec_by_id()
    for index, row in enumerate(rows, start=1):
        spec = specs[row["obstacle_id"]]
        polygon = [(u * scale, v * scale) for u, v in _polygon(row)]
        if len(polygon) >= 3:
            draw.line(polygon + [polygon[0]], fill=spec.target_rgb, width=3)
            label_x = max(2, min(output.width - 30, int(polygon[0][0])))
            label_y = max(2, min(composed.height * scale - 12, int(polygon[0][1]) - 12))
            draw.text((label_x, label_y), str(index), fill=spec.target_rgb, font=font)
    cx = float(rows[0].get("cx_px", "79.5")) * scale if "cx_px" in rows[0] else 79.5 * scale
    cy = 59.5 * scale
    draw.line([(cx - 5, cy), (cx + 5, cy)], fill=(255, 255, 255), width=1)
    draw.line([(cx, cy - 5), (cx, cy + 5)], fill=(255, 255, 255), width=1)
    y = composed.height * scale + 4
    draw.text((4, y), f"M4D {channel} overlay: heat = heuristic image risk; polygon outlines are projected/clipped Boxes", fill=(255, 255, 255), font=font)
    draw.text((4, y + 14), "P=planned risk, S=state risk, C=combined risk; white cross=principal point", fill=(230, 230, 230), font=font)
    for i, row in enumerate(rows):
        spec = specs[row["obstacle_id"]]
        col = i // 5
        line = i % 5
        x = 4 + col * 320
        yy = y + 34 + line * 20
        draw.rectangle((x, yy + 3, x + 8, yy + 11), fill=spec.target_rgb)
        label = f"{i + 1}. {row['role']} P={float(row['planned_risk']):.3f} S={float(row['state_risk']):.3f} C={float(row['combined_risk']):.3f}"
        draw.text((x + 12, yy), label, fill=(230, 230, 230), font=font)
    output.save(path)


def _summary(rows: list[dict[str, str]], path: Path) -> None:
    width = 1200
    height = 360
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((15, 12), "M4D world-to-image risk summary (heuristic proxy, not collision probability)", fill=(0, 0, 0), font=font)
    max_bar = 180
    y = 42
    headers = ["role", "visibility", "eligible", "planned", "state", "combined", "candidate/written"]
    xs = [15, 260, 395, 490, 610, 730, 850]
    for x, header in zip(xs, headers):
        draw.text((x, y), header, fill=(0, 0, 0), font=font)
    y += 18
    for row in rows:
        draw.text((xs[0], y), row["role"], fill=(0, 0, 0), font=font)
        draw.text((xs[1], y), row["actual_visibility"], fill=(0, 0, 0), font=font)
        draw.text((xs[2], y), row["eligible_for_mask"], fill=(0, 0, 0), font=font)
        for idx, field in enumerate(("planned_risk", "state_risk", "combined_risk")):
            value = float(row[field])
            x0 = xs[3 + idx]
            draw.rectangle((x0, y + 2, x0 + int(max_bar * value), y + 10), fill=_heat_color(value))
            draw.text((x0, y + 11), f"{value:.3f}", fill=(0, 0, 0), font=font)
        counts = f"{row['candidate_pixel_count']}/{row['planned_written_pixel_count']},{row['state_written_pixel_count']},{row['combined_written_pixel_count']}"
        draw.text((xs[6], y), counts, fill=(0, 0, 0), font=font)
        y += 30
    image.save(path)


def plot(csv_path: Path) -> dict[str, str]:
    rows = _load_rows(csv_path)
    if not rows:
        raise ValueError("CSV has no rows")
    metadata_path = PROJECT_ROOT / "data" / "metadata" / "m4" / f"{csv_path.stem}.json"
    masks_path = PROJECT_ROOT / "data" / "masks" / "m4" / f"{csv_path.stem}_masks.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    masks_payload = json.loads(masks_path.read_text(encoding="utf-8"))["masks"]
    frame = Image.open(PROJECT_ROOT / metadata["frame_path"]).convert("RGB")
    output_dir = PROJECT_ROOT / M4_RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for channel in ("planned", "state", "combined"):
        mask = mask_from_json(masks_payload[channel])
        mask_path = output_dir / f"{channel}_mask.png"
        overlay_path = output_dir / f"{channel}_overlay.png"
        _save_mask_png(mask, mask_path)
        _overlay(frame, mask, rows, channel, overlay_path)
        outputs[f"{channel}_mask"] = str(mask_path)
        outputs[f"{channel}_overlay"] = str(overlay_path)
    summary_path = output_dir / "world_to_image_risk_summary.png"
    _summary(rows, summary_path)
    outputs["summary"] = str(summary_path)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path)
    args = parser.parse_args()
    csv_path = args.csv_path or _latest_csv()
    outputs = plot(csv_path if csv_path.is_absolute() else PROJECT_ROOT / csv_path)
    print(json.dumps(outputs, indent=2, sort_keys=True))
    print("m4d_plot: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
