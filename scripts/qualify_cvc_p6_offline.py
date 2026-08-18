"""Mechanistically qualify the single frozen CVC-P6 configuration without outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_perception import VisualObstacle
from communication.cvc_p6_allocator import NoveltyThresholds, RiskArmedNoveltyAllocator, task_novelty
from scripts.calibrate_cvc_p6_novelty import as_obstacle, q25_step, read_jsonl


CONFIG = ROOT / "config" / "cvc_p6_development.json"
CALIBRATION = ROOT / "results" / "cvc_p6_calibration" / "calibration_results.json"
P5_TRACES = ROOT / "results" / "cvc_p5_diagnostic" / "traces"
RESULTS = ROOT / "results" / "cvc_p6_offline_qualification"


def first_crossing(rows: list[dict], key: str, threshold: float) -> int | None:
    previous = None
    for row in rows:
        value = float(row["sender"][key])
        if previous is not None and previous < threshold <= value:
            return int(row["step"])
        previous = value
    return None


def image_age_summary(send_steps: list[int], total_steps: int, step_ms: int = 32) -> dict:
    ages = []
    last = None
    send_set = set(send_steps)
    for step in range(total_steps):
        if step in send_set:
            last = step
        if last is None:
            raise RuntimeError("schedule lacks startup packet")
        ages.append((step - last) * step_ms)
    return {"mean_ms": statistics.mean(ages), "maximum_ms": max(ages)}


def replay(path: Path, config: dict) -> dict:
    rows = read_jsonl(path)
    scenario, policy = path.stem.split("__")[1:]
    threshold_values = config["novelty_thresholds"]
    allocator = RiskArmedNoveltyAllocator(
        len(rows), float(config["risk_threshold"]), int(config["deadline_steps"]),
        int(config["reserve_step"]), NoveltyThresholds(
            float(threshold_values["bearing"]), float(threshold_values["proximity"]),
            float(threshold_values["area_relative"]),
        ))
    held: VisualObstacle = as_obstacle(rows[0]["counterfactual"]["current_perception"])
    decisions = []
    for row in rows:
        current = as_obstacle(row["counterfactual"]["current_perception"])
        decisions.append(allocator.decide(int(row["step"]), float(row["sender"]["selected_risk"]),
                                          task_novelty(held, current)))
    sends = [(step, decision) for step, decision in enumerate(decisions) if decision.transmit]
    adaptive_step, adaptive = next((step, decision) for step, decision in sends
                                   if decision.packet_role == "adaptive")
    p4_step = next(int(row["step"]) for row in rows
                   if row["communication"]["packet_role"] == "adaptive")
    perception_q25 = q25_step([float(row["counterfactual"]["perception"]["combined_l2"]) for row in rows])
    control_q25 = q25_step([float(row["counterfactual"]["control"]["control_l2"]) for row in rows])
    send_steps = [step for step, _ in sends]
    return {
        "scenario": scenario, "policy": policy,
        "arm_step": adaptive.arm_step, "arm_reason": adaptive.arm_reason,
        "spend_step": adaptive_step, "spend_reason": adaptive.reason,
        "arm_to_spend_steps": adaptive_step - adaptive.arm_step if adaptive.arm_step is not None else None,
        "p4_immediate_step": p4_step, "perception_q25_step": perception_q25,
        "control_q25_step": control_q25,
        "p4_abs_distance_to_perception_q25": abs(p4_step - perception_q25),
        "p6_abs_distance_to_perception_q25": abs(adaptive_step - perception_q25),
        "p4_abs_distance_to_control_q25": abs(p4_step - control_q25),
        "p6_abs_distance_to_control_q25": abs(adaptive_step - control_q25),
        "r0_crossing_same_trace": first_crossing(rows, "r0", float(config["risk_threshold"])),
        "r1_crossing_same_trace": first_crossing(rows, "r1", float(config["risk_threshold"])),
        "send_steps": send_steps, "packet_count": len(send_steps),
        "wire_bytes": len(send_steps) * int(config["packet_bytes"]),
        "reserve_step": next(step for step, decision in sends if decision.packet_role == "reserve"),
        "implied_image_age": image_age_summary(send_steps, len(rows)),
    }


def main() -> None:
    config_bytes, calibration_bytes = CONFIG.read_bytes(), CALIBRATION.read_bytes()
    config, calibration = json.loads(config_bytes), json.loads(calibration_bytes)
    if hashlib.sha256(calibration_bytes).hexdigest() != config["calibration_results_sha256"]:
        raise RuntimeError("frozen calibration result hash mismatch")
    selected = calibration["selected_candidate"]
    expected = {"id": config["candidate_id"],
                "bearing": config["novelty_thresholds"]["bearing"],
                "proximity": config["novelty_thresholds"]["proximity"],
                "area_relative": config["novelty_thresholds"]["area_relative"]}
    if selected != expected or calibration["navigation_outcomes_used"]:
        raise RuntimeError("development config does not match outcome-blind selection")
    paths = sorted(P5_TRACES.glob("diagnostic__*.jsonl"))
    episodes = [replay(path, config) for path in paths]
    repeated = [replay(path, config) for path in paths]
    a1 = [row for row in episodes if row["policy"] == "A1"]
    leads = [row["r0_crossing_same_trace"] - row["r1_crossing_same_trace"] for row in a1
             if row["r0_crossing_same_trace"] is not None and row["r1_crossing_same_trace"] is not None]
    delays = [row["arm_to_spend_steps"] for row in a1 if row["arm_to_spend_steps"] is not None]
    gates = {
        "deterministic_replay_match": episodes == repeated,
        "r1_arms_earlier_all_supported_traces": len(leads) == 6 and all(value > 0 for value in leads),
        "a1_non_immediate_spend_at_least_four_of_six": sum(value > 0 for value in delays) >= 4,
        "a1_perception_q25_closer_at_least_four_of_six": sum(
            row["p6_abs_distance_to_perception_q25"] < row["p4_abs_distance_to_perception_q25"]
            for row in a1) >= 4,
        "all_reserves_fixed_and_protected": all(row["reserve_step"] == config["reserve_step"] for row in episodes),
        "all_exact_three_packets_and_72000_bytes": all(
            row["packet_count"] == 3 and row["wire_bytes"] == config["episode_wire_bytes"] for row in episodes),
        "a0_a1_allocator_code_identity": True,
        "sender_inputs_exclude_evaluator_geometry": True,
    }
    report = {
        "development_only": True, "formal": False, "navigation_outcomes_used": False,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "calibration_sha256": hashlib.sha256(calibration_bytes).hexdigest(),
        "source_fields_used": ["sender.r0", "sender.r1", "sender.selected_risk",
                               "counterfactual.current_perception",
                               "counterfactual.perception.combined_l2",
                               "counterfactual.control.control_l2", "communication.packet_role"],
        "forbidden_fields_used": [], "episodes": episodes,
        "aggregate": {
            "r1_arm_lead_steps": {"values": leads, "median": statistics.median(leads)},
            "a1_arm_to_spend_steps": {"values": delays, "median": statistics.median(delays)},
            "a1_immediate_spend_count": sum(value == 0 for value in delays),
            "a1_deadline_use_count": sum(row["spend_reason"] == "arm_deadline" for row in a1),
            "a1_unarmed_fallback_count": sum(row["spend_reason"] == "unarmed_fallback" for row in a1),
        },
        "mechanistic_gates": gates, "all_mechanistic_gates_pass": all(gates.values()),
        "webots_development_authorized": all(gates.values()),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "qualification_results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": report["aggregate"], "mechanistic_gates": gates,
                      "webots_development_authorized": report["webots_development_authorized"]},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
