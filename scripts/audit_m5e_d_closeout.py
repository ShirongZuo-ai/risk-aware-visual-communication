"""Read-only M5E-D closeout audit and descriptive summary generator.

The script deliberately never writes below ``data/m5e_formal``.  It checks the
frozen matrix as stored, verifies every decoded PNG is readable, and writes a
small reproducible summary outside the formal-data root.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = PROJECT_ROOT / "data" / "m5e_formal"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "results" / "m5e_d_closeout_summary.json"
METHODS = ("uniform", "center_roi", "object_roi", "risk_roi")
BUDGETS = {"severe": 31466, "low": 32374, "medium": 33509, "high": 34871}
SCENES = tuple(f"S{index}" for index in range(1, 9))
KEY_FIELDS = ("frame_id", "method", "budget_label")
NUMERIC_FIELDS = (
    "actual_total_bytes", "unused_bytes", "utilization", "full_psnr_db", "full_ssim",
    "risk_weighted_psnr_db", "object_psnr_db", "risk_support_psnr_db", "background_psnr_db",
    "risk_sum", "object_fraction", "risk_support_fraction", "background_fraction",
    "risk_weighted_mean_quality", "total_tile_payload_bytes", "container_overhead_bytes",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _mean(rows: list[dict[str, str]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row[field] not in ("", "undefined")]
    return sum(values) / len(values) if values else None


def _group_summary(rows: list[dict[str, str]], fields: tuple[str, ...]) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    result: list[dict[str, object]] = []
    for key in sorted(groups):
        group = groups[key]
        item: dict[str, object] = dict(zip(fields, key, strict=True))
        item["n_reconstructions"] = len(group)
        for field in ("actual_total_bytes", "utilization", "full_psnr_db", "full_ssim", "risk_weighted_psnr_db", "object_psnr_db", "risk_support_psnr_db", "background_psnr_db", "risk_weighted_mean_quality"):
            value = _mean(group, field)
            item[f"mean_{field}"] = value
        result.append(item)
    return result


def audit(formal_root: Path = FORMAL_ROOT) -> dict[str, object]:
    evaluation = formal_root / "formal_evaluation"
    metrics_path = evaluation / "m5e_d_formal_quality_metrics.csv"
    allocations_path = evaluation / "m5e_d_formal_allocations.csv"
    manifest_path = formal_root / "logs" / "m5" / "m5e_dataset_manifest.csv"
    metrics = _read_csv(metrics_path)
    allocations = _read_csv(allocations_path)
    manifest = [row for row in _read_csv(manifest_path) if row["split"] == "formal"]
    errors: list[str] = []
    if len(manifest) != 256 or len({row["episode_id"] for row in manifest}) != 64:
        errors.append("formal manifest is not 64 episodes / 256 frames")
    if len(metrics) != 4096 or len(allocations) != 4096:
        errors.append("formal tables are not both 4096 rows")
    metric_keys = [tuple(row[field] for field in KEY_FIELDS) for row in metrics]
    allocation_keys = [tuple(row[field] for field in KEY_FIELDS) for row in allocations]
    if len(metric_keys) != len(set(metric_keys)) or len(allocation_keys) != len(set(allocation_keys)):
        errors.append("duplicate frame-method-budget key")
    if set(metric_keys) != set(allocation_keys):
        errors.append("allocation and metric keys differ")
    metric_frames = {row["frame_id"] for row in metrics}
    expected = {(frame_id, method, budget) for frame_id in metric_frames for method in METHODS for budget in BUDGETS}
    if set(metric_keys) != expected:
        errors.append("formal method-budget matrix has missing or unexpected keys")
    if {row["scenario_id"] for row in metrics} != set(SCENES):
        errors.append("formal scenes are incomplete")
    if {row["method"] for row in metrics} != set(METHODS) or {row["budget_label"] for row in metrics} != set(BUDGETS):
        errors.append("formal method or budget coverage differs from frozen protocol")
    replacements = sum(int(row["replacement_index"]) != 0 for row in metrics)
    fallbacks = sum(row.get("actual_future_trajectory_used") != "false" for row in metrics)
    bad_numbers = 0
    unreadable_pngs = 0
    missing_artifacts = 0
    byte_tolerance_violations = 0
    for row in metrics:
        for field in NUMERIC_FIELDS:
            if row[field] not in ("", "undefined") and not math.isfinite(float(row[field])):
                bad_numbers += 1
        if int(row["actual_total_bytes"]) > int(row["target_bytes"]):
            byte_tolerance_violations += 1
        for field in ("container_path", "decoded_png_path"):
            path = PROJECT_ROOT / row[field]
            if not path.is_file():
                missing_artifacts += 1
        png = PROJECT_ROOT / row["decoded_png_path"]
        if png.is_file():
            try:
                with Image.open(png) as image:
                    image.verify()
            except (OSError, ValueError):
                unreadable_pngs += 1
    if replacements or fallbacks or bad_numbers or unreadable_pngs or missing_artifacts or byte_tolerance_violations:
        errors.append("one or more row-level integrity checks failed")
    metadata = json.loads((evaluation / "m5e_d_formal_evaluation_metadata.json").read_text(encoding="utf-8"))
    summary = {
        "audit_type": "m5e-d-read-only-closeout-v1",
        "formal_root": str(formal_root.relative_to(PROJECT_ROOT)),
        "integrity_passed": not errors,
        "errors": errors,
        "counts": {"episodes": len({row["episode_id"] for row in manifest}), "formal_frames": len(manifest), "reconstructions": len(metrics), "scenes": len(SCENES), "methods": len(METHODS), "budgets": len(BUDGETS)},
        "integrity": {"replacement_records": replacements, "actual_future_trajectory_records": fallbacks, "duplicate_metric_keys": len(metric_keys) - len(set(metric_keys)), "missing_or_unexpected_matrix_keys": len(set(metric_keys) ^ expected), "nonfinite_numeric_cells": bad_numbers, "missing_artifacts": missing_artifacts, "unreadable_decoded_pngs": unreadable_pngs, "over_budget_records": byte_tolerance_violations},
        "metadata": {"reconstruction_count": metadata.get("reconstruction_count"), "over_budget_count": metadata.get("over_budget_count")},
        "coverage": {"scenes": sorted({row["scenario_id"] for row in metrics}), "methods": sorted({row["method"] for row in metrics}), "budgets": sorted({row["budget_label"] for row in metrics})},
        "by_method_budget": _group_summary(metrics, ("method", "budget_label")),
        "by_scene_method_budget": _group_summary(metrics, ("scenario_id", "method", "budget_label")),
        "worst_cases_by_risk_weighted_psnr": [
            {field: row[field] for field in ("frame_id", "scenario_id", "method", "budget_label", "risk_weighted_psnr_db", "full_psnr_db", "object_psnr_db", "actual_total_bytes", "target_bytes")}
            for row in sorted(metrics, key=lambda item: float(item["risk_weighted_psnr_db"]))[:10]
        ],
        "undefined_high_risk_metric_rows": sum(row["high_risk_psnr_db"] == "undefined" for row in metrics),
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-root", type=Path, default=FORMAL_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = audit(args.formal_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M5E-D read-only closeout audit {'passed' if summary['integrity_passed'] else 'failed'}: {args.output}")
    return 0 if summary["integrity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
