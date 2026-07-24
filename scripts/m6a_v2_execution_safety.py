"""Fail-closed ownership, authorization, launch, and final-result gates for M6-A v2.

This module never starts a process. Process execution is injected through the
``launch_owned_attempt`` runner contract.
"""
from __future__ import annotations

import json
import os
import socket
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest

PILOT_ROOT = PROJECT_ROOT / "data" / "m6a" / "pilot"
CONTROL_ROOT = PROJECT_ROOT / "results" / "m6a_v2_control"
OWNER = ".m6a_v2_ownership.json"
OWNED_CONTEXT = ".m6a_v2_owned_context.json"
OWNERSHIP_TERMINAL = ".m6a_v2_ownership_terminal.json"
FINAL = "m6a_v2_final_success.json"
OWNED_CONTEXT_SCHEMA = "m6a-v2-durable-owned-attempt-context-v1"
_OWNED_TOKEN = object()


@dataclass(frozen=True)
class ValidatedExecutionContext:
    """B2-produced authority boundary; tests may use the explicit temporary fixture."""

    authorization_id: str
    authorization_sha256: str
    launch_id: str
    attempt_id: str
    identity_id: str
    scene_id: str
    seed: int
    launch_spec_sha256: str
    runtime_config_sha256: str
    prospective_attempt_root: str
    validated_at_utc: str
    test_fixture: bool = False

    def validate(self):
        if self.test_fixture is not True or not all(
            isinstance(value, str) and value
            for value in (
                self.authorization_id,
                self.authorization_sha256,
                self.launch_id,
                self.attempt_id,
                self.identity_id,
                self.scene_id,
                self.launch_spec_sha256,
                self.runtime_config_sha256,
            )
        ):
            raise ValueError("invalid validated execution context")
        root = validate_prospective_root(
            self.prospective_attempt_root, launch_id=self.launch_id, attempt_id=self.attempt_id
        )
        temporary = Path(tempfile.gettempdir()).resolve()
        if temporary not in PILOT_ROOT.resolve().parents and PILOT_ROOT.resolve() != temporary:
            raise ValueError("test context requires temporary pilot root")
        return root

    @classmethod
    def test_fixture_for(
        cls, *, launch_id, attempt_id, identity_id, scene_id, seed, launch_spec_sha256, runtime_config_sha256
    ):
        root = attempt_root(launch_id, attempt_id)
        return cls(
            "test-" + digest({"l": launch_id, "a": attempt_id}),
            digest({"l": launch_id, "a": attempt_id, "fixture": True}),
            launch_id,
            attempt_id,
            identity_id,
            scene_id,
            seed,
            launch_spec_sha256,
            runtime_config_sha256,
            str(root),
            _utc(),
            True,
        )


class OwnedAttemptContext(Mapping):
    """Factory-only, disk-backed production authority for one owned attempt."""

    def __init__(self, token, data: dict, artifact_path: Path, expected_head: str):
        if token is not _OWNED_TOKEN:
            raise TypeError("load_owned_attempt_context factory required")
        self._data = data
        self.artifact_path = Path(artifact_path).resolve()
        self.expected_head = expected_head

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    @property
    def data(self) -> dict:
        return dict(self._data)


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed


def _new(path: Path, value: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = dict(value)
    value["sha256"] = digest(value)
    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_canonical(value))
    return value


def _new_canonical(path: Path, value: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = dict(value)
    value["canonical_digest"] = digest(value)
    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_canonical(value))
    return value


def _read_canonical(path: Path, *, digest_field="sha256") -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe or missing canonical evidence")
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != _canonical(value) or value.get(digest_field) != digest(
        {key: item for key, item in value.items() if key != digest_field}
    ):
        raise ValueError("invalid canonical evidence")
    return value


def _under(path: Path, root: Path) -> bool:
    return path.is_absolute() and path.resolve().is_relative_to(root.resolve())


def attempt_root(launch_id, attempt_id):
    if not all(
        isinstance(value, str) and value and value.replace("-", "").isalnum()
        for value in (launch_id, attempt_id)
    ):
        raise ValueError("unsafe launch/attempt id")
    return (PILOT_ROOT / launch_id / attempt_id).resolve()


def attempt_path_plan(launch_id, attempt_id, identity_id, scene_id, seed):
    root = attempt_root(launch_id, attempt_id)
    items = {
        "ownership_marker": root / OWNER,
        "owned_context": root / OWNED_CONTEXT,
        "ownership_terminal": root / OWNERSHIP_TERMINAL,
        "stdout": root / "host_stdout.log",
        "stderr": root / "host_stderr.log",
        "process_evidence": root / "host_process_result.json",
        "runtime_summary": root / "episode_runtime_summary.json",
        "runtime_status": root / "episode_runtime_status.json",
        "runtime_diagnostic": root / "episode_runtime_failure.json",
        "runtime_manifest": root / "runtime_artifacts.json",
        "snapshot_root": root / "snapshots",
        "codec_root": root / "codec",
        "codec_aggregate": root / "codec_aggregate.json",
        "aggregate_validation": root / "codec_aggregate_validation.json",
        "joint_report": root / "joint_validation.json",
        "final_marker": root / FINAL,
        "consumption_record": CONTROL_ROOT
        / "consumption"
        / (digest({"launch": launch_id, "attempt": attempt_id}) + ".json"),
    }
    if len({str(path.resolve()).lower() for path in items.values()}) != len(items):
        raise ValueError("artifact path alias")
    for name, path in items.items():
        if name != "consumption_record" and not _under(path, root):
            raise ValueError("artifact path escape")
    return {
        "schema_version": "m6a-v2-attempt-path-plan-v2",
        "launch_id": launch_id,
        "attempt_id": attempt_id,
        "identity_id": identity_id,
        "scene_id": scene_id,
        "seed": seed,
        "attempt_root": str(root),
        "artifacts": {key: str(path.resolve()) for key, path in items.items()},
    }


def validate_prospective_root(root, *, launch_id, attempt_id):
    root = Path(root)
    if (
        root != attempt_root(launch_id, attempt_id)
        or root.exists()
        or not _under(root, PILOT_ROOT)
        or CONTROL_ROOT.resolve() in root.parents
    ):
        raise ValueError("unsafe or reused attempt root")
    if any(part in {".", ".."} for part in root.parts):
        raise ValueError("path traversal")
    parent = root.parent
    while parent != PILOT_ROOT.parent:
        if parent.exists() and parent.is_symlink():
            raise ValueError("symlink escape")
        parent = parent.parent
    return root


def acquire_ownership(root, authorization, *, launcher_identity="m6a-v2-host"):
    root = validate_prospective_root(
        root, launch_id=authorization["launch_id"], attempt_id=authorization["attempt_id"]
    )
    root.mkdir(parents=True, exist_ok=False)
    marker = {
        "schema_version": "m6a-v2-ownership-v1",
        "launch_id": authorization["launch_id"],
        "attempt_id": authorization["attempt_id"],
        "authorization_id": authorization["authorization_id"],
        "identity_id": authorization["identity_id"],
        "scene": authorization["scene_id"],
        "seed": authorization["seed"],
        "launch_spec_sha256": authorization["launch_spec_sha256"],
        "authorization_sha256": authorization["authorization_sha256"],
        "output_root": str(root),
        "launcher_identity": launcher_identity,
        "host": socket.gethostname(),
        "acquired_at_utc": _utc(),
        "state": "owned_pre_spawn",
        "launch_performed": False,
        "webots_started": False,
        "scientific_result": False,
    }
    try:
        return _new(root / OWNER, marker)
    except Exception:
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()
        raise


def load_ownership(path, root, *, owner_identity="m6a-v2-host"):
    root = Path(root).resolve()
    value = _read_canonical(path)
    if (
        value.get("schema_version") != "m6a-v2-ownership-v1"
        or value.get("output_root") != str(root)
        or value.get("launcher_identity") != owner_identity
        or value.get("state") != "owned_pre_spawn"
        or value.get("launch_performed") is not False
        or value.get("webots_started") is not False
        or value.get("scientific_result") is not False
    ):
        raise ValueError("invalid ownership evidence")
    return value


_load_ownership = load_ownership


def _production_owned_payload(package_path, package, context, ownership, receipt_path, root):
    external = dict(context.data)
    receipt = dict(external["verified_receipt"])
    return {
        "schema_version": OWNED_CONTEXT_SCHEMA,
        "package_path": str(Path(package_path).resolve()),
        "package_digest": package["package_sha256"],
        "package_head": package["head"],
        "package_branch": package["branch"],
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "scene_id": package["scene_id"],
        "seed": package["seed"],
        "authorization_id": external["authorization_id"],
        "nonce": external["nonce"],
        "receipt_path": str(Path(receipt_path).resolve()),
        "receipt_digest": receipt["canonical_receipt_digest"],
        "external_context": external,
        "external_context_digest": external["canonical_context_digest"],
        "attempt_root": str(root),
        "ownership_path": str((Path(root) / OWNER).resolve()),
        "ownership_digest": ownership["sha256"],
        "execution_mode": "production",
        "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_result": False,
    }


def _rollback_new_owned_root(root: Path) -> None:
    root = Path(root)
    allowed = {root / OWNER, root / OWNED_CONTEXT}
    if root.is_dir() and all(path in allowed for path in root.iterdir()):
        for path in (root / OWNED_CONTEXT, root / OWNER):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        if not any(root.iterdir()):
            root.rmdir()


def materialize_authorized_attempt(
    package,
    context,
    *,
    launcher_identity="m6a-v2-host",
    mode="test",
    prepared_package_path=None,
    repository_head=None,
):
    """The only B2-to-attempt transition; never starts a process."""
    if mode == "test":
        if not isinstance(context, ValidatedExecutionContext):
            raise TypeError("TestValidatedExecutionContext required")
        root = context.validate()
        authorization = {
            "authorization_id": context.authorization_id,
            "authorization_sha256": context.authorization_sha256,
            "launch_id": context.launch_id,
            "attempt_id": context.attempt_id,
            "identity_id": context.identity_id,
            "scene_id": context.scene_id,
            "seed": context.seed,
            "launch_spec_sha256": context.launch_spec_sha256,
            "nonce": digest({"test_context": context.authorization_id}),
        }
    elif mode == "production":
        from scripts.m6a_v2_detached_authorization import authoritative_detached_authorization_paths
        from scripts.m6a_v2_execution_authorization import (
            ExternallyValidatedExecutionContext,
            build_expected_authorization_binding,
        )
        from scripts.m6a_v2_prepared_launch import (
            current_repository_head,
            load_prepared_launch_package,
        )

        if not isinstance(context, ExternallyValidatedExecutionContext):
            raise TypeError("ExternallyValidatedExecutionContext required")
        if prepared_package_path is None:
            raise ValueError("production materialization requires authoritative prepared package path")
        repository_head = repository_head or current_repository_head()
        reloaded = load_prepared_launch_package(prepared_package_path, expected_head=repository_head)
        if reloaded != package:
            raise ValueError("caller package differs from authoritative package")
        binding = build_expected_authorization_binding(
            prepared_package_path, package["preflight_report_path"]
        )
        context.validate(binding)
        root = Path(context.data["prospective_attempt_root"])
        authorization = {
            "authorization_id": context.data["authorization_id"],
            "authorization_sha256": context.data["authorization_artifact_digest"],
            "launch_id": context.data["launch_id"],
            "attempt_id": context.data["attempt_id"],
            "identity_id": context.data["identity_id"],
            "scene_id": package["scene_id"],
            "seed": package["seed"],
            "launch_spec_sha256": context.data["launch_spec_digest"],
            "nonce": context.data["nonce"],
        }
        receipt_path = authoritative_detached_authorization_paths(prepared_package_path)["verified_receipt"]
    else:
        raise ValueError("unknown materialization mode")
    if (
        package.get("launch_id") != authorization["launch_id"]
        or package.get("attempt_id") != authorization["attempt_id"]
        or package.get("identity_id") != authorization["identity_id"]
        or package.get("prospective_attempt_root") != str(root)
    ):
        raise ValueError("package/context mismatch")
    paths = attempt_path_plan(
        authorization["launch_id"],
        authorization["attempt_id"],
        authorization["identity_id"],
        authorization["scene_id"],
        authorization["seed"],
    )["artifacts"]
    preexisting = (
        "ownership_marker",
        "owned_context",
        "ownership_terminal",
        "consumption_record",
        "process_evidence",
        "final_marker",
    )
    if Path(root).exists() or any(Path(paths[key]).exists() for key in preexisting):
        raise ValueError("attempt or execution evidence already exists")
    ownership = acquire_ownership(root, authorization, launcher_identity=launcher_identity)
    if mode == "test":
        owned = {
            "schema_version": "m6a-v2-owned-attempt-context-v1",
            "attempt_root": str(root),
            "ownership": ownership,
            "launch_id": authorization["launch_id"],
            "attempt_id": authorization["attempt_id"],
            "identity_id": authorization["identity_id"],
            "authorization_id": authorization["authorization_id"],
            "nonce": authorization["nonce"],
            "execution_mode": mode,
            "test_fixture": True,
        }
        owned["canonical_digest"] = digest(owned)
        return owned
    try:
        payload = _production_owned_payload(
            prepared_package_path, package, context, ownership, receipt_path, root
        )
        _new_canonical(Path(paths["owned_context"]), payload)
        return load_owned_attempt_context(
            paths["owned_context"], expected_head=repository_head, mode="production"
        )
    except Exception:
        _rollback_new_owned_root(root)
        raise


def _expected_binding_from_owned(value: dict):
    from scripts.m6a_v2_execution_authorization import ExpectedAuthorizationBinding

    external = value["external_context"]
    return ExpectedAuthorizationBinding(
        launch_id=value["launch_id"],
        attempt_id=value["attempt_id"],
        identity_id=value["identity_id"],
        prepared_package_digest=value["package_digest"],
        fresh_preflight_report_digest=external["fresh_preflight_report_digest"],
        launch_spec_digest=external["launch_spec_digest"],
        runtime_config_digest=external["runtime_config_digest"],
        prospective_attempt_root=value["attempt_root"],
    )


def _load_production_owned_context(path, *, expected_head):
    from scripts.m6a_v2_detached_authorization import authoritative_detached_authorization_paths_for_audit
    from scripts.m6a_v2_execution_authorization import VerifiedAuthorizationReceipt
    from scripts.m6a_v2_prepared_launch import load_owned_prepared_launch_package

    path = Path(path).resolve()
    value = _read_canonical(path, digest_field="canonical_digest")
    if value.get("schema_version") != OWNED_CONTEXT_SCHEMA or value.get("execution_mode") != "production":
        raise ValueError("invalid durable owned context schema")
    required_digests = (
        "package_digest",
        "receipt_digest",
        "external_context_digest",
        "ownership_digest",
    )
    if any(not isinstance(value.get(key), str) or len(value[key]) != 64 for key in required_digests):
        raise ValueError("incomplete durable owned context digests")
    if value.get("scientific_result") is not False:
        raise ValueError("owned context cannot be scientific evidence")
    root = attempt_root(value.get("launch_id"), value.get("attempt_id"))
    if value.get("attempt_root") != str(root) or path != root / OWNED_CONTEXT or not root.is_dir():
        raise ValueError("durable owned context root/path mismatch")
    ownership_path = root / OWNER
    if value.get("ownership_path") != str(ownership_path.resolve()):
        raise ValueError("durable owned context ownership path")
    ownership = load_ownership(ownership_path, root)
    if value["ownership_digest"] != ownership["sha256"]:
        raise ValueError("durable owned context ownership digest")
    package_path = Path(value.get("package_path", "")).resolve()
    package = load_owned_prepared_launch_package(
        package_path, ownership, expected_head=expected_head
    )
    package_fields = {
        "package_digest": package["package_sha256"],
        "package_head": package["head"],
        "package_branch": package["branch"],
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "scene_id": package["scene_id"],
        "seed": package["seed"],
    }
    if any(value.get(key) != expected for key, expected in package_fields.items()):
        raise ValueError("durable owned context package binding")
    authoritative_receipt = authoritative_detached_authorization_paths_for_audit(package_path)["verified_receipt"].resolve()
    receipt_path = Path(value.get("receipt_path", "")).resolve()
    if receipt_path != authoritative_receipt:
        raise ValueError("durable owned context receipt path")
    receipt = _read_canonical(receipt_path, digest_field="canonical_receipt_digest")
    if receipt["canonical_receipt_digest"] != value["receipt_digest"]:
        raise ValueError("durable owned context receipt digest")
    external = value.get("external_context")
    if (
        not isinstance(external, dict)
        or external.get("canonical_context_digest") != digest(
            {key: item for key, item in external.items() if key != "canonical_context_digest"}
        )
        or external.get("canonical_context_digest") != value["external_context_digest"]
        or external.get("verified_receipt") != receipt
        or external.get("verified_receipt_digest") != value["receipt_digest"]
        or external.get("authorization_id") != value["authorization_id"]
        or external.get("nonce") != value["nonce"]
    ):
        raise ValueError("durable external-context binding")
    binding = _expected_binding_from_owned(value)
    materialized_at = _parse_utc(value["materialized_at_utc"])
    VerifiedAuthorizationReceipt(receipt).validate(binding, now=materialized_at)
    for key, expected in asdict(binding).items():
        if external.get(key) != expected:
            raise ValueError("durable external-context package binding")
    if _parse_utc(external["context_created_at_utc"]) > materialized_at:
        raise ValueError("owned context materialization time")
    return OwnedAttemptContext(_OWNED_TOKEN, value, path, expected_head)


def _validate_test_owned_context(value):
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "m6a-v2-owned-attempt-context-v1"
        or value.get("canonical_digest")
        != digest({key: item for key, item in value.items() if key != "canonical_digest"})
        or value.get("execution_mode") != "test"
        or value.get("test_fixture") is not True
    ):
        raise ValueError("invalid test owned attempt context")
    root = Path(value["attempt_root"]).resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if (
        not _under(root, PILOT_ROOT)
        or temporary not in PILOT_ROOT.resolve().parents and PILOT_ROOT.resolve() != temporary
    ):
        raise ValueError("unsafe test owned attempt root")
    ownership = load_ownership(root / OWNER, root)
    if (
        ownership["launch_id"] != value["launch_id"]
        or ownership["attempt_id"] != value["attempt_id"]
        or ownership["identity_id"] != value["identity_id"]
        or ownership["authorization_id"] != value["authorization_id"]
        or ownership["sha256"] != value["ownership"]["sha256"]
    ):
        raise ValueError("test owned context mismatch")
    return root, ownership, value


def load_owned_attempt_context(value, *, expected_head=None, mode="production"):
    """Load a production artifact path, or revalidate a temporary test context."""
    if mode == "test":
        root, ownership, loaded = _validate_test_owned_context(value)
        result = dict(loaded)
        result["attempt_root"] = str(root)
        result["ownership"] = ownership
        if result["canonical_digest"] != digest(
            {key: item for key, item in result.items() if key != "canonical_digest"}
        ):
            raise ValueError("test owned context reload digest")
        return result
    if mode != "production":
        raise ValueError("unknown owned context mode")
    if isinstance(value, (dict, OwnedAttemptContext)):
        raise TypeError("production owned context must be reloaded from its canonical artifact path")
    if not isinstance(expected_head, str) or not expected_head:
        raise ValueError("expected repository HEAD required for production owned context")
    return _load_production_owned_context(value, expected_head=expected_head)


def _validated_owned(value, *, mode, repository_head=None):
    if mode == "test":
        return _validate_test_owned_context(value)
    if mode != "production" or not isinstance(value, OwnedAttemptContext):
        raise TypeError("OwnedAttemptContext required for production launch")
    expected = repository_head or value.expected_head
    reloaded = _load_production_owned_context(value.artifact_path, expected_head=expected)
    if reloaded.data != value.data:
        raise ValueError("owned context changed after reload")
    root = Path(reloaded["attempt_root"])
    ownership = load_ownership(reloaded["ownership_path"], root)
    return root, ownership, reloaded


def _identity(context, ownership):
    return {
        "launch_id": context["launch_id"],
        "attempt_id": context["attempt_id"],
        "identity_id": context["identity_id"],
        "scene_id": ownership["scene"],
        "seed": ownership["seed"],
    }


def _launched_from_evidence(context, root, ownership, consumption, process, *, mode, idempotent):
    launched = {
        "schema_version": "m6a-v2-launched-attempt-context-v1",
        "launch_id": context["launch_id"],
        "attempt_id": context["attempt_id"],
        "identity_id": context["identity_id"],
        "authorization_id": context["authorization_id"],
        "nonce": context["nonce"],
        "owner_identity": ownership["launcher_identity"],
        "attempt_root": str(root),
        "ownership_digest": ownership["sha256"],
        "consumption_path": str(
            attempt_path_plan(
                context["launch_id"],
                context["attempt_id"],
                context["identity_id"],
                ownership["scene"],
                ownership["seed"],
            )["artifacts"]["consumption_record"]
        ),
        "consumption_digest": consumption["sha256"],
        "process_evidence_path": str(Path(root) / "host_process_result.json"),
        "process_evidence_digest": process["sha256"],
        "launch_performed": True,
        "process_outcome": {
            "return_code": process["return_code"],
            "timed_out": process["timed_out"],
            "termination_state": process["termination_state"],
        },
        "started_at_utc": process["started_at_utc"],
        "ended_at_utc": process["ended_at_utc"],
        "execution_mode": mode,
        "idempotent": idempotent,
    }
    launched["canonical_digest"] = digest(launched)
    return launched


def recover_launched_attempt_context(owned_attempt_context, *, mode="production", repository_head=None):
    """Reload a complete consumption/process pair without invoking a runner."""
    from scripts.m6a_v2_runtime_evidence import load_process_evidence

    root, ownership, context = _validated_owned(
        owned_attempt_context, mode=mode, repository_head=repository_head
    )
    paths = attempt_path_plan(
        context["launch_id"], context["attempt_id"], context["identity_id"], ownership["scene"], ownership["seed"]
    )["artifacts"]
    consumption_path = Path(paths["consumption_record"])
    process_path = Path(paths["process_evidence"])
    if consumption_path.exists() != process_path.exists() or not consumption_path.exists():
        raise ValueError("complete launch evidence pair required for recovery")
    terminal_path = Path(paths["ownership_terminal"])
    if terminal_path.exists():
        terminal = load_ownership_terminal(terminal_path, ownership=ownership)
        if terminal["state"] != "completed":
            raise ValueError(f"attempt terminal state rejects recovery: {terminal['state']}")
    consumption = load_consumption(consumption_path, context)
    process = load_process_evidence(process_path, _identity(context, ownership))
    return _launched_from_evidence(
        context, root, ownership, consumption, process, mode=mode, idempotent=True
    )


def load_finalized_attempt_result(owned_attempt_context, *, mode="production", repository_head=None):
    """Validate and return an already-completed attempt without invoking launch or completion."""
    launched = recover_launched_attempt_context(
        owned_attempt_context, mode=mode, repository_head=repository_head
    )
    root = Path(launched["attempt_root"])
    ownership = load_ownership(root / OWNER, root)
    paths = attempt_path_plan(
        launched["launch_id"], launched["attempt_id"], launched["identity_id"], ownership["scene"], ownership["seed"]
    )["artifacts"]
    final = _load_final_marker(paths["final_marker"], launched)
    terminal = load_ownership_terminal(paths["ownership_terminal"], ownership=ownership)
    if terminal["state"] != "completed" or terminal.get("final_marker_sha256") != final["sha256"]:
        raise ValueError("completed terminal/final marker mismatch")
    return {
        "schema_version": "m6a-v2-finalized-attempt-result-v1",
        "idempotent": True,
        "final_marker": final,
        "terminal": terminal,
    }


def launch_owned_attempt(owned_attempt_context, process_runner, *, mode="test", repository_head=None):
    """Launch once, then persist single-use consumption and process evidence."""
    from scripts.m6a_v2_runtime_evidence import load_process_evidence, persist_process_evidence

    root, ownership, context = _validated_owned(
        owned_attempt_context, mode=mode, repository_head=repository_head
    )
    paths = attempt_path_plan(
        context["launch_id"], context["attempt_id"], context["identity_id"], ownership["scene"], ownership["seed"]
    )["artifacts"]
    consumption = Path(paths["consumption_record"])
    evidence = Path(paths["process_evidence"])
    terminal = Path(paths["ownership_terminal"])
    final = Path(paths["final_marker"])
    if terminal.exists():
        state = load_ownership_terminal(terminal, ownership=ownership)["state"]
        raise ValueError(f"attempt terminal state rejects launch: {state}")
    if final.exists():
        raise ValueError("attempt already finalized")
    if consumption.exists() and evidence.exists():
        consumed = load_consumption(consumption, context)
        process = load_process_evidence(evidence, _identity(context, ownership))
        return _launched_from_evidence(
            context, root, ownership, consumed, process, mode=mode, idempotent=True
        )
    if consumption.exists() or evidence.exists():
        raise ValueError("incomplete launch evidence; retry forbidden")
    if not hasattr(process_runner, "run"):
        raise TypeError("process runner with run() required")
    result = process_runner.run(root=root, path_plan=paths, owned_attempt_context=context)
    required = {
        "launch_performed",
        "started_at_utc",
        "ended_at_utc",
        "return_code",
        "timed_out",
        "termination_state",
        "stdout_path",
        "stderr_path",
        "process_identity",
    }
    if (
        not isinstance(result, dict)
        or not required <= set(result)
        or not isinstance(result["launch_performed"], bool)
        or not isinstance(result["return_code"], int)
        or not isinstance(result["timed_out"], bool)
        or not result["process_identity"]
    ):
        raise ValueError("invalid process runner result")
    if not result["launch_performed"]:
        raise RuntimeError("process did not launch; authorization remains unconsumed")
    if (
        Path(result["stdout_path"]).resolve() != Path(paths["stdout"])
        or Path(result["stderr_path"]).resolve() != Path(paths["stderr"])
    ):
        raise ValueError("process runner wrote outside authoritative log paths")
    authorization = {
        "authorization_id": context["authorization_id"],
        "authorization_sha256": ownership["authorization_sha256"],
        "launch_id": context["launch_id"],
        "attempt_id": context["attempt_id"],
        "identity_id": context["identity_id"],
        "scene_id": ownership["scene"],
        "seed": ownership["seed"],
        "launch_spec_sha256": ownership["launch_spec_sha256"],
        "nonce": context["nonce"],
    }
    consume_authorization(
        authorization,
        ownership,
        launch_performed_at_utc=result["started_at_utc"],
        path=consumption,
    )
    persist_process_evidence(
        evidence,
        _identity(context, ownership),
        result["stdout_path"],
        result["stderr_path"],
        launch_performed=True,
        process_identity=result["process_identity"],
        timed_out=result["timed_out"],
        termination_state=result["termination_state"],
        started_at_utc=result["started_at_utc"],
        ended_at_utc=result["ended_at_utc"],
        return_code=result["return_code"],
        owner_identity=ownership["launcher_identity"],
        authorization_id=authorization["authorization_id"],
        nonce=authorization["nonce"],
    )
    process = load_process_evidence(evidence, _identity(context, ownership))
    consumed = load_consumption(consumption, context)
    return _launched_from_evidence(
        context, root, ownership, consumed, process, mode=mode, idempotent=False
    )


def build_authorization(package, *, head, branch, attempt_id, valid_minutes=30):
    launch_id = digest({"package": package["package_sha256"], "attempt": attempt_id})
    root = attempt_root(launch_id, attempt_id)
    value = {
        "schema_version": "m6a-v2-authorization-v2",
        "authorization_id": digest({"launch": launch_id, "attempt": attempt_id, "head": head}),
        "launch_id": launch_id,
        "attempt_id": attempt_id,
        "identity_id": package["identity_id"],
        "scene_id": package["scene_id"],
        "seed": package["seed"],
        "repository_root": str(PROJECT_ROOT),
        "authorized_head": head,
        "branch": branch,
        "prepared_package_sha256": package["package_sha256"],
        "launch_spec_sha256": package["launch_spec_sha256"],
        "runtime_config_sha256": package["runtime_config_sha256"],
        "temporary_world_sha256": package["temporary_world_sha256"],
        "controller_sha256": package["controller_sha256"],
        "executable": package["executable"],
        "argv_sha256": package["argv_sha256"],
        "manifest_sha256": package["manifest_sha256"],
        "lock_sha256": package["lock_sha256"],
        "owned_output_root": str(root),
        "purpose": "single-identity M6-A v2 pilot smoke",
        "authorized_at_utc": _utc(),
        "valid_until_utc": (
            datetime.now(timezone.utc) + timedelta(minutes=valid_minutes)
        ).replace(microsecond=0).isoformat(),
        "execution_authorized": True,
        "consumed": False,
        "launch_performed": False,
        "webots_started": False,
        "scientific_result": False,
        "test_fixture": False,
    }
    value["authorization_sha256"] = digest(value)
    return value


def validate_authorization(authorization, package, *, head, branch):
    if (
        authorization.get("authorization_sha256")
        != digest({key: item for key, item in authorization.items() if key != "authorization_sha256"})
        or not authorization.get("execution_authorized")
        or authorization.get("test_fixture")
        or authorization.get("consumed")
        or authorization.get("launch_performed")
        or authorization.get("scientific_result")
        or authorization.get("prepared_package_sha256") != package["package_sha256"]
        or authorization.get("authorized_head") != head
        or authorization.get("branch") != branch
        or datetime.fromisoformat(authorization["valid_until_utc"]) <= datetime.now(timezone.utc)
    ):
        raise PermissionError("invalid authorization")
    validate_prospective_root(
        authorization["owned_output_root"],
        launch_id=authorization["launch_id"],
        attempt_id=authorization["attempt_id"],
    )
    return authorization


def consume_authorization(authorization, ownership, *, launch_performed_at_utc=None, path=None):
    path = (
        Path(path)
        if path is not None
        else CONTROL_ROOT / "consumption" / (authorization["authorization_id"] + ".json")
    )
    root = authorization.get("owned_output_root", ownership.get("output_root"))
    return _new(
        path,
        {
            "schema_version": "m6a-v2-consumption-v1",
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": authorization["authorization_sha256"],
            "nonce": authorization.get("nonce", "legacy-no-nonce"),
            "launch_id": authorization["launch_id"],
            "attempt_id": authorization["attempt_id"],
            "identity_id": authorization["identity_id"],
            "output_root": root,
            "launch_spec_sha256": authorization["launch_spec_sha256"],
            "ownership_sha256": ownership["sha256"],
            "owner_identity": ownership["launcher_identity"],
            "launch_performed_at_utc": launch_performed_at_utc or _utc(),
            "consumed_at_utc": _utc(),
            "state": "consumed_post_launch",
        },
    )


def load_consumption(path, context):
    value = _read_canonical(path)
    if (
        any(value.get(key) != context[key] for key in ("authorization_id", "launch_id", "attempt_id", "identity_id"))
        or value.get("nonce") != context["nonce"]
        or value.get("state") != "consumed_post_launch"
    ):
        raise ValueError("invalid consumption evidence")
    return value


def write_final_marker(root, evidence):
    required = {
        "launch_id",
        "attempt_id",
        "authorization_id",
        "ownership_sha256",
        "process_sha256",
        "runtime_sha256",
        "snapshot_validation_sha256",
        "b5_sha256",
        "aggregate_sha256",
        "joint_validator_sha256",
        "manifest_sha256",
        "lock_sha256",
    }
    mode = evidence.get("execution_mode", "production")
    if mode == "production":
        required.add("consumption_sha256")
        if "research_launch_claim_sha256" in evidence:
            raise ValueError("research evidence is forbidden in production finalization")
    elif mode == "research":
        required.add("research_launch_claim_sha256")
        if "consumption_sha256" in evidence:
            raise ValueError("production consumption is forbidden in research finalization")
    else:
        raise ValueError("unsupported finalization mode")
    if not required <= set(evidence) or evidence.get("joint_pass") is not True:
        raise ValueError("joint validation required")
    return _new(
        Path(root) / FINAL,
        {
            "schema_version": "m6a-v2-final-success-v1",
            **evidence,
            "created_at_utc": _utc(),
            "scientific_result": False,
        },
    )


def _load_final_marker(path, launched):
    value = _read_canonical(path)
    if (
        any(value.get(key) != launched[key] for key in ("launch_id", "attempt_id", "authorization_id"))
        or value.get("scientific_result") is not False
    ):
        raise ValueError("invalid final marker")
    return value


def _completed_terminal(path, launched, ownership, final):
    return _new(
        path,
        {
            "schema_version": "m6a-v2-ownership-terminal-v1",
            "launch_id": launched["launch_id"],
            "attempt_id": launched["attempt_id"],
            "authorization_id": launched["authorization_id"],
            "owner_identity": ownership["launcher_identity"],
            "ownership_sha256": ownership["sha256"],
            "final_marker_sha256": final["sha256"],
            "state": "completed",
            "completed_at_utc": _utc(),
        },
    )


def write_completed_ownership_terminal(path, launched, ownership, final):
    """Public immutable writer shared by production and research finalizers."""
    return _completed_terminal(path, launched, ownership, final)


def write_failed_process_terminal(path, launched, ownership, process):
    """Persist an immutable terminal failure after a research process ran once."""
    if (
        launched.get("execution_mode") != "research"
        or process.get("sha256") != launched.get("process_evidence_digest")
        or (
            process.get("return_code") == 0
            and process.get("timed_out") is False
            and process.get("termination_state") == "exited"
        )
    ):
        raise ValueError("process is not an eligible research failure")
    return _new(
        path,
        {
            "schema_version": "m6a-v2-ownership-terminal-v1",
            "launch_id": launched["launch_id"],
            "attempt_id": launched["attempt_id"],
            "authorization_id": launched["authorization_id"],
            "owner_identity": ownership["launcher_identity"],
            "ownership_sha256": ownership["sha256"],
            "process_sha256": process["sha256"],
            "return_code": process["return_code"],
            "timed_out": process["timed_out"],
            "termination_state": process["termination_state"],
            "state": "failed_process",
            "launch_performed": True,
            "authorization_consumed": False,
            "scientific_result": False,
            "completed_at_utc": _utc(),
        },
    )


def load_ownership_terminal(path, *, ownership=None):
    value = _read_canonical(path)
    if value.get("schema_version") != "m6a-v2-ownership-terminal-v1" or value.get("state") not in {
        "completed",
        "failed_process",
        "retired_pre_spawn",
    }:
        raise ValueError("invalid ownership terminal")
    if ownership is not None and (
        value.get("launch_id") != ownership["launch_id"]
        or value.get("attempt_id") != ownership["attempt_id"]
        or value.get("authorization_id") != ownership["authorization_id"]
        or value.get("ownership_sha256") != ownership["sha256"]
        or value.get("owner_identity") != ownership["launcher_identity"]
    ):
        raise ValueError("ownership terminal binding")
    if value["state"] == "retired_pre_spawn" and (
        value.get("reason") != "package_head_superseded_before_launch"
        or value.get("launch_performed") is not False
        or value.get("authorization_consumed") is not False
        or value.get("scientific_result") is not False
    ):
        raise ValueError("invalid pre-spawn retirement semantics")
    if value["state"] == "failed_process" and (
        value.get("launch_performed") is not True
        or value.get("authorization_consumed") is not False
        or value.get("scientific_result") is not False
        or not isinstance(value.get("return_code"), int)
        or not isinstance(value.get("timed_out"), bool)
        or not value.get("termination_state")
        or not value.get("process_sha256")
        or (
            value["return_code"] == 0
            and value["timed_out"] is False
            and value["termination_state"] == "exited"
        )
    ):
        raise ValueError("invalid failed-process terminal semantics")
    return value


def retire_pre_spawn_attempt(
    package_path,
    *,
    current_head,
    reason="package_head_superseded_before_launch",
):
    """Retire a legacy, unlaunched owned root without fabricating an owned context."""
    from scripts.m6a_v2_prepared_launch import load_prepared_launch_package_for_audit

    if reason != "package_head_superseded_before_launch":
        raise ValueError("unsupported retirement reason")
    package = load_prepared_launch_package_for_audit(package_path)
    if package["head"] == current_head:
        raise ValueError("current-HEAD attempt is not eligible for superseded-package retirement")
    root = attempt_root(package["launch_id"], package["attempt_id"])
    if not root.is_dir() or str(root) != package["prospective_attempt_root"]:
        raise ValueError("retirement requires the authoritative attempt root")
    ownership = load_ownership(root / OWNER, root)
    expected = {
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "scene": package["scene_id"],
        "seed": package["seed"],
        "launch_spec_sha256": package["launch_spec_sha256"],
    }
    if any(ownership.get(key) != value for key, value in expected.items()):
        raise ValueError("legacy package/ownership binding")
    paths = attempt_path_plan(
        package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
    )["artifacts"]
    forbidden = set(paths) - {"ownership_marker", "ownership_terminal"}
    if any(Path(paths[key]).exists() for key in forbidden):
        raise ValueError("attempt is not an evidence-free pre-spawn root")
    if set(root.iterdir()) != {root / OWNER}:
        raise ValueError("unexpected attempt-root content blocks retirement")
    terminal_path = Path(paths["ownership_terminal"])
    terminal = _new(
        terminal_path,
        {
            "schema_version": "m6a-v2-ownership-terminal-v1",
            "launch_id": package["launch_id"],
            "attempt_id": package["attempt_id"],
            "identity_id": package["identity_id"],
            "authorization_id": ownership["authorization_id"],
            "owner_identity": ownership["launcher_identity"],
            "ownership_sha256": ownership["sha256"],
            "package_path": str(Path(package_path).resolve()),
            "package_digest": package["package_sha256"],
            "package_head": package["head"],
            "current_head": current_head,
            "state": "retired_pre_spawn",
            "reason": reason,
            "retired_at_utc": _utc(),
            "launch_performed": False,
            "authorization_consumed": False,
            "scientific_result": False,
        },
    )
    return load_ownership_terminal(terminal_path, ownership=ownership)


def finalize_launched_attempt(launched_attempt_context, completion_spec, *, mode="test", completion_runner=None):
    """Close a launched attempt only after reloading launch evidence; never launches a process."""
    value = launched_attempt_context
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "m6a-v2-launched-attempt-context-v1"
        or value.get("canonical_digest")
        != digest({key: item for key, item in value.items() if key != "canonical_digest"})
        or value.get("execution_mode") != mode
    ):
        raise ValueError("invalid launched attempt context")
    root = Path(value["attempt_root"]).resolve()
    ownership = load_ownership(root / OWNER, root, owner_identity=value["owner_identity"])
    identity = {
        "launch_id": value["launch_id"],
        "attempt_id": value["attempt_id"],
        "identity_id": value["identity_id"],
        "scene_id": ownership["scene"],
        "seed": ownership["seed"],
    }
    paths = attempt_path_plan(
        value["launch_id"], value["attempt_id"], value["identity_id"], ownership["scene"], ownership["seed"]
    )["artifacts"]
    consumption = load_consumption(paths["consumption_record"], value)
    from scripts.m6a_v2_runtime_evidence import load_process_evidence

    process = load_process_evidence(paths["process_evidence"], identity)
    if (
        process["sha256"] != value["process_evidence_digest"]
        or consumption["sha256"] != value["consumption_digest"]
    ):
        raise ValueError("launched evidence mismatch")
    final_path = Path(paths["final_marker"])
    terminal_path = Path(paths["ownership_terminal"])
    if final_path.exists():
        final = _load_final_marker(final_path, value)
        if terminal_path.exists():
            terminal = load_ownership_terminal(terminal_path, ownership=ownership)
            if terminal["state"] != "completed" or terminal.get("final_marker_sha256") != final["sha256"]:
                raise ValueError("final marker/terminal mismatch")
            return {
                "schema_version": "m6a-v2-finalized-attempt-result-v1",
                "idempotent": True,
                "final_marker": final,
                "terminal": terminal,
            }
        terminal = _completed_terminal(terminal_path, value, ownership, final)
        return {
            "schema_version": "m6a-v2-finalized-attempt-result-v1",
            "idempotent": True,
            "final_marker": final,
            "terminal": terminal,
        }
    if terminal_path.exists():
        terminal = load_ownership_terminal(terminal_path, ownership=ownership)
        raise ValueError(f"terminal state without success final marker: {terminal['state']}")
    if process["return_code"] != 0 or process["timed_out"] or process["termination_state"] != "exited":
        raise RuntimeError("process not eligible for completion")
    if completion_runner is None:
        from scripts.m6a_v2_pilot_completion import process_completed_pilot_launch

        completion_runner = process_completed_pilot_launch
    result = completion_runner(
        completion_spec,
        {"started": True, "timed_out": False, "interrupted": False},
        owned_output_root=root,
    )
    evidence = result.get("final_evidence") if isinstance(result, dict) else None
    if not result.get("integration_valid") or not isinstance(evidence, dict):
        raise ValueError("completion did not provide validated final evidence")
    evidence = {
        **evidence,
        "launch_id": value["launch_id"],
        "attempt_id": value["attempt_id"],
        "authorization_id": value["authorization_id"],
        "ownership_sha256": ownership["sha256"],
        "consumption_sha256": consumption["sha256"],
        "process_sha256": process["sha256"],
        "joint_pass": True,
    }
    final = write_final_marker(root, evidence)
    final = _load_final_marker(final_path, value)
    terminal = _completed_terminal(terminal_path, value, ownership, final)
    finalized = {
        "schema_version": "m6a-v2-finalized-attempt-result-v1",
        "launch_id": value["launch_id"],
        "attempt_id": value["attempt_id"],
        "identity_id": value["identity_id"],
        "authorization_id": value["authorization_id"],
        "attempt_root": str(root),
        "owner_identity": ownership["launcher_identity"],
        "consumption_digest": consumption["sha256"],
        "process_evidence_digest": process["sha256"],
        "runtime_manifest_digest": evidence["runtime_sha256"],
        "aggregate_validation_digest": evidence["b5_sha256"],
        "joint_report_digest": evidence["joint_validator_sha256"],
        "final_marker_digest": final["sha256"],
        "final_outcome": "success",
        "completed_at_utc": terminal["completed_at_utc"],
        "execution_mode": mode,
    }
    finalized["canonical_digest"] = digest(finalized)
    return finalized
