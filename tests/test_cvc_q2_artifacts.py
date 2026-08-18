from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_q2_readiness_manifest_and_protected_inputs_are_intact() -> None:
    manifest_path = ROOT / "results" / "cvc_q2_readiness" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sidecar = manifest_path.with_suffix(".json.sha256").read_text(encoding="utf-8").split()[0]
    assert digest(manifest_path) == sidecar
    assert sidecar == "d5acb4b3b1a9857fe0c0154ee69e3f9a999917a417271e4a059bf6cecba67ca7"
    assert manifest["frozen_before_q2_policy_outcomes"] is True
    assert manifest["q1_planner_and_grid_unchanged"] is True

    paths = {
        "q2_config": ROOT / "config" / "cvc_q2_development.json",
        "q2_protocol": ROOT / "docs" / "cvc_q2_development_protocol.md",
        "q2_allocator": ROOT / "communication" / "cvc_q2_allocator.py",
        "q2_offline_qualification": ROOT / "results" / "cvc_q2_offline_qualification" / "qualification.json",
        "q2_controller": ROOT / "simulator" / "controllers" / "cvc_q2_runner" / "cvc_q2_runner.py",
        "q2_world": ROOT / "simulator" / "worlds" / "cvc_q2_runner.wbt",
        "q2_runner": ROOT / "scripts" / "run_cvc_q2_webots.py",
        "q2_smoke_qualification": ROOT / "results" / "cvc_q2_smoke" / "qualification.json",
        "risk_implementation": ROOT / "communication" / "cvc_p2_protocol.py",
        "q1_readiness_manifest": ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json",
        "q1_grid": ROOT / "config" / "cvc_q1_support_grid.json",
        "q1_planner_config": ROOT / "config" / "cvc_q1_planner_v2.json",
        "q1_planner": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "q1_visual_geometry": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "q1_obstacle_memory": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
        "q1_range_calibration": ROOT / "results" / "cvc_q1_range_calibration" / "calibration_results.json",
        "q1_world": ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt",
        "q1_controller": ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py",
    }
    assert {name: digest(path) for name, path in paths.items()} == manifest["protected_sha256"]


def test_q2_primary_matrix_is_complete_paired_and_exact_cost() -> None:
    matrix = json.loads((ROOT / "results" / "cvc_q2_webots" / "matrix_results.json").read_text())
    records = matrix["records"]
    assert matrix["all_exact_cost"] is True
    assert matrix["all_mirrors_match"] is True
    assert len(records) == 30
    assert {row["policy"] for row in records} == {"U0", "A0", "A1"}
    scenario_ids = {row["scenario"] for row in records}
    assert len(scenario_ids) == 10
    assert all(sum(row["scenario"] == scenario and row["policy"] == policy for row in records) == 1
               for scenario in scenario_ids for policy in ("U0", "A0", "A1"))
    assert all(row["transmissions"] == 3 and row["wire_bytes"] == 72_000 for row in records)
    assert all(row["byte_reconciliation"] and row["mirror_all_steps_match"] for row in records)


def test_q2_analysis_is_strict_and_terminal_case_d() -> None:
    path = ROOT / "results" / "cvc_q2_analysis" / "analysis.json"
    raw = path.read_text(encoding="utf-8")
    assert "NaN" not in raw and "Infinity" not in raw
    analysis = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    criteria = analysis["frozen_criteria"]
    assert analysis["classification"] == "CASE D"
    assert analysis["safety_value_validated"] is False
    assert analysis["predictive_arm_engineering_safety_value"] is False
    assert analysis["broader_development_validation_justified"] is False
    assert analysis["ml_justified"] is False
    assert analysis["formal_justified"] is False
    assert criteria["mechanism_pass"] is False
    assert criteria["safety_value_spends"] == 0
    assert criteria["fallback_deadline_fraction"] == 1.0
    assert len(analysis["adaptive_packets"]) == 20
    assert all(row["reason"] in {"arm_deadline", "unarmed_fallback"}
               for row in analysis["adaptive_packets"])


def test_preexisting_scientific_evidence_hashes_remain_unchanged() -> None:
    expected = {
        "results/m9a_formal/formal_manifest.json": "52b33b0778f52870f867688d16ce8d32ac086c58a30689ea97672b533a702e8f",
        "results/m9a_formal/formal_results.json": "efaea55013747f3cedc408817ced79139f2a6654ebe0bf24269de265ef041715",
        "results/m9a_formal/formal_access_ledger.jsonl": "efd873be3adf726d10e5a3b84d98244a3adcffc3b49d0b8f2277afb43a2950ca",
        "results/m9b_formal/formal_results.json": "59bfd8c579daa04b65d34f0b24b6e1f6d478c673b11be2f5047e8f27d96f8b11",
        "results/m9b_readiness_v3/formal_access_ledger.jsonl": "bd9b6fd3bd16c3d648c4b8897cef4a66621cc6bc8eeac57d0a3f12f8b5c73bc4",
        "results/cvc_p7_readiness/scenario_manifest.json": "c64674cbb67079c4f9708a41059772ff97c8e6f0378151e2e3bbb2acaa66fbad",
        "results/cvc_p7_webots/matrix_summary.json": "0f49a8b159a90e68fc6862a871b1182366fa522de69aa844b7ab47c888cca9f4",
        "results/cvc_p7_analysis/mechanistic_analysis.json": "23d44758c633c60c0276596608dbcfbe53a2d69c7e2bfb2f653bb1511c17d8f1",
    }
    assert {name: digest(ROOT / name) for name in expected} == expected
