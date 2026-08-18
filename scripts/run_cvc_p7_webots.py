"""Run unchanged P6-v1 U0/A0/A1 on the frozen CVC-P7 suite."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_p7_development.json"
P6_CONFIG = ROOT / "config" / "cvc_p6_development.json"
FROZEN = ROOT / "results" / "cvc_p7_readiness" / "scenario_manifest.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_p7_runner.wbt"
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_p7_runner" / "cvc_p7_runner.py"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_freeze(config: dict, p6: dict, frozen: dict) -> None:
    if frozen["scenario_config_sha256"] != sha256(CONFIG) or frozen["p6_config_sha256"] != sha256(P6_CONFIG):
        raise RuntimeError("P7 or P6 configuration changed after scenario freeze")
    for relative, expected in frozen["protected_p6_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"protected P6 source changed after freeze: {relative}")
    baseline = config["frozen_p6_baseline"]
    if (p6["packet_count"], p6["packet_bytes"], p6["episode_wire_bytes"]) != (
            baseline["packet_count"], baseline["packet_bytes"], baseline["episode_wire_bytes"]):
        raise RuntimeError("P6 budget no longer matches P7 frozen baseline")


def run_one(webots: Path, root: Path, job_config: dict, identity: str, timeout: float) -> dict:
    jobs, logs, traces = (root / name for name in ("jobs", "logs", "traces"))
    for directory in (jobs, logs, traces):
        directory.mkdir(parents=True, exist_ok=True)
    job, output = jobs / f"{identity}.json", traces / f"{identity}.jsonl"
    summary_path = output.with_suffix(".summary.json")
    if summary_path.exists() and output.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    job.write_text(json.dumps(job_config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = dict(os.environ)
    environment.update(CVC_CONFIG=str(job), CVC_OUTPUT=str(output))
    process = subprocess.run([str(webots), "--batch", "--mode=fast", str(WORLD)], cwd=ROOT,
                             env=environment, capture_output=True, text=True, timeout=timeout)
    (logs / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode != 0 or not summary_path.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    p6 = json.loads(P6_CONFIG.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    validate_freeze(config, p6, frozen)
    result_root = ROOT / "results" / "cvc_p7_webots"
    result_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "study_id": config["study_id"], "development_only": True, "formal": False,
        "frozen_suite_manifest_sha256": sha256(FROZEN),
        "scenario_config_sha256": sha256(CONFIG), "p6_config_sha256": sha256(P6_CONFIG),
        "world_sha256": sha256(WORLD), "controller_sha256": sha256(CONTROLLER),
        "protected_p6_sha256": frozen["protected_p6_sha256"], "webots": str(args.webots),
    }
    manifest_path = result_root / "manifest.json"
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != payload:
        raise RuntimeError("P7 execution manifest changed during development run")
    manifest_path.write_text(payload, encoding="utf-8")
    thresholds = {key: p6["novelty_thresholds"][key] for key in ("bearing", "proximity", "area_relative")}
    runs = []
    for scenario in config["scenarios"]:
        for policy in ("U0", "A0", "A1"):
            job = {
                **scenario, "scenario": scenario["id"], "policy": policy,
                "duration_s": p6["duration_s"], "cruise_rad_s": p6["cruise_rad_s"],
                "jpeg_quality": p6["jpeg_quality"], "packet_bytes": p6["packet_bytes"],
                "risk_threshold": p6["risk_threshold"], "novelty_thresholds": thresholds,
                "deadline_steps": p6["deadline_steps"], "reserve_step": p6["reserve_step"],
                "u0_schedule": p6["u0_schedule"], "changed_pixel_threshold": 10,
                "diagnostic_thresholds": config["diagnostic_thresholds"],
            }
            identity = f"p7__{scenario['id']}__{policy}"
            runs.append(run_one(args.webots, result_root, job, identity, args.timeout))
    if len(runs) != 36:
        raise RuntimeError("incomplete P7 comparison")
    if any(row["transmissions"] != 3 or row["wire_bytes"] != 72000 or not row["byte_reconciliation"]
           for row in runs):
        raise RuntimeError("P7 exact communication cost failure")
    if any(row["reserve_step"] != 218 or row["budget_exhaustion_step"] != 218 for row in runs):
        raise RuntimeError("P7 protected reserve failure")
    if any(not row["mirror_all_steps_match"] for row in runs):
        raise RuntimeError("P7 receiver-held mirror failure")
    summary = {"study_id": config["study_id"], "development_only": True, "formal": False,
               "frozen_p6_v1_unchanged": True, "run_count": len(runs), "exact_cost_match": True,
               "episode_wire_bytes": [72000], "all_reserves_protected": True,
               "all_mirrors_match": True, "runs": runs}
    (result_root / "matrix_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({"run_count": len(runs), "exact_cost_match": True,
                      "episode_wire_bytes": [72000], "all_reserves_protected": True,
                      "all_mirrors_match": True}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
