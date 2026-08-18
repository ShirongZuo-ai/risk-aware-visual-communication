"""Frozen M9-A-I1 identities and typed configuration (no simulator execution)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

PROTOCOL_VERSION = "m9a-p-v1"
SEED_MAPPING_VERSION = "m9a-seed-v1"
PHYSICAL_RADIUS_M = 0.037
PREDICTOR_UNCERTAINTY_CORRIDOR_RADIUS_M = 0.037592257
BASIC_TIMESTEP_S = 0.032
NOMINAL_HORIZONS_S = (0.5, 1.0, 2.0)


class Split(str, Enum):
    PILOT = "pilot"
    CALIBRATION = "calibration"
    FORMAL = "formal"


class ScenarioFamily(str, Enum):
    F1 = "F1"; F2 = "F2"; F3 = "F3"; F4 = "F4"
    F5 = "F5"; F6 = "F6"; F7 = "F7"; F8 = "F8"


class ExclusionCode(str, Enum):
    SIMULATOR_CRASH = "SIMULATOR_CRASH"
    PROCESS_FAILURE = "PROCESS_FAILURE"
    INCOMPLETE_LOG = "INCOMPLETE_LOG"
    NONMONOTONIC_TIME = "NONMONOTONIC_TIME"
    CORRUPT_ARTIFACT = "CORRUPT_ARTIFACT"
    HASH_MISMATCH = "HASH_MISMATCH"
    MISSING_CONTACT_STREAM = "MISSING_CONTACT_STREAM"
    CONTACT_VALIDATION_FAILURE = "CONTACT_VALIDATION_FAILURE"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    UNDECLARED_GEOMETRY_CHANGE = "UNDECLARED_GEOMETRY_CHANGE"
    MISSING_PREDICTOR_INPUT = "MISSING_PREDICTOR_INPUT"
    MISSING_COMMAND_SCHEDULE = "MISSING_COMMAND_SCHEDULE"
    COORDINATE_UNIT_MISMATCH = "COORDINATE_UNIT_MISMATCH"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    TECHNICAL_CONTEXT_SHORTFALL = "TECHNICAL_CONTEXT_SHORTFALL"


@dataclass(frozen=True)
class Command:
    start_s: float; end_s: float; left_rad_s: float; right_rad_s: float
    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.start_s, self.end_s, self.left_rad_s, self.right_rad_s)) or self.start_s < 0 or self.end_s <= self.start_s:
            raise ValueError("command values must be finite and form a positive interval")


@dataclass(frozen=True)
class Obstacle:
    obstacle_id: str; kind: str; min_x_m: float; max_x_m: float; min_y_m: float; max_y_m: float
    def __post_init__(self):
        if not self.obstacle_id or self.kind not in {"obstacle", "wall"} or self.min_x_m >= self.max_x_m or self.min_y_m >= self.max_y_m:
            raise ValueError("invalid obstacle configuration")


@dataclass(frozen=True)
class EpisodeConfig:
    split: Split; family: ScenarioFamily; parameter_set_id: str; replicate_index: int
    initial_pose: tuple[float, float, float]; commands: tuple[Command, ...]; obstacles: tuple[Obstacle, ...]
    protocol_version: str = PROTOCOL_VERSION
    def __post_init__(self):
        if not self.parameter_set_id or self.replicate_index < 0 or len(self.initial_pose) != 3 or not self.commands or not self.obstacles:
            raise ValueError("incomplete episode configuration")
        if self.commands[0].start_s != 0 or any(a.end_s != b.start_s for a, b in zip(self.commands, self.commands[1:])):
            raise ValueError("command schedule must start at zero and be contiguous")
    @property
    def seed(self) -> int:
        return seed_for(self.split, self.family, self.parameter_set_id, self.replicate_index)
    @property
    def episode_id(self) -> str:
        return f"m9a-{self.split.value}-{self.family.value.lower()}-{self.parameter_set_id.lower()}-r{self.replicate_index:02d}"


def seed_for(split: Split, family: ScenarioFamily, parameter_set_id: str, replicate_index: int) -> int:
    """Map a planned identity to its collision-free six-digit namespace seed."""
    if replicate_index < 0 or replicate_index >= {Split.PILOT: 1, Split.CALIBRATION: 2, Split.FORMAL: 3}[split]:
        raise ValueError("replicate index outside frozen split allocation")
    try:
        p_index = int(parameter_set_id.removeprefix("P")) - 1
    except ValueError as exc:
        raise ValueError("parameter_set_id must be P01..P06") from exc
    if p_index not in range(6):
        raise ValueError("parameter_set_id must be P01..P06")
    family_index = list(ScenarioFamily).index(family)
    base = {Split.PILOT: 910000, Split.CALIBRATION: 920000, Split.FORMAL: 930000}[split]
    return base + family_index * 1000 + p_index * 10 + replicate_index
