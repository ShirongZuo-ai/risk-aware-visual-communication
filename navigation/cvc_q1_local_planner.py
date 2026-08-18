"""Deterministic safety-first sampled local planner for CVC-Q1.

Runtime inputs are causal robot-local goal direction and visual obstacle
estimates.  Simulator geometry and evaluator outcomes are intentionally absent.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from navigation.trajectory_prediction import (
    CommandSegment,
    EPUCK_AXLE_LENGTH_M,
    EPUCK_WHEEL_RADIUS_M,
    TrajectoryPoint,
    normalize_angle,
    predict_command_conditioned_trajectory,
)


@dataclass(frozen=True, order=True)
class CandidateAction:
    linear_m_s: float
    angular_rad_s: float


@dataclass(frozen=True)
class LocalObstacleEstimate:
    x_m: float
    y_m: float
    radius_m: float
    range_uncertainty_m: float
    source: str = "decoded_visual"


@dataclass(frozen=True)
class CandidateEvaluation:
    action: CandidateAction
    trajectory: tuple[TrajectoryPoint, ...]
    conservative_min_clearance_m: float
    safety_class: str
    hard_feasible: bool
    preferred_safe: bool
    goal_progress_m: float
    terminal_heading_error_rad: float
    wheel_left_rad_s: float
    wheel_right_rad_s: float


@dataclass(frozen=True)
class PlannerDecision:
    selected: CandidateEvaluation
    evaluations: tuple[CandidateEvaluation, ...]
    safe_action_ids: tuple[str, ...]
    preferred_action_ids: tuple[str, ...]
    selection_mode: str


def action_id(action: CandidateAction) -> str:
    return f"v{action.linear_m_s:+.3f}_w{action.angular_rad_s:+.3f}"


def default_action_grid() -> tuple[CandidateAction, ...]:
    return tuple(CandidateAction(v, omega)
                 for v in (0.0, 0.045, 0.080)
                 for omega in (-1.6, -0.8, 0.0, 0.8, 1.6))


def twist_to_wheels(action: CandidateAction) -> tuple[float, float]:
    left = (action.linear_m_s - action.angular_rad_s * EPUCK_AXLE_LENGTH_M / 2.0) / EPUCK_WHEEL_RADIUS_M
    right = (action.linear_m_s + action.angular_rad_s * EPUCK_AXLE_LENGTH_M / 2.0) / EPUCK_WHEEL_RADIUS_M
    return left, right


def rollout(action: CandidateAction, horizon_s: float, step_s: float) -> tuple[TrajectoryPoint, ...]:
    left, right = twist_to_wheels(action)
    segment = CommandSegment(0.0, horizon_s, left, right)
    return tuple(predict_command_conditioned_trajectory(
        x=0.0, y=0.0, yaw_rad=0.0, command_segments=(segment,),
        horizon_s=horizon_s, step_s=step_s,
    ))


def _conservative_clearance(point: TrajectoryPoint, obstacle: LocalObstacleEstimate,
                            robot_radius_m: float) -> float:
    center_distance = math.hypot(point.x - obstacle.x_m, point.y - obstacle.y_m)
    return center_distance - robot_radius_m - obstacle.radius_m - obstacle.range_uncertainty_m


def evaluate_candidate(
    action: CandidateAction,
    obstacles: Iterable[LocalObstacleEstimate],
    goal_bearing_rad: float,
    *,
    horizon_s: float,
    step_s: float,
    robot_radius_m: float,
    hard_clearance_m: float,
    preferred_clearance_m: float,
) -> CandidateEvaluation:
    points = rollout(action, horizon_s, step_s)
    obstacle_list = tuple(obstacles)
    if obstacle_list:
        clearance = min(_conservative_clearance(point, obstacle, robot_radius_m)
                        for point in points for obstacle in obstacle_list)
    else:
        clearance = math.inf
    hard = clearance >= hard_clearance_m
    preferred = clearance >= preferred_clearance_m
    safety_class = "preferred_safe" if preferred else ("hard_safe" if hard else "hard_unsafe")
    terminal = points[-1]
    progress = terminal.x * math.cos(goal_bearing_rad) + terminal.y * math.sin(goal_bearing_rad)
    heading_error = abs(normalize_angle(terminal.yaw_rad - goal_bearing_rad))
    left, right = twist_to_wheels(action)
    return CandidateEvaluation(action, points, clearance, safety_class, hard, preferred,
                               progress, heading_error, left, right)


def _away_score(action: CandidateAction, obstacles: tuple[LocalObstacleEstimate, ...]) -> float:
    if not obstacles:
        return -abs(action.angular_rad_s)
    weighted_side = sum(obstacle.y_m / max(math.hypot(obstacle.x_m, obstacle.y_m), 1e-6)
                        for obstacle in obstacles)
    # Positive obstacle y is robot-left; negative omega is a right turn away.
    return -action.angular_rad_s * weighted_side


def plan_local_action(
    obstacles: Iterable[LocalObstacleEstimate],
    goal_bearing_rad: float,
    *,
    actions: tuple[CandidateAction, ...] | None = None,
    horizon_s: float = 1.5,
    step_s: float = 0.1,
    robot_radius_m: float = 0.037,
    hard_clearance_m: float = 0.025,
    preferred_clearance_m: float = 0.075,
    near_slowdown_range_m: float | None = None,
    near_max_speed_m_s: float = 0.045,
) -> PlannerDecision:
    """Select safety-feasible action first, then goal-efficient action."""
    if not 0 < hard_clearance_m < preferred_clearance_m:
        raise ValueError("invalid safety thresholds")
    if horizon_s <= 0 or step_s <= 0:
        raise ValueError("invalid rollout timing")
    obstacle_tuple = tuple(obstacles)
    action_tuple = default_action_grid() if actions is None else tuple(actions)
    if not action_tuple:
        raise ValueError("at least one candidate action is required")
    evaluations = tuple(evaluate_candidate(
        action, obstacle_tuple, goal_bearing_rad, horizon_s=horizon_s, step_s=step_s,
        robot_radius_m=robot_radius_m, hard_clearance_m=hard_clearance_m,
        preferred_clearance_m=preferred_clearance_m,
    ) for action in action_tuple)
    preferred = [item for item in evaluations if item.preferred_safe]
    hard_safe = [item for item in evaluations if item.hard_feasible]
    near_obstacle = (near_slowdown_range_m is not None and obstacle_tuple and
                     min(math.hypot(item.x_m, item.y_m) for item in obstacle_tuple) <= near_slowdown_range_m)
    if near_obstacle:
        preferred = [item for item in preferred if item.action.linear_m_s <= near_max_speed_m_s]
        hard_safe = [item for item in hard_safe if item.action.linear_m_s <= near_max_speed_m_s]
    moving_preferred = [item for item in preferred if item.action.linear_m_s > 0]
    if moving_preferred:
        pool, mode = moving_preferred, "preferred_safe_goal_efficient"
        selected = max(pool, key=lambda item: (
            item.goal_progress_m, -item.terminal_heading_error_rad,
            _away_score(item.action, obstacle_tuple), -abs(item.action.angular_rad_s),
        ))
    elif preferred:
        pool, mode = preferred, "preferred_safe_stationary"
        selected = max(pool, key=lambda item: (
            _away_score(item.action, obstacle_tuple), -abs(item.action.angular_rad_s),
        ))
    elif hard_safe:
        # In the intermediate region safety margin outranks progress.
        pool, mode = hard_safe, "hard_safe_max_margin"
        selected = max(pool, key=lambda item: (
            item.conservative_min_clearance_m, item.goal_progress_m,
            _away_score(item.action, obstacle_tuple), -abs(item.action.angular_rad_s),
        ))
    else:
        stops = [item for item in evaluations
                 if item.action.linear_m_s == 0.0 and item.action.angular_rad_s == 0.0]
        if not stops:
            raise RuntimeError("candidate grid lacks deterministic stop fallback")
        selected, mode = stops[0], "hard_unsafe_stop_fallback"
    return PlannerDecision(
        selected, evaluations,
        tuple(action_id(item.action) for item in evaluations if item.hard_feasible),
        tuple(action_id(item.action) for item in evaluations if item.preferred_safe),
        mode,
    )


def compare_decisions(held: PlannerDecision, current: PlannerDecision) -> dict:
    held_safe, current_safe = set(held.safe_action_ids), set(current.safe_action_ids)
    return {
        "action_changed": action_id(held.selected.action) != action_id(current.selected.action),
        "safe_set_changed": held_safe != current_safe,
        "safe_actions_added": sorted(current_safe - held_safe),
        "safe_actions_removed": sorted(held_safe - current_safe),
        "held_safety_class": held.selected.safety_class,
        "current_safety_class": current.selected.safety_class,
        "safety_class_changed": held.selected.safety_class != current.selected.safety_class,
        "selected_margin_change_m": (
            current.selected.conservative_min_clearance_m - held.selected.conservative_min_clearance_m
        ),
        "selected_goal_progress_change_m": current.selected.goal_progress_m - held.selected.goal_progress_m,
        "goal_efficient_safe_path_changed": (
            action_id(held.selected.action) != action_id(current.selected.action)
            and current.selected.hard_feasible
        ),
    }
