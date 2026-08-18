from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_p6_runner" / "cvc_p6_runner.py"


def test_p6_controller_uses_no_m9_or_ground_truth_module() -> None:
    tree = ast.parse(CONTROLLER.read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and ("m9" in module or "ground_truth" in module) for module in modules)


def test_evaluator_fields_do_not_feed_sender_or_control() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    decision_index = source.index("decision =")
    evaluator_index = source.index('"evaluator":')
    assert evaluator_index > decision_index
    assert "selected_risk = r0 if policy in (\"U0\", \"A0\") else r1" in source


def test_p6_world_retains_real_160x120_camera() -> None:
    source = (ROOT / "simulator" / "worlds" / "cvc_p6_runner.wbt").read_text(encoding="utf-8")
    assert 'controller "cvc_p6_runner"' in source
    assert "camera_width 160" in source and "camera_height 120" in source
