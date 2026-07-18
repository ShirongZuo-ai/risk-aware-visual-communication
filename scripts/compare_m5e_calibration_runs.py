"""Compare two complete M5E-C calibration runs without using quality metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_calibration_common import calibration_paths, output_root_from_argument
from scripts.m5e_dataset_common import load_json, read_manifest


def _normalized_manifest(root: Path) -> list[dict[str, str]]:
    records = []
    for row in read_manifest(root):
        metadata = load_json(PROJECT_ROOT / row["metadata_path"])
        normalized_metadata = dict(metadata)
        for field in ("frame_path", "masks_path", "frame_sha256", "masks_sha256"):
            normalized_metadata.pop(field, None)
        records.append(
            {
                "scenario_id": row["scenario_id"], "episode_id": row["episode_id"], "snapshot_index": row["snapshot_index"],
                "frame_sha256": row["frame_sha256"], "mask_sha256": row["mask_sha256"],
                "combined_mask_sha256": row["combined_mask_sha256"], "config_hash": metadata["config_hash"],
                "normalized_metadata": normalized_metadata,
            }
        )
    return records


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first")
    parser.add_argument("second")
    args = parser.parse_args()
    try:
        first = output_root_from_argument(args.first)
        second = output_root_from_argument(args.second)
        comparisons = {
            "source_frame_mask_config_metadata": _normalized_manifest(first) == _normalized_manifest(second),
            "feasible_ranges": _load(calibration_paths(first)["ranges"]) == _load(calibration_paths(second)["ranges"]),
            "frozen_budgets": {
                key: value for key, value in _load(calibration_paths(first)["budget_manifest"]).items() if key not in {"generated_at", "git_commit"}
            } == {
                key: value for key, value in _load(calibration_paths(second)["budget_manifest"]).items() if key not in {"generated_at", "git_commit"}
            },
            "allocations": _load(calibration_paths(first)["allocations"]) == _load(calibration_paths(second)["allocations"]),
        }
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"M5E calibration comparison failed: {error}")
        return 1
    failed = [name for name, matched in comparisons.items() if not matched]
    if failed:
        print(f"M5E calibration comparison failed: {', '.join(failed)}")
        return 1
    print("M5E calibration comparison passed: source/masks/config/metadata/ranges/budgets/allocations identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
