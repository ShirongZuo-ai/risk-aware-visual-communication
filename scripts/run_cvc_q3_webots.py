"""Run the frozen ten-cell CVC-Q3 U0/A0/A1 development matrix."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_q3_development.json"
GRID = ROOT / "config" / "cvc_q1_support_grid.json"
PLANNER = ROOT / "config" / "cvc_q1_planner_v2.json"
READINESS = ROOT / "results" / "cvc_q3_readiness" / "manifest.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_q3_runner.wbt"
OUT = ROOT / "results" / "cvc_q3_webots"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_paths() -> dict[str, Path]:
    return {
        "q3_config": CONFIG,
        "q3_protocol": ROOT / "docs" / "cvc_q3_development_protocol.md",
        "q3_allocator": ROOT / "communication" / "cvc_q3_allocator.py",
        "q3_diagnosis_script": ROOT / "scripts" / "diagnose_cvc_q3_temporal.py",
        "q3_diagnosis": ROOT / "results" / "cvc_q3_temporal_diagnosis" / "diagnosis.json",
        "q3_qualification_script": ROOT / "scripts" / "qualify_cvc_q3_temporal.py",
        "q3_offline_qualification": ROOT / "results" / "cvc_q3_offline_qualification" / "qualification.json",
        "q3_profile_script": ROOT / "scripts" / "profile_cvc_q3_runtime.py",
        "q3_runtime_profile": ROOT / "results" / "cvc_q3_runtime_profile" / "profile.json",
        "q3_controller": ROOT / "simulator" / "controllers" / "cvc_q3_runner" / "cvc_q3_runner.py",
        "q3_world": WORLD,
        "q3_runner": ROOT / "scripts" / "run_cvc_q3_webots.py",
        "q3_smoke_script": ROOT / "scripts" / "smoke_cvc_q3_webots.py",
        "q3_smoke": ROOT / "results" / "cvc_q3_smoke" / "qualification.json",
        "q2_readiness_manifest": ROOT / "results" / "cvc_q2_readiness" / "manifest.json",
        "q2_matrix": ROOT / "results" / "cvc_q2_webots" / "matrix_results.json",
        "q2_safety_value": ROOT / "communication" / "cvc_q2_allocator.py",
        "risk_implementation": ROOT / "communication" / "cvc_p2_protocol.py",
        "q1_readiness_manifest": ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json",
        "q1_grid": GRID,
        "q1_planner_config": PLANNER,
        "q1_planner": ROOT / "navigation" / "cvc_q1_local_planner.py",
        "q1_visual_geometry": ROOT / "communication" / "cvc_q1_visual_geometry.py",
        "q1_obstacle_memory": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
    }


def validate_readiness() -> dict:
    manifest = json.loads(READINESS.read_text(encoding="utf-8"))
    if not manifest.get("frozen_before_q3_policy_outcomes"):
        raise RuntimeError("Q3 is not frozen")
    actual = {name: sha(path) for name, path in protected_paths().items()}
    if actual != manifest["protected_sha256"]:
        changed = [name for name in actual if actual[name] != manifest["protected_sha256"].get(name)]
        raise RuntimeError(f"Q3 protected input changed after freeze: {changed}")
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
        raise RuntimeError(f"incompatible prior Q3 result: {summary_path}")
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
    q3 = json.loads(CONFIG.read_text(encoding="utf-8"))
    grid = json.loads(GRID.read_text(encoding="utf-8"))
    planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    matrix_manifest = {
        "study_id": q3["study_id"], "development_only": True, "formal": False,
        "readiness_sha256": sha(READINESS), "policies": q3["policies"],
        "scenario_ids": readiness["scenario_ids"], "expected_episodes": 30,
        "episode_wire_bytes": q3["communication"]["episode_wire_bytes"],
    }
    manifest_path = OUT / "matrix_manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != matrix_manifest:
        raise RuntimeError("Q3 matrix manifest drift")
    manifest_path.write_text(json.dumps(matrix_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records = []
    for policy in q3["policies"]:
        for scenario in grid["scenarios"]:
            identity = f"q3__{scenario['id']}__{policy}"
            job = {**scenario, "scenario": scenario["id"], "semantic": scenario["family"],
                   "duration_s": q3["duration_s"], "policy": policy,
                   "jpeg_quality": q3["communication"]["jpeg_quality"],
                   "packet_bytes": q3["communication"]["packet_bytes"],
                   "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
                   "q3": {"risk_threshold": q3["risk"]["threshold"],
                          "validity_steps": q3["scheduler"]["validity_steps"],
                          "fallback_step": q3["scheduler"]["fallback_step"],
                          "reserve_step": q3["scheduler"]["reserve_step"],
                          "u0_schedule": q3["scheduler"]["u0_schedule"],
                          "safety_decision_value_thresholds": {
                              "safe_set_contraction_fraction": q3["safety_decision_value"]["safe_set_contraction_fraction"],
                              "matched_margin_deterioration_m": q3["safety_decision_value"]["matched_margin_deterioration_m"],
                              "numerical_tolerance": q3["safety_decision_value"]["numerical_tolerance"]}}}
            result = run_one(args.webots, job, identity, args.timeout)
            records.append(result)
            print(json.dumps({"scenario": result["scenario"], "policy": policy,
                              "send_steps": result["send_steps"], "reason": result["adaptive_reason"],
                              "value_send": result["value_triggered_spend"],
                              "collision": result["collision"], "min_clearance_m": result["min_clearance_m"],
                              "progress_m": result["goal_progress_m"]}), flush=True)
    result = {"development_only": True, "formal": False, "records": records,
              "all_exact_cost": all(row["wire_bytes"] == 72_000 and row["transmissions"] == 3 and
                                    row["byte_reconciliation"] for row in records),
              "all_mirrors_match": all(row["mirror_all_steps_match"] for row in records)}
    (OUT / "matrix_results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "episodes": len(records),
                      "all_exact_cost": result["all_exact_cost"],
                      "all_mirrors_match": result["all_mirrors_match"]}, indent=2))


if __name__ == "__main__":
    main()
