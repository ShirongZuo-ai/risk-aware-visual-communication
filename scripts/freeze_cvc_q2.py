"""Freeze CVC-Q2 protocol/config and protected Q1 inputs before Q2 outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "cvc_q2_readiness"
PRIMARY = ROOT / "results" / "cvc_q2_webots"
FILES = {
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
    "q1_controller": ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py"
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if PRIMARY.exists() and any(PRIMARY.rglob("*.summary.json")):
        raise RuntimeError("Q2 outcomes already exist; refusing retroactive freeze")
    if OUT.exists():
        raise RuntimeError("Q2 readiness already exists")
    qualification = json.loads(FILES["q2_offline_qualification"].read_text(encoding="utf-8"))
    if not qualification.get("passed") or qualification.get("navigation_outcomes_used"):
        raise RuntimeError("Q2 offline qualification did not pass its outcome-blind gate")
    q1_manifest = json.loads(FILES["q1_readiness_manifest"].read_text(encoding="utf-8"))
    manifest = {
        "study_id": "cvc-q2-risk-arm-safety-value-spend-v1",
        "development_only": True, "formal": False,
        "frozen_before_q2_policy_outcomes": True,
        "q1_planner_and_grid_unchanged": True,
        "scenario_ids": q1_manifest["scenario_ids"],
        "protected_sha256": {name: sha(path) for name, path in FILES.items()},
    }
    OUT.mkdir(parents=True)
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha(path)
    path.with_suffix(".json.sha256").write_text(f"{digest}  manifest.json\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "manifest_sha256": digest,
                      "scenario_count": len(manifest["scenario_ids"])}, indent=2))


if __name__ == "__main__":
    main()
