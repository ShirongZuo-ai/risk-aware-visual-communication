"""Generate or check deterministic M8-B0 synthetic unit-validation evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scripts.m6a_trusted_artifacts import digest
from scripts.m8_evaluator_reference import CCORFInput, evaluate_ccorf, validate_ccorf_evidence
from scripts.m8_proxy_common import canonical_json_bytes, sequence_diagnostics
from scripts.m8_proxy_synthetic import (
    JPEG_QUALITY_LADDER,
    controlled_perturbations,
    jpeg_reconstruction,
    synthetic_fixture,
    synthetic_identity,
)
from scripts.m8_sender_proxies import (
    FROPUInput,
    STRCFInput,
    evaluate_fropu,
    evaluate_strcf,
    validate_fropu_evidence,
    validate_strcf_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "results" / "m8_b0_unit_validation.json"
SCHEMA = "m8-b0-unit-validation-v1"


def _evaluate_case(
    name: str,
    reconstruction,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    identity = synthetic_identity(name)
    fropu_input = FROPUInput.create(
        identity=identity,
        original=fixture["original"],
        reconstruction=reconstruction,
        union_corridor=fixture["union_corridor"],
    )
    strcf_input = STRCFInput.create(
        identity=identity,
        original=fixture["original"],
        reconstruction=reconstruction,
        union_risk=fixture["union_risk"],
        union_uncertainty=fixture["union_uncertainty"],
    )
    ccorf_input = CCORFInput.create(
        identity=identity,
        original=fixture["original"],
        reconstruction=reconstruction,
        critical_obstacle_mask=fixture["critical_obstacle_mask"],
        critical_boundary_mask=fixture["critical_boundary_mask"],
        geometry_digest=fixture["geometry_digest"],
    )
    fropu = evaluate_fropu(fropu_input)
    strcf = evaluate_strcf(strcf_input)
    ccorf = evaluate_ccorf(ccorf_input)
    validate_fropu_evidence(fropu, expected_identity=identity, source_input=fropu_input)
    validate_strcf_evidence(strcf, expected_identity=identity, source_input=strcf_input)
    validate_ccorf_evidence(ccorf, expected_identity=identity, source_input=ccorf_input)
    return {
        "name": name,
        "fropu": fropu["score"],
        "strcf": strcf["score"],
        "ccorf": ccorf["score"],
        "fropu_digest": fropu["canonical_digest"],
        "strcf_digest": strcf["canonical_digest"],
        "ccorf_digest": ccorf["canonical_digest"],
    }


def build_report() -> dict[str, Any]:
    fixture = synthetic_fixture()
    cases = [
        _evaluate_case(name, reconstruction, fixture)
        for name, reconstruction in controlled_perturbations(fixture).items()
    ]
    ladder = [
        _evaluate_case(
            f"jpeg_q{quality}",
            jpeg_reconstruction(fixture["original"], quality),
            fixture,
        )
        for quality in JPEG_QUALITY_LADDER
    ]
    diagnostics = {
        proxy: sequence_diagnostics([case[proxy] for case in ladder])
        for proxy in ("fropu", "strcf", "ccorf")
    }
    deterministic_repeat = _evaluate_case(
        "compression_q15",
        jpeg_reconstruction(fixture["original"], 15),
        fixture,
    )
    first_q15 = next(case for case in cases if case["name"] == "compression_q15")
    base = {
        "schema_version": SCHEMA,
        "status": "UNIT_VALIDATION_PASS",
        "scientific_qualification": "NOT_EVALUATED_REQUIRES_810XXX_CALIBRATION",
        "candidate_selection": "NOT_PERFORMED",
        "source": "repository_owned_synthetic_fixture",
        "protocol_sources": [
            "docs/m8_a_scientific_design.md",
            "docs/m8_a_proxy_comparison.md",
            "docs/results/m8_a_proxy_validation_rules.json",
        ],
        "operational": {"fropu": True, "strcf": True, "ccorf": True},
        "boundary": {
            "sender_evaluator_separated": True,
            "actual_future_usage": 0,
            "fallback": False,
            "replacement": False,
        },
        "controlled_perturbations": cases,
        "jpeg_quality_ladder": {
            "qualities": list(JPEG_QUALITY_LADDER),
            "cases": ladder,
            "diagnostics": diagnostics,
        },
        "deterministic_repeat": {
            "case": "compression_q15",
            "digests_match": all(
                first_q15[field] == deterministic_repeat[field]
                for field in ("fropu_digest", "strcf_digest", "ccorf_digest")
            ),
        },
        "unit_gate_notes": {
            "synthetic_scores_are_not_proxy_qualification": True,
            "g2_dynamic_range": "DIAGNOSTIC_ONLY",
            "g3_monotonicity": "DIAGNOSTIC_ONLY",
            "g4_to_g8": "NOT_EVALUATED_REQUIRES_810XXX_CALIBRATION",
            "fropu_detector_prerequisite": "NOT_EVALUATED_REQUIRES_810XXX_CALIBRATION",
        },
    }
    if not base["deterministic_repeat"]["digests_match"]:
        raise ValueError("M8-B0 deterministic repeat failed")
    return {**base, "canonical_digest": digest(base)}


def validate_report(value: dict[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    supplied = payload.pop("canonical_digest", None)
    if payload.get("schema_version") != SCHEMA or supplied != digest(payload):
        raise ValueError("invalid M8-B0 unit-validation report")
    if payload.get("scientific_qualification") != "NOT_EVALUATED_REQUIRES_810XXX_CALIBRATION":
        raise ValueError("M8-B0 report must not claim proxy qualification")
    if payload.get("candidate_selection") != "NOT_PERFORMED":
        raise ValueError("M8-B0 report must not select a proxy")
    if payload.get("operational") != {"fropu": True, "strcf": True, "ccorf": True}:
        raise ValueError("M8-B0 operational status incomplete")
    payload["canonical_digest"] = supplied
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = validate_report(build_report())
    encoded = canonical_json_bytes(report)
    if args.check:
        if args.output.read_bytes() != encoded:
            raise ValueError("M8-B0 unit-validation report is not reproducible")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(report["canonical_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
