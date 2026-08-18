"""Run the sealed Q6 generation-2 opportunity-confirmed development matrix."""
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


CONFIG = ROOT / "config/cvc_q6_generation2.json"
READINESS = ROOT / "results/cvc_q6_generation2_readiness_v2/manifest.json"
VARIANT_ID = "q6-g2-opportunity-confirmed"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_paths() -> dict[str, Path]:
    return {
        "config": CONFIG,
        "scheduler": ROOT / "communication/cvc_q6_scheduler.py",
        "controller": ROOT / "simulator/controllers/cvc_q6_runner/cvc_q6_runner.py",
        "world": ROOT / "simulator/worlds/cvc_q6_runner.wbt",
        "runner": Path(__file__),
        "q5_manifest": ROOT / "results/cvc_q5_readiness/manifest.json",
        "q4_precursor": ROOT / "evaluation/cvc_q4_precursor.py",
        "q2_safety_value": ROOT / "communication/cvc_q2_allocator.py",
        "q1_planner": ROOT / "navigation/cvc_q1_local_planner.py",
        "planner_config": PLANNER,
        "generation1_result": ROOT / "results/cvc_q6_webots/q6-v1-value-confirmed/matrix_results.json",
        "generation1_analysis": ROOT / "results/cvc_q6_analysis/q6-v1-value-confirmed.json",
        "development_ledger": ROOT / "results/cvc_q6_development/development_ledger.json",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    manifest = json.loads(READINESS.read_text(encoding="utf-8"))
    actual = {name: sha(path) for name, path in protected_paths().items()}
    if not manifest.get("frozen_before_generation2_outcomes") or actual != manifest["protected_sha256"]:
        raise RuntimeError("Q6 generation-2 readiness/protected hashes failed")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    cells = selected_cells(config, json.loads(SOURCE.read_text(encoding="utf-8")))
    if cells != manifest["screening_cells"]:
        raise RuntimeError("generation-2 cell drift")
    out = OUT / VARIANT_ID
    out.mkdir(parents=True, exist_ok=True)
    matrix_manifest = {"study_id": config["study_id"], "method_id": VARIANT_ID,
                       "development_only": True, "formal": False,
                       "readiness_sha256": sha(READINESS), "cell_ids": [row["id"] for row in cells],
                       "policies": config["policies"], "expected_episodes": 60,
                       "episode_wire_bytes": 72_000, "outcomes_read_before_manifest": False}
    matrix_path = out / "matrix_manifest.json"
    canonical = json.dumps(matrix_manifest, indent=2, sort_keys=True) + "\n"
    if matrix_path.exists() and matrix_path.read_text(encoding="utf-8") != canonical:
        raise RuntimeError("generation-2 matrix manifest drift")
    matrix_path.write_text(canonical, encoding="utf-8")
    records = []
    for policy in config["policies"]:
        for cell in cells:
            identity = f"{VARIANT_ID}__{cell['id']}__{policy}"
            job = {
                **{key: cell[key] for key in ("id", "role", "seed", "start", "goal", "objects")},
                "scenario": cell["id"], "semantic": cell["family"], "duration_s": config["duration_s"],
                "policy": policy, "jpeg_quality": config["communication"]["jpeg_quality"],
                "packet_bytes": config["communication"]["packet_bytes"],
                "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
                "q3": {"risk_threshold": .14, "validity_steps": config["scheduler"]["prepare_validity_steps"],
                       "fallback_step": config["scheduler"]["fallback_step"],
                       "reserve_step": config["scheduler"]["reserve_step"],
                       "u0_schedule": config["communication"]["u0_schedule"],
                       "safety_decision_value_thresholds": {"safe_set_contraction_fraction": .5,
                                                             "matched_margin_deterioration_m": .02,
                                                             "numerical_tolerance": 1e-9}},
                "q6": {"variant": (config["scheduler"]["A1_variant"] if policy == "A1"
                                     else config["scheduler"]["A0_variant"]),
                       "prepare_validity_steps": config["scheduler"]["prepare_validity_steps"],
                       "fallback_step": config["scheduler"]["fallback_step"],
                       "reserve_step": config["scheduler"]["reserve_step"]},
            }
            result = run_one(args.webots, job, identity, out, args.timeout)
            records.append(result)
            print(json.dumps({"cell": cell["id"], "family": cell["family"], "policy": policy,
                              "sends": result["send_steps"], "collision": result["collision"],
                              "clearance": result["min_clearance_m"], "progress": result["goal_progress_m"]}), flush=True)
    result = {"study_id": config["study_id"], "variant_id": VARIANT_ID,
              "variant": config["scheduler"]["A1_variant"], "development_only": True, "formal": False,
              "records": records,
              "all_exact_cost": all(row["wire_bytes"] == 72_000 and row["transmissions"] == 3
                                    and row["byte_reconciliation"] for row in records),
              "all_mirrors_match": all(row["mirror_all_steps_match"] for row in records)}
    result_path = out / "matrix_results.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    result_path.with_suffix(".json.sha256").write_text(sha(result_path) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "episodes": len(records), "all_exact_cost": result["all_exact_cost"],
                      "all_mirrors_match": result["all_mirrors_match"]}, indent=2))


if __name__ == "__main__":
    main()
