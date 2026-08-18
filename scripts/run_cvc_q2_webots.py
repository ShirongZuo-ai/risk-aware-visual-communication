"""Run the frozen ten-cell CVC-Q2 U0/A0/A1 development matrix."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_q2_development.json"
GRID = ROOT / "config" / "cvc_q1_support_grid.json"
PLANNER = ROOT / "config" / "cvc_q1_planner_v2.json"
READINESS = ROOT / "results" / "cvc_q2_readiness" / "manifest.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_q2_runner.wbt"
OUT = ROOT / "results" / "cvc_q2_webots"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_readiness() -> dict:
    manifest = json.loads(READINESS.read_text(encoding="utf-8"))
    if not manifest.get("frozen_before_q2_policy_outcomes"):
        raise RuntimeError("Q2 is not frozen")
    mapping = {
        "q2_config": CONFIG,
        "q2_protocol": ROOT / "docs" / "cvc_q2_development_protocol.md",
        "q2_allocator": ROOT / "communication" / "cvc_q2_allocator.py",
        "q2_offline_qualification": ROOT / "results" / "cvc_q2_offline_qualification" / "qualification.json",
        "q2_controller": ROOT / "simulator" / "controllers" / "cvc_q2_runner" / "cvc_q2_runner.py",
        "q2_world": WORLD,
        "q2_runner": ROOT / "scripts" / "run_cvc_q2_webots.py",
        "q2_smoke_qualification": ROOT / "results" / "cvc_q2_smoke" / "qualification.json",
        "risk_implementation": ROOT / "communication" / "cvc_p2_protocol.py",
        "q1_readiness_manifest": ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json",
        "q1_grid": GRID,
        "q1_planner_config": PLANNER,
        "q1_planner": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "q1_visual_geometry": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "q1_obstacle_memory": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
        "q1_range_calibration": ROOT / "results" / "cvc_q1_range_calibration" / "calibration_results.json",
        "q1_world": ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt",
        "q1_controller": ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py",
    }
    actual = {name: sha(path) for name, path in mapping.items()}
    if actual != manifest["protected_sha256"]:
        changed = [name for name in actual if actual[name] != manifest["protected_sha256"].get(name)]
        raise RuntimeError(f"Q2 protected input changed after freeze: {changed}")
    return manifest


def run_one(webots: Path, job: dict, identity: str, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    job_path = OUT / "jobs" / f"{identity}.json"
    trace_path = OUT / "traces" / f"{identity}.jsonl"
    summary_path = trace_path.with_suffix(".summary.json")
    if summary_path.is_file():
        prior = json.loads(summary_path.read_text(encoding="utf-8"))
        if prior.get("scenario") == job["scenario"] and prior.get("policy") == job["policy"]:
            return prior
        raise RuntimeError(f"incompatible prior Q2 result: {summary_path}")
    job_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = os.environ.copy(); environment.update(CVC_CONFIG=str(job_path), CVC_OUTPUT=str(trace_path))
    try:
        process = subprocess.run([str(webots), "--batch", "--mode=fast", "--stdout", "--stderr", str(WORLD)],
                                 cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        (OUT / "logs" / f"{identity}.log").write_text(stdout + stderr, encoding="utf-8")
        raise
    (OUT / "logs" / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode or not summary_path.is_file():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    readiness = validate_readiness()
    q2 = json.loads(CONFIG.read_text(encoding="utf-8"))
    grid = json.loads(GRID.read_text(encoding="utf-8"))
    planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    matrix_manifest = {
        "study_id": q2["study_id"], "development_only": True, "formal": False,
        "readiness_sha256": sha(READINESS), "policies": q2["policies"],
        "scenario_ids": readiness["scenario_ids"], "expected_episodes": 30,
        "episode_wire_bytes": q2["communication"]["episode_wire_bytes"],
    }
    manifest_path = OUT / "matrix_manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != matrix_manifest:
        raise RuntimeError("Q2 matrix manifest drift")
    manifest_path.write_text(json.dumps(matrix_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records = []
    for policy in q2["policies"]:
        for scenario in grid["scenarios"]:
            identity = f"q2__{scenario['id']}__{policy}"
            job = {**scenario, "scenario": scenario["id"], "semantic": scenario["family"],
                   "duration_s": q2["duration_s"], "policy": policy,
                   "jpeg_quality": q2["communication"]["jpeg_quality"],
                   "packet_bytes": q2["communication"]["packet_bytes"],
                   "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
                   "q2": {"risk_threshold": q2["risk"]["threshold"],
                          "deadline_steps": q2["communication"]["deadline_steps_after_arm"],
                          "reserve_step": q2["communication"]["protected_reserve_step"],
                          "u0_schedule": q2["communication"]["u0_schedule"],
                          "safety_decision_value_thresholds": {
                              "safe_set_contraction_fraction": q2["safety_decision_value"]["safe_set_contraction_fraction"],
                              "matched_margin_deterioration_m": q2["safety_decision_value"]["matched_margin_deterioration_m"],
                              "numerical_tolerance": q2["safety_decision_value"]["numerical_tolerance"]}}}
            result = run_one(args.webots, job, identity, args.timeout)
            records.append(result)
            print(json.dumps({"scenario": result["scenario"], "policy": policy,
                              "send_steps": result["send_steps"], "reason": result["adaptive_reason"],
                              "collision": result["collision"], "min_clearance_m": result["min_clearance_m"],
                              "progress_m": result["goal_progress_m"]}), flush=True)
    result = {"development_only": True, "formal": False, "records": records,
              "all_exact_cost": all(row["wire_bytes"] == 72000 and row["transmissions"] == 3 and
                                    row["byte_reconciliation"] for row in records),
              "all_mirrors_match": all(row["mirror_all_steps_match"] for row in records)}
    (OUT / "matrix_results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "episodes": len(records),
                      "all_exact_cost": result["all_exact_cost"],
                      "all_mirrors_match": result["all_mirrors_match"]}, indent=2))


if __name__ == "__main__":
    main()
