"""Freeze the complete precursor-blinded CVC-Q5 Stage-A corpus."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE_A = ROOT / "results/cvc_q5_stage_a/support_qualification.json"
OUT = ROOT / "results/cvc_q5_readiness"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def main() -> None:
    support = json.loads(STAGE_A.read_text(encoding="utf-8"))
    if not support.get("support_gate_pass"):
        raise RuntimeError("CVC-Q5 cannot be unblinded: Stage-A support gate failed")
    if support.get("precursor_imported_or_evaluated") is not False:
        raise RuntimeError("Stage-A anti-contamination assertion is absent")
    records = support["records"]
    if len(records) != support["attempted_cells"] or len(records) != 70:
        raise RuntimeError("expected all 70 attempted cells")
    if len({row["cell_id"] for row in records}) != len(records):
        raise RuntimeError("duplicate Stage-A cell")
    for row in records:
        trace = ROOT / f"results/cvc_q5_stage_a/traces/{row['cell_id']}.jsonl"
        job = ROOT / f"results/cvc_q5_stage_a/jobs/{row['cell_id']}.json"
        if sha(trace) != row["trace_sha256"] or sha(job) != row["job_sha256"]:
            raise RuntimeError(f"artifact drift for {row['cell_id']}")

    protected_paths = [
        "results/cvc_q1_support_readiness/manifest.json",
        "results/cvc_q2_readiness/manifest.json",
        "results/cvc_q3_readiness/manifest.json",
        "results/cvc_q3_webots/matrix_results.json",
        "results/cvc_q3_analysis/analysis.json",
        "evaluation/cvc_q4_precursor.py",
        "results/cvc_q4_analysis/analysis.json",
        "results/m9a_formal/formal_manifest.json",
        "results/m9a_formal/formal_results.json",
        "results/m9a_formal/formal_access_ledger.jsonl",
        "results/m9b_formal/formal_results.json",
        "results/m9b_readiness_v3/formal_access_ledger.jsonl",
    ]
    protected = {}
    for relative in protected_paths:
        path = ROOT / relative
        if not path.exists():
            raise RuntimeError(f"missing protected evidence: {relative}")
        protected[relative] = sha(path)
    manifest = {
        "study_id": "cvc-q5-event-rich-precursor-qualification-v1",
        "development_only": True,
        "formal": False,
        "stage_a_completed_before_precursor_unblinding": True,
        "stage_a_config_path": "config/cvc_q5_stage_a.json",
        "stage_a_config_sha256": sha(ROOT / "config/cvc_q5_stage_a.json"),
        "stage_a_support_path": STAGE_A.relative_to(ROOT).as_posix(),
        "stage_a_support_sha256": sha(STAGE_A),
        "stage_a_qualification_sha256": sha(STAGE_A),
        "support_gate_pass": True,
        "support_gates": json.loads((ROOT / "config/cvc_q5_stage_a.json").read_text(
            encoding="utf-8"))["support_gates"],
        "family_support": support["family_support"],
        "positive_families": support["positive_families"],
        "complete_attempted_corpus": records,
        "protected_sha256": protected,
        "generalization_gates": {
            "A_pooled_onset_coverage_min": 0.75,
            "B_family_coverage_min": 0.50,
            "B_positive_families_meeting_min": 3,
            "C_median_lead_s_min": 0.25,
            "D_active_fraction_max": 0.02,
            "E_event_free_episode_activation_max": 0.25,
            "F_covered_onsets_usable_opportunity_min": 0.50,
            "usable_opportunity": "at least two consecutive active samples before onset",
        },
        "fixed_execution": {
            "duration_s": 10.0,
            "step_s": 0.032,
            "communication_mode": "U0",
            "transmission_count": 3,
            "q1_world_sha256": support["q1_world_sha256"],
            "q1_controller_sha256": support["q1_controller_sha256"],
            "q1_readiness_sha256": support["q1_readiness_sha256"],
        },
    }
    manifest["manifest_content_sha256"] = canonical_sha(manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise RuntimeError("refusing to alter an existing CVC-Q5 frozen manifest")
    else:
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (OUT / "manifest.json.sha256").write_text(sha(path) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": path.relative_to(ROOT).as_posix(),
                      "sha256": sha(path), "cells": len(records),
                      "positive_families": support["positive_families"]}, indent=2))


if __name__ == "__main__":
    main()
