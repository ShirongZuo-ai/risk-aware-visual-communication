"""Immutable M7 v1 development-corpus authority and information boundary."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import M6AProjectionConfig, digest
from scripts.m6a_v2_episode_source import BUDGETS, METHODS, WORLD, _sha
from simulator.m5e_config import MAX_REPLACEMENTS, primary_seed, primary_seed_indices, replacement_seed
from simulator.m7_scenarios import (
    SCENE_IDS, SNAPSHOT_TIMES_S, canonical_scene, evaluator_only_geometry,
    generate_m7_scenario, geometric_event_evidence,
)


VERSION = "m7-development-corpus-v1"
MANIFEST_PATH = PROJECT_ROOT / "docs/results/m7_v1_episode_source_manifest.json"
LOCK_PATH = PROJECT_ROOT / "docs/results/m7_v1_episode_source_manifest.lock.json"
PREREGISTRATION_PATH = PROJECT_ROOT / "docs/results/m7_v1_development_preregistration.json"
V2_MANIFEST_PATH = PROJECT_ROOT / "docs/results/m6a_v2_episode_source_manifest.json"
V2_LOCK_PATH = PROJECT_ROOT / "docs/results/m6a_v2_episode_source_manifest.lock.json"
V3_MANIFEST_PATH = PROJECT_ROOT / "docs/results/m6a_v3_episode_source_manifest.json"
V3_LOCK_PATH = PROJECT_ROOT / "docs/results/m6a_v3_episode_source_manifest.lock.json"
V2_MANIFEST_SHA256 = "61e2e9e311d703564441627efde2da17954605b1f389a047ace8aa898c650724"
V2_LOCK_SHA256 = "10d4c6c62be463b0d052e853c73a46ff57723239df65e7bb7876877fcbc2fc1b"
V3_MANIFEST_SHA256 = "941780a9985469164c2f6610432cd4d7ed6001cbc55b860858057bcc5066158d"
V3_LOCK_SHA256 = "68aefdd5450474e6653e53cb050b58633cfbd6a545e84265d6edbfb4856299cf"


def _bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def identities() -> tuple[dict, ...]:
    return tuple(
        {
            "split": "development", "scenario_id": scene,
            "episode_id": f"m7_v1_development_{scene.lower()}_seed{seed}", "seed": seed,
        }
        for scene_index, scene in enumerate(SCENE_IDS, start=1)
        for seed in range(710000 + scene_index * 100, 710000 + scene_index * 100 + 2)
    )


def _m5_seed_authority() -> set[int]:
    values = set()
    for split in ("smoke", "calibration", "formal"):
        for scene_index in range(1, 9):
            for index in primary_seed_indices(split):
                values.add(primary_seed(split, scene_index, index))
            for replacement_index in range(MAX_REPLACEMENTS[split]):
                values.add(replacement_seed(split, scene_index, replacement_index))
    return values


def _m6_identity_authority() -> tuple[set[str], set[int]]:
    ids, seeds = set(), set()
    for path, expected in ((V2_MANIFEST_PATH, V2_MANIFEST_SHA256), (V3_MANIFEST_PATH, V3_MANIFEST_SHA256)):
        if _sha(path) != expected:
            raise ValueError("frozen M6 manifest changed")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload["records"]:
            ids.add(record["identity"]["episode_id"]); seeds.add(record["identity"]["seed"])
    return ids, seeds


def build_record(identity: dict) -> dict:
    if identity not in identities():
        raise ValueError("identity is not in the frozen M7 v1 matrix")
    config = generate_m7_scenario(identity["scenario_id"], identity["seed"])
    schedule = tuple(asdict(item) for item in config.command_schedule)
    projection = M6AProjectionConfig().canonical()
    sender_scene = {
        "scene_id": identity["scenario_id"], "seed": identity["seed"],
        "initial_pose": list(config.start_pose), "schedule": schedule,
        "duration_s": "6.0", "primitive_authority": "simulator.m7_scenarios",
    }
    boundary = {
        "schema_version": "m7-v1-information-boundary-v1",
        "allocator_visible": [
            "trusted_rgb", "sender_time_current_state", "predefined_command_schedule",
            "projection_config", "camera_context", "predicted_trajectory", "uncertainty_config",
        ],
        "evaluator_only": ["obstacle_geometry", "critical_event_labels", "future_ground_truth", "tcobr_annotations"],
        "actual_future_available_to_allocator": False,
        "evaluator_annotations_available_to_allocator": False,
    }
    record = {
        "protocol_version": VERSION, "supersedes": "m6a-byte-fair-v3",
        "identity": dict(identity),
        "source_world_path": str(WORLD.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_world_sha256": _sha(WORLD),
        "scene_generator_path": "simulator/m7_scenarios.py",
        "scene_generator_sha256": _sha(PROJECT_ROOT / "simulator/m7_scenarios.py"),
        "scene_generator_version": config.generator_version,
        "scene_config": sender_scene, "scene_config_sha256": digest(sender_scene),
        "timestep_s": "0.032", "duration_s": "6.0",
        "schedule": schedule, "schedule_sha256": digest(schedule), "schedule_available_time_s": "0.0",
        "snapshot_progress": ("0.20", "0.45", "0.70", "0.90"),
        "snapshot_raw_times_s": ("1.200", "2.700", "4.200", "5.400"),
        "snapshot_step_indices": (38, 84, 131, 169),
        "snapshot_aligned_times_s": tuple(f"{value:.3f}" for value in SNAPSHOT_TIMES_S),
        "projection_config": projection, "projection_config_sha256": digest(projection),
        "methods": tuple(METHODS), "budgets": BUDGETS,
        "information_boundary": boundary,
        "geometric_event_precheck": geometric_event_evidence(config),
        "evaluator_only_obstacle_geometry": evaluator_only_geometry(config),
        "causal_pre_run_source": True, "derived_from_actual_trace": False,
        "actual_future_prohibited": True, "combined_mask_prohibited": True,
        "codec_outcomes_observed_during_selection": False,
    }
    record["source_record_sha256"] = digest(record)
    return record


def manifest_payload() -> dict:
    for path, expected in (
        (V2_MANIFEST_PATH, V2_MANIFEST_SHA256), (V2_LOCK_PATH, V2_LOCK_SHA256),
        (V3_MANIFEST_PATH, V3_MANIFEST_SHA256), (V3_LOCK_PATH, V3_LOCK_SHA256),
    ):
        if _sha(path) != expected:
            raise ValueError("frozen M6 authority changed")
    records = [build_record(identity) for identity in identities()]
    m6_ids, m6_seeds = _m6_identity_authority()
    new_ids = {item["identity"]["episode_id"] for item in records}
    new_seeds = {item["identity"]["seed"] for item in records}
    if new_ids & m6_ids or new_seeds & (m6_seeds | _m5_seed_authority()) or len(new_ids) != 16 or len(new_seeds) != 16:
        raise ValueError("M7 corpus identities are not disjoint")
    return {
        "protocol_version": VERSION,
        "manifest_schema_version": "m7-v1-development-corpus-manifest-v1",
        "status": "immutable", "corpus_role": "allocator-development-only-not-formal",
        "canonical_json_rule": "utf-8; sort_keys; separators=comma/colon; trailing-newline",
        "record_sort_rule": "M7C1-M7C6,M7G1-M7G2; ascending seed; two episodes per scene",
        "source_adapter_path": "scripts/m7_v1_episode_source.py",
        "source_adapter_sha256": _sha(Path(__file__)),
        "scene_generator_path": "simulator/m7_scenarios.py",
        "scene_generator_sha256": _sha(PROJECT_ROOT / "simulator/m7_scenarios.py"),
        "base_world_path": str(WORLD.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "base_world_sha256": _sha(WORLD),
        "parent_authorities": {
            "m6_v2_manifest_sha256": V2_MANIFEST_SHA256, "m6_v2_lock_sha256": V2_LOCK_SHA256,
            "m6_v3_manifest_sha256": V3_MANIFEST_SHA256, "m6_v3_lock_sha256": V3_LOCK_SHA256,
        },
        "disjointness": {
            "m5_seed_authority_count": len(_m5_seed_authority()),
            "m6_identity_authority_count": len(m6_ids), "m6_seed_authority_count": len(m6_seeds),
            "identity_overlap_count": 0, "seed_overlap_count": 0,
        },
        "timestep_s": "0.032", "duration_s": "6.0",
        "snapshot_step_indices": [38, 84, 131, 169],
        "snapshot_aligned_times_s": [f"{value:.3f}" for value in SNAPSHOT_TIMES_S],
        "methods": list(METHODS), "budgets": BUDGETS,
        "split_counts": {"development": 16}, "scene_counts": {scene: 2 for scene in SCENE_IDS},
        "total_records": 16, "actual_future_prohibited": True, "combined_mask_prohibited": True,
        "records": records,
    }


def lock_payload(payload: dict) -> dict:
    raw = _bytes(payload)
    return {
        "lock_schema_version": "m7-v1-development-corpus-lock-v1",
        "protocol_version": VERSION, "status": "immutable",
        "manifest_relative_path": "docs/results/m7_v1_episode_source_manifest.json",
        "manifest_sha256": hashlib.sha256(raw).hexdigest(), "canonical_byte_length": len(raw),
        "total_records": 16, "split_counts": {"development": 16},
        "scene_counts": payload["scene_counts"], "parent_authorities": payload["parent_authorities"],
        "base_world_sha256": payload["base_world_sha256"],
        "source_adapter_sha256": payload["source_adapter_sha256"],
        "scene_generator_sha256": payload["scene_generator_sha256"],
        "canonical_json_rule": payload["canonical_json_rule"],
    }


def preregistration_payload(payload: dict, lock: dict) -> dict:
    matrix = [
        {
            "attempt_id": f"m7v1d-{item['identity']['scenario_id'].lower()}-{item['identity']['seed']}",
            "episode_id": item["identity"]["episode_id"], "scene": item["identity"]["scenario_id"],
            "seed": item["identity"]["seed"], "source_record_sha256": item["source_record_sha256"],
            "scene_role": item["geometric_event_precheck"]["scene_role"],
        }
        for item in payload["records"]
    ]
    return {
        "schema_version": "m7-v1-development-preregistration-v1", "status": "frozen-before-generation",
        "manifest_sha256": lock["manifest_sha256"], "lock_sha256": hashlib.sha256(_bytes(lock)).hexdigest(),
        "purpose": "deterministic allocator development corpus; not formal scientific inference",
        "selection_rule": "all sixteen registered records; no post-outcome selection or replacement",
        "launch_rule": "one launch per identity; zero retries; shared defect stops remaining batch",
        "information_boundary": "sender-time fields only; evaluator geometry remains isolated",
        "expected": {"episodes": 16, "scenes": 8, "snapshots": 64, "codec_cases": 512},
        "matrix": matrix,
    }


def write_authority() -> tuple[dict, dict, dict]:
    payload = manifest_payload(); lock = lock_payload(payload); prereg = preregistration_payload(payload, lock)
    for path, value in ((MANIFEST_PATH, payload), (LOCK_PATH, lock), (PREREGISTRATION_PATH, prereg)):
        raw = _bytes(value)
        if path.exists() and path.read_bytes() != raw:
            raise FileExistsError("refusing to replace immutable M7 v1 authority")
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    return payload, lock, prereg


def load_and_validate_m7_v1_manifest(manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH) -> dict:
    raw = Path(manifest_path).read_bytes(); payload = json.loads(raw)
    lock_raw = Path(lock_path).read_bytes(); lock = json.loads(lock_raw)
    if raw != _bytes(payload) or lock_raw != _bytes(lock) or hashlib.sha256(raw).hexdigest() != lock.get("manifest_sha256"):
        raise ValueError("invalid canonical M7 manifest/lock")
    if payload.get("total_records") != 16 or payload.get("split_counts") != {"development": 16} or payload.get("scene_counts") != {scene: 2 for scene in SCENE_IDS}:
        raise ValueError("invalid M7 corpus matrix")
    expected = json.loads(_bytes(manifest_payload()).decode("utf-8"))
    if payload != expected or lock != lock_payload(payload):
        raise ValueError("tampered or nonreproducible M7 manifest")
    return payload


def record_for_runtime(runtime_config: dict) -> dict:
    payload = load_and_validate_m7_v1_manifest(runtime_config["v2_manifest_path"], runtime_config["v2_lock_path"])
    matches = [item for item in payload["records"] if item["source_record_sha256"] == runtime_config.get("source_record_sha256")]
    if len(matches) != 1:
        raise ValueError("runtime does not bind one M7 record")
    record = matches[0]
    identity = record["identity"]
    if (
        runtime_config.get("manifest_authority_version") != "m7v1"
        or runtime_config.get("split") != "development"
        or (runtime_config.get("episode_id"), runtime_config.get("scene"), runtime_config.get("seed"))
        != (identity["episode_id"], identity["scenario_id"], identity["seed"])
    ):
        raise ValueError("M7 runtime identity mismatch")
    return record


def persist_evaluator_only_geometry(runtime_config: dict, root: str | Path) -> dict:
    root = Path(root).resolve(); path = root / "evaluator_only_geometry.json"
    if not root.is_dir() or path.exists():
        raise ValueError("unsafe or reused evaluator geometry path")
    record = record_for_runtime(runtime_config)
    value = {
        "schema_version": "m7-v1-persisted-evaluator-only-geometry-v1",
        "identity": dict(record["identity"]), "source_record_sha256": record["source_record_sha256"],
        "runtime_config_sha256": runtime_config["config_sha256"],
        "information_boundary_sha256": digest(record["information_boundary"]),
        "geometric_event_precheck": record["geometric_event_precheck"],
        "evaluator_only_obstacle_geometry": record["evaluator_only_obstacle_geometry"],
        "allocator_access_allowed": False, "persisted_after_runtime": True,
    }
    value["canonical_digest"] = digest(value); path.write_bytes(_bytes(value))
    return load_evaluator_only_geometry(path, runtime_config, root)


def load_evaluator_only_geometry(path: str | Path, runtime_config: dict, root: str | Path) -> dict:
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or path.resolve() != root / "evaluator_only_geometry.json" or not path.is_file():
        raise ValueError("unsafe evaluator geometry artifact")
    raw = path.read_bytes(); value = json.loads(raw)
    if raw != _bytes(value) or value.get("canonical_digest") != digest({k:v for k,v in value.items() if k != "canonical_digest"}):
        raise ValueError("evaluator geometry canonical digest")
    record = record_for_runtime(runtime_config)
    if (
        value.get("schema_version") != "m7-v1-persisted-evaluator-only-geometry-v1"
        or value.get("identity") != record["identity"]
        or value.get("source_record_sha256") != record["source_record_sha256"]
        or value.get("runtime_config_sha256") != runtime_config["config_sha256"]
        or value.get("information_boundary_sha256") != digest(record["information_boundary"])
        or value.get("geometric_event_precheck") != record["geometric_event_precheck"]
        or value.get("evaluator_only_obstacle_geometry") != record["evaluator_only_obstacle_geometry"]
        or value.get("allocator_access_allowed") is not False
        or value.get("persisted_after_runtime") is not True
    ):
        raise ValueError("evaluator geometry binding")
    return value


if __name__ == "__main__":
    manifest, lock, preregistration = write_authority()
    print(json.dumps({"records": len(manifest["records"]), "manifest_sha256": lock["manifest_sha256"], "matrix": len(preregistration["matrix"])}, sort_keys=True))
