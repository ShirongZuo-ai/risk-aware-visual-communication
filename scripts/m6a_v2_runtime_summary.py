"""Fail-closed M6-A v2 controller lifecycle and trusted runtime summaries.

The module contains no Webots import.  Controller entry injects Supervisor and
device/episode hooks; unit tests exercise those hooks with ordinary fakes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import re
import sys
import tempfile
import traceback

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_scene_wiring import BASE_WORLD_SHA256, SceneInitializationEvidence, initialize_v2_scene_before_motion
from scripts.run_m6a_one_identity import load_v2_runtime_config, validate_runtime_attempt_paths
from scripts.m6a_v2_runtime_evidence import persist_runtime_diagnostic, load_runtime_diagnostic, persist_runtime_manifest, load_runtime_manifest


SUMMARY_SCHEMA = "m6a-v2-episode-runtime-summary-v1"
FAILURE_SCHEMA = "m6a-v2-episode-runtime-failure-v2"
METHODS = ("command_conditioned_risk_roi", "state_only_risk_roi")


class FailureStage(str, Enum):
    CONFIG_LOADING = "CONFIG_LOADING"
    RUNTIME_OUTPUT_PATH_VALIDATION = "RUNTIME_OUTPUT_PATH_VALIDATION"
    SUPERVISOR_INITIALIZATION = "SUPERVISOR_INITIALIZATION"
    SCENE_INITIALIZATION = "SCENE_INITIALIZATION"
    STATE_READER_SETUP = "STATE_READER_SETUP"
    ACTUATOR_SCHEDULE_SETUP = "ACTUATOR_SCHEDULE_SETUP"
    CAMERA_SETUP = "CAMERA_SETUP"
    EPISODE_EXECUTION = "EPISODE_EXECUTION"
    SUMMARY_BUILD = "SUMMARY_BUILD"
    SUMMARY_PERSISTENCE = "SUMMARY_PERSISTENCE"
    RUNTIME_EVIDENCE_PERSISTENCE = "RUNTIME_EVIDENCE_PERSISTENCE"
    LIFECYCLE_COMMIT = "LIFECYCLE_COMMIT"
    CONTROLLED_SHUTDOWN = "CONTROLLED_SHUTDOWN"


class StagedControllerError(Exception):
    """Internal carrier that retains the original exception and precise stage."""

    def __init__(self, stage: FailureStage, original: Exception):
        super().__init__(str(original))
        self.stage = stage
        self.original = original


def run_controller_stage(stage: FailureStage, operation):
    try:
        return operation()
    except StagedControllerError:
        raise
    except Exception as error:
        raise StagedControllerError(stage, error) from error


class LifecycleState(str, Enum):
    CONFIG_VALIDATED = "CONFIG_VALIDATED"
    SCENE_INITIALIZED = "SCENE_INITIALIZED"
    DEVICES_READY = "DEVICES_READY"
    EPISODE_RUNNING = "EPISODE_RUNNING"
    EPISODE_COMPLETED = "EPISODE_COMPLETED"
    SUMMARY_COMMITTED = "SUMMARY_COMMITTED"
    FAILED = "FAILED"


@dataclass
class Lifecycle:
    state: LifecycleState | None = None
    transitions: list[str] = None

    def __post_init__(self):
        if self.transitions is None:
            self.transitions = []

    def transition(self, target: LifecycleState) -> None:
        allowed = {
            None: LifecycleState.CONFIG_VALIDATED,
            LifecycleState.CONFIG_VALIDATED: LifecycleState.SCENE_INITIALIZED,
            LifecycleState.SCENE_INITIALIZED: LifecycleState.DEVICES_READY,
            LifecycleState.DEVICES_READY: LifecycleState.EPISODE_RUNNING,
            LifecycleState.EPISODE_RUNNING: LifecycleState.EPISODE_COMPLETED,
            LifecycleState.EPISODE_COMPLETED: LifecycleState.SUMMARY_COMMITTED,
        }
        if self.state == LifecycleState.FAILED or allowed.get(self.state) != target:
            raise ValueError(f"invalid lifecycle transition {self.state!s}->{target!s}")
        self.state = target
        self.transitions.append(target.value)

    def fail(self) -> None:
        if self.state != LifecycleState.SUMMARY_COMMITTED:
            self.state = LifecycleState.FAILED
            self.transitions.append(LifecycleState.FAILED.value)


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _safe_path(path: Path, *, authoritative_root: Path | None = None) -> None:
    resolved = path.resolve()
    if authoritative_root is not None:
        root = Path(authoritative_root).resolve()
        if (
            not Path(path).is_absolute()
            or resolved.parent != root
            or resolved.exists()
            or resolved.is_symlink()
            or not root.is_dir()
            or root.is_symlink()
        ):
            raise ValueError("runtime evidence path is not a new file in the authoritative root")
        return
    lowered = {part.lower() for part in resolved.parts}
    if resolved.exists() or PROJECT_ROOT in resolved.parents or {"m5", "v1", "pilot", "formal", "calibration", "data"} & lowered:
        raise ValueError("runtime summary path is not a new safe temporary path")


def _scene_evidence_dict(evidence: SceneInitializationEvidence) -> dict:
    data = asdict(evidence)
    if (not data["scene_initialized_before_motion"] or data["actual_future_usage"] != 0 or data["combined_mask_usage"] != 0 or data["frozen_scene_config_sha256"] != data["applied_scene_config_sha256"]):
        raise ValueError("unsafe or mismatched scene initialization evidence")
    return data


def build_episode_runtime_summary(runtime_config: dict, scene_evidence: SceneInitializationEvidence, snapshot_records: list[dict], lifecycle: Lifecycle, *, temporary_world: dict | None = None) -> dict:
    load_v2_runtime_config(runtime_config)
    scene = _scene_evidence_dict(scene_evidence)
    if scene["source_record_sha256"] != runtime_config["source_record_sha256"] or scene["seed"] != runtime_config["seed"]:
        raise ValueError("scene evidence does not match runtime identity")
    expected = runtime_config["snapshots"]
    if len(snapshot_records) != 4 or lifecycle.state != LifecycleState.EPISODE_COMPLETED:
        raise ValueError("episode is incomplete")
    identifiers = [item.get("snapshot_id") for item in snapshot_records]
    times = [item.get("timestamp_s") for item in snapshot_records]
    paths = [item.get("path") for item in snapshot_records]; snapshot_details=[item.get('snapshot_record') for item in snapshot_records]
    methods = tuple(sorted({method for item in snapshot_records for method in item.get("methods", [])}))
    counts = {key: sum(int(item.get(key, 0)) for item in snapshot_records) for key in ("actual_future_usage", "combined_usage", "raw_mask_usage", "fallback", "replacement")}
    if identifiers != [item["snapshot_id"] for item in expected] or times != [item["timestamp_s"] for item in expected] or len(set(identifiers)) != 4 or methods != METHODS or any(counts.values()) or any(not isinstance(path, str) or not path for path in paths) or (any(x is not None for x in snapshot_details) and any(not isinstance(x,dict) or not Path(x.get('raw_rgb_path','')).is_file() or not Path(x.get('metadata_json_path','')).is_file() or not Path(x.get('serialized_snapshot_path','')).is_dir() for x in snapshot_details)):
        raise ValueError("invalid trusted snapshot records")
    payload = {
        "schema_version": SUMMARY_SCHEMA, "protocol_version": runtime_config["protocol_version"],
        "v2_manifest_sha256": runtime_config["v2_manifest_sha256"], "v2_lock_sha256": runtime_config["v2_lock_sha256"],
        "source_record_sha256": runtime_config["source_record_sha256"],
        "identity": {"split": runtime_config["split"], "scene": runtime_config["scene"], "episode_id": runtime_config["episode_id"], "seed": runtime_config["seed"]},
        "controller": runtime_config["controller"], "base_world": {"path": runtime_config["source_world"], "sha256": runtime_config["source_world_sha256"]},
        "temporary_world": temporary_world, "scene_evidence": scene, "schedule_sha256": runtime_config["schedule_sha256"],
        "projection_config_sha256": runtime_config["projection_config_sha256"], "expected_snapshot_count": 4, "actual_snapshot_count": 4,
        "snapshot_ids": identifiers, "snapshot_times_s": times, "snapshot_paths": paths, "method_set": list(methods), **counts,
        "scene_initialized_before_motion": True, "lifecycle_final_state": lifecycle.state.value, "success": True,
    }
    if all(item is not None for item in snapshot_details):
        payload["snapshots"] = snapshot_details
    payload["summary_sha256"] = digest(payload)
    return payload


def validate_episode_runtime_summary(summary: dict, expected_runtime_config: dict, *, require_paths: bool = False) -> dict:
    load_v2_runtime_config(expected_runtime_config)
    allowed = {"schema_version","protocol_version","v2_manifest_sha256","v2_lock_sha256","source_record_sha256","identity","controller","base_world","temporary_world","scene_evidence","schedule_sha256","projection_config_sha256","expected_snapshot_count","actual_snapshot_count","snapshot_ids","snapshot_times_s","snapshot_paths","snapshots","method_set","actual_future_usage","combined_usage","raw_mask_usage","fallback","replacement","scene_initialized_before_motion","lifecycle_final_state","success","summary_sha256"}
    if not (set(summary) == allowed or set(summary) == allowed-{"snapshots"}) or summary.get("schema_version") != SUMMARY_SCHEMA or summary.get("summary_sha256") != digest({key: value for key, value in summary.items() if key != "summary_sha256"}):
        raise ValueError("invalid runtime summary digest or schema")
    identity = summary["identity"]
    expected_identity = {"split": expected_runtime_config["split"], "scene": expected_runtime_config["scene"], "episode_id": expected_runtime_config["episode_id"], "seed": expected_runtime_config["seed"]}
    if (summary["protocol_version"] != expected_runtime_config["protocol_version"] or summary["v2_manifest_sha256"] != expected_runtime_config["v2_manifest_sha256"] or summary["v2_lock_sha256"] != expected_runtime_config["v2_lock_sha256"] or summary["source_record_sha256"] != expected_runtime_config["source_record_sha256"] or identity != expected_identity or summary["controller"] != expected_runtime_config["controller"] or summary["base_world"] != {"path": expected_runtime_config["source_world"], "sha256": expected_runtime_config["source_world_sha256"]} or summary["base_world"]["sha256"].upper() != BASE_WORLD_SHA256 or summary["schedule_sha256"] != expected_runtime_config["schedule_sha256"] or summary["projection_config_sha256"] != expected_runtime_config["projection_config_sha256"]):
        raise ValueError("runtime summary identity mismatch")
    scene = _scene_evidence_dict(SceneInitializationEvidence(**summary["scene_evidence"]))
    if "snapshots" in summary:
        records=summary["snapshots"]
        if len(records)!=4 or [x.get("snapshot_id") for x in records]!=summary["snapshot_ids"] or len({x.get("snapshot_index") for x in records})!=4: raise ValueError("invalid authoritative snapshot records")
        for item in records:
            raw,meta,serial=(Path(item.get(key,"")) for key in ("raw_rgb_path","metadata_json_path","serialized_snapshot_path"))
            if not raw.is_file() or not meta.is_file() or not serial.is_dir() or item.get("scene")!=expected_runtime_config["scene"] or item.get("seed")!=expected_runtime_config["seed"]:raise ValueError("invalid snapshot artifact reference")
    if scene["source_record_sha256"] != expected_runtime_config["source_record_sha256"] or scene["seed"] != expected_runtime_config["seed"] or summary["expected_snapshot_count"] != 4 or summary["actual_snapshot_count"] != 4 or summary["method_set"] != list(METHODS) or summary["snapshot_ids"] != [item["snapshot_id"] for item in expected_runtime_config["snapshots"]] or summary["snapshot_times_s"] != [item["timestamp_s"] for item in expected_runtime_config["snapshots"]] or any(summary[key] != 0 for key in ("actual_future_usage", "combined_usage", "raw_mask_usage", "fallback", "replacement")) or not summary["scene_initialized_before_motion"] or summary["lifecycle_final_state"] not in {LifecycleState.EPISODE_COMPLETED.value, LifecycleState.SUMMARY_COMMITTED.value} or not summary["success"]:
        raise ValueError("runtime summary acceptance conditions failed")
    if require_paths and any(not Path(path).is_dir() for path in summary["snapshot_paths"]):
        raise ValueError("runtime snapshot path missing")
    return summary


def persist_episode_runtime_summary(summary: dict, summary_path: str | Path, status_path: str | Path, expected_runtime_config: dict, *, authoritative_root: Path | None = None) -> None:
    summary_path, status_path = Path(summary_path), Path(status_path)
    _safe_path(summary_path, authoritative_root=authoritative_root); _safe_path(status_path, authoritative_root=authoritative_root)
    if summary_path.parent != status_path.parent:
        raise ValueError("summary and status must share one safe directory")
    validate_episode_runtime_summary(summary, expected_runtime_config)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_tmp, status_tmp = summary_path.with_suffix(summary_path.suffix + ".tmp"), status_path.with_suffix(status_path.suffix + ".tmp")
    try:
        summary_tmp.write_bytes(_canonical(summary)); summary_tmp.replace(summary_path)
        status = {"schema_version": "m6a-v2-runtime-success-status-v1", "summary_sha256": summary["summary_sha256"], "success": True}
        status_tmp.write_bytes(_canonical(status)); status_tmp.replace(status_path)
    except Exception:
        for item in (summary_tmp, status_tmp, summary_path, status_path):
            if item.exists(): item.unlink()
        raise


def load_and_validate_episode_runtime_summary(summary_path: str | Path, expected_runtime_config: dict, *, require_paths: bool = False) -> dict:
    raw = Path(summary_path).read_bytes(); summary = json.loads(raw)
    if raw != _canonical(summary):
        raise ValueError("runtime summary is not canonical JSON")
    return validate_episode_runtime_summary(summary, expected_runtime_config, require_paths=require_paths)


def _redact_failure_message(error: Exception, authoritative_root: Path | None) -> str:
    message = str(error).replace("\r", " ").replace("\n", " ").strip() or "<no message>"
    replacements = {
        str(PROJECT_ROOT.resolve()): "<PROJECT_ROOT>",
        str(Path.home().resolve()): "<HOME>",
        str(Path(tempfile.gettempdir()).resolve()): "<TEMP_ROOT>",
    }
    if authoritative_root is not None:
        replacements[str(Path(authoritative_root).resolve())] = "<ATTEMPT_ROOT>"
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        message = re.sub(re.escape(source), target, message, flags=re.IGNORECASE)
        message = re.sub(re.escape(source.replace("\\", "/")), target, message, flags=re.IGNORECASE)
    return message[:1000]


def _failure_frames(error: Exception) -> list[dict]:
    return [
        {
            "module": Path(frame.filename).stem,
            "file": Path(frame.filename).name,
            "function": frame.name,
            "line": frame.lineno,
        }
        for frame in traceback.extract_tb(error.__traceback__)
    ]


def validate_runtime_failure_status(value: dict) -> dict:
    allowed = {
        "schema_version", "success", "lifecycle_final_state", "failure_stage",
        "last_completed_state", "transitions", "runtime_identity", "exception",
        "producer_identity", "sha256",
    }
    if set(value) != allowed or value.get("schema_version") != FAILURE_SCHEMA or value.get("sha256") != digest({key: item for key, item in value.items() if key != "sha256"}):
        raise ValueError("invalid runtime failure status digest or schema")
    if value.get("success") is not False or value.get("lifecycle_final_state") != LifecycleState.FAILED.value or value.get("failure_stage") not in {stage.value for stage in FailureStage} or value.get("producer_identity") != "m6a_v2_runtime_summary":
        raise ValueError("invalid runtime failure status semantics")
    transitions = value.get("transitions")
    normal = [state.value for state in LifecycleState if state != LifecycleState.FAILED]
    if not isinstance(transitions, list) or not transitions or transitions[-1] != LifecycleState.FAILED.value or transitions[:-1] != normal[:len(transitions) - 1]:
        raise ValueError("invalid runtime failure transition evidence")
    expected_last = transitions[-2] if len(transitions) > 1 else None
    if value.get("last_completed_state") != expected_last:
        raise ValueError("invalid runtime failure completed stage")
    identity = value.get("runtime_identity")
    if identity is not None and (set(identity) != {"scene", "episode_id", "seed"} or not identity["scene"] or not identity["episode_id"] or not isinstance(identity["seed"], int)):
        raise ValueError("invalid runtime failure identity")
    exception = value.get("exception")
    if not isinstance(exception, dict) or set(exception) != {"type", "message", "frames"} or not exception["type"] or not exception["message"] or not isinstance(exception["frames"], list):
        raise ValueError("invalid runtime failure exception")
    for frame in exception["frames"]:
        if set(frame) != {"module", "file", "function", "line"} or not all(frame[key] for key in ("module", "file", "function")) or not isinstance(frame["line"], int) or frame["line"] <= 0 or Path(frame["file"]).name != frame["file"]:
            raise ValueError("invalid runtime failure frame")
    return value


def load_runtime_failure_status(status_path: str | Path) -> dict:
    raw = Path(status_path).read_bytes()
    value = json.loads(raw)
    if raw != _canonical(value):
        raise ValueError("runtime failure status is not canonical JSON")
    return validate_runtime_failure_status(value)


def build_runtime_failure_status(lifecycle: Lifecycle, error: Exception, *, failure_stage: FailureStage, last_completed_state: LifecycleState | None, runtime_config: dict | None = None, authoritative_root: Path | None = None) -> dict:
    if isinstance(error, StagedControllerError):
        failure_stage, error = error.stage, error.original
    identity_values = None if runtime_config is None else {
        "scene": runtime_config.get("scene"),
        "episode_id": runtime_config.get("episode_id"),
        "seed": runtime_config.get("seed"),
    }
    identity = identity_values if identity_values and identity_values["scene"] and identity_values["episode_id"] and isinstance(identity_values["seed"], int) else None
    payload = {
        "schema_version": FAILURE_SCHEMA,
        "success": False,
        "lifecycle_final_state": LifecycleState.FAILED.value,
        "failure_stage": failure_stage.value,
        "last_completed_state": last_completed_state.value if last_completed_state else None,
        "transitions": list(lifecycle.transitions),
        "runtime_identity": identity,
        "exception": {
            "type": type(error).__name__,
            "message": _redact_failure_message(error, authoritative_root),
            "frames": _failure_frames(error),
        },
        "producer_identity": "m6a_v2_runtime_summary",
    }
    payload["sha256"] = digest(payload)
    return validate_runtime_failure_status(payload)


def emit_runtime_failure_status(payload: dict) -> None:
    validate_runtime_failure_status(payload)
    print("M6A_CONTROLLER_FAILURE " + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), file=sys.stderr, flush=True)


def write_runtime_failure_status(status_path: str | Path, lifecycle: Lifecycle, error: Exception, *, failure_stage: FailureStage, last_completed_state: LifecycleState | None, runtime_config: dict | None = None, authoritative_root: Path | None = None) -> dict:
    path = Path(status_path)
    _safe_path(path, authoritative_root=authoritative_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_runtime_failure_status(lifecycle, error, failure_stage=failure_stage, last_completed_state=last_completed_state, runtime_config=runtime_config, authoritative_root=authoritative_root)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(_canonical(payload))
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return load_runtime_failure_status(path)


def run_v2_controller_lifecycle(runtime_config_path: str | Path, *, supervisor_factory, devices_initializer, episode_runner, summary_path: str | Path, status_path: str | Path, diagnostic_path: str | Path | None = None, runtime_manifest_path: str | Path | None = None, manifest_identity: dict | None = None) -> tuple[int, Lifecycle]:
    lifecycle = Lifecycle()
    authoritative_root = None
    runtime_config = None
    failure_stage = FailureStage.CONFIG_LOADING
    try:
        runtime_config = json.loads(Path(runtime_config_path).read_text(encoding="utf-8")); load_v2_runtime_config(runtime_config)
        failure_stage = FailureStage.RUNTIME_OUTPUT_PATH_VALIDATION
        authoritative_root = validate_runtime_attempt_paths(runtime_config)
        if authoritative_root is not None:
            paths = runtime_config["attempt_paths"]
            expected = {
                "runtime_summary": str(Path(summary_path).resolve()),
                "runtime_status": str(Path(status_path).resolve()),
                "runtime_diagnostic": str(Path(diagnostic_path).resolve()) if diagnostic_path is not None else None,
                "runtime_manifest": str(Path(runtime_manifest_path).resolve()) if runtime_manifest_path is not None else None,
            }
            if any(paths[key] != value for key, value in expected.items()):
                raise ValueError("controller output path does not match authoritative runtime configuration")
        lifecycle.transition(LifecycleState.CONFIG_VALIDATED)
        failure_stage = FailureStage.SUPERVISOR_INITIALIZATION
        supervisor = supervisor_factory()
        failure_stage = FailureStage.SCENE_INITIALIZATION
        scene = initialize_v2_scene_before_motion(runtime_config, supervisor); lifecycle.transition(LifecycleState.SCENE_INITIALIZED)
        if runtime_config["robot_def"] != "ROBOT": raise ValueError("unexpected robot DEF")
        failure_stage = FailureStage.STATE_READER_SETUP
        devices_initializer(supervisor, runtime_config); lifecycle.transition(LifecycleState.DEVICES_READY)
        lifecycle.transition(LifecycleState.EPISODE_RUNNING); failure_stage = FailureStage.EPISODE_EXECUTION
        snapshots = episode_runner(supervisor, runtime_config); lifecycle.transition(LifecycleState.EPISODE_COMPLETED)
        failure_stage = FailureStage.SUMMARY_BUILD
        summary = build_episode_runtime_summary(runtime_config, scene, snapshots, lifecycle); summary["lifecycle_final_state"] = LifecycleState.SUMMARY_COMMITTED.value; summary["summary_sha256"] = digest({key: value for key, value in summary.items() if key != "summary_sha256"})
        failure_stage = FailureStage.SUMMARY_PERSISTENCE
        persist_episode_runtime_summary(summary, summary_path, status_path, runtime_config, authoritative_root=authoritative_root)
        if (diagnostic_path is None) != (runtime_manifest_path is None): raise ValueError("runtime diagnostic and manifest must be paired")
        if runtime_manifest_path is not None:
            failure_stage = FailureStage.RUNTIME_EVIDENCE_PERSISTENCE
            identity = manifest_identity or {"launch_id":"runtime-local","attempt_id":"runtime-local","identity_id":runtime_config["episode_id"],"scene_id":runtime_config["scene"],"seed":runtime_config["seed"]}
            root = Path(summary_path).parent.resolve()
            if Path(status_path).parent.resolve() != root or Path(diagnostic_path).parent.resolve() != root or Path(runtime_manifest_path).parent.resolve() != root: raise ValueError("runtime evidence must share one authoritative root")
            persist_runtime_diagnostic(diagnostic_path,identity,"success",[]);load_runtime_diagnostic(diagnostic_path,identity,root)
            persist_runtime_manifest(runtime_manifest_path,identity,root,runtime_config=runtime_config,summary_path=summary_path,status_path=status_path,diagnostic_path=diagnostic_path)
            load_runtime_manifest(runtime_manifest_path,identity,root,runtime_config)
        failure_stage = FailureStage.LIFECYCLE_COMMIT
        lifecycle.transition(LifecycleState.SUMMARY_COMMITTED)
        return 0, lifecycle
    except Exception as error:
        last_completed_state = lifecycle.state
        lifecycle.fail()
        try:
            failure = write_runtime_failure_status(status_path, lifecycle, error, failure_stage=failure_stage, last_completed_state=last_completed_state, runtime_config=runtime_config, authoritative_root=authoritative_root)
        except Exception:
            failure = build_runtime_failure_status(lifecycle, error, failure_stage=failure_stage, last_completed_state=last_completed_state, runtime_config=runtime_config, authoritative_root=authoritative_root)
        emit_runtime_failure_status(failure)
        return 1, lifecycle
