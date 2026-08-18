"""Seal the qualified CVC-Q1 physical-support configuration before U0 sweeps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "results" / "cvc_q1_support_readiness"
SWEEP = ROOT / "results" / "cvc_q1_neutral_sweep"
FILES = {
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if SWEEP.exists() and any(SWEEP.rglob("*.summary.json")):
        raise RuntimeError("neutral-sweep outcomes already exist; refusing retroactive freeze")
    missing = [str(path) for path in FILES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing freeze inputs: {missing}")
    fresh = json.loads(FILES["fresh_vision_qualification"].read_text(encoding="utf-8"))
    support = json.loads(FILES["support_qualification"].read_text(encoding="utf-8"))
    if not fresh.get("full_vision_qualified") or not support.get("all_cells_fresh_feasible"):
        raise RuntimeError("fresh-vision and support qualification must both pass before freeze")
    grid = json.loads(FILES["support_grid"].read_text(encoding="utf-8"))
    manifest = {
        "study_id": "cvc-q1-safety-aware-local-planning-v2",
        "development_only": True,
        "formal": False,
        "frozen_before_neutral_communication_sweep": True,
        "predictive_or_adaptive_policy_outcomes_used": False,
        "construction_boundary": grid["construction_boundary"],
        "scenario_count": len(grid["scenarios"]),
        "scenario_ids": [row["id"] for row in grid["scenarios"]],
        "physical_labels": grid["physical_labels"],
        "qualification_rule": {
            "collision_free": True,
            "minimum_clearance_m_at_least": 0.025,
            "goal_progress_m_at_least": 0.35,
            "task_success_0p5m_not_a_freeze_requirement": True,
        },
        "protected_sha256": {name: sha256(path) for name, path in FILES.items()},
    }
    READINESS.mkdir(parents=True, exist_ok=False)
    out = READINESS / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha256(out)
    out.with_suffix(".json.sha256").write_text(f"{digest}  manifest.json\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "manifest_sha256": digest,
                      "scenario_count": manifest["scenario_count"]}, indent=2))


if __name__ == "__main__":
    main()
