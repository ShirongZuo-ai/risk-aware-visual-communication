"""Outcome-free scheduler-timing qualification on Q5-consumed development traces."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_q6_scheduler import PrecursorScheduler, Q6CausalContext
from evaluation.cvc_q5_support import safety_value_from_planners


CONFIG = ROOT / "config/cvc_q6_development.json"
Q5_CONFIG = ROOT / "config/cvc_q5_stage_a.json"
Q5_MANIFEST = ROOT / "results/cvc_q5_readiness/manifest.json"
OUT = ROOT / "results/cvc_q6_offline_qualification"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def screening_ids(q6: dict, q5: dict) -> list[str]:
    selected = []
    for family in q5["families"]:
        if family["id"] not in q6["consumed_q5_positive_families"]:
            continue
        events = [row["id"] for row in family["cells"] if row["role"] == "event_candidate"][:4]
        controls = [row["id"] for row in family["cells"] if row["role"] == "matched_control"][:1]
        selected.extend([*events, *controls])
    if len(selected) != 20 or len(set(selected)) != 20:
        raise RuntimeError("Q6 literal screening selection must contain 20 unique cells")
    return selected


def load_rows(cell_id: str) -> list[dict]:
    path = ROOT / f"results/cvc_q5_stage_a/traces/{cell_id}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> None:
    q6 = json.loads(CONFIG.read_text(encoding="utf-8"))
    q5 = json.loads(Q5_CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads(Q5_MANIFEST.read_text(encoding="utf-8"))
    records = {row["cell_id"]: row for row in manifest["complete_attempted_corpus"]}
    cells = screening_ids(q6, q5)
    variants = [row["variant"] for row in q6["bounded_variants"]]
    details = []
    for variant in variants:
        for policy in ("A0", "A1"):
            for cell_id in cells:
                context = Q6CausalContext()
                common = q6["scheduler_common"]
                scheduler = PrecursorScheduler(
                    total_steps=q6["total_steps"], policy=policy, variant=variant,
                    prepare_validity_steps=common["prepare_validity_steps"],
                    fallback_step=common["fallback_step"], reserve_step=common["reserve_step"],
                    context=context,
                )
                decisions = []
                for row in load_rows(cell_id):
                    cf = row["counterfactual"]
                    context.observe(cf["held_planner"], cf["current_planner"], cf["current_obstacles"])
                    value = safety_value_from_planners(cf["held_planner"], cf["current_planner"])
                    decisions.append(scheduler.decide(int(row["step"]), 0.0, value))
                sends = [(index, item.reason) for index, item in enumerate(decisions) if item.transmit]
                onsets = [row["step"] for row in records[cell_id]["support"]["accepted_onsets"]]
                prepares = [index for index, item in enumerate(decisions) if item.latch.activated_this_step]
                covered = [onset for onset in onsets if any(max(0, onset - 63) <= step < onset for step in prepares)]
                details.append({
                    "variant": variant, "policy": policy, "cell_id": cell_id,
                    "family": records[cell_id]["family"], "event_onsets": onsets,
                    "covered_onsets": covered,
                    "arm_step": next((item.arm_step for item in decisions if item.arm_step is not None), None),
                    "prepare_steps": prepares, "send_steps": [step for step, _ in sends],
                    "adaptive_reason": sends[1][1],
                    "fallback": sends[1][1] in ("armed_fallback", "unarmed_fallback"),
                    "precursor_spend": sends[1][1].startswith("prepared_"),
                    "event_free": not onsets,
                })
    summary = {}
    for variant in variants:
        summary[variant] = {}
        for policy in ("A0", "A1"):
            rows = [row for row in details if row["variant"] == variant and row["policy"] == policy]
            event_free = [row for row in rows if row["event_free"]]
            total_onsets = sum(len(row["event_onsets"]) for row in rows)
            summary[variant][policy] = {
                "episodes": len(rows),
                "risk_armed": sum(row["arm_step"] is not None for row in rows),
                "precursor_spends": sum(row["precursor_spend"] for row in rows),
                "fallback_spends": sum(row["fallback"] for row in rows),
                "adaptive_reasons": dict(Counter(row["adaptive_reason"] for row in rows)),
                "event_onsets": total_onsets,
                "prepare_covered_onsets": sum(len(row["covered_onsets"]) for row in rows),
                "prepare_coverage": sum(len(row["covered_onsets"]) for row in rows) / total_onsets,
                "event_free_episodes": len(event_free),
                "event_free_precursor_spends": sum(row["precursor_spend"] for row in event_free),
            }
    result = {
        "study_id": q6["study_id"], "development_only": True, "formal": False,
        "navigation_outcomes_used": False, "q5_manifest_sha256": sha(Q5_MANIFEST),
        "q6_config_sha256": sha(CONFIG), "screening_cells": cells,
        "variants": variants, "summary": summary, "details": details,
        "initial_variant_remains_predeclared": q6["initial_variant"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "qualification.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "qualification.json.sha256").write_text(sha(path) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
