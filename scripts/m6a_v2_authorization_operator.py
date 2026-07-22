"""Safe operator commands for M6-A v2 authorization evidence only.

This module has no private-key input and never creates execution context,
materializes an attempt, or starts a process.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_detached_authorization import run_detached_authorization_verification_only
from scripts.m6a_v2_fresh_preflight import (
    load_fresh_preflight_report,
    refresh_fresh_preflight_for_prepared_launch,
)
from scripts.m6a_v2_prepared_launch import load_prepared_launch_package
from scripts.m6a_v2_production_trust import (
    authoritative_signing_request_path,
    load_execution_authorization_signing_request,
    run_production_authorization_readiness,
)

PRODUCTION_PACKAGE = PROJECT_ROOT / "results" / "m6a_v2_control" / "prepared" / "m6a-prod-pilot-001" / "package.json"
PRODUCTION_TRUST_CONFIG = PROJECT_ROOT / "config" / "m6a_v2" / "production_authorization_trust.json"
REQUEST_HISTORY_DIRECTORY = "unsigned_authorization_request_history"


def _canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed


def _load_request_shape(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    request = json.loads(raw)
    if raw != _canonical_bytes(request):
        raise ValueError("noncanonical existing unsigned request")
    if request.get("canonical_request_digest") != digest(
        {key: item for key, item in request.items() if key != "canonical_request_digest"}
    ):
        raise ValueError("existing unsigned request digest")
    return raw, request


def _bound_preflight_candidates(package: dict) -> list[Path]:
    workspace = Path(package["preflight_workspace_root"]).resolve()
    current = Path(package["preflight_report_path"]).resolve()
    history = workspace / "fresh_preflight_history"
    candidates = [current]
    if history.is_dir():
        candidates.extend(sorted(history.glob("fresh_preflight_report.*.json")))
    if any(not candidate.resolve().is_relative_to(workspace) for candidate in candidates):
        raise ValueError("preflight history escaped prepared workspace")
    return candidates


def archive_existing_unsigned_request(
    package_path,
    trust_config_path,
    *,
    repository_root=PROJECT_ROOT,
) -> Path:
    """Archive one historically valid request without weakening current validation."""
    package = load_prepared_launch_package(package_path)
    request_path = authoritative_signing_request_path(package_path)
    raw, request = _load_request_shape(request_path)
    target_preflight_digest = request["authorization_payload"]["fresh_preflight_report_digest"]
    historical_now = _parse_time(request["issued_at_utc"])
    matched = None
    for candidate in _bound_preflight_candidates(package):
        try:
            report = json.loads(candidate.read_bytes())
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if report.get("canonical_digest") != target_preflight_digest:
            continue
        load_execution_authorization_signing_request(
            request_path,
            package_path=package_path,
            preflight_path=candidate,
            trust_config_path=trust_config_path,
            repository_root=repository_root,
            now=historical_now,
        )
        matched = candidate
        break
    if matched is None:
        raise ValueError("existing unsigned request has no validated bound preflight evidence")
    workspace = Path(package["preflight_workspace_root"]).resolve()
    history = workspace / REQUEST_HISTORY_DIRECTORY
    history.mkdir(parents=True, exist_ok=True)
    stamp = request["issued_at_utc"].replace(":", "").replace("+", "_")
    archive = history / f"unsigned_authorization_signing_request.{stamp}.{request['canonical_request_digest']}.json"
    if archive.exists():
        if archive.read_bytes() != raw:
            raise FileExistsError("conflicting archived unsigned request evidence")
        request_path.unlink()
    else:
        request_path.rename(archive)
    return archive


def refresh_and_export_current_request(
    package_path=PRODUCTION_PACKAGE,
    trust_config_path=PRODUCTION_TRUST_CONFIG,
    *,
    repository_root=PROJECT_ROOT,
    now: datetime | None = None,
) -> dict:
    """Command A: safely renew expired control evidence and return exact deadlines."""
    current = now or datetime.now(timezone.utc).replace(microsecond=0)
    package = load_prepared_launch_package(package_path)
    preflight_path = Path(package["preflight_report_path"]).resolve()
    request_path = authoritative_signing_request_path(package_path)
    archived_request = None
    if request_path.exists():
        try:
            request = load_execution_authorization_signing_request(
                request_path,
                package_path=package_path,
                preflight_path=preflight_path,
                trust_config_path=trust_config_path,
                repository_root=repository_root,
                now=current,
            )
            report = load_fresh_preflight_report(preflight_path, package_path, now=current)
            return _command_a_result(package, report, request, request_path, archived_request)
        except ValueError:
            archived_request = archive_existing_unsigned_request(
                package_path, trust_config_path, repository_root=repository_root
            )
    report = refresh_fresh_preflight_for_prepared_launch(package_path, now=current)
    readiness = run_production_authorization_readiness(
        package_path,
        preflight_path,
        trust_config_path,
        repository_root=repository_root,
        now=current,
    )
    request = load_execution_authorization_signing_request(
        readiness["signing_request_path"],
        package_path=package_path,
        preflight_path=preflight_path,
        trust_config_path=trust_config_path,
        repository_root=repository_root,
        now=current,
    )
    return _command_a_result(package, report, request, request_path, archived_request)


def _command_a_result(package, report, request, request_path, archived_request) -> dict:
    effective = min(_parse_time(report["valid_until_utc"]), _parse_time(request["expires_at_utc"]))
    return {
        "command": "refresh-export",
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "fresh_preflight_path": str(Path(package["preflight_report_path"]).resolve()),
        "fresh_preflight_digest": report["canonical_digest"],
        "fresh_preflight_valid_until_utc": report["valid_until_utc"],
        "unsigned_request_path": str(request_path.resolve()),
        "unsigned_request_digest": request["canonical_request_digest"],
        "authorization_id": request["authorization_id"],
        "request_expires_at_utc": request["expires_at_utc"],
        "effective_deadline_utc": effective.isoformat(),
        "archived_unsigned_request_path": str(archived_request) if archived_request else None,
        "signature_present": False,
        "execution_authorized": False,
        "stop_after_export": True,
    }


def verify_current_detached_signature(
    package_path=PRODUCTION_PACKAGE,
    trust_config_path=PRODUCTION_TRUST_CONFIG,
    *,
    repository_root=PROJECT_ROOT,
) -> dict:
    """Command C: verify existing evidence and stop before execution context creation."""
    package = load_prepared_launch_package(package_path)
    return run_detached_authorization_verification_only(
        package_path,
        package["preflight_report_path"],
        trust_config_path,
        repository_root=repository_root,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("refresh-export", "verify-only"))
    args = parser.parse_args(argv)
    if args.command == "refresh-export":
        result = refresh_and_export_current_request()
    else:
        result = verify_current_detached_signature()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
