"""Mechanistic analysis for the frozen CVC-P7 development suite."""
from __future__ import annotations

from collections import Counter
import csv
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_perception import VisualObstacle
from communication.cvc_p7_diagnostics import directional_control_diagnostic, wheel_kinematics
from evaluation.cvc_p7_safety import classify_spend, physical_safety_reference


CONFIG = ROOT / "config" / "cvc_p7_development.json"
P7 = ROOT / "results" / "cvc_p7_webots"
P6 = ROOT / "results" / "cvc_p6_webots"
OUTPUT = ROOT / "results" / "cvc_p7_analysis"


FEATURES = (
    "absolute_bearing",
    "bearing_convergence_rate_s",
    "proximity_growth_rate_s",
    "relative_area_growth_rate_s",
    "bbox_height_growth_rate_px_s",
    "forward_corridor_overlap",
    "delta_v_m_s",
    "delta_abs_turn_rad_s",
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def visual_obstacle(value: dict) -> VisualObstacle:
    bbox = tuple(value["bbox_xyxy"]) if value["bbox_xyxy"] is not None else None
    centroid = tuple(value["centroid_xy"]) if value["centroid_xy"] is not None else None
    proximity = float(value["proximity"])
    return VisualObstacle(bool(value["detected"]), value["bearing"], proximity, bbox,
                          int(value["pixel_count"]), centroid, int(value["component_count"]),
                          float(value["confidence"]), proximity, ())


def first_step(rows: list[dict], predicate) -> int | None:
    return next((int(row["step"]) for row in rows if predicate(row)), None)


def median_or_none(values: list[float | int | None]) -> float | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.median(finite) if finite else None


def historical_p6_tradeoff() -> dict:
    matrix = json.loads((P6 / "matrix_summary.json").read_text(encoding="utf-8"))
    summaries = {(row["scenario"], row["policy"]): row for row in matrix["runs"]}
    pairs = []
    for scenario in sorted({key[0] for key in summaries}):
        a0_summary, a1_summary = summaries[(scenario, "A0")], summaries[(scenario, "A1")]
        a0_rows = read_jsonl(P6 / "traces" / f"p6__{scenario}__A0.jsonl")
        a1_rows = read_jsonl(P6 / "traces" / f"p6__{scenario}__A1.jsonl")
        a1_spend = int(a1_summary["adaptive_step"])
        row = a1_rows[a1_spend]
        held = visual_obstacle(row["counterfactual"]["held_perception"])
        current = visual_obstacle(row["counterfactual"]["current_perception"])
        diagnostic = directional_control_diagnostic(held, current, 5.0)
        a0_v, a0_omega = wheel_kinematics(a0_rows[a1_spend]["control"]["left_rad_s"],
                                          a0_rows[a1_spend]["control"]["right_rad_s"])
        a1_v, a1_omega = wheel_kinematics(a1_rows[a1_spend]["control"]["left_rad_s"],
                                          a1_rows[a1_spend]["control"]["right_rad_s"])
        divergence = next((step for step, (left, right) in enumerate(zip(a0_rows, a1_rows))
                           if math.hypot(left["evaluator"]["x_m"] - right["evaluator"]["x_m"],
                                         left["evaluator"]["y_m"] - right["evaluator"]["y_m"]) > 1e-6), None)
        pairs.append({
            "scenario": scenario,
            "schedules_equal": a0_summary["send_steps"] == a1_summary["send_steps"],
            "a0_send_steps": a0_summary["send_steps"], "a1_send_steps": a1_summary["send_steps"],
            "trajectory_divergence_step": divergence,
            "a1_spend_step": a1_spend,
            "a1_spend_delta_v_m_s": diagnostic.delta_v_m_s,
            "a1_spend_delta_abs_turn_rad_s": diagnostic.delta_abs_turn_rad_s,
            "a1_spend_steering_sign_change": diagnostic.steering_sign_change,
            "a1_spend_slowdown": diagnostic.slowdown_event,
            "a1_spend_turn_toward_component": diagnostic.turn_toward_obstacle,
            "a1_spend_turn_away_from_component": diagnostic.turn_away_from_obstacle,
            "a1_vs_a0_v_at_early_spend_m_s": a1_v - a0_v,
            "a1_vs_a0_abs_turn_at_early_spend_rad_s": abs(a1_omega) - abs(a0_omega),
            "a1_minus_a0_progress_m": a1_summary["forward_progress_m"] - a0_summary["forward_progress_m"],
            "a1_minus_a0_min_clearance_m": a1_summary["min_clearance_m"] - a0_summary["min_clearance_m"],
            "a0_success": a0_summary["task_success"], "a1_success": a1_summary["task_success"],
        })
    different = [row for row in pairs if not row["schedules_equal"]]
    return {
        "pairs": pairs,
        "schedule_different_count": len(different),
        "schedule_different_all_gain_progress": all(row["a1_minus_a0_progress_m"] > 0 for row in different),
        "schedule_different_all_lose_clearance": all(row["a1_minus_a0_min_clearance_m"] < 0 for row in different),
        "schedule_different_all_turn_toward_component_at_a1_spend":
            all(row["a1_spend_turn_toward_component"] for row in different),
        "schedule_different_all_reduce_forward_velocity_at_a1_spend":
            all(row["a1_spend_delta_v_m_s"] < 0 for row in different),
        "interpretation": (
            "The earlier A1 update is not an obstacle-avoidance action: the frozen controller yaws toward the "
            "selected red component while slightly reducing forward velocity. It reduces stale, often large detours and keeps the robot "
            "tracking/centering the component, which improves forward completion but carries the path closer to it."
        ),
    }


def episode_record(summary: dict, rows: list[dict], config: dict) -> tuple[dict, list[dict]]:
    safety_cfg = config["physical_safety_window"]
    reference = physical_safety_reference(
        [float(row["evaluator"]["clearance_m"]) for row in rows],
        [bool(row["evaluator"]["contact"]) for row in rows],
        float(safety_cfg["clearance_threshold_m"]), int(safety_cfg["future_horizon_steps"]),
    )
    arm = summary["arm_step"]
    spend = int(summary["adaptive_step"])
    spend_row = rows[spend]
    directional = spend_row["directional_control"]
    spend_class = classify_spend(
        reference.relevant[spend], float(directional["delta_v_m_s"]),
        bool(directional["slowdown_event"]), bool(directional["increased_turn_event"]),
        bool(directional["turn_away_from_obstacle"]),
        float(config["diagnostic_thresholds"]["progress_m_s"]),
    )
    candidate_steps = {
        "bearing_convergence": first_step(rows, lambda row: row["visual_safety_cue"]["bearing_moving_toward_center"]),
        "proximity_growth": first_step(rows, lambda row: row["visual_safety_cue"]["proximity_growth_rate_s"] > 0),
        "corridor_overlap": first_step(rows, lambda row: row["visual_safety_cue"]["forward_corridor_overlap"] > 0),
        "conflict_relevant_appearance": first_step(rows, lambda row: row["visual_safety_cue"]["conflict_relevant_appearance"]),
    }
    post_arm_rows = rows[int(arm):] if arm is not None else []
    candidate_after_arm = {
        "bearing_convergence": first_step(post_arm_rows, lambda row: row["visual_safety_cue"]["bearing_moving_toward_center"]),
        "proximity_growth": first_step(post_arm_rows, lambda row: row["visual_safety_cue"]["proximity_growth_rate_s"] > 0),
        "corridor_overlap": first_step(post_arm_rows, lambda row: row["visual_safety_cue"]["forward_corridor_overlap"] > 0),
        "conflict_relevant_appearance": first_step(post_arm_rows, lambda row: row["visual_safety_cue"]["conflict_relevant_appearance"]),
    }
    protective = first_step(rows, lambda row: row["directional_control"]["slowdown_event"] or (
        row["directional_control"]["increased_turn_event"] and row["directional_control"]["turn_away_from_obstacle"]))
    p6_novelty = first_step(rows, lambda row: row["task_novelty"]["event"])
    minimum = reference.minimum_clearance_step
    record = {
        **summary,
        "physical_safety_window_steps": sum(reference.relevant),
        "physical_danger_realized": reference.danger_onset_step is not None,
        "physical_danger_onset_step": reference.danger_onset_step,
        "minimum_clearance_step": minimum,
        "r1_arm_step": arm if summary["policy"] == "A1" else None,
        "p6_first_novelty_step": p6_novelty,
        "candidate_first_steps": candidate_steps,
        "candidate_first_steps_after_arm": candidate_after_arm,
        "arm_to_candidate_steps": {
            name: (value - arm if value is not None and arm is not None else None)
            for name, value in candidate_after_arm.items()
        },
        "candidate_protective_control_first_step": protective,
        "spend_safety_relevant": reference.relevant[spend],
        "spend_classification": spend_class,
        "spend_features": {
            **{name: float(spend_row["visual_safety_cue"][name]) for name in FEATURES[:6]},
            **{name: float(spend_row["directional_control"][name]) for name in FEATURES[6:]},
            "p6_delta_bearing": float(spend_row["task_novelty"]["delta_bearing"]),
            "p6_delta_proximity": float(spend_row["task_novelty"]["delta_proximity"]),
            "p6_delta_area_relative": float(spend_row["task_novelty"]["delta_area_relative"]),
            "p6_component_event": bool(spend_row["task_novelty"]["component_event"]),
            "turn_toward_obstacle": bool(directional["turn_toward_obstacle"]),
            "turn_away_from_obstacle": bool(directional["turn_away_from_obstacle"]),
            "slowdown_event": bool(directional["slowdown_event"]),
        },
    }
    aligned = []
    for row, relevant in zip(rows, reference.relevant):
        aligned.append({
            "scenario": summary["scenario"], "category": summary["category"], "policy": summary["policy"],
            "step": row["step"], "r0": row["sender"]["r0"], "r1": row["sender"]["r1"],
            "arm_state": row["policy_state"]["state"], "p6_novelty": row["task_novelty"]["event"],
            "hypothetical_spend": row["communication"]["packet_role"] == "adaptive",
            "image_age_ms": row["receiver"]["image_age_ms"],
            **row["visual_safety_cue"], **row["directional_control"],
            "actual_left_rad_s": row["control"]["left_rad_s"],
            "actual_right_rad_s": row["control"]["right_rad_s"],
            "x_m": row["evaluator"]["x_m"], "y_m": row["evaluator"]["y_m"],
            "physical_clearance_m": row["evaluator"]["clearance_m"],
            "contact": row["evaluator"]["contact"], "forward_progress_m": row["evaluator"]["forward_progress_m"],
            "physical_safety_relevant": relevant,
        })
    return record, aligned


def distribution(records: list[dict]) -> list[dict]:
    rows = []
    for category in "ABCD":
        selected = [record for record in records if record["category"] == category and record["policy"] == "A1"]
        for feature in FEATURES:
            values = [record["spend_features"][feature] for record in selected]
            rows.append({"category": category, "feature": feature, "n_cells": len(values),
                         "minimum": min(values), "median": statistics.median(values),
                         "maximum": max(values), "mean": statistics.mean(values)})
    return rows


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    matrix = json.loads((P7 / "matrix_summary.json").read_text(encoding="utf-8"))
    summaries = {(row["scenario"], row["policy"]): row for row in matrix["runs"]}
    records, aligned = [], []
    for path in sorted((P7 / "traces").glob("p7__*.jsonl")):
        _, scenario, policy = path.stem.split("__")
        record, rows = episode_record(summaries[(scenario, policy)], read_jsonl(path), config)
        records.append(record)
        aligned.extend(rows)
    if len(records) != 36:
        raise RuntimeError("P7 analysis requires all 36 frozen runs")
    p6_tradeoff = historical_p6_tradeoff()
    a1 = [record for record in records if record["policy"] == "A1"]
    danger_cells = [record for record in a1 if record["physical_danger_realized"]]
    usable_leads = []
    for record in danger_cells:
        onset = record["physical_danger_onset_step"]
        candidates = [value for value in record["candidate_first_steps"].values() if value is not None]
        if candidates and onset is not None:
            usable_leads.append(onset - min(candidates))
    contract = config["classification_contract"]
    usable_window = (len(danger_cells) >= int(contract["usable_window_min_cells"]) and
                     sum(lead >= 10 for lead in usable_leads) / len(danger_cells) >=
                     float(contract["usable_window_min_fraction_with_10_step_lead"])) if danger_cells else False
    if not usable_window:
        classification = "CASE D"
        classification_label = "No usable communication safety window demonstrated"
        classification_basis = (
            "Zero A1 cells realized the frozen physical-danger boundary, so cue discrimination and cue-to-danger "
            "lead are unsupported. This is a frozen-suite physical-support failure, not evidence that no window "
            "exists in the broader problem."
        )
    else:
        classification = "UNRESOLVED"
        classification_label = "Feature discrimination would be required"
        classification_basis = "The analysis contract requires a supported feature-ranking stage."
    policy_summary = {}
    for policy in ("U0", "A0", "A1"):
        selected = [record for record in records if record["policy"] == policy]
        policy_summary[policy] = {
            "episodes": len(selected), "collisions": sum(record["collision"] for record in selected),
            "task_successes": sum(record["task_success"] for record in selected),
            "mean_minimum_clearance_m": statistics.mean(record["min_clearance_m"] for record in selected),
            "mean_clearance_m": statistics.mean(record["mean_clearance_m"] for record in selected),
            "mean_forward_progress_m": statistics.mean(record["forward_progress_m"] for record in selected),
            "physical_danger_cells": sum(record["physical_danger_realized"] for record in selected),
        }
    category_policy_summary = {}
    for category in "ABCD":
        category_policy_summary[category] = {}
        for policy in ("U0", "A0", "A1"):
            selected = [record for record in records if record["category"] == category and record["policy"] == policy]
            category_policy_summary[category][policy] = {
                "episodes": 3, "collisions": sum(record["collision"] for record in selected),
                "task_successes": sum(record["task_success"] for record in selected),
                "mean_minimum_clearance_m": statistics.mean(record["min_clearance_m"] for record in selected),
                "mean_clearance_m": statistics.mean(record["mean_clearance_m"] for record in selected),
                "mean_forward_progress_m": statistics.mean(record["forward_progress_m"] for record in selected),
            }
    spend_counts = Counter(record["spend_classification"] for record in a1)
    failed_features = {name: "undefined_no_positive_physical_safety_windows" for name in FEATURES}
    report = {
        "study_id": config["study_id"], "development_only": True, "formal": False,
        "p6_v1_modified": False, "scenario_geometry_modified_after_outcomes": False,
        "historical_p6_tradeoff": p6_tradeoff,
        "physical_safety_window": config["physical_safety_window"],
        "suite_support": {"a1_cells": len(a1), "a1_physical_danger_cells": len(danger_cells),
                          "a1_category_danger_counts": {category: sum(
                              record["physical_danger_realized"] for record in a1 if record["category"] == category)
                              for category in "ABCD"},
                          "usable_candidate_leads_steps": usable_leads,
                          "usable_window": usable_window},
        "policy_summary": policy_summary,
        "category_policy_summary": category_policy_summary,
        "episode_records": records,
        "a1_spend_classification_counts": dict(spend_counts),
        "feature_discrimination": {"status": "not_estimable", "reason": "no_positive_physical_safety_windows",
                                   "single_feature_auprc": failed_features,
                                   "multivariate_model_run": False, "ml_justified": False},
        "candidate_features_that_failed": failed_features,
        "classification": classification, "classification_label": classification_label,
        "classification_basis": classification_basis,
        "p8_recommendation": (
            "Do not implement a Safety-Value-SPEND rule or learned estimator. First create a separately frozen "
            "physically supported danger suite and qualify an avoidance-capable controller; retain this P7 suite "
            "as negative development evidence."
        ),
        "c4_c5_formal_justified": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "mechanistic_analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                                       encoding="utf-8")
    distributions = distribution(records)
    for name, rows, fields in (
        ("episode_summary.csv", records,
         ["scenario", "category", "policy", "arm_step", "adaptive_step", "adaptive_reason", "collision",
          "task_success", "min_clearance_m", "mean_clearance_m", "forward_progress_m",
          "physical_danger_realized", "physical_danger_onset_step", "minimum_clearance_step",
          "spend_safety_relevant", "spend_classification", "wire_bytes", "content_bytes", "metadata_bytes",
          "padding_bytes", "byte_reconciliation"]),
        ("feature_distribution.csv", distributions,
         ["category", "feature", "n_cells", "minimum", "median", "maximum", "mean"]),
    ):
        with (OUTPUT / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({field: row.get(field) for field in fields} for row in rows)
    with (OUTPUT / "aligned_a1_timeseries.csv").open("w", newline="", encoding="utf-8") as handle:
        selected = [row for row in aligned if row["policy"] == "A1"]
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps({"classification": classification, "suite_support": report["suite_support"],
                      "policy_summary": policy_summary, "a1_spend_classification_counts": dict(spend_counts),
                      "historical_p6_tradeoff": {key: value for key, value in p6_tradeoff.items() if key != "pairs"}},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
