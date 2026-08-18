"""Run a frozen CVC-Q6 development variant in Webots at exactly 72 kB/episode."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/cvc_q6_development.json"
SOURCE = ROOT / "config/cvc_q5_stage_a.json"
PLANNER = ROOT / "config/cvc_q1_planner_v2.json"
READINESS = ROOT / "results/cvc_q6_readiness/manifest.json"
WORLD = ROOT / "simulator/worlds/cvc_q6_runner.wbt"
OUT = ROOT / "results/cvc_q6_webots"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_cells(config: dict, source: dict) -> list[dict]:
    wanted = set(config["consumed_q5_positive_families"])
    rows = []
    for family in source["families"]:
        if family["id"] not in wanted:
            continue
        events = [cell for cell in family["cells"] if cell["role"] == "event_candidate"][:4]
        controls = [cell for cell in family["cells"] if cell["role"] == "matched_control"][:1]
        rows.extend({**cell, "family": family["id"]} for cell in events + controls)
    return rows


def protected_paths() -> dict[str, Path]:
    return {
        "q6_config": CONFIG,
        "q6_protocol": ROOT / "docs/cvc_q6_development_protocol.md",
        "q6_scheduler": ROOT / "communication/cvc_q6_scheduler.py",
        "q6_controller": ROOT / "simulator/controllers/cvc_q6_runner/cvc_q6_runner.py",
        "q6_world": WORLD,
        "q6_runner": Path(__file__),
        "q6_offline_script": ROOT / "scripts/qualify_cvc_q6_offline.py",
        "q6_offline_result": ROOT / "results/cvc_q6_offline_qualification/qualification.json",
        "q5_config": SOURCE,
        "q5_manifest": ROOT / "results/cvc_q5_readiness/manifest.json",
        "q4_precursor": ROOT / "evaluation/cvc_q4_precursor.py",
        "q4_analysis": ROOT / "results/cvc_q4_analysis/analysis.json",
        "q3_controller": ROOT / "simulator/controllers/cvc_q3_runner/cvc_q3_runner.py",
        "q3_world": ROOT / "simulator/worlds/cvc_q3_runner.wbt",
        "q3_readiness": ROOT / "results/cvc_q3_readiness/manifest.json",
        "q2_safety_value": ROOT / "communication/cvc_q2_allocator.py",
        "q1_planner_config": PLANNER,
        "q1_planner": ROOT / "navigation/cvc_q1_local_planner.py",
        "m9b_warning": ROOT / "results/m9b_readiness_v3/calibration_warning_decision.json",
        "m9b_formal_result": ROOT / "results/m9b_formal/formal_results.json",
        "m9a_formal_result": ROOT / "results/m9a_formal/formal_results.json",
    }


def validate_readiness(variant: str) -> tuple[dict, list[dict]]:
    manifest = json.loads(READINESS.read_text(encoding="utf-8"))
    if not manifest.get("frozen_before_q6_webots_outcomes"):
        raise RuntimeError("Q6 readiness is not frozen")
    actual = {name: sha(path) for name, path in protected_paths().items()}
    if actual != manifest["protected_sha256"]:
        changed = sorted(name for name, digest in actual.items()
                         if digest != manifest["protected_sha256"].get(name))
        raise RuntimeError(f"Q6 protected input drift: {changed}")
    if variant not in manifest["allowed_variant_ids"]:
        raise ValueError(f"variant is outside bounded family: {variant}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cells = selected_cells(config, json.loads(SOURCE.read_text(encoding="utf-8")))
    if cells != manifest["screening_cells"]:
        raise RuntimeError("Q6 screening-cell drift")
    return manifest, cells


def run_one(webots: Path, job: dict, identity: str, out: Path, timeout: float) -> dict:
    for name in ("jobs", "traces", "logs"):
        (out / name).mkdir(parents=True, exist_ok=True)
    job_path = out / "jobs" / f"{identity}.json"
    trace_path = out / "traces" / f"{identity}.jsonl"
    summary_path = trace_path.with_suffix(".summary.json")
    canonical = json.dumps(job, indent=2, sort_keys=True) + "\n"
    if summary_path.exists():
        if not job_path.exists() or job_path.read_text(encoding="utf-8") != canonical:
            raise RuntimeError(f"existing Q6 job drift: {identity}")
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
        (out / "logs" / f"{identity}.log").write_text(stdout + stderr, encoding="utf-8")
        raise
    (out / "logs" / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode or not summary_path.exists():
        raise RuntimeError(f"{identity} failed: {(process.stdout + process.stderr)[-3000:]}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="q6-v1-value-confirmed")
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    readiness, cells = validate_readiness(args.variant)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    planner = json.loads(PLANNER.read_text(encoding="utf-8"))
    variant_row = next(row for row in config["bounded_variants"] if row["id"] == args.variant)
    out = OUT / args.variant
    manifest = {
        "study_id": config["study_id"], "variant_id": args.variant,
        "variant": variant_row["variant"], "development_only": True, "formal": False,
        "readiness_sha256": sha(READINESS), "policies": config["policies"],
        "cell_ids": [cell["id"] for cell in cells], "expected_episodes": 60,
        "episode_wire_bytes": config["communication"]["episode_wire_bytes"],
        "outcomes_read_before_manifest": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "matrix_manifest.json"
    canonical_manifest = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != canonical_manifest:
        raise RuntimeError("Q6 variant manifest drift")
    manifest_path.write_text(canonical_manifest, encoding="utf-8")

    records = []
    for policy in config["policies"]:
        for cell in cells:
            identity = f"{args.variant}__{cell['id']}__{policy}"
            job = {
                **{key: cell[key] for key in ("id", "role", "seed", "start", "goal", "objects")},
                "scenario": cell["id"], "semantic": cell["family"],
                "duration_s": config["duration_s"], "policy": policy,
                "jpeg_quality": config["communication"]["jpeg_quality"],
                "packet_bytes": config["communication"]["packet_bytes"],
                "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
                "q3": {
                    "risk_threshold": 0.14,
                    "validity_steps": config["scheduler_common"]["prepare_validity_steps"],
                    "fallback_step": config["scheduler_common"]["fallback_step"],
                    "reserve_step": config["scheduler_common"]["reserve_step"],
                    "u0_schedule": config["communication"]["u0_schedule"],
                    "safety_decision_value_thresholds": {
                        "safe_set_contraction_fraction": 0.5,
                        "matched_margin_deterioration_m": 0.02,
                        "numerical_tolerance": 1e-9,
                    },
                },
                "q6": {
                    "variant": variant_row["variant"],
                    "prepare_validity_steps": config["scheduler_common"]["prepare_validity_steps"],
                    "fallback_step": config["scheduler_common"]["fallback_step"],
                    "reserve_step": config["scheduler_common"]["reserve_step"],
                },
            }
            result = run_one(args.webots, job, identity, out, args.timeout)
            records.append(result)
            print(json.dumps({"cell": cell["id"], "family": cell["family"], "policy": policy,
                              "sends": result["send_steps"], "collision": result["collision"],
                              "clearance": result["min_clearance_m"],
                              "progress": result["goal_progress_m"]}), flush=True)
    result = {
        "study_id": config["study_id"], "variant_id": args.variant,
        "variant": variant_row["variant"], "development_only": True, "formal": False,
        "records": records,
        "all_exact_cost": all(row["wire_bytes"] == 72_000 and row["transmissions"] == 3
                              and row["byte_reconciliation"] for row in records),
        "all_mirrors_match": all(row["mirror_all_steps_match"] for row in records),
    }
    result_path = out / "matrix_results.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    result_path.with_suffix(".json.sha256").write_text(sha(result_path) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "episodes": len(records),
                      "all_exact_cost": result["all_exact_cost"],
                      "all_mirrors_match": result["all_mirrors_match"]}, indent=2))


if __name__ == "__main__":
    main()
