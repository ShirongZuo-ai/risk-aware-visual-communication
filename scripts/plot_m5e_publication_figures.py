"""Render curated, publication-quality M5E-E figures without altering formal results."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METHOD_LABELS = {
    "uniform": "Uniform",
    "center_roi": "Center ROI",
    "object_roi": "Object ROI",
    "risk_roi": "Risk ROI",
}
COMPARATOR_COLORS = {
    "uniform": "#2166AC",
    "center_roi": "#7B3294",
    "object_roi": "#008837",
}
BUDGET_LABELS = {"severe": "Severe", "low": "Low", "medium": "Medium", "high": "High"}
PRIMARY_BUDGETS = ("severe", "low")
BASELINES = ("uniform", "center_roi", "object_roi")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _normalize_svg(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text("\n".join(line.rstrip() for line in text.splitlines()) + "\n", encoding="utf-8")


def _save_pair(figure: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    svg = output_dir / f"{stem}.svg"
    figure.savefig(png, dpi=300, bbox_inches="tight", metadata={"Software": "risk-aware-visual-communication M5E public figures"})
    figure.savefig(svg, bbox_inches="tight")
    _normalize_svg(svg)
    plt.close(figure)
    return png, svg


def load_snapshot(analysis_root: Path) -> dict[str, Any]:
    """Load only the frozen analysis outputs used by the public figures."""
    bootstrap = [row for row in _read_csv(analysis_root / "bootstrap_results.csv") if row["analysis_role"] == "primary"]
    scenarios = [
        row
        for row in _read_csv(analysis_root / "scenario_diagnostics.csv")
        if row["metric_name"] == "risk_weighted_psnr_db"
    ]
    inputs = _read_csv(analysis_root / "figure_inputs.csv")
    if len(bootstrap) != 6 or len(scenarios) != 96 or len(inputs) != 384:
        raise ValueError("unexpected frozen M5E-E publication input coverage")
    if {row["budget_label"] for row in bootstrap} != set(PRIMARY_BUDGETS):
        raise ValueError("primary budget coverage changed")
    if {row["baseline_method"] for row in bootstrap} != set(BASELINES):
        raise ValueError("primary comparator coverage changed")
    return {
        "statistical_unit": "episode",
        "methods": list(METHOD_LABELS.values()),
        "primary_bootstrap": bootstrap,
        "scenario_effects": scenarios,
        "tradeoff_inputs": inputs,
    }


def write_snapshot(snapshot: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _primary_rows(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    index = {(row["budget_label"], row["baseline_method"]): row for row in snapshot["primary_bootstrap"]}
    return [index[(budget, baseline)] for budget in PRIMARY_BUDGETS for baseline in BASELINES]


def plot_primary_forest(snapshot: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    rows = _primary_rows(snapshot)
    figure, axis = plt.subplots(figsize=(9.0, 5.3), constrained_layout=True)
    positions = np.arange(len(rows))
    for index, row in enumerate(rows):
        mean = float(row["observed_equal_scenario_mean_difference"])
        lower = float(row["ci_lower_95"])
        upper = float(row["ci_upper_95"])
        axis.errorbar(mean, positions[index], xerr=[[mean - lower], [upper - mean]], fmt="o", markersize=7,
                      color=COMPARATOR_COLORS[row["baseline_method"]], capsize=4, linewidth=1.7)
        axis.annotate(f"{mean:+.3f}", (mean, positions[index]), xytext=(0, 8), textcoords="offset points",
                      ha="center", fontsize=8)
    axis.axvline(0.0, color="#222222", linewidth=1.0, linestyle="--", zorder=0)
    axis.set_yticks(positions, [f"{BUDGET_LABELS[row['budget_label']]} / {METHOD_LABELS[row['baseline_method']]}" for row in rows])
    axis.invert_yaxis()
    axis.set_xlabel("Risk ROI − comparator RW-PSNR (dB; positive favors Risk ROI)")
    axis.set_title("Risk ROI paired difference by comparator and budget")
    axis.grid(axis="x", alpha=0.22)
    axis.text(0.01, 0.02, "Points: equal-scenario episode means; bars: 95% bootstrap CI (n = 64 episodes)",
              transform=axis.transAxes, fontsize=8, va="bottom")
    return _save_pair(figure, output_dir, "m5e_primary_paired_effects")


def plot_budget_effects(snapshot: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    rows = _primary_rows(snapshot)
    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.7), sharey=True, constrained_layout=True)
    for axis, budget in zip(axes, PRIMARY_BUDGETS):
        subset = [row for row in rows if row["budget_label"] == budget]
        for position, row in enumerate(subset):
            mean = float(row["observed_equal_scenario_mean_difference"])
            lower = float(row["ci_lower_95"]); upper = float(row["ci_upper_95"])
            axis.errorbar(position, mean, yerr=[[mean - lower], [upper - mean]], fmt="o", markersize=7,
                          color=COMPARATOR_COLORS[row["baseline_method"]], capsize=4, linewidth=1.7)
            axis.annotate(f"{mean:+.3f}", (position, mean), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
        axis.axhline(0.0, color="#222222", linewidth=1.0, linestyle="--")
        axis.set_xticks(range(3), [METHOD_LABELS[row["baseline_method"]] for row in subset])
        axis.set_title(BUDGET_LABELS[budget])
        axis.grid(axis="y", alpha=0.22)
    axes[0].set_ylabel("Risk ROI − comparator RW-PSNR (dB)")
    figure.suptitle("Method performance by communication budget\nEpisode means with 95% bootstrap CI (positive favors Risk ROI)")
    return _save_pair(figure, output_dir, "m5e_budget_paired_effects")


def plot_scene_effects(snapshot: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    rows = snapshot["scenario_effects"]
    limit = max(abs(float(row["paired_mean_difference"])) for row in rows)
    figure, axes = plt.subplots(1, 3, figsize=(13.5, 5.8), constrained_layout=True)
    image = None
    for axis, baseline in zip(axes, BASELINES):
        matrix = np.zeros((8, 4))
        for scene_index in range(8):
            for budget_index, budget in enumerate(("severe", "low", "medium", "high")):
                row = next(item for item in rows if item["scenario_id"] == f"S{scene_index + 1}" and item["budget_label"] == budget and item["baseline_method"] == baseline)
                matrix[scene_index, budget_index] = float(row["paired_mean_difference"])
        image = axis.imshow(matrix, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
        for (row_index, column_index), value in np.ndenumerate(matrix):
            axis.text(column_index, row_index, f"{value:+.1f}", ha="center", va="center", fontsize=8,
                      color="white" if abs(value) > 0.55 * limit else "#161616")
        axis.set_xticks(range(4), [BUDGET_LABELS[item] for item in ("severe", "low", "medium", "high")], rotation=25, ha="right")
        axis.set_yticks(range(8), [f"S{index}" for index in range(1, 9)])
        axis.set_title(f"Risk ROI − {METHOD_LABELS[baseline]}")
    figure.colorbar(image, ax=axes, label="Episode-level RW-PSNR difference (dB)", shrink=0.83)
    figure.suptitle("All-scene heterogeneity by communication budget\nPositive values favor Risk ROI; no scene is removed or down-weighted")
    return _save_pair(figure, output_dir, "m5e_scene_budget_effects")


def plot_quality_tradeoff(snapshot: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    for axis, budget in zip(axes, PRIMARY_BUDGETS):
        for baseline in BASELINES:
            rows = [row for row in snapshot["tradeoff_inputs"] if row["budget_label"] == budget and row["baseline_method"] == baseline]
            axis.scatter([float(row["risk_weighted_difference"]) for row in rows], [float(row["full_psnr_difference"]) for row in rows],
                         s=24, alpha=0.72, color=COMPARATOR_COLORS[baseline], label=METHOD_LABELS[baseline])
        axis.axhline(0.0, color="#222222", linewidth=1.0, linestyle="--")
        axis.axvline(0.0, color="#222222", linewidth=1.0, linestyle="--")
        axis.set_title(BUDGET_LABELS[budget])
        axis.set_xlabel("Risk-weighted PSNR difference (dB)")
        axis.grid(alpha=0.20)
    axes[0].set_ylabel("Full-frame PSNR difference (dB)")
    axes[0].legend(frameon=False, title="Comparator")
    figure.suptitle("Risk-region benefit versus full-frame quality cost\nEpisode means; positive x favors Risk ROI")
    return _save_pair(figure, output_dir, "m5e_quality_tradeoff")


def write_publication_figures(analysis_root: Path, output_dir: Path, snapshot_path: Path) -> list[Path]:
    snapshot = load_snapshot(analysis_root)
    write_snapshot(snapshot, snapshot_path)
    paths: list[Path] = []
    for function in (plot_primary_forest, plot_budget_effects, plot_scene_effects, plot_quality_tradeoff):
        paths.extend(function(snapshot, output_dir))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=PROJECT_ROOT / "data/m5e_formal/statistical_analysis")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "docs/assets")
    parser.add_argument("--snapshot", type=Path, default=PROJECT_ROOT / "docs/results/m5e_publication_figure_snapshot.json")
    args = parser.parse_args()
    outputs = write_publication_figures(args.analysis_root, args.output_dir, args.snapshot)
    print(f"Generated {len(outputs) // 2} M5E public figures (PNG + SVG).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
