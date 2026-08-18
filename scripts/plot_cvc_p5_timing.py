"""Render frozen representative CVC-P5 causal timing traces."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "cvc_p5_diagnostic"
SCENARIOS = ("center_large", "left_offset", "two_component")
COLORS = {"r0": "#667085", "r1": "#175CD3", "visual": "#B54708",
          "perception": "#7F56D9", "control": "#C01048", "clearance": "#344054"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def normalized(values: list[float]) -> list[float]:
    maximum = max(values)
    return [value / maximum if maximum > 0 else 0.0 for value in values]


def main() -> None:
    output = RESULTS / "figures"
    output.mkdir(parents=True, exist_ok=True)
    for scenario in SCENARIOS:
        rows = read_jsonl(RESULTS / "traces" / f"diagnostic__{scenario}__A1.jsonl")
        steps = [row["step"] for row in rows]
        r0 = [row["sender"]["r0"] for row in rows]
        r1 = [row["sender"]["r1"] for row in rows]
        visual = normalized([row["counterfactual"]["visual"]["pixel_mae"] for row in rows])
        perception = normalized([row["counterfactual"]["perception"]["combined_l2"] for row in rows])
        control = normalized([row["counterfactual"]["control"]["control_l2"] for row in rows])
        clearance = [row["evaluator"]["clearance_m"] for row in rows]
        sends = [row["step"] for row in rows if row["communication"]["transmitted"]]

        fig, (top, bottom) = plt.subplots(2, 1, figsize=(10.5, 6.2), sharex=True,
                                          gridspec_kw={"height_ratios": [1.2, 1.0]})
        top.plot(steps, r0, color=COLORS["r0"], linewidth=1.5, linestyle="--", label="R0")
        top.plot(steps, r1, color=COLORS["r1"], linewidth=1.8, label="R1")
        top.axhline(0.14, color="#98A2B3", linewidth=1.0, linestyle=":", label="P4 trigger = 0.14")
        top.set_ylabel("Risk")
        top.set_ylim(-0.03, 1.05)
        top.legend(loc="upper right", ncols=3, frameon=False)

        bottom.plot(steps, visual, color=COLORS["visual"], linewidth=1.4, label="Visual MAE / peak")
        bottom.plot(steps, perception, color=COLORS["perception"], linewidth=1.4,
                    linestyle="--", label="Perception change / peak")
        bottom.plot(steps, control, color=COLORS["control"], linewidth=1.8,
                    label="Control sensitivity / peak")
        clearance_axis = bottom.twinx()
        clearance_axis.plot(steps, clearance, color=COLORS["clearance"], linewidth=1.0,
                            alpha=0.55, linestyle=":", label="Physical clearance")
        for index, step in enumerate(sends):
            for axis in (top, bottom):
                axis.axvline(step, color="#101828", linewidth=0.9,
                             linestyle=("-" if index == 1 else ":"), alpha=0.55)
        bottom.set_ylabel("Normalized diagnostic")
        clearance_axis.set_ylabel("Clearance (m)")
        bottom.set_xlabel("Controller step (32 ms)")
        bottom.set_ylim(-0.03, 1.05)
        lines = [line for line in bottom.get_lines() + clearance_axis.get_lines()
                 if not line.get_label().startswith("_")]
        bottom.legend(lines, [line.get_label() for line in lines], loc="upper right", ncols=2, frameon=False)
        fig.suptitle(f"CVC-P5 A1 held-versus-current timing: {scenario.replace('_', ' ')}")
        fig.text(0.5, 0.01,
                 "Vertical lines: startup, adaptive (solid), and fixed reserve transmissions. Diagnostic curves are peak-normalized.",
                 ha="center", fontsize=9, color="#475467")
        fig.tight_layout(rect=(0, 0.04, 1, 0.96))
        fig.savefig(output / f"a1_timing__{scenario}.png", dpi=180, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    main()
