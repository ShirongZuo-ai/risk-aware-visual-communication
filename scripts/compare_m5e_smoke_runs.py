"""Compare two independently generated M5E-B smoke datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import load_json, read_manifest, resolve_output_root, sha256_file  # noqa: E402
from scripts.validate_m5e_dataset import validate_dataset  # noqa: E402


PATH_KEYS = {"frame_path", "mask_path", "masks_path", "metadata_path", "summary_path"}


def _without_paths(value):
    if isinstance(value, dict):
        return {key: _without_paths(item) for key, item in value.items() if key not in PATH_KEYS}
    if isinstance(value, list):
        return [_without_paths(item) for item in value]
    return value


def _rows_by_identity(output_root: Path) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["scenario_id"], row["snapshot_index"]): row for row in read_manifest(output_root)}


def compare_runs(first_root: Path, second_root: Path) -> None:
    validate_dataset(first_root)
    validate_dataset(second_root)
    first = _rows_by_identity(first_root)
    second = _rows_by_identity(second_root)
    if first.keys() != second.keys():
        raise ValueError("dataset snapshot identities differ")
    for identity in sorted(first):
        left, right = first[identity], second[identity]
        if _without_paths(left) != _without_paths(right):
            raise ValueError(f"manifest values differ for {identity}")
        left_frame, right_frame = PROJECT_ROOT / left["frame_path"], PROJECT_ROOT / right["frame_path"]
        if sha256_file(left_frame) != sha256_file(right_frame):
            raise ValueError(f"frame bytes differ for {identity}")
        left_mask, right_mask = PROJECT_ROOT / left["mask_path"], PROJECT_ROOT / right["mask_path"]
        if left_mask.read_bytes() != right_mask.read_bytes():
            raise ValueError(f"float mask evidence differs for {identity}")
        left_metadata = load_json(PROJECT_ROOT / left["metadata_path"])
        right_metadata = load_json(PROJECT_ROOT / right["metadata_path"])
        if _without_paths(left_metadata) != _without_paths(right_metadata):
            raise ValueError(f"snapshot metadata differs for {identity}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first_root")
    parser.add_argument("second_root")
    args = parser.parse_args()
    try:
        compare_runs(resolve_output_root(args.first_root), resolve_output_root(args.second_root))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"M5E deterministic comparison failed: {error}")
        return 1
    print("M5E deterministic comparison passed: 32 frames, masks, configs, and metadata are identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
