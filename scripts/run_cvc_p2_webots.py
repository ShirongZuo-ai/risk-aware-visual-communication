"""Run CVC-P2 development only; stop before any Formal C4/C5 stage."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_p2_development.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_p2_runner.wbt"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def run_one(webots: Path, root: Path, config: dict, ident: str, timeout: float) -> dict:
    jobs, logs, traces = (root / name for name in ("jobs", "logs", "traces"))
    for directory in (jobs, logs, traces):
        directory.mkdir(parents=True, exist_ok=True)
    job = jobs / f"{ident}.json"
    output = traces / f"{ident}.jsonl"
    job.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(CVC_CONFIG=str(job), CVC_OUTPUT=str(output))
    process = subprocess.run([str(webots), "--batch", "--mode=fast", str(WORLD)], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=timeout)
    (logs / f"{ident}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    summary = output.with_suffix(".summary.json")
    if process.returncode != 0 or not summary.exists():
        raise RuntimeError(f"{ident} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary.read_text(encoding="utf-8"))


def select_non_ceiling(summaries: list[dict], candidates: list[int], scenario_count: int) -> dict:
    rows = []
    for quota in candidates:
        selected = [row for row in summaries if row["transmissions"] == quota]
        collisions = sum(row["collision"] for row in selected)
        physical_failures = sum(row["collision"] or row["min_clearance_m"] < 0.12 for row in selected)
        rows.append({"transmissions": quota, "collision_count": collisions, "scenario_count": scenario_count,
                     "physical_failure_count": physical_failures,
                     "min_clearance_m": min(row["min_clearance_m"] for row in selected),
                     "mean_progress_m": sum(row["forward_progress_m"] for row in selected) / len(selected)})
    eligible = [row for row in rows if 0 < row["physical_failure_count"] < scenario_count and row["transmissions"] >= 2]
    return {"criterion": "U0 physical outcomes only: collision or clearance < 0.12 m; mixed across scenarios; quota >= 2",
            "eligible": bool(eligible), "selected_transmissions": eligible[0]["transmissions"] if eligible else None,
            "sweep": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("sweep", "matrix", "all"), default="all")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    args = parser.parse_args()
    specification_bytes = CONFIG.read_bytes()
    specification = json.loads(specification_bytes)
    root = ROOT / "results" / "cvc_p2_development"
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"development_only": True, "formal": False, "config": str(CONFIG.relative_to(ROOT)),
                "config_sha256": hashlib.sha256(specification_bytes).hexdigest(),
                "world": str(WORLD.relative_to(ROOT)), "webots": str(args.webots)}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.mode in ("sweep", "all"):
        sweep_path = root / "u0_sweep_summary.json"
        sweep = json.loads(sweep_path.read_text(encoding="utf-8"))["runs"] if sweep_path.exists() else []
        completed = {(row["transmissions"], row["scenario"]) for row in sweep}
        for quota in specification["u0_sweep_transmissions"]:
            for scenario, scenario_config in specification["scenarios"].items():
                if (quota, scenario) in completed:
                    continue
                config = {**scenario_config, "scenario": scenario, "mechanism": "U0", "risk_signal": "NONE",
                          "transmissions": quota, "packet_bytes": specification["packet_bytes"],
                          "duration_s": specification["duration_s"], "cruise_rad_s": specification["cruise_rad_s"]}
                sweep.append(run_one(args.webots, root, config, f"sweep__q{quota:03d}__{scenario}", args.timeout))
        sweep_path.write_text(json.dumps({"runs": sweep}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        selection = select_non_ceiling(sweep, specification["u0_sweep_transmissions"], len(specification["scenarios"]))
        (root / "u0_selection.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(selection, indent=2))

    if args.mode in ("matrix", "all"):
        selection_path = root / "u0_selection.json"
        if not selection_path.exists():
            raise RuntimeError("run --mode sweep before the adaptive matrix")
        quota = json.loads(selection_path.read_text(encoding="utf-8"))["selected_transmissions"]
        if quota is None:
            raise RuntimeError("U0 sweep found no non-ceiling regime; adaptive matrix intentionally not run")
        methods = [("U0", "NONE")] + [(mechanism, risk) for mechanism in ("T", "S", "TS") for risk in ("R0", "R1")]
        matrix = []
        for scenario, scenario_config in specification["scenarios"].items():
            for mechanism, risk in methods:
                config = {**scenario_config, "scenario": scenario, "mechanism": mechanism, "risk_signal": risk,
                          "transmissions": quota, "packet_bytes": specification["packet_bytes"],
                          "duration_s": specification["duration_s"], "cruise_rad_s": specification["cruise_rad_s"]}
                ident = f"matrix__{scenario}__{mechanism}__{risk}"
                matrix.append(run_one(args.webots, root, config, ident, args.timeout))
        episode_costs = sorted(set(row["wire_bytes"] for row in matrix))
        aggregate = {"development_only": True, "formal": False, "selected_transmissions": quota,
                     "episode_wire_costs": episode_costs, "exact_cost_match": len(episode_costs) == 1,
                     "runs": matrix}
        (root / "matrix_summary.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"runs": len(matrix), "exact_cost_match": len(episode_costs) == 1,
                          "episode_wire_costs": episode_costs}, indent=2))


if __name__ == "__main__":
    main()
