"""Seal the final bounded Q6 generation before its A1 outcomes."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.run_cvc_q6_generation3 import CONFIG, METHOD, READINESS, protected_paths
from scripts.run_cvc_q6_webots import SOURCE, selected_cells

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    out = ROOT / "results/cvc_q6_webots" / METHOD
    if out.exists() and list(out.glob("traces/*.summary.json")): raise RuntimeError("generation-3 outcomes exist")
    config = json.loads(CONFIG.read_text()); cells = selected_cells(config, json.loads(SOURCE.read_text()))
    paths = protected_paths(); missing = [name for name, path in paths.items() if not path.is_file()]
    if missing: raise RuntimeError(f"missing inputs: {missing}")
    manifest = {"study_id": config["study_id"], "method_id": METHOD,
                "parent_method_id": config["parent_method_id"], "development_only": True, "formal": False,
                "frozen_before_generation3_outcomes": True, "outcomes_present_at_freeze": False,
                "final_bounded_rule_based_attempt": True,
                "mechanism": "two consecutive frozen-Q5 precursor samples spend without hard ARM or live SafetyValue",
                "screening_cells": cells, "new_A1_episodes": 20, "sealed_reused_controls": 40,
                "exact_episode_wire_bytes": 72_000,
                "protected_sha256": {name: sha(path) for name, path in paths.items()},
                "independent_validation_eligible": False}
    READINESS.parent.mkdir(parents=True, exist_ok=True); canonical = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if READINESS.exists() and READINESS.read_text() != canonical: raise RuntimeError("readiness drift")
    READINESS.write_text(canonical, encoding="utf-8"); READINESS.with_suffix(".json.sha256").write_text(sha(READINESS)+"\n")
    print(json.dumps({"manifest": READINESS.relative_to(ROOT).as_posix(), "sha256": sha(READINESS), "cells": len(cells)}, indent=2))

if __name__ == "__main__": main()
