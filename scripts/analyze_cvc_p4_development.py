"""Post-gate CVC-P4 reserve, image-age, control, and outcome diagnostics."""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "cvc_p4_webots"
CRUISE = 5.0
PRE_DANGER_STEPS = 63  # Approximately 2.0 seconds at 32 ms.


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def first_divergence(left: list[dict], right: list[dict], predicate) -> int | None:
    return next((a["step"] for a, b in zip(left, right) if predicate(a, b)), None)


def episode_diagnostics(rows: list[dict], summary: dict) -> dict:
    danger = next((row["step"] for row in rows if row["evaluator"]["clearance_m"] < 0.12), None)
    minimum = min(range(len(rows)), key=lambda step: rows[step]["evaluator"]["clearance_m"])
    anchor = danger if danger is not None else minimum
    window = rows[max(0, anchor - PRE_DANGER_STEPS):anchor + 1]
    avoidance = next((row["step"] for row in rows
                      if abs(row["control"]["left_rad_s"] - row["control"]["right_rad_s"]) > 0.25
                      or (row["control"]["left_rad_s"] + row["control"]["right_rad_s"]) / 2 < CRUISE - 0.25), None)
    material_change = next((rows[index]["step"] for index in range(1, len(rows))
                            if (abs(rows[index]["control"]["left_rad_s"] - rows[index - 1]["control"]["left_rad_s"])
                                + abs(rows[index]["control"]["right_rad_s"] - rows[index - 1]["control"]["right_rad_s"])) / 2 > 0.25), None)
    send_rows = [row for row in rows if row["communication"]["transmitted"]]
    return {
        "scenario": summary["scenario"], "policy": summary["policy"],
        "collision": summary["collision"],
        "task_success": (not summary["collision"]) and summary["forward_progress_m"] >= 0.5,
        "minimum_clearance_m": summary["min_clearance_m"], "mean_clearance_m": summary["mean_clearance_m"],
        "adaptive_step": summary["adaptive_step"], "reserve_step": summary["reserve_step"],
        "budget_exhaustion_step": summary["budget_exhaustion_step"], "send_steps": summary["send_steps"],
        "overall_mean_image_age_ms": statistics.mean(row["receiver"]["image_age_ms"] for row in rows),
        "overall_max_image_age_ms": max(row["receiver"]["image_age_ms"] for row in rows),
        "danger_onset_step": danger, "minimum_clearance_step": minimum,
        "pre_danger_anchor": "danger_onset" if danger is not None else "minimum_clearance",
        "pre_danger_window_start_step": window[0]["step"], "pre_danger_window_end_step": window[-1]["step"],
        "pre_danger_mean_image_age_ms": statistics.mean(row["receiver"]["image_age_ms"] for row in window),
        "pre_danger_max_image_age_ms": max(row["receiver"]["image_age_ms"] for row in window),
        "first_avoidance_command_step": avoidance,
        "image_age_at_first_avoidance_ms": rows[avoidance]["receiver"]["image_age_ms"] if avoidance is not None else None,
        "first_material_control_change_step": material_change,
        "image_age_at_first_material_control_change_ms": (rows[material_change]["receiver"]["image_age_ms"]
                                                          if material_change is not None else None),
        "time_from_last_frame_to_danger_s": rows[danger]["receiver"]["image_age_ms"] / 1000 if danger is not None else None,
        "reserve_available_after_adaptive": (send_rows[1]["communication"]["tokens_after"] == 1
                                              and send_rows[1]["communication"]["reserve_locked"]),
        "component_accounting_valid": all(
            row["communication"]["content_bytes"] + row["communication"]["metadata_bytes"]
            + row["communication"]["padding_bytes"] == row["communication"]["wire_bytes"]
            for row in send_rows
        ),
    }


def main() -> None:
    matrix = json.loads((RESULTS / "matrix_summary.json").read_text(encoding="utf-8"))
    summaries = {(row["scenario"], row["policy"]): row for row in matrix["runs"]}
    traces = {}
    for path in sorted((RESULTS / "traces").glob("matrix__*.jsonl")):
        _, scenario, policy = path.stem.split("__")
        traces[(scenario, policy)] = read_jsonl(path)
    diagnostics = [episode_diagnostics(traces[key], summaries[key]) for key in sorted(traces)]
    scenarios = sorted({key[0] for key in traces})
    method_summary = []
    for policy in ("U0", "A0", "A1"):
        group = [row for row in diagnostics if row["policy"] == policy]
        method_summary.append({
            "policy": policy, "episodes": len(group), "collisions": sum(row["collision"] for row in group),
            "task_successes": sum(row["task_success"] for row in group),
            "minimum_clearance_m": min(row["minimum_clearance_m"] for row in group),
            "mean_episode_minimum_clearance_m": statistics.mean(row["minimum_clearance_m"] for row in group),
            "mean_clearance_m": statistics.mean(row["mean_clearance_m"] for row in group),
            "mean_overall_image_age_ms": statistics.mean(row["overall_mean_image_age_ms"] for row in group),
            "mean_pre_danger_image_age_ms": statistics.mean(row["pre_danger_mean_image_age_ms"] for row in group),
            "maximum_pre_danger_image_age_ms": max(row["pre_danger_max_image_age_ms"] for row in group),
            "budget_exhaustion_steps": sorted({row["budget_exhaustion_step"] for row in group}),
        })
    pairs = []
    for scenario in scenarios:
        a0, a1 = traces[(scenario, "A0")], traces[(scenario, "A1")]
        d0 = next(row for row in diagnostics if row["scenario"] == scenario and row["policy"] == "A0")
        d1 = next(row for row in diagnostics if row["scenario"] == scenario and row["policy"] == "A1")
        t0 = next((row["step"] for row in a0 if row["communication"]["trigger_event"]), None)
        t1 = next((row["step"] for row in a1 if row["communication"]["trigger_event"]), None)
        prediction_lead = t0 - t1 if t0 is not None and t1 is not None else None
        communication_lead = d0["adaptive_step"] - d1["adaptive_step"]
        first_perception = first_divergence(a0, a1, lambda x, y: (
            x["perception"]["detected"] != y["perception"]["detected"]
            or x["perception"]["bearing"] != y["perception"]["bearing"]
            or abs(x["perception"]["proximity"] - y["perception"]["proximity"]) > 1e-12))
        first_control = first_divergence(a0, a1, lambda x, y: (
            abs(x["control"]["left_rad_s"] - y["control"]["left_rad_s"]) > 1e-12
            or abs(x["control"]["right_rad_s"] - y["control"]["right_rad_s"]) > 1e-12))
        first_trajectory = first_divergence(a0, a1, lambda x, y: math.hypot(
            x["evaluator"]["x_m"] - y["evaluator"]["x_m"],
            x["evaluator"]["y_m"] - y["evaluator"]["y_m"]) > 1e-9)
        perception_difference = 0
        wheel_divergence = []
        trajectory_divergence = []
        for x, y in zip(a0, a1):
            perception_difference += (x["perception"]["detected"] != y["perception"]["detected"]
                                      or x["perception"]["bearing"] != y["perception"]["bearing"]
                                      or abs(x["perception"]["proximity"] - y["perception"]["proximity"]) > 1e-12)
            wheel_divergence.append((abs(x["control"]["left_rad_s"] - y["control"]["left_rad_s"])
                                     + abs(x["control"]["right_rad_s"] - y["control"]["right_rad_s"])) / 2)
            trajectory_divergence.append(math.hypot(x["evaluator"]["x_m"] - y["evaluator"]["x_m"],
                                                     x["evaluator"]["y_m"] - y["evaluator"]["y_m"]))
        pairs.append({
            "scenario": scenario, "a0_send_steps": d0["send_steps"], "a1_send_steps": d1["send_steps"],
            "prediction_lead_steps": prediction_lead, "communication_lead_steps": communication_lead,
            "communication_lead_s": communication_lead * 0.032,
            "lead_conversion": communication_lead / prediction_lead if prediction_lead not in (None, 0) else None,
            "reserve_step_a0": d0["reserve_step"], "reserve_step_a1": d1["reserve_step"],
            "reserve_available_after_adaptive_a0": d0["reserve_available_after_adaptive"],
            "reserve_available_after_adaptive_a1": d1["reserve_available_after_adaptive"],
            "budget_exhaustion_step_a0": d0["budget_exhaustion_step"],
            "budget_exhaustion_step_a1": d1["budget_exhaustion_step"],
            "starvation_fixed": (d0["reserve_step"] == d1["reserve_step"] == 218
                                 and d0["budget_exhaustion_step"] == d1["budget_exhaustion_step"] == 218),
            "a1_minus_a0_overall_mean_image_age_ms": d1["overall_mean_image_age_ms"] - d0["overall_mean_image_age_ms"],
            "a1_minus_a0_pre_danger_mean_image_age_ms": d1["pre_danger_mean_image_age_ms"] - d0["pre_danger_mean_image_age_ms"],
            "a1_reduces_pre_danger_image_age": d1["pre_danger_mean_image_age_ms"] < d0["pre_danger_mean_image_age_ms"],
            "a0_time_last_frame_to_danger_s": d0["time_from_last_frame_to_danger_s"],
            "a1_time_last_frame_to_danger_s": d1["time_from_last_frame_to_danger_s"],
            "first_perception_divergence_step": first_perception,
            "first_control_divergence_step": first_control,
            "first_trajectory_divergence_step": first_trajectory,
            "perception_difference_fraction": perception_difference / len(a0),
            "mean_wheel_command_divergence_rad_s": statistics.mean(wheel_divergence),
            "max_trajectory_divergence_m": max(trajectory_divergence),
            "a0_collision": d0["collision"], "a1_collision": d1["collision"],
            "a0_task_success": d0["task_success"], "a1_task_success": d1["task_success"],
            "a1_minus_a0_minimum_clearance_m": d1["minimum_clearance_m"] - d0["minimum_clearance_m"],
            "a1_minus_a0_mean_clearance_m": d1["mean_clearance_m"] - d0["mean_clearance_m"],
        })
    a0 = next(row for row in method_summary if row["policy"] == "A0")
    a1 = next(row for row in method_summary if row["policy"] == "A1")
    schedules_distinct = all(row["a0_send_steps"] != row["a1_send_steps"] for row in pairs)
    clearance_wins = sum(row["a1_minus_a0_minimum_clearance_m"] > 1e-6 for row in pairs)
    clearance_losses = sum(row["a1_minus_a0_minimum_clearance_m"] < -1e-6 for row in pairs)
    benefit = ((a1["collisions"] < a0["collisions"] and a1["task_successes"] >= a0["task_successes"])
               or (a1["task_successes"] > a0["task_successes"] and a1["collisions"] <= a0["collisions"])
               or (clearance_wins >= 4 and clearance_wins > clearance_losses))
    worse = (a1["collisions"] > a0["collisions"] or a1["task_successes"] < a0["task_successes"]
             or (clearance_losses >= 4 and clearance_losses > clearance_wins))
    if not schedules_distinct:
        case, classification = "D", "allocator_qualification_failed"
    elif worse:
        case, classification = "C", "predictive_timing_poorly_aligned_with_task_value"
    elif benefit:
        case, classification = "A", "predictive_risk_has_development_engineering_task_value"
    else:
        case, classification = "B", "actionable_but_still_no_demonstrated_task_value"
    report = {
        "development_only": True, "formal": False,
        "exact_cost_match": matrix["exact_cost_match"] and all(row["component_accounting_valid"] for row in diagnostics),
        "pre_danger_definition": "63-step (~2 s) window ending at first clearance <0.12 m; if absent, ending at minimum-clearance step.",
        "avoidance_command_definition": "First decoded wheel command with differential magnitude >0.25 rad/s or mean speed >0.25 rad/s below cruise.",
        "avoidance_command_caveat": "The first-avoidance diagnostic occurs at startup in every episode and is non-discriminating; the preserved secondary diagnostic is the first >0.25 rad/s step-to-step material command change.",
        "episode_diagnostics": diagnostics, "method_summary": method_summary, "a0_a1_pairs": pairs,
        "clearance_wins_losses_ties": {"wins": clearance_wins, "losses": clearance_losses,
                                         "ties": len(pairs) - clearance_wins - clearance_losses},
        "p3_starvation_fixed_all_pairs": all(row["starvation_fixed"] for row in pairs),
        "result_case": case, "classification": classification,
        "c4_c5_confirmatory_justified": (case == "A" and clearance_wins >= 4
                                          and (a1["collisions"] < a0["collisions"]
                                               or a1["task_successes"] > a0["task_successes"])),
    }
    (RESULTS / "development_analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
