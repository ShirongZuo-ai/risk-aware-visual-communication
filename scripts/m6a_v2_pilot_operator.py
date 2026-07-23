"""One-shot production launch/recovery operator for an already-owned M6-A v2 attempt."""
from __future__ import annotations

from pathlib import Path

from scripts.m6a_v2_execution_safety import (
    CONTROL_ROOT,
    attempt_path_plan,
    finalize_launched_attempt,
    launch_owned_attempt,
    load_finalized_attempt_result,
    load_owned_attempt_context,
    load_ownership,
    load_ownership_terminal,
    recover_launched_attempt_context,
    retire_pre_spawn_attempt,
)
from scripts.m6a_v2_host_wrapper import ProductionOwnedProcessRunner
from scripts.m6a_v2_prepared_launch import (
    current_repository_head,
    load_prepared_launch_package_for_audit,
)


def authoritative_operator_package_path(package_path, *, prepared_root=None) -> Path:
    """Accept only ``prepared/<attempt-id>/package.json``, never an arbitrary root."""
    prepared_root = Path(prepared_root or (CONTROL_ROOT / "prepared")).resolve()
    path = Path(package_path).resolve()
    if (
        path.name != "package.json"
        or path.parent.parent != prepared_root
        or path.parent.name in {"", ".", ".."}
        or not path.is_file()
        or path.is_symlink()
    ):
        raise ValueError("operator package path is not an authoritative prepared package")
    return path


def build_production_completion_spec(package: dict) -> dict:
    """Map the authoritative package path plan to the existing B5 completion contract."""
    spec = package["launch_spec"]
    artifacts = attempt_path_plan(
        package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
    )["artifacts"]
    return {
        "runtime_config": spec["runtime_config"],
        "summary_path": artifacts["runtime_summary"],
        "runtime_manifest_path": artifacts["runtime_manifest"],
        "aggregate_validation_path": artifacts["aggregate_validation"],
        "joint_report_path": artifacts["joint_report"],
        "owner_marker": artifacts["ownership_marker"],
    }


def run_production_pilot(
    package_path,
    *,
    repository_head=None,
    process_runner=None,
    completion_runner=None,
    prepared_root=None,
) -> dict:
    """Launch once or recover/finalize one already-materialized production attempt."""
    package_path = authoritative_operator_package_path(package_path, prepared_root=prepared_root)
    package = load_prepared_launch_package_for_audit(package_path)
    repository_head = repository_head or current_repository_head()
    if package["head"] != repository_head or package["launch_spec"]["head"] != repository_head:
        raise ValueError("run-pilot rejects a package from a different repository HEAD")
    artifacts = attempt_path_plan(
        package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
    )["artifacts"]
    root = Path(package["prospective_attempt_root"]).resolve()
    ownership = load_ownership(artifacts["ownership_marker"], root)
    owned = load_owned_attempt_context(
        artifacts["owned_context"], expected_head=repository_head, mode="production"
    )
    terminal_path = Path(artifacts["ownership_terminal"])
    final_path = Path(artifacts["final_marker"])
    consumption_path = Path(artifacts["consumption_record"])
    process_path = Path(artifacts["process_evidence"])
    if terminal_path.exists():
        terminal = load_ownership_terminal(terminal_path, ownership=ownership)
        if terminal["state"] != "completed":
            raise ValueError(f"run-pilot rejects terminal state: {terminal['state']}")
        if not final_path.exists():
            raise ValueError("completed terminal is missing its final marker")
        finalized = load_finalized_attempt_result(
            owned, mode="production", repository_head=repository_head
        )
        return {
            "command": "run-pilot",
            "state": "already_finalized",
            "launch_id": package["launch_id"],
            "attempt_id": package["attempt_id"],
            "identity_id": package["identity_id"],
            "runner_invoked": False,
            "authorization_consumed": True,
            "process_evidence_present": True,
            "finalized": True,
            "result": finalized,
        }
    if consumption_path.exists() != process_path.exists():
        raise ValueError("partial launch evidence; automatic retry is forbidden")
    if consumption_path.exists():
        launched = recover_launched_attempt_context(
            owned, mode="production", repository_head=repository_head
        )
        runner_invoked = False
    else:
        if final_path.exists():
            raise ValueError("final marker exists without launch evidence")
        process_runner = process_runner or ProductionOwnedProcessRunner(
            package_path, repository_head=repository_head
        )
        launched = launch_owned_attempt(
            owned, process_runner, mode="production", repository_head=repository_head
        )
        runner_invoked = True
    outcome = launched["process_outcome"]
    if outcome["return_code"] != 0 or outcome["timed_out"] or outcome["termination_state"] != "exited":
        return {
            "command": "run-pilot",
            "state": "process_failed",
            "launch_id": package["launch_id"],
            "attempt_id": package["attempt_id"],
            "identity_id": package["identity_id"],
            "runner_invoked": runner_invoked,
            "authorization_consumed": True,
            "process_evidence_present": True,
            "finalized": False,
            "process_outcome": outcome,
        }
    finalized = finalize_launched_attempt(
        launched,
        build_production_completion_spec(package),
        mode="production",
        completion_runner=completion_runner,
    )
    return {
        "command": "run-pilot",
        "state": "finalized",
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "runner_invoked": runner_invoked,
        "authorization_consumed": True,
        "process_evidence_present": True,
        "finalized": True,
        "result": finalized,
    }


def retire_superseded_pre_spawn_package(package_path, *, repository_head=None, prepared_root=None):
    package_path = authoritative_operator_package_path(package_path, prepared_root=prepared_root)
    repository_head = repository_head or current_repository_head()
    terminal = retire_pre_spawn_attempt(package_path, current_head=repository_head)
    return {
        "command": "retire-pre-spawn",
        "state": terminal["state"],
        "launch_id": terminal["launch_id"],
        "attempt_id": terminal["attempt_id"],
        "reason": terminal["reason"],
        "terminal_digest": terminal["sha256"],
        "launch_performed": False,
        "authorization_consumed": False,
        "scientific_result": False,
    }
