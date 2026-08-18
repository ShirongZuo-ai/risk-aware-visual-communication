"""Fresh-vision feasibility qualification for the draft Q1 support grid."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "config" / "cvc_q1_planner_v2.json"
GRID = ROOT / "config" / "cvc_q1_support_grid.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt"
OUT = ROOT / "results" / "cvc_q1_support_qualification"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_one(webots: Path, job: dict, identity: str, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    job_path, trace = OUT / "jobs" / f"{identity}.json", OUT / "traces" / f"{identity}.jsonl"
    job_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    env = os.environ.copy(); env.update(CVC_CONFIG=str(job_path), CVC_OUTPUT=str(trace))
    process = subprocess.run([str(webots), "--batch", "--mode=fast", "--stdout", "--stderr", str(WORLD)],
                             cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    (OUT / "logs" / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    summary = trace.with_suffix(".summary.json")
    if process.returncode or not summary.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0); args = parser.parse_args()
    planner, grid = json.loads(PLANNER.read_text()), json.loads(GRID.read_text())
    runs = []
    for scenario in grid["scenarios"]:
        job = {**scenario, "scenario": scenario["id"], "semantic": scenario["family"],
               "duration_s": grid["duration_s"], "communication_mode": "HIGH", "transmission_count": 0,
               "jpeg_quality": planner["communication"]["jpeg_quality"],
               "packet_bytes": planner["communication"]["packet_bytes"],
               "planner": planner["planner"], "visual_geometry": planner["visual_geometry"]}
        runs.append(run_one(args.webots, job, scenario["id"], args.timeout))
    feasible = [not run["collision"] and run["min_clearance_m"] >= .025 and run["goal_progress_m"] >= .35 for run in runs]
    result = {"development_only": True, "formal": False, "grid_sha256": sha256(GRID),
              "planner_sha256": sha256(PLANNER), "runs": runs,
              "fresh_feasible_by_cell": dict(zip((row["id"] for row in grid["scenarios"]), feasible)),
              "all_cells_fresh_feasible": all(feasible)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qualification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_cells_fresh_feasible": all(feasible),
                      "runs": [{k: run[k] for k in ("scenario", "collision", "min_clearance_m", "goal_progress_m", "task_success")}
                               for run in runs]}, indent=2))


if __name__ == "__main__": main()
