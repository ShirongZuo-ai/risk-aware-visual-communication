"""Pinned public trust and unsigned signing-request export for M6-A v2."""
from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_execution_authorization import (
    ED25519_DOMAIN,
    SCHEMA as AUTHORIZATION_SCHEMA,
    Ed25519AuthorizationVerifier,
    authorization_canonical_payload_bytes,
    authorization_signed_message,
    build_expected_authorization_binding,
)

TRUST_SCHEMA = "m6a-v2-production-authorization-trust-v1"
REQUEST_SCHEMA = "m6a-v2-unsigned-authorization-signing-request-v1"
PROHIBITED_CONFIG_FIELDS = {"private_key", "private_key_path", "password", "secret", "signing_command", "auto_sign"}


def _canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _parse_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed


def validate_production_authorization_trust_config(value, *, repository_root=PROJECT_ROOT):
    required = {
        "schema_version", "verifier_type", "public_key_path", "expected_public_key_fingerprint",
        "expected_key_id", "expected_issuer", "accepted_authorization_policy_version",
        "verifier_identity", "trust_domain", "signing_domain_hex", "config_digest",
    }
    if not isinstance(value, dict) or set(value) != required or PROHIBITED_CONFIG_FIELDS & set(value):
        raise ValueError("invalid production trust schema")
    if value["schema_version"] != TRUST_SCHEMA or value["verifier_type"] != "ed25519":
        raise ValueError("unsupported production trust configuration")
    if value["config_digest"] != digest({key: item for key, item in value.items() if key != "config_digest"}):
        raise ValueError("production trust config digest")
    text_fields = ("expected_key_id", "expected_issuer", "accepted_authorization_policy_version", "verifier_identity", "trust_domain")
    if any(not isinstance(value[key], str) or not value[key] or "placeholder" in value[key].lower() for key in text_fields):
        raise ValueError("incomplete production trust identity")
    if value["signing_domain_hex"] != ED25519_DOMAIN.hex():
        raise ValueError("signing domain mismatch")
    relative = Path(value["public_key_path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("public key path must be repository-relative")
    root = Path(repository_root).resolve()
    public_path = root / relative
    if public_path.is_symlink() or any(parent.is_symlink() for parent in public_path.parents if parent != root.parent):
        raise ValueError("public key symlink rejected")
    resolved = public_path.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("trusted public key unavailable")
    verifier = Ed25519AuthorizationVerifier(
        public_key_path=resolved,
        expected_public_key_fingerprint=value["expected_public_key_fingerprint"],
        expected_key_id=value["expected_key_id"],
        expected_issuer=value["expected_issuer"],
        expected_policy_version=value["accepted_authorization_policy_version"],
        verifier_identity=value["verifier_identity"],
        trust_domain=value["trust_domain"],
    )
    return value, resolved, verifier.public_key_fingerprint


def load_production_authorization_trust_config(path, *, repository_root=PROJECT_ROOT):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    if raw != _canonical_bytes(value):
        raise ValueError("noncanonical production trust configuration")
    return validate_production_authorization_trust_config(value, repository_root=repository_root)[0]


def build_production_authorization_verifier_from_config(path, *, repository_root=PROJECT_ROOT):
    value = load_production_authorization_trust_config(path, repository_root=repository_root)
    _, public_path, _ = validate_production_authorization_trust_config(value, repository_root=repository_root)
    return Ed25519AuthorizationVerifier(
        public_key_path=public_path,
        expected_public_key_fingerprint=value["expected_public_key_fingerprint"],
        expected_key_id=value["expected_key_id"],
        expected_issuer=value["expected_issuer"],
        expected_policy_version=value["accepted_authorization_policy_version"],
        verifier_identity=value["verifier_identity"],
        trust_domain=value["trust_domain"],
    )


def _authorization_payload(binding, trust, issued_at_utc, expires_at_utc, nonce):
    authorization_id = digest({"binding": binding.__dict__, "issued_at_utc": issued_at_utc, "nonce": nonce, "key_id": trust["expected_key_id"]})
    return {
        "schema_version": AUTHORIZATION_SCHEMA,
        "authorization_id": authorization_id,
        "launch_id": binding.launch_id,
        "attempt_id": binding.attempt_id,
        "identity_id": binding.identity_id,
        "prepared_package_digest": binding.prepared_package_digest,
        "fresh_preflight_report_digest": binding.fresh_preflight_report_digest,
        "launch_spec_digest": binding.launch_spec_digest,
        "runtime_config_digest": binding.runtime_config_digest,
        "prospective_attempt_root": binding.prospective_attempt_root,
        "issued_at_utc": issued_at_utc,
        "expires_at_utc": expires_at_utc,
        "issuer_claim": trust["expected_issuer"],
        "authorization_policy_version": trust["accepted_authorization_policy_version"],
        "nonce": nonce,
    }


def validate_execution_authorization_signing_request(value, *, package_path, preflight_path, trust_config_path, repository_root=PROJECT_ROOT, now=None):
    if not isinstance(value, dict) or value.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError("unsigned signing request schema")
    if value.get("canonical_request_digest") != digest({key: item for key, item in value.items() if key != "canonical_request_digest"}):
        raise ValueError("unsigned signing request digest")
    if value.get("signature_absent") is not True or value.get("signature_present") is not False or value.get("trust_root_loaded") is not True or any(value.get(key) is not False for key in ("authorization_verified", "execution_authorized", "materialization_allowed")) or "signature" in value:
        raise ValueError("unsigned signing request semantics")
    trust = load_production_authorization_trust_config(trust_config_path, repository_root=repository_root)
    binding = build_expected_authorization_binding(package_path, preflight_path, now=now)
    if value.get("trust_config_digest") != trust["config_digest"] or value.get("public_key_fingerprint") != trust["expected_public_key_fingerprint"] or value.get("key_id") != trust["expected_key_id"] or value.get("issuer") != trust["expected_issuer"] or value.get("policy_version") != trust["accepted_authorization_policy_version"] or value.get("trust_domain") != trust["trust_domain"] or value.get("signing_domain_hex") != ED25519_DOMAIN.hex():
        raise ValueError("unsigned signing request trust binding")
    payload = _authorization_payload(binding, trust, value["issued_at_utc"], value["expires_at_utc"], value["nonce"])
    if any(value.get(key) != getattr(binding, key) for key in ("launch_id", "attempt_id", "identity_id")) or value.get("authorization_id") != payload["authorization_id"] or value.get("authorization_payload") != payload:
        raise ValueError("unsigned signing request authorization payload")
    payload_bytes = authorization_canonical_payload_bytes(payload)
    signed_message = authorization_signed_message(payload)
    if value.get("authorization_payload_base64") != base64.b64encode(payload_bytes).decode("ascii") or value.get("payload_digest") != digest(payload) or value.get("signed_message_base64") != base64.b64encode(signed_message).decode("ascii") or value.get("signed_message_sha256") != __import__("hashlib").sha256(signed_message).hexdigest():
        raise ValueError("unsigned signing request byte contract")
    current = now or datetime.now(timezone.utc)
    issued, expires = _parse_time(value["issued_at_utc"]), _parse_time(value["expires_at_utc"])
    if issued > current or expires <= issued or expires <= current:
        raise ValueError("unsigned signing request timing")
    root = Path(binding.prospective_attempt_root)
    if root.exists():
        raise ValueError("prospective attempt root already exists")
    from scripts.m6a_v2_execution_safety import attempt_path_plan
    planned = attempt_path_plan(binding.launch_id, binding.attempt_id, binding.identity_id, "preflight", 0)["artifacts"]
    if any(Path(planned[key]).exists() for key in ("ownership_marker", "consumption_record", "final_marker")):
        raise ValueError("execution evidence already exists")
    return value


def persist_execution_authorization_signing_request(path, value, *, package_path, preflight_path, trust_config_path, repository_root=PROJECT_ROOT, now=None):
    validated = validate_execution_authorization_signing_request(value, package_path=package_path, preflight_path=preflight_path, trust_config_path=trust_config_path, repository_root=repository_root, now=now)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_canonical_bytes(validated))
    return load_execution_authorization_signing_request(path, package_path=package_path, preflight_path=preflight_path, trust_config_path=trust_config_path, repository_root=repository_root, now=now)


def load_execution_authorization_signing_request(path, *, package_path, preflight_path, trust_config_path, repository_root=PROJECT_ROOT, now=None):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    if raw != _canonical_bytes(value):
        raise ValueError("noncanonical unsigned signing request")
    return validate_execution_authorization_signing_request(value, package_path=package_path, preflight_path=preflight_path, trust_config_path=trust_config_path, repository_root=repository_root, now=now)


def export_execution_authorization_signing_request(package_path, preflight_path, trust_config_path, output_path, *, repository_root=PROJECT_ROOT, issued_at_utc=None, expires_at_utc=None, nonce=None, now=None):
    trust = load_production_authorization_trust_config(trust_config_path, repository_root=repository_root)
    build_production_authorization_verifier_from_config(trust_config_path, repository_root=repository_root)
    current = now or datetime.now(timezone.utc).replace(microsecond=0)
    binding = build_expected_authorization_binding(package_path, preflight_path, now=current)
    issued = issued_at_utc or current.isoformat()
    expires = expires_at_utc or (current + timedelta(minutes=15)).isoformat()
    nonce = nonce or secrets.token_hex(32)
    payload = _authorization_payload(binding, trust, issued, expires, nonce)
    payload_bytes = authorization_canonical_payload_bytes(payload)
    signed_message = authorization_signed_message(payload)
    request = {
        "schema_version": REQUEST_SCHEMA,
        "artifact_kind": "unsigned-execution-authorization-signing-request",
        "signing_domain_hex": ED25519_DOMAIN.hex(),
        "key_id": trust["expected_key_id"],
        "issuer": trust["expected_issuer"],
        "policy_version": trust["accepted_authorization_policy_version"],
        "trust_domain": trust["trust_domain"],
        "trust_config_digest": trust["config_digest"],
        "public_key_fingerprint": trust["expected_public_key_fingerprint"],
        "authorization_id": payload["authorization_id"],
        "launch_id": binding.launch_id,
        "attempt_id": binding.attempt_id,
        "identity_id": binding.identity_id,
        "issued_at_utc": issued,
        "expires_at_utc": expires,
        "nonce": nonce,
        "authorization_payload": payload,
        "authorization_payload_base64": base64.b64encode(payload_bytes).decode("ascii"),
        "payload_digest": digest(payload),
        "signed_message_base64": base64.b64encode(signed_message).decode("ascii"),
        "signed_message_sha256": __import__("hashlib").sha256(signed_message).hexdigest(),
        "signature_absent": True,
        "signature_present": False,
        "trust_root_loaded": True,
        "authorization_verified": False,
        "execution_authorized": False,
        "materialization_allowed": False,
    }
    request["canonical_request_digest"] = digest(request)
    return persist_execution_authorization_signing_request(output_path, request, package_path=package_path, preflight_path=preflight_path, trust_config_path=trust_config_path, repository_root=repository_root, now=current)


def authoritative_signing_request_path(package_path):
    from scripts.m6a_v2_prepared_launch import load_prepared_launch_package
    package = load_prepared_launch_package(package_path)
    workspace = Path(package["preflight_workspace_root"]).resolve()
    if workspace != Path(package_path).resolve().parent:
        raise ValueError("prepared package workspace mismatch")
    return workspace / "unsigned_authorization_signing_request.json"


def run_production_authorization_readiness(package_path, preflight_path, trust_config_path, signing_request_path=None, *, repository_root=PROJECT_ROOT, now=None):
    trust = load_production_authorization_trust_config(trust_config_path, repository_root=repository_root)
    verifier = build_production_authorization_verifier_from_config(trust_config_path, repository_root=repository_root)
    authoritative_path = authoritative_signing_request_path(package_path)
    if signing_request_path is not None and Path(signing_request_path).resolve() != authoritative_path:
        raise ValueError("signing request path is not package-authoritative")
    signing_request_path = authoritative_path
    if signing_request_path.exists():
        request = load_execution_authorization_signing_request(signing_request_path, package_path=package_path, preflight_path=preflight_path, trust_config_path=trust_config_path, repository_root=repository_root, now=now)
    else:
        request = export_execution_authorization_signing_request(package_path, preflight_path, trust_config_path, signing_request_path, repository_root=repository_root, now=now)
    load_execution_authorization_signing_request(signing_request_path, package_path=package_path, preflight_path=preflight_path, trust_config_path=trust_config_path, repository_root=repository_root, now=now)
    return {"schema_version": "m6a-v2-production-authorization-readiness-v1", "verifier_identity": verifier.verifier_identity, "trust_config_digest": trust["config_digest"], "signing_request_path": str(signing_request_path), "signing_request_digest": request["canonical_request_digest"], "trust_root_loaded": True, "public_key_fingerprint_verified": True, "signing_request_valid": True, "signature_present": False, "authorization_verified": False, "execution_authorized": False, "attempt_materialized": False, "process_launched": False}
