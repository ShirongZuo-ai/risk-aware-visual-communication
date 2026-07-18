"""Print explainable trajectory/risk diagnostics from one saved M5E-B episode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import load_json, resolve_output_root  # noqa: E402


def _format_optional(value) -> str:
    return "none" if value is None else f"{float(value):.6f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_id", choices=tuple(f"S{index}" for index in range(1, 9)))
    parser.add_argument("--output-root", default="data")
    args = parser.parse_args()
    root = resolve_output_root(args.output_root)
    summaries = sorted((root / "metadata" / "m5e" / "smoke" / args.scenario_id).glob("*/episode_summary.json"))
    if len(summaries) != 1:
        print(f"expected one accepted episode, found {len(summaries)}")
        return 1
    summary = load_json(summaries[0])
    print(f"episode={summary['episode_id']} config_hash={summary['config_hash']}")
    for snapshot in summary["snapshots"]:
        metadata = load_json(PROJECT_ROOT / snapshot["metadata_path"])
        print(
            f"snapshot={metadata['snapshot_index']} progress={metadata['actual_progress']:.6f} "
            f"disagreement={metadata['trajectory_disagreement_m']:.6f} "
            f"lateral_separation={metadata['maximum_lateral_separation_m']:.6f} "
            f"planned_yaw={metadata['planned_yaw_change']:.6f} state_yaw={metadata['state_yaw_change']:.6f}"
        )
        print(
            f"  planned_ranking={metadata['planned_risk_ranking']} margin={_format_optional(metadata['planned_ranking_margin'])}; "
            f"state_ranking={metadata['state_risk_ranking']} margin={_format_optional(metadata['state_ranking_margin'])}"
        )
        for item in metadata["obstacles"]:
            print(
                f"  {item['obstacle_id']} role={item['role']} visibility={item['visibility_status']} "
                f"eligible={item['eligible_for_mask']} area={item['candidate_pixel_count']} "
                f"risk={item['planned_risk']:.6f}/{item['state_risk']:.6f}/{item['combined_risk']:.6f} "
                f"clearance={item['planned_clearance_m']:.6f}/{item['state_clearance_m']:.6f} "
                f"ttcf={_format_optional(item['planned_ttcf_s'])}/{_format_optional(item['state_ttcf_s'])} "
                f"overlap={item['planned_overlap_duration_s']:.6f}/{item['state_overlap_duration_s']:.6f} "
                f"nearest={item['planned_nearest']['nearest_index']}/{item['state_nearest']['nearest_index']} "
                f"written={item['planned_written_pixel_count']}/{item['state_written_pixel_count']}/{item['combined_written_pixel_count']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
