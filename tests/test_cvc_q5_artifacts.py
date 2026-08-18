import csv
import hashlib
import json
from pathlib import Path

from evaluation.cvc_q4_precursor import decision_space_signals, rolling_causal_trends


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_manifest_hash_and_complete_family_identity():
    path = ROOT / "results/cvc_q5_readiness/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert (ROOT / "results/cvc_q5_readiness/manifest.json.sha256").read_text().strip() == sha(path)
    content = dict(manifest); expected = content.pop("manifest_content_sha256")
    actual = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert actual == expected
    records = manifest["complete_attempted_corpus"]
    assert len(records) == 70 and len({row["cell_id"] for row in records}) == 70
    assert all(row["family"] for row in records)


def test_exact_q4_rule_and_protected_hashes_are_unchanged():
    analysis = json.loads((ROOT / "results/cvc_q5_analysis/analysis.json").read_text())
    assert analysis["rule"]["level_threshold"] == 0.6543448254639964
    assert analysis["rule"]["slope_threshold_magnitude_per_s"] == 0.11876628431105299
    assert analysis["rule"]["method"] == "ols" and analysis["rule"]["window_samples"] == 8
    manifest = json.loads((ROOT / "results/cvc_q5_readiness/manifest.json").read_text())
    assert all(sha(ROOT / relative) == expected for relative, expected in manifest["protected_sha256"].items())


def test_ols8_is_causal_and_does_not_change_with_future_samples():
    values = [.9, .88, .85, .8, .75, .7, .65, .6, .1, 1.0]
    original = rolling_causal_trends(values, window_samples=8, step_s=.032, method="ols")
    changed = rolling_causal_trends(values[:8] + [99., -99.], window_samples=8, step_s=.032, method="ols")
    assert original[7] == changed[7]


def test_causal_feature_export_excludes_evaluator_information():
    path = ROOT / "results/cvc_q5_analysis/causal_feature_dataset.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle); first = next(reader); fields = set(reader.fieldnames or ())
    assert len(first) == len(fields)
    assert not any(name.startswith("evaluator") or "collision" in name or "clearance_m" == name for name in fields)
    assert {"family", "episode", "time_s", "soft_feasibility_mass", "safety_value_triggered"} <= fields


def test_recomputed_signal_matches_exported_first_row():
    trace = ROOT / "results/cvc_q5_stage_a/traces/q5-poc-e01.jsonl"
    row = json.loads(trace.read_text(encoding="utf-8").splitlines()[0])
    signal = decision_space_signals(row["counterfactual"]["held_planner"], row["counterfactual"]["current_planner"])
    with (ROOT / "results/cvc_q5_analysis/causal_feature_dataset.csv").open(newline="", encoding="utf-8") as handle:
        exported = next(csv.DictReader(handle))
    assert float(exported["soft_feasibility_mass"]) == signal.soft_feasibility_mass
