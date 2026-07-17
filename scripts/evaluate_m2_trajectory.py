"""Evaluate Milestone 2 trajectory predictors and generate figures."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path
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
from navigation.trajectory_uncertainty import (
    ErrorSample,
    summarize_corridors,
    trajectory_corridor_disks,
)


HORIZONS_S = (0.5, 1.0, 2.0)
STEP_S = 0.032
TRANSITION_GUARD_START_S = 0.10
TRANSITION_GUARD_END_S = 0.20
METHODS = ("state_only", "command_conditioned")


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    start_s: float
    end_s: float
    left_command: float
    right_command: float


@dataclass(frozen=True)
class TransitionSpec:
    boundary_s: float
    category: str


@dataclass(frozen=True)
class EvaluationProfile:
    name: str
    description: str
    phases: tuple[PhaseSpec, ...]
    output_dir_name: str

    @property
    def transitions(self) -> tuple[TransitionSpec, ...]:
        transitions = []
        for previous, current in zip(self.phases, self.phases[1:]):
            transitions.append(
                TransitionSpec(
                    current.start_s,
                    f"transition_{previous.name.removeprefix('stable_')}_to_{current.name.removeprefix('stable_')}",
                )
            )
        return tuple(transitions)

    @property
    def categories(self) -> tuple[str, ...]:
        stable = tuple(phase.name for phase in self.phases)
        transitions = tuple(transition.category for transition in self.transitions)
        return stable + transitions + ("all_stable", "all_transition")


PROFILES = {
    "in_place": EvaluationProfile(
        name="in_place",
        description="in-place rotation validation",
        output_dir_name="m2_trajectory",
        phases=(
            PhaseSpec("stable_straight", 0.0, 4.0, 2.0, 2.0),
            PhaseSpec("stable_left_turn", 4.0, 8.0, -1.5, 1.5),
            PhaseSpec("stable_right_turn", 8.0, 12.0, 1.5, -1.5),
            PhaseSpec("stable_stop", 12.0, 16.0, 0.0, 0.0),
        ),
    ),
    "arc": EvaluationProfile(
        name="arc",
        description="forward arc validation",
        output_dir_name="m2_trajectory_arc",
        phases=(
            PhaseSpec("stable_straight", 0.0, 4.0, 2.0, 2.0),
            PhaseSpec("stable_forward_left_arc", 4.0, 8.0, 1.0, 2.0),
            PhaseSpec("stable_forward_right_arc", 8.0, 12.0, 2.0, 1.0),
            PhaseSpec("stable_stop", 12.0, 16.0, 0.0, 0.0),
        ),
    ),
}


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


def window_intersects(start_a: float, end_a: float, start_b: float, end_b: float) -> bool:
    return start_a < end_b and end_a > start_b


def category_for_window(start_time: float, horizon_s: float, profile: EvaluationProfile) -> str | None:
    end_time = start_time + horizon_s
    for transition in profile.transitions:
        guard_start = transition.boundary_s + TRANSITION_GUARD_START_S
        guard_end = transition.boundary_s + TRANSITION_GUARD_END_S
        if window_intersects(start_time, end_time, guard_start, guard_end):
            return transition.category
    for phase in profile.phases:
        stable_start = phase.start_s + TRANSITION_GUARD_END_S
        if start_time >= stable_start and end_time <= phase.end_s:
            return phase.name
    return None


def phase_at_time(absolute_time: float, profile: EvaluationProfile) -> PhaseSpec:
    for phase in profile.phases:
        if phase.start_s <= absolute_time < phase.end_s:
            return phase
    return profile.phases[-1]


def command_segments_for_window(start_time: float, horizon_s: float, profile: EvaluationProfile) -> list[CommandSegment]:
    absolute_end = start_time + horizon_s
    segments: list[CommandSegment] = []
    cursor = start_time
    while cursor < absolute_end - 1e-12:
        phase = phase_at_time(cursor + 1e-12, profile)
        segment_end = min(absolute_end, phase.end_s)
        if segment_end <= cursor:
            segment_end = absolute_end
        segments.append(
            CommandSegment(
                cursor - start_time,
                segment_end - start_time,
                phase.left_command,
                phase.right_command,
            )
        )
        cursor = segment_end
    return segments


def aggregate_category(category: str) -> str:
    if category.startswith("stable_"):
        return "all_stable"
    if category.startswith("transition_"):
        return "all_transition"
    return category


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def evaluate(
    rows: list[Row],
    output_dir: Path,
    profile: EvaluationProfile,
) -> tuple[list[dict[str, str]], list[ErrorSample], list[dict]]:
    window_results: list[dict] = []
    error_samples: list[ErrorSample] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in rows:
        for horizon in HORIZONS_S:
            category = category_for_window(row.sim_time_s, horizon, profile)
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
                    command_segments=command_segments_for_window(row.sim_time_s, horizon, profile),
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
                    yaw_errors.append(abs(angle_delta(point.yaw_rad, actual.yaw)))
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

    summary = summarize_window_results(window_results, profile)
    write_csv(output_dir / "window_results.csv", window_results)
    write_csv(output_dir / "summary_metrics.csv", summary)
    corridor_stats = summarize_corridors(error_samples, horizons_s=HORIZONS_S, methods=METHODS)
    write_csv(output_dir / "uncertainty_corridors.csv", [stats.__dict__ for stats in corridor_stats])
    return summary, error_samples, window_results


def summarize_window_results(window_results: list[dict], profile: EvaluationProfile) -> list[dict[str, str]]:
    summary = []
    for method in METHODS:
        for horizon in HORIZONS_S:
            for category in profile.categories:
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
        item
        for item in window_results
        if item["method"] == method
        and item["category"] == category
        and math.isclose(item["horizon_s"], horizon_s)
    ]
    if not candidates:
        raise ValueError(f"no representative window for {method} {category} {horizon_s}")
    return candidates[len(candidates) // 2]["start_time_s"]


def trajectory_for_plot(rows: list[Row], start_time: float, horizon_s: float, profile: EvaluationProfile):
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
        command_segments=command_segments_for_window(row.sim_time_s, horizon_s, profile),
        horizon_s=horizon_s,
        step_s=STEP_S,
    )
    actual = [interpolate_actual(rows, row.sim_time_s + point.time_offset_s) for point in state]
    actual = [point for point in actual if point]
    return row, state, command, actual


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot_window(
    *,
    rows: list[Row],
    window_results: list[dict],
    output_dir: Path,
    profile: EvaluationProfile,
    filename: str,
    start_time: float,
    horizon_s: float,
    title: str,
    corridor_radius: float | None = None,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    row, state, command, actual = trajectory_for_plot(rows, start_time, horizon_s, profile)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([p.x for p in actual], [p.y for p in actual], "k-", label="actual")
    ax.plot([p.x for p in state], [p.y for p in state], "b--", label="state-only")
    ax.plot([p.x for p in command], [p.y for p in command], "g--", label="command-conditioned")
    ax.scatter([row.x], [row.y], c="red", label="current")
    if corridor_radius is not None:
        for disk in trajectory_corridor_disks(command, corridor_radius):
            ax.add_patch(
                Circle(
                    (disk.center_x, disk.center_y),
                    disk.radius_m,
                    fill=True,
                    facecolor="green",
                    edgecolor="green",
                    alpha=0.045,
                    linewidth=0.4,
                )
            )
    state_metrics = [
        item
        for item in window_results
        if item["method"] == "state_only"
        and math.isclose(item["start_time_s"], row.sim_time_s)
        and math.isclose(item["horizon_s"], horizon_s)
    ]
    command_metrics = [
        item
        for item in window_results
        if item["method"] == "command_conditioned"
        and math.isclose(item["start_time_s"], row.sim_time_s)
        and math.isclose(item["horizon_s"], horizon_s)
    ]
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


def plot_method_comparison(summary: list[dict], output_dir: Path) -> None:
    import matplotlib.pyplot as plt

    rows = [
        row
        for row in summary
        if row["category"] in ("all_stable", "all_transition")
        and row["horizon_s"] in ("0.5", "1.0", "2.0")
    ]
    labels = [
        f"{row['method'].replace('_', '-')} {row['category'].replace('all_', '')} {row['horizon_s']}s"
        for row in rows
    ]
    values = [float(row["ade_mean_m"]) for row in rows]
    colors = ["#4C78A8" if row["method"] == "state_only" else "#54A24B" for row in rows]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(range(len(values)), values, color=colors)
    ax.set_yscale("log")
    ax.set_xticks(range(len(values)), labels, rotation=45, ha="right")
    ax.set_ylabel("Mean ADE (m), log scale")
    ax.set_title("Method comparison by stable and transition windows")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            value * 1.12,
            f"{value:.2e}",
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=90,
        )
    fig.tight_layout()
    fig.savefig(output_dir / "method_comparison_log_scale.png", dpi=170)
    plt.close(fig)


def plot_results(
    rows: list[Row],
    summary: list[dict],
    error_samples: list[ErrorSample],
    window_results: list[dict],
    output_dir: Path,
    profile: EvaluationProfile,
) -> None:
    _ = error_samples
    corridor_rows = read_csv_dicts(output_dir / "uncertainty_corridors.csv")
    command_2s = next(
        (
            row
            for row in corridor_rows
            if row["method"] == "command_conditioned"
            and row["horizon_s"] == "2.0"
            and row["status"] == "ok"
        ),
        None,
    )
    corridor_radius = float(command_2s["corridor_radius_m"]) if command_2s else EPUCK_ROBOT_HALF_WIDTH_M

    if profile.name == "arc":
        left_arc_start = find_representative_window(
            window_results, "state_only", "stable_forward_left_arc", 1.0
        )
        right_arc_start = find_representative_window(
            window_results, "state_only", "stable_forward_right_arc", 1.0
        )
        transition_start = find_representative_window(
            window_results,
            "command_conditioned",
            "transition_forward_left_arc_to_forward_right_arc",
            2.0,
        )
        plot_window(
            rows=rows,
            window_results=window_results,
            output_dir=output_dir,
            profile=profile,
            filename="forward_left_arc_1s.png",
            start_time=left_arc_start,
            horizon_s=1.0,
            title="Stable forward-left arc 1s",
        )
        plot_window(
            rows=rows,
            window_results=window_results,
            output_dir=output_dir,
            profile=profile,
            filename="forward_right_arc_1s.png",
            start_time=right_arc_start,
            horizon_s=1.0,
            title="Stable forward-right arc 1s",
        )
        plot_window(
            rows=rows,
            window_results=window_results,
            output_dir=output_dir,
            profile=profile,
            filename="arc_transition_2s.png",
            start_time=transition_start,
            horizon_s=2.0,
            title="Arc transition 2s",
        )
        plot_window(
            rows=rows,
            window_results=window_results,
            output_dir=output_dir,
            profile=profile,
            filename="arc_uncertainty_corridor.png",
            start_time=transition_start,
            horizon_s=2.0,
            title="Command-conditioned arc corridor",
            corridor_radius=corridor_radius,
        )
        plot_method_comparison(summary, output_dir)
        return

    straight_start = find_representative_window(window_results, "state_only", "stable_straight", 1.0)
    transition_start = find_representative_window(
        window_results, "command_conditioned", "transition_left_turn_to_right_turn", 2.0
    )
    plot_window(
        rows=rows,
        window_results=window_results,
        output_dir=output_dir,
        profile=profile,
        filename="state_only_straight_1s.png",
        start_time=straight_start,
        horizon_s=1.0,
        title="Stable straight 1s",
    )
    plot_window(
        rows=rows,
        window_results=window_results,
        output_dir=output_dir,
        profile=profile,
        filename="command_conditioned_transition_2s.png",
        start_time=transition_start,
        horizon_s=2.0,
        title="Transition left-to-right 2s",
    )
    plot_window(
        rows=rows,
        window_results=window_results,
        output_dir=output_dir,
        profile=profile,
        filename="uncertainty_corridor_example.png",
        start_time=transition_start,
        horizon_s=2.0,
        title="Command-conditioned corridor example",
        corridor_radius=corridor_radius,
    )


def latest_m2_csv(root: Path) -> Path:
    candidates = sorted((root / "data" / "logs" / "m2").glob("trajectory_validation_episode_*.csv"))
    if not candidates:
        raise FileNotFoundError("no M2 validation CSV found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", help="M2 trajectory validation CSV")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="in_place")
    parser.add_argument("--output-dir", help="override result output directory")
    args = parser.parse_args()

    root = project_root()
    profile = PROFILES[args.profile]
    csv_path = Path(args.csv_path) if args.csv_path else latest_m2_csv(root)
    output_dir = Path(args.output_dir) if args.output_dir else root / "results" / profile.output_dir_name
    rows = read_rows(csv_path)
    summary, error_samples, window_results = evaluate(rows, output_dir, profile)
    plot_results(rows, summary, error_samples, window_results, output_dir, profile)
    print(f"Evaluated {csv_path}")
    print(f"Profile: {profile.name} ({profile.description})")
    print(
        "Transition guard: "
        f"{TRANSITION_GUARD_START_S:.2f}-{TRANSITION_GUARD_END_S:.2f}s after each command switch"
    )
    print(f"Wrote results to {output_dir}")
    for item in summary:
        if item["category"] in ("all_stable", "all_transition") or profile.name == "arc":
            print(
                f"{item['method']} horizon={item['horizon_s']} category={item['category']} "
                f"windows={item['window_count']} ADE={item['ade_mean_m']} "
                f"FDE={item['fde_mean_m']} yawMAE={item['yaw_mae_mean_rad']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
