"""Independently validate M5E-C calibration data, byte ranges, and frozen allocations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_calibration_common import (
    METHOD_ORDER,
    calibration_paths,
    calibration_rows,
    calculate_feasible_ranges,
    common_interval,
    frozen_budgets,
    match_all_budgets,
    output_root_from_argument,
    range_json,
    records_hash,
)
from scripts.m5e_dataset_common import load_json
from scripts.validate_m5e_dataset import validate_dataset


def validate_calibration(output_root: Path) -> dict:
    summaries = validate_dataset(output_root, split="calibration")
    rows = calibration_rows(output_root)
    paths = calibration_paths(output_root)
    range_records = load_json(paths["ranges"])
    allocation_records = load_json(paths["allocations"])
    manifest = load_json(paths["budget_manifest"])
    if not isinstance(range_records, list) or len(range_records) != 256:
        raise ValueError("feasible range record count must be 256")
    if not isinstance(allocation_records, list) or len(allocation_records) != 1024:
        raise ValueError("matched allocation record count must be 1024")
    if manifest["scenario_count"] != 8 or manifest["episode_count"] != 16 or manifest["frame_count"] != 64 or manifest["method_count"] != 4:
        raise ValueError("calibration manifest counts are incorrect")
    if manifest["actual_future_trajectory_used"] is not False or manifest["calibration_only"] is not True or manifest["formal_evaluation_started"] is not False:
        raise ValueError("calibration provenance flags are incorrect")
    calculated_ranges = calculate_feasible_ranges(rows)
    recomputed_ranges = [range_json(item) for item in calculated_ranges]
    if range_records != recomputed_ranges:
        raise ValueError("feasible range records are not independently reproducible")
    lower, upper, lower_witness, upper_witness = common_interval(calculated_ranges)
    budgets = frozen_budgets(lower, upper)
    if (manifest["L_common"], manifest["U_common"]) != (lower, upper):
        raise ValueError("common interval mismatch")
    if any(manifest[f"{label}_bytes"] != value for label, value in budgets.items()):
        raise ValueError("frozen budget mismatch")
    if manifest["lower_bound_witness"] != range_json(lower_witness) or manifest["upper_bound_witness"] != range_json(upper_witness):
        raise ValueError("common interval witness mismatch")
    if manifest["range_record_hash"] != records_hash(range_records):
        raise ValueError("range record hash mismatch")
    recomputed_allocations = match_all_budgets(rows, budgets)
    if allocation_records != recomputed_allocations:
        raise ValueError("allocation records are not independently reproducible")
    if manifest["allocation_record_hash"] != records_hash(allocation_records):
        raise ValueError("allocation record hash mismatch")
    if any(item["actual_total_bytes"] > item["target_bytes"] for item in allocation_records):
        raise ValueError("allocation exceeds target budget")
    expected_keys = {
        (row["frame_id"], method, budget_id)
        for row in rows
        for method in METHOD_ORDER
        for budget_id in budgets
    }
    observed_keys = {(item["frame_id"], item["method"], item["budget_id"]) for item in allocation_records}
    if observed_keys != expected_keys:
        raise ValueError("allocation matrix identities are incomplete or duplicated")
    return {
        "episodes": len(summaries), "frames": len(rows), "ranges": len(range_records), "allocations": len(allocation_records),
        "L_common": lower, "U_common": upper, "budgets": budgets,
        "minimum_utilization": min(float(item["utilization"]) for item in allocation_records),
        "maximum_utilization": max(float(item["utilization"]) for item in allocation_records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/m5e_calibration")
    args = parser.parse_args()
    try:
        result = validate_calibration(output_root_from_argument(args.output_root))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"M5E calibration validation failed: {error}")
        return 1
    print(
        "M5E calibration validation passed: "
        f"episodes={result['episodes']} frames={result['frames']} ranges={result['ranges']} allocations={result['allocations']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
