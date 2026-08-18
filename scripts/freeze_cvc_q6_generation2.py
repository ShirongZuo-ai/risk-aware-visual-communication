"""Seal Q6 generation 2 after generation-1 failure diagnosis and before outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_cvc_q6_generation2 import CONFIG, READINESS, VARIANT_ID, protected_paths
from scripts.run_cvc_q6_webots import SOURCE, selected_cells


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    out = ROOT / "results/cvc_q6_webots" / VARIANT_ID
    if out.exists() and list(out.glob("traces/*.summary.json")):
        raise RuntimeError("generation-2 outcomes already exist")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cells = selected_cells(config, json.loads(SOURCE.read_text(encoding="utf-8")))
    paths = protected_paths()
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing generation-2 inputs: {missing}")
    manifest = {
        "study_id": config["study_id"], "method_id": VARIANT_ID,
        "parent_method_id": "q6-v1-value-confirmed", "development_only": True, "formal": False,
        "frozen_before_generation2_outcomes": True, "outcomes_present_at_freeze": False,
        "failure_repaired": "F7 hard-ARM bootstrap starvation causing F6 fallback dominance",
        "only_scheduler_change": config["change_from_parent"],
        "screening_cells": cells, "expected_episodes": 60, "exact_episode_wire_bytes": 72_000,
        "protected_sha256": {name: sha(path) for name, path in paths.items()},
        "independent_validation_eligible": False,
    }
    READINESS.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if READINESS.exists() and READINESS.read_text(encoding="utf-8") != canonical:
        raise RuntimeError("refusing to alter generation-2 readiness")
    READINESS.write_text(canonical, encoding="utf-8")
    READINESS.with_suffix(".json.sha256").write_text(sha(READINESS) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": READINESS.relative_to(ROOT).as_posix(), "sha256": sha(READINESS),
                      "cells": len(cells), "method": VARIANT_ID}, indent=2))


if __name__ == "__main__":
    main()
