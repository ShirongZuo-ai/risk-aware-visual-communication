"""Run precursor-blinded CVC-Q5 Safety-Value support development in Webots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.cvc_q5_support import assert_stage_a_blinded, qualify_trace
from scripts.run_cvc_q1_neutral_sweep import validate_freeze


CONFIG = ROOT / "config" / "cvc_q5_stage_a.json"
PLANNER = ROOT / "config" / "cvc_q1_planner_v2.json"
Q1_READINESS = ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json"
WORLD = ROOT / "simulator" / "worlds" / "cvc_q1_runner.wbt"
OUT = ROOT / "results" / "cvc_q5_stage_a"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_one(webots: Path, job: dict, identity: str, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    job_path = OUT / "jobs" / f"{identity}.json"
    trace_path = OUT / "traces" / f"{identity}.jsonl"
    summary_path = trace_path.with_suffix(".summary.json")
    canonical = json.dumps(job, indent=2, sort_keys=True) + "\n"
    if summary_path.exists():
        if not job_path.exists() or job_path.read_text(encoding="utf-8") != canonical:
            raise RuntimeError(f"existing Q5 Stage-A job drift: {identity}")
        return json.loads(summary_path.read_text(encoding="utf-8"))
    job_path.write_text(canonical, encoding="utf-8")
    environment = os.environ.copy()
    environment.update(CVC_CONFIG=str(job_path), CVC_OUTPUT=str(trace_path))
    process = subprocess.run(
        [str(webots), "--batch", "--mode=fast", "--stdout", "--stderr", str(WORLD)],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout,
    )
    (OUT / "logs" / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode or not summary_path.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    assert_stage_a_blinded((Path(__file__), ROOT / "evaluation/cvc_q5_support.py", CONFIG))
    readiness = json.loads(Q1_READINESS.read_text(encoding="utf-8"))
    validate_freeze(readiness)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    records = []
    for family in config["families"]:
        for cell in family["cells"]:
            job = {
                **cell, "scenario": cell["id"], "semantic": family["id"],
                "duration_s": config["duration_s"],
                "communication_mode": config["communication_mode"],
                "transmission_count": config["transmission_count"],
                "jpeg_quality": planner["communication"]["jpeg_quality"],
                "packet_bytes": planner["communication"]["packet_bytes"],
                "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
            }
            summary = run_one(args.webots, job, cell["id"], args.timeout)
            trace_path = OUT / "traces" / f"{cell['id']}.jsonl"
            support = qualify_trace(load_rows(trace_path))
            record = {
                "family": family["id"], "mechanism": family["mechanism"],
                "cell_id": cell["id"], "role": cell["role"], "seed": cell["seed"],
                "job_sha256": sha(OUT / "jobs" / f"{cell['id']}.json"),
                "trace_sha256": sha(trace_path), "support": support,
                "physical": {key: summary[key] for key in (
                    "collision", "min_clearance_m", "goal_progress_m", "task_success", "steps")},
            }
            records.append(record)
            print(json.dumps({"cell": cell["id"], "family": family["id"],
                              "accepted_onsets": len(support["accepted_onsets"]),
                              "event_positive": support["event_positive"],
                              "collision": summary["collision"]}), flush=True)
    family_rows = {}
    for family in config["families"]:
        subset = [row for row in records if row["family"] == family["id"]]
        family_rows[family["id"]] = {
            "attempted_cells": len(subset),
            "positive_episodes": sum(row["support"]["event_positive"] for row in subset),
            "accepted_onsets": sum(len(row["support"]["accepted_onsets"]) for row in subset),
            "event_free_episodes": sum(not row["support"]["event_positive"] for row in subset),
            "candidate_positive_episodes": sum(row["support"]["event_positive"] and row["role"] == "event_candidate" for row in subset),
            "control_positive_episodes": sum(row["support"]["event_positive"] and row["role"] == "matched_control" for row in subset),
        }
    gates = config["support_gates"]
    positive_families = [name for name, row in family_rows.items()
                         if row["accepted_onsets"] >= gates["accepted_onsets_per_positive_family_min"]]
    gate_results = {
        "new_positive_families": len(positive_families) >= gates["new_positive_families_min"],
        "accepted_onsets_total": sum(family_rows[name]["accepted_onsets"] for name in positive_families)
        >= gates["accepted_onsets_total_min"],
        "event_free_episode_total": sum(row["event_free_episodes"] for row in family_rows.values())
        >= gates["event_free_episode_total_min"],
        "event_free_per_positive_family": all(
            family_rows[name]["event_free_episodes"] >= gates["event_free_episode_per_positive_family_min"]
            for name in positive_families
        ),
    }
    result = {
        "study_id": config["study_id"], "development_only": True, "formal": False,
        "stage": "A_blinded_physical_support", "precursor_imported_or_evaluated": False,
        "stage_a_config_sha256": sha(CONFIG), "q1_readiness_sha256": sha(Q1_READINESS),
        "q1_world_sha256": sha(WORLD),
        "q1_controller_sha256": sha(ROOT / "simulator/controllers/cvc_q1_runner/cvc_q1_runner.py"),
        "attempted_cells": len(records), "records": records,
        "family_support": family_rows, "positive_families": positive_families,
        "gate_results": gate_results, "support_gate_pass": all(gate_results.values()),
        "all_attempts_preserved": True,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "support_qualification.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    path.with_suffix(".json.sha256").write_text(f"{sha(path)}  support_qualification.json\n", encoding="utf-8")
    print(json.dumps({"support_gate_pass": result["support_gate_pass"],
                      "positive_families": positive_families,
                      "family_support": family_rows,
                      "qualification_sha256": sha(path)}, indent=2))


if __name__ == "__main__":
    main()
