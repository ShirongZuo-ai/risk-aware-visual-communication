"""Generate M5E-B smoke diagnostics without compression or quality metrics."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import load_json, resolve_output_root  # noqa: E402
from scripts.m4d_image_risk_common import decode_masks_json  # noqa: E402
from scripts.validate_m5e_dataset import validate_dataset  # noqa: E402


SCENARIOS = ("S2", "S3", "S5", "S7")


def _snapshot_two(output_root: Path, scenario: str) -> dict:
    summary_path = next((output_root / "metadata" / "m5e" / "smoke" / scenario).glob("*/episode_summary.json"))
    summary = load_json(summary_path)
    return load_json(PROJECT_ROOT / summary["snapshots"][2]["metadata_path"])


def generate_plots(output_root: Path, result_root: Path) -> tuple[Path, Path]:
    validate_dataset(output_root)
    result_root.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(len(SCENARIOS), 3, figsize=(12, 13), constrained_layout=True)
    for row, scenario in enumerate(SCENARIOS):
        metadata = _snapshot_two(output_root, scenario)
        frame = np.asarray(Image.open(PROJECT_ROOT / metadata["frame_path"]).convert("RGB"))
        masks = decode_masks_json(load_json(PROJECT_ROOT / metadata["masks_path"])["masks"])
        combined = np.asarray(masks.combined.values).reshape(masks.combined.height_px, masks.combined.width_px)
        axes[row, 0].imshow(frame)
        axes[row, 0].set_title(f"{scenario} RGB, p={metadata['actual_progress']:.3f}")
        axes[row, 1].imshow(frame)
        image = axes[row, 1].imshow(combined, cmap="inferno", vmin=0.0, vmax=1.0, alpha=0.62)
        axes[row, 1].set_title("Combined image-risk mask")
        planned = metadata["planned_trajectory_points"]
        state = metadata["state_trajectory_points"]
        axes[row, 2].plot([item["x"] for item in planned], [item["y"] for item in planned], label="planned", linewidth=2)
        axes[row, 2].plot([item["x"] for item in state], [item["y"] for item in state], label="state", linewidth=2)
        for obstacle in metadata["obstacles"]:
            if not obstacle["eligible_for_mask"]:
                continue
            axes[row, 2].scatter(obstacle["center_x"], obstacle["center_y"], s=35 + 120 * obstacle["combined_risk"], label=obstacle["role"])
        axes[row, 2].set_aspect("equal", adjustable="datalim")
        axes[row, 2].set_xlabel("world x (m)")
        axes[row, 2].set_ylabel("world y (m)")
        axes[row, 2].set_title(f"Trajectories, disagreement={metadata['trajectory_disagreement_m']:.3f} m")
        axes[row, 2].legend(fontsize=7, loc="best")
        for column in (0, 1):
            axes[row, column].axis("off")
    figure.colorbar(image, ax=axes[:, 1], label="Heuristic image-risk score [0,1]", shrink=0.75)
    diagnostics = result_root / "m5e_scenario_diagnostics.png"
    figure.savefig(diagnostics, dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    for scenario in (f"S{index}" for index in range(1, 9)):
        summary_path = next((output_root / "metadata" / "m5e" / "smoke" / scenario).glob("*/episode_summary.json"))
        summary = load_json(summary_path)
        points = [load_json(PROJECT_ROOT / item["metadata_path"]) for item in summary["snapshots"]]
        axis.plot([item["target_progress"] for item in points], [item["actual_progress"] for item in points], marker="o", label=scenario)
    axis.plot((0.15, 0.95), (0.15, 0.95), color="black", linestyle="--", linewidth=1, label="target")
    axis.set_xlabel("Target reference progress")
    axis.set_ylabel("Captured reference progress")
    axis.set_title("Method-independent deterministic snapshot crossings")
    axis.legend(ncol=3, fontsize=8)
    progress = result_root / "m5e_snapshot_progress.png"
    figure.savefig(progress, dpi=180)
    plt.close(figure)
    return diagnostics, progress


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data")
    parser.add_argument("--result-root", default="results/m5_compression/m5e_smoke")
    args = parser.parse_args()
    try:
        outputs = generate_plots(resolve_output_root(args.output_root), resolve_output_root(args.result_root))
    except Exception as error:
        print(f"M5E diagnostic plot generation failed: {error}")
        return 1
    print("M5E diagnostic plots generated: " + ", ".join(str(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
