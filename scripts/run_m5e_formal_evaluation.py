"""Run M5E-D formal offline quality evaluation on the frozen formal dataset."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import resolve_output_root
from scripts.m5e_formal_evaluation_common import write_formal_evaluation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/m5e_formal")
    parser.add_argument("--calibration-root", default="data/m5e_calibration")
    parser.add_argument("--allow-subset", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    output_root = resolve_output_root(args.output_root)
    calibration_root = resolve_output_root(args.calibration_root)
    metadata = write_formal_evaluation(output_root, calibration_root, allow_subset=args.allow_subset, overwrite=args.overwrite)
    print(
        "M5E-D formal evaluation passed: "
        f"frames={metadata['frame_count']} reconstructions={metadata['reconstruction_count']} "
        f"over_budget={metadata['over_budget_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
