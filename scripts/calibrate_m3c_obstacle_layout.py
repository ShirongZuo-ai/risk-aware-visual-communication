"""Development helper for the fixed Milestone 3C obstacle layout.

This script does not produce the formal M3C result. The formal result must come
from Webots reading the fixed DEF Box nodes in m3_world_risk_validation.wbt.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from navigation.trajectory_prediction import (  # noqa: E402
    CommandSegment,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
    wheel_commands_to_twist,
)
from risk_map.models import ObstacleFootprint  # noqa: E402
from risk_map.trajectory_obstacle_risk import analyze_dual_trajectory_obstacle  # noqa: E402
from simulator.m3c_config import (  # noqa: E402
    ANALYSIS_TIME_S,
    CALIBRATION_CURRENT_ANGULAR_VELOCITY_RAD_S,
    CALIBRATION_CURRENT_LINEAR_VELOCITY_M_S,
    CALIBRATION_CURRENT_X,
    CALIBRATION_CURRENT_Y,
    CALIBRATION_CURRENT_YAW_RAD,
    COMMAND_SCHEDULE,
    OBSTACLE_SPECS,
    PREDICTION_HORIZON_S,
    PREDICTION_STEP_S,
    RISK_PARAMETERS,
)


def nominal_state_at_analysis():
    return None


def future_segments() -> list[CommandSegment]:
    horizon_end = ANALYSIS_TIME_S + PREDICTION_HORIZON_S
    segments = []
    for phase in COMMAND_SCHEDULE:
        start = max(phase.start_s, ANALYSIS_TIME_S)
        end = min(phase.end_s, horizon_end)
        if end > start:
            segments.append(CommandSegment(start - ANALYSIS_TIME_S, end - ANALYSIS_TIME_S, phase.left_rad_s, phase.right_rad_s))
    return segments


def main() -> int:
    current_x = CALIBRATION_CURRENT_X
    current_y = CALIBRATION_CURRENT_Y
    current_yaw = CALIBRATION_CURRENT_YAW_RAD
    left_arc_v = CALIBRATION_CURRENT_LINEAR_VELOCITY_M_S
    left_arc_omega = CALIBRATION_CURRENT_ANGULAR_VELOCITY_RAD_S
    planned = predict_command_conditioned_trajectory(
        x=current_x,
        y=current_y,
        yaw_rad=current_yaw,
        command_segments=future_segments(),
        horizon_s=PREDICTION_HORIZON_S,
        step_s=PREDICTION_STEP_S,
    )
    state = predict_state_only_trajectory(
        x=current_x,
        y=current_y,
        yaw_rad=current_yaw,
        linear_velocity_m_s=left_arc_v,
        angular_velocity_rad_s=left_arc_omega,
        horizon_s=PREDICTION_HORIZON_S,
        step_s=PREDICTION_STEP_S,
    )

    print(f"analysis_time_s={ANALYSIS_TIME_S:.3f}")
    print(f"calibration_current_x={current_x:.9f} calibration_current_y={current_y:.9f} yaw={current_yaw:.9f}")
    print(f"risk_parameters={RISK_PARAMETERS}")
    for spec in OBSTACLE_SPECS:
        obstacle = ObstacleFootprint(spec.obstacle_id, spec.center_x, spec.center_y, spec.size_x, spec.size_y)
        result = analyze_dual_trajectory_obstacle(planned, state, obstacle, RISK_PARAMETERS)
        print(
            f"{spec.obstacle_id} {spec.def_name} "
            f"center=({spec.center_x:.6f},{spec.center_y:.6f}) size=({spec.size_x:.3f},{spec.size_y:.3f}) "
            f"planned_clearance={result.planned_result.minimum_clearance_m:.9f} "
            f"planned_ttc={result.planned_result.first_corridor_entry_time_s} "
            f"planned_risk={result.planned_result.risk_score:.9f} "
            f"state_clearance={result.state_result.minimum_clearance_m:.9f} "
            f"state_ttc={result.state_result.first_corridor_entry_time_s} "
            f"state_risk={result.state_result.risk_score:.9f} "
            f"combined={result.combined_risk_score:.9f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
