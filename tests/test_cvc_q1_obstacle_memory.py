from __future__ import annotations

import pytest

from communication.cvc_q1_obstacle_memory import CausalObstacleMemory, Pose2D
from navigation.cvc_q1_local_planner import LocalObstacleEstimate


def test_memory_transforms_obstacle_after_robot_turn_and_translation() -> None:
    memory = CausalObstacleMemory(10)
    observation = (LocalObstacleEstimate(.30, .10, .04, .05),)
    source = Pose2D(0, 0, 0)
    memory.update(observation, source, 0)
    current = Pose2D(.10, 0, 0)
    recalled = memory.preview((), current, 1, current, 1)
    assert recalled[0].x_m == pytest.approx(.20)
    assert recalled[0].y_m == pytest.approx(.10)
    assert recalled[0].source == "causal_static_obstacle_memory"


def test_repeated_stale_observation_does_not_refresh_source_age() -> None:
    memory = CausalObstacleMemory(2)
    observation = (LocalObstacleEstimate(.30, 0, .04, .05),)
    pose = Pose2D(0, 0, 0)
    memory.update(observation, pose, 0)
    memory.update(observation, pose, 0)
    assert memory.source_step == 0
    assert memory.preview((), pose, 0, pose, 3) == ()


def test_preview_current_observation_does_not_mutate_actual_memory() -> None:
    memory = CausalObstacleMemory(10)
    pose = Pose2D(0, 0, 0)
    preview = memory.preview((LocalObstacleEstimate(.2, 0, .04, .05),), pose, 2, pose, 2)
    assert preview
    assert memory.source_step is None
