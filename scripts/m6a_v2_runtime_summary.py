"""Fail-closed M6-A v2 controller lifecycle and trusted runtime summaries.

The module contains no Webots import.  Controller entry injects Supervisor and
device/episode hooks; unit tests exercise those hooks with ordinary fakes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_scene_wiring import BASE_WORLD_SHA256, SceneInitializationEvidence, initialize_v2_scene_before_motion
from scripts.run_m6a_one_identity import load_v2_runtime_config
from scripts.m6a_v2_runtime_evidence import persist_runtime_diagnostic, load_runtime_diagnostic, persist_runtime_manifest, load_runtime_manifest


SUMMARY_SCHEMA = "m6a-v2-episode-runtime-summary-v1"
FAILURE_SCHEMA = "m6a-v2-episode-runtime-failure-v1"
METHODS = ("command_conditioned_risk_roi", "state_only_risk_roi")


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


def _safe_path(path: Path) -> None:
    resolved = path.resolve()
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
    if (summary["protocol_version"] != expected_runtime_config["protocol_version"] or summary["v2_manifest_sha256"] != expected_runtime_config["v2_manifest_sha256"] or summary["v2_lock_sha256"] != expected_runtime_config["v2_lock_sha256"] or summary["source_record_sha256"] != expected_runtime_config["source_record_sha256"] or identity != {"split": "pilot", "scene": expected_runtime_config["scene"], "episode_id": expected_runtime_config["episode_id"], "seed": expected_runtime_config["seed"]} or summary["controller"] != expected_runtime_config["controller"] or summary["base_world"] != {"path": expected_runtime_config["source_world"], "sha256": expected_runtime_config["source_world_sha256"]} or summary["base_world"]["sha256"].upper() != BASE_WORLD_SHA256 or summary["schedule_sha256"] != expected_runtime_config["schedule_sha256"] or summary["projection_config_sha256"] != expected_runtime_config["projection_config_sha256"]):
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


def persist_episode_runtime_summary(summary: dict, summary_path: str | Path, status_path: str | Path, expected_runtime_config: dict) -> None:
    summary_path, status_path = Path(summary_path), Path(status_path)
    _safe_path(summary_path); _safe_path(status_path)
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


def write_runtime_failure_status(status_path: str | Path, lifecycle: Lifecycle, error: Exception) -> None:
    path = Path(status_path)
    _safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": FAILURE_SCHEMA, "success": False, "lifecycle_final_state": lifecycle.state.value if lifecycle.state else LifecycleState.FAILED.value, "error_type": type(error).__name__}
    path.write_bytes(_canonical(payload))


def run_v2_controller_lifecycle(runtime_config_path: str | Path, *, supervisor_factory, devices_initializer, episode_runner, summary_path: str | Path, status_path: str | Path, diagnostic_path: str | Path | None = None, runtime_manifest_path: str | Path | None = None, manifest_identity: dict | None = None) -> tuple[int, Lifecycle]:
    lifecycle = Lifecycle()
    try:
        runtime_config = json.loads(Path(runtime_config_path).read_text(encoding="utf-8")); load_v2_runtime_config(runtime_config); lifecycle.transition(LifecycleState.CONFIG_VALIDATED)
        supervisor = supervisor_factory(); scene = initialize_v2_scene_before_motion(runtime_config, supervisor); lifecycle.transition(LifecycleState.SCENE_INITIALIZED)
        if runtime_config["robot_def"] != "ROBOT": raise ValueError("unexpected robot DEF")
        devices_initializer(supervisor, runtime_config); lifecycle.transition(LifecycleState.DEVICES_READY)
        lifecycle.transition(LifecycleState.EPISODE_RUNNING); snapshots = episode_runner(supervisor, runtime_config); lifecycle.transition(LifecycleState.EPISODE_COMPLETED)
        summary = build_episode_runtime_summary(runtime_config, scene, snapshots, lifecycle); summary["lifecycle_final_state"] = LifecycleState.SUMMARY_COMMITTED.value; summary["summary_sha256"] = digest({key: value for key, value in summary.items() if key != "summary_sha256"}); persist_episode_runtime_summary(summary, summary_path, status_path, runtime_config)
        if (diagnostic_path is None) != (runtime_manifest_path is None): raise ValueError("runtime diagnostic and manifest must be paired")
        if runtime_manifest_path is not None:
            identity = manifest_identity or {"launch_id":"runtime-local","attempt_id":"runtime-local","identity_id":runtime_config["episode_id"],"scene_id":runtime_config["scene"],"seed":runtime_config["seed"]}
            root = Path(summary_path).parent.resolve()
            if Path(status_path).parent.resolve() != root or Path(diagnostic_path).parent.resolve() != root or Path(runtime_manifest_path).parent.resolve() != root: raise ValueError("runtime evidence must share one authoritative root")
            persist_runtime_diagnostic(diagnostic_path,identity,"success",[]);load_runtime_diagnostic(diagnostic_path,identity,root)
            persist_runtime_manifest(runtime_manifest_path,identity,root,runtime_config=runtime_config,summary_path=summary_path,status_path=status_path,diagnostic_path=diagnostic_path)
            load_runtime_manifest(runtime_manifest_path,identity,root,runtime_config)
        lifecycle.transition(LifecycleState.SUMMARY_COMMITTED)
        return 0, lifecycle
    except Exception as error:
        lifecycle.fail()
        try: write_runtime_failure_status(status_path, lifecycle, error)
        except Exception: pass
        return 1, lifecycle
