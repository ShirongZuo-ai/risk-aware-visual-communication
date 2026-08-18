from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from communication.cvc_p2_perception import VisualObstacle
from communication.cvc_p7_diagnostics import (
    directional_control_diagnostic,
    visual_safety_cue,
    wheel_kinematics,
)
from evaluation.cvc_p7_safety import classify_spend, physical_safety_reference


ROOT = Path(__file__).resolve().parents[1]


def obstacle(bearing: float, proximity: float, pixels: int, bbox=(60, 30, 100, 90)) -> VisualObstacle:
    return VisualObstacle(True, bearing, proximity, bbox, pixels, (80.0, 60.0), 1,
                          1.0, proximity, ())


def test_directional_decomposition_preserves_wheel_deltas_and_physical_units() -> None:
    held, current = obstacle(-0.5, 0.08, 100), obstacle(0.1, 0.16, 220)
    diagnostic = directional_control_diagnostic(held, current, 5.0)
    assert diagnostic.delta_left_rad_s == pytest.approx(
        diagnostic.send_left_rad_s - diagnostic.held_left_rad_s)
    assert diagnostic.delta_right_rad_s == pytest.approx(
        diagnostic.send_right_rad_s - diagnostic.held_right_rad_s)
    assert wheel_kinematics(5.0, 5.0) == pytest.approx((0.1025, 0.0))
    assert diagnostic.slowdown_event


def test_frozen_controller_turns_toward_off_center_red_component() -> None:
    diagnostic = directional_control_diagnostic(obstacle(0.0, 0.1, 100), obstacle(0.5, 0.1, 100), 5.0)
    assert diagnostic.turn_toward_obstacle
    assert not diagnostic.turn_away_from_obstacle


def test_visual_cue_bearing_convergence_and_growth_rates() -> None:
    held = obstacle(0.6, 0.08, 100, (20, 40, 40, 60))
    current = obstacle(0.2, 0.12, 180, (60, 30, 100, 80))
    cue = visual_safety_cue(held, current, 2.0)
    assert cue.bearing_convergence_rate_s == pytest.approx(0.2)
    assert cue.bearing_moving_toward_center
    assert cue.proximity_growth_rate_s == pytest.approx(0.02)
    assert cue.area_growth_rate_px_s == pytest.approx(40.0)
    assert cue.bbox_height_growth_rate_px_s == pytest.approx(15.0)
    assert cue.forward_corridor_overlap > 0.0


def test_component_event_distinguishes_conflict_region() -> None:
    missing = VisualObstacle(False, None, 0.0, None, 0)
    lateral = obstacle(0.8, 0.1, 50, (140, 30, 155, 70))
    center = obstacle(0.0, 0.1, 50, (70, 30, 90, 70))
    assert not visual_safety_cue(missing, lateral, 1.0).conflict_relevant_appearance
    assert visual_safety_cue(missing, center, 1.0).conflict_relevant_appearance


def test_evaluator_reference_and_spend_classification_are_separate() -> None:
    reference = physical_safety_reference([.4, .2, .11, .08, .2], [False] * 5,
                                          threshold_m=.12, future_horizon_steps=2)
    assert reference.relevant == (True, True, True, True, False)
    assert reference.danger_onset_step == 2
    assert classify_spend(True, -.01, True, False, False) == "mainly_safety_protective"
    assert classify_spend(False, .01, False, False, False) == "mainly_progress_enabling"


def test_sender_diagnostic_module_has_no_evaluator_import_or_clearance_input() -> None:
    path = ROOT / "communication" / "cvc_p7_diagnostics.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and module.startswith("evaluation") for module in modules)
    assert "clearance" not in inspect.signature(visual_safety_cue).parameters
