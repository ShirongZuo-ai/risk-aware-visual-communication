"""Create allocation diagnostics only; figures do not choose a best method."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5c_allocation_common import DEVELOPMENT_BUDGETS, M5C_CSV_PATH  # noqa: E402


RESULTS_DIR = PROJECT_ROOT / "results" / "m5_compression"


def load_rows(path: Path = M5C_CSV_PATH) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _grid(values):
    return [values[row * 8 : (row + 1) * 8] for row in range(6)]


def plot(rows: list[dict[str, str]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    by_key = {(row["method"], row["budget_id"]): row for row in rows}
    _plot_scores(by_key)
    _plot_qualities(by_key)
    _plot_utilization(by_key)


def _plot_scores(by_key) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.7), constrained_layout=True)
    for axis, method in zip(axes, ("center_roi", "object_roi", "risk_roi")):
        row = by_key[(method, "severe")]
        image = axis.imshow(_grid(json.loads(row["tile_scores_json"])), vmin=0.0, vmax=1.0, cmap="viridis", interpolation="nearest")
        axis.set_title(method.replace("_", " ").title())
        axis.set_xlabel("Tile column")
        axis.set_ylabel("Tile row")
        axis.set_xticks(range(8))
        axis.set_yticks(range(6))
    figure.colorbar(image, ax=axes, label="Tile score [0,1]")
    figure.savefig(RESULTS_DIR / "m5c_score_maps.png", dpi=160)
    plt.close(figure)


def _plot_qualities(by_key) -> None:
    methods = ("uniform", "center_roi", "object_roi", "risk_roi")
    figure, axes = plt.subplots(4, 4, figsize=(12, 11), constrained_layout=True)
    image = None
    for row_index, (budget_id, target) in enumerate(DEVELOPMENT_BUDGETS):
        for column, method in enumerate(methods):
            axis = axes[row_index][column]
            row = by_key[(method, budget_id)]
            image = axis.imshow(_grid(json.loads(row["tile_qualities_json"])), vmin=1, vmax=95, cmap="plasma", interpolation="nearest")
            axis.set_title(f"{method.replace('_', ' ')}\n{target}/{row['actual_total_bytes']} B", fontsize=8)
            axis.set_xticks(range(8))
            axis.set_yticks(range(6))
            if column == 0:
                axis.set_ylabel(f"{budget_id}\nrow")
    figure.colorbar(image, ax=axes.ravel().tolist(), label="JPEG tile quality [1,95]")
    figure.savefig(RESULTS_DIR / "m5c_quality_maps.png", dpi=160)
    plt.close(figure)


def _plot_utilization(by_key) -> None:
    methods = ("uniform", "center_roi", "object_roi", "risk_roi")
    figure, axis = plt.subplots(figsize=(8.2, 4.3), constrained_layout=True)
    offsets = (-0.27, -0.09, 0.09, 0.27)
    for offset, method in zip(offsets, methods):
        values = [float(by_key[(method, budget_id)]["utilization"]) for budget_id, _ in DEVELOPMENT_BUDGETS]
        bars = axis.bar([index + offset for index in range(4)], values, 0.17, label=method.replace("_", " "))
        axis.bar_label(bars, labels=[f"{value:.3f}" for value in values], fontsize=7, padding=2)
    axis.set_xticks(range(4), [f"{budget_id}\n{target} B" for budget_id, target in DEVELOPMENT_BUDGETS])
    axis.set_ylim(0.9, 1.01)
    axis.set_ylabel("Actual bytes / target bytes")
    axis.set_title("M5C budget utilization")
    axis.legend(ncol=2)
    figure.savefig(RESULTS_DIR / "m5c_budget_utilization.png", dpi=160)
    plt.close(figure)


def main() -> int:
    plot(load_rows())
    print("m5c_allocation_maps: complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
