"""Minimal local research runner for one frozen M6-A v2 prepared package.

This module deliberately has no production authorization, signature, receipt,
or consumption dependency.  It reuses the prepared-package, ownership,
process-evidence, scientific-completion, and final-marker contracts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_execution_safety import (
    CONTROL_ROOT,
    FINAL,
    OWNER,
    OWNERSHIP_TERMINAL,
    _load_final_marker,
    _new,
    _read_canonical,
    acquire_ownership,
    attempt_path_plan,
    load_ownership,
    load_ownership_terminal,
    write_completed_ownership_terminal,
    write_failed_process_terminal,
    write_final_marker,
)
from scripts.m6a_v2_host_wrapper import ProductionOwnedProcessRunner
from scripts.m6a_v2_prepared_launch import (
    load_prepared_launch_package,
    load_prepared_launch_package_for_audit,
)
from scripts.m6a_v2_runtime_evidence import load_process_evidence, persist_process_evidence


RESEARCH_CONTEXT = ".m6a_v2_research_context.json"
RESEARCH_CLAIM = ".m6a_v2_research_launch_claim.json"
RESEARCH_OWNER = "m6a-v2-research-host"
RESEARCH_BRIDGE_ALLOWED_PATHS = frozenset(
    {
        "scripts/m6a_v2_research_pilot.py",
        "scripts/m6a_v2_execution_safety.py",
        "tests/test_m6a_v2_research_pilot.py",
        "docs/m6a_v2_research_pilot_runbook.md",
        "docs/progress.md",
        "docs/decisions.md",
    }
)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git(repository_root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    errors = []
    for executable in ("git", r"C:\Program Files\Git\cmd\git.exe"):
        try:
            return subprocess.run(
                [executable, *arguments],
                cwd=repository_root,
                check=check,
                capture_output=True,
                text=True,
                shell=False,
            )
        except (FileNotFoundError, OSError) as exc:
            errors.append(f"{executable}: {exc}")
    raise RuntimeError("unable to run Git: " + "; ".join(errors))


def build_research_head_binding(package_head: str, package_branch: str, *, repository_root=PROJECT_ROOT):
    """Bind a package to HEAD or to this runner's single non-scientific commit.

    The one-commit bridge is intentionally narrow: it lets a package prepared
    immediately before this runner was added remain usable without rewriting
    any frozen package artifact.
    """
    root = Path(repository_root).resolve()
    current_head = _git(root, "rev-parse", "HEAD").stdout.strip().lower()
    current_branch = _git(root, "branch", "--show-current").stdout.strip()
    tracked = _git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if tracked:
        raise ValueError("tracked working tree must be clean")
    if current_branch != package_branch:
        raise ValueError("prepared package branch mismatch")
    if current_head == package_head:
        mode, changed = "exact", []
    else:
        ancestor = _git(root, "merge-base", "--is-ancestor", package_head, current_head, check=False)
        count = _git(root, "rev-list", "--count", f"{package_head}..{current_head}").stdout.strip()
        changed = [
            line.replace("\\", "/")
            for line in _git(root, "diff", "--name-only", f"{package_head}..{current_head}").stdout.splitlines()
            if line.strip()
        ]
        if ancestor.returncode != 0 or count != "1" or not changed:
            raise ValueError("prepared package is not bound to current HEAD")
        unexpected = sorted(set(changed) - RESEARCH_BRIDGE_ALLOWED_PATHS)
        if unexpected:
            raise ValueError("HEAD bridge changes non-research files: " + ", ".join(unexpected))
        mode = "single_research_runner_commit"
    value = {
        "schema_version": "m6a-v2-research-head-binding-v1",
        "package_head": package_head,
        "execution_head": current_head,
        "branch": current_branch,
        "binding_mode": mode,
        "changed_paths": sorted(changed),
        "allowed_paths": sorted(RESEARCH_BRIDGE_ALLOWED_PATHS),
    }
    value["binding_digest"] = digest(value)
    return value


def _identity(package):
    return {
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "scene_id": package["scene_id"],
        "seed": package["seed"],
    }


def _paths(package):
    return attempt_path_plan(
        package["launch_id"],
        package["attempt_id"],
        package["identity_id"],
        package["scene_id"],
        package["seed"],
    )["artifacts"]


def _research_authority(package, binding):
    declaration = {
        "schema_version": "m6a-v2-local-research-authority-v1",
        **_identity(package),
        "package_sha256": package["package_sha256"],
        "launch_spec_sha256": package["launch_spec_sha256"],
        "runtime_config_sha256": package["runtime_config_sha256"],
        "head_binding_digest": binding["binding_digest"],
        "execution_mode": "research",
        "production_authorization_used": False,
        "production_consumption_allowed": False,
    }
    authority_digest = digest(declaration)
    return {
        **declaration,
        "authorization_id": "research-" + authority_digest[:32],
        "authorization_sha256": authority_digest,
    }


def _materialize_research_context(package_path, package, binding):
    # This loader is the authoritative pre-root package and input validator.
    load_prepared_launch_package(package_path, expected_head=package["head"])
    root = Path(package["prospective_attempt_root"]).resolve()
    authority = _research_authority(package, binding)
    ownership = acquire_ownership(root, authority, launcher_identity=RESEARCH_OWNER)
    context_path = root / RESEARCH_CONTEXT
    payload = {
        "schema_version": "m6a-v2-research-attempt-context-v1",
        "package_path": str(Path(package_path).resolve()),
        "package_sha256": package["package_sha256"],
        "package_head": package["head"],
        "execution_head": binding["execution_head"],
        "head_binding": binding,
        **_identity(package),
        "authorization_id": authority["authorization_id"],
        "research_authority_sha256": authority["authorization_sha256"],
        "attempt_root": str(root),
        "ownership_path": str((root / OWNER).resolve()),
        "ownership_sha256": ownership["sha256"],
        "execution_mode": "research",
        "production_authorization_used": False,
        "production_consumption_allowed": False,
        "created_at_utc": _utc(),
    }
    try:
        _new(context_path, payload)
    except Exception:
        if (root / OWNER).is_file():
            (root / OWNER).unlink()
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()
        raise
    return _load_research_context(context_path, package_path, package, binding)


def _load_research_context(path, package_path, package, binding):
    value = _read_canonical(path)
    root = Path(package["prospective_attempt_root"]).resolve()
    ownership = load_ownership(root / OWNER, root, owner_identity=RESEARCH_OWNER)
    expected = {
        "schema_version": "m6a-v2-research-attempt-context-v1",
        "package_path": str(Path(package_path).resolve()),
        "package_sha256": package["package_sha256"],
        "package_head": package["head"],
        "execution_head": binding["execution_head"],
        "head_binding": binding,
        **_identity(package),
        "authorization_id": ownership["authorization_id"],
        "research_authority_sha256": ownership["authorization_sha256"],
        "attempt_root": str(root),
        "ownership_path": str((root / OWNER).resolve()),
        "ownership_sha256": ownership["sha256"],
        "execution_mode": "research",
        "production_authorization_used": False,
        "production_consumption_allowed": False,
    }
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("invalid research attempt context binding")
    if load_prepared_launch_package_for_audit(package_path)["package_sha256"] != package["package_sha256"]:
        raise ValueError("research context package mismatch")
    return value, ownership


def _load_claim(path, context, ownership):
    claim = _read_canonical(path)
    expected = {
        "schema_version": "m6a-v2-research-launch-claim-v1",
        "launch_id": context["launch_id"],
        "attempt_id": context["attempt_id"],
        "identity_id": context["identity_id"],
        "authorization_id": context["authorization_id"],
        "research_context_sha256": context["sha256"],
        "ownership_sha256": ownership["sha256"],
        "package_sha256": context["package_sha256"],
        "head_binding_digest": context["head_binding"]["binding_digest"],
        "execution_mode": "research",
        "at_most_once": True,
        "automatic_retry_allowed": False,
        "production_authorization_used": False,
        "production_consumption_allowed": False,
    }
    if any(claim.get(key) != item for key, item in expected.items()):
        raise ValueError("invalid research launch claim")
    return claim


def _new_claim(path, context, ownership):
    return _new(
        path,
        {
            "schema_version": "m6a-v2-research-launch-claim-v1",
            "launch_id": context["launch_id"],
            "attempt_id": context["attempt_id"],
            "identity_id": context["identity_id"],
            "authorization_id": context["authorization_id"],
            "research_context_sha256": context["sha256"],
            "ownership_sha256": ownership["sha256"],
            "package_sha256": context["package_sha256"],
            "head_binding_digest": context["head_binding"]["binding_digest"],
            "execution_mode": "research",
            "claimed_at_utc": _utc(),
            "at_most_once": True,
            "automatic_retry_allowed": False,
            "production_authorization_used": False,
            "production_consumption_allowed": False,
        },
    )


def _launched(context, ownership, claim, process, root):
    value = {
        "schema_version": "m6a-v2-launched-attempt-context-v1",
        "launch_id": context["launch_id"],
        "attempt_id": context["attempt_id"],
        "identity_id": context["identity_id"],
        "authorization_id": context["authorization_id"],
        "owner_identity": ownership["launcher_identity"],
        "attempt_root": str(root),
        "ownership_digest": ownership["sha256"],
        "research_launch_claim_digest": claim["sha256"],
        "process_evidence_path": str((root / "host_process_result.json").resolve()),
        "process_evidence_digest": process["sha256"],
        "launch_performed": True,
        "process_outcome": {
            "return_code": process["return_code"],
            "timed_out": process["timed_out"],
            "termination_state": process["termination_state"],
        },
        "started_at_utc": process["started_at_utc"],
        "ended_at_utc": process["ended_at_utc"],
        "execution_mode": "research",
    }
    value["canonical_digest"] = digest(value)
    return value


def _validate_research_final(final, launched, ownership, claim, process):
    if (
        final.get("execution_mode") != "research"
        or final.get("ownership_sha256") != ownership["sha256"]
        or final.get("research_launch_claim_sha256") != claim["sha256"]
        or final.get("process_sha256") != process["sha256"]
        or "consumption_sha256" in final
        or final.get("joint_pass") is not True
    ):
        raise ValueError("invalid research final marker binding")
    return final


def run_research_pilot(
    package_path,
    *,
    confirm_attempt,
    repository_root=PROJECT_ROOT,
    process_runner=None,
    completion_runner=None,
    require_authoritative_path=True,
):
    """Run or recover one research attempt; the process can be claimed once."""
    package_path = Path(package_path).resolve()
    package = load_prepared_launch_package_for_audit(package_path)
    if confirm_attempt != package["attempt_id"]:
        raise ValueError("explicit attempt confirmation mismatch")
    if require_authoritative_path:
        expected = (CONTROL_ROOT / "prepared" / package["attempt_id"] / "package.json").resolve()
        if package_path != expected:
            raise ValueError("non-authoritative prepared package path")
    binding = build_research_head_binding(package["head"], package["branch"], repository_root=repository_root)
    root = Path(package["prospective_attempt_root"]).resolve()
    paths = _paths(package)
    context_path, claim_path = root / RESEARCH_CONTEXT, root / RESEARCH_CLAIM
    if root.exists():
        if not context_path.is_file():
            raise ValueError("existing attempt root is not a research-owned attempt")
        context, ownership = _load_research_context(context_path, package_path, package, binding)
    else:
        context, ownership = _materialize_research_context(package_path, package, binding)

    consumption_path = Path(paths["consumption_record"])
    if consumption_path.exists():
        raise ValueError("production consumption evidence is forbidden in research mode")
    process_path = Path(paths["process_evidence"])
    terminal_path = Path(paths["ownership_terminal"])
    final_path = Path(paths["final_marker"])
    identity = _identity(package)

    if terminal_path.exists():
        terminal = load_ownership_terminal(terminal_path, ownership=ownership)
        if terminal["state"] == "failed_process":
            process = load_process_evidence(process_path, identity)
            if terminal["process_sha256"] != process["sha256"]:
                raise ValueError("failed terminal/process mismatch")
            return {"state": "process_failed", "idempotent": True, "process": process, "terminal": terminal}
        if terminal["state"] == "completed":
            claim = _load_claim(claim_path, context, ownership)
            process = load_process_evidence(process_path, identity)
            launched = _launched(context, ownership, claim, process, root)
            final = _validate_research_final(
                _load_final_marker(final_path, launched), launched, ownership, claim, process
            )
            if terminal.get("final_marker_sha256") != final["sha256"]:
                raise ValueError("completed terminal/final mismatch")
            return {"state": "already_finalized", "idempotent": True, "final_marker": final, "terminal": terminal}
        raise ValueError("unsupported research terminal state")
    if final_path.exists():
        claim = _load_claim(claim_path, context, ownership)
        process = load_process_evidence(process_path, identity)
        launched = _launched(context, ownership, claim, process, root)
        final = _validate_research_final(
            _load_final_marker(final_path, launched), launched, ownership, claim, process
        )
        terminal = write_completed_ownership_terminal(terminal_path, launched, ownership, final)
        return {"state": "finalized", "idempotent": True, "final_marker": final, "terminal": terminal}

    if claim_path.exists():
        claim = _load_claim(claim_path, context, ownership)
        if not process_path.exists():
            raise RuntimeError("research launch was claimed but process evidence is incomplete; retry forbidden")
        process = load_process_evidence(process_path, identity)
        runner_invoked = False
    else:
        if process_path.exists() or Path(paths["stdout"]).exists() or Path(paths["stderr"]).exists():
            raise ValueError("process evidence exists without an at-most-once launch claim")
        claim = _new_claim(claim_path, context, ownership)
        runner = process_runner or ProductionOwnedProcessRunner(package_path, repository_head=package["head"])
        result = runner.run(root=root, path_plan=paths, owned_attempt_context=context)
        persist_process_evidence(
            process_path,
            identity,
            result["stdout_path"],
            result["stderr_path"],
            launch_performed=result["launch_performed"],
            process_identity=result["process_identity"],
            timed_out=result["timed_out"],
            termination_state=result["termination_state"],
            started_at_utc=result["started_at_utc"],
            ended_at_utc=result["ended_at_utc"],
            return_code=result["return_code"],
            owner_identity=ownership["launcher_identity"],
            authorization_id=context["authorization_id"],
            execution_mode="research",
            production_authorization_used=False,
            production_consumption_created=False,
        )
        process = load_process_evidence(process_path, identity)
        runner_invoked = True

    launched = _launched(context, ownership, claim, process, root)
    if process["return_code"] != 0 or process["timed_out"] or process["termination_state"] != "exited":
        terminal = write_failed_process_terminal(terminal_path, launched, ownership, process)
        return {"state": "process_failed", "idempotent": not runner_invoked, "process": process, "terminal": terminal}

    if completion_runner is None:
        from scripts.m6a_v2_pilot_completion import process_completed_pilot_launch

        completion_runner = process_completed_pilot_launch
    completion = completion_runner(
        package["launch_spec"],
        {"started": True, "timed_out": False, "interrupted": False},
        owned_output_root=root,
    )
    evidence = completion.get("final_evidence") if isinstance(completion, dict) else None
    if not completion.get("integration_valid") or not isinstance(evidence, dict):
        raise ValueError("completion did not provide validated final evidence")
    final = write_final_marker(
        root,
        {
            **evidence,
            "launch_id": context["launch_id"],
            "attempt_id": context["attempt_id"],
            "authorization_id": context["authorization_id"],
            "ownership_sha256": ownership["sha256"],
            "research_launch_claim_sha256": claim["sha256"],
            "process_sha256": process["sha256"],
            "execution_mode": "research",
            "joint_pass": True,
        },
    )
    final = _validate_research_final(
        _load_final_marker(final_path, launched), launched, ownership, claim, process
    )
    terminal = write_completed_ownership_terminal(terminal_path, launched, ownership, final)
    return {
        "state": "finalized",
        "idempotent": not runner_invoked,
        "runner_invoked": runner_invoked,
        "process": process,
        "final_marker": final,
        "terminal": terminal,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one frozen M6-A v2 local research pilot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="claim, run once, validate, and finalize")
    run.add_argument("--package", required=True)
    run.add_argument("--confirm-attempt", required=True)
    args = parser.parse_args(argv)
    result = run_research_pilot(args.package, confirm_attempt=args.confirm_attempt)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["state"] in {"finalized", "already_finalized"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
