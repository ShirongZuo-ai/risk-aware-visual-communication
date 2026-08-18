"""M9-A physical ground truth. Predictor outputs are deliberately not inputs."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from risk_map.geometry import segment_to_aabb_distance
from risk_map.models import ObstacleFootprint
from simulator.m9a_config import PHYSICAL_RADIUS_M

# World-coordinate contact positions are transported as C doubles. 1e-6 m is
# far above double round-off at the metre scale yet only 0.001 mm and 1/26000
# of the physical robot radius. It is frozen before I2-V2 execution.
EPSILON_CONTACT_M = 1e-6


@dataclass(frozen=True)
class ActualState:
    timestamp_s: float; x_m: float; y_m: float; yaw_rad: float = 0.0


@dataclass(frozen=True)
class RawContactObservation:
    timestamp_s: float; counterpart_node_id: int | None; counterpart_def: str | None
    point_xyz_m: tuple[float, float, float]; raw_index: int = 0


@dataclass(frozen=True)
class EligibleCounterpart:
    root_def: str; root_node_id: int; kind: str
    def __post_init__(self):
        if not self.root_def or self.root_node_id < 0 or self.kind not in {"obstacle", "wall"}:
            raise ValueError("eligible counterpart must be a declared obstacle/wall root")


@dataclass(frozen=True)
class ContactSet:
    queried_root_def: str; queried_root_node_id: int
    points: tuple[RawContactObservation, ...]


@dataclass(frozen=True)
class PairContactResult:
    timestamp_s: float; matched_counterpart_defs: tuple[str, ...]
    nearest_distance_by_def_m: tuple[tuple[str, float | None], ...]
    match_count_by_def: tuple[tuple[str, int], ...]
    validated_pair_contact: bool


@dataclass(frozen=True)
class ValidatedCollisionEvent:
    start_s: float; end_s: float; counterpart_node_ids: tuple[int, ...]


@dataclass(frozen=True)
class HorizonWindow:
    states: tuple[ActualState, ...]; horizon_s: float; full_intervals: int; interpolation_fraction: float


def match_dual_sided_contacts(robot: ContactSet, counterpart_sets: dict[EligibleCounterpart, ContactSet], *, epsilon_contact_m: float = EPSILON_CONTACT_M) -> PairContactResult:
    """Match declared roots by world positions; ContactPoint.node_id is diagnostic only."""
    if epsilon_contact_m <= 0 or not math.isfinite(epsilon_contact_m):
        raise ValueError("epsilon_contact_m must be finite and positive")
    if not robot.points:
        timestamp = next((p.timestamp_s for s in counterpart_sets.values() for p in s.points), 0.0)
    else:
        timestamp = robot.points[0].timestamp_s
    nearest=[]; counts=[]; matched=[]
    for counterpart, contact_set in sorted(counterpart_sets.items(), key=lambda item:item[0].root_def):
        if contact_set.queried_root_def != counterpart.root_def or contact_set.queried_root_node_id != counterpart.root_node_id:
            raise ValueError("counterpart contact set does not match frozen eligible root")
        distances=[math.dist(a.point_xyz_m,b.point_xyz_m) for a in robot.points for b in contact_set.points]
        nearest_distance=min(distances) if distances else None
        count=sum(distance <= epsilon_contact_m for distance in distances)
        nearest.append((counterpart.root_def,nearest_distance)); counts.append((counterpart.root_def,count))
        if count: matched.append(counterpart.root_def)
    return PairContactResult(timestamp,tuple(matched),tuple(nearest),tuple(counts),bool(matched))


def group_collision_events(observations: Iterable[PairContactResult], merge_gap_s: float = 0.5) -> tuple[ValidatedCollisionEvent, ...]:
    contacts=sorted((x for x in observations if x.validated_pair_contact),key=lambda x:x.timestamp_s)
    groups=[]
    for contact in contacts:
        if not groups or contact.timestamp_s-groups[-1][-1].timestamp_s >= merge_gap_s: groups.append([contact])
        else: groups[-1].append(contact)
    # More than one matched root is retained. Planned scientific episodes treat
    # simultaneous multi-root contact as CONTACT_VALIDATION_FAILURE, not a choice.
    return tuple(ValidatedCollisionEvent(g[0].timestamp_s,g[-1].timestamp_s,tuple()) for g in groups)


def extract_exact_horizon(states: Iterable[ActualState], decision_index: int, horizon_s: float) -> HorizonWindow | None:
    values = tuple(states)
    if decision_index < 0 or decision_index >= len(values) or horizon_s <= 0:
        raise ValueError("invalid horizon request")
    start = values[decision_index]
    target = start.timestamp_s + horizon_s
    selected = [start]
    upper = None
    for state in values[decision_index + 1:]:
        if state.timestamp_s < target - 1e-12:
            selected.append(state)
        else:
            upper = state
            break
    if upper is None:
        return None
    lower = selected[-1]
    if math.isclose(upper.timestamp_s, target, abs_tol=1e-12):
        endpoint, fraction = upper, 1.0
    else:
        fraction = (target - lower.timestamp_s) / (upper.timestamp_s - lower.timestamp_s)
        delta = math.atan2(math.sin(upper.yaw_rad - lower.yaw_rad), math.cos(upper.yaw_rad - lower.yaw_rad))
        endpoint = ActualState(target, lower.x_m + fraction * (upper.x_m - lower.x_m), lower.y_m + fraction * (upper.y_m - lower.y_m), lower.yaw_rad + fraction * delta)
    selected.append(endpoint)
    return HorizonWindow(tuple(selected), horizon_s, len(selected) - 2, fraction)


def actual_future_min_clearance(window: HorizonWindow, obstacles: Iterable[ObstacleFootprint]) -> float:
    obstacles = tuple(obstacles)
    if not obstacles or len(window.states) < 2:
        raise ValueError("clearance needs geometry and a future segment")
    return min(segment_to_aabb_distance(a.x_m, a.y_m, b.x_m, b.y_m, obstacle).distance_m - PHYSICAL_RADIUS_M for a, b in zip(window.states, window.states[1:]) for obstacle in obstacles)


def collision_within_H(decision_time_s: float, horizon_s: float, events: Iterable[ValidatedCollisionEvent]) -> bool:
    return any(decision_time_s < e.start_s <= decision_time_s + horizon_s + 1e-12 for e in events)


def near_collision_within_H(clearance_m: float, collision: bool, d_near_m: float) -> bool:
    return not collision and clearance_m < d_near_m


def danger_within_H(clearance_m: float, collision: bool, d_near_m: float) -> bool:
    return collision or near_collision_within_H(clearance_m, collision, d_near_m)


def time_to_actual_first_danger(decision_time_s: float, horizon_s: float, events: Iterable[ValidatedCollisionEvent], clearance_crossing_times_s: Iterable[float]) -> float | None:
    candidates = [e.start_s for e in events if decision_time_s < e.start_s <= decision_time_s + horizon_s]
    if not candidates:
        candidates = [t for t in clearance_crossing_times_s if decision_time_s < t <= decision_time_s + horizon_s]
    return min(candidates) - decision_time_s if candidates else None
