"""Evaluate Milestone 2 trajectory predictors and generate figures."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import statistics
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from navigation.trajectory_prediction import (
    CommandSegment,
    EPUCK_ROBOT_HALF_WIDTH_M,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
)
from navigation.trajectory_uncertainty import ErrorSample, summarize_corridors


HORIZONS_S = (0.5, 1.0, 2.0)
STEP_S = 0.032
TRANSITIONS = (
    (4.0, "transition_straight_to_left"),
    (8.0, "transition_left_to_right"),
    (12.0, "transition_right_to_stop"),
)
PHASE_INTERVALS = {
    "stable_straight": (0.0, 4.0),
    "stable_left_turn": (4.0, 8.0),
    "stable_right_turn": (8.0, 12.0),
    "stable_stop": (12.0, 16.0),
}
METHODS = ("state_only", "command_conditioned")


@dataclass(frozen=True)
class Row:
    sim_time_s: float
    motion_phase: str
    x: float
    y: float
    yaw: float
    linear_velocity: float
    angular_velocity: float
    left_command: float
    right_command: float


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def angle_delta(a: float, b: float) -> float:
    return normalize_angle(b - a)


def read_rows(csv_path: Path) -> list[Row]:
    rows = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                Row(
                    sim_time_s=float(raw["sim_time_s"]),
                    motion_phase=raw["motion_phase"],
                    x=float(raw["robot_x"]),
                    y=float(raw["robot_y"]),
                    yaw=float(raw["yaw_rad"]),
                    linear_velocity=float(raw["linear_velocity_m_s"]),
                    angular_velocity=float(raw["angular_velocity_rad_s"]),
                    left_command=float(raw["left_wheel_command_rad_s"]),
                    right_command=float(raw["right_wheel_command_rad_s"]),
                )
            )
    if len(rows) < 2:
        raise ValueError("M2 CSV must contain at least two rows")
    return rows


def interpolate_actual(rows: list[Row], target_time: float) -> Row | None:
    if target_time < rows[0].sim_time_s or target_time > rows[-1].sim_time_s:
        return None
    for index in range(len(rows) - 1):
        a = rows[index]
        b = rows[index + 1]
        if a.sim_time_s <= target_time <= b.sim_time_s:
            if math.isclose(target_time, a.sim_time_s):
                return a
            if math.isclose(target_time, b.sim_time_s):
                return b
            ratio = (target_time - a.sim_time_s) / (b.sim_time_s - a.sim_time_s)
            yaw = normalize_angle(a.yaw + angle_delta(a.yaw, b.yaw) * ratio)
            return Row(
                sim_time_s=target_time,
                motion_phase=a.motion_phase,
                x=a.x + (b.x - a.x) * ratio,
                y=a.y + (b.y - a.y) * ratio,
                yaw=yaw,
                linear_velocity=a.linear_velocity + (b.linear_velocity - a.linear_velocity) * ratio,
                angular_velocity=a.angular_velocity + (b.angular_velocity - a.angular_velocity) * ratio,
                left_command=a.left_command,
                right_command=a.right_command,
            )
    return None


def category_for_window(start_time: float, horizon_s: float) -> str | None:
    end_time = start_time + horizon_s
    for category, (start, end) in PHASE_INTERVALS.items():
        if start_time >= start and end_time <= end:
            return category
    for boundary, category in TRANSITIONS:
        if start_time < boundary < end_time:
            return category
    return None


def command_at_time(absolute_time: float) -> tuple[float, float]:
    if absolute_time < 4.0:
        return 2.0, 2.0
    if absolute_time < 8.0:
        return -1.5, 1.5
    if absolute_time < 12.0:
        return 1.5, -1.5
    return 0.0, 0.0


def command_segments_for_window(start_time: float, horizon_s: float) -> list[CommandSegment]:
    boundaries = [0.0, 4.0, 8.0, 12.0, 16.0]
    absolute_start = start_time
    absolute_end = start_time + horizon_s
    segments: list[CommandSegment] = []
    cursor = absolute_start
    for boundary in boundaries[1:]:
        if cursor >= absolute_end:
            break
        segment_end = min(absolute_end, boundary)
        if segment_end > cursor:
            left, right = command_at_time(cursor + 1e-12)
            segments.append(CommandSegment(cursor - absolute_start, segment_end - absolute_start, left, right))
            cursor = segment_end
    if cursor < absolute_end:
        left, right = command_at_time(cursor + 1e-12)
        segments.append(CommandSegment(cursor - absolute_start, absolute_end - absolute_start, left, right))
    return segments


def aggregate_category(category: str) -> str:
    if category.startswith("stable_"):
        return "all_stable"
    if category.startswith("transition_"):
        return "all_transition"
    return category


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def evaluate(rows: list[Row], output_dir: Path) -> tuple[list[dict[str, str]], list[ErrorSample], list[dict]]:
    window_results: list[dict] = []
    error_samples: list[ErrorSample] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in rows:
        for horizon in HORIZONS_S:
            category = category_for_window(row.sim_time_s, horizon)
            if not category:
                continue
            if row.sim_time_s + horizon > rows[-1].sim_time_s:
                continue

            methods = {
                "state_only": lambda: predict_state_only_trajectory(
                    x=row.x,
                    y=row.y,
                    yaw_rad=row.yaw,
                    linear_velocity_m_s=row.linear_velocity,
                    angular_velocity_rad_s=row.angular_velocity,
                    horizon_s=horizon,
                    step_s=STEP_S,
                ),
                "command_conditioned": lambda: predict_command_conditioned_trajectory(
                    x=row.x,
                    y=row.y,
                    yaw_rad=row.yaw,
                    command_segments=command_segments_for_window(row.sim_time_s, horizon),
                    horizon_s=horizon,
                    step_s=STEP_S,
                ),
            }
            for method, predictor in methods.items():
                start_ns = time.perf_counter_ns()
                predicted = predictor()
                elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

                position_errors = []
                yaw_errors = []
                valid_points = 0
                for point in predicted:
                    actual = interpolate_actual(rows, row.sim_time_s + point.time_offset_s)
                    if not actual:
                        continue
                    error = math.hypot(point.x - actual.x, point.y - actual.y)
                    position_errors.append(error)
                    yaw_error = abs(angle_delta(point.yaw_rad, actual.yaw))
                    yaw_errors.append(yaw_error)
                    valid_points += 1
                    error_samples.append(
                        ErrorSample(method, horizon, category, point.time_offset_s, error)
                    )

                if not position_errors:
                    continue
                window_results.append(
                    {
                        "method": method,
                        "horizon_s": horizon,
                        "category": category,
                        "start_time_s": row.sim_time_s,
                        "ade_m": mean(position_errors),
                        "fde_m": position_errors[-1],
                        "yaw_mae_rad": mean(yaw_errors),
                        "valid_points": valid_points,
                        "compute_time_ms": elapsed_ms,
                    }
                )

    summary = summarize_window_results(window_results)
    write_csv(output_dir / "window_results.csv", window_results)
    write_csv(output_dir / "summary_metrics.csv", summary)
    corridor_stats = summarize_corridors(error_samples, horizons_s=HORIZONS_S, methods=METHODS)
    write_csv(output_dir / "uncertainty_corridors.csv", [stats.__dict__ for stats in corridor_stats])
    return summary, error_samples, window_results


def summarize_window_results(window_results: list[dict]) -> list[dict[str, str]]:
    categories = [
        "stable_straight",
        "stable_left_turn",
        "stable_right_turn",
        "stable_stop",
        "transition_straight_to_left",
        "transition_left_to_right",
        "transition_right_to_stop",
        "all_stable",
        "all_transition",
    ]
    summary = []
    for method in METHODS:
        for horizon in HORIZONS_S:
            for category in categories:
                if category.startswith("all_"):
                    selected = [
                        item
                        for item in window_results
                        if item["method"] == method
                        and math.isclose(item["horizon_s"], horizon)
                        and aggregate_category(item["category"]) == category
                    ]
                else:
                    selected = [
                        item
                        for item in window_results
                        if item["method"] == method
                        and math.isclose(item["horizon_s"], horizon)
                        and item["category"] == category
                    ]
                if not selected:
                    continue
                summary.append(
                    {
                        "method": method,
                        "horizon_s": f"{horizon:.1f}",
                        "category": category,
                        "window_count": str(len(selected)),
                        "ade_mean_m": f"{mean([item['ade_m'] for item in selected]):.9f}",
                        "fde_mean_m": f"{mean([item['fde_m'] for item in selected]):.9f}",
                        "yaw_mae_mean_rad": f"{mean([item['yaw_mae_rad'] for item in selected]):.9f}",
                        "compute_time_mean_ms": f"{mean([item['compute_time_ms'] for item in selected]):.9f}",
                    }
                )
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def find_representative_window(window_results: list[dict], method: str, category: str, horizon_s: float) -> float:
    candidates = [
        item for item in window_results
        if item["method"] == method and item["category"] == category and math.isclose(item["horizon_s"], horizon_s)
    ]
    if not candidates:
        raise ValueError(f"no representative window for {method} {category} {horizon_s}")
    return candidates[len(candidates) // 2]["start_time_s"]


def trajectory_for_plot(rows: list[Row], start_time: float, horizon_s: float):
    row = min(rows, key=lambda candidate: abs(candidate.sim_time_s - start_time))
    state = predict_state_only_trajectory(
        x=row.x,
        y=row.y,
        yaw_rad=row.yaw,
        linear_velocity_m_s=row.linear_velocity,
        angular_velocity_rad_s=row.angular_velocity,
        horizon_s=horizon_s,
        step_s=STEP_S,
    )
    command = predict_command_conditioned_trajectory(
        x=row.x,
        y=row.y,
        yaw_rad=row.yaw,
        command_segments=command_segments_for_window(row.sim_time_s, horizon_s),
        horizon_s=horizon_s,
        step_s=STEP_S,
    )
    actual = [interpolate_actual(rows, row.sim_time_s + point.time_offset_s) for point in state]
    actual = [point for point in actual if point]
    return row, state, command, actual


def plot_results(rows: list[Row], summary: list[dict], error_samples: list[ErrorSample], window_results: list[dict], output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    def plot_window(filename: str, start_time: float, horizon_s: float, title: str, corridor_radius: float | None = None):
        row, state, command, actual = trajectory_for_plot(rows, start_time, horizon_s)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot([p.x for p in actual], [p.y for p in actual], "k-", label="actual")
        ax.plot([p.x for p in state], [p.y for p in state], "b--", label="state-only")
        ax.plot([p.x for p in command], [p.y for p in command], "g--", label="command-conditioned")
        ax.scatter([row.x], [row.y], c="red", label="current")
        if corridor_radius is not None:
            for point in command[:: max(1, len(command) // 12)]:
                ax.add_patch(Circle((point.x, point.y), corridor_radius, fill=False, color="green", alpha=0.18))
        for boundary, label in TRANSITIONS:
            if row.sim_time_s < boundary < row.sim_time_s + horizon_s:
                ax.axvline(row.x, color="gray", alpha=0.1)
                ax.text(row.x, row.y, label, fontsize=8)
        state_metrics = [item for item in window_results if item["method"] == "state_only" and math.isclose(item["start_time_s"], row.sim_time_s) and math.isclose(item["horizon_s"], horizon_s)]
        command_metrics = [item for item in window_results if item["method"] == "command_conditioned" and math.isclose(item["start_time_s"], row.sim_time_s) and math.isclose(item["horizon_s"], horizon_s)]
        subtitle = ""
        if state_metrics and command_metrics:
            subtitle = (
                f"State ADE/FDE={state_metrics[0]['ade_m']:.4f}/{state_metrics[0]['fde_m']:.4f} m; "
                f"Cmd ADE/FDE={command_metrics[0]['ade_m']:.4f}/{command_metrics[0]['fde_m']:.4f} m"
            )
        ax.set_title(f"{title}\n{subtitle}")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.axis("equal")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=160)
        plt.close(fig)

    straight_start = find_representative_window(window_results, "state_only", "stable_straight", 1.0)
    transition_start = find_representative_window(window_results, "command_conditioned", "transition_left_to_right", 2.0)
    corridor_rows = read_csv_dicts(output_dir / "uncertainty_corridors.csv")
    command_2s = next(
        (row for row in corridor_rows if row["method"] == "command_conditioned" and row["horizon_s"] == "2.0" and row["status"] == "ok"),
        None,
    )
    corridor_radius = float(command_2s["corridor_radius_m"]) if command_2s else EPUCK_ROBOT_HALF_WIDTH_M

    plot_window("state_only_straight_1s.png", straight_start, 1.0, "Stable straight 1s")
    plot_window("command_conditioned_transition_2s.png", transition_start, 2.0, "Transition left-to-right 2s")
    plot_window("uncertainty_corridor_example.png", transition_start, 2.0, "Command-conditioned corridor example", corridor_radius)

    fig, ax = plt.subplots(figsize=(8, 5))
    rows_1s = [row for row in summary if row["category"] in ("all_stable", "all_transition") and row["horizon_s"] in ("1.0", "2.0")]
    labels = []
    values = []
    colors = []
    for row in rows_1s:
        labels.append(f"{row['method']}\n{row['category']}\n{row['horizon_s']}s")
        values.append(float(row["ade_mean_m"]))
        colors.append("#4C78A8" if row["method"] == "state_only" else "#54A24B")
    ax.bar(range(len(values)), values, color=colors)
    ax.set_xticks(range(len(values)), labels, rotation=45, ha="right")
    ax.set_ylabel("Mean ADE (m)")
    ax.set_title("Method comparison by stable/transition windows")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "method_comparison_ade.png", dpi=160)
    plt.close(fig)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_m2_csv(root: Path) -> Path:
    candidates = sorted((root / "data" / "logs" / "m2").glob("trajectory_validation_episode_*.csv"))
    if not candidates:
        raise FileNotFoundError("no M2 validation CSV found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", help="M2 trajectory validation CSV")
    args = parser.parse_args()

    root = project_root()
    csv_path = Path(args.csv_path) if args.csv_path else latest_m2_csv(root)
    output_dir = root / "results" / "m2_trajectory"
    rows = read_rows(csv_path)
    summary, error_samples, window_results = evaluate(rows, output_dir)
    plot_results(rows, summary, error_samples, window_results, output_dir)
    print(f"Evaluated {csv_path}")
    print(f"Wrote results to {output_dir}")
    for item in summary:
        if item["category"] in ("all_stable", "all_transition"):
            print(
                f"{item['method']} horizon={item['horizon_s']} category={item['category']} "
                f"windows={item['window_count']} ADE={item['ade_mean_m']} "
                f"FDE={item['fde_mean_m']} yawMAE={item['yaw_mae_mean_rad']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
