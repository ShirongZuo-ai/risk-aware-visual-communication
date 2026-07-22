"""Import an offline Ed25519 signature and verify it without authorizing execution."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_execution_authorization import (
    SCHEMA as AUTHORIZATION_SCHEMA,
    ExpectedAuthorizationBinding,
    VerifiedAuthorizationReceipt,
    authorization_signed_message,
    build_expected_authorization_binding,
    load_execution_authorization_artifact,
    validate_authorization_binding,
    verify_execution_authorization,
)
from scripts.m6a_v2_prepared_launch import load_prepared_launch_package
from scripts.m6a_v2_production_trust import (
    authoritative_signing_request_path,
    build_production_authorization_verifier_from_config,
    load_execution_authorization_signing_request,
    load_production_authorization_trust_config,
)

BUNDLE_SCHEMA = "m6a-v2-detached-authorization-signature-v1"
READINESS_SCHEMA = "m6a-v2-authorization-verification-only-readiness-v1"
BUNDLE_FILENAME = "detached_authorization_signature.json"
AUTHORIZATION_FILENAME = "execution_authorization_artifact.json"
RECEIPT_FILENAME = "verified_authorization_receipt.json"


def _canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed


def _read_canonical(path: Path, description: str) -> dict:
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != _canonical_bytes(value):
        raise ValueError(f"noncanonical {description}")
    return value


def authoritative_detached_authorization_paths(package_path) -> dict[str, Path]:
    """Derive every import/verification path from the prepared-package workspace."""
    package_path = Path(package_path).resolve()
    package = load_prepared_launch_package(package_path)
    workspace = Path(package["preflight_workspace_root"]).resolve()
    if workspace != package_path.parent:
        raise ValueError("prepared package workspace mismatch")
    request_path = authoritative_signing_request_path(package_path)
    paths = {
        "unsigned_request": request_path,
        "detached_signature_bundle": workspace / BUNDLE_FILENAME,
        "authorization_artifact": workspace / AUTHORIZATION_FILENAME,
        "verified_receipt": workspace / RECEIPT_FILENAME,
    }
    if any(path.resolve().parent != workspace for path in paths.values()):
        raise ValueError("authorization path escaped prepared workspace")
    return paths


def build_detached_signature_bundle(
    request: dict,
    *,
    signature_base64: str,
    signed_at_utc: str,
    now: datetime | None = None,
) -> dict:
    """Package an already-created detached signature; this function never signs."""
    bundle = {
        "schema_version": BUNDLE_SCHEMA,
        "authorization_id": request.get("authorization_id"),
        "unsigned_request_digest": request.get("canonical_request_digest"),
        "signed_message_sha256": request.get("signed_message_sha256"),
        "key_id": request.get("key_id"),
        "signature_scheme": "ed25519",
        "signature_base64": signature_base64,
        "signed_at_utc": signed_at_utc,
        "signature_present": True,
        "trust_verified": False,
        "execution_authorized": False,
        "materialization_allowed": False,
    }
    bundle["canonical_bundle_digest"] = digest(bundle)
    return validate_detached_signature_bundle(bundle, request=request, now=now)


def validate_detached_signature_bundle(value: dict, *, request: dict, now: datetime | None = None) -> dict:
    required = {
        "schema_version", "authorization_id", "unsigned_request_digest", "signed_message_sha256",
        "key_id", "signature_scheme", "signature_base64", "signed_at_utc", "signature_present",
        "trust_verified", "execution_authorized", "materialization_allowed", "canonical_bundle_digest",
    }
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != BUNDLE_SCHEMA:
        raise ValueError("detached signature bundle schema")
    if value["canonical_bundle_digest"] != digest({key: item for key, item in value.items() if key != "canonical_bundle_digest"}):
        raise ValueError("detached signature bundle digest")
    if value["signature_present"] is not True or any(value[key] is not False for key in ("trust_verified", "execution_authorized", "materialization_allowed")):
        raise ValueError("detached signature bundle semantics")
    bindings = {
        "authorization_id": "authorization_id",
        "unsigned_request_digest": "canonical_request_digest",
        "signed_message_sha256": "signed_message_sha256",
        "key_id": "key_id",
    }
    if any(value[bundle_key] != request.get(request_key) for bundle_key, request_key in bindings.items()):
        raise ValueError("detached signature request binding")
    if value["signature_scheme"] != "ed25519":
        raise ValueError("detached signature scheme")
    try:
        signature = base64.b64decode(value["signature_base64"], validate=True)
    except Exception as exc:
        raise ValueError("malformed detached signature Base64") from exc
    if len(signature) != 64:
        raise ValueError("detached Ed25519 signature must be 64 bytes")
    current = now or datetime.now(timezone.utc)
    signed = _parse_time(value["signed_at_utc"])
    issued = _parse_time(request["issued_at_utc"])
    expires = _parse_time(request["expires_at_utc"])
    if signed < issued or signed > current or signed >= expires or expires <= current:
        raise ValueError("detached signature timing")
    exact_message = base64.b64decode(request["signed_message_base64"], validate=True)
    if hashlib.sha256(exact_message).hexdigest() != value["signed_message_sha256"]:
        raise ValueError("detached signature message digest")
    return value


def persist_detached_signature_bundle(path, value: dict, *, request: dict, now: datetime | None = None) -> dict:
    validated = validate_detached_signature_bundle(value, request=request, now=now)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_canonical_bytes(validated))
    return load_detached_signature_bundle(path, request=request, now=now)


def load_detached_signature_bundle(path, *, request: dict, now: datetime | None = None) -> dict:
    return validate_detached_signature_bundle(
        _read_canonical(Path(path), "detached signature bundle"), request=request, now=now
    )


def import_execution_authorization_artifact(
    path,
    *,
    request: dict,
    signature_bundle: dict,
    binding: ExpectedAuthorizationBinding,
    now: datetime | None = None,
) -> dict:
    """Combine a validated request and detached signature into the existing artifact schema."""
    validate_detached_signature_bundle(signature_bundle, request=request, now=now)
    artifact = dict(request["authorization_payload"])
    if artifact.get("schema_version") != AUTHORIZATION_SCHEMA:
        raise ValueError("authorization request payload schema")
    artifact["authenticator_envelope"] = {
        "scheme": "ed25519",
        "key_id": signature_bundle["key_id"],
        "signature_base64": signature_bundle["signature_base64"],
    }
    if authorization_signed_message(artifact) != base64.b64decode(request["signed_message_base64"], validate=True):
        raise ValueError("authorization exact signed message changed")
    artifact["payload_digest"] = digest(artifact)
    artifact["canonical_artifact_digest"] = digest(artifact)
    validate_authorization_binding(artifact, binding)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_canonical_bytes(artifact))
    loaded = load_execution_authorization_artifact(path)
    validate_authorization_binding(loaded, binding)
    return loaded


def persist_verified_authorization_receipt(path, receipt: VerifiedAuthorizationReceipt, binding: ExpectedAuthorizationBinding) -> VerifiedAuthorizationReceipt:
    if not isinstance(receipt, VerifiedAuthorizationReceipt):
        raise TypeError("VerifiedAuthorizationReceipt required")
    receipt.validate(binding)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_canonical_bytes(receipt.data))
    return load_verified_authorization_receipt(path, binding)


def load_verified_authorization_receipt(path, binding: ExpectedAuthorizationBinding) -> VerifiedAuthorizationReceipt:
    value = _read_canonical(Path(path), "verified authorization receipt")
    return VerifiedAuthorizationReceipt(value).validate(binding)


def run_detached_authorization_verification_only(
    package_path,
    preflight_path,
    trust_config_path,
    *,
    detached_signature_path=None,
    authorization_artifact_path=None,
    receipt_path=None,
    repository_root=PROJECT_ROOT,
    now: datetime | None = None,
) -> dict:
    """Verify offline authorization evidence and deliberately stop before execution context creation."""
    package = load_prepared_launch_package(package_path)
    paths = authoritative_detached_authorization_paths(package_path)
    supplied = {
        "detached_signature_bundle": detached_signature_path,
        "authorization_artifact": authorization_artifact_path,
        "verified_receipt": receipt_path,
    }
    for key, candidate in supplied.items():
        if candidate is not None and Path(candidate).resolve() != paths[key].resolve():
            raise ValueError(f"{key} path is not package-authoritative")
    current = now or datetime.now(timezone.utc)
    request = load_execution_authorization_signing_request(
        paths["unsigned_request"], package_path=package_path, preflight_path=preflight_path,
        trust_config_path=trust_config_path, repository_root=repository_root, now=current,
    )
    bundle = load_detached_signature_bundle(paths["detached_signature_bundle"], request=request, now=current)
    trust = load_production_authorization_trust_config(trust_config_path, repository_root=repository_root)
    if bundle["key_id"] != trust["expected_key_id"]:
        raise ValueError("detached signature key does not match pinned trust")
    binding = build_expected_authorization_binding(package_path, preflight_path, now=current)
    artifact = import_execution_authorization_artifact(
        paths["authorization_artifact"], request=request, signature_bundle=bundle,
        binding=binding, now=current,
    )
    verifier = build_production_authorization_verifier_from_config(
        trust_config_path, repository_root=repository_root
    )
    receipt = verify_execution_authorization(
        package_path, preflight_path, paths["authorization_artifact"], verifier
    )
    loaded_receipt = persist_verified_authorization_receipt(paths["verified_receipt"], receipt, binding)
    if Path(package["prospective_attempt_root"]).exists():
        raise ValueError("verification-only flow created prospective attempt root")
    return {
        "schema_version": READINESS_SCHEMA,
        "authorization_id": artifact["authorization_id"],
        "launch_id": binding.launch_id,
        "attempt_id": binding.attempt_id,
        "identity_id": binding.identity_id,
        "unsigned_request_digest": request["canonical_request_digest"],
        "detached_signature_bundle_digest": bundle["canonical_bundle_digest"],
        "authorization_artifact_digest": artifact["canonical_artifact_digest"],
        "verified_receipt_digest": loaded_receipt.data["canonical_receipt_digest"],
        "verifier_identity": loaded_receipt.data["verifier_identity"],
        "trust_domain": loaded_receipt.data["trust_domain"],
        "trust_root_loaded": True,
        "signature_present": True,
        "authorization_verified": True,
        "trust_verified": True,
        "receipt_valid": True,
        "execution_context_created": False,
        "execution_authorized_for_materialization": False,
        "materialization_allowed": False,
        "attempt_materialized": False,
        "ownership_acquired": False,
        "process_launched": False,
        "authorization_consumed": False,
        "final_marker_written": False,
    }
