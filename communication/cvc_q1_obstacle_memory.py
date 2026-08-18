"""Causal odometry-frame memory for static visually observed Q1 obstacles."""
from __future__ import annotations

from dataclasses import dataclass
import math

from navigation.cvc_q1_local_planner import LocalObstacleEstimate


@dataclass(frozen=True)
class Pose2D:
    x_m: float
    y_m: float
    yaw_rad: float


@dataclass(frozen=True)
class WorldObstacleTrack:
    x_m: float
    y_m: float
    radius_m: float
    uncertainty_m: float


def local_to_world(obstacle: LocalObstacleEstimate, pose: Pose2D) -> WorldObstacleTrack:
    cosine, sine = math.cos(pose.yaw_rad), math.sin(pose.yaw_rad)
    return WorldObstacleTrack(
        pose.x_m + cosine * obstacle.x_m - sine * obstacle.y_m,
        pose.y_m + sine * obstacle.x_m + cosine * obstacle.y_m,
        obstacle.radius_m, obstacle.range_uncertainty_m,
    )


def world_to_local(track: WorldObstacleTrack, pose: Pose2D) -> LocalObstacleEstimate:
    dx, dy = track.x_m - pose.x_m, track.y_m - pose.y_m
    cosine, sine = math.cos(pose.yaw_rad), math.sin(pose.yaw_rad)
    return LocalObstacleEstimate(
        cosine * dx + sine * dy,
        -sine * dx + cosine * dy,
        track.radius_m, track.uncertainty_m, "causal_static_obstacle_memory",
    )


class CausalObstacleMemory:
    def __init__(self, max_age_steps: int) -> None:
        if max_age_steps < 1:
            raise ValueError("max_age_steps must be positive")
        self.max_age_steps = max_age_steps
        self._tracks: tuple[WorldObstacleTrack, ...] = ()
        self._source_step: int | None = None

    def preview(self, observations: tuple[LocalObstacleEstimate, ...], source_pose: Pose2D,
                source_step: int, current_pose: Pose2D, current_step: int) -> tuple[LocalObstacleEstimate, ...]:
        if observations:
            tracks = tuple(local_to_world(item, source_pose) for item in observations)
            return tuple(world_to_local(item, current_pose) for item in tracks)
        if self._source_step is None or current_step - self._source_step > self.max_age_steps:
            return ()
        return tuple(world_to_local(item, current_pose) for item in self._tracks)

    def update(self, observations: tuple[LocalObstacleEstimate, ...], source_pose: Pose2D,
               source_step: int) -> None:
        if observations and (self._source_step is None or source_step >= self._source_step):
            self._tracks = tuple(local_to_world(item, source_pose) for item in observations)
            self._source_step = source_step

    @property
    def source_step(self) -> int | None:
        return self._source_step
