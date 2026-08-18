"""Analyze the single frozen CVC-P6 Webots development comparison."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "cvc_p6_webots"
P4_MATRIX = ROOT / "results" / "cvc_p4_webots" / "matrix_summary.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def cumulative_step(values: list[float], probability: float) -> int | None:
    if not 0.0 < probability < 1.0 or any(value < 0 or not math.isfinite(value) for value in values):
        raise ValueError("invalid cumulative signal")
    total = sum(values)
    if total <= 0:
        return None
    target, running = total * probability, 0.0
    for step, value in enumerate(values):
        running += value
        if running >= target:
            return step
    return len(values) - 1


def signal_timing(values: list[float]) -> dict:
    peak = max(values)
    return {"q25_step": cumulative_step(values, 0.25), "q50_step": cumulative_step(values, 0.5),
            "q75_step": cumulative_step(values, 0.75), "peak_step": values.index(peak),
            "peak_value": peak, "total": sum(values)}


def pre_danger_window(rows: list[dict], threshold_m: float = 0.12, width_steps: int = 63) -> tuple[int, int, str]:
    danger = next((int(row["step"]) for row in rows if row["evaluator"]["clearance_m"] < threshold_m), None)
    if danger is None:
        end = min(range(len(rows)), key=lambda index: rows[index]["evaluator"]["clearance_m"])
        reason = "minimum_clearance"
    else:
        end, reason = danger, "first_clearance_below_0.12m"
    return max(0, end - width_steps + 1), end, reason


def age_summary(rows: list[dict]) -> dict:
    ages = [float(row["receiver"]["image_age_ms"]) for row in rows]
    start, end, reason = pre_danger_window(rows)
    pre = ages[start:end + 1]
    return {"overall_mean_ms": statistics.mean(ages), "overall_maximum_ms": max(ages),
            "pre_danger_mean_ms": statistics.mean(pre), "pre_danger_maximum_ms": max(pre),
            "pre_danger_start_step": start, "pre_danger_end_step": end,
            "pre_danger_endpoint_reason": reason}


def result_case(mechanism_works: bool, a0: dict, a1: dict) -> tuple[str, str]:
    if not mechanism_works:
        return "CASE D", "Task-novelty gate itself fails"
    if a1["collisions"] <= a0["collisions"] and a1["task_successes"] > a0["task_successes"]:
        return "CASE A", "Mechanism + task benefit"
    if a1["collisions"] == a0["collisions"] and a1["task_successes"] == a0["task_successes"]:
        return "CASE B", "Mechanism works, task result tied"
    return "CASE C", "Mechanism works but A1 remains worse"


def main() -> None:
    matrix = json.loads((RESULTS / "matrix_summary.json").read_text(encoding="utf-8"))
    p4 = json.loads(P4_MATRIX.read_text(encoding="utf-8"))
    p4_runs = {(row["scenario"], row["policy"]): row for row in p4["runs"]}
    summaries = {(row["scenario"], row["policy"]): row for row in matrix["runs"]}
    episodes = []
    representatives = {}
    for path in sorted((RESULTS / "traces").glob("p6__*.jsonl")):
        _, scenario, policy = path.stem.split("__")
        rows = read_jsonl(path)
        summary = summaries[(scenario, policy)]
        signals = {
            "visual_mae": [float(row["counterfactual"]["visual"]["pixel_mae"]) for row in rows],
            "perception_combined": [float(row["counterfactual"]["perception"]["combined_l2"]) for row in rows],
            "control_l2": [float(row["counterfactual"]["control"]["control_l2"]) for row in rows],
        }
        timing = {name: signal_timing(values) for name, values in signals.items()}
        spend = int(summary["adaptive_step"])
        arm = summary["arm_step"]
        p4_spend = int(p4_runs[(scenario, policy)]["adaptive_step"])
        episode = {
            **summary, "p4_immediate_step": p4_spend,
            "arm_to_spend_steps": spend - arm if arm is not None else None,
            "p6_minus_p4_spend_steps": spend - p4_spend,
            "signal_timing": timing,
            "spend_to_visual_q25_steps": timing["visual_mae"]["q25_step"] - spend,
            "spend_to_perception_q25_steps": timing["perception_combined"]["q25_step"] - spend,
            "spend_to_control_q25_steps": timing["control_l2"]["q25_step"] - spend,
            "spend_to_perception_peak_steps": timing["perception_combined"]["peak_step"] - spend,
            "spend_to_control_peak_steps": timing["control_l2"]["peak_step"] - spend,
            "control_at_spend": signals["control_l2"][spend],
            "control_at_arm": signals["control_l2"][arm] if arm is not None else None,
            "novelty_at_spend": rows[spend]["task_novelty"],
            "image_age": age_summary(rows),
        }
        episodes.append(episode)
        if scenario in ("center_large", "left_offset", "two_component") and policy == "A1":
            key_steps = sorted(set(value for value in (
                0, arm, spend, timing["perception_combined"]["q25_step"],
                timing["control_l2"]["q25_step"], timing["control_l2"]["peak_step"], 218
            ) if value is not None))
            representatives[scenario] = [{
                "step": step, "r0": rows[step]["sender"]["r0"], "r1": rows[step]["sender"]["r1"],
                "state": rows[step]["policy_state"]["state"],
                "task_novelty_event": rows[step]["task_novelty"]["event"],
                "task_novelty_reasons": rows[step]["task_novelty"]["event_reasons"],
                "delta_bearing": rows[step]["task_novelty"]["delta_bearing"],
                "delta_proximity": rows[step]["task_novelty"]["delta_proximity"],
                "delta_area_relative": rows[step]["task_novelty"]["delta_area_relative"],
                "transmitted": rows[step]["communication"]["transmitted"],
                "packet_role": rows[step]["communication"]["packet_role"],
                "image_age_ms": rows[step]["receiver"]["image_age_ms"],
                "perception_combined": signals["perception_combined"][step],
                "control_l2": signals["control_l2"][step],
                "left_rad_s": rows[step]["control"]["left_rad_s"],
                "right_rad_s": rows[step]["control"]["right_rad_s"],
                "clearance_m": rows[step]["evaluator"]["clearance_m"],
                "contact": rows[step]["evaluator"]["contact"],
            } for step in key_steps]

    policy_summary = {}
    for policy in ("U0", "A0", "A1"):
        selected = [row for row in episodes if row["policy"] == policy]
        policy_summary[policy] = {
            "episodes": len(selected), "collisions": sum(row["collision"] for row in selected),
            "task_successes": sum(row["task_success"] for row in selected),
            "mean_minimum_clearance_m": statistics.mean(row["min_clearance_m"] for row in selected),
            "mean_clearance_m": statistics.mean(row["mean_clearance_m"] for row in selected),
            "mean_forward_progress_m": statistics.mean(row["forward_progress_m"] for row in selected),
            "mean_path_length_m": statistics.mean(row["path_length_m"] for row in selected),
            "mean_overall_image_age_ms": statistics.mean(row["image_age"]["overall_mean_ms"] for row in selected),
            "mean_pre_danger_image_age_ms": statistics.mean(row["image_age"]["pre_danger_mean_ms"] for row in selected),
            "maximum_pre_danger_image_age_ms": max(row["image_age"]["pre_danger_maximum_ms"] for row in selected),
            "deadline_uses": sum(row["deadline_used"] for row in selected),
            "reserve_uses": sum(row["reserve_step"] == 218 for row in selected),
        }
    a1 = [row for row in episodes if row["policy"] == "A1"]
    pairs = []
    for scenario in sorted({row["scenario"] for row in episodes}):
        a0_row, a1_row = summaries[(scenario, "A0")], summaries[(scenario, "A1")]
        pairs.append({
            "scenario": scenario, "schedules_equal": a0_row["send_steps"] == a1_row["send_steps"],
            "a0_send_steps": a0_row["send_steps"], "a1_send_steps": a1_row["send_steps"],
            "a1_minus_a0_minimum_clearance_m": a1_row["min_clearance_m"] - a0_row["min_clearance_m"],
            "a1_minus_a0_mean_clearance_m": a1_row["mean_clearance_m"] - a0_row["mean_clearance_m"],
            "a1_minus_a0_forward_progress_m": a1_row["forward_progress_m"] - a0_row["forward_progress_m"],
            "a0_task_success": a0_row["task_success"], "a1_task_success": a1_row["task_success"],
            "a0_collision": a0_row["collision"], "a1_collision": a1_row["collision"],
        })
    delayed = sum(row["arm_to_spend_steps"] is not None and row["arm_to_spend_steps"] > 0 for row in a1)
    moved_closer_perception = sum(
        abs(row["spend_to_perception_q25_steps"]) <
        abs(row["signal_timing"]["perception_combined"]["q25_step"] - row["p4_immediate_step"])
        for row in a1)
    moved_closer_control = sum(
        abs(row["spend_to_control_q25_steps"]) <
        abs(row["signal_timing"]["control_l2"]["q25_step"] - row["p4_immediate_step"])
        for row in a1)
    mechanism_works = (
        delayed >= 4 and moved_closer_perception >= 4 and
        all(row["wire_bytes"] == 72000 and row["reserve_step"] == 218 for row in episodes) and
        all(row["mirror_all_steps_match"] for row in episodes)
    )
    classification, label = result_case(mechanism_works, policy_summary["A0"], policy_summary["A1"])
    clearance_deltas = [row["a1_minus_a0_minimum_clearance_m"] for row in pairs]
    aggregate = {
        "mechanism_works": mechanism_works, "a1_delayed_spend_count": delayed,
        "a1_immediate_spend_count": 6 - delayed,
        "a1_moved_closer_to_perception_q25_count": moved_closer_perception,
        "a1_moved_closer_to_control_q25_count": moved_closer_control,
        "a0_a1_schedule_collapse_count": sum(row["schedules_equal"] for row in pairs),
        "a1_arm_to_spend_steps": [row["arm_to_spend_steps"] for row in a1],
        "a1_arm_to_spend_median_steps": statistics.median(row["arm_to_spend_steps"] for row in a1),
        "a1_deadline_use_count": sum(row["deadline_used"] for row in a1),
        "a1_reserve_use_count": sum(row["reserve_step"] == 218 for row in a1),
        "a1_clearance_wins_losses_ties": {
            "wins": sum(value > 1e-12 for value in clearance_deltas),
            "losses": sum(value < -1e-12 for value in clearance_deltas),
            "ties": sum(abs(value) <= 1e-12 for value in clearance_deltas),
        },
        "classification": classification, "classification_label": label,
        "predictive_risk_engineering_task_value": (
            "supported_for_task_completion_and_progress_in_this development set; not supported for safety clearance"
            if classification == "CASE A" else "not demonstrated"),
        "broader_development_validation_justified": classification == "CASE A",
        "c4_c5_confirmatory_justified": False,
    }
    report = {
        "development_only": True, "formal": False, "single_frozen_comparison": True,
        "new_configuration_search_after_outcomes": False,
        "policy_summary": policy_summary, "episodes": episodes, "a0_a1_pairs": pairs,
        "aggregate": aggregate, "representative_a1_traces": representatives,
    }
    (RESULTS / "development_analysis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fields = ["scenario", "policy", "arm_step", "adaptive_step", "adaptive_reason", "arm_to_spend_steps",
              "p4_immediate_step", "spend_to_perception_q25_steps", "spend_to_control_q25_steps",
              "spend_to_control_peak_steps", "deadline_used", "collision", "task_success",
              "min_clearance_m", "mean_clearance_m", "forward_progress_m", "path_length_m"]
    with (RESULTS / "episode_analysis.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in episodes)
    print(json.dumps({"aggregate": aggregate, "policy_summary": policy_summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
