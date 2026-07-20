"""Create deterministic episode-level M5E-E diagnostic figures."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_statistical_analysis_common import (
    BASELINE_METHODS,
    FORMAL_BUDGET_LABELS,
    PRIMARY_BUDGETS,
    SCENARIO_IDS,
    analysis_paths,
)


METHOD_LABELS = {
    "uniform": "Uniform",
    "center_roi": "Center ROI",
    "object_roi": "Object ROI",
}
BUDGET_LABELS = {
    "severe": "Severe",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}
COLORS = {
    "uniform": "#2f6f9f",
    "center_roi": "#b5523b",
    "object_roi": "#27845b",
}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        dpi=170,
        bbox_inches="tight",
        metadata={"Software": "risk-aware-visual-communication M5E-E"},
    )
    plt.close(fig)


def _zero_line(axis: plt.Axes) -> None:
    axis.axvline(0.0, color="#333333", linewidth=0.8, linestyle="--", zorder=0)


def _primary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row["analysis_role"] == "primary"]


def _forest(bootstrap: list[dict[str, str]], path: Path) -> None:
    rows = _primary_rows(bootstrap)
    labels = [
        f"{BUDGET_LABELS[row['budget_label']]}: Risk - {METHOD_LABELS[row['baseline_method']]}"
        for row in rows
    ]
    means = np.asarray([float(row["observed_equal_scenario_mean_difference"]) for row in rows])
    lower = np.asarray([float(row["ci_lower_95"]) for row in rows])
    upper = np.asarray([float(row["ci_upper_95"]) for row in rows])
    y = np.arange(len(rows))
    fig, axis = plt.subplots(figsize=(8.4, 4.8), constrained_layout=True)
    for index, row in enumerate(rows):
        axis.errorbar(
            means[index], y[index],
            xerr=[[means[index] - lower[index]], [upper[index] - means[index]]],
            fmt="o", color=COLORS[row["baseline_method"]], capsize=3,
        )
    _zero_line(axis)
    axis.set_yticks(y, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Episode-level RW-PSNR difference (dB)")
    axis.set_title("Primary paired effects (episode resampling unit)")
    axis.grid(axis="x", alpha=0.2)
    _save(fig, path)


def _bootstrap_ci(bootstrap: list[dict[str, str]], path: Path) -> None:
    rows = _primary_rows(bootstrap)
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2), sharex=True, constrained_layout=True)
    for axis, budget in zip(axes, PRIMARY_BUDGETS):
        subset = [row for row in rows if row["budget_label"] == budget]
        for index, row in enumerate(subset):
            mean = float(row["observed_equal_scenario_mean_difference"])
            lower = float(row["ci_lower_95"])
            upper = float(row["ci_upper_95"])
            axis.errorbar(
                mean, index, xerr=[[mean - lower], [upper - mean]],
                fmt="o", color=COLORS[row["baseline_method"]], capsize=3,
            )
        _zero_line(axis)
        axis.set_yticks(range(3), [METHOD_LABELS[row["baseline_method"]] for row in subset])
        axis.set_title(BUDGET_LABELS[budget])
        axis.set_xlabel("Risk-minus-baseline RW-PSNR (dB)")
        axis.grid(axis="x", alpha=0.2)
    fig.suptitle("10,000-replicate stratified bootstrap CI (episode unit)")
    _save(fig, path)


def _scenario_heatmap(scenarios: list[dict[str, str]], path: Path) -> None:
    rows = [row for row in scenarios if row["metric_name"] == "risk_weighted_psnr_db"]
    values = np.asarray([abs(float(row["paired_mean_difference"])) for row in rows])
    limit = max(float(np.max(values)), 1e-9)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 5.0), constrained_layout=True)
    image = None
    for axis, baseline in zip(axes, BASELINE_METHODS):
        matrix = np.zeros((len(SCENARIO_IDS), len(FORMAL_BUDGET_LABELS)))
        for i, scenario in enumerate(SCENARIO_IDS):
            for j, budget in enumerate(FORMAL_BUDGET_LABELS):
                row = next(
                    item for item in rows
                    if item["scenario_id"] == scenario
                    and item["budget_label"] == budget
                    and item["baseline_method"] == baseline
                )
                matrix[i, j] = float(row["paired_mean_difference"])
        image = axis.imshow(matrix, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
        axis.set_xticks(range(4), [BUDGET_LABELS[item] for item in FORMAL_BUDGET_LABELS], rotation=35, ha="right")
        axis.set_yticks(range(8), SCENARIO_IDS)
        axis.set_title(f"Risk - {METHOD_LABELS[baseline]}")
    fig.colorbar(image, ax=axes, label="Episode-level RW-PSNR difference (dB)", shrink=0.8)
    fig.suptitle("Exploratory scenario x budget effects (episode means)")
    _save(fig, path)


def _paired_scatter(inputs: list[dict[str, str]], path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 7.2), constrained_layout=True)
    for row_index, budget in enumerate(PRIMARY_BUDGETS):
        for column, baseline in enumerate(BASELINE_METHODS):
            axis = axes[row_index, column]
            rows = [
                row for row in inputs
                if row["budget_label"] == budget and row["baseline_method"] == baseline
            ]
            x = np.asarray([float(row["risk_weighted_baseline_value"]) for row in rows])
            y = np.asarray([float(row["risk_weighted_risk_value"]) for row in rows])
            minimum = min(float(np.min(x)), float(np.min(y)))
            maximum = max(float(np.max(x)), float(np.max(y)))
            axis.scatter(x, y, s=14, alpha=0.7, color=COLORS[baseline])
            axis.plot([minimum, maximum], [minimum, maximum], color="#333333", linestyle="--", linewidth=0.8)
            axis.set_title(f"{BUDGET_LABELS[budget]} / {METHOD_LABELS[baseline]}")
            axis.set_xlabel("Baseline episode RW-PSNR (dB)")
            axis.set_ylabel("Risk ROI episode RW-PSNR (dB)")
            axis.grid(alpha=0.15)
    fig.suptitle("Primary paired episode-level scatter")
    _save(fig, path)


def _win_tie_loss(wins: list[dict[str, str]], path: Path) -> None:
    rows = [
        row for row in wins
        if row["scope"] == "overall" and row["analysis_role"] == "primary"
    ]
    labels = [
        f"{BUDGET_LABELS[row['budget_label']]} / {METHOD_LABELS[row['baseline_method']]}"
        for row in rows
    ]
    win_values = np.asarray([int(row["wins"]) for row in rows])
    tie_values = np.asarray([int(row["ties"]) for row in rows])
    loss_values = np.asarray([int(row["losses"]) for row in rows])
    y = np.arange(len(rows))
    fig, axis = plt.subplots(figsize=(8.8, 4.8), constrained_layout=True)
    axis.barh(y, win_values, color="#27845b", label="Win")
    axis.barh(y, tie_values, left=win_values, color="#8b8b8b", label="Tie")
    axis.barh(y, loss_values, left=win_values + tie_values, color="#b5523b", label="Loss")
    axis.set_yticks(y, labels)
    axis.invert_yaxis()
    axis.set_xlim(0, 64)
    axis.set_xlabel("Episodes")
    axis.set_title("Primary episode win/tie/loss counts")
    axis.legend(frameon=False, ncols=3)
    _save(fig, path)


def _tradeoff(inputs: list[dict[str, str]], y_field: str, y_label: str, title: str, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.5), constrained_layout=True)
    for axis, budget in zip(axes, PRIMARY_BUDGETS):
        for baseline in BASELINE_METHODS:
            rows = [
                row for row in inputs
                if row["budget_label"] == budget and row["baseline_method"] == baseline
            ]
            axis.scatter(
                [float(row["risk_weighted_difference"]) for row in rows],
                [float(row[y_field]) for row in rows],
                s=13, alpha=0.6, color=COLORS[baseline], label=METHOD_LABELS[baseline],
            )
        axis.axhline(0.0, color="#333333", linewidth=0.8, linestyle="--")
        axis.axvline(0.0, color="#333333", linewidth=0.8, linestyle="--")
        axis.set_title(BUDGET_LABELS[budget])
        axis.set_xlabel("RW-PSNR difference (dB)")
        axis.set_ylabel(y_label)
        axis.grid(alpha=0.15)
    axes[0].legend(frameon=False)
    fig.suptitle(title + " (episode means, diagnostic)")
    _save(fig, path)


def _selected_scenarios(
    scenarios: list[dict[str, str]],
    selected: tuple[str, ...],
    title: str,
    path: Path,
) -> None:
    rows = [
        row for row in scenarios
        if row["metric_name"] == "risk_weighted_psnr_db"
        and row["budget_label"] in PRIMARY_BUDGETS
        and row["scenario_id"] in selected
    ]
    fig, axes = plt.subplots(1, len(selected), figsize=(4.2 * len(selected), 4.4), sharey=True, constrained_layout=True)
    axes = np.atleast_1d(axes)
    width = 0.12
    for axis, scenario in zip(axes, selected):
        positions = np.arange(len(BASELINE_METHODS))
        for offset, budget in enumerate(PRIMARY_BUDGETS):
            values = [
                float(next(
                    row["paired_mean_difference"] for row in rows
                    if row["scenario_id"] == scenario
                    and row["budget_label"] == budget
                    and row["baseline_method"] == baseline
                ))
                for baseline in BASELINE_METHODS
            ]
            axis.bar(
                positions + (offset - 0.5) * width,
                values, width=width,
                label=BUDGET_LABELS[budget],
                color="#2f6f9f" if budget == "severe" else "#b5523b",
            )
        axis.axhline(0.0, color="#333333", linewidth=0.8, linestyle="--")
        axis.set_xticks(positions, [METHOD_LABELS[item] for item in BASELINE_METHODS], rotation=35, ha="right")
        axis.set_title(scenario)
        axis.set_ylabel("Risk-minus-baseline RW-PSNR (dB)")
        axis.grid(axis="y", alpha=0.15)
    axes[0].legend(frameon=False)
    fig.suptitle(title + " (episode means, exploratory)")
    _save(fig, path)


def write_figures(
    analysis_root: Path,
    figure_root: Path,
    *,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    paths = analysis_paths(analysis_root)
    bootstrap = _read(paths["bootstrap_results"])
    scenarios = _read(paths["scenario_diagnostics"])
    wins = _read(paths["win_tie_loss"])
    inputs = _read(paths["figure_inputs"])
    specifications = [
        ("primary_paired_effect_forest.png", "primary", _forest, (bootstrap,)),
        ("primary_bootstrap_ci.png", "primary", _bootstrap_ci, (bootstrap,)),
        ("scenario_budget_effect_heatmap.png", "exploratory", _scenario_heatmap, (scenarios,)),
        ("episode_paired_scatter.png", "primary", _paired_scatter, (inputs,)),
        ("primary_win_tie_loss.png", "primary", _win_tie_loss, (wins,)),
        (
            "rw_vs_full_psnr_tradeoff.png", "diagnostic", _tradeoff,
            (inputs, "full_psnr_difference", "Full-frame PSNR difference (dB)", "RW-PSNR vs full-frame trade-off"),
        ),
        (
            "background_quality_tradeoff.png", "diagnostic", _tradeoff,
            (inputs, "background_psnr_difference", "Background PSNR difference (dB)", "RW-PSNR vs background-quality trade-off"),
        ),
        (
            "s2_s5_s6_diagnostics.png", "exploratory", _selected_scenarios,
            (scenarios, ("S2", "S5", "S6"), "S2/S5/S6 scenario diagnostics"),
        ),
        (
            "s8_low_risk_control.png", "exploratory", _selected_scenarios,
            (scenarios, ("S8",), "S8 low-risk control"),
        ),
    ]
    figure_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for filename, role, function, arguments in specifications:
        path = figure_root / filename
        if path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite figure: {path}")
        function(*arguments, path)
        entries.append(
            {
                "filename": filename,
                "role": role,
                "sample_unit": "episode",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "protocol_version": "m5e-e-episode-statistics-v1",
        "figure_count": len(entries),
        "method_order": list(BASELINE_METHODS),
        "budget_order": list(FORMAL_BUDGET_LABELS),
        "scenario_order": list(SCENARIO_IDS),
        "sample_unit": "episode",
        "figures": entries,
    }
    paths["figure_manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return entries
