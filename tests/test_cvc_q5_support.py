from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.cvc_q5_support import (
    MATCHED_MARGIN_DETERIORATION_M,
    SAFE_SET_CONTRACTION_FRACTION,
    assert_stage_a_blinded,
    onset_indices,
    qualify_trace,
    safety_value_from_planners,
)


ROOT = Path(__file__).resolve().parents[1]


def _planner(*, selected="move", move_margin=0.20, safe=("stop", "move", "left"),
             selected_class="preferred_safe"):
    values = {"stop": 0.30, "move": move_margin, "left": 0.18}
    actions = {"stop": 0.0, "move": 0.08, "left": 0.045}
    return {
        "selected_action_id": selected,
        "selected_safety_class": selected_class,
        "safe_action_ids": list(safe),
        "candidates": [
            {"action_id": key, "action": {"linear_m_s": actions[key], "angular_rad_s": 0.0},
             "conservative_min_clearance_m": values[key], "hard_feasible": key in safe}
            for key in ("stop", "move", "left")
        ],
    }


def test_frozen_threshold_constants_are_exact():
    assert SAFE_SET_CONTRACTION_FRACTION == 1.0 / 3.0
    assert MATCHED_MARGIN_DETERIORATION_M == 0.01


def test_safety_value_detects_held_action_becoming_unsafe():
    held = _planner()
    current = _planner(selected="left", move_margin=0.0, safe=("stop", "left"),
                       selected_class="hard_safe")
    value = safety_value_from_planners(held, current)
    assert value.triggered
    assert value.safety_class_deterioration
    assert value.safety_forced_action_change
    assert value.primary_reason == "safety_class_deterioration"


def test_onset_extraction_groups_contiguous_event_steps():
    assert onset_indices([False, True, True, False, True, False]) == [1, 4]


def test_stage_a_source_and_config_are_precursor_blinded():
    assert_stage_a_blinded((
        ROOT / "evaluation/cvc_q5_support.py",
        ROOT / "scripts/run_cvc_q5_stage_a.py",
        ROOT / "config/cvc_q5_stage_a.json",
    ))


def test_stage_a_config_preserves_family_identity_and_unique_cells():
    config = json.loads((ROOT / "config/cvc_q5_stage_a.json").read_text(encoding="utf-8"))
    assert config["precursor_blinded"]
    assert len(config["families"]) >= 3
    family_ids = [family["id"] for family in config["families"]]
    cell_ids = [cell["id"] for family in config["families"] for cell in family["cells"]]
    assert len(family_ids) == len(set(family_ids))
    assert len(cell_ids) == len(set(cell_ids))
    assert all(any(cell["role"] == "matched_control" for cell in family["cells"])
               for family in config["families"])


def test_qualify_trace_rejects_contact_timed_or_choice_free_onset():
    safe = _planner()
    unsafe = _planner(selected="stop", move_margin=0.0, safe=("stop",),
                      selected_class="hard_safe")
    rows = []
    for step in range(10):
        rows.append({
            "time_s": step * 0.032,
            "counterfactual": {"held_planner": safe, "current_planner": unsafe if step >= 8 else safe},
            "evaluator": {"contact": step >= 8},
        })
    result = qualify_trace(rows)
    assert not result["accepted_onsets"]
    assert result["rejected_onsets"][0]["rejection_reasons"]


def test_blinding_guard_rejects_forbidden_import(tmp_path):
    path = tmp_path / "bad.py"
    path.write_text("import evaluation.cvc_q4_precursor\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        assert_stage_a_blinded((path,))
