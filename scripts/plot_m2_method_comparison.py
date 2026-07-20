"""Render the curated M2 ADE comparison directly from its public summary CSV.

The script deliberately draws only category/horizon combinations present in the
CSV.  It never fills absent stable or transition results with estimates.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = {
    "method",
    "horizon_s",
    "category",
    "window_count",
    "ade_mean_m",
    "source_artifact",
}
METHOD_LABELS = {
    "state_only": "State-only",
    "command_conditioned": "Command-conditioned",
}
METHOD_COLORS = {
    "state_only": "#4C78A8",
    "command_conditioned": "#F58518",
}


def read_summary(path: Path) -> list[dict[str, object]]:
    """Load and validate a compact, meter-valued M2 ADE summary."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("M2 summary CSV has no header")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"M2 summary CSV is missing columns: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("M2 summary CSV contains no rows")

    parsed: list[dict[str, object]] = []
    seen: set[tuple[str, str, float]] = set()
    for index, row in enumerate(rows, start=2):
        method = row["method"].strip()
        if method not in METHOD_LABELS:
            raise ValueError(f"row {index}: unsupported method {method!r}")
        category = row["category"].strip()
        if not category:
            raise ValueError(f"row {index}: category is empty")
        try:
            horizon = float(row["horizon_s"])
            ade = float(row["ade_mean_m"])
            windows = int(row["window_count"])
        except ValueError as exc:
            raise ValueError(f"row {index}: invalid numeric value") from exc
        if not (math.isfinite(horizon) and horizon > 0):
            raise ValueError(f"row {index}: horizon_s must be finite and positive")
        if not (math.isfinite(ade) and ade > 0):
            raise ValueError(f"row {index}: ade_mean_m must be finite and non-zero for log plotting")
        if windows <= 0:
            raise ValueError(f"row {index}: window_count must be positive")
        key = (method, category, horizon)
        if key in seen:
            raise ValueError(f"row {index}: duplicate method/category/horizon key {key}")
        seen.add(key)
        parsed.append({"method": method, "category": category, "horizon": horizon, "ade": ade})

    grouped: dict[tuple[str, float], set[str]] = defaultdict(set)
    for row in parsed:
        grouped[(str(row["category"]), float(row["horizon"]))].add(str(row["method"]))
    incomplete = [key for key, methods in grouped.items() if set(METHOD_LABELS) != methods]
    if incomplete:
        raise ValueError(f"M2 comparison requires both methods for each category/horizon: {incomplete}")
    return parsed


def _category_label(category: str) -> str:
    return {"all_stable": "Stable windows", "all_transition": "Transition windows"}.get(
        category, category.replace("_", " ").title()
    )


def _group_rows(rows: Iterable[dict[str, object]]) -> dict[str, dict[float, dict[str, float]]]:
    grouped: dict[str, dict[float, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        grouped[str(row["category"])][float(row["horizon"])][str(row["method"])] = float(row["ade"])
    return grouped


def _annotate(ax, x: float, value: float) -> None:
    ax.annotate(
        f"{value:.2e}",
        (x, value),
        xytext=(0, 5),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=8,
    )


def write_figures(rows: list[dict[str, object]], output_dir: Path) -> list[Path]:
    """Write log-scale ADE and factor figures as PNG (300 dpi) and SVG."""
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped = _group_rows(rows)
    categories = sorted(grouped, key=lambda value: (value != "all_stable", value))
    figure, axes = plt.subplots(1, len(categories), figsize=(5.1 * len(categories), 4.8), squeeze=False, constrained_layout=True)
    axes_list = list(axes[0])
    for axis, category in zip(axes_list, categories):
        horizons = sorted(grouped[category])
        for horizon_index, horizon in enumerate(horizons):
            for method_index, method in enumerate(METHOD_LABELS):
                value = grouped[category][horizon][method]
                x = horizon_index + (method_index - 0.5) * 0.34
                axis.bar(x, value, width=0.30, color=METHOD_COLORS[method])
                _annotate(axis, x, value)
        axis.set_title(_category_label(category), fontsize=12)
        axis.set_xticks(range(len(horizons)), [f"{horizon:.1f} s" for horizon in horizons])
        axis.set_xlabel("Prediction horizon")
        axis.set_yscale("log")
        axis.grid(axis="y", which="both", alpha=0.28)
    axes_list[0].set_ylabel("Mean ADE (m, log scale)")
    figure.suptitle("Trajectory Prediction ADE by Window Type and Horizon", fontsize=14)
    figure.legend(
        handles=[Patch(facecolor=METHOD_COLORS[method], label=label) for method, label in METHOD_LABELS.items()],
        loc="outside lower center",
        ncols=2,
    )
    main_png = output_dir / "m2_method_comparison_ade.png"
    main_svg = output_dir / "m2_method_comparison_ade.svg"
    figure.savefig(main_png, dpi=300, bbox_inches="tight")
    figure.savefig(main_svg, bbox_inches="tight")
    plt.close(figure)

    factor_figure, factor_axes = plt.subplots(1, len(categories), figsize=(5.1 * len(categories), 4.5), squeeze=False, constrained_layout=True)
    for axis, category in zip(factor_axes[0], categories):
        horizons = sorted(grouped[category])
        factors = [grouped[category][horizon]["state_only"] / grouped[category][horizon]["command_conditioned"] for horizon in horizons]
        bars = axis.bar(range(len(horizons)), factors, color="#54A24B", width=0.55)
        axis.bar_label(bars, labels=[f"{value:.1f}×" for value in factors], padding=3, fontsize=9)
        axis.set_title(_category_label(category), fontsize=12)
        axis.set_xticks(range(len(horizons)), [f"{horizon:.1f} s" for horizon in horizons])
        axis.set_xlabel("Prediction horizon")
        axis.grid(axis="y", alpha=0.28)
    factor_axes[0][0].set_ylabel("State-only ADE / Command-conditioned ADE")
    factor_figure.suptitle("M2 ADE improvement factor", fontsize=14)
    factor_png = output_dir / "m2_method_improvement_factor.png"
    factor_svg = output_dir / "m2_method_improvement_factor.svg"
    factor_figure.savefig(factor_png, dpi=300, bbox_inches="tight")
    factor_figure.savefig(factor_svg, bbox_inches="tight")
    plt.close(factor_figure)
    return [main_png, main_svg, factor_png, factor_svg]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "docs/results/m2_in_place_summary_metrics.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "docs/assets")
    args = parser.parse_args()
    outputs = write_figures(read_summary(args.input), args.output_dir)
    print("M2 figures generated from validated CSV:")
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
