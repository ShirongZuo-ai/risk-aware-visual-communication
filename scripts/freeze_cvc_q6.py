"""Freeze bounded CVC-Q6 development inputs before any Q6 Webots outcome read."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_cvc_q6_webots import CONFIG, SOURCE, protected_paths, selected_cells


OUT = ROOT / "results/cvc_q6_readiness"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    cells = selected_cells(config, source)
    if len(cells) != 20 or len({row["id"] for row in cells}) != 20:
        raise RuntimeError("Q6 screen must contain exactly 20 distinct cells")
    if (ROOT / "results/cvc_q6_webots").exists():
        outcomes = list((ROOT / "results/cvc_q6_webots").glob("**/*.summary.json"))
        if outcomes:
            raise RuntimeError("cannot perform a first freeze after Q6 outcomes exist")
    paths = protected_paths()
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing Q6 protected inputs: {missing}")
    q5_manifest = ROOT / "results/cvc_q5_readiness/manifest.json"
    expected_q5 = "5d1f4f6ff683937bdde6c2df1d61ec11a37b9f6bf199d3b3abc2999e3398616c"
    if sha(q5_manifest) != expected_q5:
        raise RuntimeError("protected Q5 manifest no longer matches its qualified identity")
    variants = config["bounded_variants"]
    manifest = {
        "study_id": config["study_id"], "development_only": True, "formal": False,
        "frozen_before_q6_webots_outcomes": True,
        "q6_webots_outcomes_present_at_freeze": False,
        "initial_variant_id": config["initial_variant"],
        "allowed_variant_ids": [row["id"] for row in variants],
        "bounded_variants": variants,
        "screening_cells": cells,
        "screening_cell_ids": [row["id"] for row in cells],
        "expected_episodes_per_variant": 60,
        "exact_episode_wire_bytes": 72_000,
        "initial_execution": "Only q6-v1-value-confirmed. Later variants require a durable failure diagnosis and ledger entry.",
        "protected_q5_manifest_sha256": expected_q5,
        "protected_sha256": {name: sha(path) for name, path in paths.items()},
        "offline_qualification_is_outcome_free": True,
        "independent_validation_eligible": False,
    }
    manifest["manifest_content_sha256"] = canonical_sha(manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    canonical = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != canonical:
        raise RuntimeError("refusing to alter an existing Q6 frozen manifest")
    path.write_text(canonical, encoding="utf-8")
    path.with_suffix(".json.sha256").write_text(sha(path) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                      "cells": len(cells), "initial_variant": config["initial_variant"]}, indent=2))


if __name__ == "__main__":
    main()
