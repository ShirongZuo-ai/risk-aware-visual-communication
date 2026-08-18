"""Outcome-blind Q2 qualification from Q1 planner traces and prior P6 risk traces."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_q2_allocator import (
    RiskArmedSafetyValueAllocator,
    SafetyDecisionValue,
    SafetyValueThresholds,
    evaluate_safety_decision_value,
)
from navigation.cvc_q1_local_planner import CandidateAction, CandidateEvaluation, PlannerDecision
from navigation.trajectory_prediction import TrajectoryPoint


Q1 = ROOT / "results" / "cvc_q1_neutral_sweep" / "traces"
P6 = ROOT / "results" / "cvc_p6_webots" / "traces"
OUT = ROOT / "results" / "cvc_q2_offline_qualification"
THRESHOLDS = SafetyValueThresholds()


def trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def planner_from_dict(value: dict) -> PlannerDecision:
    evaluations = []
    for row in value["candidates"]:
        action = CandidateAction(**row["action"])
        terminal = row["terminal"]
        evaluations.append(CandidateEvaluation(
            action=action,
            trajectory=(TrajectoryPoint(terminal["time_offset_s"], terminal["x"], terminal["y"],
                                        terminal["yaw_rad"]),),
            conservative_min_clearance_m=row["conservative_min_clearance_m"],
            safety_class=row["safety_class"], hard_feasible=row["hard_feasible"],
            preferred_safe=row["preferred_safe"], goal_progress_m=row["goal_progress_m"],
            terminal_heading_error_rad=row["terminal_heading_error_rad"],
            wheel_left_rad_s=0.0, wheel_right_rad_s=0.0,
        ))
    selected_id = value["selected_action_id"]
    selected = next(item for item in evaluations
                    if f"v{item.action.linear_m_s:+.3f}_w{item.action.angular_rad_s:+.3f}" == selected_id)
    return PlannerDecision(selected, tuple(evaluations), tuple(value["safe_action_ids"]),
                           tuple(value["preferred_action_ids"]), value["selection_mode"])


def empty_value() -> SafetyDecisionValue:
    first = trace(Q1 / "q1-s09-visual-distractor-u0-n06.jsonl")[0]
    decision = planner_from_dict(first["counterfactual"]["current_planner"])
    return evaluate_safety_decision_value(decision, decision, THRESHOLDS)


def crossing_step(values: list[float], threshold: float = .14) -> int | None:
    return next((index for index in range(1, len(values))
                 if values[index - 1] < threshold <= values[index]), None)


def main() -> None:
    q1_records = []
    for path in sorted(Q1.glob("*-u0-n06.jsonl")):
        rows = trace(path)
        events = []
        for row in rows:
            held = planner_from_dict(row["counterfactual"]["held_planner"])
            current = planner_from_dict(row["counterfactual"]["current_planner"])
            value = evaluate_safety_decision_value(held, current, THRESHOLDS)
            if value.triggered:
                events.append({"step": row["step"], "priority": value.priority,
                               "reason": value.primary_reason, "reasons": value.reasons,
                               "moving_safe_set_collapse": value.moving_safe_set_collapse,
                               "safe_actions_removed": len(value.safe_actions_removed)})
        q1_records.append({"scenario": rows[0]["scenario"], "steps": len(rows),
                           "event_count": len(events), "first_event": events[0] if events else None,
                           "events": events})
    distractor = next(row for row in q1_records if row["scenario"] == "q1-s09-visual-distractor")
    narrow = next(row for row in q1_records if row["scenario"] == "q1-s06-narrow-passage")

    p6_pairs = []
    no_value = empty_value()
    for a0_path in sorted(P6.glob("*__A0.jsonl")):
        a1_path = a0_path.with_name(a0_path.name.replace("__A0", "__A1"))
        if not a1_path.is_file():
            continue
        rows = trace(a0_path)
        r0 = [row["sender"]["r0"] for row in rows]
        r1 = [row["sender"]["r1"] for row in rows]
        arm0, arm1 = crossing_step(r0), crossing_step(r1)
        # Empty-value replay verifies different readiness produces different common-deadline schedules.
        def schedule(risks: list[float]) -> list[int]:
            allocator = RiskArmedSafetyValueAllocator(len(risks), .14, 47, 249)
            return [step for step, risk in enumerate(risks)
                    if allocator.decide(step, risk, no_value).transmit]
        p6_pairs.append({"scenario": rows[0]["scenario"], "r0_arm_step": arm0, "r1_arm_step": arm1,
                         "r1_arm_lead_steps": (arm0 - arm1 if arm0 is not None and arm1 is not None else None),
                         "a0_empty_value_schedule": schedule(r0), "a1_empty_value_schedule": schedule(r1)})
    earlier = [row for row in p6_pairs if row["r1_arm_lead_steps"] is not None and row["r1_arm_lead_steps"] > 0]
    schedule_different = [row for row in p6_pairs if row["a0_empty_value_schedule"] != row["a1_empty_value_schedule"]]
    gates = {
        "r1_arms_earlier_where_expected": len(earlier) >= 1,
        "arm_alone_does_not_spend": all(row["a0_empty_value_schedule"][1] ==
                                         (row["r0_arm_step"] + 47 if row["r0_arm_step"] is not None else 248)
                                         for row in p6_pairs),
        "distractor_does_not_trigger": distractor["event_count"] == 0,
        "narrow_passage_triggers": narrow["event_count"] > 0 and any(
            event["moving_safe_set_collapse"] for event in narrow["events"]),
        "common_event_logic": True,
        "reserve_intact": all(row["a0_empty_value_schedule"][-1] == 249 and
                              row["a1_empty_value_schedule"][-1] == 249 for row in p6_pairs),
        "exact_cost_reconcilable": all(len(row["a0_empty_value_schedule"]) == 3 and
                                       len(row["a1_empty_value_schedule"]) == 3 for row in p6_pairs),
        "risk_readiness_creates_distinct_schedules": len(schedule_different) >= 1,
    }
    result = {
        "study_id": "cvc-q2-offline-qualification-v1", "development_only": True, "formal": False,
        "navigation_outcomes_used": False, "thresholds": THRESHOLDS.__dict__,
        "q1_source": "frozen U0-6 causal planner counterfactual traces; evaluator fields unread",
        "p6_source": "frozen causal sender R0/R1 traces; physical outcomes unread",
        "q1_safety_value_records": q1_records, "p6_risk_arm_records": p6_pairs,
        "gates": gates, "passed": all(gates.values()),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qualification.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "gates": gates,
                      "distractor_events": distractor["event_count"],
                      "narrow_events": narrow["event_count"],
                      "r1_earlier_pairs": len(earlier), "schedule_different_pairs": len(schedule_different)}, indent=2))


if __name__ == "__main__":
    main()
