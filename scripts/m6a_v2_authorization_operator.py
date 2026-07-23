"""Safe operator commands for M6-A v2 authorization and ownership gates.

This module has no private-key input.  Its materialize-only command may create
one validated context, attempt root, and ownership marker, but never starts a
process, consumes authorization, or finalizes an attempt.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_detached_authorization import (
    authoritative_detached_authorization_paths,
    load_detached_signature_bundle,
    load_verified_authorization_receipt,
    run_detached_authorization_verification_only,
)
from scripts.m6a_v2_execution_authorization import (
    authorization_signed_message,
    build_expected_authorization_binding,
    build_externally_validated_execution_context,
    load_execution_authorization_artifact,
    validate_authorization_binding,
    verify_execution_authorization,
)
from scripts.m6a_v2_execution_safety import (
    attempt_path_plan,
    load_owned_attempt_context,
    materialize_authorized_attempt,
)
from scripts.m6a_v2_fresh_preflight import (
    load_fresh_preflight_report,
    refresh_fresh_preflight_for_prepared_launch,
)
from scripts.m6a_v2_prepared_launch import current_repository_head, load_prepared_launch_package
from scripts.m6a_v2_production_trust import (
    authoritative_signing_request_path,
    build_production_authorization_verifier_from_config,
    load_execution_authorization_signing_request,
    load_production_authorization_trust_config,
    run_production_authorization_readiness,
)

PRODUCTION_PACKAGE = PROJECT_ROOT / "results" / "m6a_v2_control" / "prepared" / "m6a-prod-pilot-001" / "package.json"
PRODUCTION_TRUST_CONFIG = PROJECT_ROOT / "config" / "m6a_v2" / "production_authorization_trust.json"
REQUEST_HISTORY_DIRECTORY = "unsigned_authorization_request_history"
AUTHORIZATION_GENERATION_HISTORY_DIRECTORY = "authorization_generation_history"
AUTHORIZATION_GENERATION_ARCHIVE_SCHEMA = "m6a-v2-verified-authorization-generation-archive-v1"
_GENERATION_ARCHIVE_FILENAMES = {
    "detached_signature_bundle": "bundle.json",
    "authorization_artifact": "artifact.json",
    "verified_receipt": "receipt.json",
}


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


def _request_history_directory(workspace: Path) -> Path:
    history = workspace / REQUEST_HISTORY_DIRECTORY
    resolved = history.resolve()
    if resolved.parent != workspace or not resolved.is_relative_to(workspace):
        raise ValueError("unsigned-request history escaped prepared workspace")
    if history.is_symlink() or history.exists() and not history.is_dir():
        raise ValueError("unsafe unsigned-request history directory")
    history.mkdir(parents=True, exist_ok=True)
    return history


def _request_archive_path(workspace: Path, request_digest: str) -> Path:
    if not isinstance(request_digest, str) or len(request_digest) != 64:
        raise ValueError("invalid archived request digest")
    try:
        int(request_digest, 16)
    except ValueError as exc:
        raise ValueError("invalid archived request digest") from exc
    history = _request_history_directory(workspace)
    archive = history / f"request.{request_digest}.json"
    if archive.resolve().parent != history.resolve() or archive.is_symlink():
        raise ValueError("unsafe unsigned-request archive path")
    return archive


def _validate_historical_request(
    request_path: Path,
    package_path,
    package: dict,
    trust_config_path,
    *,
    repository_root,
) -> tuple[bytes, dict, Path]:
    raw, request = _load_request_shape(request_path)
    target_preflight_digest = request["authorization_payload"]["fresh_preflight_report_digest"]
    historical_now = _parse_time(request["issued_at_utc"])
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
        return raw, request, candidate
    raise ValueError("existing unsigned request has no validated bound preflight evidence")


def archive_existing_unsigned_request(
    package_path,
    trust_config_path,
    *,
    repository_root=PROJECT_ROOT,
    expected_request_digest=None,
) -> Path:
    """Atomically archive or recover one historically validated request."""
    package = load_prepared_launch_package(package_path)
    request_path = authoritative_signing_request_path(package_path)
    workspace = Path(package["preflight_workspace_root"]).resolve()
    if request_path.exists():
        raw, request, _ = _validate_historical_request(
            request_path,
            package_path,
            package,
            trust_config_path,
            repository_root=repository_root,
        )
        request_digest = request["canonical_request_digest"]
        if expected_request_digest is not None and request_digest != expected_request_digest:
            raise ValueError("existing request does not match expected archive digest")
    else:
        if expected_request_digest is None:
            raise FileNotFoundError("unsigned request source is absent and no recovery digest was supplied")
        request_digest = expected_request_digest
        archive = _request_archive_path(workspace, request_digest)
        if not archive.is_file():
            raise FileNotFoundError("unsigned request source and expected archive are both absent")
        raw, request, _ = _validate_historical_request(
            archive,
            package_path,
            package,
            trust_config_path,
            repository_root=repository_root,
        )
        if request["canonical_request_digest"] != request_digest:
            raise ValueError("recovered archive digest mismatch")
        return archive
    archive = _request_archive_path(workspace, request_digest)
    if archive.exists():
        if archive.read_bytes() != raw:
            raise FileExistsError("conflicting archived unsigned request evidence")
        # A prior copy-before-crash left two identical names for the same evidence.
        # The immutable archive is retained; the canonical current slot is released.
        request_path.unlink()
    else:
        request_path.rename(archive)
    if archive.read_bytes() != raw or hashlib.sha256(archive.read_bytes()).digest() != hashlib.sha256(raw).digest():
        raise OSError("archived unsigned request bytes changed")
    return archive


def _validated_digest(value, description: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"invalid {description}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"invalid {description}") from exc
    return value.lower()


def _read_canonical_mapping(path: Path, description: str) -> tuple[bytes, dict]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unsafe or missing {description}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {description} JSON") from exc
    if not isinstance(value, dict) or raw != _canonical_bytes(value):
        raise ValueError(f"noncanonical {description}")
    return raw, value


def _generation_history_directory(workspace: Path) -> Path:
    history = workspace / AUTHORIZATION_GENERATION_HISTORY_DIRECTORY
    resolved = history.resolve()
    if resolved.parent != workspace or not resolved.is_relative_to(workspace):
        raise ValueError("authorization-generation history escaped prepared workspace")
    if history.is_symlink() or history.exists() and not history.is_dir():
        raise ValueError("unsafe authorization-generation history directory")
    history.mkdir(parents=True, exist_ok=True)
    return history


def _generation_archive_directory(workspace: Path, request_digest: str) -> Path:
    request_digest = _validated_digest(request_digest, "generation request digest")
    history = _generation_history_directory(workspace)
    archive = history / f"g.{request_digest[:16]}"
    if archive.resolve().parent != history.resolve() or archive.is_symlink():
        raise ValueError("unsafe authorization-generation archive path")
    if archive.exists() and not archive.is_dir():
        raise ValueError("authorization-generation archive path is not a directory")
    archive.mkdir(exist_ok=True)
    return archive


def _request_candidates(package: dict) -> list[Path]:
    workspace = Path(package["preflight_workspace_root"]).resolve()
    current = workspace / "unsigned_authorization_signing_request.json"
    history = workspace / REQUEST_HISTORY_DIRECTORY
    candidates = [current]
    if history.is_dir() and not history.is_symlink():
        candidates.extend(sorted(history.glob("request.*.json")))
    if any(candidate.is_symlink() or not candidate.resolve().is_relative_to(workspace) for candidate in candidates):
        raise ValueError("unsigned-request candidate escaped prepared workspace")
    return candidates


def _find_historical_request(
    package_path,
    package: dict,
    trust_config_path,
    *,
    repository_root,
    request_digest: str | None = None,
    authorization_id: str | None = None,
) -> tuple[bytes, dict, Path, Path]:
    if (request_digest is None) == (authorization_id is None):
        raise ValueError("exactly one historical request selector is required")
    matches = []
    for candidate in _request_candidates(package):
        if not candidate.is_file():
            continue
        try:
            _, shape = _load_request_shape(candidate)
        except (ValueError, json.JSONDecodeError):
            continue
        if request_digest is not None and shape.get("canonical_request_digest") == request_digest:
            matches.append(candidate)
        if authorization_id is not None and shape.get("authorization_id") == authorization_id:
            matches.append(candidate)
    unique = list(dict.fromkeys(path.resolve() for path in matches))
    if len(unique) != 1:
        raise ValueError("historical authorization request was not found uniquely")
    request_path = unique[0]
    raw, request, preflight_path = _validate_historical_request(
        request_path,
        package_path,
        package,
        trust_config_path,
        repository_root=repository_root,
    )
    if request_digest is not None and request["canonical_request_digest"] != request_digest:
        raise ValueError("historical request digest mismatch")
    if authorization_id is not None and request["authorization_id"] != authorization_id:
        raise ValueError("historical request authorization ID mismatch")
    return raw, request, request_path, preflight_path


def _generation_source_paths(package_path) -> tuple[dict, dict[str, Path]]:
    package = load_prepared_launch_package(package_path)
    authoritative = authoritative_detached_authorization_paths(package_path)
    return package, {
        "detached_signature_bundle": authoritative["detached_signature_bundle"],
        "authorization_artifact": authoritative["authorization_artifact"],
        "verified_receipt": authoritative["verified_receipt"],
    }


def _validate_verified_generation_files(
    package_path,
    trust_config_path,
    paths: dict[str, Path],
    *,
    repository_root,
    expected_request_digest: str | None = None,
) -> dict:
    package = load_prepared_launch_package(package_path)
    raw_bundle, bundle_shape = _read_canonical_mapping(paths["detached_signature_bundle"], "detached signature bundle")
    raw_artifact, artifact_shape = _read_canonical_mapping(paths["authorization_artifact"], "authorization artifact")
    raw_receipt, receipt_shape = _read_canonical_mapping(paths["verified_receipt"], "verified receipt")
    request_digest = _validated_digest(bundle_shape.get("unsigned_request_digest"), "bundle request digest")
    if expected_request_digest is not None and request_digest != expected_request_digest:
        raise ValueError("verification-generation request digest mismatch")
    _, request, request_path, preflight_path = _find_historical_request(
        package_path,
        package,
        trust_config_path,
        repository_root=repository_root,
        request_digest=request_digest,
    )
    authorization_id = request["authorization_id"]
    if any(value.get("authorization_id") != authorization_id for value in (bundle_shape, artifact_shape, receipt_shape)):
        raise ValueError("verification-generation authorization ID mismatch")
    historical_now = _parse_time(receipt_shape.get("verified_at_utc", ""))
    bundle = load_detached_signature_bundle(
        paths["detached_signature_bundle"], request=request, now=historical_now
    )
    artifact = load_execution_authorization_artifact(paths["authorization_artifact"], now=historical_now)
    binding = build_expected_authorization_binding(package_path, preflight_path, now=historical_now)
    validate_authorization_binding(artifact, binding, now=historical_now)
    if authorization_signed_message(artifact) != base64.b64decode(request["signed_message_base64"], validate=True):
        raise ValueError("verification-generation signed message mismatch")
    envelope = artifact["authenticator_envelope"]
    if (
        envelope.get("scheme") != bundle["signature_scheme"]
        or envelope.get("key_id") != bundle["key_id"]
        or envelope.get("signature_base64") != bundle["signature_base64"]
    ):
        raise ValueError("verification-generation bundle/artifact mismatch")
    trust = load_production_authorization_trust_config(trust_config_path, repository_root=repository_root)
    if (
        bundle["key_id"] != trust["expected_key_id"]
        or request["trust_config_digest"] != trust["config_digest"]
        or request["public_key_fingerprint"] != trust["expected_public_key_fingerprint"]
        or request["trust_domain"] != trust["trust_domain"]
    ):
        raise ValueError("verification-generation production trust mismatch")
    persisted_receipt = load_verified_authorization_receipt(
        paths["verified_receipt"], binding, now=historical_now
    )
    verifier = build_production_authorization_verifier_from_config(
        trust_config_path, repository_root=repository_root
    )
    reverified = verifier.verify(artifact, binding, now=historical_now).validate(
        binding, now=historical_now
    )
    if reverified.data != persisted_receipt.data:
        raise ValueError("persisted receipt does not match historical public-key verification")
    canonical_digests = {
        "detached_signature_bundle": bundle["canonical_bundle_digest"],
        "authorization_artifact": artifact["canonical_artifact_digest"],
        "verified_receipt": persisted_receipt.data["canonical_receipt_digest"],
    }
    return {
        "authorization_id": authorization_id,
        "unsigned_request_digest": request_digest,
        "signed_message_sha256": request["signed_message_sha256"],
        "key_id": bundle["key_id"],
        "launch_id": request["launch_id"],
        "attempt_id": request["attempt_id"],
        "identity_id": request["identity_id"],
        "prepared_package_digest": request["authorization_payload"]["prepared_package_digest"],
        "fresh_preflight_report_digest": request["authorization_payload"]["fresh_preflight_report_digest"],
        "trust_config_digest": trust["config_digest"],
        "public_key_fingerprint": trust["expected_public_key_fingerprint"],
        "trust_domain": trust["trust_domain"],
        "historical_request_path": str(request_path),
        "historical_preflight_path": str(preflight_path),
        "raw": {
            "detached_signature_bundle": raw_bundle,
            "authorization_artifact": raw_artifact,
            "verified_receipt": raw_receipt,
        },
        "canonical_digests": canonical_digests,
    }


def _generation_manifest(validation: dict) -> dict:
    manifest = {
        "schema_version": AUTHORIZATION_GENERATION_ARCHIVE_SCHEMA,
        "authorization_id": validation["authorization_id"],
        "unsigned_request_digest": validation["unsigned_request_digest"],
        "signed_message_sha256": validation["signed_message_sha256"],
        "key_id": validation["key_id"],
        "launch_id": validation["launch_id"],
        "attempt_id": validation["attempt_id"],
        "identity_id": validation["identity_id"],
        "prepared_package_digest": validation["prepared_package_digest"],
        "fresh_preflight_report_digest": validation["fresh_preflight_report_digest"],
        "trust_config_digest": validation["trust_config_digest"],
        "public_key_fingerprint": validation["public_key_fingerprint"],
        "trust_domain": validation["trust_domain"],
        "files": {},
    }
    for key, filename in _GENERATION_ARCHIVE_FILENAMES.items():
        raw = validation["raw"][key]
        manifest["files"][key] = {
            "filename": filename,
            "byte_length": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "canonical_digest": validation["canonical_digests"][key],
        }
    manifest["canonical_manifest_digest"] = digest(manifest)
    return manifest


def _persist_exact_bytes(path: Path, raw: bytes, description: str) -> None:
    if path.is_symlink():
        raise ValueError(f"unsafe {description} archive path")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise FileExistsError(f"conflicting {description} archive")
        return
    with path.open("xb") as stream:
        stream.write(raw)
    if path.read_bytes() != raw:
        raise OSError(f"{description} archive bytes changed")


def _archive_paths(archive_directory: Path) -> dict[str, Path]:
    paths = {key: archive_directory / filename for key, filename in _GENERATION_ARCHIVE_FILENAMES.items()}
    paths["manifest"] = archive_directory / "manifest.json"
    if any(path.resolve().parent != archive_directory.resolve() or path.is_symlink() for path in paths.values()):
        raise ValueError("authorization-generation file escaped archive directory")
    return paths


def _load_completed_generation_archive(
    package_path,
    trust_config_path,
    request_digest: str,
    *,
    repository_root,
) -> dict:
    package = load_prepared_launch_package(package_path)
    workspace = Path(package["preflight_workspace_root"]).resolve()
    archive_directory = _generation_archive_directory(workspace, request_digest)
    paths = _archive_paths(archive_directory)
    if not all(path.is_file() for path in paths.values()):
        raise ValueError("authorization-generation archive is incomplete")
    validation = _validate_verified_generation_files(
        package_path,
        trust_config_path,
        {key: paths[key] for key in _GENERATION_ARCHIVE_FILENAMES},
        repository_root=repository_root,
        expected_request_digest=request_digest,
    )
    _, manifest = _read_canonical_mapping(paths["manifest"], "authorization-generation manifest")
    if manifest != _generation_manifest(validation):
        raise ValueError("authorization-generation archive manifest mismatch")
    return {
        "archive_directory": str(archive_directory),
        "manifest_path": str(paths["manifest"]),
        "manifest_digest": manifest["canonical_manifest_digest"],
        "authorization_id": validation["authorization_id"],
        "unsigned_request_digest": validation["unsigned_request_digest"],
        "files": manifest["files"],
    }


def archive_existing_verified_authorization_generation(
    package_path,
    trust_config_path,
    *,
    repository_root=PROJECT_ROOT,
    expected_request_digest: str | None = None,
) -> dict | None:
    """Archive one verified bundle/artifact/receipt generation as an immutable unit."""
    package, source_paths = _generation_source_paths(package_path)
    present = {key: path.exists() for key, path in source_paths.items()}
    if not any(present.values()):
        if expected_request_digest is None:
            return None
        return _load_completed_generation_archive(
            package_path,
            trust_config_path,
            expected_request_digest,
            repository_root=repository_root,
        )
    for key, exists in present.items():
        if exists and (source_paths[key].is_symlink() or not source_paths[key].is_file()):
            raise ValueError(f"unsafe current {key}")
    if present["detached_signature_bundle"]:
        _, selector = _read_canonical_mapping(source_paths["detached_signature_bundle"], "detached signature bundle")
        request_digest = _validated_digest(selector.get("unsigned_request_digest"), "bundle request digest")
    else:
        selector_key = "authorization_artifact" if present["authorization_artifact"] else "verified_receipt"
        _, selector = _read_canonical_mapping(source_paths[selector_key], selector_key.replace("_", " "))
        authorization_id = _validated_digest(selector.get("authorization_id"), "authorization ID")
        _, request, _, _ = _find_historical_request(
            package_path,
            package,
            trust_config_path,
            repository_root=repository_root,
            authorization_id=authorization_id,
        )
        request_digest = request["canonical_request_digest"]
    if expected_request_digest is not None and request_digest != expected_request_digest:
        raise ValueError("current verification generation does not match expected request digest")
    workspace = Path(package["preflight_workspace_root"]).resolve()
    archive_directory = _generation_archive_directory(workspace, request_digest)
    archive_paths = _archive_paths(archive_directory)
    if archive_paths["manifest"].is_file():
        completed = _load_completed_generation_archive(
            package_path,
            trust_config_path,
            request_digest,
            repository_root=repository_root,
        )
        for key, exists in present.items():
            if exists and source_paths[key].read_bytes() != archive_paths[key].read_bytes():
                raise FileExistsError(f"current {key} conflicts with completed generation archive")
        for key, exists in present.items():
            if exists:
                source_paths[key].unlink()
        return completed
    if not all(present.values()):
        raise ValueError("incomplete current verification generation without completed archive")
    validation = _validate_verified_generation_files(
        package_path,
        trust_config_path,
        source_paths,
        repository_root=repository_root,
        expected_request_digest=request_digest,
    )
    for key, raw in validation["raw"].items():
        _persist_exact_bytes(archive_paths[key], raw, key.replace("_", " "))
    archived_validation = _validate_verified_generation_files(
        package_path,
        trust_config_path,
        {key: archive_paths[key] for key in _GENERATION_ARCHIVE_FILENAMES},
        repository_root=repository_root,
        expected_request_digest=request_digest,
    )
    manifest = _generation_manifest(archived_validation)
    _persist_exact_bytes(
        archive_paths["manifest"],
        _canonical_bytes(manifest),
        "authorization-generation manifest",
    )
    completed = _load_completed_generation_archive(
        package_path,
        trust_config_path,
        request_digest,
        repository_root=repository_root,
    )
    for key in source_paths:
        if source_paths[key].read_bytes() != archive_paths[key].read_bytes():
            raise OSError(f"current {key} changed before archive release")
    for key in source_paths:
        source_paths[key].unlink()
    return completed


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
    archived_generation = archive_existing_verified_authorization_generation(
        package_path,
        trust_config_path,
        repository_root=repository_root,
    )
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
            return _command_a_result(
                package, report, request, request_path, archived_request, archived_generation
            )
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
    return _command_a_result(
        package, report, request, request_path, archived_request, archived_generation
    )


def _command_a_result(
    package, report, request, request_path, archived_request, archived_generation
) -> dict:
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
        "archived_verification_generation": archived_generation,
        "signature_present": False,
        "authorization_verified": False,
        "execution_authorized": False,
        "materialization_allowed": False,
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


def _receipts_match_persisted_evidence(persisted, reverified) -> bool:
    omitted = {"verified_at_utc", "canonical_receipt_digest"}
    return (
        {key: item for key, item in persisted.data.items() if key not in omitted}
        == {key: item for key, item in reverified.data.items() if key not in omitted}
    )


def materialize_current_verified_authorization(
    package_path=PRODUCTION_PACKAGE,
    trust_config_path=PRODUCTION_TRUST_CONFIG,
    *,
    repository_root=PROJECT_ROOT,
    now: datetime | None = None,
    current_head: str | None = None,
) -> dict:
    """Command D: create/reload ownership and stop before process launch."""
    current_head = current_head or current_repository_head(repository_root)
    package = load_prepared_launch_package(package_path, expected_head=current_head)
    preflight_path = Path(package["preflight_report_path"]).resolve()
    current = now or datetime.now(timezone.utc)
    load_fresh_preflight_report(preflight_path, package_path, now=current)
    paths = authoritative_detached_authorization_paths(package_path)
    request = load_execution_authorization_signing_request(
        paths["unsigned_request"],
        package_path=package_path,
        preflight_path=preflight_path,
        trust_config_path=trust_config_path,
        repository_root=repository_root,
        now=current,
    )
    bundle = load_detached_signature_bundle(paths["detached_signature_bundle"], request=request, now=current)
    artifact = load_execution_authorization_artifact(paths["authorization_artifact"])
    binding = build_expected_authorization_binding(package_path, preflight_path, now=current)
    validate_authorization_binding(artifact, binding)
    if artifact["authorization_id"] != request["authorization_id"]:
        raise ValueError("authorization artifact/request identity mismatch")
    if authorization_signed_message(artifact) != base64.b64decode(request["signed_message_base64"], validate=True):
        raise ValueError("authorization artifact/request signed-message mismatch")
    envelope = artifact["authenticator_envelope"]
    if (
        envelope.get("scheme") != bundle["signature_scheme"]
        or envelope.get("key_id") != bundle["key_id"]
        or envelope.get("signature_base64") != bundle["signature_base64"]
    ):
        raise ValueError("authorization artifact/detached bundle mismatch")
    persisted_receipt = load_verified_authorization_receipt(paths["verified_receipt"], binding)
    verifier = build_production_authorization_verifier_from_config(
        trust_config_path, repository_root=repository_root
    )
    reverified_receipt = verify_execution_authorization(
        package_path, preflight_path, paths["authorization_artifact"], verifier
    )
    if not _receipts_match_persisted_evidence(persisted_receipt, reverified_receipt):
        raise ValueError("persisted receipt does not match fresh public-key verification")
    context = build_externally_validated_execution_context(
        package_path,
        preflight_path,
        paths["authorization_artifact"],
        persisted_receipt,
    )
    plan = attempt_path_plan(
        package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
    )["artifacts"]
    if any(
        Path(plan[key]).exists()
        for key in (
            "ownership_marker",
            "owned_context",
            "ownership_terminal",
            "consumption_record",
            "process_evidence",
            "final_marker",
        )
    ):
        raise ValueError("execution evidence already exists before materialization")
    owned = materialize_authorized_attempt(
        package,
        context,
        mode="production",
        prepared_package_path=package_path,
        repository_head=current_head,
    )
    loaded = load_owned_attempt_context(
        plan["owned_context"], expected_head=current_head, mode="production"
    )
    if loaded.data != owned.data:
        raise ValueError("persisted owned context differs after materialization reload")
    if any(Path(plan[key]).exists() for key in ("consumption_record", "process_evidence", "final_marker")):
        raise ValueError("materialize-only produced forbidden execution evidence")
    return {
        "command": "materialize-only",
        "launch_id": loaded["launch_id"],
        "attempt_id": loaded["attempt_id"],
        "identity_id": loaded["identity_id"],
        "authorization_id": loaded["authorization_id"],
        "attempt_root": loaded["attempt_root"],
        "ownership_path": plan["ownership_marker"],
        "owned_context_path": plan["owned_context"],
        "ownership_digest": loaded["ownership_digest"],
        "owned_context_digest": loaded["canonical_digest"],
        "trust_verified": True,
        "receipt_valid": True,
        "execution_context_created": True,
        "materialization_allowed": True,
        "attempt_materialized": True,
        "ownership_acquired": True,
        "process_launched": False,
        "authorization_consumed": False,
        "final_marker_written": False,
        "stop_before_launch": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("refresh-export", "verify-only", "materialize-only", "run-pilot", "retire-pre-spawn"),
    )
    parser.add_argument("--package", type=Path, default=PRODUCTION_PACKAGE)
    args = parser.parse_args(argv)
    from scripts.m6a_v2_pilot_operator import authoritative_operator_package_path

    package_path = authoritative_operator_package_path(args.package)
    if args.command == "refresh-export":
        result = refresh_and_export_current_request(package_path)
    elif args.command == "verify-only":
        result = verify_current_detached_signature(package_path)
    elif args.command == "materialize-only":
        result = materialize_current_verified_authorization(package_path)
    elif args.command == "run-pilot":
        from scripts.m6a_v2_pilot_operator import run_production_pilot

        result = run_production_pilot(package_path)
    else:
        from scripts.m6a_v2_pilot_operator import retire_superseded_pre_spawn_package

        result = retire_superseded_pre_spawn_package(package_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
