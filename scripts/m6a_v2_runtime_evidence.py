"""Canonical, reloadable M6-A v2 runtime evidence; no Webots import or launch."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from scripts.m6a_trusted_artifacts import digest


RUNTIME_MANIFEST_SCHEMA = "m6a-v2-runtime-artifact-manifest-v2"
SNAPSHOT_RECORD_SCHEMA = "m6a-v2-authoritative-snapshot-record-v1"
RAW_METADATA_SCHEMA = "m6a-v2-raw-snapshot-metadata-v1"
RAW_METADATA_SCHEMA_V2 = "m6a-v2-raw-snapshot-metadata-v2"


def _b(value): return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _finite(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def persist(path, payload):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): raise FileExistsError("immutable evidence")
    value = dict(payload); value["sha256"] = digest(value); path.write_bytes(_b(value)); return value


def load(path, schema, identity):
    raw = Path(path).read_bytes(); value = json.loads(raw)
    if raw != _b(value) or value.get("schema_version") != schema or value.get("sha256") != digest({k: v for k, v in value.items() if k != "sha256"}) or value.get("identity") != identity:
        raise ValueError("invalid evidence")
    return value


def _under(path, root, *, directory=False):
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("symlink/reparse artifact")
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or (not resolved.is_dir() if directory else not resolved.is_file()):
        raise ValueError("unsafe artifact")
    return resolved


def file_entry(role, path, root, **extra):
    path = _under(path, root)
    return {"role": role, "path": str(path), "relative_path": path.relative_to(Path(root).resolve()).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path), **extra}


def _tree_entries(directory, root):
    directory = _under(directory, root, directory=True)
    entries = []
    for path in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()):
        if path.is_symlink() or not path.is_file():
            if not path.is_dir(): raise ValueError("invalid serialization tree entry")
            continue
        entries.append({"relative_path": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)})
    if not entries: raise ValueError("empty serialization tree")
    return entries


def _snapshot_evidence(record, runtime_config, root):
    if set(record) != {"schema_version", "snapshot_id", "snapshot_index", "scene", "seed", "capture_time_s", "raw_rgb_path", "metadata_json_path", "serialized_snapshot_path", "producer_identity", "producer_frame_hash"}:
        raise ValueError("invalid authoritative snapshot record schema")
    expected = runtime_config["snapshots"]
    index = record["snapshot_index"]
    if record["schema_version"] != SNAPSHOT_RECORD_SCHEMA or not isinstance(index, int) or not 0 <= index < 4 or record["snapshot_id"] != expected[index]["snapshot_id"] or record["scene"] != runtime_config["scene"] or record["seed"] != runtime_config["seed"] or not _finite(record["capture_time_s"]) or not record["producer_identity"] or not record["producer_frame_hash"]:
        raise ValueError("snapshot record identity")
    raw = file_entry("raw_rgb", record["raw_rgb_path"], root, producer_identity=record["producer_identity"])
    metadata = file_entry("raw_metadata", record["metadata_json_path"], root, producer_identity=record["producer_identity"])
    try: meta = json.loads(Path(record["metadata_json_path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ValueError("invalid raw metadata") from exc
    required = {"schema_version", "snapshot_id", "snapshot_index", "scene", "seed", "frame_reference", "frame_sha256", "width_px", "height_px", "simulation_timestamp_s", "state_timestamp_s", "frame_timestamp_s", "target_timestamp_s", "state", "schedule_id", "schedule_available_time_s", "schedule_segments", "schedule_sha256"}
    allowed = required | ({"camera_context"} if meta.get("schema_version") == RAW_METADATA_SCHEMA_V2 else set())
    if set(meta) != allowed or meta["schema_version"] not in {RAW_METADATA_SCHEMA, RAW_METADATA_SCHEMA_V2} or meta["snapshot_id"] != record["snapshot_id"] or meta["snapshot_index"] != index or meta["scene"] != record["scene"] or meta["seed"] != record["seed"] or meta["frame_sha256"] != raw["sha256"] or meta["frame_sha256"] != record["producer_frame_hash"] or (meta["width_px"], meta["height_px"]) != (160, 120) or any(not _finite(meta[key]) for key in ("simulation_timestamp_s", "state_timestamp_s", "frame_timestamp_s", "target_timestamp_s", "schedule_available_time_s")):
        raise ValueError("raw metadata identity")
    if runtime_config.get("split") in {"formal", "development"}:
        from scripts.m6_tcobr import _camera_models
        if meta["schema_version"] != RAW_METADATA_SCHEMA_V2: raise ValueError("analysis camera metadata missing")
        _camera_models(meta.get("camera_context"))
    raw_relative = Path(record["raw_rgb_path"]).resolve().relative_to(Path(root).resolve()).as_posix()
    if meta["frame_reference"] != raw_relative or len(Path(record["raw_rgb_path"]).read_bytes()) != 160 * 120 * 3:
        raise ValueError("raw frame metadata mismatch")
    serialization = _under(record["serialized_snapshot_path"], root, directory=True)
    from scripts.m6a_snapshot_serialization import load_and_validate_serialized_snapshot
    loaded = load_and_validate_serialized_snapshot(serialization, runtime_config["v2_manifest_sha256"])
    if loaded.snapshot_id != record["snapshot_id"] or loaded.scene != record["scene"] or loaded.seed != record["seed"]:
        raise ValueError("trusted serialization identity")
    tree = _tree_entries(serialization, root)
    return {"snapshot_id": record["snapshot_id"], "snapshot_index": index, "scene": record["scene"], "seed": record["seed"], "capture_time_s": record["capture_time_s"], "producer_identity": record["producer_identity"], "producer_frame_hash_observation": record["producer_frame_hash"], "raw_rgb": raw, "metadata": metadata, "serialization_path": str(serialization), "serialization_relative_path": serialization.relative_to(Path(root).resolve()).as_posix(), "serialization_tree_entries": tree, "serialization_tree_digest": digest(tree), "authoritative_reload_result": "pass"}


def validate_runtime_manifest(manifest, identity, root, runtime_config):
    root = Path(root).resolve()
    if manifest.get("schema_version") != RUNTIME_MANIFEST_SCHEMA or manifest.get("identity") != identity or manifest.get("sha256") != digest({k: v for k, v in manifest.items() if k != "sha256"}): raise ValueError("runtime manifest digest or identity")
    required_identity = {"launch_id", "attempt_id", "identity_id", "scene_id", "seed"}
    if set(identity) != required_identity or identity["identity_id"] != runtime_config["episode_id"] or identity["scene_id"] != runtime_config["scene"] or identity["seed"] != runtime_config["seed"]: raise ValueError("runtime manifest identity")
    if manifest.get("attempt_root") != str(root) or manifest.get("runtime_config_sha256") != runtime_config["config_sha256"] or manifest.get("controller_identity") != runtime_config["controller"] or manifest.get("source_identity") != runtime_config["source_record_sha256"] or not manifest.get("produced_at_utc"): raise ValueError("runtime manifest binding")
    try: datetime.fromisoformat(manifest["produced_at_utc"])
    except Exception as exc: raise ValueError("runtime manifest time") from exc
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or [item.get("role") for item in artifacts] != ["runtime_summary", "runtime_status", "runtime_diagnostic"]: raise ValueError("runtime artifact set")
    from scripts.m6a_v2_runtime_summary import load_and_validate_episode_runtime_summary
    summary_entry, status_entry, diagnostic_entry = artifacts
    for entry in artifacts:
        if file_entry(entry["role"], entry["path"], root, schema_version=entry.get("schema_version"), producer_identity=entry.get("producer_identity")) != entry: raise ValueError("runtime artifact tamper")
    summary = load_and_validate_episode_runtime_summary(summary_entry["path"], runtime_config, require_paths=True)
    status = json.loads(Path(status_entry["path"]).read_text(encoding="utf-8"))
    if set(status) != {"schema_version", "summary_sha256", "success"} or status["schema_version"] != "m6a-v2-runtime-success-status-v1" or status["summary_sha256"] != summary["summary_sha256"] or status["success"] is not True: raise ValueError("runtime status mismatch")
    diagnostic = load_runtime_diagnostic(diagnostic_entry["path"], identity, root)
    if diagnostic["outcome"] != "success": raise ValueError("runtime diagnostic failure")
    records = summary.get("snapshots")
    if not isinstance(records, list) or len(records) != 4: raise ValueError("missing authoritative snapshots")
    snapshots = [_snapshot_evidence(record, runtime_config, root) for record in records]
    if [item["snapshot_id"] for item in snapshots] != [item["snapshot_id"] for item in runtime_config["snapshots"]] or [item["snapshot_index"] for item in snapshots] != list(range(4)) or len({item["raw_rgb"]["path"] for item in snapshots}) != 4 or len({item["metadata"]["path"] for item in snapshots}) != 4 or len({item["serialization_path"] for item in snapshots}) != 4: raise ValueError("snapshot set mismatch")
    validation = manifest.get("snapshot_validation", {})
    expected_validation = {"validator_identity": "m6a_v2_runtime_evidence", "checked_invariants": ["count", "identity", "unique_paths", "raw_metadata", "trusted_serialization"], "expected_count": 4, "actual_count": 4, "validated_snapshot_ids": [item["snapshot_id"] for item in snapshots], "snapshots": snapshots, "pass": True, "errors": []}
    if {k: v for k, v in validation.items() if k not in {"validated_at_utc", "canonical_digest"}} != expected_validation or not validation.get("validated_at_utc") or validation.get("canonical_digest") != digest({k: v for k, v in validation.items() if k != "canonical_digest"}): raise ValueError("snapshot validation evidence")
    return manifest


def persist_runtime_manifest(path, identity, root, *, runtime_config, summary_path, status_path, diagnostic_path):
    root = Path(root).resolve()
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    records = summary.get("snapshots", [])
    snapshots = [_snapshot_evidence(record, runtime_config, root) for record in records]
    validation = {"validator_identity": "m6a_v2_runtime_evidence", "checked_invariants": ["count", "identity", "unique_paths", "raw_metadata", "trusted_serialization"], "expected_count": 4, "actual_count": len(snapshots), "validated_snapshot_ids": [item["snapshot_id"] for item in snapshots], "snapshots": snapshots, "pass": len(snapshots) == 4, "errors": [], "validated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    if not validation["pass"]: raise ValueError("snapshot validation failed")
    validation["canonical_digest"] = digest(validation)
    artifacts = [file_entry("runtime_summary", summary_path, root, schema_version=summary.get("schema_version"), producer_identity="m6a_v2_runtime_summary"), file_entry("runtime_status", status_path, root, schema_version="m6a-v2-runtime-success-status-v1", producer_identity="m6a_v2_runtime_summary"), file_entry("runtime_diagnostic", diagnostic_path, root, schema_version="m6a-v2-runtime-diagnostic-v1", producer_identity="m6a_v2_runtime_summary")]
    manifest = persist(path, {"schema_version": RUNTIME_MANIFEST_SCHEMA, "identity": identity, "attempt_root": str(root), "runtime_config_sha256": runtime_config["config_sha256"], "controller_identity": runtime_config["controller"], "source_identity": runtime_config["source_record_sha256"], "producer_identity": "m6a_v2_runtime_evidence", "produced_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "artifacts": artifacts, "snapshot_validation": validation})
    return validate_runtime_manifest(manifest, identity, root, runtime_config)


def load_runtime_manifest(path, identity, root, runtime_config):
    return validate_runtime_manifest(load(path, RUNTIME_MANIFEST_SCHEMA, identity), identity, root, runtime_config)


def persist_validation(path, schema, identity, source, passed, errors=()):
    if not isinstance(passed, bool): raise ValueError("validation result")
    return persist(path, {"schema_version": schema, "identity": identity, "source_path": str(Path(source).resolve()), "source_sha256": _sha(source), "passed": passed, "errors": list(errors)})
def load_validation(path, schema, identity):
    value = load(path, schema, identity)
    if _sha(value["source_path"]) != value["source_sha256"] or not value["passed"]: raise ValueError("validation failed")
    return value
def persist_joint_report(path, identity, upstream):
    actual = [{"role": role, "path": str(Path(item).resolve()), "sha256": json.loads(Path(item).read_text()).get("sha256")} for role, item in upstream.items()]
    if any(not item["sha256"] for item in actual): raise ValueError("missing upstream digest")
    return persist(path, {"schema_version": "m6a-v2-joint-report-v1", "identity": identity, "upstream": actual, "passed": True, "errors": []})
def persist_process_evidence(path, identity, stdout, stderr, **fields):
    out=file_entry("stdout",stdout,Path(path).parent);err=file_entry("stderr",stderr,Path(path).parent)
    if fields.get("ended_at_utc","") < fields.get("started_at_utc","") or not isinstance(fields.get("return_code"),int): raise ValueError("invalid process timing/code")
    return persist(path,{"schema_version":"m6a-v2-process-evidence-v1","identity":identity,"stdout":out,"stderr":err,**fields})
def load_process_evidence(path,identity):
    value=load(path,"m6a-v2-process-evidence-v1",identity);root=Path(path).parent
    if file_entry("stdout",value["stdout"]["path"],root)!=value["stdout"] or file_entry("stderr",value["stderr"]["path"],root)!=value["stderr"] or value["ended_at_utc"]<value["started_at_utc"] or not isinstance(value["return_code"],int) or any(not item for item in (value["stdout"]["sha256"],value["stderr"]["sha256"])):raise ValueError("invalid process evidence")
    return value
def persist_runtime_diagnostic(path,identity,outcome,issues,producer_identity="m6a_v2_runtime_summary"):
    if outcome not in {"success","failure"} or not isinstance(issues,list):raise ValueError("diagnostic input")
    state="not_required" if outcome=="success" else "present"
    if (outcome=="success" and issues) or (outcome=="failure" and not issues):raise ValueError("diagnostic issues")
    return persist(path,{"schema_version":"m6a-v2-runtime-diagnostic-v1","identity":identity,"outcome":outcome,"diagnostic_state":state,"issue_count":len(issues),"issues":issues,"produced_at_utc":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"producer_identity":producer_identity})
def load_runtime_diagnostic(path,identity,root=None):
    if root is not None:_under(path,root)
    value=load(path,"m6a-v2-runtime-diagnostic-v1",identity)
    try:datetime.fromisoformat(value["produced_at_utc"])
    except Exception as exc:raise ValueError("diagnostic time") from exc
    if value["issue_count"]!=len(value["issues"]) or not isinstance(value["issues"],list) or value["outcome"] not in {"success","failure"} or (value["outcome"]=="success" and (value["diagnostic_state"]!="not_required" or value["issues"])) or (value["outcome"]=="failure" and (value["diagnostic_state"]!="present" or not value["issues"])):raise ValueError("diagnostic semantics")
    return value
