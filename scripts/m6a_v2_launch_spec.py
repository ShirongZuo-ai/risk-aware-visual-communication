"""Preflight-only M6-A v2 host launch specifications; this module never launches Webots."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_scene_wiring import CONTROLLER_NAME, materialize_m6a_temporary_world
from scripts.m6a_v2_runtime_summary import load_and_validate_episode_runtime_summary
from scripts.run_m6a_one_identity import build_one_identity_runtime_config, materialize_runtime_config


WEBOTS_VERSION = "R2025a"
OWNER_NAME = ".m6a_v2_launch_owner.json"
CONTROLLER_PATH = PROJECT_ROOT / "simulator" / "controllers" / "m6a_trusted_runtime" / "m6a_trusted_runtime.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


@dataclass(frozen=True)
class WebotsExecutableEvidence:
    path: str
    version: str
    source: str
    version_evidence_path: str
    version_evidence_sha256: str
    executable_sha256: str
    executable_bytes: int
    executable_mtime_ns: int


def _static_version_evidence(path: Path) -> tuple[str, Path]:
    """Read Webots' installed version record without launching an executable."""
    try:
        install_root = path.resolve().parents[3]
    except IndexError as error:
        raise ValueError("Webots executable has no expected installation layout") from error
    version_path = install_root / "resources" / "version.txt"
    if not version_path.is_file():
        raise ValueError("Webots static version evidence is missing")
    version = version_path.read_text(encoding="utf-8").strip()
    if version != WEBOTS_VERSION:
        raise ValueError("unsupported Webots version")
    return version, version_path


def resolve_webots_executable(explicit_path: str | Path | None = None) -> WebotsExecutableEvidence:
    candidates: list[tuple[Path, str]] = []
    if explicit_path is not None:
        path = Path(explicit_path)
        if not path.is_absolute():
            raise ValueError("explicit Webots executable must be absolute")
        candidates.append((path, "explicit"))
    home = os.environ.get("WEBOTS_HOME")
    if home:
        candidates.append((Path(home) / "msys64" / "mingw64" / "bin" / "webots.exe", "WEBOTS_HOME"))
    candidates.append((Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"), "R2025a-standard"))
    for candidate, source in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            version, version_path = _static_version_evidence(resolved)
            stat = resolved.stat()
            return WebotsExecutableEvidence(
                str(resolved), version, source, str(version_path.resolve()), _sha256(version_path),
                _sha256(resolved), stat.st_size, stat.st_mtime_ns,
            )
    raise FileNotFoundError("Webots R2025a executable was not found")


def _safe_root(root: Path) -> Path:
    resolved = root.resolve(); temporary = Path(tempfile.gettempdir()).resolve()
    if temporary not in resolved.parents or PROJECT_ROOT in resolved.parents or {"m5", "data", "pilot", "formal", "calibration"} & {x.lower() for x in resolved.parts}:
        raise ValueError("preflight root must be an owned system-temporary path")
    return resolved


def _owner(root: Path) -> dict:
    marker = root / OWNER_NAME
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("preflight root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    value = {"schema_version": "m6a-v2-launch-owner-v1", "root": str(root), "owner": "m6a-v2-preflight"}; value["owner_sha256"] = digest(value)
    marker.write_bytes(_canonical(value)); return value


def build_one_identity_launch_spec(v2_manifest_path, v2_lock_path, *, preflight_root, webots_executable=None) -> dict:
    root = _safe_root(Path(preflight_root)); owner = _owner(root)
    runtime = build_one_identity_runtime_config(v2_manifest_path, v2_lock_path, output_root=root / "episode_output")
    config_path = materialize_runtime_config(runtime, root / "runtime_config.json")
    world = materialize_m6a_temporary_world(runtime, root / "m6a_temporary.wbt")
    executable = resolve_webots_executable(webots_executable)
    if not CONTROLLER_PATH.is_file():
        raise FileNotFoundError("trusted controller wrapper is missing")
    spec = {
        "schema_version": "m6a-v2-webots-launch-spec-v1", "protocol_version": runtime["protocol_version"],
        "v2_manifest_sha256": runtime["v2_manifest_sha256"], "v2_lock_sha256": runtime["v2_lock_sha256"], "source_record_sha256": runtime["source_record_sha256"],
        "identity": {"split": runtime["split"], "scene": runtime["scene"], "episode_id": runtime["episode_id"], "seed": runtime["seed"]},
        "webots": asdict(executable), "temporary_world": asdict(world), "controller": {"name": CONTROLLER_NAME, "path": str(CONTROLLER_PATH), "sha256": _sha256(CONTROLLER_PATH)},
        "runtime_config": {"path": str(config_path.resolve()), "sha256": _sha256(config_path)},
        "environment": {"M6A_RUNTIME_CONFIG": str(config_path.resolve())}, "environment_keys": ["M6A_RUNTIME_CONFIG"], "environment_sha256": digest({"M6A_RUNTIME_CONFIG": str(config_path.resolve())}),
        "working_directory": str(PROJECT_ROOT), "summary_path": str(root / "episode_runtime_summary.json"), "status_path": str(root / "episode_runtime_status.json"), "diagnostic_path": str(root / "episode_runtime_failure.json"),
        "argv": [executable.path, "--batch", "--mode=fast", world.temporary_world_path], "timeout_s": 75, "graceful_termination_s": 10, "forced_termination": "terminate-owned-process-only",
        "owned_root": str(root), "owner_marker": str(root / OWNER_NAME), "owner_sha256": owner["owner_sha256"], "expected": {"episodes": 1, "snapshots": 4, "methods": 2, "budgets": 4, "future_cases": 32}, "execution_authorized": False, "webots_started": False,
    }
    spec["launch_spec_sha256"] = digest(spec); validate_launch_spec(spec); return spec


def validate_launch_spec(spec: dict) -> dict:
    if spec.get("launch_spec_sha256") != digest({key: value for key, value in spec.items() if key != "launch_spec_sha256"}):
        raise ValueError("launch spec digest mismatch")
    if spec.get("protocol_version") != "m6a-byte-fair-v2" or spec.get("identity", {}).get("episode_id") != "m6a_pilot_s1_seed600100" or spec.get("identity", {}).get("split") != "pilot" or spec.get("controller", {}).get("name") != CONTROLLER_NAME or spec.get("expected") != {"episodes": 1, "snapshots": 4, "methods": 2, "budgets": 4, "future_cases": 32} or spec.get("execution_authorized") or spec.get("webots_started"):
        raise ValueError("unsafe launch specification")
    root = _safe_root(Path(spec["owned_root"])); marker = Path(spec["owner_marker"])
    if marker != root / OWNER_NAME or not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")).get("owner_sha256") != spec["owner_sha256"]:
        raise ValueError("launch ownership marker mismatch")
    if not isinstance(spec.get("argv"), list) or spec["argv"] != [spec["webots"]["path"], "--batch", "--mode=fast", spec["temporary_world"]["temporary_world_path"]] or spec.get("environment") != {"M6A_RUNTIME_CONFIG": spec["runtime_config"]["path"]}:
        raise ValueError("unsafe argv or environment")
    for key in ("runtime_config", "temporary_world", "controller"):
        path = Path(spec[key]["path"] if key != "temporary_world" else spec[key]["temporary_world_path"])
        if not path.is_file(): raise ValueError(f"missing launch input: {key}")
    if _sha256(Path(spec["runtime_config"]["path"])) != spec["runtime_config"]["sha256"] or _sha256(Path(spec["temporary_world"]["temporary_world_path"])) != spec["temporary_world"]["temporary_world_sha256"] or _sha256(Path(spec["controller"]["path"])) != spec["controller"]["sha256"]:
        raise ValueError("launch input hash mismatch")
    return spec


def validate_one_identity_launch_result(launch_spec: dict, process_result: dict) -> dict:
    validate_launch_spec(launch_spec)
    if not process_result.get("started") or process_result.get("timed_out") or process_result.get("interrupted") or process_result.get("returncode") not in {0, None}:
        raise ValueError("host process did not complete successfully")
    summary_path, status_path = Path(launch_spec["summary_path"]), Path(launch_spec["status_path"])
    if not summary_path.is_file() or not status_path.is_file(): raise ValueError("summary/status missing")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("success") is not True: raise ValueError("controller did not report success")
    runtime = json.loads(Path(launch_spec["runtime_config"]["path"]).read_text(encoding="utf-8"))
    summary = load_and_validate_episode_runtime_summary(summary_path, runtime, require_paths=False)
    if summary["summary_sha256"] != status.get("summary_sha256") or summary["lifecycle_final_state"] != "SUMMARY_COMMITTED" or any(Path(path).resolve().parent.parent != Path(launch_spec["owned_root"]).resolve() for path in summary["snapshot_paths"]):
        raise ValueError("launch result does not belong to this owned preflight root")
    return {"success": True, "summary_sha256": summary["summary_sha256"], "process_returncode": process_result.get("returncode")}


def owned_cleanup_plan(launch_spec: dict) -> tuple[Path, ...]:
    validate_launch_spec(launch_spec)
    root = Path(launch_spec["owned_root"]).resolve()
    return tuple(path for path in (Path(launch_spec["runtime_config"]["path"]), Path(launch_spec["temporary_world"]["temporary_world_path"]), Path(launch_spec["summary_path"]), Path(launch_spec["status_path"]), Path(launch_spec["diagnostic_path"]), Path(launch_spec["owner_marker"])) if root in path.resolve().parents)
