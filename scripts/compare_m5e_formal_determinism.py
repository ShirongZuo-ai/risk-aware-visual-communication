"""Compare two M5E-D formal evaluation runs for deterministic byte/metric identity."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import resolve_output_root
from scripts.m5e_formal_evaluation_common import formal_paths, read_csv_rows


COMPARE_FIELDS = [
    "source_frame_sha256",
    "mask_sha256",
    "combined_mask_sha256",
    "config_hash",
    "metadata_normalized_sha256",
    "allocation_identity_sha256",
    "target_bytes",
    "actual_total_bytes",
    "unused_bytes",
    "container_sha256",
    "reconstruction_sha256",
    "full_mse",
    "full_psnr_db",
    "full_ssim",
    "risk_sum",
    "risk_weighted_mse",
    "risk_weighted_psnr_db",
    "object_mse",
    "risk_support_mse",
    "high_risk_mse",
    "background_mse",
    "tile_qualities_json",
    "tile_payload_bytes_json",
]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", default="data/m5e_formal")
    parser.add_argument("--repeat-root", required=True)
    return parser


def _key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (row["scenario_id"], row["original_seed"], row["snapshot_index"], row["method"], row["budget_label"])


def compare(reference_root: Path, repeat_root: Path) -> dict[str, int]:
    reference_rows = {_key(row): row for row in read_csv_rows(formal_paths(reference_root)["metrics_csv"])}
    repeat_rows = {_key(row): row for row in read_csv_rows(formal_paths(repeat_root)["metrics_csv"])}
    shared = sorted(set(reference_rows) & set(repeat_rows))
    if not shared:
        raise ValueError("no shared formal frame-method-budget rows to compare")
    errors = []
    for key in shared:
        left = reference_rows[key]
        right = repeat_rows[key]
        for field in COMPARE_FIELDS:
            if left[field] != right[field]:
                errors.append(f"{key} {field}: {left[field]!r} != {right[field]!r}")
                if len(errors) >= 20:
                    raise ValueError("determinism comparison failed: " + "; ".join(errors))
    if errors:
        raise ValueError("determinism comparison failed: " + "; ".join(errors))
    return {"reference_rows": len(reference_rows), "repeat_rows": len(repeat_rows), "shared_rows": len(shared)}


def main() -> int:
    args = _parser().parse_args()
    summary = compare(resolve_output_root(args.reference_root), resolve_output_root(args.repeat_root))
    print(
        "M5E-D formal determinism comparison passed: "
        f"reference_rows={summary['reference_rows']} repeat_rows={summary['repeat_rows']} shared_rows={summary['shared_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
