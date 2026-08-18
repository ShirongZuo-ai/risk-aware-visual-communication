"""Generate the final, submission-sized manuscript figures from frozen evidence.

This script is plotting-only.  It reads existing machine-readable artifacts,
checks the displayed values, and writes new ``*_final`` outputs without
overwriting historical figures or experiment results.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.ticker import LogFormatterMathtext, NullFormatter
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Paper-level semantic palette.  Meaning is held fixed across all figures.
INK = "#17232D"
MUTED = "#65717B"
GRID = "#DCE1E5"
GRAY = "#707B84"          # current/reference/baseline
GRAY_LIGHT = "#EDF0F2"
BLUE = "#0F4D92"          # future prediction / R1 / principal predictive result
BLUE_LIGHT = "#EAF2F8"
GREEN = "#3D8653"         # positive physical improvement / supportive secondary result
GREEN_LIGHT = "#EAF4EC"
RED = "#B64342"           # adverse physical outcome
RED_LIGHT = "#F8EAEA"
ACCENT = "#B56B00"        # Safety Value / feasibility precursor
ACCENT_LIGHT = "#FBF1DF"


@dataclass(frozen=True)
class BoxRecord:
    patch: FancyBboxPatch
    text: Any


def apply_publication_style() -> None:
    """Apply an IEEE-size adaptation of the figures4papers house style."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.3,
            "axes.titlesize": 8.5,
            "axes.labelsize": 7.5,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.labelsize": 7.0,
            "ytick.labelsize": 7.0,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "legend.frameon": False,
            "legend.fontsize": 7.0,
            "text.color": INK,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
        }
    )


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_m2() -> dict[str, list[float]]:
    path = ROOT / "results" / "m2_trajectory" / "summary_metrics.csv"
    rows = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows.extend(csv.DictReader(stream))
    selected = {
        (row["method"], float(row["horizon_s"])): float(row["ade_mean_m"])
        for row in rows
        if row["category"] == "all_stable" and float(row["horizon_s"]) in (0.5, 2.0)
    }
    assert len(selected) == 4
    result = {
        "state_only": [selected[("state_only", 0.5)], selected[("state_only", 2.0)]],
        "command_conditioned": [
            selected[("command_conditioned", 0.5)],
            selected[("command_conditioned", 2.0)],
        ],
    }
    assert np.allclose(result["state_only"], [1.20561e-4, 7.15992e-4], rtol=0, atol=5e-13)
    assert np.allclose(result["command_conditioned"], [6.398e-6, 1.3655e-5], rtol=0, atol=5e-13)
    return result


def load_m9b() -> dict[str, Any]:
    path = ROOT / "results" / "m9b_formal" / "formal_results.json"
    data = read_json(path)
    assert data["support_pass"] is True and data["valid_episodes"] == 240
    assert data["excluded_episodes"] == []
    return data


def load_q5() -> dict[str, Any]:
    path = ROOT / "results" / "cvc_q5_analysis" / "analysis.json"
    data = read_json(path)
    assert data["all_gates_pass"] is True
    assert data["metrics"]["accepted_onset_count"] == 19
    assert data["metrics"]["covered_onsets"] == 16
    assert data["rule"]["changed_or_refit"] is False
    return data


def load_q6() -> dict[str, Any]:
    path = ROOT / "results" / "cvc_q6_analysis" / "q6-g3-opportunity-persistent.json"
    data = read_json(path)
    assert data["exact_matched_cost"] is True
    assert data["classification"] == "Q6-NEGATIVE-CHAIN-LOCALIZED"
    assert data["pooled"]["U0"]["cells"] == 20
    return data


def load_q65_example() -> list[dict[str, Any]]:
    path = (
        ROOT
        / "results"
        / "cvc_q65_development"
        / "generation2_schedule_bank"
        / "analysis.json"
    )
    data = read_json(path)
    records = [row for row in data["corpus"] if row["cell_id"] == "q65-afs-01"]
    records.sort(key=lambda row: row["step"])
    assert [row["step"] for row in records] == [80, 109, 144]
    assert [row["next_step"] for row in records] == [109, 144, 217]
    assert [row["label"] for row in records] == ["neutral", "helpful", "harmful"]
    assert [row["utility"]["danger_steps_delta"] for row in records] == [0, -122, 26]
    return records


def _figure_text_bounds(fig: plt.Figure) -> None:
    """Fail if a visible text artist is clipped by the exported figure canvas."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    tolerance = 2.0
    failures = []
    for text in fig.findobj(match=lambda artist: isinstance(artist, matplotlib.text.Text)):
        if not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer=renderer)
        if box.width == 0 or box.height == 0:
            continue
        if (
            box.x0 < canvas.x0 - tolerance
            or box.y0 < canvas.y0 - tolerance
            or box.x1 > canvas.x1 + tolerance
            or box.y1 > canvas.y1 + tolerance
        ):
            failures.append(text.get_text())
    if failures:
        raise AssertionError(f"Text outside figure canvas: {failures}")


def _validate_box_text(fig: plt.Figure, records: Iterable[BoxRecord]) -> None:
    """Fail if conceptual-diagram text escapes its intended rounded box."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    failures = []
    for record in records:
        patch_box = record.patch.get_window_extent(renderer=renderer)
        text_box = record.text.get_window_extent(renderer=renderer)
        inset = 3.0
        if not (
            text_box.x0 >= patch_box.x0 + inset
            and text_box.x1 <= patch_box.x1 - inset
            and text_box.y0 >= patch_box.y0 + inset
            and text_box.y1 <= patch_box.y1 - inset
        ):
            failures.append(record.text.get_text())
    if failures:
        raise AssertionError(f"Text exceeds its intended box: {failures}")


def save_figure(fig: plt.Figure, basename: str, box_records: Iterable[BoxRecord] = ()) -> None:
    fig.canvas.draw()
    if box_records:
        _validate_box_text(fig, box_records)
    _figure_text_bounds(fig)
    for suffix, kwargs in (
        ("pdf", {}),
        ("svg", {}),
        ("png", {"dpi": 600}),
    ):
        fig.savefig(
            OUT / f"{basename}.{suffix}",
            bbox_inches="tight",
            pad_inches=0.025,
            **kwargs,
        )
    plt.close(fig)


def figure_1() -> None:
    """Conceptual sender/receiver/evaluator overview with bounded box text."""
    fig, ax = plt.subplots(figsize=(7.16, 2.05))
    fig.subplots_adjust(left=0.008, right=0.995, bottom=0.04, top=0.98)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Subtle swimlanes make the information boundary visible without heavy frames.
    ax.axvspan(0.005, 0.665, color="#F8FAFB", zorder=0)
    ax.axvspan(0.680, 0.865, color="#F3F7FA", zorder=0)
    ax.axvspan(0.880, 0.995, color="#FAF7F7", zorder=0)
    ax.plot([0.672, 0.672], [0.20, 0.91], color=GRID, lw=0.8)
    ax.plot([0.872, 0.872], [0.20, 0.91], color=GRID, lw=0.8)

    ax.text(0.015, 0.955, "CAUSAL SENDER", fontsize=8.2, weight="bold", va="top")
    ax.text(0.690, 0.955, "RECEIVER", fontsize=8.2, weight="bold", va="top")
    ax.text(0.985, 0.955, "EVALUATOR ONLY", fontsize=8.2, weight="bold", va="top", ha="right")

    records: list[BoxRecord] = []

    def add_box(
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        face: str,
        edge: str,
        *,
        weight: str = "normal",
        fontsize: float = 7.0,
    ) -> tuple[float, float, float, float]:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.018",
            facecolor=face,
            edgecolor=edge,
            linewidth=0.9,
            zorder=2,
        )
        ax.add_patch(patch)
        artist = ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            weight=weight,
            linespacing=1.12,
            zorder=3,
        )
        records.append(BoxRecord(patch, artist))
        return x, y, w, h

    def connect(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> None:
        x1 = left[0] + left[2]
        x2 = right[0]
        y = left[1] + left[3] / 2
        arrow = FancyArrowPatch(
            (x1 + 0.004, y),
            (x2 - 0.004, y),
            arrowstyle="-|>",
            mutation_scale=8,
            linewidth=0.9,
            color=MUTED,
            zorder=1,
        )
        ax.add_patch(arrow)

    boxes = [
        add_box(0.018, 0.49, 0.105, 0.29, "RGB frame $I_t$\nstate + command", BLUE_LIGHT, BLUE),
        add_box(0.151, 0.49, 0.105, 0.29, "Future danger\n$R_1$", BLUE_LIGHT, BLUE, weight="bold"),
        add_box(0.284, 0.49, 0.112, 0.29, "Feasibility\nprecursor", ACCENT_LIGHT, ACCENT, weight="bold"),
        add_box(0.424, 0.49, 0.105, 0.29, "Safety Value\ndecision\nrelevance", ACCENT_LIGHT, ACCENT, weight="bold"),
        add_box(0.557, 0.49, 0.098, 0.29, "SEND / HOLD\nfinite budget", GRAY_LIGHT, INK, weight="bold"),
        add_box(0.691, 0.43, 0.163, 0.41, "Decode or hold $\\tilde I_t$\n15-action safety planner\nwheel control", BLUE_LIGHT, BLUE),
        add_box(0.888, 0.43, 0.099, 0.41, "Collision\nclearance\ndanger burden", RED_LIGHT, RED),
    ]
    for left, right in zip(boxes[:-1], boxes[1:]):
        connect(left, right)

    # The central scientific distinction is outside every box and well separated.
    ax.text(
        0.50,
        0.155,
        "Future risk  $\\ne$  decision value  $\\ne$  send utility",
        ha="center",
        va="center",
        fontsize=9.0,
        weight="bold",
        color=RED,
    )
    ax.text(
        0.50,
        0.055,
        "Real serialized bytes are matched; simulator contact and true clearance never enter the sender.",
        ha="center",
        va="center",
        fontsize=7.0,
        color=MUTED,
    )
    save_figure(fig, "fig1_system_overview_final", records)


def _style_quant_axis(ax: plt.Axes, *, grid_axis: str = "y") -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.45, zorder=0)
    ax.tick_params(direction="out", length=2.8, pad=2.0)


def figure_2(m2: dict[str, list[float]], m9b: dict[str, Any], q5: dict[str, Any]) -> None:
    fig = plt.figure(figsize=(7.16, 2.55))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=[1.02, 1.02, 1.25],
        left=0.075,
        right=0.992,
        bottom=0.19,
        top=0.78,
        wspace=0.58,
    )

    # (a) Motion prediction: paired markers avoid a misleading log-scale bar baseline.
    ax = fig.add_subplot(grid[0, 0])
    x = np.arange(2)
    state = np.asarray(m2["state_only"])
    command = np.asarray(m2["command_conditioned"])
    for index in range(2):
        ax.plot([x[index], x[index]], [command[index], state[index]], color=GRID, lw=2.0, zorder=1)
    ax.scatter(x, state, marker="s", s=31, color=GRAY, edgecolor=INK, linewidth=0.6, zorder=3)
    ax.scatter(x, command, marker="o", s=34, color=BLUE, edgecolor=INK, linewidth=0.6, zorder=3)
    labels_state = ["1.21e-4", "7.16e-4"]
    labels_command = ["6.40e-6", "1.37e-5"]
    for xi, value, label in zip(x, state, labels_state):
        ax.annotate(label, (xi, value), xytext=(4, 4), textcoords="offset points", fontsize=7.0)
    for xi, value, label in zip(x, command, labels_command):
        ax.annotate(label, (xi, value), xytext=(4, -9), textcoords="offset points", fontsize=7.0)
    ax.set_yscale("log")
    ax.set_ylim(3.2e-6, 1.45e-3)
    ax.set_yticks([1e-5, 1e-4, 1e-3])
    ax.yaxis.set_major_formatter(LogFormatterMathtext())
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(-0.34, 1.43)
    ax.set_xticks(x, ["0.5 s", "2.0 s"])
    ax.set_xlabel("Prediction horizon")
    ax.set_ylabel("ADE (m, log scale)")
    ax.set_title("(a) Motion prediction", loc="left", weight="bold", pad=4)
    handles = [
        Line2D([], [], marker="s", color="none", markerfacecolor=GRAY, markeredgecolor=INK, markersize=5, label="state-only"),
        Line2D([], [], marker="o", color="none", markerfacecolor=BLUE, markeredgecolor=INK, markersize=5, label="command-conditioned"),
    ]
    ax.legend(handles=handles, loc="upper left", borderaxespad=0.2, handletextpad=0.4)
    _style_quant_axis(ax)

    # (b) Future danger: R0 is explicitly current-state, R1 is the primary future rollout.
    ax = fig.add_subplot(grid[0, 1])
    auprc = m9b["primary_2s_auprc"]
    values = [auprc["R0"], auprc["R1"], auprc["R2"]]
    bars = ax.bar(
        np.arange(3),
        values,
        width=0.62,
        color=[GRAY_LIGHT, BLUE, GREEN_LIGHT],
        edgecolor=[INK, INK, GREEN],
        linewidth=0.8,
        hatch=["///", "", ".."],
        zorder=2,
    )
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.002, f"{value:.4f}", ha="center", va="bottom", fontsize=7.0)
    contrast = m9b["contrasts"]["primary_R1_minus_R0"]
    lower = contrast["ci95"]["lower"]
    upper = contrast["ci95"]["upper"]
    y0, y1 = 1.003, 1.008
    ax.plot([0, 0, 1, 1], [y0, y1, y1, y0], color=INK, lw=0.7, clip_on=False)
    ax.text(0.50, 1.010, f"$R_1-R_0={contrast['delta']:.5f}$\n95% CI [{lower:.5f}, {upper:.5f}]", ha="center", va="bottom", fontsize=7.0)
    ax.set_ylim(0.88, 1.029)
    ax.set_xticks(
        np.arange(3),
        ["$R_0$\ncurrent", "$R_1$\nstate rollout", "$R_2$\ncmd rollout"],
    )
    ax.set_ylabel("2-s danger AUPRC")
    ax.set_title("(b) Future danger", loc="left", weight="bold", pad=4)
    _style_quant_axis(ax)

    # (c) Q5 frozen precursor transfer.
    ax = fig.add_subplot(grid[0, 2])
    family_keys = [
        "staggered_slalom_constraint",
        "three_stage_weave",
        "opposed_gate_contraction",
        "reverse_diagonal_chicane",
    ]
    family_labels = [
        "Staggered\nslalom",
        "Three-stage\nweave",
        "Opposed gate",
        "Reverse diagonal\nchicane",
    ]
    metrics = q5["metrics"]
    coverage = [100.0 * metrics["per_family"][key]["coverage"] for key in family_keys]
    fractions = [
        f"{metrics['per_family'][key]['covered_onsets']}/{metrics['per_family'][key]['onset_count']}"
        for key in family_keys
    ]
    y = np.arange(len(family_keys))
    bars = ax.barh(
        y,
        coverage,
        height=0.58,
        color=ACCENT_LIGHT,
        edgecolor=ACCENT,
        linewidth=0.9,
        hatch="//",
        zorder=2,
    )
    for bar, fraction, value in zip(bars, fractions, coverage):
        ax.text(min(value - 2.0, 98.0), bar.get_y() + bar.get_height() / 2, fraction, ha="right", va="center", fontsize=7.0, weight="bold", color=INK)
    ax.set_yticks(y, family_labels)
    ax.invert_yaxis()
    ax.set_ylim(3.6, -1.05)
    ax.set_xlim(0, 105)
    ax.set_xticks([0, 50, 100])
    ax.set_xlabel("Accepted-onset coverage (%)")
    ax.set_title("(c) Safety-Value precursor", loc="left", weight="bold", pad=4)
    ax.text(
        0.0,
        -0.73,
        f"Frozen; no refitting  |  {metrics['covered_onsets']}/{metrics['accepted_onset_count']} = {100*metrics['covered_onsets']/metrics['accepted_onset_count']:.2f}%\nmedian lead {metrics['median_lead_s']:.3f} s",
        ha="left",
        va="center",
        fontsize=7.0,
        color=ACCENT,
        weight="bold",
    )
    _style_quant_axis(ax, grid_axis="x")

    save_figure(fig, "fig2_evidence_chain_final")


def _signed_bar_panel(
    ax: plt.Axes,
    values: list[float],
    family_labels: list[str],
    *,
    safer_when_negative: bool,
    title: str,
    xlabel: str,
    xlim: tuple[float, float],
    fmt: str,
    show_ylabels: bool,
) -> None:
    y = np.arange(len(values))
    for index, value in enumerate(values):
        safer = value < 0 if safer_when_negative else value > 0
        bar = ax.barh(
            index,
            value,
            height=0.56,
            color=GREEN_LIGHT if safer else RED_LIGHT,
            edgecolor=GREEN if safer else RED,
            linewidth=0.9,
            hatch="" if safer else "///",
            zorder=2,
        )[0]
        span = xlim[1] - xlim[0]
        if abs(value) >= 0.17 * span:
            if value >= 0:
                xtext, align = value - 0.02 * span, "right"
            else:
                xtext, align = value + 0.02 * span, "left"
        elif value >= 0:
            xtext, align = value + 0.015 * span, "left"
        else:
            xtext, align = value - 0.015 * span, "right"
        ax.text(xtext, bar.get_y() + bar.get_height() / 2, format(value, fmt), ha=align, va="center", fontsize=7.0, weight="bold")
    ax.axvline(0, color=INK, lw=0.85, zorder=3)
    ax.set_xlim(*xlim)
    ax.set_ylim(-0.6, len(values) - 0.4)
    ax.set_yticks(y, family_labels if show_ylabels else [""] * len(values))
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", weight="bold", pad=4)
    if safer_when_negative:
        direction = "$\\leftarrow$ safer    adverse $\\rightarrow$"
    else:
        direction = "adverse $\\leftarrow$    safer $\\rightarrow$"
    ax.text(0.5, 0.965, direction, transform=ax.transAxes, ha="center", va="top", fontsize=7.0, color=MUTED)
    _style_quant_axis(ax, grid_axis="x")


def figure_3(q6: dict[str, Any], q65_records: list[dict[str, Any]]) -> None:
    fig = plt.figure(figsize=(7.16, 2.30))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=[1.15, 1.05, 0.90],
        left=0.17,
        right=0.992,
        bottom=0.22,
        top=0.94,
        wspace=0.56,
    )
    family_keys = [
        "opposed_gate_contraction",
        "reverse_diagonal_chicane",
        "staggered_slalom_constraint",
        "three_stage_weave",
    ]
    family_labels = [
        "Opposed gate",
        "Reverse diagonal\nchicane",
        "Staggered slalom",
        "Three-stage weave",
    ]
    effects = [q6["families"][key]["U0"] for key in family_keys]
    danger = [row["mean_danger_steps_delta"] for row in effects]
    clearance_mm = [1000.0 * row["mean_min_clearance_delta_m"] for row in effects]

    ax = fig.add_subplot(grid[0, 0])
    _signed_bar_panel(
        ax,
        danger,
        family_labels,
        safer_when_negative=True,
        title="(a) Danger burden",
        xlabel="Scheduler $-$ $U_0$ danger steps/cell",
        xlim=(-47, 35),
        fmt="+.1f",
        show_ylabels=True,
    )

    ax = fig.add_subplot(grid[0, 1])
    _signed_bar_panel(
        ax,
        clearance_mm,
        family_labels,
        safer_when_negative=False,
        title="(b) Minimum clearance",
        xlabel="Scheduler $-$ $U_0$ clearance (mm)",
        xlim=(-18.5, 13.5),
        fmt="+.1f",
        show_ylabels=False,
    )

    # (c) One frozen Q6.5 cell: adjacent opportunities reverse utility.
    ax = fig.add_subplot(grid[0, 2])
    x = np.arange(len(q65_records))
    values = [row["utility"]["danger_steps_delta"] for row in q65_records]
    labels = [row["label"] for row in q65_records]
    colors = [GRAY_LIGHT, GREEN_LIGHT, RED_LIGHT]
    edges = [GRAY, GREEN, RED]
    hatches = ["..", "", "///"]
    for index, (value, label) in enumerate(zip(values, labels)):
        if value == 0:
            ax.scatter(index, 0, marker="D", s=27, facecolor=colors[index], edgecolor=edges[index], linewidth=0.9, zorder=4)
            ax.text(index, 9, "0\nneutral", ha="center", va="bottom", fontsize=7.0, weight="bold")
        else:
            bar = ax.bar(index, value, width=0.58, color=colors[index], edgecolor=edges[index], linewidth=0.9, hatch=hatches[index], zorder=2)[0]
            ytext = value + 8 if value < 0 else value + 6
            va = "bottom"
            ax.text(index, ytext, f"{value:+d}\n{label}", ha="center", va=va, fontsize=7.0, weight="bold")
    ax.axhline(0, color=INK, lw=0.85, zorder=3)
    ax.set_ylim(-145, 55)
    ax.set_yticks([-125, -100, -50, 0, 25, 50])
    ax.set_xticks(
        x,
        [f"{row['step']}→{row['next_step']}" for row in q65_records],
    )
    ax.set_xlabel("SEND step\n$\\rightarrow$ next opportunity")
    ax.set_ylabel("SEND-now $\\Delta$ danger steps")
    ax.set_title("(c) Q6.5 timing reversal", loc="left", weight="bold", pad=4)
    _style_quant_axis(ax)

    save_figure(fig, "fig3_q6_closed_loop_final")


def write_provenance(
    m2: dict[str, list[float]],
    m9b: dict[str, Any],
    q5: dict[str, Any],
    q6: dict[str, Any],
    q65_records: list[dict[str, Any]],
) -> None:
    family_keys = [
        "opposed_gate_contraction",
        "reverse_diagonal_chicane",
        "staggered_slalom_constraint",
        "three_stage_weave",
    ]
    payload = {
        "schema_version": "submission-figure-provenance-v1",
        "scope": "plotting-only; no experiment or result recomputation",
        "style_contract": {
            "final_width_in": 7.16,
            "minimum_text_pt": 7.0,
            "font_fallback": ["Arial", "Helvetica", "DejaVu Sans"],
            "semantic_palette": {
                "current_or_baseline": GRAY,
                "future_prediction_R1": BLUE,
                "positive_physical_effect_or_secondary": GREEN,
                "adverse_physical_effect": RED,
                "safety_value_or_precursor": ACCENT,
            },
            "non_color_channels": ["bar edge", "marker shape", "hatch", "sign", "zero reference", "direction label"],
            "primary_export": "vector PDF",
            "editable_export": "SVG with text preserved",
            "review_export": "600 dpi PNG",
        },
        "figure_1": {
            "kind": "conceptual schematic",
            "numeric_labels": {"episode_wire_bytes": 72000},
            "sources": [
                "docs/research_protocol.md",
                "docs/cvc_q65_communication_opportunity_value_report.md",
                "results/cvc_q6_final_status.json",
                "results/cvc_q65_final_status.json",
            ],
        },
        "figure_2": {
            "motion_prediction": {
                "source": "results/m2_trajectory/summary_metrics.csv",
                "filter": "category=all_stable; horizons=0.5,2.0 s",
                "ade_m": m2,
            },
            "future_danger": {
                "source": "results/m9b_formal/formal_results.json",
                "valid_episodes": m9b["valid_episodes"],
                "excluded_episodes": len(m9b["excluded_episodes"]),
                "auprc": m9b["primary_2s_auprc"],
                "primary_R1_minus_R0": m9b["contrasts"]["primary_R1_minus_R0"],
            },
            "safety_value_precursor": {
                "source": "results/cvc_q5_analysis/analysis.json",
                "positive_families": q5["support"]["positive_families"],
                "per_family": {key: q5["metrics"]["per_family"][key] for key in q5["support"]["positive_families"]},
                "aggregate": {
                    "covered": q5["metrics"]["covered_onsets"],
                    "onsets": q5["metrics"]["accepted_onset_count"],
                    "median_lead_s": q5["metrics"]["median_lead_s"],
                    "lead_iqr_s": [q5["metrics"]["lead_distribution_s"]["q25"], q5["metrics"]["lead_distribution_s"]["q75"]],
                    "rule_changed_or_refit": q5["rule"]["changed_or_refit"],
                },
            },
        },
        "figure_3": {
            "q6_family_effects": {
                "source": "results/cvc_q6_analysis/q6-g3-opportunity-persistent.json",
                "comparison": "scheduler minus U0",
                "wire_bytes_per_episode": 72000,
                "families": {key: q6["families"][key]["U0"] for key in family_keys},
                "pooled": q6["pooled"]["U0"],
            },
            "q65_timing_reversal": {
                "source": "results/cvc_q65_development/generation2_schedule_bank/analysis.json",
                "cell_id": "q65-afs-01",
                "records": q65_records,
                "reason_for_inclusion": "compact mechanism panel; replaces no main quantitative panel and shows adjacent-opportunity non-monotonicity",
            },
        },
    }
    target = OUT / "figure_data_provenance_final.json"
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> None:
    apply_publication_style()
    m2 = load_m2()
    m9b = load_m9b()
    q5 = load_q5()
    q6 = load_q6()
    q65_records = load_q65_example()
    figure_1()
    figure_2(m2, m9b, q5)
    figure_3(q6, q65_records)
    write_provenance(m2, m9b, q5, q6, q65_records)


if __name__ == "__main__":
    main()
