"""Create descriptive M5E-D formal diagnostic plots without statistical claims."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw

from scripts.m5e_dataset_common import resolve_output_root
from scripts.m5e_formal_evaluation_common import FORMAL_BUDGET_LABELS, formal_paths, read_csv_rows
from scripts.m5e_calibration_common import METHOD_ORDER


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/m5e_formal")
    parser.add_argument("--results-root", default="results/m5_compression/m5e_formal")
    return parser


def _float(value: str) -> float | None:
    if value == "undefined":
        return None
    if value == "inf":
        return float("inf")
    return float(value)


def _save_boxplot(rows: list[dict[str, str]], metric: str, destination: Path) -> None:
    import matplotlib.pyplot as plt

    labels = []
    data = []
    for method in METHOD_ORDER:
        for budget in FORMAL_BUDGET_LABELS:
            values = [_float(row[metric]) for row in rows if row["method"] == method and row["budget_label"] == budget]
            values = [value for value in values if value is not None and value != float("inf")]
            labels.append(f"{method}\n{budget}")
            data.append(values)
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.boxplot(data, tick_labels=labels, showfliers=False)
    ax.set_title(f"M5E-D descriptive {metric}; formal statistics deferred to M5E-E")
    ax.set_ylabel(metric)
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def _save_utilization_heatmap(rows: list[dict[str, str]], destination: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    matrix = []
    xlabels = list(FORMAL_BUDGET_LABELS)
    ylabels = list(METHOD_ORDER)
    for method in ylabels:
        matrix.append([
            sum(float(row["utilization"]) for row in rows if row["method"] == method and row["budget_label"] == budget)
            / sum(1 for row in rows if row["method"] == method and row["budget_label"] == budget)
            for budget in xlabels
        ])
    values = np.asarray(matrix)
    fig, ax = plt.subplots(figsize=(7, 4))
    image = ax.imshow(values, vmin=0.0, vmax=1.0, cmap="viridis")
    ax.set_xticks(range(len(xlabels)), xlabels)
    ax.set_yticks(range(len(ylabels)), ylabels)
    ax.set_title("M5E-D mean byte utilization; descriptive only")
    for row_index, row_values in enumerate(values):
        for column_index, value in enumerate(row_values):
            ax.text(column_index, row_index, f"{value:.3f}", ha="center", va="center", color="white" if value < 0.65 else "black", fontsize=8)
    fig.colorbar(image, ax=ax, label="actual / target")
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def _save_scenario_summary(rows: list[dict[str, str]], destination: Path) -> None:
    import matplotlib.pyplot as plt

    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        value = _float(row["risk_weighted_psnr_db"])
        if value is not None and value != float("inf"):
            grouped[(row["scenario_id"], row["method"])].append(value)
    scenarios = sorted({row["scenario_id"] for row in rows})
    fig, axes = plt.subplots(2, 4, figsize=(14, 6), sharey=True)
    for ax, scenario in zip(axes.ravel(), scenarios):
        means = []
        for method in METHOD_ORDER:
            values = grouped[(scenario, method)]
            means.append(sum(values) / len(values))
        ax.bar(range(len(METHOD_ORDER)), means, color=["#4c78a8", "#f58518", "#54a24b", "#e45756"])
        ax.set_title(scenario)
        ax.set_xticks(range(len(METHOD_ORDER)), METHOD_ORDER, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("mean RW-PSNR dB")
    fig.suptitle("M5E-D scenario summaries are descriptive; inference deferred to M5E-E")
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def _save_montage(rows: list[dict[str, str]], destination: Path) -> None:
    selected = []
    for scenario in ("S2", "S5", "S6", "S7"):
        matches = [
            row for row in rows
            if row["scenario_id"] == scenario
            and row["method"] in ("uniform", "risk_roi")
            and row["budget_label"] == "severe"
            and row["snapshot_index"] == "2"
        ]
        if len(matches) >= 2:
            selected.extend(sorted(matches, key=lambda row: row["method"]))
    if not selected:
        return
    cell_w, cell_h = 160, 145
    montage = Image.new("RGB", (cell_w * 2, cell_h * (len(selected) // 2)), "white")
    draw = ImageDraw.Draw(montage)
    for index, row in enumerate(selected):
        path = PROJECT_ROOT / row["decoded_png_path"]
        if not path.exists():
            continue
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        x = (index % 2) * cell_w
        y = (index // 2) * cell_h
        montage.paste(image, (x, y))
        draw.text((x + 4, y + 123), f"{row['scenario_id']} {row['method']} severe", fill=(0, 0, 0))
    destination.parent.mkdir(parents=True, exist_ok=True)
    montage.save(destination)


def main() -> int:
    args = _parser().parse_args()
    output_root = resolve_output_root(args.output_root)
    results_root = resolve_output_root(args.results_root)
    rows = read_csv_rows(formal_paths(output_root)["metrics_csv"])
    _save_utilization_heatmap(rows, results_root / "m5e_d_byte_utilization_heatmap.png")
    _save_boxplot(rows, "full_psnr_db", results_root / "m5e_d_full_psnr_boxplot.png")
    _save_boxplot(rows, "risk_weighted_psnr_db", results_root / "m5e_d_risk_weighted_psnr_boxplot.png")
    _save_scenario_summary(rows, results_root / "m5e_d_scenario_method_summary.png")
    _save_montage(rows, results_root / "m5e_d_representative_reconstructions.png")
    print(f"M5E-D descriptive diagnostics written to {results_root.relative_to(PROJECT_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
