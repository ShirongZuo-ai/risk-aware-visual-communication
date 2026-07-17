"""Validate Milestone 3C world-risk CSV output."""

from __future__ import annotations

import csv
import math
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from navigation.trajectory_prediction import EPUCK_ROBOT_HALF_WIDTH_M  # noqa: E402
from simulator.m3c_config import OBSTACLE_SPECS, PREDICTION_HORIZON_S, RISK_PARAMETERS  # noqa: E402


REQUIRED_FIELDS = [
    "episode_id",
    "analysis_time_s",
    "prediction_horizon_s",
    "prediction_step_s",
    "obstacle_id",
    "obstacle_def_name",
    "obstacle_center_x",
    "obstacle_center_y",
    "obstacle_size_x",
    "obstacle_size_y",
    "obstacle_min_x",
    "obstacle_max_x",
    "obstacle_min_y",
    "obstacle_max_y",
    "planned_minimum_centerline_distance_m",
    "planned_minimum_clearance_m",
    "planned_closest_time_s",
    "planned_enters_corridor",
    "planned_first_corridor_entry_time_s",
    "planned_corridor_overlap_duration_s",
    "planned_spatial_score",
    "planned_temporal_score",
    "planned_risk_score",
    "state_minimum_centerline_distance_m",
    "state_minimum_clearance_m",
    "state_closest_time_s",
    "state_enters_corridor",
    "state_first_corridor_entry_time_s",
    "state_corridor_overlap_duration_s",
    "state_spatial_score",
    "state_temporal_score",
    "state_risk_score",
    "trajectory_disagreement_m",
    "combined_risk_score",
    "current_robot_x",
    "current_robot_y",
    "current_robot_yaw_rad",
    "current_linear_velocity_m_s",
    "current_angular_velocity_rad_s",
]

EXPECTED_IDS = {spec.obstacle_id for spec in OBSTACLE_SPECS}
EXPECTED_DEFS = {spec.def_name for spec in OBSTACLE_SPECS}
TOLERANCE = 1e-6
OUTSIDE_CLEARANCE_MIN_M = 0.01


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    fail(f"invalid boolean value: {value}")


def parse_float(row: dict[str, str], field: str, *, allow_empty: bool = False) -> float | None:
    value = row[field]
    if value == "":
        if allow_empty:
            return None
        fail(f"{field} must not be empty")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise AssertionError(f"{field} is not numeric: {value}") from exc
    if not math.isfinite(parsed):
        fail(f"{field} must be finite")
    return parsed


def latest_csv() -> Path:
    root = PROJECT_ROOT / "data" / "logs" / "m3"
    paths = sorted(root.glob("risk_validation_episode_*.csv"))
    if not paths:
        fail("no M3C risk validation CSV found")
    return paths[-1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            fail(f"missing required fields: {missing}")
        return list(reader)


def aabb(row: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        parse_float(row, "obstacle_min_x"),
        parse_float(row, "obstacle_max_x"),
        parse_float(row, "obstacle_min_y"),
        parse_float(row, "obstacle_max_y"),
    )


def aabbs_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def validate_structure(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if len(rows) != 6:
        fail(f"expected 6 rows, got {len(rows)}")
    ids = [row["obstacle_id"] for row in rows]
    defs = [row["obstacle_def_name"] for row in rows]
    if set(ids) != EXPECTED_IDS:
        fail(f"unexpected obstacle IDs: {ids}")
    if set(defs) != EXPECTED_DEFS:
        fail(f"unexpected DEF names: {defs}")
    if len(set(ids)) != 6 or len(set(defs)) != 6:
        fail("obstacle IDs and DEF names must be unique")

    by_id = {row["obstacle_id"]: row for row in rows}
    for row in rows:
        for field in REQUIRED_FIELDS:
            if field not in row:
                fail(f"missing field {field}")
        for field in REQUIRED_FIELDS:
            if field in {"obstacle_id", "obstacle_def_name", "episode_id"}:
                continue
            if field.endswith("enters_corridor"):
                parse_bool(row[field])
            elif field.endswith("first_corridor_entry_time_s"):
                parse_float(row, field, allow_empty=True)
            else:
                parse_float(row, field)
        if parse_float(row, "obstacle_size_x") <= 0 or parse_float(row, "obstacle_size_y") <= 0:
            fail(f"{row['obstacle_id']} has non-positive obstacle size")
        for prefix in ("planned", "state"):
            for score in ("spatial_score", "temporal_score", "risk_score"):
                value = parse_float(row, f"{prefix}_{score}")
                if value < -TOLERANCE or value > 1.0 + TOLERANCE:
                    fail(f"{row['obstacle_id']} {prefix}_{score} out of [0,1]: {value}")
        combined = parse_float(row, "combined_risk_score")
        if combined < -TOLERANCE or combined > 1.0 + TOLERANCE:
            fail(f"{row['obstacle_id']} combined risk out of [0,1]")
    return by_id


def validate_geometry(rows: list[dict[str, str]]) -> None:
    radius = RISK_PARAMETERS.corridor_radius_m
    for row in rows:
        horizon = parse_float(row, "prediction_horizon_s")
        if abs(horizon - PREDICTION_HORIZON_S) > TOLERANCE:
            fail("prediction horizon does not match configuration")
        for prefix in ("planned", "state"):
            distance = parse_float(row, f"{prefix}_minimum_centerline_distance_m")
            clearance = parse_float(row, f"{prefix}_minimum_clearance_m")
            if abs(clearance - (distance - radius)) > 2e-6:
                fail(f"{row['obstacle_id']} {prefix} clearance is inconsistent with distance")
            enters = parse_bool(row[f"{prefix}_enters_corridor"])
            if enters != (clearance <= RISK_PARAMETERS.geometry_tolerance_m + 2e-6):
                fail(f"{row['obstacle_id']} {prefix} enters_corridor inconsistent with clearance")
            entry = parse_float(row, f"{prefix}_first_corridor_entry_time_s", allow_empty=True)
            closest = parse_float(row, f"{prefix}_closest_time_s")
            overlap = parse_float(row, f"{prefix}_corridor_overlap_duration_s")
            if entry is None and enters:
                fail(f"{row['obstacle_id']} {prefix} enters but entry time is empty")
            if entry is not None and not enters:
                fail(f"{row['obstacle_id']} {prefix} has entry time without entering")
            if entry is not None and not (0.0 <= entry <= horizon + TOLERANCE):
                fail(f"{row['obstacle_id']} {prefix} entry time out of horizon")
            if not (0.0 <= closest <= horizon + TOLERANCE):
                fail(f"{row['obstacle_id']} {prefix} closest time out of horizon")
            if overlap < -TOLERANCE or overlap > horizon + TOLERANCE:
                fail(f"{row['obstacle_id']} {prefix} overlap duration invalid")

    for index, row in enumerate(rows):
        current_x = parse_float(row, "current_robot_x")
        current_y = parse_float(row, "current_robot_y")
        robot_aabb = (
            current_x - EPUCK_ROBOT_HALF_WIDTH_M,
            current_x + EPUCK_ROBOT_HALF_WIDTH_M,
            current_y - EPUCK_ROBOT_HALF_WIDTH_M,
            current_y + EPUCK_ROBOT_HALF_WIDTH_M,
        )
        if aabbs_overlap(robot_aabb, aabb(row)):
            fail(f"current robot AABB overlaps {row['obstacle_id']}")
        for other in rows[index + 1 :]:
            if aabbs_overlap(aabb(row), aabb(other)):
                fail(f"obstacles overlap: {row['obstacle_id']} and {other['obstacle_id']}")


def validate_roles(by_id: dict[str, dict[str, str]]) -> None:
    early = by_id["EARLY_CONFLICT"]
    late = by_id["LATE_CONFLICT"]
    planned = by_id["ON_PLANNED_PATH"]
    state = by_id["ON_STATE_PATH"]
    outside = by_id["OUTSIDE_BOTH"]
    near = by_id["NEAR_BOUNDARY"]

    if not parse_bool(early["planned_enters_corridor"]):
        fail("EARLY_CONFLICT must enter planned corridor")
    if not parse_bool(late["planned_enters_corridor"]):
        fail("LATE_CONFLICT must enter planned corridor")
    if parse_float(early, "planned_first_corridor_entry_time_s", allow_empty=True) >= parse_float(
        late, "planned_first_corridor_entry_time_s", allow_empty=True
    ):
        fail("EARLY_CONFLICT planned TTCf must be earlier than LATE_CONFLICT")
    if parse_float(early, "planned_risk_score") <= parse_float(late, "planned_risk_score"):
        fail("EARLY_CONFLICT planned risk must be greater than LATE_CONFLICT")

    if parse_float(planned, "planned_risk_score") <= parse_float(planned, "state_risk_score"):
        fail("ON_PLANNED_PATH planned risk must exceed state risk")
    if parse_float(planned, "planned_minimum_clearance_m") >= parse_float(planned, "state_minimum_clearance_m"):
        fail("ON_PLANNED_PATH planned clearance must be smaller than state clearance")

    if parse_float(state, "state_risk_score") <= parse_float(state, "planned_risk_score"):
        fail("ON_STATE_PATH state risk must exceed planned risk")
    if parse_float(state, "state_minimum_clearance_m") >= parse_float(state, "planned_minimum_clearance_m"):
        fail("ON_STATE_PATH state clearance must be smaller than planned clearance")

    if parse_bool(outside["planned_enters_corridor"]) or parse_bool(outside["state_enters_corridor"]):
        fail("OUTSIDE_BOTH must not enter either corridor")
    if parse_float(outside, "planned_minimum_clearance_m") <= OUTSIDE_CLEARANCE_MIN_M:
        fail("OUTSIDE_BOTH planned clearance is not clearly positive")
    if parse_float(outside, "state_minimum_clearance_m") <= OUTSIDE_CLEARANCE_MIN_M:
        fail("OUTSIDE_BOTH state clearance is not clearly positive")

    near_abs = min(
        abs(parse_float(near, "planned_minimum_clearance_m")),
        abs(parse_float(near, "state_minimum_clearance_m")),
    )
    if near_abs <= RISK_PARAMETERS.geometry_tolerance_m * 10:
        fail("NEAR_BOUNDARY depends on geometry tolerance")
    if near_abs > 0.01:
        fail("NEAR_BOUNDARY is not within the required clearance band")

    disagreements = {round(parse_float(row, "trajectory_disagreement_m"), 9) for row in by_id.values()}
    if len(disagreements) != 1:
        fail("trajectory disagreement must be identical on all rows")
    disagreement = next(iter(disagreements))
    if disagreement <= 0:
        fail("trajectory disagreement must be positive")


def validate_paths_and_leakage(csv_path: Path) -> None:
    text = csv_path.read_text(encoding="utf-8")
    if "Downloads" in text:
        fail("CSV contains Downloads path")
    if "C:\\" in text or ":/" in text:
        fail("CSV contains an absolute path")
    controller = PROJECT_ROOT / "simulator" / "controllers" / "m3_world_risk_validation" / "m3_world_risk_validation.py"
    source = controller.read_text(encoding="utf-8")
    forbidden = ("future_actual", "actual_future", "future_x", "future_y", "future_yaw", "future_velocity")
    matches = [token for token in forbidden if token in source]
    if matches:
        fail(f"controller source contains future-actual leakage tokens: {matches}")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    if "data/logs/*" not in gitignore:
        fail("data/logs outputs are not ignored by Git")


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_csv()
    rows = read_rows(csv_path)
    by_id = validate_structure(rows)
    validate_geometry(rows)
    validate_roles(by_id)
    validate_paths_and_leakage(csv_path)
    print(f"OK: validated {csv_path} with {len(rows)} M3C risk rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
