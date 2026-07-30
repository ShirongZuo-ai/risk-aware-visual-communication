"""Read-only validation for the proposed M8-A measurement design."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "docs" / "results" / "m8_a_proposed_corpus_matrix.csv"
DEFAULT_RULES = ROOT / "docs" / "results" / "m8_a_proxy_validation_rules.json"
EXPECTED_SCHEMA = "m8-a-proposed-corpus-v1"
EXPECTED_RULES_SCHEMA = "m8-a-proxy-validation-rules-v1"
EXPECTED_SPLIT_COUNTS = {"calibration": 28, "development": 40, "formal": 40}
EXPECTED_CRITICAL_SCENES = {f"M8C{index}" for index in range(1, 9)}
EXPECTED_GENERALIZATION_SCENES = {"M8G1", "M8G2"}
EXPECTED_GATE_IDS = {
    "G1_integrity_boundary",
    "G2_dynamic_range",
    "G3_monotonicity",
    "G4_ccorf_association",
    "G5_pairwise_ranking",
    "G6_critical_specificity",
    "G7_scene_stability",
    "G8_incremental_validity",
    "G9_reproduction",
}


@dataclass(frozen=True)
class ProposedIdentity:
    split: str
    scene_id: str
    seed: int
    identity_id: str


def _load_matrix(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("M8-A matrix is empty")
    return rows


def _load_rules(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("M8-A rules must be a JSON object")
    return payload


def expand_matrix(rows: Iterable[dict[str, str]]) -> tuple[ProposedIdentity, ...]:
    identities: list[ProposedIdentity] = []
    for row in rows:
        if row["schema_version"] != EXPECTED_SCHEMA:
            raise ValueError("unexpected M8-A matrix schema")
        start = int(row["seed_start"])
        end = int(row["seed_end"])
        count = int(row["episode_count"])
        if end - start + 1 != count:
            raise ValueError(f"non-contiguous episode range for {row['split']} {row['scene_id']}")
        template = row["identity_template"]
        if template.count("{seed}") != 1:
            raise ValueError("identity template must contain exactly one {seed} token")
        for seed in range(start, end + 1):
            identities.append(
                ProposedIdentity(
                    split=row["split"],
                    scene_id=row["scene_id"],
                    seed=seed,
                    identity_id=template.format(seed=seed),
                )
            )
    return tuple(identities)


def _collect_seed_values(value: Any, key: str = "") -> set[int]:
    seeds: set[int] = set()
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            seeds.update(_collect_seed_values(child_value, child_key.lower()))
    elif isinstance(value, list):
        for child in value:
            seeds.update(_collect_seed_values(child, key))
    elif "seed" in key and isinstance(value, int) and not isinstance(value, bool):
        seeds.add(value)
    return seeds


def collect_existing_authoritative_seeds(root: Path = ROOT) -> set[int]:
    seeds: set[int] = set()
    results_root = root / "docs" / "results"
    for path in sorted(results_root.glob("*manifest*.json")):
        if path.name.startswith("m8_a_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid authoritative JSON: {path}") from exc
        seeds.update(_collect_seed_values(payload))
    return seeds


def validate_design(
    matrix_path: Path = DEFAULT_MATRIX,
    rules_path: Path = DEFAULT_RULES,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    rows = _load_matrix(matrix_path)
    if len(rows) != 30:
        raise ValueError("M8-A matrix must contain exactly 30 split-scene rows")

    expected_scenes = EXPECTED_CRITICAL_SCENES | EXPECTED_GENERALIZATION_SCENES
    for split in EXPECTED_SPLIT_COUNTS:
        split_rows = [row for row in rows if row["split"] == split]
        if {row["scene_id"] for row in split_rows} != expected_scenes:
            raise ValueError(f"{split} does not contain the exact ten-scene matrix")
        roles = {row["scene_id"]: row["role"] for row in split_rows}
        if any(roles[scene] != "critical" for scene in EXPECTED_CRITICAL_SCENES):
            raise ValueError(f"{split} critical-scene role mismatch")
        if any(roles[scene] != "generalization" for scene in EXPECTED_GENERALIZATION_SCENES):
            raise ValueError(f"{split} generalization-scene role mismatch")

    identities = expand_matrix(rows)
    split_counts = {
        split: sum(identity.split == split for identity in identities)
        for split in EXPECTED_SPLIT_COUNTS
    }
    if split_counts != EXPECTED_SPLIT_COUNTS:
        raise ValueError("M8-A expanded split counts do not match the frozen proposal")
    seeds = [identity.seed for identity in identities]
    identity_ids = [identity.identity_id for identity in identities]
    if len(seeds) != len(set(seeds)) or len(identity_ids) != len(set(identity_ids)):
        raise ValueError("M8-A proposed seeds and identities must be unique")

    prior_seeds = collect_existing_authoritative_seeds(root)
    overlap = sorted(set(seeds) & prior_seeds)
    if overlap:
        raise ValueError(f"M8-A proposal overlaps authoritative prior seeds: {overlap}")

    rules = _load_rules(rules_path)
    if rules.get("schema_version") != EXPECTED_RULES_SCHEMA:
        raise ValueError("unexpected M8-A proxy-rules schema")
    if rules.get("status") != "proposed_not_executed":
        raise ValueError("M8-A rules must remain explicitly unexecuted")
    bootstrap = rules.get("bootstrap", {})
    if bootstrap.get("replicates") != 10000 or bootstrap.get("seed") != 20260724:
        raise ValueError("M8-A bootstrap definition changed")
    gate_ids = {gate.get("id") for gate in rules.get("gates", [])}
    if gate_ids != EXPECTED_GATE_IDS or len(rules.get("gates", [])) != 9:
        raise ValueError("M8-A must define the exact nine proxy gates")
    selection = rules.get("selection_rule", {})
    if selection.get("allocator_outcomes_may_select_proxy") is not False:
        raise ValueError("allocator outcomes must not select the M8-A proxy")
    if rules.get("tcobr_role") != "non_degradation_safety_metric":
        raise ValueError("TCOBR role must remain non-degradation safety")

    return {
        "schema_version": EXPECTED_SCHEMA,
        "rules_schema_version": EXPECTED_RULES_SCHEMA,
        "row_count": len(rows),
        "identity_count": len(identities),
        "split_counts": split_counts,
        "prior_seed_overlap": overlap,
        "gate_count": len(gate_ids),
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    args = parser.parse_args()
    print(json.dumps(validate_design(args.matrix, args.rules), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
