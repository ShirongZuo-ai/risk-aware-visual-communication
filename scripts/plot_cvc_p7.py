"""Reproducible static figures for CVC-P7 mechanistic evidence.

Chart contract: standalone PNGs; paired bars for historical signed deltas,
grouped point/line comparisons for category outcomes, faceted labeled dots for
small-n feature distributions, and a per-cell event timeline.  Blue/orange plus
neutral styling is used with marker/position distinctions so color is not the
only channel.  All titles are descriptive and subtitles carry n/unit context.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "results" / "cvc_p7_analysis" / "mechanistic_analysis.json"
OUT = ROOT / "results" / "cvc_p7_analysis" / "figures"
BLUE = "#3973AC"
ORANGE = "#D17A22"
GOLD = "#B89A2E"
INK = "#263238"
GREY = "#8A9499"
LIGHT = "#D8DEE2"


def style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=LIGHT, linewidth=.7, alpha=.7)
    ax.tick_params(colors=INK)


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def historical_tradeoff(report: dict) -> None:
    rows = report["historical_p6_tradeoff"]["pairs"]
    names = [row["scenario"].replace("_", " ") for row in rows]
    y = np.arange(len(rows))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, field, title, unit in (
        (axes[0], "a1_minus_a0_progress_m", "A1 minus A0 forward progress", "m"),
        (axes[1], "a1_minus_a0_min_clearance_m", "A1 minus A0 minimum clearance", "m"),
    ):
        values = [row[field] for row in rows]
        colors = [ORANGE if not row["schedules_equal"] else GREY for row in rows]
        ax.barh(y, values, color=colors, edgecolor=INK, linewidth=.5)
        ax.axvline(0, color=INK, linewidth=.9)
        ax.set_yticks(y, names if ax is axes[0] else [])
        ax.set_xlabel(unit)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        style(ax)
    fig.suptitle("Frozen P6 paired progress and clearance deltas", x=.02, ha="left", color=INK, fontsize=14)
    fig.text(.02, .035, "Orange = schedule-different pair; grey = identical A0/A1 schedule. n=6 scenarios.", color=INK)
    fig.subplots_adjust(left=.18, right=.98, bottom=.20, top=.82, wspace=.04)
    save(fig, "p6_paired_tradeoff.png")


def category_outcomes(report: dict) -> None:
    categories = list("ABCD")
    policies = ("U0", "A0", "A1")
    markers = {"U0": "o", "A0": "s", "A1": "^"}
    colors = {"U0": GREY, "A0": BLUE, "A1": ORANGE}
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))
    for ax, metric, title, ylabel in (
        (axes[0], "mean_minimum_clearance_m", "Minimum clearance by intended category", "mean across 3 cells (m)"),
        (axes[1], "mean_forward_progress_m", "Forward progress by intended category", "mean across 3 cells (m)"),
    ):
        for policy in policies:
            values = [report["category_policy_summary"][category][policy][metric] for category in categories]
            ax.plot(categories, values, marker=markers[policy], color=colors[policy], label=policy,
                    linewidth=1.5, markersize=6)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.set_xlabel("preregistered novelty × safety category")
        ax.set_ylabel(ylabel)
        style(ax)
    axes[0].legend(frameon=False, ncol=3, loc="upper right")
    fig.suptitle("Frozen P7 navigation outcomes", x=.02, ha="left", color=INK, fontsize=14)
    fig.text(.02, .035, "A/B = intended low safety relevance; C/D = intended high. No cell crossed 0.12 m.", color=INK)
    fig.subplots_adjust(left=.09, right=.98, bottom=.20, top=.82, wspace=.18)
    save(fig, "p7_category_outcomes.png")


def feature_dots(report: dict) -> None:
    a1 = [row for row in report["episode_records"] if row["policy"] == "A1"]
    panels = (
        ("bearing_convergence_rate_s", "Bearing convergence", "normalized bearing / s"),
        ("proximity_growth_rate_s", "Proximity growth", "proximity / s"),
        ("forward_corridor_overlap", "Forward-corridor overlap", "fraction"),
        ("delta_v_m_s", "Send minus hold forward speed", "m/s"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2))
    category_color = {"A": GREY, "B": GOLD, "C": BLUE, "D": ORANGE}
    for ax, (feature, title, ylabel) in zip(axes.flat, panels):
        for index, category in enumerate("ABCD"):
            rows = [row for row in a1 if row["category"] == category]
            values = [row["spend_features"][feature] for row in rows]
            offsets = np.linspace(-.12, .12, len(values))
            ax.scatter(index + offsets, values, color=category_color[category], edgecolor=INK,
                       linewidth=.5, s=42, label=category if feature == panels[0][0] else None)
        ax.axhline(0, color=INK, linewidth=.7)
        ax.set_xticks(range(4), list("ABCD"))
        ax.set_xlabel("intended category")
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        style(ax)
    fig.suptitle("A1 sender-visible features at the frozen P6 spend", x=.02, ha="left", color=INK, fontsize=14)
    fig.text(.02, .025, "Three deterministic cells per category; dots are cells, not inferential replicates.", color=INK)
    fig.subplots_adjust(left=.09, right=.98, bottom=.14, top=.88, hspace=.45, wspace=.20)
    save(fig, "p7_a1_spend_feature_dots.png")


def timing(report: dict) -> None:
    rows = [row for row in report["episode_records"] if row["policy"] == "A1"]
    rows.sort(key=lambda row: (row["category"], row["scenario"]))
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    for index, row in enumerate(rows):
        arm = row["r1_arm_step"]
        spend = row["adaptive_step"]
        minimum = row["minimum_clearance_step"]
        if arm is not None:
            ax.scatter(arm, index, marker="o", facecolor="white", edgecolor=BLUE, s=46)
        ax.scatter(spend, index, marker="s", color=ORANGE, edgecolor=INK, linewidth=.4, s=42)
        ax.scatter(minimum, index, marker="x", color=INK, s=48)
        if arm is not None:
            ax.plot([arm, spend], [index, index], color=LIGHT, linewidth=1.2, zorder=0)
    ax.set_yticks(y, [row["scenario"].replace("p7-", "") for row in rows])
    ax.invert_yaxis()
    ax.set_xlabel("32 ms control step")
    fig.suptitle("A1 ARM, adaptive spend, and physical minimum-clearance timing", x=.20, ha="left", color=INK, fontsize=13)
    fig.text(.20, .91, "Open circle = R1 ARM; square = P6 spend; x = minimum clearance. No danger-onset marker exists.", color=INK)
    style(ax)
    fig.subplots_adjust(left=.20, right=.98, bottom=.12, top=.86)
    save(fig, "p7_a1_timing.png")


def main() -> None:
    report = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    historical_tradeoff(report)
    category_outcomes(report)
    feature_dots(report)
    timing(report)
    print(json.dumps({"figures": sorted(path.name for path in OUT.glob("*.png"))}, indent=2))


if __name__ == "__main__":
    main()
