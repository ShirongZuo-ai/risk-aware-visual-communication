"""Precursor-blinded Safety-Value support utilities for CVC-Q5 Stage A.

This module intentionally has no dependency on the Q4 precursor.  It consumes
only held/current Q1 planner dictionaries and reproduces the frozen Q2/Q3
decision-level Safety Value semantics needed to qualify event support.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence


SAFETY_RANK = {"hard_unsafe": 0, "hard_safe": 1, "preferred_safe": 2}
SAFE_SET_CONTRACTION_FRACTION = 1.0 / 3.0
MATCHED_MARGIN_DETERIORATION_M = 0.01
NUMERICAL_TOLERANCE = 1e-9


@dataclass(frozen=True)
class StageASafetyValue:
    triggered: bool
    priority: int | None
    primary_reason: str | None
    reasons: tuple[str, ...]
    safety_class_deterioration: bool
    moving_safe_set_collapse: bool
    safety_forced_action_change: bool
    safe_set_contraction_fraction: float
    matched_held_action_margin_deterioration_m: float | None
    matched_margin_state: str
    held_safe_count: int
    current_safe_count: int
    held_moving_safe_count: int
    current_moving_safe_count: int


def _candidate_map(planner: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    candidates = planner.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("planner candidates are required")
    result = {str(item["action_id"]): item for item in candidates}
    if len(result) != len(candidates):
        raise ValueError("duplicate action identity")
    return result


def safety_value_from_planners(
    held: Mapping[str, object], current: Mapping[str, object],
) -> StageASafetyValue:
    """Reproduce the frozen Q2/Q3 Safety Value hierarchy from planner logs."""
    held_candidates = _candidate_map(held)
    current_candidates = _candidate_map(current)
    if held_candidates.keys() != current_candidates.keys():
        raise ValueError("candidate identities differ")
    held_action = str(held["selected_action_id"])
    current_action = str(current["selected_action_id"])
    held_safe = set(map(str, held.get("safe_action_ids", ())))
    current_safe = set(map(str, current.get("safe_action_ids", ())))
    held_moving = {
        action for action in held_safe
        if float(held_candidates[action]["action"]["linear_m_s"]) > NUMERICAL_TOLERANCE
    }
    current_moving = {
        action for action in current_safe
        if float(current_candidates[action]["action"]["linear_m_s"]) > NUMERICAL_TOLERANCE
    }
    deterioration = (
        SAFETY_RANK[str(current["selected_safety_class"])]
        < SAFETY_RANK[str(held["selected_safety_class"])]
    )
    moving_collapse = bool(held_moving) and not current_moving
    forced_action = held_action != current_action and held_action not in current_safe
    removed = held_safe - current_safe
    contraction = len(removed) / max(1, len(held_safe))
    old_margin = float(held_candidates[held_action]["conservative_min_clearance_m"])
    new_margin = float(current_candidates[held_action]["conservative_min_clearance_m"])
    if math.isinf(old_margin) and math.isfinite(new_margin):
        margin_drop, margin_state, large_drop = None, "became_bounded", True
    elif math.isfinite(old_margin) and math.isinf(new_margin):
        margin_drop, margin_state, large_drop = None, "became_unbounded", False
    elif math.isfinite(old_margin) and math.isfinite(new_margin):
        margin_drop = old_margin - new_margin
        margin_state = "finite"
        large_drop = margin_drop >= MATCHED_MARGIN_DETERIORATION_M
    else:
        margin_drop, margin_state, large_drop = 0.0, "both_unbounded", False
    reasons: list[str] = []
    priority: int | None = None
    if deterioration:
        reasons.append("safety_class_deterioration")
        priority = 1
    if moving_collapse:
        reasons.append("moving_safe_set_collapse")
        priority = 1
    if forced_action:
        reasons.append("held_action_became_unsafe")
        priority = 2 if priority is None else priority
    if contraction >= SAFE_SET_CONTRACTION_FRACTION and large_drop:
        reasons.append("large_contraction_and_margin_deterioration")
        priority = 3 if priority is None else priority
    return StageASafetyValue(
        bool(reasons), priority, reasons[0] if reasons else None, tuple(reasons),
        deterioration, moving_collapse, forced_action, contraction, margin_drop,
        margin_state, len(held_safe), len(current_safe), len(held_moving), len(current_moving),
    )


def onset_indices(events: Sequence[bool]) -> list[int]:
    return [index for index, event in enumerate(events)
            if event and (index == 0 or not events[index - 1])]


def qualify_trace(rows: Sequence[Mapping[str, object]]) -> dict:
    """Extract accepted onsets without reading any precursor quantity."""
    if not rows:
        raise ValueError("non-empty trace required")
    values: list[StageASafetyValue] = []
    contacts: list[bool] = []
    for row in rows:
        counterfactual = row["counterfactual"]
        values.append(safety_value_from_planners(
            counterfactual["held_planner"], counterfactual["current_planner"]
        ))
        contacts.append(bool(row["evaluator"]["contact"]))
    raw_onsets = onset_indices([item.triggered for item in values])
    first_contact = next((index for index, contact in enumerate(contacts) if contact), None)
    accepted = []
    rejected = []
    for index in raw_onsets:
        item = values[index]
        reasons = []
        if index < 8:
            reasons.append("too_early_for_informative_transition")
        if first_contact is not None and first_contact <= index:
            reasons.append("contact_precedes_or_coincides_with_event")
        if item.current_safe_count < 2:
            reasons.append("no_meaningful_alternative_safe_choice")
        record = {
            "step": index,
            "time_s": float(rows[index]["time_s"]),
            "priority": item.priority,
            "primary_reason": item.primary_reason,
            "reasons": list(item.reasons),
            "held_safe_count": item.held_safe_count,
            "current_safe_count": item.current_safe_count,
            "held_moving_safe_count": item.held_moving_safe_count,
            "current_moving_safe_count": item.current_moving_safe_count,
            "safe_set_contraction_fraction": item.safe_set_contraction_fraction,
            "matched_margin_deterioration_m": item.matched_held_action_margin_deterioration_m,
            "rejection_reasons": reasons,
        }
        (rejected if reasons else accepted).append(record)
    return {
        "steps": len(rows),
        "event_steps": sum(item.triggered for item in values),
        "raw_onsets": raw_onsets,
        "accepted_onsets": accepted,
        "rejected_onsets": rejected,
        "first_contact_step": first_contact,
        "event_positive": bool(accepted),
    }


def assert_stage_a_blinded(paths: Sequence[Path]) -> None:
    precursor_module = "cvc_q4" + "_precursor"
    forbidden_config_keys = (
        "soft_mass_attention" + "_q01",
        "tau_soft_mass" + "_per_s",
    )
    findings: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [alias.name for alias in node.names]
                else:
                    continue
                if any(precursor_module in name for name in names):
                    findings.append(f"{path}:imports-{precursor_module}")
        else:
            for token in forbidden_config_keys:
                if token in text:
                    findings.append(f"{path}:{token}")
    if findings:
        raise RuntimeError("Q4 precursor exposed during Stage A: " + ", ".join(findings))
