"""Run the frozen CVC-P4 reserve mechanism on unchanged development scenes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
P4_CONFIG = ROOT / "config" / "cvc_p4_development.json"
P2_CONFIG = ROOT / "config" / "cvc_p2_development.json"
QUALIFICATION = ROOT / "results" / "cvc_p4_offline_qualification" / "qualification_results.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_p4_runner.wbt"
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
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    p4_bytes, p2_bytes = P4_CONFIG.read_bytes(), P2_CONFIG.read_bytes()
    p4, p2 = json.loads(p4_bytes), json.loads(p2_bytes)
    qualification_bytes = QUALIFICATION.read_bytes()
    qualification = json.loads(qualification_bytes)
    selected = qualification.get("selected")
    expected = ("fixed_late_050", 218, 217, [0, 109, 218])
    observed = (selected.get("candidate_id") if selected else None,
                selected.get("resolved_reserve_step") if selected else None,
                selected.get("resolved_adaptive_deadline") if selected else None,
                selected.get("resolved_u0_schedule") if selected else None)
    if not qualification.get("webots_authorized") or observed != expected:
        raise RuntimeError(f"P4 offline selection is not the frozen Webots binding: {observed}")
    result_root = ROOT / "results" / "cvc_p4_webots"
    result_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "development_only": True, "formal": False,
        "p4_config_sha256": hashlib.sha256(p4_bytes).hexdigest(),
        "p2_scenario_config_sha256": hashlib.sha256(p2_bytes).hexdigest(),
        "qualification_sha256": hashlib.sha256(qualification_bytes).hexdigest(),
        "world_sha256": hashlib.sha256(WORLD.read_bytes()).hexdigest(),
        "selected": selected, "webots": str(args.webots),
    }
    (result_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runs = []
    for scenario, scenario_config in p2["scenarios"].items():
        for policy in ("U0", "A0", "A1"):
            config = {
                **scenario_config, "scenario": scenario, "policy": policy,
                "duration_s": p4["duration_s"], "cruise_rad_s": p4["cruise_rad_s"],
                "jpeg_quality": p4["jpeg_quality"], "threshold": p4["threshold"],
                "packet_bytes": p4["packet_bytes"], "reserve_step": selected["resolved_reserve_step"],
                "u0_schedule": selected["resolved_u0_schedule"],
            }
            runs.append(run_one(args.webots, result_root, config, f"matrix__{scenario}__{policy}", args.timeout))
    costs = sorted({row["wire_bytes"] for row in runs})
    if costs != [72000] or any(row["transmissions"] != 3 for row in runs):
        raise RuntimeError(f"exact cost failure: {costs}")
    if any(row["reserve_step"] != 218 or row["budget_exhaustion_step"] != 218 for row in runs):
        raise RuntimeError("protected reserve was not preserved at step 218")
    aggregate = {"development_only": True, "formal": False, "run_count": len(runs),
                 "exact_cost_match": True, "episode_wire_bytes": costs, "runs": runs}
    (result_root / "matrix_summary.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run_count": len(runs), "exact_cost_match": True,
                      "episode_wire_bytes": costs, "reserve_step": 218}, indent=2))


if __name__ == "__main__":
    main()
