from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_p7_runner" / "cvc_p7_runner.py"


def test_p7_adapter_imports_frozen_p6_policy_and_controller() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "RiskArmedNoveltyAllocator" in source
    assert "visual_wheel_command" in source
    assert "directional_control_diagnostic" in source
    assert "visual_safety_cue" in source


def test_evaluator_data_is_logged_only_after_policy_and_control() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    assert source.index("decision =") < source.index("left.setVelocity") < source.index("# Evaluator-only block")
    tree = ast.parse(source)
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and module.startswith("evaluation") for module in modules)


def test_p7_world_retains_real_camera_and_separate_controller() -> None:
    source = (ROOT / "simulator" / "worlds" / "cvc_p7_runner.wbt").read_text(encoding="utf-8")
    assert 'controller "cvc_p7_runner"' in source
    assert "camera_width 160" in source and "camera_height 120" in source
