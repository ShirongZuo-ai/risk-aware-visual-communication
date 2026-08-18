import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_q6_readiness_is_outcome_blind_and_complete() -> None:
    path = ROOT / "results/cvc_q6_readiness/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["frozen_before_q6_webots_outcomes"] is True
    assert manifest["q6_webots_outcomes_present_at_freeze"] is False
    assert manifest["initial_variant_id"] == "q6-v1-value-confirmed"
    assert len(manifest["screening_cells"]) == 20
    assert len(set(manifest["screening_cell_ids"])) == 20
    assert manifest["expected_episodes_per_variant"] == 60
    assert manifest["exact_episode_wire_bytes"] == 72_000
    assert sha(path) == (path.with_suffix(".json.sha256").read_text(encoding="utf-8").strip())


def test_q6_freeze_protects_qualified_q5_and_runtime_stack() -> None:
    manifest = json.loads((ROOT / "results/cvc_q6_readiness/manifest.json").read_text(encoding="utf-8"))
    assert manifest["protected_q5_manifest_sha256"] == sha(ROOT / "results/cvc_q5_readiness/manifest.json")
    required = {"q6_scheduler", "q6_controller", "q6_world", "q6_runner", "q5_manifest",
                "q4_precursor", "q3_controller", "q2_safety_value", "q1_planner", "m9b_warning"}
    assert required <= set(manifest["protected_sha256"])


def test_q6_exact_frozen_precursor_and_risk_thresholds() -> None:
    config = json.loads((ROOT / "config/cvc_q6_development.json").read_text(encoding="utf-8"))
    assert config["precursor"]["soft_feasibility_mass_max"] == 0.6543448254639964
    assert config["precursor"]["ols8_slope_strict_max_per_s"] == -0.11876628431105299
    assert config["risk"]["threshold"] == -0.010434420641870626
    assert config["risk"]["debounce_steps"] == 3
    assert config["communication"]["packet_count"] * config["communication"]["packet_bytes"] == 72_000
