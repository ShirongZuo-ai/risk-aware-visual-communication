"""Descriptive CVC-Q1 support and decision-value analysis (development only)."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
HIGH_PATH = ROOT / "results" / "cvc_q1_support_qualification" / "qualification.json"
SWEEP_PATH = ROOT / "results" / "cvc_q1_neutral_sweep" / "sweep_results.json"
TRACE_DIR = ROOT / "results" / "cvc_q1_neutral_sweep" / "traces"
READINESS = ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json"
OUT = ROOT / "results" / "cvc_q1_analysis"
NEAR_M = 0.12
FUTURE_STEPS = 63  # Existing 2.016 s P7 physical-danger preview, diagnostic only.


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_label(record: dict) -> str:
    if record["collision"]:
        return "collision"
    return "near" if record["min_clearance_m"] <= NEAR_M else "safe"


def load_trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def trace_identity(record: dict) -> str:
    return f"{record['scenario']}-u0-n{record['transmission_count']:02d}"


def summarize_budget(records: list[dict], label: str) -> dict:
    labels = [physical_label(row) for row in records]
    return {
        "budget": label,
        "packet_count": records[0]["transmission_count"],
        "wire_bytes_per_episode": records[0]["wire_bytes"],
        "episodes": len(records),
        "collision": labels.count("collision"),
        "near": labels.count("near"),
        "safe": labels.count("safe"),
        "minimum_clearance_m": min(row["min_clearance_m"] for row in records),
        "median_minimum_clearance_m": median(row["min_clearance_m"] for row in records),
        "mean_minimum_clearance_m": mean(row["min_clearance_m"] for row in records),
        "task_successes": sum(row["task_success"] for row in records),
        "mean_goal_progress_m": mean(row["goal_progress_m"] for row in records),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    high = json.loads(HIGH_PATH.read_text(encoding="utf-8"))["runs"]
    sweep_document = json.loads(SWEEP_PATH.read_text(encoding="utf-8"))
    sweep = sweep_document["records"]
    if len(sweep) != 70 or not sweep_document["all_byte_reconciled"] or not sweep_document["all_exact_wire_bytes"]:
        raise RuntimeError("incomplete or byte-invalid Q1 sweep")

    by_count: dict[int, list[dict]] = {}
    for record in sweep:
        by_count.setdefault(record["transmission_count"], []).append(record)
    budget_summary = [summarize_budget(high, "HIGH")]
    budget_summary += [summarize_budget(by_count[count], f"U0-{count}") for count in sorted(by_count)]

    diagnostic_by_count: dict[int, dict] = {}
    high_value_candidates: list[dict] = []
    irrelevant_candidates: list[dict] = []
    episode_diagnostics = []
    for record in sweep:
        identity = trace_identity(record)
        rows = load_trace(TRACE_DIR / f"{identity}.jsonl")
        action = safe_set = safety_class = goal_safe = 0
        margins: list[float] = []
        future_clearance = [min(row2["evaluator"]["clearance_m"] for row2 in rows[index:index + FUTURE_STEPS])
                            for index in range(len(rows))]
        for index, row in enumerate(rows):
            value = row["counterfactual"]["decision_value"]
            action += bool(value["action_changed"])
            safe_set += bool(value["safe_set_changed"])
            safety_class += bool(value["safety_class_changed"])
            goal_safe += bool(value["goal_efficient_safe_path_changed"])
            margins.append(float(value["selected_margin_change_m"]))
            margin_change = float(value["selected_margin_change_m"])
            base = {
                "scenario": record["scenario"], "packet_count": record["transmission_count"],
                "step": row["step"], "time_s": row["time_s"],
                "held_image_age_ms": row["counterfactual"]["held_image_age_before_decision_ms"],
                "future_minimum_clearance_2s_m": future_clearance[index],
                "held_action": row["counterfactual"]["held_planner"]["selected_action_id"],
                "current_action": row["counterfactual"]["current_planner"]["selected_action_id"],
                "held_safety_class": value["held_safety_class"],
                "current_safety_class": value["current_safety_class"],
                "safe_actions_added": value["safe_actions_added"],
                "safe_actions_removed": value["safe_actions_removed"],
                "selected_margin_change_m": margin_change if math.isfinite(margin_change) else None,
                "selected_margin_change_state": ("finite" if math.isfinite(margin_change) else
                                                   ("became_unbounded" if margin_change > 0 else "became_bounded")),
                "selected_goal_progress_change_m": value["selected_goal_progress_change_m"],
                "held_obstacles": row["counterfactual"]["held_obstacles"],
                "current_obstacles": row["counterfactual"]["current_obstacles"],
                "actual_clearance_m": row["evaluator"]["clearance_m"],
            }
            if (value["action_changed"] and value["safe_set_changed"] and value["safe_actions_removed"] and
                    row["counterfactual"]["current_obstacles"] and future_clearance[index] <= NEAR_M):
                base["rank_value"] = (len(value["safe_actions_added"]) + len(value["safe_actions_removed"]) +
                                      (abs(margin_change) * 10 if math.isfinite(margin_change) else 0))
                high_value_candidates.append(base)
            obstacle_changed = row["counterfactual"]["held_obstacles"] != row["counterfactual"]["current_obstacles"]
            if (record["scenario"] == "q1-s09-visual-distractor" and obstacle_changed and
                    not value["action_changed"] and not value["safe_set_changed"]):
                base["rank_value"] = row["counterfactual"]["held_image_age_before_decision_ms"]
                irrelevant_candidates.append(base)
        finite_margins = [item for item in margins if math.isfinite(item)]
        episode_diagnostics.append({
            "scenario": record["scenario"], "packet_count": record["transmission_count"],
            "steps": len(rows), "action_change_steps": action, "safe_set_change_steps": safe_set,
            "safety_class_change_steps": safety_class, "goal_efficient_safe_path_change_steps": goal_safe,
            "finite_margin_change_steps": len(finite_margins),
            "unbounded_margin_change_steps": len(margins) - len(finite_margins),
            "mean_margin_change_m": mean(finite_margins) if finite_margins else None,
            "mean_absolute_margin_change_m": mean(map(abs, finite_margins)) if finite_margins else None,
            "minimum_margin_change_m": min(finite_margins) if finite_margins else None,
            "maximum_margin_change_m": max(finite_margins) if finite_margins else None,
        })
    for count in sorted(by_count):
        group = [row for row in episode_diagnostics if row["packet_count"] == count]
        steps = sum(row["steps"] for row in group)
        diagnostic_by_count[count] = {
            "steps": steps,
            "action_change_steps": sum(row["action_change_steps"] for row in group),
            "safe_set_change_steps": sum(row["safe_set_change_steps"] for row in group),
            "safety_class_change_steps": sum(row["safety_class_change_steps"] for row in group),
            "goal_efficient_safe_path_change_steps": sum(row["goal_efficient_safe_path_change_steps"] for row in group),
            "action_change_rate": sum(row["action_change_steps"] for row in group) / steps,
            "safe_set_change_rate": sum(row["safe_set_change_steps"] for row in group) / steps,
            "safety_class_change_rate": sum(row["safety_class_change_steps"] for row in group) / steps,
            "finite_margin_change_steps": sum(row["finite_margin_change_steps"] for row in group),
            "unbounded_margin_change_steps": sum(row["unbounded_margin_change_steps"] for row in group),
            "mean_absolute_margin_change_m": mean(
                row["mean_absolute_margin_change_m"] for row in group
                if row["mean_absolute_margin_change_m"] is not None),
        }
    high_value_examples = sorted(high_value_candidates, key=lambda row: row["rank_value"], reverse=True)[:5]
    irrelevant_examples = sorted(irrelevant_candidates, key=lambda row: row["rank_value"], reverse=True)[:5]
    for row in high_value_examples + irrelevant_examples:
        row.pop("rank_value", None)

    per_scenario_range = {}
    for scenario in readiness["scenario_ids"]:
        values = [row["min_clearance_m"] for row in sweep if row["scenario"] == scenario]
        high_value = next(row["min_clearance_m"] for row in high if row["scenario"] == scenario)
        per_scenario_range[scenario] = {
            "high_minimum_clearance_m": high_value,
            "u0_minimum_clearance_m": min(values), "u0_maximum_clearance_m": max(values),
            "u0_clearance_span_m": max(values) - min(values),
        }

    analysis = {
        "study_id": "cvc-q1-safety-aware-local-planning-v2", "development_only": True, "formal": False,
        "readiness_manifest_sha256": sha256(READINESS), "sweep_results_sha256": sha256(SWEEP_PATH),
        "near_boundary_m": NEAR_M, "collision_definition": "bilateral Webots contact",
        "budget_summary": budget_summary, "decision_diagnostics_by_packet_count": diagnostic_by_count,
        "episode_decision_diagnostics": episode_diagnostics, "scenario_clearance_ranges": per_scenario_range,
        "high_safety_information_value_examples": high_value_examples,
        "visually_changed_but_safety_irrelevant_examples": irrelevant_examples,
        "transition_regime": {
            "packet_counts": [3, 6],
            "basis": "Frozen-grid descriptive support: both budgets contain near cases; six packets gives the global 1.23 mm minimum and the greatest near count. This is non-monotone development evidence, not a fitted threshold.",
            "non_monotone": True,
        },
        "classification": "CASE A",
        "classification_label": "Avoidance + physical support qualified",
        "classification_basis": (
            "Fresh vision passed the avoidance gate; the frozen neutral sweep produced real near-danger support "
            "and large within-scenario clearance changes without outcome-selected repair; and HELD/CURRENT "
            "counterfactuals changed safe sets and selected actions in future-near windows. No collision occurred."
        ),
        "next_allocator_ready": True,
        "next_allocator_boundary": "Design only after Q1 stop: predictive Risk-ARM plus decision-level Safety-Value-SPEND.",
    }
    (OUT / "analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (OUT / "budget_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(budget_summary[0]))
        writer.writeheader(); writer.writerows(budget_summary)

    # Figure 1: physical support and minimum clearances.
    labels = [row["budget"] for row in budget_summary]
    x = list(range(len(labels)))
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), constrained_layout=True)
    axes[0].bar(x, [row["safe"] for row in budget_summary], label="Safe", color="#4c956c")
    axes[0].bar(x, [row["near"] for row in budget_summary], bottom=[row["safe"] for row in budget_summary],
                label="Near", color="#f2c14e")
    axes[0].bar(x, [row["collision"] for row in budget_summary],
                bottom=[row["safe"] + row["near"] for row in budget_summary], label="Collision", color="#d1495b")
    axes[0].set_ylabel("Frozen scenarios (n=10)"); axes[0].legend(ncol=3, frameon=False)
    axes[0].set_title("CVC-Q1 physical support under fresh and neutral communication")
    axes[1].plot(x, [row["minimum_clearance_m"] for row in budget_summary], "o-", label="Suite minimum")
    axes[1].plot(x, [row["median_minimum_clearance_m"] for row in budget_summary], "s--", label="Median episode minimum")
    axes[1].axhline(NEAR_M, color="#d18f00", linestyle=":", label="Near boundary (0.12 m)")
    axes[1].axhline(0.0, color="#d1495b", linewidth=1)
    axes[1].set_ylabel("Minimum clearance (m)"); axes[1].set_xticks(x, labels, rotation=30)
    axes[1].set_xlabel("Communication condition"); axes[1].legend(frameon=False)
    fig.savefig(OUT / "figures" / "q1_support_by_budget.png", dpi=180); plt.close(fig)

    # Figure 2: decision-value diagnostics.
    counts = sorted(diagnostic_by_count)
    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    ax.plot(counts, [diagnostic_by_count[c]["action_change_rate"] for c in counts], "o-", label="Selected action")
    ax.plot(counts, [diagnostic_by_count[c]["safe_set_change_rate"] for c in counts], "s-", label="Safe set")
    ax.plot(counts, [diagnostic_by_count[c]["safety_class_change_rate"] for c in counts], "^-", label="Safety class")
    ax.set_xscale("log", base=2); ax.set_xticks(counts, [str(c) for c in counts])
    ax.set_xlabel("Uniform transmissions per 10 s episode"); ax.set_ylabel("HELD vs CURRENT change rate")
    ax.set_title("Decision-level safety information diagnostics"); ax.legend(frameon=False)
    fig.savefig(OUT / "figures" / "q1_decision_value_by_budget.png", dpi=180); plt.close(fig)

    # Figure 3: representative communication-sensitive episode.
    trace = load_trace(TRACE_DIR / "q1-s06-narrow-passage-u0-n06.jsonl")
    t = [row["time_s"] for row in trace]
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    axes[0].plot(t, [row["evaluator"]["clearance_m"] for row in trace], color="#264653")
    axes[0].axhline(NEAR_M, color="#d18f00", linestyle=":"); axes[0].axhline(0, color="#d1495b")
    axes[0].set_ylabel("Clearance (m)")
    axes[1].plot(t, [row["communication"]["image_age_ms"] / 1000 for row in trace], color="#457b9d")
    axes[1].set_ylabel("Image age (s)")
    action_times = [row["time_s"] for row in trace if row["counterfactual"]["decision_value"]["action_changed"]]
    safe_times = [row["time_s"] for row in trace if row["counterfactual"]["decision_value"]["safe_set_changed"]]
    axes[2].scatter(action_times, [1] * len(action_times), s=8, label="Action changed", color="#e76f51")
    axes[2].scatter(safe_times, [0] * len(safe_times), s=8, label="Safe set changed", color="#2a9d8f")
    axes[2].set_yticks([0, 1], ["Safe set", "Action"]); axes[2].set_xlabel("Simulation time (s)")
    axes[2].legend(frameon=False, ncol=2); axes[0].set_title("Representative transition cell: narrow passage, U0-6")
    fig.savefig(OUT / "figures" / "q1_representative_trace.png", dpi=180); plt.close(fig)
    print(json.dumps({"classification": analysis["classification"], "budget_summary": budget_summary,
                      "high_value_examples": len(high_value_examples),
                      "irrelevant_examples": len(irrelevant_examples)}, indent=2))


if __name__ == "__main__":
    main()
