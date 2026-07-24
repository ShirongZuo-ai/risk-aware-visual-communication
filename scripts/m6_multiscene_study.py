"""Pre-registered M6 formal batch orchestration and episode-level analysis."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import LOCK_PATH, MANIFEST_PATH, load_and_validate_m6a_v2_manifest
from scripts.m6a_v2_pilot_completion import load_codec_aggregate, load_codec_aggregate_validation, load_joint_validation_report
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package, current_repository_head, load_prepared_launch_package_for_audit
from scripts.m6a_v2_research_pilot import run_research_pilot
from scripts.run_m6a_one_identity import load_v2_runtime_config


PREREGISTRATION_PATH = PROJECT_ROOT / "docs/results/m6_multiscene_preregistration.json"
RESULT_ROOT = PROJECT_ROOT / "results/m6_multiscene_formal"
SCENES = tuple(f"S{i}" for i in range(1, 9))
BUDGETS = ("severe", "low", "medium", "high")
METHODS = ("state_only_risk_roi", "command_conditioned_risk_roi")


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _git(*args) -> bytes:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True).stdout


def load_preregistration(path=PREREGISTRATION_PATH) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != _canonical(value):
        raise ValueError("noncanonical M6 pre-registration")
    manifest = load_and_validate_m6a_v2_manifest(MANIFEST_PATH, LOCK_PATH)
    records = {item["identity"]["episode_id"]: item for item in manifest["records"] if item["identity"]["split"] == "formal"}
    matrix = value.get("matrix")
    if value.get("schema_version") != "m6-multiscene-preregistration-v1" or not isinstance(matrix, list) or len(matrix) != 32:
        raise ValueError("invalid M6 study matrix")
    if len({item["episode_id"] for item in matrix}) != 32 or len({item["attempt_id"] for item in matrix}) != 32:
        raise ValueError("duplicate M6 study identity")
    for item in matrix:
        record = records.get(item.get("episode_id"))
        if record is None or item != {
            "attempt_id": f"m6f-{record['identity']['scenario_id'].lower()}-{record['identity']['seed']}",
            "episode_id": record["identity"]["episode_id"], "scene": record["identity"]["scenario_id"],
            "seed": record["identity"]["seed"], "source_record_sha256": record["source_record_sha256"],
        }:
            raise ValueError("M6 study matrix is not the exact frozen formal split")
    if {item["scene"] for item in matrix} != set(SCENES) or any(sum(x["scene"] == scene for x in matrix) != 4 for scene in SCENES):
        raise ValueError("M6 scene balance")
    expected = {
        "bootstrap_replicates": 10000, "bootstrap_seed": 20260724, "ci": 0.95,
        "primary_budgets": ["severe", "low"], "primary_contrast": "command_conditioned_risk_roi-minus-state_only_risk_roi",
        "primary_metric": "trajectory_critical_obstacle_boundary_recall", "support_gate": "primary_ci_lower_bound_gt_zero",
        "statistical_unit": "episode", "stratification": "scene",
    }
    if value.get("analysis") != expected or value.get("exclusions") != ["invalid_evidence", "no_eligible_critical_obstacles", "missing_paired_result"]:
        raise ValueError("M6 pre-registered analysis mismatch")
    return value


def verify_prelaunch_gate(path=PREREGISTRATION_PATH) -> tuple[str, dict]:
    head = current_repository_head()
    if _git("diff", "--quiet") or _git("diff", "--cached", "--quiet"):
        raise ValueError("tracked worktree must be clean")
    relative = str(Path(path).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    if _git("show", f"HEAD:{relative}") != Path(path).read_bytes():
        raise ValueError("pre-registration is not committed at HEAD")
    return head, load_preregistration(path)


def prepare_registered_packages(*, preregistration_path=PREREGISTRATION_PATH, package_root=None) -> list[dict]:
    head, prereg = verify_prelaunch_gate(preregistration_path)
    packages = []
    for row in prereg["matrix"]:
        kwargs = {} if package_root is None else {"package_root": Path(package_root)}
        path, package = build_prepared_launch_package(head=head, branch="main", attempt_id=row["attempt_id"], episode_id=row["episode_id"], **kwargs)
        loaded = load_prepared_launch_package_for_audit(path)
        if loaded != package or package["identity_id"] != row["episode_id"] or Path(package["prospective_attempt_root"]).exists():
            raise ValueError("prepared formal package validation failed")
        packages.append({"attempt_id": row["attempt_id"], "episode_id": row["episode_id"], "package_path": str(Path(path).resolve()), "package_sha256": package["package_sha256"]})
    return packages


def run_registered_batch(*, preregistration_path=PREREGISTRATION_PATH, package_root=None) -> dict:
    head, prereg = verify_prelaunch_gate(preregistration_path)
    root = Path(package_root) if package_root is not None else PROJECT_ROOT / "results/m6a_v2_control/prepared"
    launches = []
    for row in prereg["matrix"]:
        package_path = root / row["attempt_id"] / "package.json"
        package = load_prepared_launch_package_for_audit(package_path)
        if package["head"] != head or package["identity_id"] != row["episode_id"]:
            raise ValueError("registered package binding mismatch")
        result = run_research_pilot(package_path, confirm_attempt=row["attempt_id"])
        launches.append({"attempt_id": row["attempt_id"], "episode_id": row["episode_id"], "state": result["state"], "runner_invoked": result.get("runner_invoked", False)})
        if result["state"] != "finalized" or result.get("runner_invoked") is not True:
            raise RuntimeError(f"formal batch stopped after {row['attempt_id']}: {result['state']}")
    if len(launches) != 32 or sum(item["runner_invoked"] for item in launches) != 32:
        raise ValueError("formal launch count")
    return {"head": head, "launch_count": 32, "retry_count": 0, "launches": launches}


def _percentile(values: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def stratified_bootstrap(rows: list[dict], value_key: str, *, replicates=10000, seed=20260724) -> dict:
    groups = {scene: np.asarray([row[value_key] for row in rows if row["scene"] == scene], dtype=float) for scene in SCENES}
    if any(len(values) == 0 for values in groups.values()):
        raise ValueError("bootstrap requires every scene")
    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=float)
    for index in range(replicates):
        samples[index] = np.mean([np.mean(rng.choice(values, size=len(values), replace=True)) for values in groups.values()])
    low, high = _percentile(samples)
    return {"estimate": float(np.mean([np.mean(values) for values in groups.values()])), "ci_low": low, "ci_high": high, "replicates": replicates, "seed": seed}


def analyze_episode_cases(episodes: list[dict]) -> dict:
    included = []
    exclusions = []
    for episode in episodes:
        case_map = {(case["method"], case["budget"]): case for case in episode["cases"]}
        effects = {}
        valid = True
        for budget in BUDGETS:
            left = case_map.get((METHODS[0], budget)); right = case_map.get((METHODS[1], budget))
            if left is None or right is None:
                exclusions.append({"episode_id": episode["episode_id"], "reason": "missing_paired_result"}); valid = False; break
            if left["eligible_count"] == 0 or right["eligible_count"] == 0:
                exclusions.append({"episode_id": episode["episode_id"], "reason": "no_eligible_critical_obstacles"}); valid = False; break
            effects[f"tcobr_effect_{budget}"] = right["tcobr"] - left["tcobr"]
            for metric in ("full_psnr_db", "full_ssim", "charged_bytes", "roi_area_ratio"):
                effects[f"{metric}_effect_{budget}"] = right[metric] - left[metric]
        if valid:
            effects["primary_effect"] = (effects["tcobr_effect_severe"] + effects["tcobr_effect_low"]) / 2.0
            included.append({"episode_id": episode["episode_id"], "scene": episode["scene"], "seed": episode["seed"], **effects})
    if not included:
        raise ValueError("no analysis-eligible episodes")
    primary = stratified_bootstrap(included, "primary_effect")
    budgets = {budget: stratified_bootstrap(included, f"tcobr_effect_{budget}") for budget in BUDGETS}
    scenes = {scene: float(np.mean([row["primary_effect"] for row in included if row["scene"] == scene])) for scene in SCENES}
    secondary = {metric: {budget: float(np.mean([row[f"{metric}_effect_{budget}"] for row in included])) for budget in BUDGETS} for metric in ("full_psnr_db", "full_ssim", "charged_bytes", "roi_area_ratio")}
    return {"included": included, "exclusions": exclusions, "primary": primary, "budgets": budgets, "scenes": scenes, "secondary": secondary, "support_gate_passed": primary["ci_low"] > 0.0}


def load_completed_episodes(*, preregistration_path=PREREGISTRATION_PATH, package_root=None) -> list[dict]:
    _, prereg = verify_prelaunch_gate(preregistration_path)
    root = Path(package_root) if package_root is not None else PROJECT_ROOT / "results/m6a_v2_control/prepared"
    episodes = []
    for row in prereg["matrix"]:
        package = load_prepared_launch_package_for_audit(root / row["attempt_id"] / "package.json")
        attempt = Path(package["prospective_attempt_root"])
        runtime = json.loads(Path(package["launch_spec"]["runtime_config"]["path"]).read_text(encoding="utf-8")); load_v2_runtime_config(runtime)
        aggregate = load_codec_aggregate(attempt / "codec_aggregate.json", runtime, root=attempt)
        identity = {"launch_id":package["launch_id"],"attempt_id":package["attempt_id"],"identity_id":package["identity_id"],"scene_id":package["scene_id"],"seed":package["seed"]}
        load_codec_aggregate_validation(attempt / "codec_aggregate_validation.json", runtime, root=attempt, identity=identity)
        load_joint_validation_report(attempt / "joint_validation.json", runtime, root=attempt)
        pooled = {}
        for snapshot in aggregate["snapshot_evidence"]:
            for case in snapshot["cases"]:
                key = (case["method"], case["budget"]); item = pooled.setdefault(key, {"eligible_count":0,"recalled_count":0,"full_psnr_db":[],"full_ssim":[],"charged_bytes":[],"roi_area_ratio":[]})
                evidence = case["tcobr_evidence"]; item["eligible_count"] += evidence["eligible_count"]; item["recalled_count"] += evidence["recalled_count"]
                for metric in ("full_psnr_db","full_ssim","charged_bytes","roi_area_ratio"): item[metric].append(case[metric])
        cases = []
        for (method,budget), item in pooled.items():
            cases.append({"method":method,"budget":budget,"eligible_count":item["eligible_count"],"recalled_count":item["recalled_count"],"tcobr":item["recalled_count"]/item["eligible_count"] if item["eligible_count"] else None,**{metric:float(np.mean(item[metric])) for metric in ("full_psnr_db","full_ssim","charged_bytes","roi_area_ratio")}})
        episodes.append({"episode_id":row["episode_id"],"scene":row["scene"],"seed":row["seed"],"cases":cases})
    return episodes


def persist_analysis(analysis: dict, *, output_root=RESULT_ROOT) -> dict:
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    summary = {"schema_version":"m6-multiscene-analysis-v1", **analysis}
    summary["analysis_sha256"] = digest(summary)
    (root / "analysis_summary.json").write_bytes(_canonical(summary))
    with (root / "episode_effects.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(analysis["included"][0])); writer.writeheader(); writer.writerows(analysis["included"])
    decision = "PASS" if analysis["support_gate_passed"] else "FAIL"
    report = f"# M6 Multi-scene Formal Study\n\nSupport gate: **{decision}**.\n\nPrimary command-conditioned minus state-only TCOBR effect: {analysis['primary']['estimate']:.6f}, 95% CI [{analysis['primary']['ci_low']:.6f}, {analysis['primary']['ci_high']:.6f}].\n\nEligible episodes: {len(analysis['included'])}; exclusions: {len(analysis['exclusions'])}.\n"
    (root / "study_report.md").write_text(report, encoding="utf-8", newline="\n")
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("prepare"); sub.add_parser("run"); sub.add_parser("analyze")
    args=parser.parse_args(argv)
    if args.command=="prepare": result=prepare_registered_packages()
    elif args.command=="run": result=run_registered_batch()
    else: result=persist_analysis(analyze_episode_cases(load_completed_episodes()))
    print(json.dumps(result,sort_keys=True,indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
