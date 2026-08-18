"""Run the frozen CVC-Q1 neutral U0 transmission-count sweep in Webots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json"
OUT = ROOT / "results" / "cvc_q1_neutral_sweep"
WORLD = ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
COUNTS = (1, 2, 3, 6, 12, 24, 48)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_freeze(manifest: dict) -> None:
    if not manifest.get("frozen_before_neutral_communication_sweep"):
        raise RuntimeError("Q1 support is not frozen")
    for name, expected in manifest["protected_sha256"].items():
        mapping = {
            "support_grid": ROOT / "config" / "cvc_q1_support_grid.json",
            "planner": ROOT / "config" / "cvc_q1_planner_v2.json",
            "range_calibration": ROOT / "results" / "cvc_q1_range_calibration" / "calibration_results.json",
            "fresh_vision_qualification": ROOT / "results" / "cvc_q1_full_vision_v2" / "qualification.json",
            "support_qualification": ROOT / "results" / "cvc_q1_support_qualification" / "qualification.json",
            "world": WORLD,
            "controller": ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py",
            "planner_implementation": ROOT / "navigation" / "cvc_q1_local_planner.py",
            "visual_geometry_implementation": ROOT / "communication" / "cvc_q1_visual_geometry.py",
            "obstacle_memory_implementation": ROOT / "communication" / "cvc_q1_obstacle_memory.py",
        }
        if sha256(mapping[name]) != expected:
            raise RuntimeError(f"protected Q1 input changed after freeze: {name}")


def run_one(webots: Path, job: dict, identity: str, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    job_path = OUT / "jobs" / f"{identity}.json"
    trace_path = OUT / "traces" / f"{identity}.jsonl"
    summary_path = trace_path.with_suffix(".summary.json")
    if summary_path.is_file():
        prior = json.loads(summary_path.read_text(encoding="utf-8"))
        if prior.get("scenario") == job["scenario"] and prior.get("transmission_count") == job["transmission_count"]:
            return prior
        raise RuntimeError(f"incompatible existing result: {summary_path}")
    job_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(CVC_CONFIG=str(job_path), CVC_OUTPUT=str(trace_path))
    try:
        process = subprocess.run(
            [str(webots), "--batch", "--mode=fast", "--stdout", "--stderr", str(WORLD)],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout,
        )
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
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    validate_freeze(readiness)
    grid = json.loads((ROOT / "config" / "cvc_q1_support_grid.json").read_text(encoding="utf-8"))
    planner = json.loads((ROOT / "config" / "cvc_q1_planner_v2.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    sweep_manifest = {
        "study_id": "cvc-q1-neutral-u0-sweep-v1", "development_only": True, "formal": False,
        "readiness_manifest_sha256": sha256(READINESS), "communication_mode": "U0",
        "transmission_counts": list(COUNTS), "packet_bytes": planner["communication"]["packet_bytes"],
        "total_cells": len(grid["scenarios"]) * len(COUNTS),
    }
    manifest_path = OUT / "sweep_manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != sweep_manifest:
        raise RuntimeError("sweep manifest drift")
    manifest_path.write_text(json.dumps(sweep_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records = []
    for count in COUNTS:
        for scenario in grid["scenarios"]:
            identity = f"{scenario['id']}-u0-n{count:02d}"
            job = {**scenario, "scenario": scenario["id"], "semantic": scenario["family"],
                   "duration_s": grid["duration_s"], "communication_mode": "U0", "transmission_count": count,
                   "jpeg_quality": planner["communication"]["jpeg_quality"],
                   "packet_bytes": planner["communication"]["packet_bytes"],
                   "planner": planner["planner"], "visual_geometry": planner["visual_geometry"]}
            result = run_one(args.webots, job, identity, args.timeout)
            records.append(result)
            print(json.dumps({"scenario": result["scenario"], "count": count,
                              "collision": result["collision"], "min_clearance_m": result["min_clearance_m"],
                              "progress_m": result["goal_progress_m"]}), flush=True)
    summary = {"development_only": True, "formal": False, "records": records,
               "all_byte_reconciled": all(row["byte_reconciliation"] for row in records),
               "all_exact_wire_bytes": all(row["wire_bytes"] == row["transmission_count"] *
                                             planner["communication"]["packet_bytes"] for row in records)}
    (OUT / "sweep_results.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "records": len(records),
                      "all_byte_reconciled": summary["all_byte_reconciled"],
                      "all_exact_wire_bytes": summary["all_exact_wire_bytes"]}, indent=2))


if __name__ == "__main__":
    main()
