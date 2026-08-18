"""Summarize the frozen CVC-P2 development matrix without inferential claims."""
from __future__ import annotations

from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_perception import VisualObstacle, visual_wheel_command


RESULTS = ROOT / "results" / "cvc_p2_development"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def main() -> None:
    sweep_path = RESULTS / "u0_sweep_summary.json"
    sweep_runs = json.loads(sweep_path.read_text(encoding="utf-8"))["runs"]
    ceiling_runs = [row for row in sweep_runs if row["transmissions"] >= 3]
    ceiling_path = RESULTS / "u0_sweep_v1_ceiling_summary.json"
    if not ceiling_path.exists():
        ceiling_path.write_text(json.dumps({"development_only": True, "failure": "all tested U0 budgets remained ceilinged",
                                            "runs": ceiling_runs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ceiling_selection_path = RESULTS / "u0_selection_v1_ceiling.json"
    if not ceiling_selection_path.exists():
        ceiling_selection_path.write_text(json.dumps({"eligible": False, "selected_transmissions": None,
                                                       "criterion": "U0 collisions only; initial 88/44/22/11/6/3 sweep"},
                                                      indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matrix = json.loads((RESULTS / "matrix_summary.json").read_text(encoding="utf-8"))
    runs = matrix["runs"]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in runs:
        grouped[(run["mechanism"], run["risk_signal"])].append(run)

    method_rows = []
    for (mechanism, risk), group in sorted(grouped.items()):
        method_rows.append({
            "mechanism": mechanism, "risk_signal": risk, "episodes": len(group),
            "wire_bytes_per_episode": sorted({row["wire_bytes"] for row in group}),
            "collisions": sum(bool(row["collision"]) for row in group),
            "physical_failures": sum(bool(row["collision"]) or row["min_clearance_m"] < 0.12 for row in group),
            "minimum_clearance_m": min(row["min_clearance_m"] for row in group),
            "mean_minimum_clearance_m": mean([row["min_clearance_m"] for row in group]),
            "mean_forward_progress_m": mean([row["forward_progress_m"] for row in group]),
            "mean_image_age_ms": mean([row["mean_image_age_ms"] for row in group]),
            "mean_detection_fraction": mean([row["detection_fraction"] for row in group]),
        })

    paired_rows = []
    for mechanism in ("T", "S", "TS"):
        for scenario in sorted({row["scenario"] for row in runs}):
            r0 = next(row for row in runs if row["mechanism"] == mechanism and row["risk_signal"] == "R0" and row["scenario"] == scenario)
            r1 = next(row for row in runs if row["mechanism"] == mechanism and row["risk_signal"] == "R1" and row["scenario"] == scenario)
            paired_rows.append({
                "scenario": scenario, "mechanism": mechanism,
                "r1_minus_r0_min_clearance_m": r1["min_clearance_m"] - r0["min_clearance_m"],
                "r1_minus_r0_progress_m": r1["forward_progress_m"] - r0["forward_progress_m"],
                "r1_minus_r0_collisions": int(r1["collision"]) - int(r0["collision"]),
            })

    trace_rows = []
    episode_mechanistic: dict[tuple[str, str, str], dict] = {}
    accounting_valid = True
    for trace_path in sorted((RESULTS / "traces").glob("matrix__*.jsonl")):
        rows = read_jsonl(trace_path)
        first = rows[0]
        sent = [row for row in rows if row["communication"]["transmitted"]]
        first_danger = next((row for row in rows if row["evaluator"]["clearance_m"] < 0.12), None)
        first_collision = next((row for row in rows if row["evaluator"]["collision"]), None)
        r0_warning = next((row for row in rows if row["sender"]["r0"] >= 0.16), None)
        r1_warning = next((row for row in rows if row["sender"]["r1"] >= 0.16), None)
        wire_sum = sum(row["communication"]["wire_bytes"] for row in rows)
        component_sum = sum(row["communication"]["content_bytes"] + row["communication"]["metadata_bytes"] + row["communication"]["padding_bytes"] for row in sent)
        accounting_valid &= wire_sum == component_sum == 72000 and len(sent) == 2
        path_length = sum(math.hypot(b["evaluator"]["x_m"] - a["evaluator"]["x_m"],
                                     b["evaluator"]["y_m"] - a["evaluator"]["y_m"])
                          for a, b in zip(rows, rows[1:]))
        displacement = math.hypot(rows[-1]["evaluator"]["x_m"] - rows[0]["evaluator"]["x_m"],
                                  rows[-1]["evaluator"]["y_m"] - rows[0]["evaluator"]["y_m"])
        completion = next((row for row in rows if row["evaluator"]["x_m"] - rows[0]["evaluator"]["x_m"] >= 0.5), None)
        bearing_errors = []
        proximity_errors = []
        command_divergences = []
        for row in rows:
            sender_bearing = row["sender"]["bearing"]
            receiver_bearing = row["perception"]["bearing"]
            if sender_bearing is not None and receiver_bearing is not None:
                bearing_errors.append(abs(sender_bearing - receiver_bearing))
            proximity_errors.append(abs(row["sender"]["proximity"] - row["perception"]["proximity"]))
            reference = VisualObstacle(sender_bearing is not None, sender_bearing, row["sender"]["proximity"], None, 0)
            ref_left, ref_right = visual_wheel_command(reference, 5.0)
            command_divergences.append((abs(ref_left - row["control"]["left_rad_s"]) +
                                        abs(ref_right - row["control"]["right_rad_s"])) / 2)
        pre_danger_bytes = sum(row["communication"]["wire_bytes"] for row in rows
                               if first_danger is None or row["step"] < first_danger["step"])
        trace_row = {
            "scenario": first["scenario"], "mechanism": first["mechanism"], "risk_signal": first["risk_signal"],
            "transmission_steps": [row["step"] for row in sent],
            "transmission_reasons": [row["communication"]["reason"] for row in sent],
            "selected_risk_at_transmission": [row["sender"]["selected_risk"] for row in sent],
            "quality_ranges": [[row["communication"]["quality_min"], row["communication"]["quality_max"]] for row in sent],
            "first_clearance_below_0_12_step": first_danger["step"] if first_danger else None,
            "first_collision_step": first_collision["step"] if first_collision else None,
            "r0_warning_step": r0_warning["step"] if r0_warning else None,
            "r1_warning_step": r1_warning["step"] if r1_warning else None,
            "risk_warning_lead_steps_r1_before_r0": ((r0_warning["step"] - r1_warning["step"])
                                                       if r0_warning and r1_warning else None),
            "bytes_before_danger": pre_danger_bytes,
            "mean_abs_bearing_error": mean(bearing_errors) if bearing_errors else None,
            "mean_abs_proximity_error": mean(proximity_errors),
            "mean_wheel_command_divergence_rad_s": mean(command_divergences),
            "task_success": not any(row["evaluator"]["collision"] for row in rows) and completion is not None,
            "near_miss": first_danger is not None,
            "completion_time_s": completion["time_s"] if completion else None,
            "path_efficiency": displacement / path_length if path_length else 0.0,
            "wire_bytes_from_trace": wire_sum,
        }
        trace_rows.append(trace_row)
        episode_mechanistic[(first["scenario"], first["mechanism"], first["risk_signal"])] = trace_row

    for row in method_rows:
        relevant = [value for (scenario, mechanism, risk), value in episode_mechanistic.items()
                    if mechanism == row["mechanism"] and risk == row["risk_signal"]]
        row["task_successes"] = sum(value["task_success"] for value in relevant)
        row["near_misses"] = sum(value["near_miss"] for value in relevant)
        row["mean_path_efficiency"] = mean([value["path_efficiency"] for value in relevant])
        row["mean_abs_bearing_error"] = mean([value["mean_abs_bearing_error"] for value in relevant
                                               if value["mean_abs_bearing_error"] is not None])
        row["mean_abs_proximity_error"] = mean([value["mean_abs_proximity_error"] for value in relevant])
        row["mean_wheel_command_divergence_rad_s"] = mean(
            [value["mean_wheel_command_divergence_rad_s"] for value in relevant]
        )

    r1_clearance_deltas = [row["r1_minus_r0_min_clearance_m"] for row in paired_rows]
    r1_collision_deltas = [row["r1_minus_r0_collisions"] for row in paired_rows]
    conclusion = {
        "classification": "negative_development_result",
        "statement": "R1 did not improve collision count or clearance consistently over R0 at matched exact episode cost.",
        "mean_r1_minus_r0_min_clearance_m": mean(r1_clearance_deltas),
        "paired_clearance_wins": sum(value > 1e-9 for value in r1_clearance_deltas),
        "paired_clearance_losses": sum(value < -1e-9 for value in r1_clearance_deltas),
        "paired_clearance_ties": sum(abs(value) <= 1e-9 for value in r1_clearance_deltas),
        "net_r1_minus_r0_collisions": sum(r1_collision_deltas),
        "inferential_test_performed": False,
        "formal_claim_authorized": False,
        "mechanistic_reason": "R0 and R1 produced identical send steps and quality ranges in every paired episode, so no communication, perception, control, or outcome lead occurred.",
    }
    report = {
        "development_only": True, "formal": False,
        "exact_episode_cost_verified": matrix["exact_cost_match"] and accounting_valid,
        "episode_wire_bytes": matrix["episode_wire_costs"],
        "method_summary": method_rows, "paired_r0_r1": paired_rows,
        "causal_trace_summary": trace_rows, "conclusion": conclusion,
    }
    (RESULTS / "development_analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (RESULTS / "method_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=method_rows[0].keys())
        writer.writeheader()
        writer.writerows(method_rows)
    with (RESULTS / "paired_r0_r1.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=paired_rows[0].keys())
        writer.writeheader()
        writer.writerows(paired_rows)
    print(json.dumps({"exact_episode_cost_verified": report["exact_episode_cost_verified"], "conclusion": conclusion}, indent=2))


if __name__ == "__main__":
    main()
