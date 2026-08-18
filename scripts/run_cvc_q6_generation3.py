"""Run only final-generation A1; reuse sealed generation-2 controls by hash."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_cvc_q6_webots import DEFAULT_WEBOTS, OUT, PLANNER, SOURCE, run_one, selected_cells

CONFIG = ROOT / "config/cvc_q6_generation3.json"
READINESS = ROOT / "results/cvc_q6_generation3_readiness/manifest.json"
CONTROL = ROOT / "results/cvc_q6_webots/q6-g2-opportunity-confirmed/matrix_results.json"
METHOD = "q6-g3-opportunity-persistent"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_paths() -> dict[str, Path]:
    return {"config": CONFIG, "scheduler": ROOT / "communication/cvc_q6_scheduler.py",
            "controller": ROOT / "simulator/controllers/cvc_q6_runner/cvc_q6_runner.py",
            "world": ROOT / "simulator/worlds/cvc_q6_runner.wbt", "runner": Path(__file__),
            "q5_manifest": ROOT / "results/cvc_q5_readiness/manifest.json",
            "q4_precursor": ROOT / "evaluation/cvc_q4_precursor.py",
            "q2_safety_value": ROOT / "communication/cvc_q2_allocator.py",
            "q1_planner": ROOT / "navigation/cvc_q1_local_planner.py",
            "planner_config": PLANNER, "control_matrix": CONTROL,
            "generation2_analysis": ROOT / "results/cvc_q6_analysis/q6-g2-opportunity-confirmed.json",
            "development_ledger": ROOT / "results/cvc_q6_development/development_ledger.json"}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0); args = parser.parse_args()
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    if not readiness.get("frozen_before_generation3_outcomes") or {
            name: sha(path) for name, path in protected_paths().items()} != readiness["protected_sha256"]:
        raise RuntimeError("generation-3 readiness/protected hashes failed")
    config = json.loads(CONFIG.read_text(encoding="utf-8")); planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    cells = selected_cells(config, json.loads(SOURCE.read_text(encoding="utf-8")))
    if cells != readiness["screening_cells"]: raise RuntimeError("generation-3 cell drift")
    controls = json.loads(CONTROL.read_text(encoding="utf-8"))
    control_records = [row for row in controls["records"] if row["policy"] in ("U0", "A0")]
    if len(control_records) != 40 or not controls["all_exact_cost"]: raise RuntimeError("invalid sealed controls")
    out = OUT / METHOD; out.mkdir(parents=True, exist_ok=True)
    matrix_manifest = {"study_id": config["study_id"], "method_id": METHOD, "development_only": True,
                       "formal": False, "readiness_sha256": sha(READINESS),
                       "new_A1_episodes": 20, "reused_control_episodes": 40,
                       "control_matrix_sha256": sha(CONTROL), "cell_ids": [row["id"] for row in cells],
                       "episode_wire_bytes": 72_000, "outcomes_read_before_manifest": False}
    mp = out / "matrix_manifest.json"; canonical = json.dumps(matrix_manifest, indent=2, sort_keys=True) + "\n"
    if mp.exists() and mp.read_text(encoding="utf-8") != canonical: raise RuntimeError("generation-3 manifest drift")
    mp.write_text(canonical, encoding="utf-8")
    new_records = []
    for cell in cells:
        identity = f"{METHOD}__{cell['id']}__A1"
        job = {**{key: cell[key] for key in ("id", "role", "seed", "start", "goal", "objects")},
               "scenario": cell["id"], "semantic": cell["family"], "duration_s": config["duration_s"],
               "policy": "A1", "jpeg_quality": config["communication"]["jpeg_quality"],
               "packet_bytes": config["communication"]["packet_bytes"],
               "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
               "q3": {"risk_threshold": .14, "validity_steps": 25, "fallback_step": 217,
                      "reserve_step": 218, "u0_schedule": [0, 109, 218],
                      "safety_decision_value_thresholds": {"safe_set_contraction_fraction": .5,
                                                            "matched_margin_deterioration_m": .02,
                                                            "numerical_tolerance": 1e-9}},
               "q6": {"variant": "opportunity_persistent", "prepare_validity_steps": 25,
                      "fallback_step": 217, "reserve_step": 218}}
        result = run_one(args.webots, job, identity, out, args.timeout); new_records.append(result)
        print(json.dumps({"cell": cell["id"], "family": cell["family"], "policy": "A1",
                          "sends": result["send_steps"], "collision": result["collision"],
                          "clearance": result["min_clearance_m"], "progress": result["goal_progress_m"]}), flush=True)
    records = control_records + new_records
    result = {"study_id": config["study_id"], "variant_id": METHOD, "variant": "opportunity_persistent",
              "development_only": True, "formal": False, "records": records,
              "reused_control_provenance": {"matrix": CONTROL.relative_to(ROOT).as_posix(), "sha256": sha(CONTROL)},
              "all_exact_cost": all(row["wire_bytes"] == 72_000 and row["transmissions"] == 3
                                    and row["byte_reconciliation"] for row in records),
              "all_mirrors_match": all(row["mirror_all_steps_match"] for row in records)}
    rp = out / "matrix_results.json"; rp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rp.with_suffix(".json.sha256").write_text(sha(rp) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "new_episodes": 20, "reused_controls": 40,
                      "all_exact_cost": result["all_exact_cost"]}, indent=2))


if __name__ == "__main__": main()
