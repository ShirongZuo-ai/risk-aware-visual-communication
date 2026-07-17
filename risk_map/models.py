"""Validated data models for world-coordinate risk analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class TrajectorySource(Enum):
    PLANNED = "planned"
    STATE = "state"


def require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def require_non_empty(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True)
class ObstacleFootprint:
    obstacle_id: str
    center_x: float
    center_y: float
    size_x: float
    size_y: float

    def __post_init__(self) -> None:
        require_non_empty("obstacle_id", self.obstacle_id)
        for name in ("center_x", "center_y", "size_x", "size_y"):
            require_finite(name, getattr(self, name))
        if self.size_x <= 0:
            raise ValueError("size_x must be positive")
        if self.size_y <= 0:
            raise ValueError("size_y must be positive")

    @property
    def min_x(self) -> float:
        return self.center_x - self.size_x * 0.5

    @property
    def max_x(self) -> float:
        return self.center_x + self.size_x * 0.5

    @property
    def min_y(self) -> float:
        return self.center_y - self.size_y * 0.5

    @property
    def max_y(self) -> float:
        return self.center_y + self.size_y * 0.5


@dataclass(frozen=True)
class RiskParameters:
    corridor_radius_m: float
    sigma_distance_m: float
    tau_time_s: float
    maximum_horizon_s: float
    geometry_tolerance_m: float = 1e-9

    def __post_init__(self) -> None:
        for name in (
            "corridor_radius_m",
            "sigma_distance_m",
            "tau_time_s",
            "maximum_horizon_s",
            "geometry_tolerance_m",
        ):
            require_finite(name, getattr(self, name))
        if self.corridor_radius_m <= 0:
            raise ValueError("corridor_radius_m must be positive")
        if self.sigma_distance_m <= 0:
            raise ValueError("sigma_distance_m must be positive")
        if self.tau_time_s <= 0:
            raise ValueError("tau_time_s must be positive")
        if self.maximum_horizon_s <= 0:
            raise ValueError("maximum_horizon_s must be positive")
        if self.geometry_tolerance_m < 0:
            raise ValueError("geometry_tolerance_m must be non-negative")


@dataclass(frozen=True)
class TrajectoryConflictResult:
    obstacle_id: str
    trajectory_source: TrajectorySource
    minimum_centerline_distance_m: float
    minimum_clearance_m: float
    closest_time_s: float
    enters_corridor: bool
    first_corridor_entry_time_s: float | None
    corridor_overlap_duration_s: float
    spatial_score: float
    temporal_score: float
    risk_score: float

    def __post_init__(self) -> None:
        require_non_empty("obstacle_id", self.obstacle_id)
        if not isinstance(self.trajectory_source, TrajectorySource):
            raise ValueError("trajectory_source must be a TrajectorySource")
        for name in (
            "minimum_centerline_distance_m",
            "minimum_clearance_m",
            "closest_time_s",
            "corridor_overlap_duration_s",
            "spatial_score",
            "temporal_score",
            "risk_score",
        ):
            require_finite(name, getattr(self, name))
        if self.closest_time_s < 0:
            raise ValueError("closest_time_s must be non-negative")
        if self.corridor_overlap_duration_s < 0:
            raise ValueError("corridor_overlap_duration_s must be non-negative")
        if self.enters_corridor:
            if self.first_corridor_entry_time_s is None:
                raise ValueError("first_corridor_entry_time_s is required when enters_corridor is true")
            require_finite("first_corridor_entry_time_s", self.first_corridor_entry_time_s)
            if self.first_corridor_entry_time_s < 0:
                raise ValueError("first_corridor_entry_time_s must be non-negative")
        elif self.first_corridor_entry_time_s is not None:
            raise ValueError("first_corridor_entry_time_s must be None when enters_corridor is false")
        for name in ("spatial_score", "temporal_score", "risk_score"):
            value = getattr(self, name)
            if value < -1e-12 or value > 1.0 + 1e-12:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class DualTrajectoryRiskResult:
    obstacle_id: str
    planned_result: TrajectoryConflictResult
    state_result: TrajectoryConflictResult
    trajectory_disagreement_m: float
    combined_risk_score: float

    def __post_init__(self) -> None:
        require_non_empty("obstacle_id", self.obstacle_id)
        if self.planned_result.obstacle_id != self.obstacle_id:
            raise ValueError("planned_result obstacle_id must match")
        if self.state_result.obstacle_id != self.obstacle_id:
            raise ValueError("state_result obstacle_id must match")
        if self.planned_result.trajectory_source is not TrajectorySource.PLANNED:
            raise ValueError("planned_result must use TrajectorySource.PLANNED")
        if self.state_result.trajectory_source is not TrajectorySource.STATE:
            raise ValueError("state_result must use TrajectorySource.STATE")
        require_finite("trajectory_disagreement_m", self.trajectory_disagreement_m)
        require_finite("combined_risk_score", self.combined_risk_score)
        if self.trajectory_disagreement_m < 0:
            raise ValueError("trajectory_disagreement_m must be non-negative")
        if self.combined_risk_score < -1e-12 or self.combined_risk_score > 1.0 + 1e-12:
            raise ValueError("combined_risk_score must be in [0, 1]")
