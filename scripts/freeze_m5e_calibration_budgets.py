"""Measure M5E-C actual-byte ranges and freeze common calibration-only budgets."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_calibration_common import (
    CALIBRATION_PROTOCOL_VERSION,
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
from simulator.m5e_config import primary_seed, primary_seed_indices


def _git_commit() -> str:
    result = subprocess.run(
        [r"C:\Program Files\Git\cmd\git.exe", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout.strip()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_ranges_csv(path: Path, ranges: list[dict]) -> None:
    fields = [
        "frame_id", "scenario_id", "episode_id", "snapshot_index", "method", "minimum_actual_bytes",
        "maximum_actual_bytes", "minimum_allocation", "maximum_allocation", "candidate_count",
        "source_frame_sha256", "mask_sha256", "config_hash", "codec_version", "container_version",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in ranges:
            row = dict(item)
            row["minimum_allocation"] = json.dumps(row["minimum_allocation"], sort_keys=True, separators=(",", ":"))
            row["maximum_allocation"] = json.dumps(row["maximum_allocation"], sort_keys=True, separators=(",", ":"))
            writer.writerow(row)


def _write_allocations_csv(path: Path, records: list[dict]) -> None:
    fields = [
        "frame_id", "scenario_id", "episode_id", "snapshot_index", "method", "budget_id", "target_bytes",
        "actual_total_bytes", "unused_bytes", "utilization", "selected_allocation", "tile_qualities",
        "candidate_count", "deterministic_tie_break", "source_frame_sha256", "mask_sha256", "config_hash",
        "actual_future_trajectory_used",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in records:
            row = dict(item)
            row["selected_allocation"] = json.dumps(row["selected_allocation"], sort_keys=True, separators=(",", ":"))
            row["tile_qualities"] = json.dumps(row["tile_qualities"], separators=(",", ":"))
            row["actual_future_trajectory_used"] = str(row["actual_future_trajectory_used"]).lower()
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/m5e_calibration")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output_root = output_root_from_argument(args.output_root)
    paths = calibration_paths(output_root)
    existing = tuple(path for name, path in paths.items() if name != "root" and path.exists())
    if existing and not args.overwrite:
        print(f"Refusing to overwrite calibration analysis: {existing[0]}")
        return 2
    try:
        rows = calibration_rows(output_root)
        ranges = calculate_feasible_ranges(rows)
        lower, upper, lower_witness, upper_witness = common_interval(ranges)
        budgets = frozen_budgets(lower, upper)
        records = match_all_budgets(rows, budgets)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"M5E calibration freeze failed: {error}")
        return 1
    range_records = [range_json(item) for item in ranges]
    lower_record = range_json(lower_witness)
    upper_record = range_json(upper_witness)
    if any(record["actual_total_bytes"] > record["target_bytes"] for record in records):
        print("M5E calibration freeze failed: an allocation exceeds its target")
        return 1
    manifest = {
        "schema_version": 1,
        "calibration_protocol_version": CALIBRATION_PROTOCOL_VERSION,
        "codec_version": "tiled-jpeg-pillow-12.3.0",
        "container_version": "RAVCJT1-v1",
        "scenario_count": 8,
        "episode_count": 16,
        "frame_count": 64,
        "method_count": len(METHOD_ORDER),
        "calibration_seeds": {
            f"S{scenario_index}": [primary_seed("calibration", scenario_index, seed_index) for seed_index in primary_seed_indices("calibration")]
            for scenario_index in range(1, 9)
        },
        "L_common": lower,
        "U_common": upper,
        "common_interval_width_bytes": upper - lower,
        "rounding_rule": "floor(L_common + fraction * (U_common - L_common)) for fractions severe=0.05, low=0.25, medium=0.50, high=0.80",
        "severe_bytes": budgets["severe"],
        "low_bytes": budgets["low"],
        "medium_bytes": budgets["medium"],
        "high_bytes": budgets["high"],
        "lower_bound_witness": lower_record,
        "upper_bound_witness": upper_record,
        "range_record_hash": records_hash(range_records),
        "allocation_record_hash": records_hash(records),
        "allocation_count": len(records),
        "actual_future_trajectory_used": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "calibration_only": True,
        "formal_evaluation_started": False,
        "method_performance_compared": False,
    }
    _write_json(paths["ranges"], range_records)
    _write_ranges_csv(paths["ranges_csv"], range_records)
    _write_json(paths["allocations"], records)
    _write_allocations_csv(paths["allocation_csv"], records)
    _write_json(paths["budget_manifest"], manifest)
    utilization = [float(item["utilization"]) for item in records]
    print(
        "M5E calibration freeze passed: "
        f"ranges={len(range_records)} allocations={len(records)} "
        f"common=[{lower},{upper}] budgets={budgets} utilization=[{min(utilization):.6f},{max(utilization):.6f}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
