from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_paths() -> dict[str, Path]:
    return {
        "q3_config": ROOT / "config" / "cvc_q3_development.json",
        "q3_protocol": ROOT / "docs" / "cvc_q3_development_protocol.md",
        "q3_allocator": ROOT / "communication" / "cvc_q3_allocator.py",
        "q3_diagnosis_script": ROOT / "scripts" / "diagnose_cvc_q3_temporal.py",
        "q3_diagnosis": ROOT / "results" / "cvc_q3_temporal_diagnosis" / "diagnosis.json",
        "q3_qualification_script": ROOT / "scripts" / "qualify_cvc_q3_temporal.py",
        "q3_offline_qualification": ROOT / "results" / "cvc_q3_offline_qualification" / "qualification.json",
        "q3_profile_script": ROOT / "scripts" / "profile_cvc_q3_runtime.py",
        "q3_runtime_profile": ROOT / "results" / "cvc_q3_runtime_profile" / "profile.json",
        "q3_controller": ROOT / "simulator" / "controllers" / "cvc_q3_runner" / "cvc_q3_runner.py",
        "q3_world": ROOT / "simulator" / "worlds" / "cvc_q3_runner.wbt",
        "q3_runner": ROOT / "scripts" / "run_cvc_q3_webots.py",
        "q3_smoke_script": ROOT / "scripts" / "smoke_cvc_q3_webots.py",
        "q3_smoke": ROOT / "results" / "cvc_q3_smoke" / "qualification.json",
        "q2_readiness_manifest": ROOT / "results" / "cvc_q2_readiness" / "manifest.json",
        "q2_matrix": ROOT / "results" / "cvc_q2_webots" / "matrix_results.json",
        "q2_safety_value": ROOT / "communication" / "cvc_q2_allocator.py",
        "risk_implementation": ROOT / "communication" / "cvc_p2_protocol.py",
        "q1_readiness_manifest": ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json",
        "q1_grid": ROOT / "config" / "cvc_q1_support_grid.json",
        "q1_planner_config": ROOT / "config" / "cvc_q1_planner_v2.json",
        "q1_planner": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "q1_visual_geometry": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "q1_obstacle_memory": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
    }


def test_q3_preoutcome_manifest_and_protected_inputs_are_exact() -> None:
    path = ROOT / "results" / "cvc_q3_readiness" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    sidecar = path.with_suffix(".json.sha256").read_text(encoding="utf-8").split()[0]
    assert digest(path) == sidecar
    assert sidecar == "d05c0ca5332c4e676dbcf0058d789fb03da3837206988badd394e833520a1673"
    assert manifest["frozen_before_q3_policy_outcomes"] is True
    assert manifest["method_selection_navigation_outcomes_used"] is False
    assert manifest["chosen_candidate"] == "bounded_latch_late_token"
    assert {name: digest(path0) for name, path0 in protected_paths().items()} == manifest["protected_sha256"]


def test_q3_primary_matrix_is_complete_paired_and_exact_cost() -> None:
    matrix = json.loads((ROOT / "results" / "cvc_q3_webots" / "matrix_results.json").read_text())
    records = matrix["records"]
    assert matrix["all_exact_cost"] and matrix["all_mirrors_match"]
    assert len(records) == 30
    assert {row["policy"] for row in records} == {"U0", "A0", "A1"}
    scenarios = {row["scenario"] for row in records}
    assert len(scenarios) == 10
    assert all(sum(row["scenario"] == scenario and row["policy"] == policy for row in records) == 1
               for scenario in scenarios for policy in ("U0", "A0", "A1"))
    assert all(row["transmissions"] == 3 and row["wire_bytes"] == 72_000 for row in records)
    assert all(row["byte_reconciliation"] and row["mirror_all_steps_match"] for row in records)


def test_q3_analysis_is_strict_terminal_case_d_and_preserves_local_actuation() -> None:
    path = ROOT / "results" / "cvc_q3_analysis" / "analysis.json"
    raw = path.read_text(encoding="utf-8")
    assert "NaN" not in raw and "Infinity" not in raw
    analysis = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    mechanism = analysis["mechanism"]
    assert analysis["classification"] == "CASE D"
    assert mechanism["value_triggered_packets"] == 2
    assert mechanism["armed_late_fallback_packets"] == 4
    assert mechanism["unarmed_late_fallback_packets"] == 14
    assert mechanism["gate_pass"] is False
    assert mechanism["gate_items"]["capture_all_observed_eligible_value_episodes"] is True
    assert mechanism["gate_items"]["same_step_value_to_spend"] is True
    assert analysis["safety_value_to_send_established_locally"] is True
    assert analysis["safety_value_to_send_established_at_frozen_meaningful_frequency"] is False
    assert analysis["predictive_arm_engineering_safety_value"] is False
    assert analysis["broader_development_validation_justified"] is False
    assert analysis["ml_justified"] is False and analysis["formal_justified"] is False


def test_q3_runtime_instrumentation_reports_component_and_combined_behavior() -> None:
    analysis = json.loads((ROOT / "results" / "cvc_q3_analysis" / "analysis.json").read_text())
    runtime = analysis["prospective_runtime_profile"]
    assert runtime["frozen_latency_classification"] == "logical_scheduler_timing"
    assert runtime["any_component_deadline_miss"] is False
    assert runtime["communication_decision_total"]["p95_ms"] < 32
    assert runtime["combined_deadline_misses"] == 99
    assert runtime["prospective_assessment"] == "occasional_combined_overrun"


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
