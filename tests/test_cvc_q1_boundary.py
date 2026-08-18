from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py"


def test_planner_module_has_no_evaluator_or_simulator_import() -> None:
    source = (ROOT / "navigation" / "cvc_q1_local_planner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and (module.startswith("evaluation") or module == "controller") for module in modules)
    assert "clearance_m" in source  # estimated planner clearance is explicit
    assert "Webots" not in source


def test_evaluator_ground_truth_starts_after_runtime_action() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    assert source.index("actual_decision =") < source.index("left.setVelocity") < source.index("# Evaluator-only ground truth")
    assert "self_node.getPosition()" in source[source.index("# Evaluator-only ground truth"):]
    assert "self_node.getPosition()" not in source[:source.index("# Evaluator-only ground truth")]


def test_q1_runtime_does_not_import_m9_ground_truth() -> None:
    tree = ast.parse(CONTROLLER.read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and ("m9" in module or "ground_truth" in module) for module in modules)
