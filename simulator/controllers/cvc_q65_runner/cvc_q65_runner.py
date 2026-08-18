"""Q6.5 paired-intervention adapter over the established visual-control loop."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import communication.cvc_q2_allocator as q2_allocator
import communication.cvc_q3_allocator as q3_allocator
import navigation.cvc_q1_local_planner as q1_planner
from communication.cvc_q65_intervention import OpportunityInterventionScheduler
from communication.cvc_q65_predictor import FrozenOpportunityPredictor
from communication.cvc_q65_scheduler import OnlineFeatureState, OpportunityValueScheduler
from communication.cvc_q6_scheduler import Q6CausalContext
from navigation.cvc_q1_local_planner import action_id

context = Q6CausalContext()
planner_calls: list[tuple[tuple[object, ...], object]] = []
original_plan = q1_planner.plan_local_action
original_value = q2_allocator.evaluate_safety_decision_value
original_allocator = q3_allocator.TemporalRepairAllocator
online_state = OnlineFeatureState(context)


def planner_mapping(decision) -> dict:
    selected = decision.selected
    return {
        "selected_action_id": action_id(selected.action),
        "selected_action": asdict(selected.action),
        "selected_safety_class": selected.safety_class,
        "safe_action_ids": list(decision.safe_action_ids),
        "candidates": [
            {"action_id": action_id(item.action), "action": asdict(item.action),
             "hard_feasible": item.hard_feasible,
             "conservative_min_clearance_m": item.conservative_min_clearance_m}
            for item in decision.evaluations
        ],
    }


def observed_plan(obstacles, goal_bearing_rad, **kwargs):
    obstacle_tuple = tuple(obstacles)
    decision = original_plan(obstacle_tuple, goal_bearing_rad, **kwargs)
    planner_calls.append((obstacle_tuple, decision))
    if len(planner_calls) > 4:
        del planner_calls[:-4]
    return decision


def observed_value(held, current, thresholds):
    if len(planner_calls) < 2 or planner_calls[-2][1] is not held or planner_calls[-1][1] is not current:
        raise RuntimeError("Q6.5 planner/value causal ordering changed")
    held_mapping, current_mapping = planner_mapping(held), planner_mapping(current)
    value = original_value(held, current, thresholds)
    previous_actual = planner_calls[-3][1] if len(planner_calls) >= 3 else None
    context.observe(held_mapping, current_mapping, planner_calls[-1][0])
    online_state.observe(held_mapping, current_mapping, value, previous_actual)
    return value


class InterventionAdapter:
    def __init__(self, total_steps, _risk_threshold, _validity_steps,
                 _fallback_step, _reserve_step):
        cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
        study = cfg["q65"]
        mode = study.get("mode", "intervention")
        if mode == "intervention":
            self.scheduler = OpportunityInterventionScheduler(
                total_steps=total_steps, branch=study["branch"],
                probe_step=study.get("probe_step"),
                min_later_gap_steps=study["min_later_gap_steps"],
                candidate_start_step=study["candidate_start_step"],
                candidate_end_step=study["candidate_end_step"],
                fallback_step=study["fallback_step"],
                reserve_step=study["reserve_step"], context=context,
            )
        elif mode == "utility_scheduler":
            predictor = FrozenOpportunityPredictor.from_path(ROOT / study["model_path"])
            self.scheduler = OpportunityValueScheduler(
                total_steps=total_steps, predictor=predictor, feature_state=online_state,
                candidate_start_step=study["candidate_start_step"],
                candidate_end_step=study["candidate_end_step"],
                clock_steps=tuple(study["clock_steps"]), fallback_step=study["fallback_step"],
                reserve_step=study["reserve_step"],
            )
        elif mode == "baseline_a0":
            self.scheduler = original_allocator(
                total_steps, float(cfg["q3"]["risk_threshold"]),
                int(cfg["q3"]["validity_steps"]), int(cfg["q3"]["fallback_step"]),
                int(cfg["q3"]["reserve_step"]),
            )
        else:
            raise ValueError(f"unknown Q6.5 controller mode: {mode}")

    def decide(self, step, risk, value):
        return self.scheduler.decide(step, risk, value)


q1_planner.plan_local_action = observed_plan
q2_allocator.evaluate_safety_decision_value = observed_value
q3_allocator.TemporalRepairAllocator = InterventionAdapter
runpy.run_path(str(ROOT / "simulator/controllers/cvc_q3_runner/cvc_q3_runner.py"), run_name="__main__")
