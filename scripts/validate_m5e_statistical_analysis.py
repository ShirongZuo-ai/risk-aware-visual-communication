"""Independently validate M5E-E episode statistics, bootstrap, and figures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_statistical_analysis_common import (
    ANALYSIS_PROTOCOL_VERSION,
    BOOTSTRAP_FIELDS,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    EPISODE_FIELDS,
    FIGURE_INPUT_FIELDS,
    PAIR_FIELDS,
    PRIMARY_BUDGETS,
    PRIMARY_METHOD,
    SCENARIO_FIELDS,
    WIN_FIELDS,
    analysis_paths,
    build_analysis,
)
from scripts.m5e_formal_evaluation_common import formal_paths
from scripts.m5e_dataset_common import sha256_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-root", default="data/m5e_formal")
    parser.add_argument(
        "--analysis-root",
        default="data/m5e_formal/statistical_analysis",
    )
    parser.add_argument(
        "--figure-root",
        default="results/m5_compression/m5e_statistics",
    )
    return parser


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _compare_rows(
    actual: list[dict[str, str]],
    expected: list[dict[str, str]],
    fields: list[str],
    label: str,
) -> None:
    if len(actual) != len(expected):
        raise ValueError(f"{label} row count mismatch: {len(actual)} != {len(expected)}")
    for index, (left, right) in enumerate(zip(actual, expected)):
        if set(left) != set(fields):
            raise ValueError(f"{label} schema mismatch")
        for field in fields:
            if left[field] != right[field]:
                raise ValueError(
                    f"{label} recomputation mismatch at row {index} field {field}"
                )


def validate_outputs(
    formal_root: Path,
    analysis_root: Path,
    figure_root: Path,
) -> dict[str, int | bool]:
    paths = analysis_paths(analysis_root)
    built = build_analysis(formal_root)
    episodes = _read(paths["episode_metrics"])
    pairs = _read(paths["paired_effects"])
    bootstrap = _read(paths["bootstrap_results"])
    scenarios = _read(paths["scenario_diagnostics"])
    wins = _read(paths["win_tie_loss"])
    inputs = _read(paths["figure_inputs"])
    _compare_rows(episodes, built["episodes"], EPISODE_FIELDS, "episode metrics")
    _compare_rows(pairs, built["pairs"], PAIR_FIELDS, "paired effects")
    _compare_rows(bootstrap, built["bootstrap"], BOOTSTRAP_FIELDS, "bootstrap results")
    _compare_rows(scenarios, built["scenarios"], SCENARIO_FIELDS, "scenario diagnostics")
    _compare_rows(wins, built["wins"], WIN_FIELDS, "win/tie/loss")
    _compare_rows(inputs, built["figure_inputs"], FIGURE_INPUT_FIELDS, "figure inputs")
    if any(row["frame_count"] != "4" for row in episodes):
        raise ValueError("frame-level pseudoreplication guard failed")
    episode_identities = {
        (row["scenario_id"], row["episode_id"], row["original_seed"]) for row in episodes
    }
    if len(episode_identities) != 64:
        raise ValueError("episode identity count is not 64")
    primary_pairs = [row for row in pairs if row["analysis_role"] == "primary"]
    if len(primary_pairs) != 384 or any(row["pair_valid"] != "true" for row in primary_pairs):
        raise ValueError("primary pair matrix must contain 384 valid pairs")
    primary_bootstrap = [row for row in bootstrap if row["analysis_role"] == "primary"]
    if len(primary_bootstrap) != 6:
        raise ValueError("six preregistered primary comparisons are required")
    for row in primary_bootstrap:
        if row["bootstrap_seed"] != str(BOOTSTRAP_SEED):
            raise ValueError("bootstrap seed changed")
        if row["bootstrap_iterations"] != str(BOOTSTRAP_ITERATIONS):
            raise ValueError("bootstrap iteration count changed")
        if row["budget_label"] not in PRIMARY_BUDGETS:
            raise ValueError("primary tag applied outside severe/low")
    manifest = json.loads(paths["analysis_manifest"].read_text(encoding="utf-8"))
    if manifest.get("protocol_version") != ANALYSIS_PROTOCOL_VERSION:
        raise ValueError("analysis protocol version mismatch")
    if manifest.get("bootstrap_seed") != BOOTSTRAP_SEED:
        raise ValueError("analysis manifest seed mismatch")
    if manifest.get("bootstrap_iterations") != BOOTSTRAP_ITERATIONS:
        raise ValueError("analysis manifest iteration mismatch")
    source_path = formal_paths(formal_root)["metrics_csv"]
    if manifest.get("source_formal_metric_sha256") != sha256_file(source_path):
        raise ValueError("source formal result hash mismatch")
    failure_log = json.loads(paths["failure_log"].read_text(encoding="utf-8"))
    if failure_log.get("missing_primary_pair_count") != 0:
        raise ValueError("missing primary pairs were silently dropped")
    if failure_log.get("duplicate_pair_count") != 0:
        raise ValueError("duplicate pairs were accepted")
    if failure_log.get("frame_level_inference_performed") is not False:
        raise ValueError("frame-level inference was performed")
    if failure_log.get("unfavorable_result_exclusion_performed") is not False:
        raise ValueError("unfavorable results were excluded")
    figure_manifest = json.loads(paths["figure_manifest"].read_text(encoding="utf-8"))
    if figure_manifest.get("figure_count") != 9:
        raise ValueError("nine M5E-E figures are required")
    for entry in figure_manifest["figures"]:
        figure_path = figure_root / entry["filename"]
        if not figure_path.exists():
            raise FileNotFoundError(f"missing figure: {figure_path}")
        digest = hashlib.sha256(figure_path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"figure hash mismatch: {entry['filename']}")
        if entry.get("sample_unit") != "episode":
            raise ValueError("figure sample unit must be episode")
    summary = {
        "passed": True,
        "episodes": len(episode_identities),
        "primary_pairs": len(primary_pairs),
        "primary_comparisons": len(primary_bootstrap),
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "figures": figure_manifest["figure_count"],
        "recomputed": True,
    }
    (analysis_root / "m5e_e_validation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = _parser().parse_args()
    summary = validate_outputs(
        (PROJECT_ROOT / args.formal_root).resolve(),
        (PROJECT_ROOT / args.analysis_root).resolve(),
        (PROJECT_ROOT / args.figure_root).resolve(),
    )
    print(
        "M5E-E validation passed: "
        f"episodes={summary['episodes']} primary_pairs={summary['primary_pairs']} "
        f"bootstrap_iterations={summary['bootstrap_iterations']} "
        f"figures={summary['figures']} recomputed={summary['recomputed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
