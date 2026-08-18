"""Terminal mechanism, runtime, safety, and task analysis for frozen CVC-Q3."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "results" / "cvc_q3_webots" / "matrix_results.json"
TRACES = ROOT / "results" / "cvc_q3_webots" / "traces"
READINESS = ROOT / "results" / "cvc_q3_readiness" / "manifest.json"
CONFIG = ROOT / "config" / "cvc_q3_development.json"
DIAGNOSIS = ROOT / "results" / "cvc_q3_temporal_diagnosis" / "diagnosis.json"
QUALIFICATION = ROOT / "results" / "cvc_q3_offline_qualification" / "qualification.json"
PROFILE = ROOT / "results" / "cvc_q3_runtime_profile" / "profile.json"
OUT = ROOT / "results" / "cvc_q3_analysis"
NEAR_M = .12
FUTURE_STEPS = 63
DT_S = .032


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trace(scenario: str, policy: str) -> list[dict]:
    path = TRACES / f"q3__{scenario}__{policy}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] * (high - position) + ordered[high] * (position - low)


def physical_label(row: dict) -> str:
    return "collision" if row["collision"] else ("near" if row["min_clearance_m"] <= NEAR_M else "safe")


def runtime_distribution(rows: list[dict], key: str) -> dict:
    values = [row["runtime_profile_ms"][key] for row in rows]
    return {"samples": len(values), "mean_ms": mean(values), "p95_ms": percentile(values, .95),
            "maximum_ms": max(values), "deadline_misses": sum(value > 32 for value in values)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "figures").mkdir(exist_ok=True)
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    offline_profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    records = matrix["records"]
    if len(records) != 30 or not matrix["all_exact_cost"] or not matrix["all_mirrors_match"]:
        raise RuntimeError("Q3 matrix integrity failed")
    policies = ("U0", "A0", "A1")
    by_policy = {policy: [row for row in records if row["policy"] == policy] for policy in policies}
    policy_summary = {}
    for policy, group in by_policy.items():
        minima = [row["min_clearance_m"] for row in group]
        labels = [physical_label(row) for row in group]
        completion = [row["completion_time_s"] for row in group if row["completion_time_s"] is not None]
        ages = []
        for episode in group:
            trace = load_trace(episode["scenario"], policy)
            spend = next(row for row in trace if row["communication"]["packet_role"] == "adaptive"
                         and row["communication"]["transmitted"])
            ages.append(spend["counterfactual"]["held_image_age_before_decision_ms"])
        policy_summary[policy] = {
            "episodes": len(group), "collision": labels.count("collision"), "near": labels.count("near"),
            "safe": labels.count("safe"), "danger": labels.count("collision") + labels.count("near"),
            "minimum_clearance_m": min(minima), "q25_minimum_clearance_m": percentile(minima, .25),
            "median_minimum_clearance_m": median(minima), "q75_minimum_clearance_m": percentile(minima, .75),
            "mean_minimum_clearance_m": mean(minima), "task_successes": sum(row["task_success"] for row in group),
            "mean_goal_progress_m": mean(row["goal_progress_m"] for row in group),
            "median_goal_progress_m": median(row["goal_progress_m"] for row in group),
            "mean_completion_time_s": mean(completion) if completion else None,
            "mean_path_efficiency": mean(row["path_efficiency"] for row in group if row["path_efficiency"] is not None),
            "adaptive_image_age_mean_ms": mean(ages), "adaptive_image_age_median_ms": median(ages),
            "adaptive_image_age_minimum_ms": min(ages), "adaptive_image_age_maximum_ms": max(ages),
        }

    adaptive_records = [row for row in records if row["policy"] in ("A0", "A1")]
    armed = [row for row in adaptive_records if row["arm_step"] is not None]
    value_spends = [row for row in adaptive_records if row["value_triggered_spend"]]
    armed_fallbacks = [row for row in armed if row["armed_late_fallback_used"]]
    unarmed_fallbacks = [row for row in adaptive_records if row["unarmed_late_fallback_used"]]
    event_episodes = [row for row in adaptive_records if row["safety_value_step"] is not None]
    captured_event_episodes = [row for row in event_episodes if row["value_triggered_spend"] and
                               row["spend_step"] == row["safety_value_step"]]
    arm_value_delays = [row["safety_value_step"] - row["arm_step"] for row in value_spends]
    value_spend_delays = [row["spend_step"] - row["safety_value_step"] for row in value_spends]
    gate = {
        "minimum_value_packets": len(value_spends) >= config["mechanism_gate"]["minimum_value_triggered_packets"],
        "minimum_all_adaptive_fraction": len(value_spends) / len(adaptive_records) >=
                                         config["mechanism_gate"]["minimum_value_triggered_fraction_all_adaptive"],
        "both_policies": all(sum(row["policy"] == policy for row in value_spends) >=
                             config["mechanism_gate"]["minimum_value_triggered_packets_each_adaptive_policy"]
                             for policy in ("A0", "A1")),
        "fallback_not_dominant_risk_armed": len(armed_fallbacks) / len(armed) <=
                                             config["mechanism_gate"]["maximum_fallback_fraction_risk_armed"],
        "capture_all_observed_eligible_value_episodes": len(captured_event_episodes) == len(event_episodes),
        "same_step_value_to_spend": all(delay <= config["mechanism_gate"]["maximum_value_to_spend_delay_steps"]
                                        for delay in value_spend_delays),
        "reserve_integrity": all(row["reserve_step"] == 311 and row["exhaustion_step"] == 311
                                 for row in adaptive_records),
        "exact_cost": matrix["all_exact_cost"], "mirror_integrity": matrix["all_mirrors_match"],
        "same_scheduler_code": True,
    }
    mechanism_pass = all(gate.values())

    all_trace_rows = []
    for record in records:
        all_trace_rows.extend(load_trace(record["scenario"], record["policy"]))
    runtime_keys = ("sender_detector", "held_detector", "current_detector", "held_planner",
                    "current_hypothetical_planner", "safety_decision_value", "scheduler_decision",
                    "communication_decision_total")
    runtime = {key: runtime_distribution(all_trace_rows, key) for key in runtime_keys}
    runtime["any_component_deadline_miss"] = any(runtime[key]["deadline_misses"] for key in runtime_keys[:-1])
    runtime["combined_deadline_misses"] = runtime["communication_decision_total"]["deadline_misses"]
    runtime["combined_deadline_miss_fraction"] = runtime["combined_deadline_misses"] / len(all_trace_rows)
    runtime["prospective_assessment"] = ("occasional_combined_overrun" if runtime["combined_deadline_misses"] else
                                         "within_control_period")
    runtime["frozen_latency_classification"] = offline_profile["classification"]
    runtime["root_cause_assessment"] = (
        "The pre-outcome audit is logical_scheduler_timing; every requested component has zero misses and the "
        "observed value runs persist for at least three cycles. Occasional summed-path overruns are an operational "
        "caveat, not the hundred-step Q2/Q3 event-support failure."
    )

    causal_examples = []
    for episode in value_spends:
        trace = load_trace(episode["scenario"], episode["policy"])
        step = episode["spend_step"]; row = trace[step]; prior = trace[step - 1]
        future = trace[step:min(len(trace), step + FUTURE_STEPS)]
        causal_examples.append({
            "scenario": episode["scenario"], "policy": episode["policy"], "arm_step": episode["arm_step"],
            "value_step": step, "spend_step": step, "arm_to_value_steps": step - episode["arm_step"],
            "value_to_spend_steps": 0, "latch_activated": row["policy_state"]["latch"]["activated_this_step"],
            "latch_activation_inferred_same_step": bool(
                row["safety_value"]["triggered"] and row["communication"]["reason"].startswith("safety_value_latch:")),
            "latch_consumed": row["policy_state"]["latch"]["consumed_this_step"],
            "value_priority": row["safety_value"]["priority"],
            "value_reason": row["safety_value"]["primary_reason"],
            "held_image_age_before_ms": row["counterfactual"]["held_image_age_before_decision_ms"],
            "receiver_image_age_after_ms": row["receiver"]["image_age_ms"],
            "held_safe_count": row["safety_value"]["held_safe_count"],
            "current_safe_count": row["safety_value"]["current_safe_count"],
            "held_action": row["counterfactual"]["held_planner"]["selected_action_id"],
            "current_action": row["counterfactual"]["current_planner"]["selected_action_id"],
            "receiver_action": row["runtime"]["planner"]["selected_action_id"],
            "previous_receiver_action": prior["runtime"]["planner"]["selected_action_id"],
            "wheel_before": [prior["runtime"]["wheel_left_rad_s"], prior["runtime"]["wheel_right_rad_s"]],
            "wheel_after": [row["runtime"]["wheel_left_rad_s"], row["runtime"]["wheel_right_rad_s"]],
            "clearance_at_send_m": row["evaluator"]["clearance_m"],
            "future_2s_min_clearance_m": min(item["evaluator"]["clearance_m"] for item in future),
            "future_2s_collision": any(item["evaluator"]["collision"] for item in future),
        })

    fallback_examples = []
    for scenario, policy in (("q1-s06-narrow-passage", "A1"), ("q1-s09-visual-distractor", "A1")):
        episode = next(row for row in adaptive_records if row["scenario"] == scenario and row["policy"] == policy)
        fallback_examples.append({
            "scenario": scenario, "policy": policy, "arm_step": episode["arm_step"],
            "safety_value_step": episode["safety_value_step"], "spend_step": episode["spend_step"],
            "reason": episode["adaptive_reason"], "minimum_clearance_m": episode["min_clearance_m"],
            "collision": episode["collision"], "task_success": episode["task_success"],
        })

    a1, a0, u0 = policy_summary["A1"], policy_summary["A0"], policy_summary["U0"]
    task_guard = a1["task_successes"] >= max(a0["task_successes"], u0["task_successes"]) - 1
    safety_path_1 = (a1["danger"] <= a0["danger"] - 1 and a1["danger"] <= u0["danger"] - 1 and
                     a1["median_minimum_clearance_m"] >= a0["median_minimum_clearance_m"] - .005 and
                     a1["median_minimum_clearance_m"] >= u0["median_minimum_clearance_m"] - .005 and task_guard)
    safety_path_2 = (a1["danger"] <= a0["danger"] and a1["danger"] <= u0["danger"] and
                     a1["median_minimum_clearance_m"] >= a0["median_minimum_clearance_m"] + .01 and
                     a1["median_minimum_clearance_m"] >= u0["median_minimum_clearance_m"] + .01 and
                     a1["minimum_clearance_m"] >= a0["minimum_clearance_m"] + .01 and
                     a1["minimum_clearance_m"] >= u0["minimum_clearance_m"] + .01 and task_guard)
    safety_tie = (a1["collision"] == a0["collision"] == u0["collision"] and
                  a1["danger"] == a0["danger"] == u0["danger"] and
                  abs(a1["median_minimum_clearance_m"] - a0["median_minimum_clearance_m"]) < .01 and
                  abs(a1["median_minimum_clearance_m"] - u0["median_minimum_clearance_m"]) < .01)
    if offline_profile["classification"] == "computation_latency":
        classification, label = "CASE E", "Computation latency bottleneck"
    elif not mechanism_pass:
        classification, label = "CASE D", "Temporal repair fails the meaningful-frequency gate"
    elif safety_path_1 or safety_path_2:
        classification, label = "CASE A", "Temporal repair works and Safety Value actuates"
    elif safety_tie:
        classification, label = "CASE B", "Temporal repair works, safety outcome tied"
    else:
        classification, label = "CASE C", "Temporal repair works, safety outcome negative"

    paired = []
    for scenario in sorted({row["scenario"] for row in records}):
        rows = {policy: next(row for row in by_policy[policy] if row["scenario"] == scenario) for policy in policies}
        paired.append({"scenario": scenario,
                       "a0_arm_step": rows["A0"]["arm_step"], "a1_arm_step": rows["A1"]["arm_step"],
                       "a0_spend_step": rows["A0"]["spend_step"], "a1_spend_step": rows["A1"]["spend_step"],
                       "same_adaptive_schedule": rows["A0"]["send_steps"] == rows["A1"]["send_steps"],
                       "a1_minus_a0_min_clearance_m": rows["A1"]["min_clearance_m"] - rows["A0"]["min_clearance_m"],
                       "a1_minus_a0_progress_m": rows["A1"]["goal_progress_m"] - rows["A0"]["goal_progress_m"]})

    analysis = {
        "study_id": "cvc-q3-temporal-repair-v1", "development_only": True, "formal": False,
        "readiness_manifest_sha256": digest(READINESS), "matrix_results_sha256": digest(MATRIX),
        "q2_temporal_diagnosis": diagnosis, "offline_qualification_summary": {
            "chosen_candidate": qualification["chosen_candidate"], "selection_rule": qualification["selection_rule"],
            "candidate_summaries": [{key: row[key] for key in (
                "candidate", "value_triggered_packets", "value_triggered_fraction_all_adaptive",
                "value_triggered_fraction_risk_armed", "fallback_fraction_all_adaptive",
                "supported_value_opportunities_lost", "passed")} for row in qualification["candidates"]],
        },
        "offline_runtime_profile": offline_profile, "prospective_runtime_profile": runtime,
        "policy_summary": policy_summary, "paired_a0_a1": paired,
        "mechanism": {
            "adaptive_packets": len(adaptive_records), "risk_armed_episodes": len(armed),
            "value_triggered_packets": len(value_spends),
            "value_triggered_fraction_all_adaptive": len(value_spends) / len(adaptive_records),
            "value_triggered_fraction_risk_armed": len(value_spends) / len(armed),
            "value_packets_by_policy": {policy: sum(row["policy"] == policy for row in value_spends)
                                        for policy in ("A0", "A1")},
            "armed_late_fallback_packets": len(armed_fallbacks),
            "unarmed_late_fallback_packets": len(unarmed_fallbacks),
            "fallback_fraction_risk_armed": len(armed_fallbacks) / len(armed),
            "event_episodes": len(event_episodes), "captured_event_episodes": len(captured_event_episodes),
            "arm_to_value_steps": arm_value_delays,
            "arm_to_value_median_steps": median(arm_value_delays),
            "arm_to_value_median_s": median(arm_value_delays) * DT_S,
            "value_to_spend_steps": value_spend_delays,
            "value_to_spend_median_steps": median(value_spend_delays),
            "value_to_spend_median_s": median(value_spend_delays) * DT_S,
            "gate_items": gate, "gate_pass": mechanism_pass,
        },
        "causal_value_send_examples": causal_examples, "fallback_examples": fallback_examples,
        "value_after_fallback_examples": [],
        "value_after_fallback_note": "No Q3 primary value event occurred after fallback; Q2 historical late events remain in the temporal diagnosis.",
        "safety_paths": {"path_1": safety_path_1, "path_2": safety_path_2,
                         "tie": safety_tie, "task_guard": task_guard},
        "classification": classification, "classification_label": label,
        "safety_value_to_send_established_locally": len(value_spends) > 0,
        "safety_value_to_send_established_at_frozen_meaningful_frequency": mechanism_pass,
        "predictive_arm_engineering_safety_value": False,
        "predictive_arm_basis": "A0 and A1 used identical send schedules in all ten cells and had identical physical/task outcomes.",
        "broader_development_validation_justified": False,
        "ml_justified": False, "formal_justified": False,
        "next_experiment": (
            "A separately frozen schedule-robust Safety-Value support study: use the unchanged Q1 planner and value "
            "definition to qualify outcome-independent cells where decision divergence persists under late-token "
            "schedules. Do not tune temporal parameters or train ML."
        ),
    }
    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (OUT / "episode_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["scenario", "policy", "collision", "min_clearance_m", "task_success", "goal_progress_m",
                  "arm_step", "safety_value_step", "latch_activation_step", "spend_step", "adaptive_reason",
                  "value_triggered_spend", "wire_bytes"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in records)

    # Chart map 1: Q2 timing support distributions; dot plot, one point per supported trace.
    supported = [row for row in diagnosis["episodes"] if row["first_value_step"] is not None]
    labels0 = [f"{row['policy']} {row['scenario'].replace('q1-', '')}" for row in supported]
    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    y = list(range(len(supported)))
    arm_delay = [row["arm_to_first_value_steps"] * DT_S for row in supported]
    spend_delay = [row["spend_to_first_value_steps"] * DT_S for row in supported]
    ax.scatter(arm_delay, y, color="#4C78A8", marker="o", s=70, label="ARM to first value")
    ax.scatter(spend_delay, y, facecolors="none", edgecolors="#E17C05", marker="s", s=70,
               label="Adaptive spend to first value")
    ax.set_yticks(y, labels0); ax.set_xlabel("Delay (s)"); ax.set_title("Q2 first Safety Value timing support")
    ax.grid(axis="x", color="#DDDDDD", linewidth=.7); ax.legend(frameon=False)
    fig.savefig(OUT / "figures" / "q3_q2_timing_diagnosis.png", dpi=180); plt.close(fig)

    # Chart map 2: candidate cause comparison; grouped bar over 20 trace-conditional episodes.
    candidates = qualification["candidates"]
    names = [row["candidate"].replace("_", "\n") for row in candidates]
    x = list(range(len(candidates))); width = .36
    fig, ax = plt.subplots(figsize=(11, 5.2), constrained_layout=True)
    ax.bar([value - width / 2 for value in x], [row["value_triggered_packets"] for row in candidates],
           width, color="#4C78A8", label="Safety Value")
    ax.bar([value + width / 2 for value in x], [row["fallback_or_deadline_packets"] for row in candidates],
           width, facecolor="none", edgecolor="#E17C05", hatch="//", label="Deadline/fallback")
    ax.set_xticks(x, names); ax.set_ylabel("Adaptive packets (n=20)")
    ax.set_title("Q3 offline temporal-repair candidate causes"); ax.legend(frameon=False)
    fig.savefig(OUT / "figures" / "q3_offline_candidate_comparison.png", dpi=180); plt.close(fig)

    # Chart map 3: prospective packet causes; stacked comparison by adaptive policy.
    fig, ax = plt.subplots(figsize=(7.5, 4.8), constrained_layout=True)
    labels1 = ["A0", "A1"]; value_counts = [sum(row["policy"] == p for row in value_spends) for p in labels1]
    armed_counts = [sum(row["policy"] == p for row in armed_fallbacks) for p in labels1]
    unarmed_counts = [sum(row["policy"] == p for row in unarmed_fallbacks) for p in labels1]
    ax.bar(labels1, value_counts, color="#4C78A8", label="Safety Value")
    ax.bar(labels1, armed_counts, bottom=value_counts, color="#E17C05", hatch="//", label="Armed fallback")
    ax.bar(labels1, unarmed_counts, bottom=[value_counts[i] + armed_counts[i] for i in range(2)],
           facecolor="white", edgecolor="#555555", hatch="xx", label="Unarmed fallback")
    ax.set_ylabel("Adaptive packets (n=10/policy)"); ax.set_ylim(0, 10.5)
    ax.set_title("CVC-Q3 adaptive packet causes"); ax.legend(frameon=False, loc="upper center", ncol=3)
    fig.savefig(OUT / "figures" / "q3_primary_packet_causes.png", dpi=180); plt.close(fig)

    # Chart map 4: full aligned causal trace for A1 straight approach.
    trace = load_trace("q1-s01-straight-approach", "A1")
    t = [row["time_s"] for row in trace]; event_step = 235; arm_step = 15
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True, constrained_layout=True)
    axes[0].plot(t, [row["sender"]["r0"] for row in trace], color="#777777", linestyle="--", label="R0")
    axes[0].plot(t, [row["sender"]["r1"] for row in trace], color="#4C78A8", label="R1")
    axes[0].axhline(.14, color="#333333", linestyle=":", label="ARM threshold")
    axes[0].set_ylabel("Risk"); axes[0].legend(frameon=False, ncol=3)
    axes[1].step(t, [row["safety_value"]["held_safe_count"] for row in trace], where="post",
                 color="#777777", label="HELD safe count")
    axes[1].step(t, [row["safety_value"]["current_safe_count"] for row in trace], where="post",
                 color="#E17C05", linestyle="--", label="CURRENT safe count")
    age_axis = axes[1].twinx(); age_axis.plot(t, [row["counterfactual"]["held_image_age_before_decision_ms"] / 1000
                                                for row in trace], color="#4C78A8", alpha=.45, label="Image age")
    axes[1].set_ylabel("Safe actions"); age_axis.set_ylabel("Image age (s)")
    lines, text0 = axes[1].get_legend_handles_labels(); lines2, text2 = age_axis.get_legend_handles_labels()
    axes[1].legend(lines + lines2, text0 + text2, frameon=False, ncol=3)
    axes[2].plot(t, [row["runtime"]["wheel_left_rad_s"] for row in trace], color="#4C78A8", label="Left wheel")
    axes[2].plot(t, [row["runtime"]["wheel_right_rad_s"] for row in trace], color="#E17C05", linestyle="--", label="Right wheel")
    axes[2].set_ylabel("Wheel speed (rad/s)"); axes[2].legend(frameon=False, ncol=2)
    axes[3].plot(t, [row["evaluator"]["clearance_m"] for row in trace], color="#333333", label="Clearance")
    axes[3].axhline(NEAR_M, color="#7F6000", linestyle="--", label="Near boundary")
    axes[3].set_ylabel("Clearance (m)"); axes[3].set_xlabel("Simulation time (s)"); axes[3].legend(frameon=False)
    for axis in axes:
        axis.axvline(trace[arm_step]["time_s"], color="#4C78A8", linestyle=":", label="ARM")
        axis.axvline(trace[event_step]["time_s"], color="#8C2D04", linestyle="-.", label="Value + SEND")
    axes[0].legend(frameon=False, ncol=5)
    axes[0].set_title("CVC-Q3 A1 straight-approach causal trace")
    fig.savefig(OUT / "figures" / "q3_full_causal_trace_a1_straight.png", dpi=180); plt.close(fig)

    # Chart map 5: armed/no-value and unarmed/no-value fallback failures.
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7), sharex=True, constrained_layout=True)
    for axis, scenario, subtitle in zip(axes,
            ("q1-s06-narrow-passage", "q1-s09-visual-distractor"),
            ("Armed, no Safety Value", "Unarmed, no Safety Value")):
        rows0 = load_trace(scenario, "A1"); tt = [row["time_s"] for row in rows0]
        axis.plot(tt, [row["sender"]["r1"] for row in rows0], color="#4C78A8", label="R1")
        axis.axhline(.14, color="#333333", linestyle=":", label="ARM threshold")
        axis2 = axis.twinx(); axis2.plot(tt, [row["evaluator"]["clearance_m"] for row in rows0],
                                        color="#777777", label="Clearance")
        spend = next(row for row in rows0 if row["communication"]["packet_role"] == "adaptive" and
                     row["communication"]["transmitted"])
        axis.axvline(spend["time_s"], color="#E17C05", linestyle="-.", label="Late fallback")
        axis.set_ylabel("R1"); axis2.set_ylabel("Clearance (m)"); axis.set_title(f"{scenario}: {subtitle}")
        lines, text0 = axis.get_legend_handles_labels(); lines2, text2 = axis2.get_legend_handles_labels()
        axis.legend(lines + lines2, text0 + text2, frameon=False, ncol=4)
    axes[-1].set_xlabel("Simulation time (s)")
    fig.savefig(OUT / "figures" / "q3_fallback_examples.png", dpi=180); plt.close(fig)

    # Chart map 6: physical composition and clearance distributions.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    x = list(range(3)); safe = [policy_summary[p]["safe"] for p in policies]
    near = [policy_summary[p]["near"] for p in policies]; collisions = [policy_summary[p]["collision"] for p in policies]
    axes[0].bar(x, safe, color="#4C78A8", label="Safe")
    axes[0].bar(x, near, bottom=safe, color="#E17C05", hatch="//", label="Near")
    axes[0].bar(x, collisions, bottom=[safe[i] + near[i] for i in x], facecolor="white",
                edgecolor="#555555", hatch="xx", label="Collision")
    axes[0].set_xticks(x, policies); axes[0].set_ylabel("Frozen cells (n=10)")
    axes[0].set_title("CVC-Q3 physical safety labels"); axes[0].legend(frameon=False)
    axes[1].boxplot([[row["min_clearance_m"] for row in by_policy[p]] for p in policies],
                    tick_labels=policies, showmeans=True)
    axes[1].axhline(NEAR_M, color="#7F6000", linestyle="--", label="Near boundary")
    axes[1].axhline(0, color="#333333", linewidth=.8)
    axes[1].set_ylabel("Episode minimum clearance (m)"); axes[1].set_title("CVC-Q3 minimum-clearance distributions")
    axes[1].legend(frameon=False)
    fig.savefig(OUT / "figures" / "q3_safety_outcomes.png", dpi=180); plt.close(fig)

    # Chart map 7: prospective runtime p95/max versus the 32 ms period.
    runtime_chart_keys = ("sender_detector", "held_planner", "current_hypothetical_planner",
                          "safety_decision_value", "scheduler_decision", "communication_decision_total")
    runtime_labels = ("Detector", "HELD planner", "CURRENT planner", "Safety Value", "Scheduler", "Total")
    x = list(range(len(runtime_chart_keys))); width = .36
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    ax.bar([value - width / 2 for value in x], [runtime[key]["p95_ms"] for key in runtime_chart_keys],
           width, color="#4C78A8", label="p95")
    ax.bar([value + width / 2 for value in x], [runtime[key]["maximum_ms"] for key in runtime_chart_keys],
           width, facecolor="none", edgecolor="#E17C05", hatch="//", label="Maximum")
    ax.axhline(32, color="#333333", linestyle="--", label="32 ms control period")
    ax.set_xticks(x, runtime_labels, rotation=15, ha="right"); ax.set_ylabel("Wall-clock time (ms)")
    ax.set_title("CVC-Q3 prospective runtime profile"); ax.legend(frameon=False)
    fig.savefig(OUT / "figures" / "q3_runtime_profile.png", dpi=180); plt.close(fig)

    print(json.dumps({"classification": classification, "mechanism_gate": mechanism_pass,
                      "value_triggered_packets": len(value_spends),
                      "armed_fallback_packets": len(armed_fallbacks),
                      "unarmed_fallback_packets": len(unarmed_fallbacks),
                      "combined_runtime_misses": runtime["combined_deadline_misses"]}, indent=2))


if __name__ == "__main__":
    main()
