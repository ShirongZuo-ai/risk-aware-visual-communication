"""Run the qualified CVC-P3 mechanism in Webots development only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
P3_CONFIG = ROOT / "config" / "cvc_p3_development.json"
P2_CONFIG = ROOT / "config" / "cvc_p2_development.json"
QUALIFICATION = ROOT / "results" / "cvc_p3_offline_qualification" / "qualification_results.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_p3_runner.wbt"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def run_one(webots: Path, result_root: Path, config: dict, identity: str, timeout: float) -> dict:
    jobs, logs, traces = (result_root / name for name in ("jobs", "logs", "traces"))
    for directory in (jobs, logs, traces):
        directory.mkdir(parents=True, exist_ok=True)
    job = jobs / f"{identity}.json"
    output = traces / f"{identity}.jsonl"
    job.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = dict(os.environ)
    environment.update(CVC_CONFIG=str(job), CVC_OUTPUT=str(output))
    process = subprocess.run([str(webots), "--batch", "--mode=fast", str(WORLD)], cwd=ROOT,
                             env=environment, capture_output=True, text=True, timeout=timeout)
    (logs / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    summary = output.with_suffix(".summary.json")
    if process.returncode != 0 or not summary.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    p3_bytes, p2_bytes = P3_CONFIG.read_bytes(), P2_CONFIG.read_bytes()
    p3, p2 = json.loads(p3_bytes), json.loads(p2_bytes)
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    selected = qualification.get("selected")
    if not qualification.get("webots_authorized") or not selected or not selected.get("gate_pass"):
        raise RuntimeError("offline CVC-P3 actuation gate has not passed")
    if (selected["spec_id"], selected["transmissions"], selected["packet_bytes"], selected["episode_wire_bytes"]) != (
        "threshold_0.140", 3, 24000, 72000
    ):
        raise RuntimeError("qualified selection differs from the frozen Webots binding")
    result_root = ROOT / "results" / "cvc_p3_webots"
    result_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "development_only": True, "formal": False,
        "p3_config_sha256": hashlib.sha256(p3_bytes).hexdigest(),
        "p2_scenario_config_sha256": hashlib.sha256(p2_bytes).hexdigest(),
        "qualification_sha256": hashlib.sha256(QUALIFICATION.read_bytes()).hexdigest(),
        "world_sha256": hashlib.sha256(WORLD.read_bytes()).hexdigest(),
        "selection": selected, "webots": str(args.webots),
    }
    (result_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runs = []
    for scenario, scenario_config in p2["scenarios"].items():
        for policy in ("U0", "A0", "A1"):
            config = {
                **scenario_config, "scenario": scenario, "policy": policy,
                "duration_s": p3["webots"]["duration_s"],
                "cruise_rad_s": p3["webots"]["cruise_rad_s"],
                "jpeg_quality": p3["webots"]["jpeg_quality"],
                "threshold": selected["spec"]["threshold"],
                "transmissions": selected["transmissions"], "packet_bytes": selected["packet_bytes"],
            }
            runs.append(run_one(args.webots, result_root, config, f"matrix__{scenario}__{policy}", args.timeout))
    costs = sorted({row["wire_bytes"] for row in runs})
    if costs != [72000] or any(row["transmissions"] != 3 for row in runs):
        raise RuntimeError(f"matched-cost failure: costs={costs}")
    summary = {"development_only": True, "formal": False, "run_count": len(runs),
               "exact_cost_match": True, "episode_wire_bytes": costs, "runs": runs}
    (result_root / "matrix_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run_count": len(runs), "exact_cost_match": True,
                      "episode_wire_bytes": costs}, indent=2))


if __name__ == "__main__":
    main()
