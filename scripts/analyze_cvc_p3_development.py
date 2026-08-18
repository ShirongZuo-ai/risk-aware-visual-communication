"""Analyze CVC-P3 Webots development after the risk-only gate was frozen."""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "cvc_p3_webots"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def first_risk_send(rows: list[dict]) -> int | None:
    return next((row["step"] for row in rows if row["communication"]["transmitted"]
                 and row["communication"]["reason"].startswith("risk_")), None)


def first_trigger(rows: list[dict]) -> int | None:
    return next((row["step"] for row in rows if row["communication"]["trigger_event"]), None)


def first_divergence(a: list[dict], b: list[dict], predicate) -> int | None:
    return next((left["step"] for left, right in zip(a, b) if predicate(left, right)), None)


def main() -> None:
    matrix = json.loads((RESULTS / "matrix_summary.json").read_text(encoding="utf-8"))
    runs = matrix["runs"]
    traces = {}
    for path in sorted((RESULTS / "traces").glob("matrix__*.jsonl")):
        parts = path.stem.split("__")
        traces[(parts[1], parts[2])] = read_jsonl(path)
    scenarios = sorted({row["scenario"] for row in runs})
    method_summary = []
    for policy in ("U0", "A0", "A1"):
        group = [row for row in runs if row["policy"] == policy]
        successes = sum((not row["collision"]) and row["forward_progress_m"] >= 0.5 for row in group)
        method_summary.append({
            "policy": policy, "episodes": len(group), "collisions": sum(row["collision"] for row in group),
            "task_successes": successes, "minimum_clearance_m": min(row["min_clearance_m"] for row in group),
            "mean_minimum_clearance_m": statistics.mean(row["min_clearance_m"] for row in group),
            "mean_image_age_ms": statistics.mean(row["mean_image_age_ms"] for row in group),
            "mean_forward_progress_m": statistics.mean(row["forward_progress_m"] for row in group),
            "wire_bytes": sorted({row["wire_bytes"] for row in group}),
        })
    pairs = []
    for scenario in scenarios:
        a0, a1 = traces[(scenario, "A0")], traces[(scenario, "A1")]
        s0, s1 = first_risk_send(a0), first_risk_send(a1)
        p0, p1 = first_trigger(a0), first_trigger(a1)
        first_perception = first_divergence(a0, a1, lambda x, y: (
            x["perception"]["detected"] != y["perception"]["detected"]
            or abs(x["perception"]["proximity"] - y["perception"]["proximity"]) > 1e-12
            or x["perception"]["bearing"] != y["perception"]["bearing"]
        ))
        first_control = first_divergence(a0, a1, lambda x, y: (
            abs(x["control"]["left_rad_s"] - y["control"]["left_rad_s"]) > 1e-12
            or abs(x["control"]["right_rad_s"] - y["control"]["right_rad_s"]) > 1e-12
        ))
        first_trajectory = first_divergence(a0, a1, lambda x, y: math.hypot(
            x["evaluator"]["x_m"] - y["evaluator"]["x_m"],
            x["evaluator"]["y_m"] - y["evaluator"]["y_m"],
        ) > 1e-9)
        perception_different = 0
        control_differences = []
        trajectory_differences = []
        age_differences = []
        for left, right in zip(a0, a1):
            perception_different += (
                left["perception"]["detected"] != right["perception"]["detected"]
                or abs(left["perception"]["proximity"] - right["perception"]["proximity"]) > 1e-12
                or left["perception"]["bearing"] != right["perception"]["bearing"]
            )
            control_differences.append((abs(left["control"]["left_rad_s"] - right["control"]["left_rad_s"])
                                        + abs(left["control"]["right_rad_s"] - right["control"]["right_rad_s"])) / 2)
            trajectory_differences.append(math.hypot(left["evaluator"]["x_m"] - right["evaluator"]["x_m"],
                                                      left["evaluator"]["y_m"] - right["evaluator"]["y_m"]))
            age_differences.append(right["receiver"]["image_age_ms"] - left["receiver"]["image_age_ms"])
        summary0 = next(row for row in runs if row["scenario"] == scenario and row["policy"] == "A0")
        summary1 = next(row for row in runs if row["scenario"] == scenario and row["policy"] == "A1")
        pairs.append({
            "scenario": scenario, "a0_send_steps": summary0["send_steps"], "a1_send_steps": summary1["send_steps"],
            "communication_lead_steps": s0 - s1 if s0 is not None and s1 is not None else None,
            "communication_lead_s": (s0 - s1) * 0.032 if s0 is not None and s1 is not None else None,
            "prediction_lead_steps": p0 - p1 if p0 is not None and p1 is not None else None,
            "prediction_lead_s": (p0 - p1) * 0.032 if p0 is not None and p1 is not None else None,
            "conversion_efficiency": ((s0 - s1) / (p0 - p1)
                                      if p0 is not None and p1 is not None and p0 != p1
                                      and s0 is not None and s1 is not None else None),
            "mean_a1_minus_a0_image_age_ms": statistics.mean(age_differences),
            "perception_difference_fraction": perception_different / len(a0),
            "mean_wheel_command_divergence_rad_s": statistics.mean(control_differences),
            "max_trajectory_divergence_m": max(trajectory_differences),
            "first_perception_divergence_step": first_perception,
            "first_control_divergence_step": first_control,
            "first_trajectory_divergence_step": first_trajectory,
            "causal_order_supported": (s1 is not None and first_perception is not None and first_control is not None
                                       and first_trajectory is not None and s1 <= first_perception <= first_control <= first_trajectory),
            "a0_collision": summary0["collision"], "a1_collision": summary1["collision"],
            "a1_minus_a0_min_clearance_m": summary1["min_clearance_m"] - summary0["min_clearance_m"],
            "a0_task_success": (not summary0["collision"]) and summary0["forward_progress_m"] >= 0.5,
            "a1_task_success": (not summary1["collision"]) and summary1["forward_progress_m"] >= 0.5,
            "exact_cost_match": summary0["wire_bytes"] == summary1["wire_bytes"] == 72000,
        })
    a0_summary = next(row for row in method_summary if row["policy"] == "A0")
    a1_summary = next(row for row in method_summary if row["policy"] == "A1")
    actionable = any(row["communication_lead_steps"] not in (None, 0) for row in pairs)
    downstream = any(row["first_control_divergence_step"] is not None for row in pairs)
    collision_benefit = a1_summary["collisions"] < a0_summary["collisions"]
    success_benefit = a1_summary["task_successes"] > a0_summary["task_successes"]
    clearance_wins = sum(row["a1_minus_a0_min_clearance_m"] > 1e-6 for row in pairs)
    clearance_losses = sum(row["a1_minus_a0_min_clearance_m"] < -1e-6 for row in pairs)
    task_benefit = (collision_benefit and a1_summary["task_successes"] >= a0_summary["task_successes"]) or (
        success_benefit and a1_summary["collisions"] <= a0_summary["collisions"]
    ) or (clearance_wins > clearance_losses and clearance_wins >= 4)
    classification = ("actionable_with_engineering_task_benefit" if actionable and downstream and task_benefit
                      else "actionable_but_no_demonstrated_task_benefit" if actionable
                      else "informative_but_non_actionable")
    report = {
        "development_only": True, "formal": False,
        "exact_cost_match": matrix["exact_cost_match"] and all(row["exact_cost_match"] for row in pairs),
        "method_summary": method_summary, "a0_a1_pairs": pairs,
        "clearance_wins_losses_ties": {"wins": clearance_wins, "losses": clearance_losses,
                                         "ties": len(pairs) - clearance_wins - clearance_losses},
        "classification": classification,
        "actual_packet_accounting": {
            "packet_count": sum(row["communication"]["transmitted"] for rows in traces.values() for row in rows),
            "component_sums_match_wire": all(
                row["communication"]["content_bytes"] + row["communication"]["metadata_bytes"]
                + row["communication"]["padding_bytes"] == row["communication"]["wire_bytes"]
                for rows in traces.values() for row in rows if row["communication"]["transmitted"]
            ),
        },
        "task_benefit_rule": "Development-only benefit requires fewer collisions without fewer successes, more successes without more collisions, or clearance wins in at least four of six scenarios and more wins than losses.",
        "confirmatory_c4_c5_justified": False,
        "confirmatory_reason": "CVC-P3 is development-only; any confirmatory study requires a separate frozen protocol even if engineering benefit appears.",
    }
    (RESULTS / "development_analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
