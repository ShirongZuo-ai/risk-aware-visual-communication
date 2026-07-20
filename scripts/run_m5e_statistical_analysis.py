"""Run the frozen M5E-E episode-level statistical analysis and diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_statistical_analysis_common import write_analysis_tables
from scripts.plot_m5e_statistical_diagnostics import write_figures


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
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    formal_root = (PROJECT_ROOT / args.formal_root).resolve()
    analysis_root = (PROJECT_ROOT / args.analysis_root).resolve()
    figure_root = (PROJECT_ROOT / args.figure_root).resolve()
    built = write_analysis_tables(
        formal_root,
        analysis_root,
        overwrite=args.overwrite,
    )
    figures = write_figures(
        analysis_root,
        figure_root,
        overwrite=args.overwrite,
    )
    print(
        "M5E-E analysis completed: "
        f"episodes={built['summary']['episode_count']} "
        f"primary_pairs={built['summary']['primary_pair_count']} "
        f"bootstrap_iterations={built['summary']['bootstrap']['iterations']} "
        f"figures={len(figures)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
