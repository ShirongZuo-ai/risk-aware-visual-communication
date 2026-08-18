"""Freeze the outcome-independent CVC-P7 development suite before comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_p7_development.json"
P6_CONFIG = ROOT / "config" / "cvc_p6_development.json"
PROTECTED = (
    ROOT / "communication" / "cvc_p6_allocator.py",
    ROOT / "communication" / "cvc_p2_perception.py",
    ROOT / "simulator" / "controllers" / "cvc_p6_runner" / "cvc_p6_runner.py",
    ROOT / "simulator" / "worlds" / "cvc_p6_runner.wbt",
)
OUTPUT = ROOT / "results" / "cvc_p7_readiness" / "scenario_manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(enforce_preoutcome: bool = True) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    scenarios = config["scenarios"]
    identities = [item["id"] for item in scenarios]
    physical_tuples = [
        (tuple(item["start"]), tuple((obj["id"], tuple(obj["center"]), tuple(obj["size"]),
                                      obj.get("physical", True), tuple(obj.get("color", [1, 0, 0])))
                                     for obj in item["objects"]))
        for item in scenarios
    ]
    if len(scenarios) != 12 or len(set(identities)) != 12 or len(set(physical_tuples)) != 12:
        raise RuntimeError("P7 requires 12 distinct deterministic cells")
    category_counts = {category: sum(item["category"] == category for item in scenarios)
                       for category in "ABCD"}
    if category_counts != {category: 3 for category in "ABCD"}:
        raise RuntimeError("P7 2x2 suite must contain three cells per category")
    if enforce_preoutcome and (ROOT / "results" / "cvc_p7_webots" / "matrix_summary.json").exists():
        raise RuntimeError("comparative outcomes already exist; suite cannot be newly frozen")
    return {
        "study_id": config["study_id"],
        "development_only": True,
        "formal": False,
        "frozen_before_comparative_outcomes": True,
        "scenario_count": len(scenarios),
        "category_counts": category_counts,
        "scenario_ids": identities,
        "scenario_config_sha256": sha256(CONFIG),
        "p6_config_sha256": sha256(P6_CONFIG),
        "protected_p6_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in PROTECTED},
        "outcome_fields_used_for_construction": [],
        "construction_inputs": ["physical_geometry", "intended_motion_structure", "camera_observability",
                                "conceptual_category", "deterministic_identity_seed"],
    }


def main() -> None:
    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") != payload:
        raise RuntimeError("a different P7 suite is already frozen")
    OUTPUT.write_text(payload, encoding="utf-8")
    sidecar = OUTPUT.with_suffix(".json.sha256")
    sidecar.write_text(hashlib.sha256(payload.encode("utf-8")).hexdigest() + "\n", encoding="ascii")
    print(payload, end="")


if __name__ == "__main__":
    main()
