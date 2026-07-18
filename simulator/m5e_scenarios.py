"""Deterministic static-AABB scenarios for M5E-B."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import random
from typing import Iterable

from simulator.m5e_config import M5E_GENERATOR_VERSION, SCENARIO_IDS, SNAPSHOT_PROGRESS_TARGETS


@dataclass(frozen=True)
class WheelCommandPhase:
    name: str
    start_s: float
    end_s: float
    left_rad_s: float
    right_rad_s: float


@dataclass(frozen=True)
class M5EObstacleSpec:
    obstacle_id: str
    role: str
    center_world: tuple[float, float, float]
    size_xyz: tuple[float, float, float]
    orientation: tuple[float, float, float, float]
    display_color: tuple[float, float, float]
    expected_visibility_role: str
    expected_risk_role: str


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_id: str
    scenario_name: str
    split: str
    seed: int
    start_pose: tuple[float, float, float]
    command_schedule: tuple[WheelCommandPhase, ...]
    duration_seconds: float
    trajectory_horizon_s: float
    obstacle_specs: tuple[M5EObstacleSpec, ...]
    snapshot_progress_targets: tuple[float, ...]
    validation_rules: dict[str, object]
    expected_tags: tuple[str, ...]
    generator_version: str = M5E_GENERATOR_VERSION


_NAMES = {
    "S1": "straight_collision_relevant",
    "S2": "off_trajectory_visual_distractor",
    "S3": "left_turn_trajectory",
    "S4": "right_turn_trajectory",
    "S5": "planned_state_disagreement",
    "S6": "large_low_risk_small_high_risk",
    "S7": "partial_visibility",
    "S8": "low_risk_control",
}


def scenario_index(scenario_id: str) -> int:
    if scenario_id not in SCENARIO_IDS:
        raise ValueError(f"unknown scenario id: {scenario_id}")
    return int(scenario_id[1:])


def _jitter(seed: int, magnitude: float = 0.002) -> float:
    return random.Random(seed).uniform(-magnitude, magnitude)


def _obstacle(
    scenario_id: str,
    name: str,
    role: str,
    x: float,
    y: float,
    size: tuple[float, float, float],
    color: tuple[float, float, float],
    visibility: str = "fully_visible",
    risk: str = "context",
) -> M5EObstacleSpec:
    return M5EObstacleSpec(
        obstacle_id=f"M5E_{scenario_id}_{name}",
        role=role,
        center_world=(x, y, size[2] * 0.5),
        size_xyz=size,
        orientation=(0.0, 0.0, 1.0, 0.0),
        display_color=color,
        expected_visibility_role=visibility,
        expected_risk_role=risk,
    )


def _straight_schedule() -> tuple[WheelCommandPhase, ...]:
    return (WheelCommandPhase("straight", 0.0, 6.0, 2.0, 2.0),)


def _approach_turn_schedule() -> tuple[WheelCommandPhase, ...]:
    return (
        WheelCommandPhase("straight", 0.0, 4.5, 2.0, 2.0),
        WheelCommandPhase("departure_arc", 4.5, 6.0, 1.0, 2.0),
    )


def _turn_schedule(direction: str) -> tuple[WheelCommandPhase, ...]:
    if direction == "left":
        turn = (1.0, 2.0)
    elif direction == "right":
        turn = (2.0, 1.0)
    else:
        raise ValueError("direction must be left or right")
    return (
        WheelCommandPhase("approach", 0.0, 2.0, 2.0, 2.0),
        WheelCommandPhase(f"{direction}_arc", 2.0, 6.0, *turn),
    )


def _disagreement_schedule() -> tuple[WheelCommandPhase, ...]:
    return (
        WheelCommandPhase("left_arc", 0.0, 4.25, 1.0, 2.0),
        WheelCommandPhase("right_arc", 4.25, 6.0, 2.0, 1.0),
    )


def generate_scenario(scenario_id: str, split: str, seed: int) -> ScenarioConfig:
    """Return one deterministic static-AABB configuration without Webots access."""

    index = scenario_index(scenario_id)
    if split not in {"smoke", "calibration", "formal"}:
        raise ValueError("split must be smoke, calibration, or formal")
    dx = _jitter(seed * 17 + index)
    dy = _jitter(seed * 31 + index)
    small = (0.025, 0.025, 0.050)
    medium = (0.050, 0.050, 0.060)
    large = (0.150, 0.150, 0.080)
    if scenario_id == "S1":
        obstacles = (_obstacle("S1", "CONFLICT", "high_risk_center", 0.270 + dx, dy, (0.030, 0.030, 0.050), (0.9, 0.2, 0.15), risk="high"),)
        schedule = _approach_turn_schedule()
        tags = ("straight", "center_control", "collision_relevant")
    elif scenario_id == "S2":
        obstacles = (
            _obstacle("S2", "RISK", "small_high_risk", 0.260 + dx, dy, (0.015, 0.015, 0.015), (0.9, 0.15, 0.15), risk="high"),
            _obstacle("S2", "DISTRACTOR", "large_off_trajectory", 0.440 + dx, 0.130 + dy, large, (0.15, 0.35, 0.9), risk="low"),
        )
        schedule = _approach_turn_schedule()
        tags = ("straight", "object_risk_disagreement", "distractor")
    elif scenario_id in {"S3", "S4"}:
        sign = 1.0 if scenario_id == "S3" else -1.0
        direction = "left" if sign > 0 else "right"
        turn_risk_x = 0.210 if scenario_id == "S3" else 0.155
        turn_risk_y = 0.110 + dy if scenario_id == "S3" else -(0.080 + dy)
        obstacles = (
            _obstacle(scenario_id, "TURN_RISK", "turn_high_risk", turn_risk_x + dx, turn_risk_y, (0.030, 0.030, 0.060), (0.2, 0.8, 0.25), risk="high"),
            _obstacle(scenario_id, "CONTEXT", "far_visible_context", 0.400 + dx, sign * 0.200, large, (0.45, 0.45, 0.45), risk="low"),
        )
        schedule = _turn_schedule(direction)
        tags = ("turn", direction, "mirror_pair")
    elif scenario_id == "S5":
        obstacles = (
            _obstacle("S5", "PLANNED_BRANCH", "planned_branch_obstacle", 0.120 + dx, 0.150 + dy, (0.015, 0.015, 0.050), (0.9, 0.2, 0.2), risk="planned"),
            _obstacle("S5", "STATE_BRANCH", "state_branch_obstacle", 0.060 + dx, 0.155 + dy, (0.020, 0.020, 0.050), (0.15, 0.8, 0.25), risk="state"),
            _obstacle("S5", "MID_SUPPORT", "mid_support", 0.030 + dx, -0.400 + dy, medium, (0.45, 0.45, 0.45), risk="low"),
            _obstacle("S5", "LATE_SUPPORT", "late_support", 0.400 + dx, dy, large, (0.35, 0.35, 0.35), risk="low"),
        )
        schedule = _disagreement_schedule()
        tags = ("trajectory_disagreement", "combined_max")
    elif scenario_id == "S6":
        obstacles = (
            _obstacle("S6", "SMALL_RISK", "small_high_risk", 0.250 + dx, dy, (0.004, 0.004, 0.030), (0.9, 0.2, 0.2), risk="high"),
            _obstacle("S6", "LARGE_LOW", "large_low_risk", 0.600 + dx, 0.025 + dy, large, (0.2, 0.35, 0.9), risk="low"),
        )
        schedule = _approach_turn_schedule()
        tags = ("area_risk_disagreement", "tile_max")
    elif scenario_id == "S7":
        obstacles = (
            _obstacle("S7", "RISK", "center_high_risk", 0.270 + dx, dy, (0.030, 0.030, 0.050), (0.9, 0.2, 0.2), risk="high"),
            _obstacle("S7", "PARTIAL", "partial_risk", 0.350 + dx, 0.070 + dy, small, (0.8, 0.2, 0.85), "partially_visible", "low"),
        )
        schedule = _approach_turn_schedule()
        tags = ("partial_visibility", "clipping")
    else:  # S8
        obstacles = (_obstacle("S8", "LOW", "visible_low_risk", 0.650 + dx, 0.060 + dy, medium, (0.85, 0.7, 0.15), risk="low"),)
        schedule = _straight_schedule()
        tags = ("low_risk_control",)
    config = ScenarioConfig(
        scenario_id=scenario_id,
        scenario_name=_NAMES[scenario_id],
        split=split,
        seed=seed,
        start_pose=(0.0, 0.0, 0.0),
        command_schedule=schedule,
        duration_seconds=6.0,
        trajectory_horizon_s=2.0,
        obstacle_specs=obstacles,
        snapshot_progress_targets=SNAPSHOT_PROGRESS_TARGETS,
        validation_rules={"scenario_id": scenario_id, "protocol": "m5e-a"},
        expected_tags=tags,
    )
    validate_config(config)
    return config


def validate_config(config: ScenarioConfig) -> None:
    if config.scenario_id not in SCENARIO_IDS:
        raise ValueError("scenario ID is not registered")
    if config.duration_seconds <= 0 or config.trajectory_horizon_s <= 0:
        raise ValueError("durations must be positive")
    if tuple(sorted(config.snapshot_progress_targets)) != config.snapshot_progress_targets:
        raise ValueError("snapshot progress targets must be sorted")
    if len(config.snapshot_progress_targets) != 4 or len(set(config.snapshot_progress_targets)) != 4:
        raise ValueError("exactly four unique snapshot targets are required")
    obstacle_ids = [item.obstacle_id for item in config.obstacle_specs]
    if not obstacle_ids or len(obstacle_ids) != len(set(obstacle_ids)):
        raise ValueError("obstacle IDs must be nonempty and unique")
    previous_end = 0.0
    for phase in config.command_schedule:
        if phase.start_s != previous_end or phase.end_s <= phase.start_s or phase.end_s > config.duration_seconds:
            raise ValueError("command schedule must be contiguous and inside the episode duration")
        previous_end = phase.end_s
    if previous_end != config.duration_seconds:
        raise ValueError("command schedule must cover the full episode")
    for item in config.obstacle_specs:
        if item.orientation != (0.0, 0.0, 1.0, 0.0):
            raise ValueError("M5E-B supports static unrotated AABB obstacles only")
        if any(value <= 0 for value in item.size_xyz):
            raise ValueError("obstacle sizes must be positive")


def config_dict(config: ScenarioConfig) -> dict:
    return asdict(config)


def config_hash(config: ScenarioConfig) -> str:
    payload = json.dumps(config_dict(config), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def configs_for_smoke(seeds: Iterable[int]) -> tuple[ScenarioConfig, ...]:
    values = tuple(seeds)
    if len(values) != 8:
        raise ValueError("smoke generation requires one seed per scenario")
    return tuple(generate_scenario(scenario_id, "smoke", seed) for scenario_id, seed in zip(SCENARIO_IDS, values))
