"""Persistent, non-scientific prepared launch packages for the sole M6-A v2 pilot."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import LOCK_PATH, MANIFEST_PATH
from scripts.m6a_v2_execution_safety import (
    CONTROL_ROOT,
    attempt_path_plan,
    attempt_root,
    validate_prospective_root,
)
from scripts.m6a_v2_launch_spec import CONTROLLER_PATH, _sha256, resolve_webots_executable
from scripts.m6a_v2_scene_wiring import materialize_m6a_temporary_world
from scripts.run_m6a_one_identity import build_one_identity_runtime_config, load_v2_runtime_config, materialize_runtime_config


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError("immutable package exists")
    path.write_bytes(_canonical(value))


def current_repository_head(repository_root=PROJECT_ROOT) -> str:
    """Return the exact checked-out commit without mutating repository state."""
    candidates = ("git", r"C:\Program Files\Git\cmd\git.exe")
    errors = []
    for executable in candidates:
        try:
            completed = subprocess.run(
                [executable, "rev-parse", "HEAD"],
                cwd=Path(repository_root),
                check=True,
                capture_output=True,
                text=True,
                shell=False,
            )
            head = completed.stdout.strip().lower()
            if len(head) == 40 and all(character in "0123456789abcdef" for character in head):
                return head
            errors.append(f"{executable}: invalid HEAD")
        except (FileNotFoundError, OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"{executable}: {exc}")
    raise RuntimeError("unable to resolve repository HEAD: " + "; ".join(errors))


def _require_package_head(package: dict, expected_head: str) -> None:
    if not isinstance(expected_head, str) or package.get("head") != expected_head:
        raise ValueError("prepared package HEAD does not match executing repository HEAD")
    if package.get("launch_spec", {}).get("head") != expected_head:
        raise ValueError("launch specification HEAD mismatch")


def build_prepared_launch_package(*, head, branch, attempt_id, episode_id="m6a_pilot_s1_seed600100", package_root=CONTROL_ROOT / "prepared", manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH):
    # Production packages must bind the exact code that creates them. Explicit
    # temporary package roots remain available to isolated tests.
    package_root = Path(package_root).resolve()
    if package_root == (CONTROL_ROOT / "prepared").resolve():
        _require_package_head({"head": head, "launch_spec": {"head": head}}, current_repository_head())

    base = package_root / attempt_id
    if base.exists() or base.is_symlink():
        raise ValueError("unsafe package path")
    provisional = "m6a" + digest(
        {"head": head, "attempt": attempt_id, "identity": episode_id}
    )[:32]
    root = attempt_root(provisional, attempt_id)
    validate_prospective_root(root, launch_id=provisional, attempt_id=attempt_id)
    runtime = build_one_identity_runtime_config(manifest_path, lock_path, output_root=root, episode_id=episode_id)
    paths = attempt_path_plan(provisional, attempt_id, runtime["episode_id"], runtime["scene"], runtime["seed"])
    host_only = {
        "consumption_record",
        "ownership_marker",
        "ownership_terminal",
        "owned_context",
        "stdout",
        "stderr",
        "process_evidence",
        "final_marker",
    }
    runtime["attempt_paths"] = {
        key: value for key, value in paths["artifacts"].items() if key not in host_only
    }
    runtime["config_sha256"] = digest(
        {key: value for key, value in runtime.items() if key != "config_sha256"}
    )
    base.mkdir(parents=True)
    config = materialize_runtime_config(runtime, base / "runtime_config.json")
    world = base / "worlds" / "prepared.wbt"
    controller = base / "controllers" / "m6a_trusted_runtime" / "m6a_trusted_runtime.py"
    world.parent.mkdir()
    controller.parent.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="m6a-package-world-") as directory:
        temporary = materialize_m6a_temporary_world(runtime, Path(directory) / "prepared.wbt")
        shutil.copyfile(temporary.temporary_world_path, world)
    shutil.copyfile(CONTROLLER_PATH, controller)
    executable = resolve_webots_executable()
    spec = {
        "schema_version": "m6a-v2-production-launch-spec-v4",
        "head": head,
        "branch": branch,
        "launch_id": provisional,
        "attempt_id": attempt_id,
        "identity": {
            "episode_id": runtime["episode_id"],
            "scene": runtime["scene"],
            "seed": runtime["seed"],
        },
        "preflight_workspace_root": str(base.resolve()),
        "prospective_attempt_root": str(root),
        "prospective_attempt_path_plan": paths,
        "path_plan": paths,
        "owned_root": str(root),
        "working_directory": str(PROJECT_ROOT.resolve()),
        "runtime_config": {"path": str(config.resolve()), "sha256": _sha256(config)},
        "temporary_world": {"path": str(world.resolve()), "sha256": _sha256(world)},
        "controller": {
            "path": str(controller.resolve()),
            "sha256": _sha256(controller),
            "source_path": str(CONTROLLER_PATH.resolve()),
            "source_sha256": _sha256(CONTROLLER_PATH),
        },
        "webots": executable.__dict__,
        "argv": [executable.path, "--batch", "--mode=fast", "--stdout", "--stderr", str(world.resolve())],
        "environment": {
            "M6A_RUNTIME_CONFIG": str(config.resolve()),
            "PYTHONPATH": str(PROJECT_ROOT.resolve()),
        },
        "summary_path": paths["artifacts"]["runtime_summary"],
        "status_path": paths["artifacts"]["runtime_status"],
        "diagnostic_path": paths["artifacts"]["runtime_diagnostic"],
        "runtime_manifest_path": paths["artifacts"]["runtime_manifest"],
        "aggregate_validation_path": paths["artifacts"]["aggregate_validation"],
        "joint_report_path": paths["artifacts"]["joint_report"],
        "owner_marker": paths["artifacts"]["ownership_marker"],
        "timeout_s": 75,
        "graceful_termination_s": 10,
        "expected": {"episodes": 1, "snapshots": 4, "methods": 2, "budgets": 4, "future_cases": 32},
        "manifest_sha256": runtime["v2_manifest_sha256"],
        "lock_sha256": runtime["v2_lock_sha256"],
        "manifest_authority_version": runtime["manifest_authority_version"],
        "execution_authorized": False,
        "webots_started": False,
    }
    spec["launch_spec_sha256"] = digest(spec)
    package = {
        "schema_version": "m6a-v2-prepared-launch-package-v2",
        "kind": "local-control-evidence-not-runtime-result",
        "head": head,
        "branch": branch,
        "launch_id": provisional,
        "attempt_id": attempt_id,
        "identity_id": runtime["episode_id"],
        "scene_id": runtime["scene"],
        "seed": runtime["seed"],
        "preflight_workspace_root": str(base.resolve()),
        "preflight_report_path": str((base / "fresh_preflight_report.json").resolve()),
        "prospective_attempt_root": str(root),
        "prospective_attempt_path_plan": paths,
        "launch_spec": spec,
        "path_plan": paths,
        "expected_evidence": {
            key: {"path": value, "required": True, "producer": "runtime-or-host"}
            for key, value in paths["artifacts"].items()
        },
        "launch_spec_sha256": spec["launch_spec_sha256"],
        "runtime_config_sha256": spec["runtime_config"]["sha256"],
        "temporary_world_sha256": spec["temporary_world"]["sha256"],
        "controller_sha256": spec["controller"]["sha256"],
        "executable": spec["webots"],
        "argv_sha256": digest(spec["argv"]),
        "manifest_sha256": runtime["v2_manifest_sha256"],
        "lock_sha256": runtime["v2_lock_sha256"],
        "manifest_authority_version": runtime["manifest_authority_version"],
        "planned_output_root": str(root),
        "authorization_generated": False,
        "launch_performed": False,
        "webots_started": False,
        "scientific_result": False,
    }
    package["package_sha256"] = digest(package)
    _write(base / "package.json", package)
    return base / "package.json", package


def load_prepared_launch_package_for_audit(path):
    """Reload immutable package inputs without granting execution authority."""
    path = Path(path).resolve()
    raw = path.read_bytes()
    package = json.loads(raw)
    if raw != _canonical(package) or package.get("package_sha256") != digest(
        {key: value for key, value in package.items() if key != "package_sha256"}
    ):
        raise ValueError("package digest")
    spec = package.get("launch_spec", {})
    if (
        package.get("schema_version") != "m6a-v2-prepared-launch-package-v2"
        or spec.get("schema_version") not in {
            "m6a-v2-production-launch-spec-v3",
            "m6a-v2-production-launch-spec-v4",
        }
        or spec.get("launch_spec_sha256") != digest(
            {key: value for key, value in spec.items() if key != "launch_spec_sha256"}
        )
        or package.get("launch_spec_sha256") != spec.get("launch_spec_sha256")
    ):
        raise ValueError("package/launch specification schema or digest")
    workspace = Path(package.get("preflight_workspace_root", "")).resolve()
    report_path = Path(package.get("preflight_report_path", "")).resolve()
    expected_root = attempt_root(package.get("launch_id"), package.get("attempt_id"))
    if (
        workspace != path.parent
        or not report_path.is_relative_to(workspace)
        or package.get("prospective_attempt_root") != str(expected_root)
        or spec.get("prospective_attempt_root") != str(expected_root)
        or package.get("planned_output_root") != str(expected_root)
        or spec.get("owned_root") != str(expected_root)
        or workspace == expected_root
    ):
        raise ValueError("preflight/attempt boundary")
    identity = spec.get("identity", {})
    if (
        spec.get("launch_id") != package.get("launch_id")
        or spec.get("attempt_id") != package.get("attempt_id")
        or identity.get("episode_id") != package.get("identity_id")
        or identity.get("scene") != package.get("scene_id")
        or identity.get("seed") != package.get("seed")
        or spec.get("branch") != package.get("branch")
        or spec.get("head") != package.get("head")
    ):
        raise ValueError("package identity mismatch")
    artifacts = package.get("path_plan", {}).get("artifacts", {})
    output_fields = {
        "summary_path": "runtime_summary",
        "status_path": "runtime_status",
        "diagnostic_path": "runtime_diagnostic",
        "runtime_manifest_path": "runtime_manifest",
        "aggregate_validation_path": "aggregate_validation",
        "joint_report_path": "joint_report",
        "owner_marker": "ownership_marker",
    }
    if spec.get("schema_version") == "m6a-v2-production-launch-spec-v4":
        expected_project = path.parent
        expected_world = expected_project / "worlds" / "prepared.wbt"
        expected_controller = expected_project / "controllers" / "m6a_trusted_runtime" / "m6a_trusted_runtime.py"
        expected_environment = {
            "M6A_RUNTIME_CONFIG": spec.get("runtime_config", {}).get("path"),
            "PYTHONPATH": str(PROJECT_ROOT.resolve()),
        }
        expected_argv = [
            spec.get("webots", {}).get("path"),
            "--batch",
            "--mode=fast",
            "--stdout",
            "--stderr",
            str(expected_world.resolve()),
        ]
        fixture = (
            spec.get("webots", {}).get("source") == "temporary-harmless-child"
            and Path(tempfile.gettempdir()).resolve() in path.parents
        )
        actual_argv = spec.get("argv")
        argv_valid = actual_argv == expected_argv or (
            fixture
            and isinstance(actual_argv, list)
            and len(actual_argv) == 3
            and actual_argv[0] == spec.get("webots", {}).get("path")
            and actual_argv[1] == "-c"
        )
        if (
            Path(spec.get("temporary_world", {}).get("path", "")).resolve() != expected_world.resolve()
            or Path(spec.get("controller", {}).get("path", "")).resolve() != expected_controller.resolve()
            or spec.get("controller", {}).get("source_path") != str(CONTROLLER_PATH.resolve())
            or spec.get("controller", {}).get("source_sha256") != _sha256(CONTROLLER_PATH)
            or spec.get("environment") != expected_environment
            or not argv_valid
            or any(spec.get(field) != artifacts.get(role) for field, role in output_fields.items())
        ):
            raise ValueError("prepared Webots project or runtime output binding")
    for field in ("runtime_config", "temporary_world", "controller"):
        source = Path(spec[field]["path"])
        if not source.is_file() or _sha256(source) != spec[field]["sha256"]:
            raise ValueError("package input hash")
    runtime = json.loads(Path(spec["runtime_config"]["path"]).read_text(encoding="utf-8"))
    load_v2_runtime_config(runtime)
    authority = runtime.get("manifest_authority_version", "v2")
    if (
        package.get("manifest_authority_version", "v2") != authority
        or spec.get("manifest_authority_version", "v2") != authority
        or package.get("manifest_sha256") != runtime["v2_manifest_sha256"]
        or spec.get("manifest_sha256") != runtime["v2_manifest_sha256"]
        or package.get("lock_sha256") != runtime["v2_lock_sha256"]
        or spec.get("lock_sha256") != runtime["v2_lock_sha256"]
    ):
        raise ValueError("package manifest authority binding")
    executable = Path(spec.get("webots", {}).get("path", ""))
    if not executable.is_file() or _sha256(executable) != spec["webots"].get("executable_sha256"):
        raise ValueError("package executable hash")
    return package


def load_prepared_launch_package(path, *, expected_head=None):
    """Pre-materialization loader: the prospective root and all launch evidence must be absent."""
    package = load_prepared_launch_package_for_audit(path)
    if expected_head is not None:
        _require_package_head(package, expected_head)
    root = validate_prospective_root(
        package["prospective_attempt_root"],
        launch_id=package["launch_id"],
        attempt_id=package["attempt_id"],
    )
    artifacts = attempt_path_plan(
        package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
    )["artifacts"]
    if any(
        Path(artifacts[key]).exists()
        for key in ("ownership_marker", "owned_context", "consumption_record", "process_evidence", "final_marker", "ownership_terminal")
    ):
        raise ValueError("pre-materialization execution evidence exists")
    if root.exists():
        raise ValueError("prospective attempt root exists")
    return package


def load_owned_prepared_launch_package(path, ownership, *, expected_head):
    """Post-materialization loader bound to validated ownership, never an arbitrary existing root."""
    package = load_prepared_launch_package_for_audit(path)
    _require_package_head(package, expected_head)
    root = Path(package["prospective_attempt_root"]).resolve()
    if not root.is_dir() or not isinstance(ownership, dict):
        raise ValueError("owned package requires an existing owned root")
    expected = {
        "launch_id": package["launch_id"],
        "attempt_id": package["attempt_id"],
        "identity_id": package["identity_id"],
        "scene": package["scene_id"],
        "seed": package["seed"],
        "output_root": str(root),
        "state": "owned_pre_spawn",
    }
    if any(ownership.get(key) != value for key, value in expected.items()):
        raise ValueError("package/ownership binding")
    return package
