"""Shared Milestone 3C validation constants."""

from __future__ import annotations

from dataclasses import dataclass

from risk_map.models import RiskParameters


ANALYSIS_TIME_S = 7.968
PREDICTION_HORIZON_S = 2.0
PREDICTION_STEP_S = 0.032

RISK_PARAMETERS = RiskParameters(
    corridor_radius_m=0.037592257,
    sigma_distance_m=0.05,
    tau_time_s=1.0,
    maximum_horizon_s=PREDICTION_HORIZON_S,
    geometry_tolerance_m=1e-6,
)

CALIBRATION_CURRENT_X = 0.242882516
CALIBRATION_CURRENT_Y = 0.070315357
CALIBRATION_CURRENT_YAW_RAD = 1.393201041
CALIBRATION_CURRENT_LINEAR_VELOCITY_M_S = 0.029944488
CALIBRATION_CURRENT_ANGULAR_VELOCITY_RAD_S = 0.350989561


@dataclass(frozen=True)
class CommandPhase:
    name: str
    start_s: float
    end_s: float
    left_rad_s: float
    right_rad_s: float


@dataclass(frozen=True)
class ObstacleSpec:
    obstacle_id: str
    def_name: str
    center_x: float
    center_y: float
    size_x: float
    size_y: float
    size_z: float = 0.05


COMMAND_SCHEDULE = (
    CommandPhase("stable_straight", 0.0, 4.0, 2.0, 2.0),
    CommandPhase("stable_forward_left_arc", 4.0, 8.0, 1.0, 2.0),
    CommandPhase("stable_forward_right_arc", 8.0, 12.0, 2.0, 1.0),
)

OBSTACLE_SPECS = (
    ObstacleSpec("EARLY_CONFLICT", "M3_EARLY_CONFLICT", 0.297106, 0.065676, 0.025, 0.025),
    ObstacleSpec("LATE_CONFLICT", "M3_LATE_CONFLICT", 0.241455, 0.162030, 0.025, 0.025),
    ObstacleSpec("ON_PLANNED_PATH", "M3_ON_PLANNED_PATH", 0.298331, 0.106364, 0.025, 0.025),
    ObstacleSpec("ON_STATE_PATH", "M3_ON_STATE_PATH", 0.203578, 0.123618, 0.025, 0.025),
    ObstacleSpec("NEAR_BOUNDARY", "M3_NEAR_BOUNDARY", 0.187397, 0.095750, 0.025, 0.025),
    ObstacleSpec("OUTSIDE_BOTH", "M3_OUTSIDE_BOTH", 0.330000, 0.185000, 0.025, 0.025),
)


def command_for_time(elapsed_s: float) -> CommandPhase:
    for phase in COMMAND_SCHEDULE:
        if phase.start_s <= elapsed_s < phase.end_s:
            return phase
    return CommandPhase("stable_stop", COMMAND_SCHEDULE[-1].end_s, float("inf"), 0.0, 0.0)
