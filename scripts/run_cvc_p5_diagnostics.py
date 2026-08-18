"""Run deterministic diagnostic replays of frozen CVC-P4 A0/A1 policies."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
P5_CONFIG = ROOT / "config" / "cvc_p5_diagnostic.json"
P4_CONFIG = ROOT / "config" / "cvc_p4_development.json"
P2_CONFIG = ROOT / "config" / "cvc_p2_development.json"
P4_MATRIX = ROOT / "results" / "cvc_p4_webots" / "matrix_summary.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_p5_diagnostic.wbt"
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
    p5_bytes, p4_bytes, p2_bytes = P5_CONFIG.read_bytes(), P4_CONFIG.read_bytes(), P2_CONFIG.read_bytes()
    p5, p4, p2 = json.loads(p5_bytes), json.loads(p4_bytes), json.loads(p2_bytes)
    p4_matrix_bytes = P4_MATRIX.read_bytes()
    p4_runs = {(row["scenario"], row["policy"]): row
               for row in json.loads(p4_matrix_bytes)["runs"] if row["policy"] in p5["policies"]}
    result_root = ROOT / "results" / "cvc_p5_diagnostic"
    result_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "development_only": True, "formal": False, "new_allocator_implemented": False,
        "p5_config_sha256": hashlib.sha256(p5_bytes).hexdigest(),
        "p4_config_sha256": hashlib.sha256(p4_bytes).hexdigest(),
        "p2_scenario_config_sha256": hashlib.sha256(p2_bytes).hexdigest(),
        "p4_matrix_sha256": hashlib.sha256(p4_matrix_bytes).hexdigest(),
        "world_sha256": hashlib.sha256(WORLD.read_bytes()).hexdigest(), "webots": str(args.webots),
    }
    (result_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runs = []
    for scenario, scenario_config in p2["scenarios"].items():
        for policy in p5["policies"]:
            config = {
                **scenario_config, "scenario": scenario, "policy": policy,
                "duration_s": p4["duration_s"], "cruise_rad_s": p4["cruise_rad_s"],
                "jpeg_quality": p5["jpeg_quality"], "packet_bytes": p5["packet_bytes"],
                "threshold": p4["threshold"], "reserve_step": 218,
                "changed_pixel_threshold": p5["changed_pixel_absolute_channel_threshold"],
            }
            replay = run_one(args.webots, result_root, config, f"diagnostic__{scenario}__{policy}", args.timeout)
            source = p4_runs[(scenario, policy)]
            exact_fields = ("send_steps", "collision")
            float_fields = ("min_clearance_m", "mean_clearance_m", "final_x_m", "final_y_m", "forward_progress_m")
            if any(replay[field] != source[field] for field in exact_fields):
                raise RuntimeError(f"{scenario}/{policy} did not reproduce P4 exact fields")
            if any(abs(replay[field] - source[field]) > 1e-12 for field in float_fields):
                raise RuntimeError(f"{scenario}/{policy} did not reproduce P4 physical fields")
            if replay["wire_bytes"] != 72000 or replay["shadow_packets_charged"] != 0:
                raise RuntimeError(f"{scenario}/{policy} violated diagnostic accounting")
            replay["p4_reproduction_verified"] = True
            runs.append(replay)
    aggregate = {"development_only": True, "formal": False, "new_allocator_implemented": False,
                 "run_count": len(runs), "all_p4_reproduced": all(row["p4_reproduction_verified"] for row in runs),
                 "actual_episode_wire_bytes": sorted({row["wire_bytes"] for row in runs}),
                 "shadow_packets_charged": sum(row["shadow_packets_charged"] for row in runs), "runs": runs}
    (result_root / "replay_summary.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run_count": len(runs), "all_p4_reproduced": aggregate["all_p4_reproduced"],
                      "actual_episode_wire_bytes": aggregate["actual_episode_wire_bytes"],
                      "shadow_packets_charged": aggregate["shadow_packets_charged"]}, indent=2))


if __name__ == "__main__":
    main()
