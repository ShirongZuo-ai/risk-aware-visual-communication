"""Prepare, execute once, and validate the registered M7 v1 development corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_v2_execution_safety import CONTROL_ROOT, _read_canonical
from scripts.m6a_v2_pilot_completion import load_codec_aggregate, load_joint_validation_report
from scripts.m6a_v2_prepared_launch import (
    build_prepared_launch_package, current_repository_head,
    load_prepared_launch_package_for_audit,
)
from scripts.m6a_v2_research_pilot import run_research_pilot
from scripts.m6a_v2_runtime_evidence import load_process_evidence, load_runtime_manifest
from scripts.m7_v1_episode_source import (
    LOCK_PATH, MANIFEST_PATH, PREREGISTRATION_PATH, _bytes,
    load_and_validate_m7_v1_manifest, load_evaluator_only_geometry, preregistration_payload,
)
from scripts.run_m6a_one_identity import load_v2_runtime_config


PACKAGE_ROOT = CONTROL_ROOT / "prepared"
BATCH_REPORT = PROJECT_ROOT / "results/m7_v1_control/development_corpus_validation.json"


def _sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_preregistration(path=PREREGISTRATION_PATH) -> dict:
    manifest = load_and_validate_m7_v1_manifest(MANIFEST_PATH, LOCK_PATH)
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    raw = Path(path).read_bytes(); value = json.loads(raw)
    expected = preregistration_payload(manifest, lock)
    if raw != _bytes(value) or value != expected or len(value.get("matrix", [])) != 16:
        raise ValueError("invalid M7 preregistration")
    if len({item["attempt_id"] for item in value["matrix"]}) != 16 or len({item["episode_id"] for item in value["matrix"]}) != 16 or len({item["seed"] for item in value["matrix"]}) != 16:
        raise ValueError("duplicate M7 preregistration identity")
    return value


def audit_historical_disjointness() -> dict:
    registration = load_preregistration(); new_ids = {item["episode_id"] for item in registration["matrix"]}; new_seeds = {item["seed"] for item in registration["matrix"]}
    historical_ids, historical_seeds = set(), set()
    for name in ("m6a_v2_episode_source_manifest.json", "m6a_v3_episode_source_manifest.json"):
        value = json.loads((PROJECT_ROOT / "docs/results" / name).read_text(encoding="utf-8"))
        for record in value["records"]:
            historical_ids.add(record["identity"]["episode_id"]); historical_seeds.add(record["identity"]["seed"])
    prepared = 0
    for path in PACKAGE_ROOT.glob("*/package.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("identity_id") not in new_ids:
            historical_ids.add(value.get("identity_id")); historical_seeds.add(value.get("seed")); prepared += 1
    completed = 0
    for path in (PROJECT_ROOT / "data/m6a/pilot").glob("*/*/episode_runtime_summary.json"):
        value = json.loads(path.read_text(encoding="utf-8")); identity = value.get("identity", {})
        if identity.get("episode_id") not in new_ids:
            historical_ids.add(identity.get("episode_id")); historical_seeds.add(identity.get("seed")); completed += 1
    overlap_ids = sorted(new_ids & historical_ids); overlap_seeds = sorted(new_seeds & historical_seeds)
    if overlap_ids or overlap_seeds:
        raise ValueError(f"M7 identity reuse: ids={overlap_ids}, seeds={overlap_seeds}")
    return {
        "registered_identity_count": 16, "registered_seed_count": 16,
        "historical_identity_count": len(historical_ids), "historical_seed_count": len(historical_seeds),
        "historical_prepared_package_count": prepared, "historical_runtime_summary_count": completed,
        "identity_overlap_count": 0, "seed_overlap_count": 0, "passed": True,
    }


def prepare_registered_packages(*, head: str, branch: str) -> list[dict]:
    if current_repository_head() != head:
        raise ValueError("M7 preparation HEAD mismatch")
    registration = load_preregistration(); audit_historical_disjointness()
    targets = [PACKAGE_ROOT / item["attempt_id"] for item in registration["matrix"]]
    if any(path.exists() for path in targets):
        raise ValueError("registered package workspace already exists")
    packages = []
    for item in registration["matrix"]:
        path, package = build_prepared_launch_package(
            head=head, branch=branch, attempt_id=item["attempt_id"], episode_id=item["episode_id"],
            manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH,
        )
        packages.append({"path": str(path.resolve()), "package": package})
    audit_registered_packages(head=head)
    return packages


def audit_registered_packages(*, head: str) -> list[dict]:
    registration = load_preregistration(); values = []
    for item in registration["matrix"]:
        path = PACKAGE_ROOT / item["attempt_id"] / "package.json"
        package = load_prepared_launch_package_for_audit(path)
        runtime = json.loads(Path(package["launch_spec"]["runtime_config"]["path"]).read_text(encoding="utf-8")); load_v2_runtime_config(runtime)
        if (
            package["head"] != head or package["attempt_id"] != item["attempt_id"]
            or package["identity_id"] != item["episode_id"] or package["scene_id"] != item["scene"]
            or package["seed"] != item["seed"] or package["manifest_authority_version"] != "m7v1"
            or runtime["split"] != "development" or Path(package["prospective_attempt_root"]).exists()
            or any(key in runtime for key in ("evaluator_only_obstacle_geometry", "critical_event_labels", "tcobr_annotations", "future_ground_truth"))
        ):
            raise ValueError("M7 prepared package binding or information boundary")
        values.append({
            "attempt_id": item["attempt_id"], "package_path": str(path.resolve()),
            "package_sha256": package["package_sha256"], "launch_id": package["launch_id"],
            "runtime_config_sha256": runtime["config_sha256"], "attempt_root": package["prospective_attempt_root"],
        })
    return values


def run_registered_batch(*, head: str) -> list[dict]:
    registration = load_preregistration(); audit_historical_disjointness(); audit_registered_packages(head=head)
    results = []
    for item in registration["matrix"]:
        path = PACKAGE_ROOT / item["attempt_id"] / "package.json"
        result = run_research_pilot(path, confirm_attempt=item["attempt_id"])
        results.append({"attempt_id": item["attempt_id"], "state": result["state"], "runner_invoked": result.get("runner_invoked")})
        if result["state"] != "finalized" or result.get("runner_invoked") is not True:
            raise RuntimeError(f"M7 shared or episode failure at {item['attempt_id']}: {result['state']}")
    return results


def validate_completed_corpus(*, head: str, persist_report: bool = False) -> dict:
    registration = load_preregistration(); packages = audit_registered_packages_after_completion(head=head); episodes = []
    for item, package in zip(registration["matrix"], packages):
        root = Path(package["prospective_attempt_root"]); runtime = json.loads(Path(package["launch_spec"]["runtime_config"]["path"]).read_text(encoding="utf-8")); load_v2_runtime_config(runtime)
        manifest_raw = json.loads((root / "runtime_artifacts.json").read_text(encoding="utf-8")); identity = manifest_raw["identity"]
        manifest = load_runtime_manifest(root / "runtime_artifacts.json", identity, root, runtime)
        aggregate = load_codec_aggregate(root / "codec_aggregate.json", runtime, root=root)
        joint = load_joint_validation_report(root / "joint_validation.json", runtime, root=root)
        geometry = load_evaluator_only_geometry(root / "evaluator_only_geometry.json", runtime, root)
        process = load_process_evidence(root / "host_process_result.json", identity)
        final = _read_canonical(root / "m6a_v2_final_success.json"); terminal = _read_canonical(root / ".m6a_v2_ownership_terminal.json")
        cases = [case for snapshot in aggregate["snapshot_evidence"] for case in snapshot["cases"]]
        if (
            process["return_code"] != 0 or process["timed_out"] or process["termination_state"] != "exited"
            or len(manifest["snapshot_validation"]["validated_snapshot_ids"]) != 4 or len(cases) != 32
            or joint["outcome"] != "pass" or terminal.get("state") != "completed"
            or terminal.get("final_marker_sha256") != final.get("sha256")
            or final.get("evaluator_geometry_sha256") != geometry["canonical_digest"]
        ):
            raise ValueError("invalid completed M7 episode")
        episodes.append({
            "attempt_id": item["attempt_id"], "episode_id": item["episode_id"], "scene": item["scene"], "seed": item["seed"],
            "snapshot_count": 4, "codec_case_count": 32, "runtime_manifest_sha256": manifest["sha256"],
            "aggregate_sha256": aggregate["aggregate_sha256"], "joint_sha256": joint["joint_sha256"],
            "evaluator_geometry_sha256": geometry["canonical_digest"], "final_marker_sha256": final["sha256"],
            "ownership_terminal_sha256": terminal["sha256"], "retry_count": 0,
        })
    report = {
        "schema_version": "m7-v1-development-corpus-validation-v1", "manifest_sha256": _sha(MANIFEST_PATH),
        "lock_sha256": _sha(LOCK_PATH), "preregistration_sha256": _sha(PREREGISTRATION_PATH),
        "expected_episode_count": 16, "completed_episode_count": len(episodes),
        "snapshot_count": sum(item["snapshot_count"] for item in episodes),
        "codec_case_count": sum(item["codec_case_count"] for item in episodes),
        "launch_count": len(episodes), "retry_count": 0, "episodes": episodes, "passed": len(episodes) == 16,
    }
    from scripts.m6a_trusted_artifacts import digest
    report["canonical_digest"] = digest(report)
    if persist_report:
        BATCH_REPORT.parent.mkdir(parents=True, exist_ok=True)
        if BATCH_REPORT.exists(): raise FileExistsError("M7 corpus report exists")
        BATCH_REPORT.write_bytes(_bytes(report))
    return report


def audit_registered_packages_after_completion(*, head: str) -> list[dict]:
    registration = load_preregistration(); packages = []
    for item in registration["matrix"]:
        package = load_prepared_launch_package_for_audit(PACKAGE_ROOT / item["attempt_id"] / "package.json")
        if package["head"] != head or package["identity_id"] != item["episode_id"]:
            raise ValueError("completed package identity")
        packages.append(package)
    return packages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M7 v1 development-corpus operator")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-authority")
    prepare = commands.add_parser("prepare"); prepare.add_argument("--head", required=True); prepare.add_argument("--branch", default="main")
    run = commands.add_parser("run-batch"); run.add_argument("--head", required=True)
    validate = commands.add_parser("validate-corpus"); validate.add_argument("--head", required=True); validate.add_argument("--persist-report", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "audit-authority": output = {"disjointness": audit_historical_disjointness(), "matrix": load_preregistration()["matrix"]}
    elif args.command == "prepare": output = prepare_registered_packages(head=args.head, branch=args.branch)
    elif args.command == "run-batch": output = run_registered_batch(head=args.head)
    else: output = validate_completed_corpus(head=args.head, persist_report=args.persist_report)
    print(json.dumps(output, sort_keys=True, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
