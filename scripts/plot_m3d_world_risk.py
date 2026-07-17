"""Generate Milestone 3D world-coordinate diagnostic figures."""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch, Rectangle

from m3d_world_risk_common import (
    OUTPUT_DIR,
    ROLE_ORDER,
    RISK_PARAMETERS,
    evaluate_all,
    parse_bool,
    parse_float,
    parse_optional_float,
    interpolate_trajectory_position,
)


PLANNED_COLOR = "#1f77b4"
STATE_COLOR = "#2ca02c"
COMBINED_COLOR = "#555555"
OBSTACLE_COLOR = "#d62728"


def savefig(name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / name, dpi=180)
    plt.close()


def add_corridor(ax, points, color: str, label: str) -> None:
    # Draw a union of disks along the full trajectory so the corridor is a band,
    # not a single start-point circle.
    first = True
    for point in points:
        ax.add_patch(
            Circle(
                (point.x, point.y),
                RISK_PARAMETERS.corridor_radius_m,
                facecolor=color,
                edgecolor="none",
                alpha=0.045,
                label=label if first else None,
                zorder=1,
            )
        )
        first = False


def add_obstacles(ax, rows) -> None:
    for row in rows:
        min_x = parse_float(row["obstacle_min_x"])
        max_x = parse_float(row["obstacle_max_x"])
        min_y = parse_float(row["obstacle_min_y"])
        max_y = parse_float(row["obstacle_max_y"])
        ax.add_patch(
            Rectangle(
                (min_x, min_y),
                max_x - min_x,
                max_y - min_y,
                facecolor="none",
                edgecolor=OBSTACLE_COLOR,
                linewidth=1.5,
                zorder=4,
            )
        )
        label = (
            f"{row['obstacle_id']}\n"
            f"P {parse_float(row['planned_risk_score']):.2f} "
            f"S {parse_float(row['state_risk_score']):.2f} "
            f"C {parse_float(row['combined_risk_score']):.2f}"
        )
        if row["obstacle_id"] == "OUTSIDE_BOTH":
            ax.text(min_x - 0.004, max_y + 0.003, label, fontsize=7, ha="right", va="bottom")
        else:
            ax.text(max_x + 0.003, max_y + 0.003, label, fontsize=7, ha="left", va="bottom")


def add_entry_points(ax, rows, planned, state) -> None:
    for row in rows:
        for prefix, points, color in (("planned", planned, PLANNED_COLOR), ("state", state, STATE_COLOR)):
            entry = parse_optional_float(row[f"{prefix}_first_corridor_entry_time_s"])
            if entry is None:
                continue
            x, y = interpolate_trajectory_position(points, entry)
            ax.plot(x, y, marker="x", color=color, markersize=8, markeredgewidth=2, linestyle="None", zorder=6)


def plot_world_overview(rows, trajectories) -> None:
    fig, ax = plt.subplots(figsize=(9, 7))
    add_corridor(ax, trajectories.planned, PLANNED_COLOR, "planned corridor")
    add_corridor(ax, trajectories.state, STATE_COLOR, "state corridor")
    ax.plot(
        [p.x for p in trajectories.planned],
        [p.y for p in trajectories.planned],
        color=PLANNED_COLOR,
        linewidth=2.2,
        label="planned trajectory",
        zorder=5,
    )
    ax.plot(
        [p.x for p in trajectories.state],
        [p.y for p in trajectories.state],
        color=STATE_COLOR,
        linewidth=2.2,
        label="state trajectory",
        zorder=5,
    )
    first = rows[0]
    robot_x = parse_float(first["current_robot_x"])
    robot_y = parse_float(first["current_robot_y"])
    robot_yaw = parse_float(first["current_robot_yaw_rad"])
    ax.scatter([robot_x], [robot_y], color="black", s=40, label="current robot")
    ax.arrow(robot_x, robot_y, 0.035 * math.cos(robot_yaw), 0.035 * math.sin(robot_yaw), width=0.0015, color="black")
    add_obstacles(ax, rows)
    add_entry_points(ax, rows, trajectories.planned, trajectories.state)
    ax.text(
        0.02,
        0.02,
        "P=planned risk\nS=state risk\nC=combined risk",
        transform=ax.transAxes,
        fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "#bbbbbb"},
    )
    handles, labels = ax.get_legend_handles_labels()
    handles.extend(
        [
            Patch(facecolor="none", edgecolor=OBSTACLE_COLOR, label="Obstacle AABB"),
            Line2D([0], [0], marker="x", color=PLANNED_COLOR, linestyle="None", markersize=8, markeredgewidth=2, label="planned first entry"),
            Line2D([0], [0], marker="x", color=STATE_COLOR, linestyle="None", markersize=8, markeredgewidth=2, label="state first entry"),
        ]
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("world x (m)")
    ax.set_ylabel("world y (m)")
    ax.set_title("Milestone 3D World Risk Overview")
    ax.set_xlim(0.15, 0.37)
    ax.set_ylim(0.02, 0.22)
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    ax.grid(True, linewidth=0.4, alpha=0.4)
    savefig("world_risk_overview.png")


def plot_planned_vs_state_risk(rows) -> None:
    labels = [row["obstacle_id"].replace("_", "\n") for row in rows]
    x = list(range(len(rows)))
    width = 0.25
    fig, ax = plt.subplots(figsize=(10, 5))
    planned = [parse_float(row["planned_risk_score"]) for row in rows]
    state = [parse_float(row["state_risk_score"]) for row in rows]
    combined = [parse_float(row["combined_risk_score"]) for row in rows]
    bars = [
        ax.bar([i - width for i in x], planned, width, label="planned", color=PLANNED_COLOR),
        ax.bar(x, state, width, label="state", color=STATE_COLOR),
        ax.bar([i + width for i in x], combined, width, label="combined", color=COMBINED_COLOR),
    ]
    for group in bars:
        for bar in group:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015, f"{bar.get_height():.2f}", ha="center", fontsize=7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("risk score")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("Planned, State, and Combined Risk")
    ax.legend()
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    savefig("planned_vs_state_risk.png")


def plot_decomposition(rows, prefix: str, name: str) -> None:
    labels = [row["obstacle_id"].replace("_", "\n") for row in rows]
    x = list(range(len(rows)))
    width = 0.25
    fig, ax = plt.subplots(figsize=(10, 5))
    series = [
        ("spatial", [parse_float(row[f"{prefix}_spatial_score"]) for row in rows], "#9467bd"),
        ("temporal", [parse_float(row[f"{prefix}_temporal_score"]) for row in rows], "#ff7f0e"),
        ("risk", [parse_float(row[f"{prefix}_risk_score"]) for row in rows], PLANNED_COLOR if prefix == "planned" else STATE_COLOR),
    ]
    for offset, (label, values, color) in zip((-width, 0.0, width), series):
        bars = ax.bar([i + offset for i in x], values, width, label=label, color=color)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015, f"{bar.get_height():.2f}", ha="center", fontsize=7)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("score")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title(f"{prefix.capitalize()} Risk Decomposition")
    ax.legend()
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    savefig(name)


def plot_early_vs_late_ttcf(rows) -> None:
    subset = [row for row in rows if row["obstacle_id"] in ("EARLY_CONFLICT", "LATE_CONFLICT")]
    labels = [row["obstacle_id"].replace("_", "\n") for row in subset]
    values = [parse_float(row["planned_first_corridor_entry_time_s"]) for row in subset]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    bars = ax.bar(range(len(labels)), values, color="#ff7f0e")
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.035, f"{bar.get_height():.3f}", ha="center", fontsize=9)
    ax.set_ylabel("Time-to-Conflict (s)")
    ax.set_ylim(0, max(values) * 1.25)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_title("EARLY vs LATE Planned TTCf")
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    savefig("early_vs_late_ttcf.png")


def plot_early_vs_late_risk_decomposition(rows) -> None:
    subset = [row for row in rows if row["obstacle_id"] in ("EARLY_CONFLICT", "LATE_CONFLICT")]
    labels = [row["obstacle_id"].replace("_", "\n") for row in subset]
    x = list(range(len(labels)))
    width = 0.25
    metrics = (
        ("spatial", "planned_spatial_score", "#9467bd"),
        ("temporal", "planned_temporal_score", "#ff7f0e"),
        ("risk", "planned_risk_score", PLANNED_COLOR),
    )
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for offset, (metric_label, field, color) in zip((-width, 0.0, width), metrics):
        values = [parse_float(row[field]) for row in subset]
        bars = ax.bar([i + offset for i in x], values, width, label=metric_label, color=color)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.018, f"{bar.get_height():.2f}", ha="center", fontsize=8)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Score [0,1]")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("EARLY vs LATE Planned Risk Decomposition")
    ax.legend()
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    savefig("early_vs_late_risk_decomposition.png")


def plot_clearance_curve(rows) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    clearances = [i / 1000 for i in range(-40, 201)]
    scores = [math.exp(-max(clearance, 0.0) / RISK_PARAMETERS.sigma_distance_m) for clearance in clearances]
    ax.plot(clearances, scores, color="black", label=f"heuristic spatial score, sigma={RISK_PARAMETERS.sigma_distance_m:g} m")
    for row in rows:
        for prefix, color, marker in (("planned", PLANNED_COLOR, "o"), ("state", STATE_COLOR, "s")):
            clearance = parse_float(row[f"{prefix}_minimum_clearance_m"])
            score = parse_float(row[f"{prefix}_spatial_score"])
            ax.scatter([clearance], [score], color=color, marker=marker, s=32)
            if row["obstacle_id"] == "NEAR_BOUNDARY" and prefix == "state":
                ax.annotate("NEAR_BOUNDARY state", (clearance, score), xytext=(8, -18), textcoords="offset points", fontsize=8, va="top")
            if row["obstacle_id"] == "OUTSIDE_BOTH" and prefix == "planned":
                ax.annotate("OUTSIDE_BOTH planned", (clearance, score), xytext=(8, -18), textcoords="offset points", fontsize=8)
    ax.axvline(0.0, color="#777777", linestyle="--", linewidth=1)
    ax.scatter([], [], color=PLANNED_COLOR, marker="o", label="planned obstacle clearance")
    ax.scatter([], [], color=STATE_COLOR, marker="s", label="state obstacle clearance")
    ax.set_xlabel("clearance (m)")
    ax.set_ylabel("spatial score")
    ax.set_title("Clearance to Heuristic Spatial Score (not a calibrated probability)")
    ax.legend()
    ax.grid(True, linewidth=0.4, alpha=0.4)
    savefig("clearance_risk_curve.png")


def plot_disagreement(trajectories) -> None:
    times = [item[0] for item in trajectories.disagreement_by_time]
    distances = [item[1] for item in trajectories.disagreement_by_time]
    max_index = max(range(len(distances)), key=lambda index: distances[index])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(times, distances, color="#17becf", label="planned/state distance")
    ax.scatter([times[max_index]], [distances[max_index]], color="red", label=f"max {distances[max_index]:.3f} m")
    ax.axhline(RISK_PARAMETERS.corridor_radius_m, color="#777777", linestyle="--", label="corridor radius")
    ax.set_xlabel("time offset (s)")
    ax.set_ylabel("Euclidean distance (m)")
    ax.set_title("Trajectory Disagreement Over Time")
    ax.legend()
    ax.grid(True, linewidth=0.4, alpha=0.4)
    savefig("trajectory_disagreement_over_time.png")


def plot_sensitivity(sensitivity) -> None:
    labels = [f"s={row['sigma_distance_m']}\nt={row['tau_time_s']}" for row in sensitivity]
    values = [1.0 if row["all_key_checks_pass"] else 0.0 for row in sensitivity]
    colors = ["#2ca02c" if value else "#d62728" for value in values]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(range(len(values)), values, color=colors)
    for bar, row in zip(bars, sensitivity):
        ax.text(bar.get_x() + bar.get_width() / 2, 0.5, "PASS" if row["all_key_checks_pass"] else "FAIL", ha="center", va="center", color="white", fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("key ordering pass")
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("Parameter Sensitivity: Key Ordering Checks")
    savefig("parameter_sensitivity.png")


def plot_sensitivity_margins(sensitivity) -> None:
    labels = [f"s={row['sigma_distance_m']}\nt={row['tau_time_s']}" for row in sensitivity]
    x = list(range(len(sensitivity)))
    width = 0.24
    margin_series = (
        (
            "EARLY-LATE planned",
            [row["early_planned_risk"] - row["late_planned_risk"] for row in sensitivity],
            "#1f77b4",
        ),
        (
            "ON_PLANNED P-S",
            [row["on_planned_planned_risk"] - row["on_planned_state_risk"] for row in sensitivity],
            "#ff7f0e",
        ),
        (
            "ON_STATE S-P",
            [row["on_state_state_risk"] - row["on_state_planned_risk"] for row in sensitivity],
            "#2ca02c",
        ),
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    for offset, (label, values, color) in zip((-width, 0.0, width), margin_series):
        ax.bar([i + offset for i in x], values, width, label=label, color=color)
    ax.axhline(0.0, color="black", linewidth=1.0)
    ax.set_ylabel("risk margin (positive passes)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("Parameter Sensitivity Margins")
    ax.legend()
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    savefig("parameter_sensitivity_margins.png")


def main() -> int:
    rows, trajectories, _summary, sensitivity = evaluate_all()
    plot_world_overview(rows, trajectories)
    plot_planned_vs_state_risk(rows)
    plot_decomposition(rows, "planned", "risk_decomposition_planned.png")
    plot_decomposition(rows, "state", "risk_decomposition_state.png")
    plot_early_vs_late_ttcf(rows)
    plot_early_vs_late_risk_decomposition(rows)
    plot_clearance_curve(rows)
    plot_disagreement(trajectories)
    plot_sensitivity(sensitivity)
    plot_sensitivity_margins(sensitivity)
    for name in (
        "world_risk_overview.png",
        "planned_vs_state_risk.png",
        "risk_decomposition_planned.png",
        "risk_decomposition_state.png",
        "early_vs_late_ttcf.png",
        "early_vs_late_risk_decomposition.png",
        "clearance_risk_curve.png",
        "trajectory_disagreement_over_time.png",
        "parameter_sensitivity.png",
        "parameter_sensitivity_margins.png",
    ):
        print(f"OK: wrote {OUTPUT_DIR / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
