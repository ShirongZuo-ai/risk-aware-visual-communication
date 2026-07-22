"""Read-only-first M6-A v2 fresh preflight; this module never starts Webots."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import LOCK_PATH, MANIFEST_PATH, load_and_validate_m6a_v2_manifest
from scripts.m6a_v2_launch_spec import build_one_identity_launch_spec
from scripts.m6a_v2_prepared_launch import load_prepared_launch_package


CONTROL_ROOT = PROJECT_ROOT / "results" / "m6a_v2_control"
FRESHNESS_SECONDS = 300
REPORT_SCHEMA = "m6a-v2-authoritative-fresh-preflight-v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite preflight evidence: {path}")
    path.write_bytes(_canonical(value))

def _utc_now(): return datetime.now(timezone.utc).replace(microsecond=0)
def _parse(value): return datetime.fromisoformat(value)

def _build_report(package_path, *, now=None):
    package_path=Path(package_path).resolve(); package=load_prepared_launch_package(package_path); spec=package['launch_spec']; now=now or _utc_now()
    root=Path(package['prospective_attempt_root']); plan=package['prospective_attempt_path_plan']['artifacts']
    errors=[]
    if root.exists(): errors.append('prospective attempt root exists')
    if package['preflight_workspace_root']==str(root): errors.append('preflight workspace equals attempt root')
    if any(Path(plan[key]).exists() for key in ('ownership_marker','final_marker','consumption_record')): errors.append('attempt evidence already exists')
    observed={'prospective_root_exists':root.exists(),'ownership_exists':Path(plan['ownership_marker']).exists(),'consumption_exists':Path(plan['consumption_record']).exists(),'final_marker_exists':Path(plan['final_marker']).exists()}
    report={'schema_version':REPORT_SCHEMA,'launch_id':package['launch_id'],'attempt_id':package['attempt_id'],'identity_id':package['identity_id'],'scene':package['scene_id'],'seed':package['seed'],'prepared_package_path':str(package_path),'prepared_package_digest':package['package_sha256'],'launch_spec_digest':package['launch_spec_sha256'],'runtime_config_digest':package['runtime_config_sha256'],'prepared_world_digest':package['temporary_world_sha256'],'frozen_manifest_digest':package['manifest_sha256'],'frozen_lock_digest':package['lock_sha256'],'preflight_workspace_root':package['preflight_workspace_root'],'prospective_attempt_root':str(root),'checked_invariants':['package_reload','bound_digests','identity','root_absent','no_ownership_consumption_or_marker'],'observed_values':observed,'outcome':'pass' if not errors else 'fail','errors':errors,'checked_at_utc':now.isoformat(),'valid_until_utc':(now+timedelta(seconds=FRESHNESS_SECONDS)).isoformat(),'validator_identity':'m6a_v2_fresh_preflight','validator_version':'v1'}
    report['canonical_digest']=digest(report); return report

def validate_fresh_preflight_report(report, package_path, *, now=None):
    if not isinstance(report,dict) or report.get('schema_version')!=REPORT_SCHEMA or report.get('canonical_digest')!=digest({k:v for k,v in report.items() if k!='canonical_digest'}): raise ValueError('preflight report digest')
    checked,valid=_parse(report['checked_at_utc']),_parse(report['valid_until_utc']); now=now or _utc_now()
    if checked>now or valid<=checked or valid<=now or (report['outcome']=='pass')!= (report['errors']==[]) or report['outcome'] not in {'pass','fail'}: raise ValueError('preflight freshness/outcome')
    actual=_build_report(package_path,now=checked)
    for key in ('launch_id','attempt_id','identity_id','scene','seed','prepared_package_path','prepared_package_digest','launch_spec_digest','runtime_config_digest','prepared_world_digest','frozen_manifest_digest','frozen_lock_digest','preflight_workspace_root','prospective_attempt_root','checked_invariants','observed_values','outcome','errors'):
        if report.get(key)!=actual.get(key): raise ValueError('preflight binding changed')
    return report

def persist_fresh_preflight_report(path, package_path, *, now=None):
    report=_build_report(package_path,now=now)
    if report['outcome']!='pass': raise ValueError('fresh preflight failed')
    _write_new(Path(path),report); return load_fresh_preflight_report(path,package_path,now=now)

def load_fresh_preflight_report(path, package_path, *, now=None):
    raw=Path(path).read_bytes(); report=json.loads(raw)
    if raw!=_canonical(report): raise ValueError('noncanonical preflight report')
    return validate_fresh_preflight_report(report,package_path,now=now)

def run_fresh_preflight_for_prepared_launch(package_path, *, now=None):
    """Production preflight entry: package disk reload -> persist -> reload/validate."""
    package=load_prepared_launch_package(package_path)
    report_path=Path(package['preflight_report_path']).resolve()
    if not report_path.is_relative_to(Path(package['preflight_workspace_root']).resolve()): raise ValueError('unsafe preflight report path')
    return persist_fresh_preflight_report(report_path,package_path,now=now)


def refresh_fresh_preflight_for_prepared_launch(package_path, *, now=None):
    """Return a current report, archiving only a validated expired predecessor."""
    package = load_prepared_launch_package(package_path)
    report_path = Path(package["preflight_report_path"]).resolve()
    workspace = Path(package["preflight_workspace_root"]).resolve()
    if not report_path.is_relative_to(workspace):
        raise ValueError("unsafe preflight report path")
    current = now or _utc_now()
    if report_path.exists():
        raw = report_path.read_bytes()
        existing = json.loads(raw)
        if raw != _canonical(existing):
            raise ValueError("noncanonical existing preflight report")
        checked = _parse(existing["checked_at_utc"])
        validate_fresh_preflight_report(existing, package_path, now=checked)
        if _parse(existing["valid_until_utc"]) > current:
            return load_fresh_preflight_report(report_path, package_path, now=current)
        history = workspace / "fresh_preflight_history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = existing["checked_at_utc"].replace(":", "").replace("+", "_")
        archive = history / f"fresh_preflight_report.{stamp}.{existing['canonical_digest']}.json"
        if archive.exists():
            if archive.read_bytes() != raw:
                raise FileExistsError("conflicting archived preflight evidence")
            report_path.unlink()
        else:
            report_path.rename(archive)
    return run_fresh_preflight_for_prepared_launch(package_path, now=current)


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
