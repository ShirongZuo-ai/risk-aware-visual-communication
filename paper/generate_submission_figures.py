"""Generate the vector figures used by the final manuscript.

The numbers below are copied from frozen machine-readable artifacts in the
authoritative research repository and are mirrored in the claim-provenance
manifest.  This script performs no experiment or result recomputation.
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle
import numpy as np


OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)
INK = "#17212b"
BLUE = "#2774ae"
TEAL = "#16817a"
ORANGE = "#d97b29"
RED = "#b84a4a"
GRAY = "#66727c"


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def overview():
    fig, ax = plt.subplots(figsize=(7.15, 2.45))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")

    def box(x, y, w, h, text, color="white", edge=INK, fs=6.7, weight="normal"):
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
                               facecolor=color, edgecolor=edge, linewidth=1.0)
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=INK, weight=weight)
        return patch

    def arrow(x1, y1, x2, y2, color=GRAY):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=10, linewidth=1.1, color=color))

    ax.text(0.15, 3.72, "Causal sender", fontsize=7.5, weight="bold", color=INK)
    box(0.15, 2.55, 1.35, .72, "current RGB\nframe $I_t$", "#eef5fa", BLUE)
    box(0.15, 1.45, 1.35, .72, "local state +\nissued control", "#eef5fa", BLUE)
    box(0.15, .35, 1.35, .72, "finite wire\nbudget", "#f7f2e9", ORANGE)

    ax.text(2.1, 3.72, "Three non-equivalent quantities", fontsize=7.5, weight="bold", color=INK)
    box(2.1, 2.65, 2.05, .72, "Future danger $R_1$\nlong-horizon warning", "#edf5fb", BLUE, 6.5, "bold")
    box(4.55, 2.65, 2.05, .72, "Feasibility precursor\nnear-term warning", "#eef8f5", TEAL, 6.5, "bold")
    box(7.0, 2.65, 2.05, .72, "Safety Value\ndecision relevance", "#fff5e9", ORANGE, 6.5, "bold")
    arrow(4.15, 3.01, 4.55, 3.01)
    arrow(6.60, 3.01, 7.0, 3.01)
    ax.text(5.6, 2.35, r"$R_1 \,\ne\,$ decision value $\,\ne\,$ send utility",
            ha="center", va="center", fontsize=7.5, weight="bold", color=RED)

    box(2.1, 1.15, 2.05, .72, "held decoded frame\n$\\tilde I_t$", "#f3f4f5", GRAY)
    box(4.55, 1.15, 2.05, .72, "15-action safety\nplanner", "#f3f4f5", GRAY)
    box(7.0, 1.15, 2.05, .72, "$a_t \\in \\{\\mathsf{send},\\mathsf{hold}\\}$\nexact packet cost", "#f7f2e9", ORANGE)
    arrow(4.15, 1.51, 4.55, 1.51)
    arrow(6.60, 1.51, 7.0, 1.51)

    ax.text(9.62, 3.72, "Closed loop", fontsize=7.5, weight="bold", color=INK)
    box(9.62, 2.65, 2.15, .72, "decoded perception\n$\\rightarrow$ wheel control", "#eef8f5", TEAL)
    box(9.62, 1.15, 2.15, .72, "collision, clearance,\ndanger burden", "#f3f4f5", GRAY)
    arrow(9.05, 3.01, 9.62, 3.01)
    arrow(10.70, 2.65, 10.70, 1.87)
    arrow(9.62, 1.51, 9.05, 1.51)

    ax.text(5.95, .30,
            "Matched-wire evaluation asks whether spending a scarce packet now beats preserving the opportunity.",
            ha="center", va="center", fontsize=6.3, color=INK)
    save(fig, "fig1_system_overview")


def evidence_chain():
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.25), gridspec_kw={"wspace": .52})
    # M2 kinematic prediction.
    ax = axes[0]
    x = np.arange(2)
    state = np.array([1.20561e-4, 7.15992e-4])
    command = np.array([6.398e-6, 1.3655e-5])
    w = .34
    ax.bar(x - w/2, state, w, label="state-only", color=GRAY)
    ax.bar(x + w/2, command, w, label="command-cond.", color=BLUE)
    ax.set_yscale("log")
    ax.set_xticks(x, ["0.5 s", "2.0 s"])
    ax.set_ylabel("ADE (m, log scale)")
    ax.set_title("(a) Ego-motion rollout", loc="left", fontsize=9, weight="bold")
    ax.legend(frameon=False, fontsize=6.7, loc="upper left")

    # M9-B future danger.
    ax = axes[1]
    methods = ["$R_0$", "$R_1$", "$R_2$"]
    auprc = [.906311, .993730, .999778]
    bars = ax.bar(methods, auprc, color=[GRAY, BLUE, TEAL], width=.62)
    ax.set_ylim(.88, 1.005)
    ax.set_ylabel("2 s danger AUPRC")
    ax.set_title("(b) Future danger", loc="left", fontsize=9, weight="bold")
    for b, v in zip(bars, auprc):
        ax.text(b.get_x()+b.get_width()/2, v+.002, f"{v:.3f}", ha="center", fontsize=6.7)

    # Q5 precursor qualification.
    ax = axes[2]
    fam = ["slalom", "weave", "gate", "chicane"]
    cov = [75, 100, 75, 83.333]
    ax.barh(fam, cov, color=TEAL)
    ax.set_xlim(0, 105)
    ax.set_xlabel("onset coverage (%)")
    ax.set_title("(c) Frozen precursor", loc="left", fontsize=9, weight="bold")
    for i, value in enumerate(cov):
        ax.text(value-2, i, f"{value:.0f}%", ha="right", va="center", color="white",
                fontsize=7, weight="bold")

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", color="#dfe3e6", linewidth=.45, zorder=0)
    save(fig, "fig2_evidence_chain")


def closed_loop():
    families = ["opposed gate", "reverse chicane", "staggered slalom", "three-stage weave"]
    danger = [-20.8, -8.4, 26.2, -38.2]
    clearance = [3.3298, -3.8640, -14.0405, 9.6278]
    y = np.arange(len(families))
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.35), sharey=True, gridspec_kw={"wspace": .08})
    for ax, values, xlabel in zip(
        axes, [danger, clearance],
        ["scheduler $-$ $U_0$ danger steps / cell", "scheduler $-$ $U_0$ min clearance (mm)"]
    ):
        colors = [BLUE if (v < 0 if ax is axes[0] else v > 0) else RED for v in values]
        ax.barh(y, values, color=colors, height=.62)
        ax.axvline(0, color=INK, linewidth=.8)
        ax.set_xlabel(xlabel, fontsize=7.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7)
    axes[0].set_yticks(y, families)
    axes[0].invert_yaxis()
    axes[0].set_title("(a) Danger burden (lower is safer)", fontsize=9, weight="bold")
    axes[1].set_title("(b) Clearance (higher is safer)", fontsize=9, weight="bold")
    fig.suptitle("Exact 72 kB/episode: family heterogeneity against the stronger $U_0$ baseline",
                 fontsize=9.4, weight="bold", y=1.02)
    save(fig, "fig3_q6_closed_loop")


if __name__ == "__main__":
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8, "axes.labelcolor": INK,
        "axes.edgecolor": INK, "xtick.color": INK, "ytick.color": INK,
        "text.color": INK, "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    overview()
    evidence_chain()
    closed_loop()
