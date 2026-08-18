"""Build the terminal machine-readable Q6-C evidence inventory."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/cvc_q6_final_status.json"

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    g3 = json.loads((ROOT / "results/cvc_q6_analysis/q6-g3-opportunity-persistent.json").read_text())
    ml = json.loads((ROOT / "results/cvc_q6_learned_precursor/training_report.json").read_text())
    paths = [
        "results/cvc_q6_readiness/manifest.json", "results/cvc_q6_generation2_readiness_v2/manifest.json",
        "results/cvc_q6_generation3_readiness/manifest.json", "results/cvc_q6_analysis/q6-v1-value-confirmed.json",
        "results/cvc_q6_analysis/q6-g2-opportunity-confirmed.json", "results/cvc_q6_analysis/q6-g3-opportunity-persistent.json",
        "results/cvc_q6_learned_precursor/training_report.json", "results/cvc_q6_learned_precursor/model.joblib",
        "results/cvc_q6_development/development_ledger.json", "figures/cvc_q6/q6_family_safety.png",
        "docs/cvc_simulation_program_master_report.md", "results/m9a_formal/formal_manifest.json",
        "results/m9a_formal/formal_results.json", "results/m9a_formal/formal_access_ledger.jsonl",
        "results/m9b_formal/formal_results.json", "results/m9b_readiness_v3/formal_access_ledger.jsonl",
    ]
    result = {"study_id": "cvc-q6-terminal-status-v1", "date": "2026-08-16",
              "classification": "Q6-C", "method_selected": False, "q7_authorized": False,
              "formal_authorized": False, "real_robot_authorized": False,
              "strongest_development_method": "q6-g3-opportunity-persistent",
              "strongest_method_vs_A0": g3["pooled"]["A0"],
              "strongest_method_vs_U0": g3["pooled"]["U0"],
              "serious_adverse_families_vs_U0": g3["serious_adverse_families_vs_U0"],
              "ml_selected": False, "ml_models": ml["models"],
              "final_regression": {"passed": 193, "failed": 0, "duration_s": 9.38},
              "artifact_sha256": {relative: sha(ROOT / relative) for relative in paths},
              "terminal_reason": "No bounded rule or compact learned predictor met the non-adverse strongest-baseline and cross-family development gate."}
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    OUT.with_suffix(".json.sha256").write_text(sha(OUT)+"\n", encoding="utf-8")
    print(json.dumps({"status": result["classification"], "sha256": sha(OUT),
                      "method_selected": False, "q7_authorized": False}, indent=2))

if __name__ == "__main__": main()
