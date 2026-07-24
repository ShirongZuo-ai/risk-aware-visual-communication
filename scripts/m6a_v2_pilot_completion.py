"""Owned post-runtime B5 completion evidence; never starts Webots or writes pilot data itself."""
from __future__ import annotations
import hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_codec_audit import (SnapshotCodecInput, METHODS, BUDGET_ORDER,
    build_method_mask, encode_reconstruct_case, evaluate_codec_case, audit_codec_case)
from scripts.m6a_v2_runtime_evidence import file_entry, load_runtime_manifest
from scripts.run_m6a_one_identity import load_v2_runtime_config
from scripts.m6_tcobr import validate_tcobr_evidence


AGGREGATE_SCHEMA = "m6a-v2-codec-aggregate-v2"
AGGREGATE_VALIDATION_SCHEMA = "m6a-v2-codec-aggregate-validation-v1"
JOINT_SCHEMA = "m6a-v2-persisted-joint-validation-v1"

def _canon(value): return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): raise FileExistsError("refusing overwrite")
    temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_bytes(_canon(value)); temporary.replace(path)
def _read(path):
    raw = Path(path).read_bytes(); value = json.loads(raw)
    if raw != _canon(value): raise ValueError("noncanonical evidence")
    return value
def _owned(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    return root == path or root in path.parents
def _identity(runtime, launch_id="runtime-local", attempt_id="runtime-local"):
    return {"launch_id": launch_id, "attempt_id": attempt_id, "identity_id": runtime["episode_id"], "scene_id": runtime["scene"], "seed": runtime["seed"]}
def _expected_cases(runtime): return {(snapshot["snapshot_id"], method, budget) for snapshot in runtime["snapshots"] for method in METHODS for budget in BUDGET_ORDER}


def build_snapshot_codec_input_from_runtime_artifact(runtime_config, snapshot_record, *, owned_output_root, ownership_marker):
    load_v2_runtime_config(runtime_config); root = Path(owned_output_root).resolve(); marker = Path(ownership_marker)
    if not marker.is_file() or not _owned(root, marker): raise ValueError("ownership marker")
    sid = snapshot_record["snapshot_id"]; expected = next((item for item in runtime_config["snapshots"] if item["snapshot_id"] == sid), None)
    if expected is None or snapshot_record.get("timestamp_s") != expected["timestamp_s"]: raise ValueError("snapshot identity")
    raw = Path(snapshot_record.get("raw_rgb_path", snapshot_record.get("raw_path", ""))); meta = Path(snapshot_record.get("metadata_json_path", snapshot_record.get("metadata_path", "")))
    if not _owned(root, raw) or not _owned(root, meta) or not raw.is_file() or not meta.is_file(): raise ValueError("unsafe artifact path")
    data = raw.read_bytes(); metadata = json.loads(meta.read_text())
    if len(data) != 160 * 120 * 3 or hashlib.sha256(data).hexdigest() != metadata.get("frame_sha256"): raise ValueError("raw digest")
    state = CurrentState(**metadata["state"])
    segments = tuple(CommandSegment(item.get("start_offset_s", item.get("start_s")), item.get("end_offset_s", item.get("end_s")), item.get("left_wheel_command_rad_s", item.get("left_rad_s")), item.get("right_wheel_command_rad_s", item.get("right_rad_s"))) for item in metadata["schedule_segments"])
    schedule = ScheduleEvidence(metadata["schedule_id"], metadata["schedule_available_time_s"], segments)
    return SnapshotCodecInput.create(runtime_config=runtime_config, snapshot_id=sid, timestamp_s=expected["timestamp_s"], image=np.frombuffer(data, dtype=np.uint8).reshape(120, 160, 3), state=state, schedule=schedule, synthetic_fixture=bool(metadata.get("synthetic_fixture", False)), camera_context=metadata.get("camera_context"))


def process_and_audit_runtime_snapshot(runtime_config, snapshot_record, *, owned_output_root, ownership_marker):
    input_ = build_snapshot_codec_input_from_runtime_artifact(runtime_config, snapshot_record, owned_output_root=owned_output_root, ownership_marker=ownership_marker); cases = []
    for method in METHODS:
        mask, payload = build_method_mask(runtime_config, input_, method)
        for budget in BUDGET_ORDER:
            case = encode_reconstruct_case(runtime_config, input_, mask, payload, budget); evaluation = evaluate_codec_case(runtime_config, input_, case); audit = audit_codec_case(runtime_config, input_, mask, payload, case, evaluation)
            cases.append({"snapshot_id": input_.snapshot_id, "method": method, "budget": budget, "case_sha256": case.case_sha256, "evaluation_sha256": evaluation.evaluation_sha256, "charged_bytes": case.charged_bytes, "budget_bytes": case.budget_bytes, "full_mse": evaluation.full_mse, "full_psnr_db": evaluation.full_psnr_db, "full_ssim": evaluation.full_ssim, "roi_pixel_count": mask.selected_pixel_count, "roi_area_ratio": mask.selected_area_ratio, "tcobr_evidence": evaluation.tcobr_evidence, "audit_sha256": audit["audit_sha256"]})
    if len(cases) != 8: raise ValueError("incomplete snapshot cases")
    path = Path(owned_output_root) / "codec" / f"{input_.snapshot_id}.json"; payload = {"snapshot_id": input_.snapshot_id, "raw_image_sha256": input_.raw_image_sha256, "cases": cases, "synthetic_fixture": input_.synthetic_fixture}; payload["sha256"] = digest(payload); _write(path, payload)
    payload["artifact_path"] = str(path.resolve()); payload["artifact_bytes"] = path.stat().st_size; payload["artifact_sha256"] = _sha(path); return payload


def validate_codec_aggregate(aggregate, runtime_config, *, root):
    load_v2_runtime_config(runtime_config); root = Path(root).resolve()
    if aggregate.get("schema_version") != AGGREGATE_SCHEMA or aggregate.get("aggregate_sha256") != digest({key: value for key, value in aggregate.items() if key != "aggregate_sha256"}): raise ValueError("aggregate digest/schema")
    if aggregate.get("runtime_config_sha256") != runtime_config["config_sha256"] or aggregate.get("scene") != runtime_config["scene"] or aggregate.get("seed") != runtime_config["seed"] or tuple(aggregate.get("methods", ())) != METHODS or tuple(aggregate.get("budgets", ())) != BUDGET_ORDER or aggregate.get("expected_case_count") != 32 or aggregate.get("actual_case_count") != 32 or aggregate.get("case_count") != 32 or not aggregate.get("producer_identity") or not aggregate.get("produced_at_utc"): raise ValueError("aggregate identity")
    try: datetime.fromisoformat(aggregate["produced_at_utc"])
    except Exception as exc: raise ValueError("aggregate timestamp") from exc
    snapshots = aggregate.get("snapshot_evidence")
    if not isinstance(snapshots, list) or len(snapshots) != 4 or len({item.get("snapshot_id") for item in snapshots}) != 4: raise ValueError("snapshot evidence")
    cases = [case for snapshot in snapshots for case in snapshot.get("cases", [])]
    actual = {(case.get("snapshot_id"), case.get("method"), case.get("budget")) for case in cases}
    if actual != _expected_cases(runtime_config) or len(cases) != len(actual) or any(not all(case.get(key) for key in ("case_sha256", "evaluation_sha256", "audit_sha256")) or not isinstance(case.get("charged_bytes"), int) or case["charged_bytes"] < 0 for case in cases): raise ValueError("aggregate case coverage")
    for case in cases:
        if case.get("budget_bytes") != runtime_config["budgets"][case["budget"]] or case["charged_bytes"] > case["budget_bytes"]: raise ValueError("aggregate byte fairness")
        if not all(isinstance(case.get(key), (int, float)) and math.isfinite(case[key]) for key in ("full_mse", "full_ssim", "roi_area_ratio")) or not isinstance(case.get("full_psnr_db"),(int,float)) or math.isnan(case["full_psnr_db"]): raise ValueError("aggregate quality metrics")
        if not isinstance(case.get("roi_pixel_count"), int) or case["roi_pixel_count"] < 0 or not 0 <= case["roi_area_ratio"] <= 1: raise ValueError("aggregate ROI metrics")
        if runtime_config.get("split") == "formal": validate_tcobr_evidence(case.get("tcobr_evidence"))
    if aggregate.get("per_method_count") != {method: 16 for method in METHODS} or aggregate.get("per_budget_count") != {budget: 8 for budget in BUDGET_ORDER} or aggregate.get("charged_bytes_total") != sum(case["charged_bytes"] for case in cases) or any(aggregate.get(key) != 0 for key in ("prohibited_usage", "fallback", "replacement")): raise ValueError("aggregate numeric consistency")
    if aggregate.get("synthetic_fixture") != all(snapshot.get("synthetic_fixture") is True for snapshot in snapshots): raise ValueError("aggregate synthetic state")
    return aggregate


def persist_codec_aggregate(runtime_config, snapshot_evidence, *, owned_output_root, ownership_marker):
    root = Path(owned_output_root).resolve(); marker = Path(ownership_marker)
    if not marker.is_file() or not _owned(root, marker): raise ValueError("ownership marker")
    launch_id = digest({"marker": marker.read_text(), "runtime": runtime_config["config_sha256"]})
    cases = [case for snapshot in snapshot_evidence for case in snapshot.get("cases", [])]
    payload = {"schema_version": AGGREGATE_SCHEMA, "launch_id": launch_id, "attempt_id": "runtime-local", "identity_id": runtime_config["episode_id"], "scene": runtime_config["scene"], "seed": runtime_config["seed"], "runtime_config_sha256": runtime_config["config_sha256"], "methods": list(METHODS), "budgets": list(BUDGET_ORDER), "snapshot_evidence": snapshot_evidence, "expected_case_count": 32, "actual_case_count": len(cases), "case_count": len(cases), "per_method_count": {method: sum(case.get("method") == method for case in cases) for method in METHODS}, "per_budget_count": {budget: sum(case.get("budget") == budget for case in cases) for budget in BUDGET_ORDER}, "charged_bytes_total": sum(case.get("charged_bytes", 0) for case in cases), "synthetic_fixture": all(snapshot.get("synthetic_fixture") is True for snapshot in snapshot_evidence), "prohibited_usage": 0, "fallback": 0, "replacement": 0, "producer_identity": "m6a_v2_pilot_completion", "produced_at_utc": _utc()}
    payload["aggregate_sha256"] = digest(payload); validate_codec_aggregate(payload, runtime_config, root=root); _write(root / "codec_aggregate.json", payload); return payload


def load_codec_aggregate(path, runtime_config, *, root): return validate_codec_aggregate(_read(path), runtime_config, root=root)


def _aggregate_validation(runtime_config, aggregate_path, *, root, identity):
    aggregate = load_codec_aggregate(aggregate_path, runtime_config, root=root); cases = [case for snapshot in aggregate["snapshot_evidence"] for case in snapshot["cases"]]
    return {"schema_version": AGGREGATE_VALIDATION_SCHEMA, "identity": identity, "validator_identity": "m6a_v2_pilot_completion", "aggregate_path": str(Path(aggregate_path).resolve()), "aggregate_bytes": Path(aggregate_path).stat().st_size, "aggregate_file_sha256": _sha(aggregate_path), "aggregate_canonical_digest": aggregate["aggregate_sha256"], "expected_case_identities": sorted([list(item) for item in _expected_cases(runtime_config)]), "actual_case_identities": sorted([list((case["snapshot_id"], case["method"], case["budget"])) for case in cases]), "checked_invariants": ["canonical_digest", "identity", "case_coverage", "numeric_totals", "prohibited_usage"], "passed": True, "errors": [], "validated_at_utc": _utc()}


def persist_codec_aggregate_validation(path, runtime_config, aggregate_path, *, root, identity):
    report = _aggregate_validation(runtime_config, aggregate_path, root=root, identity=identity); report["report_sha256"] = digest(report); _write(path, report); return load_codec_aggregate_validation(path, runtime_config, root=root, identity=identity)
def validate_codec_aggregate_validation(report, runtime_config, *, root, identity):
    if report.get("schema_version") != AGGREGATE_VALIDATION_SCHEMA or report.get("identity") != identity or report.get("report_sha256") != digest({key: value for key, value in report.items() if key != "report_sha256"}) or not report.get("passed") or report.get("errors") != []: raise ValueError("aggregate validation report")
    actual = _aggregate_validation(runtime_config, report["aggregate_path"], root=root, identity=identity)
    if {key: value for key, value in report.items() if key not in {"validated_at_utc", "report_sha256"}} != {key: value for key, value in actual.items() if key != "validated_at_utc"}: raise ValueError("stale aggregate validation")
    return report
def load_codec_aggregate_validation(path, runtime_config, *, root, identity): return validate_codec_aggregate_validation(_read(path), runtime_config, root=root, identity=identity)


def _joint(runtime_manifest_path, aggregate_validation_path, *, runtime_config, root):
    raw_manifest = _read(runtime_manifest_path); identity = raw_manifest.get("identity")
    manifest = load_runtime_manifest(runtime_manifest_path, identity, root, runtime_config); aggregate_validation = load_codec_aggregate_validation(aggregate_validation_path, runtime_config, root=root, identity=identity)
    aggregate = load_codec_aggregate(aggregate_validation["aggregate_path"], runtime_config, root=root)
    manifest_snapshots = manifest["snapshot_validation"]["validated_snapshot_ids"]
    aggregate_snapshots = sorted({case["snapshot_id"] for item in aggregate["snapshot_evidence"] for case in item["cases"]})
    if manifest_snapshots != [item["snapshot_id"] for item in runtime_config["snapshots"]] or aggregate_snapshots != sorted(manifest_snapshots): raise ValueError("joint snapshot mismatch")
    return identity, manifest, aggregate_validation


def persist_joint_validation_report(path, runtime_manifest_path, aggregate_validation_path, *, runtime_config, root):
    identity, manifest, validation = _joint(runtime_manifest_path, aggregate_validation_path, runtime_config=runtime_config, root=root)
    report = {"schema_version": JOINT_SCHEMA, "identity": identity, "runtime_config_sha256": runtime_config["config_sha256"], "runtime_manifest": file_entry("runtime_manifest", runtime_manifest_path, root, canonical_digest=manifest["sha256"]), "aggregate_validation": file_entry("aggregate_validation", aggregate_validation_path, root, canonical_digest=validation["report_sha256"]), "validator_identity": "m6a_v2_pilot_completion", "outcome": "pass", "errors": [], "produced_at_utc": _utc()}; report["joint_sha256"] = digest(report); _write(path, report); return load_joint_validation_report(path, runtime_config, root=root)
def validate_joint_validation_report(report, runtime_config, *, root):
    if report.get("schema_version") != JOINT_SCHEMA or report.get("joint_sha256") != digest({key: value for key, value in report.items() if key != "joint_sha256"}) or report.get("outcome") != "pass" or report.get("errors") != []: raise ValueError("joint report")
    identity, manifest, validation = _joint(report["runtime_manifest"]["path"], report["aggregate_validation"]["path"], runtime_config=runtime_config, root=root)
    if report.get("identity") != identity or report.get("runtime_config_sha256") != runtime_config["config_sha256"] or file_entry("runtime_manifest", report["runtime_manifest"]["path"], root, canonical_digest=manifest["sha256"]) != report["runtime_manifest"] or file_entry("aggregate_validation", report["aggregate_validation"]["path"], root, canonical_digest=validation["report_sha256"]) != report["aggregate_validation"]: raise ValueError("joint stale/tamper")
    return report
def load_joint_validation_report(path, runtime_config, *, root): return validate_joint_validation_report(_read(path), runtime_config, root=root)


def validate_pilot_completion(launch_spec, process_result, runtime_summary, codec_aggregate, completion_evidence, *, owned_output_root):
    if not process_result.get("started") or process_result.get("timed_out") or process_result.get("interrupted") or codec_aggregate.get("runtime_config_sha256") != completion_evidence.get("runtime_config_sha256") or completion_evidence.get("codec_aggregate_sha256") != codec_aggregate.get("aggregate_sha256") or completion_evidence.get("runtime_summary_sha256") != runtime_summary.get("summary_sha256") or completion_evidence.get("launch_id") != codec_aggregate.get("launch_id") or not _owned(owned_output_root, Path(launch_spec["owner_marker"])): raise ValueError("joint completion failed")
    return {"integration_valid": True, "synthetic_fixture": codec_aggregate["synthetic_fixture"], "scientific_result": False}


def process_completed_pilot_launch(launch_spec, process_result, *, owned_output_root):
    root = Path(owned_output_root).resolve(); runtime = _read(launch_spec["runtime_config"]["path"]); summary = _read(launch_spec["summary_path"])
    if not process_result.get("started") or not summary.get("success"): raise ValueError("runtime completion unavailable")
    manifest_path = Path(launch_spec.get("runtime_manifest_path", root / "runtime_artifacts.json")); raw_manifest = _read(manifest_path); identity = raw_manifest.get("identity"); load_runtime_manifest(manifest_path, identity, root, runtime)
    records = [{**record, "timestamp_s": runtime["snapshots"][record["snapshot_index"]]["timestamp_s"]} for record in summary.get("snapshots", [])]
    snapshots = [process_and_audit_runtime_snapshot(runtime, record, owned_output_root=root, ownership_marker=launch_spec["owner_marker"]) for record in records]
    aggregate = persist_codec_aggregate(runtime, snapshots, owned_output_root=root, ownership_marker=launch_spec["owner_marker"])
    aggregate_path = root / "codec_aggregate.json"; validation_path = Path(launch_spec.get("aggregate_validation_path", root / "codec_aggregate_validation.json")); joint_path = Path(launch_spec.get("joint_report_path", root / "joint_validation.json"))
    persist_codec_aggregate_validation(validation_path, runtime, aggregate_path, root=root, identity=identity)
    persist_joint_validation_report(joint_path, manifest_path, validation_path, runtime_config=runtime, root=root)
    joint = load_joint_validation_report(joint_path, runtime, root=root)
    manifest = load_runtime_manifest(manifest_path, identity, root, runtime)
    validation = load_codec_aggregate_validation(validation_path, runtime, root=root, identity=identity)
    completion = {"runtime_config_sha256": runtime["config_sha256"], "codec_aggregate_sha256": aggregate["aggregate_sha256"], "runtime_summary_sha256": summary["summary_sha256"], "launch_id": aggregate["launch_id"]}
    final_evidence = {"runtime_sha256": manifest["sha256"], "snapshot_validation_sha256": manifest["snapshot_validation"]["canonical_digest"], "b5_sha256": validation["report_sha256"], "aggregate_sha256": aggregate["aggregate_sha256"], "joint_validator_sha256": joint["joint_sha256"], "manifest_sha256": runtime["v2_manifest_sha256"], "lock_sha256": runtime["v2_lock_sha256"]}
    return {**validate_pilot_completion(launch_spec, process_result, summary, aggregate, completion, owned_output_root=root), "joint_report_sha256": joint["joint_sha256"], "final_evidence": final_evidence}
