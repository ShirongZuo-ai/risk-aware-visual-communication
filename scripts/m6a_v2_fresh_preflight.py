"""Read-only-first M6-A v2 fresh preflight; this module never starts Webots."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import LOCK_PATH, MANIFEST_PATH, load_and_validate_m6a_v2_manifest
from scripts.m6a_v2_launch_spec import build_one_identity_launch_spec


CONTROL_ROOT = PROJECT_ROOT / "results" / "m6a_v2_control"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite preflight evidence: {path}")
    path.write_bytes(_canonical(value))


def _temporary_spec(manifest: Path, lock: Path, executable: Path) -> tuple[dict, bool]:
    """Build twice in one disposable temp root and prove canonical spec stability."""
    with tempfile.TemporaryDirectory(prefix="m6a-v2-fresh-preflight-") as directory:
        root = Path(directory) / "preflight"
        first = build_one_identity_launch_spec(manifest, lock, preflight_root=root, webots_executable=executable)
        shutil.rmtree(root)
        second = build_one_identity_launch_spec(manifest, lock, preflight_root=root, webots_executable=executable)
        return second, first["launch_spec_sha256"] == second["launch_spec_sha256"]


def run_fresh_preflight(*, report_root: Path = CONTROL_ROOT, webots_executable: Path | None = None) -> dict:
    """Produce control evidence only; no attempt root, marker, authorization, or process is created."""
    manifest = MANIFEST_PATH.resolve()
    lock = LOCK_PATH.resolve()
    payload = load_and_validate_m6a_v2_manifest(manifest, lock)
    executable = (webots_executable or Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")).resolve()
    spec, deterministic = _temporary_spec(manifest, lock, executable)
    record = next(item for item in payload["records"] if item["identity"]["episode_id"] == "m6a_pilot_s1_seed600100")
    prospective_root = (PROJECT_ROOT / "data" / "m6a" / "pilot" / "attempt-unassigned").resolve()
    gates = {
        "frozen_manifest_lock": "PASS",
        "scientific_identity": "PASS",
        "static_executable_evidence": "PASS",
        "canonical_launch_spec": "PASS" if deterministic else "FAIL",
        "attempt_specific_output_root": "FAIL",
        "ownership_marker_before_spawn": "FAIL",
        "authorization_single_use_schema": "FAIL",
        "final_marker_single_path": "FAIL",
        "runtime_and_post_runtime": "NOT_EXECUTED",
    }
    report = {
        "schema_version": "m6a-v2-fresh-preflight-v1",
        "kind": "control-preflight-not-runtime-result",
        "manifest_sha256": _sha256(manifest),
        "lock_sha256": _sha256(lock),
        "identity": record["identity"],
        "methods": record["methods"],
        "budgets": record["budgets"],
        "snapshots": record["snapshot_aligned_times_s"],
        "expected_cases": 32,
        "launch_spec": spec,
        "prospective_output_root": str(prospective_root),
        "prospective_output_root_exists": prospective_root.exists(),
        "gates": gates,
        "authorization_generated": False,
        "execution_authorized": False,
        "consumed": False,
        "launch_performed": False,
        "webots_started": False,
        "scientific_result": False,
        "notes": [
            "The launch builder currently binds owned_root to its temporary preflight directory.",
            "The existing wrapper validates an already-created marker instead of atomically creating it after authorization and before spawn.",
            "The existing authorization schema has no consumed or launch_performed state and cannot be used as a safe single-use authorization.",
            "No final-success-marker creation gate exists after joint validation.",
        ],
    }
    report["report_sha256"] = digest(report)
    target = report_root.resolve() / "fresh_preflight.json"
    _write_new(target, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=CONTROL_ROOT)
    parser.add_argument("--webots-executable", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_fresh_preflight(report_root=args.report_root, webots_executable=args.webots_executable), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
