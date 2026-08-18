"""Terminal descriptive and causal analysis for frozen CVC-Q2 development."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "results" / "cvc_q2_webots" / "matrix_results.json"
TRACES = ROOT / "results" / "cvc_q2_webots" / "traces"
READINESS = ROOT / "results" / "cvc_q2_readiness" / "manifest.json"
CONFIG = ROOT / "config" / "cvc_q2_development.json"
OUT = ROOT / "results" / "cvc_q2_analysis"
NEAR = .12
FUTURE_STEPS = 63


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trace(scenario: str, policy: str) -> list[dict]:
    path = TRACES / f"q2__{scenario}__{policy}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def label(row: dict) -> str:
    return "collision" if row["collision"] else ("near" if row["min_clearance_m"] <= NEAR else "safe")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] * (high - position) + ordered[high] * (position - low)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "figures").mkdir(exist_ok=True)
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    records = matrix["records"]
    if len(records) != 30 or not matrix["all_exact_cost"] or not matrix["all_mirrors_match"]:
        raise RuntimeError("Q2 matrix integrity failed")
    by_policy = {policy: [row for row in records if row["policy"] == policy] for policy in ("U0", "A0", "A1")}
    policy_summary = {}
    for policy, group in by_policy.items():
        minima = [row["min_clearance_m"] for row in group]
        labels = [label(row) for row in group]
        policy_summary[policy] = {
            "episodes": len(group), "collision": labels.count("collision"), "near": labels.count("near"),
            "safe": labels.count("safe"), "danger": labels.count("collision") + labels.count("near"),
            "minimum_clearance_m": min(minima), "q25_minimum_clearance_m": percentile(minima, .25),
            "median_minimum_clearance_m": median(minima), "q75_minimum_clearance_m": percentile(minima, .75),
            "mean_minimum_clearance_m": mean(minima), "task_successes": sum(row["task_success"] for row in group),
            "mean_goal_progress_m": mean(row["goal_progress_m"] for row in group),
            "median_goal_progress_m": median(row["goal_progress_m"] for row in group),
            "mean_path_efficiency": mean(row["path_efficiency"] for row in group if row["path_efficiency"] is not None),
            "safety_value_adaptive_spends": sum(str(row["adaptive_reason"]).startswith("safety_value:") for row in group),
            "deadline_spends": sum(row["deadline_used"] for row in group),
            "unarmed_fallback_spends": sum(row["unarmed_fallback_used"] for row in group),
        }

    paired = []
    scenario_ids = sorted({row["scenario"] for row in records})
    for scenario in scenario_ids:
        rows = {policy: next(row for row in by_policy[policy] if row["scenario"] == scenario)
                for policy in ("U0", "A0", "A1")}
        arm_lead = (rows["A0"]["arm_step"] - rows["A1"]["arm_step"]
                    if rows["A0"]["arm_step"] is not None and rows["A1"]["arm_step"] is not None else None)
        paired.append({
            "scenario": scenario, "a0_arm_step": rows["A0"]["arm_step"], "a1_arm_step": rows["A1"]["arm_step"],
            "r1_arm_lead_steps": arm_lead, "a0_spend_step": rows["A0"]["spend_step"],
            "a1_spend_step": rows["A1"]["spend_step"], "a0_reason": rows["A0"]["adaptive_reason"],
            "a1_reason": rows["A1"]["adaptive_reason"],
            "a1_minus_a0_min_clearance_m": rows["A1"]["min_clearance_m"] - rows["A0"]["min_clearance_m"],
            "a1_minus_u0_min_clearance_m": rows["A1"]["min_clearance_m"] - rows["U0"]["min_clearance_m"],
            "a1_minus_a0_progress_m": rows["A1"]["goal_progress_m"] - rows["A0"]["goal_progress_m"],
        })

    event_records = []
    adaptive_packets = []
    for policy in ("A0", "A1"):
        for episode in by_policy[policy]:
            rows = load_trace(episode["scenario"], policy)
            future = [min(candidate["evaluator"]["clearance_m"] for candidate in rows[index:index + FUTURE_STEPS])
                      for index in range(len(rows))]
            for index, row in enumerate(rows):
                if row["safety_value"]["triggered"]:
                    event_records.append({
                        "scenario": episode["scenario"], "policy": policy, "step": row["step"],
                        "time_s": row["time_s"], "armed": row["policy_state"]["arm_step"] is not None,
                        "already_spent": row["policy_state"]["spend_step"] is not None,
                        "primary_reason": row["safety_value"]["primary_reason"],
                        "priority": row["safety_value"]["priority"],
                        "held_action": row["counterfactual"]["held_planner"]["selected_action_id"],
                        "current_action": row["counterfactual"]["current_planner"]["selected_action_id"],
                        "held_safe_count": row["safety_value"]["held_safe_count"],
                        "current_safe_count": row["safety_value"]["current_safe_count"],
                        "image_age_ms": row["counterfactual"]["held_image_age_before_decision_ms"],
                        "future_min_clearance_2s_m": future[index],
                        "future_physical_danger": future[index] <= NEAR,
                    })
                if row["communication"]["packet_role"] == "adaptive" and row["communication"]["transmitted"]:
                    adaptive_packets.append({
                        "scenario": episode["scenario"], "policy": policy, "step": row["step"],
                        "reason": row["communication"]["reason"], "r0": row["sender"]["r0"], "r1": row["sender"]["r1"],
                        "image_age_before_ms": row["counterfactual"]["held_image_age_before_decision_ms"],
                        "safety_value_at_send": row["safety_value"]["triggered"],
                        "future_min_clearance_2s_m": future[index],
                        "future_physical_danger": future[index] <= NEAR,
                    })

    safety_spends = [row for row in adaptive_packets if str(row["reason"]).startswith("safety_value:")]
    priority1_spends = [row for row in safety_spends if any(
        event["scenario"] == row["scenario"] and event["policy"] == row["policy"] and event["step"] == row["step"] and
        event["priority"] == 1 for event in event_records)]
    distractor_spends = [row for row in safety_spends if row["scenario"] == "q1-s09-visual-distractor"]
    narrow_spends = [row for row in safety_spends if row["scenario"] == "q1-s06-narrow-passage"]
    fallback_deadline_fraction = sum(row["reason"] in ("arm_deadline", "unarmed_fallback")
                                     for row in adaptive_packets) / len(adaptive_packets)
    mechanism = (len(safety_spends) >= 2 and len(priority1_spends) >= 1 and not distractor_spends and
                 len(narrow_spends) >= 1 and fallback_deadline_fraction <= .75)
    earlier_pairs = [row for row in paired if row["r1_arm_lead_steps"] is not None and row["r1_arm_lead_steps"] > 0]
    useful_predictive = any(row["policy"] == "A1" for row in safety_spends)
    predictive_value = len(earlier_pairs) >= 2 and useful_predictive
    a1, a0, u0 = policy_summary["A1"], policy_summary["A0"], policy_summary["U0"]
    task_ok = a1["task_successes"] >= max(a0["task_successes"], u0["task_successes"]) - 1
    safety_path_1 = (a1["danger"] <= a0["danger"] - 1 and a1["danger"] <= u0["danger"] - 1 and
                     a1["median_minimum_clearance_m"] >= a0["median_minimum_clearance_m"] - .005 and
                     a1["median_minimum_clearance_m"] >= u0["median_minimum_clearance_m"] - .005 and task_ok)
    safety_path_2 = (a1["danger"] <= a0["danger"] and a1["danger"] <= u0["danger"] and
                     a1["median_minimum_clearance_m"] >= a0["median_minimum_clearance_m"] + .01 and
                     a1["median_minimum_clearance_m"] >= u0["median_minimum_clearance_m"] + .01 and
                     a1["minimum_clearance_m"] >= a0["minimum_clearance_m"] + .01 and
                     a1["minimum_clearance_m"] >= u0["minimum_clearance_m"] + .01 and task_ok)
    if not mechanism:
        classification = "CASE D"
        classification_label = "Safety Decision Value trigger is inadequate"
    elif predictive_value and (safety_path_1 or safety_path_2):
        classification, classification_label = "CASE A", "Safety Decision Value + predictive task value"
    elif not predictive_value and a1["danger"] == a0["danger"] and abs(
            a1["median_minimum_clearance_m"] - a0["median_minimum_clearance_m"]) < .01:
        classification, classification_label = "CASE B", "Safety Decision Value works, R0/R1 tied"
    else:
        classification, classification_label = "CASE C", "Decision value works, safety outcome remains negative"

    true_value_examples = sorted([row for row in event_records if row["future_physical_danger"]],
                                 key=lambda row: (not row["already_spent"], row["future_min_clearance_2s_m"]))[:5]
    false_positive_examples = sorted([row for row in adaptive_packets if not row["safety_value_at_send"]],
                                     key=lambda row: -row["future_min_clearance_2s_m"])[:5]
    analysis = {
        "study_id": "cvc-q2-risk-arm-safety-value-spend-v1", "development_only": True, "formal": False,
        "readiness_manifest_sha256": sha(READINESS), "matrix_results_sha256": sha(MATRIX),
        "policy_summary": policy_summary, "paired_mechanism": paired,
        "adaptive_packets": adaptive_packets, "safety_value_events": event_records,
        "true_safety_value_examples": true_value_examples,
        "false_positive_or_non_value_packet_examples": false_positive_examples,
        "frozen_criteria": {
            "mechanism_pass": mechanism, "safety_value_spends": len(safety_spends),
            "priority1_spends": len(priority1_spends), "fallback_deadline_fraction": fallback_deadline_fraction,
            "predictive_value_pass": predictive_value, "r1_earlier_arm_pairs": len(earlier_pairs),
            "useful_predictive_safety_spend": useful_predictive,
            "safety_path_1_pass": safety_path_1, "safety_path_2_pass": safety_path_2, "task_guardrail_pass": task_ok,
        },
        "classification": classification, "classification_label": classification_label,
        "classification_basis": (
            "Zero adaptive packets were triggered by Safety Decision Value; all 20 used deadline or unarmed fallback. "
            "R1 armed earlier in three paired cells and A1 removed A0 contacts, but A1 still had five danger episodes "
            "versus U0's three, and the intended readiness-to-value-to-spend mechanism was absent."
        ),
        "safety_value_validated": False,
        "predictive_arm_engineering_safety_value": False,
        "broader_development_validation_justified": False,
        "ml_justified": False,
        "formal_justified": False,
        "next_experiment": (
            "Protocol-only temporal repair study: test a value-triggerable protected reserve and persistence/window "
            "semantics using these frozen traces, without changing the Q1 planner or training ML."
        ),
    }
    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (OUT / "episode_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["scenario", "policy", "collision", "min_clearance_m", "task_success", "goal_progress_m",
                  "arm_step", "safety_value_step", "spend_step", "adaptive_reason", "wire_bytes"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerows({name: row[name] for name in fields} for row in records)

    # Chart contract 1: composition + distribution, exact n=10/policy, static report artifact.
    policies = ["U0", "A0", "A1"]; x = range(3)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    safe = [policy_summary[p]["safe"] for p in policies]; near = [policy_summary[p]["near"] for p in policies]
    collision = [policy_summary[p]["collision"] for p in policies]
    axes[0].bar(x, safe, label="Safe", color="#4C78A8")
    axes[0].bar(x, near, bottom=safe, label="Near", color="#F2CF5B", hatch="//")
    axes[0].bar(x, collision, bottom=[safe[i] + near[i] for i in x], label="Collision", color="#D9D9D9", hatch="xx")
    axes[0].set_xticks(list(x), policies); axes[0].set_ylabel("Frozen cells (n=10)")
    axes[0].set_title("Physical safety labels by policy"); axes[0].legend(frameon=False)
    minima = [[row["min_clearance_m"] for row in by_policy[p]] for p in policies]
    axes[1].boxplot(minima, tick_labels=policies, showmeans=True)
    axes[1].axhline(NEAR, color="#7F6000", linestyle="--", label="Near boundary 0.12 m")
    axes[1].axhline(0, color="#333333", linewidth=.8); axes[1].set_ylabel("Episode minimum clearance (m)")
    axes[1].set_title("Minimum-clearance distributions"); axes[1].legend(frameon=False)
    fig.suptitle("CVC-Q2 frozen development outcomes (10 cells per policy)")
    fig.savefig(OUT / "figures" / "q2_safety_outcomes.png", dpi=180); plt.close(fig)

    # Chart contract 2: causal timing traces for the most informative narrow-passage pair.
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    colors = {"A0": "#4C78A8", "A1": "#E17C05"}
    for axis, policy in zip(axes, ("A0", "A1")):
        rows = load_trace("q1-s06-narrow-passage", policy)
        t = [row["time_s"] for row in rows]
        axis.plot(t, [row["sender"]["r0"] for row in rows], color="#777777", linestyle="--", label="R0")
        axis.plot(t, [row["sender"]["r1"] for row in rows], color=colors[policy], label="R1")
        axis2 = axis.twinx(); axis2.plot(t, [row["evaluator"]["clearance_m"] for row in rows], color="#222222", label="Clearance")
        episode = next(row for row in by_policy[policy] if row["scenario"] == "q1-s06-narrow-passage")
        if episode["arm_step"] is not None: axis.axvline(rows[episode["arm_step"]]["time_s"], color=colors[policy], linestyle=":", label="ARM")
        axis.axvline(rows[episode["spend_step"]]["time_s"], color="#8C2D04", linestyle="-.", label="Deadline SPEND")
        value_steps = [row["step"] for row in rows if row["safety_value"]["triggered"]]
        if value_steps: axis.axvline(rows[value_steps[0]]["time_s"], color="#7A5195", linestyle="--", label="First Safety Value")
        axis.set_ylabel(f"{policy} risk"); axis2.set_ylabel("Clearance (m)")
        axis.set_title(f"Narrow passage {policy}: readiness and forced spend")
        lines, labels0 = axis.get_legend_handles_labels(); lines2, labels2 = axis2.get_legend_handles_labels()
        axis.legend(lines + lines2, labels0 + labels2, frameon=False, ncol=5, loc="upper center")
    axes[-1].set_xlabel("Simulation time (s)")
    fig.savefig(OUT / "figures" / "q2_narrow_passage_causal_timing.png", dpi=180); plt.close(fig)

    # Chart contract 3: every adaptive packet cause, categorical count comparison.
    reasons = ["safety_value", "arm_deadline", "unarmed_fallback"]
    counts = {p: [sum((str(row["reason"]).startswith("safety_value:") if reason == "safety_value" else
                          row["reason"] == reason) for row in adaptive_packets if row["policy"] == p)
                  for reason in reasons] for p in ("A0", "A1")}
    fig, ax = plt.subplots(figsize=(8, 4.6), constrained_layout=True)
    positions = list(range(len(reasons))); width = .36
    ax.bar([p - width / 2 for p in positions], counts["A0"], width, label="A0", color="#4C78A8")
    ax.bar([p + width / 2 for p in positions], counts["A1"], width, label="A1", color="#E17C05", hatch="//")
    ax.set_xticks(positions, ["Safety Value", "ARM deadline", "Unarmed fallback"])
    ax.set_ylabel("Adaptive packets (n=10/policy)"); ax.set_title("Why each adaptive Q2 packet was sent")
    ax.legend(frameon=False); ax.set_ylim(0, 8)
    fig.savefig(OUT / "figures" / "q2_adaptive_packet_causes.png", dpi=180); plt.close(fig)

    # Chart contract 4: distractor-specific negative control.  This deliberately
    # shows the decision variables, not camera novelty, because Q2's claim is
    # that visually changing but decision-irrelevant content must not spend.
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, constrained_layout=True)
    for axis, policy in zip(axes, ("A0", "A1")):
        rows = load_trace("q1-s09-visual-distractor", policy)
        t = [row["time_s"] for row in rows]
        held = [row["safety_value"]["held_safe_count"] for row in rows]
        current = [row["safety_value"]["current_safe_count"] for row in rows]
        age = [row["counterfactual"]["held_image_age_before_decision_ms"] / 1000 for row in rows]
        axis.step(t, held, where="post", color="#4C78A8", label="HELD safe actions")
        axis.step(t, current, where="post", color="#E17C05", linestyle="--", label="CURRENT safe actions")
        axis2 = axis.twinx()
        axis2.plot(t, age, color="#777777", alpha=.65, label="HELD image age")
        episode = next(row for row in by_policy[policy] if row["scenario"] == "q1-s09-visual-distractor")
        axis.axvline(rows[episode["spend_step"]]["time_s"], color="#8C2D04", linestyle="-.",
                     label="Unarmed fallback SPEND")
        axis.set_ylabel(f"{policy} safe actions")
        axis2.set_ylabel("Image age (s)")
        axis.set_title(f"Distractor negative control {policy}: no Safety Value event")
        lines, labels0 = axis.get_legend_handles_labels(); lines2, labels2 = axis2.get_legend_handles_labels()
        axis.legend(lines + lines2, labels0 + labels2, frameon=False, ncol=4, loc="upper center")
    axes[-1].set_xlabel("Simulation time (s)")
    fig.savefig(OUT / "figures" / "q2_distractor_negative_control.png", dpi=180); plt.close(fig)
    print(json.dumps({"classification": classification, "policy_summary": policy_summary,
                      "criteria": analysis["frozen_criteria"]}, indent=2))


if __name__ == "__main__":
    main()
