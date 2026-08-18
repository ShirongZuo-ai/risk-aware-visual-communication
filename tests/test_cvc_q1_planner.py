from __future__ import annotations

import math

from navigation.cvc_q1_local_planner import (
    CandidateAction,
    LocalObstacleEstimate,
    action_id,
    compare_decisions,
    default_action_grid,
    plan_local_action,
    rollout,
)


def obstacle(x: float, y: float, uncertainty: float = .02) -> LocalObstacleEstimate:
    return LocalObstacleEstimate(x, y, .04, uncertainty)


def test_no_obstacle_selects_nominal_straight_progress() -> None:
    decision = plan_local_action([], 0.0)
    assert decision.selected.action == CandidateAction(.080, 0.0)
    assert decision.selected.safety_class == "preferred_safe"


def test_left_obstacle_selects_right_avoidance() -> None:
    decision = plan_local_action([obstacle(.18, .035)], 0.0)
    assert decision.selected.action.angular_rad_s < 0


def test_right_obstacle_selects_left_avoidance() -> None:
    decision = plan_local_action([obstacle(.18, -.035)], 0.0)
    assert decision.selected.action.angular_rad_s > 0


def test_frontal_near_never_selects_fast_straight() -> None:
    decision = plan_local_action([obstacle(.10, 0.0, .03)], 0.0,
                                 near_slowdown_range_m=.35, near_max_speed_m_s=.045)
    assert decision.selected.action != CandidateAction(.080, 0.0)
    assert decision.selected.action.linear_m_s <= .045


def test_near_speed_cap_is_not_traded_for_more_preferred_safe_progress() -> None:
    decision = plan_local_action([obstacle(.30, .05)], 0.0,
                                 near_slowdown_range_m=.35, near_max_speed_m_s=.045)
    assert decision.selected.action.linear_m_s <= .045


def test_rollout_is_deterministic() -> None:
    action = CandidateAction(.045, -.8)
    assert rollout(action, 1.5, .1) == rollout(action, 1.5, .1)


def test_hard_unsafe_progress_cannot_beat_feasible_candidate() -> None:
    actions = (CandidateAction(.080, 0.0), CandidateAction(.045, -1.6), CandidateAction(0.0, 0.0))
    decision = plan_local_action([obstacle(.15, .0)], 0.0, actions=actions)
    fast = next(item for item in decision.evaluations if item.action == CandidateAction(.080, 0.0))
    assert fast.goal_progress_m > decision.selected.goal_progress_m
    assert not fast.hard_feasible
    assert decision.selected.action != fast.action


def test_all_hard_unsafe_uses_deterministic_stop() -> None:
    decision = plan_local_action([obstacle(.04, 0.0, .04)], 0.0)
    assert decision.selection_mode == "hard_unsafe_stop_fallback"
    assert decision.selected.action == CandidateAction(0.0, 0.0)


def test_safe_set_comparison_detects_held_current_change() -> None:
    held = plan_local_action([obstacle(.40, .02)], 0.0)
    current = plan_local_action([obstacle(.16, .02)], 0.0)
    comparison = compare_decisions(held, current)
    assert comparison["safe_set_changed"]
    assert comparison["action_changed"]
    assert comparison["safe_actions_removed"]


def test_grid_is_small_fixed_and_interpretable() -> None:
    grid = default_action_grid()
    assert len(grid) == 15
    assert {item.linear_m_s for item in grid} == {0.0, .045, .080}
    assert {item.angular_rad_s for item in grid} == {-1.6, -.8, 0.0, .8, 1.6}
    assert len({action_id(item) for item in grid}) == len(grid)
