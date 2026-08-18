"""Q6 adapter over the protected Q3 visual-control runtime.

The adapter replaces only scheduler construction and records the exact Q5
decision-space precursor plus visual-state M9 R0/R1.  Camera, codec, receiver,
planner, control, and evaluator implementation remain the protected Q3 path.
"""
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
from communication.cvc_q6_scheduler import PrecursorScheduler, Q6CausalContext
from navigation.cvc_q1_local_planner import action_id


context = Q6CausalContext()
planner_calls: list[tuple[tuple[object, ...], object]] = []
original_plan = q1_planner.plan_local_action
original_value = q2_allocator.evaluate_safety_decision_value


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
        raise RuntimeError("Q6 planner/value causal ordering changed")
    context.observe(planner_mapping(held), planner_mapping(current), planner_calls[-1][0])
    return original_value(held, current, thresholds)


class TemporalRepairAdapter:
    def __init__(self, total_steps, _risk_threshold, _validity_steps,
                 _fallback_step, _reserve_step):
        cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
        q6 = cfg["q6"]
        self.scheduler = PrecursorScheduler(
            total_steps=total_steps, policy=cfg["policy"], variant=q6["variant"],
            prepare_validity_steps=q6["prepare_validity_steps"],
            fallback_step=q6["fallback_step"], reserve_step=q6["reserve_step"],
            context=context,
        )

    def decide(self, step, legacy_risk, value):
        return self.scheduler.decide(step, legacy_risk, value)


q1_planner.plan_local_action = observed_plan
q2_allocator.evaluate_safety_decision_value = observed_value
q3_allocator.TemporalRepairAllocator = TemporalRepairAdapter
runpy.run_path(str(ROOT / "simulator/controllers/cvc_q3_runner/cvc_q3_runner.py"),
               run_name="__main__")
