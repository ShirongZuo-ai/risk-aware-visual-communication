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
from scripts.m6a_v3_episode_source import LOCK_PATH, MANIFEST_PATH, load_and_validate_m6a_v3_manifest
from scripts.m6a_v2_episode_source import LOCK_PATH as V2_LOCK_PATH, MANIFEST_PATH as V2_MANIFEST_PATH, load_and_validate_m6a_v2_manifest
from scripts.m6a_v2_pilot_completion import load_codec_aggregate, load_codec_aggregate_validation, load_joint_validation_report
from scripts.m6a_v2_runtime_evidence import load_runtime_manifest
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package, current_repository_head, load_prepared_launch_package_for_audit
from scripts.m6a_v2_research_pilot import run_research_pilot
from scripts.run_m6a_one_identity import load_v2_runtime_config


PREREGISTRATION_PATH = PROJECT_ROOT / "docs/results/m6_multiscene_v3_preregistration.json"
ANALYSIS_AMENDMENT_PATH = PROJECT_ROOT / "docs/results/m6_v3_eligibility_conditional_analysis_amendment.json"
RESULT_ROOT = PROJECT_ROOT / "results/m6_multiscene_formal_v3"
SCENES = tuple(f"S{i}" for i in range(1, 9))
ELIGIBLE_SCENES = ("S2", "S3", "S4", "S5", "S6")
BUDGETS = ("severe", "low", "medium", "high")
METHODS = ("state_only_risk_roi", "command_conditioned_risk_roi")


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _git(*args) -> bytes:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True).stdout


def preregistration_payload() -> dict:
    manifest = load_and_validate_m6a_v3_manifest(MANIFEST_PATH, LOCK_PATH)
    v2 = load_and_validate_m6a_v2_manifest(V2_MANIFEST_PATH, V2_LOCK_PATH)
    records = manifest["records"]
    new_ids = {item["identity"]["episode_id"] for item in records}
    new_seeds = {item["identity"]["seed"] for item in records}
    old_ids = {item["identity"]["episode_id"] for item in v2["records"]}
    old_seeds = {item["identity"]["seed"] for item in v2["records"]}
    if new_ids & old_ids or new_seeds & old_seeds:
        raise ValueError("v3 study overlaps frozen v2 identities")
    matrix = [{
        "attempt_id": f"m6v3f-{item['identity']['scenario_id'].lower()}-{item['identity']['seed']}",
        "episode_id": item["identity"]["episode_id"],
        "scene": item["identity"]["scenario_id"],
        "seed": item["identity"]["seed"],
        "source_record_sha256": item["source_record_sha256"],
    } for item in records]
    return {
        "schema_version": "m6-multiscene-v3-preregistration-v1",
        "status": "frozen-before-data-generation",
        "manifest_sha256": hashlib.sha256(Path(MANIFEST_PATH).read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256(Path(LOCK_PATH).read_bytes()).hexdigest(),
        "parent_v2_manifest_sha256": hashlib.sha256(Path(V2_MANIFEST_PATH).read_bytes()).hexdigest(),
        "parent_v2_lock_sha256": hashlib.sha256(Path(V2_LOCK_PATH).read_bytes()).hexdigest(),
        "data_separation": {
            "registered_identity_overlap_with_v2": 0,
            "registered_seed_overlap_with_v2": 0,
            "v2_identity_count": len(old_ids),
            "v2_seed_count": len(old_seeds),
            "registered_identity_count": len(new_ids),
            "registered_seed_count": len(new_seeds),
            "prior_pilot_smoke_and_failed_formal_are_v2_bound": True,
        },
        "analysis": {
            "bootstrap_replicates": 10000, "bootstrap_seed": 20260724, "ci": 0.95,
            "primary_budgets": ["severe", "low"],
            "primary_contrast": "command_conditioned_risk_roi-minus-state_only_risk_roi",
            "primary_metric": "trajectory_critical_obstacle_boundary_recall",
            "support_gate": "primary_ci_lower_bound_gt_zero",
            "statistical_unit": "episode", "stratification": "scene",
        },
        "exclusions": ["invalid_evidence", "no_eligible_critical_obstacles", "missing_paired_result"],
        "matrix": matrix,
    }


def load_preregistration(path=PREREGISTRATION_PATH) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != _canonical(value):
        raise ValueError("noncanonical M6 pre-registration")
    manifest = load_and_validate_m6a_v3_manifest(MANIFEST_PATH, LOCK_PATH)
    if value != preregistration_payload():
        raise ValueError("nonreproducible M6 v3 pre-registration")
    records = {item["identity"]["episode_id"]: item for item in manifest["records"] if item["identity"]["split"] == "formal"}
    matrix = value.get("matrix")
    if value.get("schema_version") != "m6-multiscene-v3-preregistration-v1" or not isinstance(matrix, list) or len(matrix) != 32:
        raise ValueError("invalid M6 study matrix")
    if value.get("manifest_sha256") != hashlib.sha256(Path(MANIFEST_PATH).read_bytes()).hexdigest() or value.get("lock_sha256") != hashlib.sha256(Path(LOCK_PATH).read_bytes()).hexdigest():
        raise ValueError("M6 v3 pre-registration authority binding")
    if len({item["episode_id"] for item in matrix}) != 32 or len({item["attempt_id"] for item in matrix}) != 32:
        raise ValueError("duplicate M6 study identity")
    for item in matrix:
        record = records.get(item.get("episode_id"))
        if record is None or item != {
            "attempt_id": f"m6v3f-{record['identity']['scenario_id'].lower()}-{record['identity']['seed']}",
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


def load_analysis_amendment(path=ANALYSIS_AMENDMENT_PATH) -> dict:
    path = Path(path); raw = path.read_bytes(); value = json.loads(raw)
    if raw != _canonical(value) or value.get("amendment_sha256") != digest({key: item for key, item in value.items() if key != "amendment_sha256"}):
        raise ValueError("noncanonical M6 v3 analysis amendment")
    expected_ids = [
        *[f"m6a_v3_formal_s2_seed{seed}" for seed in range(630200, 630204)],
        *[f"m6a_v3_formal_s3_seed{seed}" for seed in range(630300, 630304)],
        "m6a_v3_formal_s4_seed630400", "m6a_v3_formal_s4_seed630402",
        "m6a_v3_formal_s5_seed630500", "m6a_v3_formal_s5_seed630502", "m6a_v3_formal_s5_seed630503",
        *[f"m6a_v3_formal_s6_seed{seed}" for seed in range(630600, 630604)],
    ]
    if (
        value.get("schema_version") != "m6-v3-eligibility-conditional-amendment-v1"
        or value.get("status") != "frozen-before-outcome-calculation"
        or value.get("original_eight_scene_gate") != {"status": "NOT_EVALUATED", "reason": "empty_scene_strata_after_preregistered_eligibility_exclusions"}
        or value.get("conditional_analysis") != {
            "bootstrap_replicates": 10000, "bootstrap_seed": 20260724, "ci": 0.95,
            "eligible_episode_count": 17, "eligible_episode_ids": expected_ids,
            "eligible_scenes": list(ELIGIBLE_SCENES), "scene_weighting": "equal",
            "resampling_unit": "episode_within_scene", "support_gate": "conditional_ci_lower_bound_gt_zero",
            "undefined_episode_rule": "exclude_without_imputation",
        }
        or value.get("secondary_analysis") != {"episode_count": 32, "eligibility_filter": "none", "metrics": ["full_psnr_db", "full_ssim", "charged_bytes", "roi_area_ratio"]}
    ):
        raise ValueError("M6 v3 analysis amendment mismatch")
    return value


def verify_analysis_amendment(path=ANALYSIS_AMENDMENT_PATH) -> dict:
    relative = str(Path(path).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    if _git("show", f"HEAD:{relative}") != Path(path).read_bytes():
        raise ValueError("analysis amendment is not committed at HEAD")
    return load_analysis_amendment(path)


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
        path, package = build_prepared_launch_package(head=head, branch="main", attempt_id=row["attempt_id"], episode_id=row["episode_id"], manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH, **kwargs)
        loaded = load_prepared_launch_package_for_audit(path)
        if loaded != package or package["identity_id"] != row["episode_id"] or package.get("manifest_authority_version") != "v3" or Path(package["prospective_attempt_root"]).exists():
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


def stratified_bootstrap(rows: list[dict], value_key: str, *, replicates=10000, seed=20260724, scenes=SCENES) -> dict:
    scenes = tuple(scenes)
    groups = {scene: np.asarray([row[value_key] for row in rows if row["scene"] == scene], dtype=float) for scene in scenes}
    if any(len(values) == 0 for values in groups.values()):
        raise ValueError("bootstrap requires every scene")
    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=float)
    for index in range(replicates):
        samples[index] = np.mean([np.mean(rng.choice(values, size=len(values), replace=True)) for values in groups.values()])
    low, high = _percentile(samples)
    return {"estimate": float(np.mean([np.mean(values) for values in groups.values()])), "ci_low": low, "ci_high": high, "replicates": replicates, "seed": seed, "scenes": list(scenes), "scene_weighting": "equal"}


def analyze_episode_cases(episodes: list[dict]) -> dict:
    amendment = load_analysis_amendment()
    included = []; secondary_rows = []
    exclusions = []
    if len(episodes) != 32 or len({episode["episode_id"] for episode in episodes}) != 32:
        raise ValueError("conditional analysis requires 32 unique validated episodes")
    for episode in episodes:
        case_map = {(case["method"], case["budget"]): case for case in episode["cases"]}
        effects = {}; secondary_effects = {}; valid = True
        for budget in BUDGETS:
            left = case_map.get((METHODS[0], budget)); right = case_map.get((METHODS[1], budget))
            if left is None or right is None:
                exclusions.append({"episode_id": episode["episode_id"], "reason": "missing_paired_result"}); valid = False; break
            for metric in ("full_psnr_db", "full_ssim", "charged_bytes", "roi_area_ratio"):
                secondary_effects[f"{metric}_effect_{budget}"] = right[metric] - left[metric]
            if left["eligible_count"] == 0 or right["eligible_count"] == 0:
                valid = False
                continue
            effects[f"tcobr_effect_{budget}"] = right["tcobr"] - left["tcobr"]
        if len(secondary_effects) != 16:
            raise ValueError("secondary paired result missing from validated episode")
        secondary_rows.append({"episode_id": episode["episode_id"], "scene": episode["scene"], "seed": episode["seed"], **secondary_effects})
        if valid:
            effects["primary_effect"] = (effects["tcobr_effect_severe"] + effects["tcobr_effect_low"]) / 2.0
            included.append({"episode_id": episode["episode_id"], "scene": episode["scene"], "seed": episode["seed"], **effects})
        else:
            exclusions.append({"episode_id": episode["episode_id"], "reason": "no_eligible_critical_obstacles"})
    expected_ids = amendment["conditional_analysis"]["eligible_episode_ids"]
    if [row["episode_id"] for row in included] != expected_ids or len(secondary_rows) != 32:
        raise ValueError("observed eligibility does not match frozen conditional amendment")
    primary = stratified_bootstrap(included, "primary_effect", scenes=ELIGIBLE_SCENES)
    budgets = {budget: stratified_bootstrap(included, f"tcobr_effect_{budget}", scenes=ELIGIBLE_SCENES) for budget in BUDGETS}
    scene_primary = {scene: float(np.mean([row["primary_effect"] for row in included if row["scene"] == scene])) for scene in ELIGIBLE_SCENES}
    scene_budgets = {scene: {budget: float(np.mean([row[f"tcobr_effect_{budget}"] for row in included if row["scene"] == scene])) for budget in BUDGETS} for scene in ELIGIBLE_SCENES}
    secondary = {metric: {budget: float(np.mean([row[f"{metric}_effect_{budget}"] for row in secondary_rows])) for budget in BUDGETS} for metric in ("full_psnr_db", "full_ssim", "charged_bytes", "roi_area_ratio")}
    method_means = {metric: {budget: {method: float(np.mean([next(case[metric] for case in episode["cases"] if case["method"] == method and case["budget"] == budget) for episode in episodes])) for method in METHODS} for budget in BUDGETS} for metric in ("full_psnr_db", "full_ssim", "charged_bytes", "roi_area_ratio")}
    return {
        "original_eight_scene_gate": amendment["original_eight_scene_gate"],
        "conditional_analysis": {"primary": primary, "budgets": budgets, "scene_primary": scene_primary, "scene_budgets": scene_budgets, "support_gate_passed": primary["ci_low"] > 0.0, "eligible_scenes": list(ELIGIBLE_SCENES)},
        "included": included, "exclusions": exclusions,
        "secondary_episode_count": 32, "secondary_rows": secondary_rows,
        "secondary": secondary, "secondary_method_means": method_means,
    }


def validate_analysis_identity_binding(identity: dict, package: dict, runtime: dict, row: dict, attempt: Path) -> dict:
    """Bind persisted runtime-local validation identity to one registered package."""
    required = {"launch_id", "attempt_id", "identity_id", "scene_id", "seed"}
    if set(identity) != required or identity["launch_id"] != "runtime-local" or identity["attempt_id"] != "runtime-local":
        raise ValueError("unexpected persisted analysis identity")
    if (
        package.get("attempt_id") != row["attempt_id"]
        or package.get("identity_id") != row["episode_id"]
        or package.get("scene_id") != row["scene"]
        or package.get("seed") != row["seed"]
        or identity["identity_id"] != row["episode_id"]
        or identity["scene_id"] != row["scene"]
        or identity["seed"] != row["seed"]
        or runtime.get("split") != "formal"
        or runtime.get("episode_id") != row["episode_id"]
        or runtime.get("scene") != row["scene"]
        or runtime.get("seed") != row["seed"]
        or runtime.get("manifest_authority_version") != "v3"
        or package.get("manifest_authority_version") != "v3"
        or package.get("manifest_sha256") != runtime.get("v2_manifest_sha256")
        or package.get("lock_sha256") != runtime.get("v2_lock_sha256")
        or Path(package.get("prospective_attempt_root", "")).resolve() != Path(attempt).resolve()
    ):
        raise ValueError("persisted analysis identity is not bound to the registered package")
    return identity


def load_bound_completion_evidence(package: dict, runtime: dict, row: dict, attempt: Path) -> tuple[dict, dict, dict]:
    manifest_path = Path(attempt) / "runtime_artifacts.json"
    raw = manifest_path.read_bytes(); manifest_value = json.loads(raw)
    if raw != _canonical(manifest_value):
        raise ValueError("noncanonical runtime manifest")
    identity = validate_analysis_identity_binding(manifest_value.get("identity"), package, runtime, row, attempt)
    manifest = load_runtime_manifest(manifest_path, identity, attempt, runtime)
    validation_path = Path(attempt) / "codec_aggregate_validation.json"
    validation = load_codec_aggregate_validation(validation_path, runtime, root=attempt, identity=identity)
    if Path(validation.get("aggregate_path", "")).resolve() != (Path(attempt) / "codec_aggregate.json").resolve():
        raise ValueError("analysis aggregate path binding")
    joint = load_joint_validation_report(Path(attempt) / "joint_validation.json", runtime, root=attempt)
    if joint.get("identity") != identity:
        raise ValueError("analysis joint identity binding")
    return manifest, validation, joint


def load_completed_episodes(*, preregistration_path=PREREGISTRATION_PATH, package_root=None) -> list[dict]:
    _, prereg = verify_prelaunch_gate(preregistration_path)
    root = Path(package_root) if package_root is not None else PROJECT_ROOT / "results/m6a_v2_control/prepared"
    episodes = []
    for row in prereg["matrix"]:
        package = load_prepared_launch_package_for_audit(root / row["attempt_id"] / "package.json")
        attempt = Path(package["prospective_attempt_root"])
        runtime = json.loads(Path(package["launch_spec"]["runtime_config"]["path"]).read_text(encoding="utf-8")); load_v2_runtime_config(runtime)
        aggregate = load_codec_aggregate(attempt / "codec_aggregate.json", runtime, root=attempt)
        load_bound_completion_evidence(package, runtime, row, attempt)
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
    root = Path(output_root)
    if root.exists(): raise FileExistsError("refusing to overwrite frozen M6 v3 analysis")
    root.mkdir(parents=True)
    summary = {"schema_version":"m6-multiscene-eligibility-conditional-analysis-v1", **analysis}
    summary["analysis_sha256"] = digest(summary)
    (root / "analysis_summary.json").write_bytes(_canonical(summary))
    with (root / "episode_effects.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(analysis["included"][0])); writer.writeheader(); writer.writerows(analysis["included"])
    with (root / "secondary_episode_effects.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(analysis["secondary_rows"][0])); writer.writeheader(); writer.writerows(analysis["secondary_rows"])
    primary=analysis["conditional_analysis"]["primary"];decision="PASS" if analysis["conditional_analysis"]["support_gate_passed"] else "FAIL"
    report = f"# M6 v3 Eligibility-Conditional Formal Analysis\n\nOriginal eight-scene support gate: **NOT EVALUATED**.\n\nAmended eligibility-conditional gate: **{decision}**.\n\nPrimary command-conditioned minus state-only TCOBR effect: {primary['estimate']:.6f}, 95% CI [{primary['ci_low']:.6f}, {primary['ci_high']:.6f}].\n\nEligible episodes: {len(analysis['included'])}; exclusions: {len(analysis['exclusions'])}; secondary episodes: {analysis['secondary_episode_count']}.\n"
    (root / "study_report.md").write_text(report, encoding="utf-8", newline="\n")
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("prepare"); sub.add_parser("run"); sub.add_parser("analyze")
    args=parser.parse_args(argv)
    if args.command=="prepare": result=prepare_registered_packages()
    elif args.command=="run": result=run_registered_batch()
    else: verify_analysis_amendment(); result=persist_analysis(analyze_episode_cases(load_completed_episodes()))
    print(json.dumps(result,sort_keys=True,indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
