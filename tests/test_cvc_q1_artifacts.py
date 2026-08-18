from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_manifest_is_deterministic_and_precedes_only_neutral_sweep() -> None:
    manifest_path = ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (manifest_path.with_suffix(".json.sha256").read_text(encoding="utf-8").split()[0])
    assert digest(manifest_path) == expected
    assert manifest["frozen_before_neutral_communication_sweep"] is True
    assert manifest["predictive_or_adaptive_policy_outcomes_used"] is False
    assert manifest["scenario_count"] == 10
    assert len(set(manifest["scenario_ids"])) == 10
    grid = json.loads((ROOT / "config" / "cvc_q1_support_grid.json").read_text(encoding="utf-8"))
    assert len({row["seed"] for row in grid["scenarios"]}) == 10
    assert manifest["scenario_ids"] == [row["id"] for row in grid["scenarios"]]


def test_frozen_inputs_still_match_manifest() -> None:
    manifest = json.loads((ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json").read_text())
    paths = {
        "support_grid": ROOT / "config" / "cvc_q1_support_grid.json",
        "planner": ROOT / "config" / "cvc_q1_planner_v2.json",
        "range_calibration": ROOT / "results" / "cvc_q1_range_calibration" / "calibration_results.json",
        "fresh_vision_qualification": ROOT / "results" / "cvc_q1_full_vision_v2" / "qualification.json",
        "support_qualification": ROOT / "results" / "cvc_q1_support_qualification" / "qualification.json",
        "world": ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt",
        "controller": ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py",
        "planner_implementation": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "visual_geometry_implementation": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "obstacle_memory_implementation": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
    }
    assert {name: digest(path) for name, path in paths.items()} == manifest["protected_sha256"]


def test_neutral_sweep_is_complete_exact_and_contains_no_adaptive_policy() -> None:
    result = json.loads((ROOT / "results" / "cvc_q1_neutral_sweep" / "sweep_results.json").read_text())
    assert result["all_byte_reconciled"] is True
    assert result["all_exact_wire_bytes"] is True
    assert len(result["records"]) == 70
    assert {row["communication_mode"] for row in result["records"]} == {"U0"}
    assert {row["transmission_count"] for row in result["records"]} == {1, 2, 3, 6, 12, 24, 48}
    assert all(row["wire_bytes"] == row["transmission_count"] * 24_000 for row in result["records"])
    assert all(row["content_bytes"] + row["metadata_bytes"] + row["padding_bytes"] == row["wire_bytes"]
               for row in result["records"])


def test_analysis_json_is_strict_and_decision_value_is_measurable() -> None:
    raw = (ROOT / "results" / "cvc_q1_analysis" / "analysis.json").read_text(encoding="utf-8")
    assert "NaN" not in raw and "Infinity" not in raw
    analysis = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert analysis["classification"] == "CASE A"
    assert analysis["high_safety_information_value_examples"]
    assert analysis["visually_changed_but_safety_irrelevant_examples"]
    assert any(row["safe_set_change_steps"] > 0 for row in analysis["episode_decision_diagnostics"])
    assert any(row["action_change_steps"] > 0 for row in analysis["episode_decision_diagnostics"])


def test_protected_scientific_evidence_hashes_unchanged() -> None:
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
