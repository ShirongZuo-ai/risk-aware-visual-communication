"""Shared helpers for Milestone 3D world-risk diagnostics."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from navigation.trajectory_prediction import (  # noqa: E402
    CommandSegment,
    TrajectoryPoint,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
)
from risk_map.models import ObstacleFootprint, RiskParameters  # noqa: E402
from risk_map.risk_formulation import compute_risk_score  # noqa: E402
from risk_map.trajectory_obstacle_risk import (  # noqa: E402
    analyze_dual_trajectory_obstacle,
    compute_trajectory_disagreement,
    interpolate_trajectory_position,
)
from simulator.m3c_config import (  # noqa: E402
    ANALYSIS_TIME_S,
    COMMAND_SCHEDULE,
    OBSTACLE_SPECS,
    PREDICTION_HORIZON_S,
    PREDICTION_STEP_S,
    RISK_PARAMETERS,
)


SUCCESS_EPISODE_ID = "episode_0002"
SUCCESS_CSV = PROJECT_ROOT / "data" / "logs" / "m3" / "risk_validation_episode_0002.csv"
TRAJECTORY_CSV = PROJECT_ROOT / "data" / "logs" / "m3" / "risk_validation_episode_0002_trajectories.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "m3_world_risk"
SUMMARY_CSV = OUTPUT_DIR / "m3d_risk_summary.csv"
SUMMARY_JSON = OUTPUT_DIR / "m3d_risk_summary.json"
SENSITIVITY_CSV = OUTPUT_DIR / "parameter_sensitivity.csv"
SIGMA_VALUES = (0.025, 0.05, 0.10)
TAU_VALUES = (0.5, 1.0, 2.0)
FLOAT_TOL = 1e-8
DOMINANT_TOL = 1e-9

ROLE_ORDER = (
    "EARLY_CONFLICT",
    "LATE_CONFLICT",
    "ON_PLANNED_PATH",
    "ON_STATE_PATH",
    "NEAR_BOUNDARY",
    "OUTSIDE_BOTH",
)


@dataclass(frozen=True)
class RebuiltTrajectories:
    planned: list[TrajectoryPoint]
    state: list[TrajectoryPoint]
    disagreement_by_time: list[tuple[float, float]]
    max_disagreement_m: float


def parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"invalid boolean value: {value}")


def parse_optional_float(value: str) -> float | None:
    if value == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite numeric value: {value}")
    return parsed


def parse_float(value: str) -> float:
    parsed = parse_optional_float(value)
    if parsed is None:
        raise ValueError("empty numeric value")
    return parsed


def load_success_rows(csv_path: Path = SUCCESS_CSV) -> list[dict[str, str]]:
    if csv_path.name != "risk_validation_episode_0002.csv":
        raise ValueError("Milestone 3D must use risk_validation_episode_0002.csv")
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 6:
        raise ValueError(f"expected 6 rows, got {len(rows)}")
    if {row["episode_id"] for row in rows} != {SUCCESS_EPISODE_ID}:
        raise ValueError("M3D input rows must all use episode_0002")
    ids = [row["obstacle_id"] for row in rows]
    if set(ids) != set(ROLE_ORDER):
        raise ValueError(f"unexpected M3D obstacle IDs: {ids}")
    return sorted(rows, key=lambda row: ROLE_ORDER.index(row["obstacle_id"]))


def future_command_segments(analysis_time_s: float = ANALYSIS_TIME_S) -> list[CommandSegment]:
    horizon_end = analysis_time_s + PREDICTION_HORIZON_S
    segments: list[CommandSegment] = []
    for phase in COMMAND_SCHEDULE:
        start = max(phase.start_s, analysis_time_s)
        end = min(phase.end_s, horizon_end)
        if end <= start:
            continue
        segments.append(CommandSegment(start - analysis_time_s, end - analysis_time_s, phase.left_rad_s, phase.right_rad_s))
    if not segments or segments[-1].end_offset_s < PREDICTION_HORIZON_S:
        start = segments[-1].end_offset_s if segments else 0.0
        segments.append(CommandSegment(start, PREDICTION_HORIZON_S, 0.0, 0.0))
    return segments


def rebuild_trajectories(rows: list[dict[str, str]]) -> RebuiltTrajectories:
    first = rows[0]
    current_x = parse_float(first["current_robot_x"])
    current_y = parse_float(first["current_robot_y"])
    current_yaw = parse_float(first["current_robot_yaw_rad"])
    current_v = parse_float(first["current_linear_velocity_m_s"])
    current_omega = parse_float(first["current_angular_velocity_rad_s"])
    planned = predict_command_conditioned_trajectory(
        x=current_x,
        y=current_y,
        yaw_rad=current_yaw,
        command_segments=future_command_segments(parse_float(first["analysis_time_s"])),
        horizon_s=PREDICTION_HORIZON_S,
        step_s=PREDICTION_STEP_S,
    )
    state = predict_state_only_trajectory(
        x=current_x,
        y=current_y,
        yaw_rad=current_yaw,
        linear_velocity_m_s=current_v,
        angular_velocity_rad_s=current_omega,
        horizon_s=PREDICTION_HORIZON_S,
        step_s=PREDICTION_STEP_S,
    )
    disagreement_by_time = []
    sample_times = sorted({point.time_offset_s for point in planned + state})
    for time_offset in sample_times:
        planned_x, planned_y = interpolate_trajectory_position(planned, time_offset)
        state_x, state_y = interpolate_trajectory_position(state, time_offset)
        disagreement_by_time.append((time_offset, math.hypot(planned_x - state_x, planned_y - state_y)))
    return RebuiltTrajectories(planned, state, disagreement_by_time, compute_trajectory_disagreement(planned, state))


def write_trajectory_csv(trajectories: RebuiltTrajectories, path: Path = TRAJECTORY_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("episode_id", "trajectory_source", "time_offset_s", "x", "y", "yaw_rad"))
        writer.writeheader()
        for source, points in (("planned", trajectories.planned), ("state", trajectories.state)):
            for point in points:
                writer.writerow(
                    {
                        "episode_id": SUCCESS_EPISODE_ID,
                        "trajectory_source": source,
                        "time_offset_s": f"{point.time_offset_s:.9f}",
                        "x": f"{point.x:.9f}",
                        "y": f"{point.y:.9f}",
                        "yaw_rad": f"{point.yaw_rad:.9f}",
                    }
                )


def obstacle_from_row(row: dict[str, str]) -> ObstacleFootprint:
    return ObstacleFootprint(
        row["obstacle_id"],
        parse_float(row["obstacle_center_x"]),
        parse_float(row["obstacle_center_y"]),
        parse_float(row["obstacle_size_x"]),
        parse_float(row["obstacle_size_y"]),
    )


def recompute_scores(row: dict[str, str], prefix: str, params: RiskParameters = RISK_PARAMETERS) -> dict[str, float]:
    clearance = parse_float(row[f"{prefix}_minimum_clearance_m"])
    closest_time = parse_float(row[f"{prefix}_closest_time_s"])
    entry_time = parse_optional_float(row[f"{prefix}_first_corridor_entry_time_s"])
    scores = compute_risk_score(
        clearance_m=clearance,
        closest_time_s=closest_time,
        first_entry_time_s=entry_time,
        sigma_distance_m=params.sigma_distance_m,
        tau_time_s=params.tau_time_s,
    )
    return {
        "spatial_score": scores.spatial_score,
        "temporal_score": scores.temporal_score,
        "risk_score": scores.risk_score,
    }


def dominant_trajectory(planned_risk: float, state_risk: float, tolerance: float = DOMINANT_TOL) -> str:
    if abs(planned_risk - state_risk) <= tolerance:
        return "tie"
    if planned_risk > state_risk:
        return "planned"
    return "state"


def validate_formula_consistency(rows: list[dict[str, str]], trajectories: RebuiltTrajectories) -> None:
    csv_disagreements = {round(parse_float(row["trajectory_disagreement_m"]), 9) for row in rows}
    if len(csv_disagreements) != 1:
        raise ValueError("CSV disagreement values are not identical")
    if abs(next(iter(csv_disagreements)) - trajectories.max_disagreement_m) > 1e-8:
        raise ValueError("trajectory disagreement recomputation mismatch")
    for row in rows:
        for prefix in ("planned", "state"):
            distance = parse_float(row[f"{prefix}_minimum_centerline_distance_m"])
            clearance = parse_float(row[f"{prefix}_minimum_clearance_m"])
            if abs(clearance - (distance - RISK_PARAMETERS.corridor_radius_m)) > 1e-8:
                raise ValueError(f"{row['obstacle_id']} {prefix} clearance mismatch")
            enters = parse_bool(row[f"{prefix}_enters_corridor"])
            entry = parse_optional_float(row[f"{prefix}_first_corridor_entry_time_s"])
            if enters and entry is None:
                raise ValueError(f"{row['obstacle_id']} {prefix} missing entry time")
            if not enters and entry is not None:
                raise ValueError(f"{row['obstacle_id']} {prefix} unexpected entry time")
            if enters != (clearance <= RISK_PARAMETERS.geometry_tolerance_m + 1e-8):
                raise ValueError(f"{row['obstacle_id']} {prefix} enters/clearance mismatch")
            recomputed = recompute_scores(row, prefix)
            for name, value in recomputed.items():
                csv_value = parse_float(row[f"{prefix}_{name}"])
                if abs(csv_value - value) > 1e-8:
                    raise ValueError(f"{row['obstacle_id']} {prefix}_{name} recomputation mismatch")
                if not (0.0 - FLOAT_TOL <= csv_value <= 1.0 + FLOAT_TOL):
                    raise ValueError(f"{row['obstacle_id']} {prefix}_{name} outside [0, 1]")
        combined = parse_float(row["combined_risk_score"])
        planned = parse_float(row["planned_risk_score"])
        state = parse_float(row["state_risk_score"])
        if abs(combined - max(planned, state)) > 1e-8:
            raise ValueError(f"{row['obstacle_id']} combined risk mismatch")


def role_acceptance(rows_by_id: dict[str, dict[str, str]]) -> dict[str, bool]:
    early = rows_by_id["EARLY_CONFLICT"]
    late = rows_by_id["LATE_CONFLICT"]
    on_planned = rows_by_id["ON_PLANNED_PATH"]
    on_state = rows_by_id["ON_STATE_PATH"]
    near = rows_by_id["NEAR_BOUNDARY"]
    outside = rows_by_id["OUTSIDE_BOTH"]
    checks = {
        "EARLY_CONFLICT": (
            parse_bool(early["planned_enters_corridor"])
            and parse_optional_float(early["planned_first_corridor_entry_time_s"]) is not None
            and parse_optional_float(early["planned_first_corridor_entry_time_s"])
            < parse_optional_float(late["planned_first_corridor_entry_time_s"])
            and parse_float(early["planned_risk_score"]) > parse_float(late["planned_risk_score"])
        ),
        "LATE_CONFLICT": (
            parse_bool(late["planned_enters_corridor"])
            and parse_optional_float(late["planned_first_corridor_entry_time_s"])
            > parse_optional_float(early["planned_first_corridor_entry_time_s"])
            and parse_float(late["planned_risk_score"]) < parse_float(early["planned_risk_score"])
        ),
        "ON_PLANNED_PATH": (
            parse_float(on_planned["planned_minimum_clearance_m"]) < parse_float(on_planned["state_minimum_clearance_m"])
            and parse_float(on_planned["planned_risk_score"]) > parse_float(on_planned["state_risk_score"])
        ),
        "ON_STATE_PATH": (
            parse_float(on_state["state_minimum_clearance_m"]) < parse_float(on_state["planned_minimum_clearance_m"])
            and parse_float(on_state["state_risk_score"]) > parse_float(on_state["planned_risk_score"])
        ),
        "NEAR_BOUNDARY": (
            0.0
            < min(
                value
                for value in (
                    parse_float(near["planned_minimum_clearance_m"]),
                    parse_float(near["state_minimum_clearance_m"]),
                )
                if value > 0.0
            )
            <= 0.01
            and not parse_bool(near["planned_enters_corridor"])
            and not parse_bool(near["state_enters_corridor"])
        ),
        "OUTSIDE_BOTH": (
            not parse_bool(outside["planned_enters_corridor"])
            and not parse_bool(outside["state_enters_corridor"])
            and parse_float(outside["planned_minimum_clearance_m"]) > 0.0
            and parse_float(outside["state_minimum_clearance_m"]) > 0.0
        ),
    }
    return checks


def build_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows_by_id = {row["obstacle_id"]: row for row in rows}
    role_checks = role_acceptance(rows_by_id)
    summary = []
    for row in rows:
        planned_risk = parse_float(row["planned_risk_score"])
        state_risk = parse_float(row["state_risk_score"])
        summary.append(
            {
                "obstacle_id": row["obstacle_id"],
                "planned_clearance_m": parse_float(row["planned_minimum_clearance_m"]),
                "planned_ttc_f_s": parse_optional_float(row["planned_first_corridor_entry_time_s"]),
                "planned_spatial_score": parse_float(row["planned_spatial_score"]),
                "planned_temporal_score": parse_float(row["planned_temporal_score"]),
                "planned_risk_score": planned_risk,
                "state_clearance_m": parse_float(row["state_minimum_clearance_m"]),
                "state_ttc_f_s": parse_optional_float(row["state_first_corridor_entry_time_s"]),
                "state_spatial_score": parse_float(row["state_spatial_score"]),
                "state_temporal_score": parse_float(row["state_temporal_score"]),
                "state_risk_score": state_risk,
                "combined_risk_score": parse_float(row["combined_risk_score"]),
                "planned_minus_state_risk": planned_risk - state_risk,
                "dominant_trajectory": dominant_trajectory(planned_risk, state_risk),
                "role_acceptance_pass": role_checks[row["obstacle_id"]],
            }
        )
    return summary


def write_summary_files(summary: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        for row in summary:
            writer.writerow(row)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def sensitivity_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for sigma, tau in itertools.product(SIGMA_VALUES, TAU_VALUES):
        params = RiskParameters(
            corridor_radius_m=RISK_PARAMETERS.corridor_radius_m,
            sigma_distance_m=sigma,
            tau_time_s=tau,
            maximum_horizon_s=RISK_PARAMETERS.maximum_horizon_s,
            geometry_tolerance_m=RISK_PARAMETERS.geometry_tolerance_m,
        )
        recomputed: dict[str, dict[str, float]] = {}
        all_in_range = True
        for row in rows:
            planned = recompute_scores(row, "planned", params)["risk_score"]
            state = recompute_scores(row, "state", params)["risk_score"]
            all_in_range = all_in_range and 0.0 <= planned <= 1.0 and 0.0 <= state <= 1.0
            recomputed[row["obstacle_id"]] = {"planned": planned, "state": state}
        early_late = recomputed["EARLY_CONFLICT"]["planned"] > recomputed["LATE_CONFLICT"]["planned"]
        on_planned = recomputed["ON_PLANNED_PATH"]["planned"] > recomputed["ON_PLANNED_PATH"]["state"]
        on_state = recomputed["ON_STATE_PATH"]["state"] > recomputed["ON_STATE_PATH"]["planned"]
        outside = (
            not parse_bool(next(row for row in rows if row["obstacle_id"] == "OUTSIDE_BOTH")["planned_enters_corridor"])
            and not parse_bool(next(row for row in rows if row["obstacle_id"] == "OUTSIDE_BOTH")["state_enters_corridor"])
        )
        output.append(
            {
                "sigma_distance_m": sigma,
                "tau_time_s": tau,
                "early_gt_late_planned": early_late,
                "on_planned_dominant": on_planned,
                "on_state_dominant": on_state,
                "outside_both_outside": outside,
                "risk_in_range": all_in_range,
                "all_key_checks_pass": early_late and on_planned and on_state and outside and all_in_range,
                "early_planned_risk": recomputed["EARLY_CONFLICT"]["planned"],
                "late_planned_risk": recomputed["LATE_CONFLICT"]["planned"],
                "on_planned_planned_risk": recomputed["ON_PLANNED_PATH"]["planned"],
                "on_planned_state_risk": recomputed["ON_PLANNED_PATH"]["state"],
                "on_state_planned_risk": recomputed["ON_STATE_PATH"]["planned"],
                "on_state_state_risk": recomputed["ON_STATE_PATH"]["state"],
            }
        )
    return output


def write_sensitivity_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with SENSITIVITY_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def evaluate_all() -> tuple[list[dict[str, str]], RebuiltTrajectories, list[dict[str, object]], list[dict[str, object]]]:
    rows = load_success_rows()
    trajectories = rebuild_trajectories(rows)
    validate_formula_consistency(rows, trajectories)
    role_checks = role_acceptance({row["obstacle_id"]: row for row in rows})
    if not all(role_checks.values()):
        raise ValueError(f"M3 role acceptance failed: {role_checks}")
    summary = build_summary(rows)
    sensitivity = sensitivity_rows(rows)
    if len(sensitivity) != 9:
        raise ValueError("parameter sensitivity must contain 9 rows")
    if not all(row["all_key_checks_pass"] for row in sensitivity):
        raise ValueError("parameter sensitivity key ordering failed")
    return rows, trajectories, summary, sensitivity
