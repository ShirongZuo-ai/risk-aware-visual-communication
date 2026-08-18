"""Run the single frozen CVC-P6 U0/A0/A1 development comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_p6_development.json"
SCENARIOS = ROOT / "config" / "cvc_p2_development.json"
CALIBRATION = ROOT / "results" / "cvc_p6_calibration" / "calibration_results.json"
QUALIFICATION = ROOT / "results" / "cvc_p6_offline_qualification" / "qualification_results.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_p6_runner.wbt"
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_p6_runner" / "cvc_p6_runner.py"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def run_one(webots: Path, root: Path, config: dict, identity: str, timeout: float) -> dict:
    jobs, logs, traces = (root / name for name in ("jobs", "logs", "traces"))
    for directory in (jobs, logs, traces):
        directory.mkdir(parents=True, exist_ok=True)
    job, output = jobs / f"{identity}.json", traces / f"{identity}.jsonl"
    job.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = dict(os.environ)
    environment.update(CVC_CONFIG=str(job), CVC_OUTPUT=str(output))
    process = subprocess.run([str(webots), "--batch", "--mode=fast", str(WORLD)], cwd=ROOT,
                             env=environment, capture_output=True, text=True, timeout=timeout)
    (logs / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    summary_path = output.with_suffix(".summary.json")
    if process.returncode != 0 or not summary_path.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    config_bytes, scenario_bytes = CONFIG.read_bytes(), SCENARIOS.read_bytes()
    calibration_bytes, qualification_bytes = CALIBRATION.read_bytes(), QUALIFICATION.read_bytes()
    config, scenarios = json.loads(config_bytes), json.loads(scenario_bytes)
    qualification = json.loads(qualification_bytes)
    if hashlib.sha256(calibration_bytes).hexdigest() != config["calibration_results_sha256"]:
        raise RuntimeError("calibration changed after P6 freeze")
    if (not qualification["webots_development_authorized"] or
            qualification["config_sha256"] != hashlib.sha256(config_bytes).hexdigest() or
            qualification["navigation_outcomes_used"]):
        raise RuntimeError("offline mechanistic qualification is not valid")
    result_root = ROOT / "results" / "cvc_p6_webots"
    result_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "development_only": True, "formal": False, "single_frozen_comparison": True,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "scenario_config_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "calibration_sha256": hashlib.sha256(calibration_bytes).hexdigest(),
        "qualification_sha256": hashlib.sha256(qualification_bytes).hexdigest(),
        "world_sha256": hashlib.sha256(WORLD.read_bytes()).hexdigest(),
        "controller_sha256": hashlib.sha256(CONTROLLER.read_bytes()).hexdigest(),
        "webots": str(args.webots),
    }
    (result_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                                encoding="utf-8")
    runs = []
    thresholds = {key: config["novelty_thresholds"][key]
                  for key in ("bearing", "proximity", "area_relative")}
    for scenario, scenario_config in scenarios["scenarios"].items():
        for policy in ("U0", "A0", "A1"):
            job = {
                **scenario_config, "scenario": scenario, "policy": policy,
                "duration_s": config["duration_s"], "cruise_rad_s": config["cruise_rad_s"],
                "jpeg_quality": config["jpeg_quality"], "packet_bytes": config["packet_bytes"],
                "risk_threshold": config["risk_threshold"], "novelty_thresholds": thresholds,
                "deadline_steps": config["deadline_steps"], "reserve_step": config["reserve_step"],
                "u0_schedule": config["u0_schedule"], "changed_pixel_threshold": 10,
            }
            runs.append(run_one(args.webots, result_root, job, f"p6__{scenario}__{policy}", args.timeout))
    if len(runs) != 18:
        raise RuntimeError("incomplete P6 comparison")
    if any(row["transmissions"] != 3 or row["wire_bytes"] != 72000 for row in runs):
        raise RuntimeError("P6 exact communication cost failure")
    if any(row["reserve_step"] != 218 or row["budget_exhaustion_step"] != 218 for row in runs):
        raise RuntimeError("P6 protected reserve failure")
    if any(not row["mirror_all_steps_match"] for row in runs):
        raise RuntimeError("P6 receiver-held mirror failure")
    summary = {"development_only": True, "formal": False, "single_frozen_comparison": True,
               "run_count": len(runs), "exact_cost_match": True, "episode_wire_bytes": [72000],
               "all_reserves_protected": True, "all_mirrors_match": True, "runs": runs}
    (result_root / "matrix_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({"run_count": len(runs), "exact_cost_match": True,
                      "episode_wire_bytes": [72000], "all_reserves_protected": True,
                      "all_mirrors_match": True}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
