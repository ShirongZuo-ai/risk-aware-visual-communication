"""Generate new CVC-Q6.5 discovery and paired SEND/HOLD Webots evidence."""
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

from communication.cvc_q65_intervention import opportunity_label


CONFIG = ROOT / "config/cvc_q65_pilot.json"
PLANNER = ROOT / "config/cvc_q1_planner_v2.json"
WORLD = ROOT / "simulator/worlds/cvc_q65_runner.wbt"
OUT = ROOT / "results/cvc_q65_development/pilot_v1"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def cells(config: dict) -> list[dict]:
    return [{**cell, "family": family["id"]}
            for family in config["families"] for cell in family["cells"]]


def run_one(webots: Path, job: dict, identity: str, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    job_path = OUT / "jobs" / f"{identity}.json"
    trace_path = OUT / "traces" / f"{identity}.jsonl"
    summary_path = trace_path.with_suffix(".summary.json")
    canonical = json.dumps(job, indent=2, sort_keys=True) + "\n"
    if summary_path.exists():
        if not job_path.exists() or job_path.read_text(encoding="utf-8") != canonical:
            raise RuntimeError(f"existing Q6.5 job drift: {identity}")
        return json.loads(summary_path.read_text(encoding="utf-8"))
    job_path.write_text(canonical, encoding="utf-8")
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
    if process.returncode or not summary_path.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def job_for(cell: dict, config: dict, planner: dict, branch: str,
            probe_step: int | None) -> dict:
    timing = config["intervention"]
    return {
        **{key: cell[key] for key in ("id", "seed", "start", "goal", "objects")},
        "scenario": cell["id"], "semantic": cell["family"], "role": "opportunity_probe",
        "duration_s": config["duration_s"], "policy": "A1",
        "jpeg_quality": config["communication"]["jpeg_quality"],
        "packet_bytes": config["communication"]["packet_bytes"],
        "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
        "q3": {
            "risk_threshold": 0.14, "validity_steps": 25,
            "fallback_step": timing["fallback_step"], "reserve_step": timing["reserve_step"],
            "u0_schedule": [0, 109, 218],
            "safety_decision_value_thresholds": {
                "safe_set_contraction_fraction": 0.5,
                "matched_margin_deterioration_m": 0.02,
                "numerical_tolerance": 1e-9
            }
        },
        "q65": {
            "branch": branch, "probe_step": probe_step,
            "min_later_gap_steps": timing["minimum_candidate_gap_steps"],
            "candidate_start_step": timing["candidate_start_step"],
            "candidate_end_step": timing["candidate_end_step"],
            "fallback_step": timing["fallback_step"], "reserve_step": timing["reserve_step"]
        }
    }


def causal_candidates(trace: list[dict], timing: dict) -> list[dict]:
    # Deliberately access policy state only; evaluator outcomes are forbidden here.
    events = [int(row["step"]) for row in trace if row["policy_state"]["candidate_event"]]
    chosen: list[dict] = []
    for step in events:
        if not chosen or step - chosen[-1]["step"] >= timing["minimum_candidate_gap_steps"]:
            chosen.append({"step": step, "source": "causal_event_onset"})
        if len(chosen) == timing["candidate_ranks_per_cell"]:
            return chosen
    fallback_pool = [*timing["clock_fallback_steps"], 112, 160]
    for step in fallback_pool:
        if timing["candidate_start_step"] <= step <= timing["candidate_end_step"] and all(
            abs(step - item["step"]) >= timing["minimum_candidate_gap_steps"] for item in chosen
        ):
            chosen.append({"step": step, "source": "clock_fallback"})
        if len(chosen) == timing["candidate_ranks_per_cell"]:
            return sorted(chosen, key=lambda item: item["step"])
    raise RuntimeError("unable to create the frozen candidate ranks")


def prefix_projection(row: dict) -> dict:
    return {key: row[key] for key in ("step", "time_s", "sender", "safety_value",
                                      "counterfactual", "receiver", "runtime", "evaluator")}


def prefix_identity(send_rows: list[dict], hold_rows: list[dict], probe: int) -> bool:
    return len(send_rows) == len(hold_rows) and all(
        prefix_projection(send_rows[index]) == prefix_projection(hold_rows[index])
        for index in range(probe)
    )


def metrics(trace: list[dict], summary: dict, near_m: float) -> dict:
    return {
        "collision": bool(summary["collision"]),
        "danger_steps": sum(float(row["evaluator"]["clearance_m"]) <= near_m for row in trace),
        "min_clearance_m": float(summary["min_clearance_m"]),
        "goal_progress_m": float(summary["goal_progress_m"]),
        "task_success": bool(summary["task_success"]),
        "wire_bytes": int(summary["wire_bytes"]),
        "transmissions": int(summary["transmissions"]),
        "mirror_all_steps_match": bool(summary["mirror_all_steps_match"]),
        "send_steps": summary["send_steps"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("discovery", "branches", "all"), default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    all_cells = cells(config)
    selected = all_cells[:args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    discovery_records = []
    if args.phase in ("discovery", "all"):
        for index, cell in enumerate(selected, 1):
            identity = f"q65-discovery__{cell['id']}"
            summary = run_one(args.webots, job_for(cell, config, planner, "D", None), identity, args.timeout)
            discovery_records.append({"cell_id": cell["id"], "family": cell["family"],
                                      "summary": summary})
            print(json.dumps({"phase":"discovery","done":index,"total":len(selected),
                              "cell":cell["id"],"sends":summary["send_steps"]}), flush=True)

    if len(selected) != len(all_cells):
        if args.phase != "discovery":
            raise RuntimeError("a limited engineering run cannot generate paired pilot evidence")
        print(json.dumps({"engineering_subset_only": True, "cells": len(selected),
                          "pilot_manifest_frozen": False}, indent=2))
        return

    manifest_path = OUT / "opportunity_manifest.json"
    if not manifest_path.exists():
        missing = [cell["id"] for cell in selected if not (OUT / "traces" / f"q65-discovery__{cell['id']}.jsonl").exists()]
        if missing:
            if args.phase == "discovery":
                return
            raise RuntimeError(f"missing discovery traces: {missing}")
        opportunities = []
        for cell in selected:
            trace_path = OUT / "traces" / f"q65-discovery__{cell['id']}.jsonl"
            for rank, candidate in enumerate(causal_candidates(read_rows(trace_path), config["intervention"]), 1):
                opportunities.append({"opportunity_id":f"{cell['id']}__p{rank}",
                                      "cell_id":cell["id"],"family":cell["family"],
                                      "rank":rank,**candidate,"discovery_trace_sha256":sha(trace_path)})
        manifest = {
            "study_id":config["study_id"],"development_only":True,"formal":False,
            "protocol_sha256":sha(ROOT / "docs/cvc_q65_opportunity_value_protocol.md"),
            "config_sha256":sha(CONFIG),"controller_sha256":sha(ROOT / "simulator/controllers/cvc_q65_runner/cvc_q65_runner.py"),
            "world_sha256":sha(WORLD),"outcomes_used_for_candidate_selection":False,
            "opportunities":opportunities
        }
        manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        manifest_path.with_suffix(".json.sha256").write_text(sha(manifest_path)+"\n",encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected_ids = {cell["id"] for cell in selected}
    opportunities = [row for row in manifest["opportunities"] if row["cell_id"] in selected_ids]
    if args.phase == "discovery":
        print(json.dumps({"manifest":str(manifest_path),"opportunities":len(opportunities),"sha256":sha(manifest_path)},indent=2))
        return

    cell_map = {cell["id"]:cell for cell in selected}
    results = []
    for index, opportunity in enumerate(opportunities, 1):
        branch_data = {}
        for branch in ("S", "H"):
            identity = f"q65-pair__{opportunity['opportunity_id']}__{branch}"
            summary = run_one(args.webots, job_for(cell_map[opportunity["cell_id"]], config, planner,
                                                   branch, opportunity["step"]), identity, args.timeout)
            branch_data[branch] = {"identity":identity,"summary":summary}
        s_trace = read_rows(OUT / "traces" / f"{branch_data['S']['identity']}.jsonl")
        h_trace = read_rows(OUT / "traces" / f"{branch_data['H']['identity']}.jsonl")
        s_metrics = metrics(s_trace, branch_data["S"]["summary"], config["utility"]["near_boundary_m"])
        h_metrics = metrics(h_trace, branch_data["H"]["summary"], config["utility"]["near_boundary_m"])
        label = opportunity_label(s_metrics, h_metrics,
            danger_step_tolerance=config["utility"]["danger_step_tolerance"],
            clearance_tolerance_m=config["utility"]["clearance_tolerance_m"],
            progress_guardrail_m=config["utility"]["progress_guardrail_m"])
        prefix_ok = prefix_identity(s_trace, h_trace, opportunity["step"])
        exact = all(item["wire_bytes"] == config["communication"]["episode_wire_bytes"]
                    and item["transmissions"] == config["communication"]["packet_count"]
                    and item["mirror_all_steps_match"] for item in (s_metrics,h_metrics))
        if not prefix_ok or not exact:
            raise RuntimeError(f"invalid paired intervention {opportunity['opportunity_id']}: prefix={prefix_ok}, exact={exact}")
        effect = {
            "receiver_image_different_steps":sum(a["receiver"]["image_sha256"] != b["receiver"]["image_sha256"] for a,b in zip(s_trace,h_trace)),
            "planner_action_different_steps":sum(a["runtime"]["planner"]["selected_action_id"] != b["runtime"]["planner"]["selected_action_id"] for a,b in zip(s_trace,h_trace)),
            "wheel_command_different_steps":sum(abs(a["runtime"]["wheel_left_rad_s"]-b["runtime"]["wheel_left_rad_s"])>1e-9 or abs(a["runtime"]["wheel_right_rad_s"]-b["runtime"]["wheel_right_rad_s"])>1e-9 for a,b in zip(s_trace,h_trace))
        }
        results.append({**opportunity,"prefix_identity":prefix_ok,"exact_cost_and_mirror":exact,
                        "S":s_metrics,"H":h_metrics,"utility":label,"causal_chain":effect})
        print(json.dumps({"phase":"pairs","done":index,"total":len(opportunities),
                          "opportunity":opportunity["opportunity_id"],"label":label["label"],
                          "S_send":s_metrics["send_steps"],"H_send":h_metrics["send_steps"]}),flush=True)
    result = {"study_id":config["study_id"],"development_only":True,"formal":False,
              "manifest_sha256":sha(manifest_path),"pairs":results,
              "all_prefix_identical":all(row["prefix_identity"] for row in results),
              "all_exact_cost_and_mirror":all(row["exact_cost_and_mirror"] for row in results)}
    result_path = OUT / "paired_results.json"
    result_path.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    result_path.with_suffix(".json.sha256").write_text(sha(result_path)+"\n",encoding="utf-8")
    print(json.dumps({"complete":True,"pairs":len(results),"sha256":sha(result_path)},indent=2))


if __name__ == "__main__":
    main()
