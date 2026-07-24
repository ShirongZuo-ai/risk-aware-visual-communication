"""Immutable v3 formal-study extension built from frozen M6 primitives."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import (
    BUDGETS, LOCK_PATH as V2_LOCK_PATH, MANIFEST_PATH as V2_MANIFEST_PATH,
    METHODS, WORLD, _sha, build_m6a_v2_episode_source,
    load_and_validate_m6a_v2_manifest,
)

VERSION = "m6a-byte-fair-v3"
MANIFEST_PATH = PROJECT_ROOT / "docs/results/m6a_v3_episode_source_manifest.json"
LOCK_PATH = PROJECT_ROOT / "docs/results/m6a_v3_episode_source_manifest.lock.json"
SCENES = tuple(f"S{index}" for index in range(1, 9))
V2_MANIFEST_SHA256 = "61e2e9e311d703564441627efde2da17954605b1f389a047ace8aa898c650724"
V2_LOCK_SHA256 = "10d4c6c62be463b0d052e853c73a46ff57723239df65e7bb7876877fcbc2fc1b"


def _bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def identities() -> tuple[dict, ...]:
    return tuple(
        {"split": "formal", "scenario_id": scene,
         "episode_id": f"m6a_v3_formal_{scene.lower()}_seed{seed}", "seed": seed}
        for scene_index, scene in enumerate(SCENES, start=1)
        for seed in range(630000 + scene_index * 100, 630000 + scene_index * 100 + 4)
    )


def build_v3_record(identity: dict) -> dict:
    if identity not in identities():
        raise ValueError("identity is not in the frozen v3 formal extension")
    record = build_m6a_v2_episode_source(identity).canonical()
    record["protocol_version"] = VERSION
    record["supersedes"] = "m6a-byte-fair-v2"
    record["source_record_sha256"] = digest(record)
    return record


def manifest_payload() -> dict:
    v2 = load_and_validate_m6a_v2_manifest(V2_MANIFEST_PATH, V2_LOCK_PATH)
    if _sha(V2_MANIFEST_PATH) != V2_MANIFEST_SHA256 or _sha(V2_LOCK_PATH) != V2_LOCK_SHA256:
        raise ValueError("v2 frozen authority changed")
    records = [build_v3_record(identity) for identity in identities()]
    v2_ids = {record["identity"]["episode_id"] for record in v2["records"]}
    v2_seeds = {record["identity"]["seed"] for record in v2["records"]}
    if v2_ids & {record["identity"]["episode_id"] for record in records} or v2_seeds & {record["identity"]["seed"] for record in records}:
        raise ValueError("v3 identity is not disjoint from v2")
    return {
        "protocol_version": VERSION,
        "manifest_schema_version": "m6a-v3-study-extension-manifest-v1",
        "status": "immutable", "extension_role": "formal-study-only",
        "parent_protocol": "m6a-byte-fair-v2",
        "parent_manifest_relative_path": "docs/results/m6a_v2_episode_source_manifest.json",
        "parent_manifest_sha256": V2_MANIFEST_SHA256,
        "parent_lock_relative_path": "docs/results/m6a_v2_episode_source_manifest.lock.json",
        "parent_lock_sha256": V2_LOCK_SHA256,
        "canonical_json_rule": "utf-8; sort_keys; separators=comma/colon; trailing-newline",
        "record_sort_rule": "scene S1-S8; ascending seed; four episodes per scene",
        "source_adapter_path": "scripts/m6a_v3_episode_source.py",
        "source_adapter_sha256": _sha(Path(__file__)),
        "scene_generator_path": v2["scene_generator_path"],
        "scene_generator_sha256": v2["scene_generator_sha256"],
        "base_world_path": v2["base_world_path"], "base_world_sha256": _sha(WORLD),
        "timestep_s": v2["timestep_s"], "duration_s": v2["duration_s"],
        "snapshot_progress": v2["snapshot_progress"],
        "snapshot_step_indices": v2["snapshot_step_indices"],
        "snapshot_aligned_times_s": v2["snapshot_aligned_times_s"],
        "methods": list(METHODS), "budgets": BUDGETS,
        "split_counts": {"formal": 32}, "total_records": 32,
        "actual_future_prohibited": True, "combined_mask_prohibited": True,
        "records": records,
    }


def lock_payload(payload: dict) -> dict:
    raw = _bytes(payload)
    return {
        "lock_schema_version": "m6a-v3-study-extension-lock-v1",
        "protocol_version": VERSION, "status": "immutable",
        "manifest_relative_path": "docs/results/m6a_v3_episode_source_manifest.json",
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_byte_length": len(raw), "total_records": 32,
        "split_counts": {"formal": 32},
        "parent_manifest_sha256": V2_MANIFEST_SHA256,
        "parent_lock_sha256": V2_LOCK_SHA256,
        "base_world_sha256": payload["base_world_sha256"],
        "source_adapter_sha256": payload["source_adapter_sha256"],
        "scene_generator_sha256": payload["scene_generator_sha256"],
        "canonical_json_rule": payload["canonical_json_rule"],
    }


def write_manifest() -> tuple[dict, dict]:
    payload = manifest_payload(); lock = lock_payload(payload)
    for path, value in ((MANIFEST_PATH, payload), (LOCK_PATH, lock)):
        raw = _bytes(value)
        if path.exists() and path.read_bytes() != raw:
            raise FileExistsError("refusing to replace immutable v3 artifact")
        path.write_bytes(raw)
    return payload, lock


def load_and_validate_m6a_v3_manifest(manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH) -> dict:
    raw = Path(manifest_path).read_bytes(); payload = json.loads(raw)
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    if raw != _bytes(payload) or hashlib.sha256(raw).hexdigest() != lock.get("manifest_sha256") or payload.get("total_records") != 32 or payload.get("split_counts") != {"formal": 32}:
        raise ValueError("invalid v3 manifest/lock")
    expected = json.loads(_bytes(manifest_payload()).decode("utf-8"))
    if payload != expected or lock != lock_payload(payload):
        raise ValueError("tampered or nonreproducible v3 manifest")
    return payload


if __name__ == "__main__":
    written, written_lock = write_manifest()
    print(json.dumps({"records": len(written["records"]), "manifest_sha256": written_lock["manifest_sha256"]}, sort_keys=True))
