"""Compare two complete M5E-E runs after allowed timestamp normalization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_statistical_analysis_common import analysis_paths


CSV_FILES = (
    "episode_metrics",
    "paired_effects",
    "bootstrap_results",
    "scenario_diagnostics",
    "win_tie_loss",
    "figure_inputs",
)
JSON_FILES = (
    "statistical_summary",
    "analysis_manifest",
    "failure_log",
    "figure_manifest",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-analysis-root", required=True)
    parser.add_argument("--repeat-analysis-root", required=True)
    parser.add_argument("--reference-figure-root", required=True)
    parser.add_argument("--repeat-figure-root", required=True)
    return parser


def _normalize(value):
    if isinstance(value, dict):
        return {
            key: _normalize(item)
            for key, item in value.items()
            if key not in {"generated_timestamp_utc"}
        }
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def compare_runs(
    reference_analysis_root: Path,
    repeat_analysis_root: Path,
    reference_figure_root: Path,
    repeat_figure_root: Path,
) -> dict[str, int | bool]:
    reference = analysis_paths(reference_analysis_root)
    repeat = analysis_paths(repeat_analysis_root)
    for key in CSV_FILES:
        if reference[key].read_bytes() != repeat[key].read_bytes():
            raise ValueError(f"determinism mismatch in {reference[key].name}")
    for key in JSON_FILES:
        left = _normalize(json.loads(reference[key].read_text(encoding="utf-8")))
        right = _normalize(json.loads(repeat[key].read_text(encoding="utf-8")))
        if left != right:
            raise ValueError(f"determinism mismatch in {reference[key].name}")
    figure_manifest = json.loads(reference["figure_manifest"].read_text(encoding="utf-8"))
    for entry in figure_manifest["figures"]:
        left = reference_figure_root / entry["filename"]
        right = repeat_figure_root / entry["filename"]
        if left.read_bytes() != right.read_bytes():
            raise ValueError(f"determinism mismatch in figure {entry['filename']}")
    return {
        "passed": True,
        "csv_files": len(CSV_FILES),
        "json_files": len(JSON_FILES),
        "figures": len(figure_manifest["figures"]),
    }


def main() -> int:
    args = _parser().parse_args()
    summary = compare_runs(
        (PROJECT_ROOT / args.reference_analysis_root).resolve(),
        (PROJECT_ROOT / args.repeat_analysis_root).resolve(),
        (PROJECT_ROOT / args.reference_figure_root).resolve(),
        (PROJECT_ROOT / args.repeat_figure_root).resolve(),
    )
    print(
        "M5E-E deterministic comparison passed: "
        f"csv={summary['csv_files']} json={summary['json_files']} "
        f"figures={summary['figures']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
