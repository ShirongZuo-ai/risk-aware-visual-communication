"""Render representative aligned causal traces for frozen CVC-P6 A1 episodes."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "cvc_p6_webots"
SCENARIOS = ("center_large", "left_offset", "two_component")
COLORS = {"blue": "#175CD3", "orange": "#B54708", "purple": "#7F56D9",
          "pink": "#C01048", "olive": "#667085", "ink": "#344054", "light": "#D0D5DD"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    output = RESULTS / "figures"
    output.mkdir(parents=True, exist_ok=True)
    for scenario in SCENARIOS:
        rows = read_jsonl(RESULTS / "traces" / f"p6__{scenario}__A1.jsonl")
        steps = [row["step"] for row in rows]
        arm = next(row["policy_state"]["arm_step"] for row in rows
                   if row["policy_state"]["arm_step"] is not None)
        spend = next(row["step"] for row in rows
                     if row["communication"]["packet_role"] == "adaptive")
        reserve = next(row["step"] for row in rows
                       if row["communication"]["packet_role"] == "reserve")
        thresholds = rows[0]["task_novelty"]["thresholds"]
        risk0 = [row["sender"]["r0"] for row in rows]
        risk1 = [row["sender"]["r1"] for row in rows]
        bearing = [row["task_novelty"]["delta_bearing"] / thresholds["bearing"] for row in rows]
        proximity = [row["task_novelty"]["delta_proximity"] / thresholds["proximity"] for row in rows]
        area = [row["task_novelty"]["delta_area_relative"] / thresholds["area_relative"] for row in rows]
        age = [row["receiver"]["image_age_ms"] for row in rows]
        control = [row["counterfactual"]["control"]["control_l2"] for row in rows]
        left = [row["control"]["left_rad_s"] for row in rows]
        right = [row["control"]["right_rad_s"] for row in rows]
        clearance = [row["evaluator"]["clearance_m"] for row in rows]
        contacts = [row["step"] for row in rows if row["evaluator"]["contact"]]

        fig, axes = plt.subplots(4, 1, figsize=(11, 9.5), sharex=True)
        risk_axis, novelty_axis, age_axis, control_axis = axes
        for axis in axes:
            axis.axvspan(arm, spend, color="#EAF2FF", alpha=0.8, label="ARMED window" if axis is risk_axis else None)
            axis.axvline(arm, color=COLORS["blue"], linestyle="--", linewidth=1.2,
                         label="ARM" if axis is risk_axis else None)
            axis.axvline(spend, color=COLORS["orange"], linewidth=1.5,
                         label="SPEND" if axis is risk_axis else None)
            axis.axvline(reserve, color=COLORS["ink"], linestyle=":", linewidth=1.2,
                         label="Reserve" if axis is risk_axis else None)
            axis.grid(axis="y", color="#EAECF0", linewidth=0.8)

        risk_axis.plot(steps, risk0, color=COLORS["olive"], linestyle="--", linewidth=1.3, label="R0")
        risk_axis.plot(steps, risk1, color=COLORS["blue"], linewidth=1.7, label="R1")
        risk_axis.axhline(0.14, color="#98A2B3", linestyle=":", linewidth=1.0, label="risk threshold")
        risk_axis.set_ylabel("Risk")
        risk_axis.set_ylim(-0.03, 1.05)
        risk_axis.legend(loc="upper right", ncols=7, frameon=False, fontsize=8)

        novelty_axis.plot(steps, bearing, color=COLORS["orange"], linewidth=1.3, label="bearing / threshold")
        novelty_axis.plot(steps, proximity, color=COLORS["purple"], linestyle="--", linewidth=1.3,
                          label="proximity / threshold")
        novelty_axis.plot(steps, area, color=COLORS["pink"], linestyle="-.", linewidth=1.3,
                          label="relative area / threshold")
        novelty_axis.axhline(1.0, color="#98A2B3", linestyle=":", linewidth=1.0, label="event boundary")
        novelty_axis.set_ylabel("Task novelty\n(threshold ratio)")
        novelty_axis.legend(loc="upper right", ncols=4, frameon=False, fontsize=8)

        age_axis.plot(steps, age, color=COLORS["blue"], linewidth=1.4, label="received image age")
        age_axis.set_ylabel("Image age (ms)")
        age_other = age_axis.twinx()
        age_other.plot(steps, control, color=COLORS["pink"], linewidth=1.5, label="counterfactual control sensitivity")
        age_other.set_ylabel("Control sensitivity (rad/s)")
        lines = age_axis.get_lines() + age_other.get_lines()
        lines = [line for line in lines if not line.get_label().startswith("_")]
        age_axis.legend(lines, [line.get_label() for line in lines], loc="upper right", ncols=2,
                        frameon=False, fontsize=8)

        control_axis.plot(steps, left, color=COLORS["blue"], linewidth=1.3, label="left wheel")
        control_axis.plot(steps, right, color=COLORS["orange"], linestyle="--", linewidth=1.3, label="right wheel")
        control_axis.set_ylabel("Wheel command\n(rad/s)")
        clearance_axis = control_axis.twinx()
        clearance_axis.plot(steps, clearance, color=COLORS["ink"], linestyle=":", linewidth=1.4,
                            label="physical clearance")
        if contacts:
            clearance_axis.scatter(contacts, [clearance[step] for step in contacts], color=COLORS["pink"],
                                   s=18, marker="x", label="contact")
        clearance_axis.set_ylabel("Clearance (m)")
        lines = [line for line in control_axis.get_lines() + clearance_axis.get_lines()
                 if not line.get_label().startswith("_")]
        labels = [line.get_label() for line in lines]
        if contacts:
            lines.append(clearance_axis.collections[-1])
            labels.append("contact")
        control_axis.legend(lines, labels, loc="upper right", ncols=4, frameon=False, fontsize=8)
        control_axis.set_xlabel("Controller step (32 ms)")

        fig.suptitle(f"CVC-P6 A1 causal trace: {scenario.replace('_', ' ')}")
        fig.text(0.5, 0.012,
                 "Frozen development episode; blue shading is ARM-to-SPEND. Actual receiver/control and evaluator clearance are aligned by step.",
                 ha="center", fontsize=9, color="#475467")
        fig.tight_layout(rect=(0, 0.035, 1, 0.965))
        fig.savefig(output / f"a1_causal_trace__{scenario}.png", dpi=180, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    main()
