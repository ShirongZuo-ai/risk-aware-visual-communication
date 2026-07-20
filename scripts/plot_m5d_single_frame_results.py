"""Plot descriptive M5D single-frame results without selecting allocations."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.region_masks import build_evaluation_regions  # noqa: E402
from scripts.m5d_evaluation_common import (  # noqa: E402
    DEVELOPMENT_BUDGETS,
    M5D_CSV_PATH,
    M5D_DECODED_DIR,
    METHOD_ORDER,
    load_fixed_evaluation_inputs,
)


RESULTS_DIR = PROJECT_ROOT / "results" / "m5_compression"
METHOD_LABELS = {"uniform": "Uniform", "center_roi": "Center ROI", "object_roi": "Object ROI", "risk_roi": "Risk ROI"}
METHOD_COLORS = {"uniform": "#4C78A8", "center_roi": "#F58518", "object_roi": "#54A24B", "risk_roi": "#E45756"}


def load_rows() -> list[dict[str, str]]:
    with M5D_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot(rows: list[dict[str, str]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    by_method = {method: sorted((row for row in rows if row["method"] == method), key=lambda row: int(row["actual_total_bytes"])) for method in METHOD_ORDER}
    chart_specs = (
        ("full_psnr_db", "Full-image PSNR (dB)", "m5d_full_psnr_vs_bytes.png"),
        ("full_ssim", "Full-image SSIM", "m5d_full_ssim_vs_bytes.png"),
        ("risk_weighted_psnr_db", "Risk-weighted PSNR (dB, proxy)", "m5d_risk_weighted_psnr_vs_bytes.png"),
        ("object_psnr_db", "Eligible-object-region PSNR (dB)", "m5d_object_region_psnr_vs_bytes.png"),
        ("high_risk_psnr_db", "High-risk-region PSNR (dB)", "m5d_high_risk_region_psnr_vs_bytes.png"),
        ("background_psnr_db", "Background-region PSNR (dB)", "m5d_background_psnr_vs_bytes.png"),
    )
    for field, ylabel, filename in chart_specs:
        figure, axis = plt.subplots(figsize=(7.2, 4.1), constrained_layout=True)
        for method in METHOD_ORDER:
            selected = by_method[method]
            axis.plot([int(row["actual_total_bytes"]) for row in selected], [float(row[field]) for row in selected], marker="o", label=METHOD_LABELS[method], color=METHOD_COLORS[method])
        axis.set_xlabel("Actual transmitted bytes per frame")
        axis.set_ylabel(ylabel)
        axis.set_title(ylabel + " across fixed matched budgets")
        axis.legend()
        axis.grid(axis="y", alpha=0.25)
        figure.savefig(RESULTS_DIR / filename, dpi=160)
        plt.close(figure)
    _plot_allocation(rows)
    _plot_reconstructions(rows)


def _plot_allocation(rows: list[dict[str, str]]) -> None:
    figure, axes = plt.subplots(1, 4, figsize=(13, 3.5), constrained_layout=True, sharey=True)
    for axis, (budget, target) in zip(axes, DEVELOPMENT_BUDGETS):
        selected = {row["method"]: row for row in rows if row["budget_label"] == budget}
        values = [float(selected[method]["risk_weighted_mean_quality"]) for method in METHOD_ORDER]
        bars = axis.bar(range(4), values, color=[METHOD_COLORS[method] for method in METHOD_ORDER])
        axis.bar_label(bars, labels=[f"{value:.1f}" for value in values], fontsize=8, padding=2)
        axis.set_title(f"{budget}\n{target} B")
        axis.set_xticks(range(4), [METHOD_LABELS[method] for method in METHOD_ORDER], rotation=35, ha="right", fontsize=8)
        axis.set_ylim(0, 100)
    axes[0].set_ylabel("Risk-weighted mean assigned quality")
    figure.savefig(RESULTS_DIR / "m5d_risk_weighted_quality_allocation.png", dpi=160)
    plt.close(figure)


def _plot_reconstructions(rows: list[dict[str, str]]) -> None:
    source_rgb, _metadata, combined_mask, _polygons, regions = load_fixed_evaluation_inputs()
    high = np.asarray(regions.high_risk.values, dtype=np.uint8).reshape((120, 160))
    for budget, _target in DEVELOPMENT_BUDGETS:
        figure, axes = plt.subplots(1, 5, figsize=(14, 3.2), constrained_layout=True)
        images = [("Source", Image.fromarray(source_rgb, mode="RGB"))] + [(METHOD_LABELS[method], Image.open(M5D_DECODED_DIR / budget / f"{method}.png").convert("RGB")) for method in METHOD_ORDER]
        for axis, (label, image) in zip(axes, images):
            axis.imshow(image)
            axis.contour(high, levels=[0.5], colors=["cyan"], linewidths=0.55)
            axis.set_title(label)
            axis.set_axis_off()
        figure.suptitle(f"M5D {budget} fixed-budget reconstructions; cyan = high-risk reference")
        figure.savefig(RESULTS_DIR / f"m5d_{budget}_reconstructions.png", dpi=160)
        plt.close(figure)


def main() -> int:
    plot(load_rows())
    print("m5d_single_frame_plots: complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
