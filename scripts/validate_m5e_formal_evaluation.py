"""Validate the M5E-D formal dataset and offline quality evaluation outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import resolve_output_root, sha256_file
from scripts.m5e_formal_evaluation_common import (
    ALLOCATION_FIELDS,
    EXPECTED_FORMAL_EPISODES,
    EXPECTED_FORMAL_FRAMES,
    EXPECTED_FORMAL_RECONSTRUCTIONS,
    EXPECTED_FROZEN_BUDGETS,
    FORMAL_BUDGET_LABELS,
    METRIC_FIELDS,
    compare_rows_exact,
    ensure_formal_seed_schedule,
    evaluate_formal_rows,
    expected_result_count,
    formal_paths,
    formal_rows,
    load_frozen_budget_manifest,
    read_csv_rows,
)
from scripts.validate_m5e_dataset import validate_dataset
from scripts.m5e_calibration_common import METHOD_ORDER


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/m5e_formal")
    parser.add_argument("--calibration-root", default="data/m5e_calibration")
    parser.add_argument("--allow-subset", action="store_true")
    parser.add_argument("--skip-recompute", action="store_true")
    return parser


def _key(row: dict[str, str]) -> tuple[str, int, int, int, int]:
    return (
        row["scenario_id"],
        int(row["original_seed"]),
        int(row["snapshot_index"]),
        METHOD_ORDER.index(row["method"]),
        FORMAL_BUDGET_LABELS.index(row["budget_label"]),
    )


def validate_outputs(output_root: Path, calibration_root: Path, *, allow_subset: bool = False, recompute: bool = True) -> dict:
    dataset_summaries = validate_dataset(output_root, "formal", require_manifest=True, require_complete=not allow_subset)
    rows = formal_rows(output_root, allow_subset=allow_subset)
    ensure_formal_seed_schedule(rows, allow_subset=allow_subset)
    load_frozen_budget_manifest(calibration_root)
    paths = formal_paths(output_root)
    allocations = sorted(read_csv_rows(paths["allocation_csv"]), key=_key)
    metrics = sorted(read_csv_rows(paths["metrics_csv"]), key=_key)
    expected_count = expected_result_count(len(rows))
    if len(allocations) != expected_count or len(metrics) != expected_count:
        raise ValueError(f"formal result matrix is incomplete: allocations={len(allocations)} metrics={len(metrics)} expected={expected_count}")
    if not allow_subset and expected_count != EXPECTED_FORMAL_RECONSTRUCTIONS:
        raise ValueError("full formal reconstruction count invariant failed")
    if set(allocations[0]) != set(ALLOCATION_FIELDS) or set(metrics[0]) != set(METRIC_FIELDS):
        raise ValueError("formal CSV schema differs from the frozen M5E-D schema")
    keys = [(row["frame_id"], row["method"], row["budget_label"]) for row in metrics]
    if len(keys) != len(set(keys)):
        raise ValueError("formal metrics contain duplicate frame-method-budget rows")
    for row in metrics:
        if int(row["target_bytes"]) != EXPECTED_FROZEN_BUDGETS[row["budget_label"]]:
            raise ValueError("metric row target does not match frozen budget")
        if int(row["actual_total_bytes"]) > int(row["target_bytes"]):
            raise ValueError("metric row exceeds frozen budget")
        if row["actual_future_trajectory_used"] != "false":
            raise ValueError("formal metric row leaks actual future trajectory")
        container_path = PROJECT_ROOT / row["container_path"]
        decoded_path = PROJECT_ROOT / row["decoded_png_path"]
        if not container_path.exists() or not decoded_path.exists():
            raise FileNotFoundError("formal reconstruction artifact is missing")
        if sha256_file(container_path) != row["container_sha256"]:
            raise ValueError("formal container hash mismatch")
    metadata = json.loads(paths["run_metadata"].read_text(encoding="utf-8"))
    if metadata.get("reconstruction_count") != len(metrics) or metadata.get("over_budget_count") != 0:
        raise ValueError("formal run metadata count invariant failed")
    recompute_errors: list[str] = []
    if recompute:
        expected_allocations, expected_metrics = evaluate_formal_rows(rows, EXPECTED_FROZEN_BUDGETS, write_artifacts=False)
        recompute_errors.extend(compare_rows_exact(allocations, expected_allocations, ALLOCATION_FIELDS))
        comparable_fields = [field for field in METRIC_FIELDS if field not in ("container_path", "decoded_png_path")]
        recompute_errors.extend(compare_rows_exact(metrics, expected_metrics, comparable_fields))
        if recompute_errors:
            raise ValueError("formal evaluation recomputation mismatch: " + "; ".join(recompute_errors[:5]))
    summary = {
        "dataset_episodes": len(dataset_summaries),
        "episodes": len({row["episode_id"] for row in rows}),
        "frames": len(rows),
        "allocations": len(allocations),
        "metrics": len(metrics),
        "expected_full_episodes": EXPECTED_FORMAL_EPISODES,
        "expected_full_frames": EXPECTED_FORMAL_FRAMES,
        "expected_full_reconstructions": EXPECTED_FORMAL_RECONSTRUCTIONS,
        "over_budget_count": 0,
        "recomputed": recompute,
    }
    paths["validation_summary"].write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    args = _parser().parse_args()
    summary = validate_outputs(
        resolve_output_root(args.output_root),
        resolve_output_root(args.calibration_root),
        allow_subset=args.allow_subset,
        recompute=not args.skip_recompute,
    )
    print(
        "M5E-D formal validation passed: "
        f"episodes={summary['episodes']} frames={summary['frames']} metrics={summary['metrics']} "
        f"recomputed={summary['recomputed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
