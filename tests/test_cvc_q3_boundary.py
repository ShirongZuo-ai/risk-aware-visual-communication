from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOCATOR = ROOT / "communication" / "cvc_q3_allocator.py"
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_q3_runner" / "cvc_q3_runner.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_q3_sender_policy_has_no_evaluator_or_webots_import_and_no_future_leakage() -> None:
    tree = ast.parse(ALLOCATOR.read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and (module.startswith("evaluation") or module == "controller") for module in modules)
    source = ALLOCATOR.read_text(encoding="utf-8").lower()
    forbidden = ("future_value", "future_collision", "future_clearance", "actual_trajectory", "webots")
    assert all(token not in source for token in forbidden)


def test_evaluator_truth_remains_after_q3_actuation() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    marker = source.index("# Evaluator-only Webots truth")
    assert source.index("actual_plan =") < source.index("left.setVelocity") < marker
    assert "self_node.getPosition()" not in source[:marker]
    assert "getContactPoints(True)" not in source[:marker]
    assert "self_node.getPosition()" in source[marker:]
    assert "getContactPoints(True)" in source[marker:]


def test_q3_controller_profiles_every_required_runtime_component() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    for key in ("sender_detector", "held_planner", "current_hypothetical_planner",
                "safety_decision_value", "scheduler_decision", "communication_decision_total"):
        assert key in source
    profile = json.loads((ROOT / "results" / "cvc_q3_runtime_profile" / "profile.json").read_text())
    assert profile["classification"] == "logical_scheduler_timing"
    assert profile["any_component_deadline_miss"] is False
    assert profile["conservative_sum_of_component_p95_ms"]["q2"] < profile["control_period_ms"]


def test_q2_fixed_scientific_components_are_unchanged() -> None:
    q2 = json.loads((ROOT / "results" / "cvc_q2_readiness" / "manifest.json").read_text())
    mapping = {
        "q2_config": ROOT / "config" / "cvc_q2_development.json",
        "q2_protocol": ROOT / "docs" / "cvc_q2_development_protocol.md",
        "q2_allocator": ROOT / "communication" / "cvc_q2_allocator.py",
        "q2_controller": ROOT / "simulator" / "controllers" / "cvc_q2_runner" / "cvc_q2_runner.py",
        "q2_world": ROOT / "simulator" / "worlds" / "cvc_q2_runner.wbt",
        "risk_implementation": ROOT / "communication" / "cvc_p2_protocol.py",
        "q1_grid": ROOT / "config" / "cvc_q1_support_grid.json",
        "q1_planner": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "q1_visual_geometry": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "q1_obstacle_memory": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
    }
    for name, path in mapping.items():
        assert digest(path) == q2["protected_sha256"][name]


def test_q3_smoke_reconciles_exact_bytes_and_preserves_reserve() -> None:
    smoke = json.loads((ROOT / "results" / "cvc_q3_smoke" / "qualification.json").read_text())
    assert smoke["passed"] is True
    assert len(smoke["records"]) == 3
    assert all(row["wire_bytes"] == 72_000 and row["transmissions"] == 3 for row in smoke["records"])
    assert all(row["byte_reconciliation"] and row["mirror_all_steps_match"] for row in smoke["records"])
    adaptive = [row for row in smoke["records"] if row["policy"] in ("A0", "A1")]
    assert all(row["send_steps"] == [0, 295, 311] for row in adaptive)
    assert all(row["adaptive_reason"] == "unarmed_late_fallback" and row["reserve_step"] == 311
               for row in adaptive)
