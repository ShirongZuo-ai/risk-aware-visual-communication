"""Strict router for immutable M6 manifest authority versions."""
from __future__ import annotations

import json
from pathlib import Path


def load_and_validate_m6a_manifest(manifest_path, lock_path) -> tuple[str, dict]:
    manifest_path = Path(manifest_path)
    schema = json.loads(manifest_path.read_text(encoding="utf-8")).get("manifest_schema_version")
    if schema == "m6a-v2-source-manifest-v1":
        from scripts.m6a_v2_episode_source import load_and_validate_m6a_v2_manifest
        return "v2", load_and_validate_m6a_v2_manifest(manifest_path, lock_path)
    if schema == "m6a-v3-study-extension-manifest-v1":
        from scripts.m6a_v3_episode_source import load_and_validate_m6a_v3_manifest
        return "v3", load_and_validate_m6a_v3_manifest(manifest_path, lock_path)
    if schema == "m7-v1-development-corpus-manifest-v1":
        from scripts.m7_v1_episode_source import load_and_validate_m7_v1_manifest
        return "m7v1", load_and_validate_m7_v1_manifest(manifest_path, lock_path)
    raise ValueError("unknown M6 manifest authority")
