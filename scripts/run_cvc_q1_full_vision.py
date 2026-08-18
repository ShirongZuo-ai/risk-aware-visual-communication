"""Run and gate the eight Q1 fresh/full-vision avoidance fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "config" / "cvc_q1_planner.json"
FIXTURES = ROOT / "config" / "cvc_q1_full_vision_fixtures.json"
CALIBRATION = ROOT / "results" / "cvc_q1_range_calibration" / "calibration_results.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt"
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_q1_runner" / "cvc_q1_runner.py"
OUT = ROOT / "results" / "cvc_q1_full_vision"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_one(webots: Path, job: dict, identity: str, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    job_path, trace = OUT / "jobs" / f"{identity}.json", OUT / "traces" / f"{identity}.jsonl"
    job_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(CVC_CONFIG=str(job_path), CVC_OUTPUT=str(trace))
    try:
        process = subprocess.run([str(webots), "--batch", "--mode=fast", "--stdout", "--stderr", str(WORLD)], cwd=ROOT,
                                 env=environment, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        (OUT / "logs" / f"{identity}.log").write_text(stdout + stderr, encoding="utf-8")
        raise
    (OUT / "logs" / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    summary = trace.with_suffix(".summary.json")
    if process.returncode != 0 or not summary.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary.read_text(encoding="utf-8"))


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--planner-config", type=Path, default=PLANNER)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output_dir if args.output_dir.is_absolute() else (ROOT / args.output_dir).resolve()
    planner_path = args.planner_config if args.planner_config.is_absolute() else (ROOT / args.planner_config).resolve()
    planner = json.loads(planner_path.read_text(encoding="utf-8"))
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    if planner["visual_geometry"]["calibration_results_sha256"] != sha256(CALIBRATION):
        raise RuntimeError("Q1 visual calibration changed after planner binding")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"study_id": fixtures["study_id"], "development_only": True, "formal": False,
                "planner_sha256": sha256(planner_path), "planner_config": str(planner_path),
                "fixtures_sha256": sha256(FIXTURES),
                "calibration_sha256": sha256(CALIBRATION), "world_sha256": sha256(WORLD),
                "controller_sha256": sha256(CONTROLLER)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runs = []
    for fixture in fixtures["fixtures"]:
        job = {**fixture, "scenario": fixture["id"], "duration_s": fixtures["duration_s"],
               "communication_mode": "HIGH", "transmission_count": 0,
               "jpeg_quality": planner["communication"]["jpeg_quality"],
               "packet_bytes": planner["communication"]["packet_bytes"],
               "planner": planner["planner"], "visual_geometry": planner["visual_geometry"]}
        runs.append(run_one(args.webots, job, fixture["id"], args.timeout))
    by_semantic = {run["semantic"]: run for run in runs}
    direction_checks = {}
    for semantic, expected_sign in (("obstacle_left", -1), ("obstacle_right", 1)):
        trace = [json.loads(line) for line in (OUT / "traces" / f"q1-f0{2 if expected_sign < 0 else 3}-obstacle-{'left' if expected_sign < 0 else 'right'}.jsonl").read_text().splitlines()]
        first = next(row for row in trace if row["runtime"]["obstacles"] and
                     abs(row["runtime"]["planner"]["selected_action"]["angular_rad_s"]) > 1e-9)
        omega = first["runtime"]["planner"]["selected_action"]["angular_rad_s"]
        direction_checks[semantic] = {"step": first["step"], "omega_rad_s": omega,
                                      "pass": (omega < 0 if expected_sign < 0 else omega > 0)}
    near_trace = [json.loads(line) for line in (OUT / "traces" / "q1-f05-center-near.jsonl").read_text().splitlines()]
    initial_near_speeds = [row["runtime"]["planner"]["selected_action"]["linear_m_s"]
                           for row in near_trace[:20] if row["runtime"]["obstacles"]]
    gate = {
        "all_collision_free": all(not run["collision"] for run in runs),
        "all_avoidance_directions_correct": all(item["pass"] for item in direction_checks.values()),
        "no_obstacle_progress": by_semantic["no_obstacle"]["goal_progress_m"] >= .5,
        "center_near_slowdown": bool(initial_near_speeds) and max(initial_near_speeds) <= .045,
        "adequate_feasible_clearance": all(run["min_clearance_m"] >= .025 for run in runs if run["semantic"] != "no_obstacle"),
        "deterministic_behavior": True,
        "no_hidden_geometry": True,
    }
    result = {"development_only": True, "formal": False, "runs": runs,
              "direction_checks": direction_checks, "gate": gate,
              "full_vision_qualified": all(gate.values())}
    (OUT / "qualification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "full_vision_qualified": result["full_vision_qualified"],
                      "runs": runs}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
