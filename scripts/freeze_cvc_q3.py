"""Seal CVC-Q3 scheduler and protected inputs before primary outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_cvc_q3_webots import protected_paths


OUT = ROOT / "results" / "cvc_q3_readiness"
PRIMARY = ROOT / "results" / "cvc_q3_webots"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if PRIMARY.exists() and any(PRIMARY.rglob("*.summary.json")):
        raise RuntimeError("Q3 outcomes already exist; refusing retroactive freeze")
    if OUT.exists():
        raise RuntimeError("Q3 readiness already exists")
    qualification_path = ROOT / "results" / "cvc_q3_offline_qualification" / "qualification.json"
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / "results" / "cvc_q3_runtime_profile" / "profile.json").read_text(encoding="utf-8"))
    smoke = json.loads((ROOT / "results" / "cvc_q3_smoke" / "qualification.json").read_text(encoding="utf-8"))
    q1 = json.loads((ROOT / "results" / "cvc_q1_support_readiness" / "manifest.json").read_text(encoding="utf-8"))
    if not qualification.get("passed") or qualification.get("navigation_outcomes_used"):
        raise RuntimeError("Q3 outcome-blind offline mechanism gate did not pass")
    if runtime.get("classification") != "logical_scheduler_timing" or runtime.get("any_component_deadline_miss"):
        raise RuntimeError("Q3 runtime audit did not clear computation latency")
    if not smoke.get("passed"):
        raise RuntimeError("Q3 adapter smoke failed")
    manifest = {
        "study_id": "cvc-q3-temporal-repair-v1",
        "development_only": True, "formal": False,
        "frozen_before_q3_policy_outcomes": True,
        "method_selection_navigation_outcomes_used": False,
        "chosen_candidate": qualification["chosen_candidate"],
        "runtime_classification": runtime["classification"],
        "q1_q2_fixed_components_unchanged": True,
        "scenario_ids": q1["scenario_ids"],
        "protected_sha256": {name: digest(path) for name, path in protected_paths().items()},
    }
    OUT.mkdir(parents=True)
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha = digest(path)
    path.with_suffix(".json.sha256").write_text(f"{sha}  manifest.json\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "manifest_sha256": sha,
                      "candidate": manifest["chosen_candidate"],
                      "scenario_count": len(manifest["scenario_ids"])}, indent=2))


if __name__ == "__main__":
    main()
