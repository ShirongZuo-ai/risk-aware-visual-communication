"""Pure geometry helpers for trajectory-to-AABB analysis."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from navigation.trajectory_prediction import TrajectoryPoint
from risk_map.models import ObstacleFootprint, require_finite


@dataclass(frozen=True)
class PointSegmentDistance:
    distance_m: float
    u: float
    closest_x: float
    closest_y: float


@dataclass(frozen=True)
class SegmentAabbDistance:
    distance_m: float
    u: float
    closest_x: float
    closest_y: float


@dataclass(frozen=True)
class PolylineAabbClosest:
    distance_m: float
    closest_time_s: float
    segment_index: int
    closest_x: float
    closest_y: float


@dataclass(frozen=True)
class CorridorIntervalSummary:
    first_entry_time_s: float | None
    overlap_duration_s: float


def _validate_xy(name: str, x: float, y: float) -> None:
    require_finite(f"{name} x", x)
    require_finite(f"{name} y", y)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _point_in_aabb(x: float, y: float, obstacle: ObstacleFootprint, tolerance_m: float = 0.0) -> bool:
    return (
        obstacle.min_x - tolerance_m <= x <= obstacle.max_x + tolerance_m
        and obstacle.min_y - tolerance_m <= y <= obstacle.max_y + tolerance_m
    )


def point_to_segment_distance(
    point_x: float,
    point_y: float,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> PointSegmentDistance:
    _validate_xy("point", point_x, point_y)
    _validate_xy("start", start_x, start_y)
    _validate_xy("end", end_x, end_y)
    dx = end_x - start_x
    dy = end_y - start_y
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return PointSegmentDistance(math.hypot(point_x - start_x, point_y - start_y), 0.0, start_x, start_y)
    u = _clamp(((point_x - start_x) * dx + (point_y - start_y) * dy) / length_sq, 0.0, 1.0)
    closest_x = start_x + u * dx
    closest_y = start_y + u * dy
    return PointSegmentDistance(math.hypot(point_x - closest_x, point_y - closest_y), u, closest_x, closest_y)


def point_to_aabb_distance(point_x: float, point_y: float, obstacle: ObstacleFootprint) -> float:
    _validate_xy("point", point_x, point_y)
    closest_x = _clamp(point_x, obstacle.min_x, obstacle.max_x)
    closest_y = _clamp(point_y, obstacle.min_y, obstacle.max_y)
    return math.hypot(point_x - closest_x, point_y - closest_y)


def _orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax: float, ay: float, bx: float, by: float, px: float, py: float, tolerance_m: float) -> bool:
    return (
        min(ax, bx) - tolerance_m <= px <= max(ax, bx) + tolerance_m
        and min(ay, by) - tolerance_m <= py <= max(ay, by) + tolerance_m
        and abs(_orientation(ax, ay, bx, by, px, py)) <= tolerance_m
    )


def _segments_intersect(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
    tolerance_m: float,
) -> bool:
    o1 = _orientation(ax, ay, bx, by, cx, cy)
    o2 = _orientation(ax, ay, bx, by, dx, dy)
    o3 = _orientation(cx, cy, dx, dy, ax, ay)
    o4 = _orientation(cx, cy, dx, dy, bx, by)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    return (
        _on_segment(ax, ay, bx, by, cx, cy, tolerance_m)
        or _on_segment(ax, ay, bx, by, dx, dy, tolerance_m)
        or _on_segment(cx, cy, dx, dy, ax, ay, tolerance_m)
        or _on_segment(cx, cy, dx, dy, bx, by, tolerance_m)
    )


def _segment_to_segment_distance(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
    tolerance_m: float = 0.0,
) -> SegmentAabbDistance:
    if _segments_intersect(ax, ay, bx, by, cx, cy, dx, dy, tolerance_m):
        return SegmentAabbDistance(0.0, 0.0, ax, ay)
    candidates = [
        point_to_segment_distance(cx, cy, ax, ay, bx, by),
        point_to_segment_distance(dx, dy, ax, ay, bx, by),
    ]
    reverse = [
        (point_to_segment_distance(ax, ay, cx, cy, dx, dy), 0.0, ax, ay),
        (point_to_segment_distance(bx, by, cx, cy, dx, dy), 1.0, bx, by),
    ]
    best = min(candidates, key=lambda item: item.distance_m)
    best_result = SegmentAabbDistance(best.distance_m, best.u, best.closest_x, best.closest_y)
    for item, u, x, y in reverse:
        if item.distance_m < best_result.distance_m:
            best_result = SegmentAabbDistance(item.distance_m, u, x, y)
    return best_result


def segment_aabb_intersection_interval(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    obstacle: ObstacleFootprint,
    inflation_radius_m: float = 0.0,
    tolerance_m: float = 0.0,
) -> tuple[float, float] | None:
    _validate_xy("start", start_x, start_y)
    _validate_xy("end", end_x, end_y)
    require_finite("inflation_radius_m", inflation_radius_m)
    require_finite("tolerance_m", tolerance_m)
    if inflation_radius_m < 0:
        raise ValueError("inflation_radius_m must be non-negative")
    if tolerance_m < 0:
        raise ValueError("tolerance_m must be non-negative")

    inflate = inflation_radius_m + tolerance_m
    min_x = obstacle.min_x - inflate
    max_x = obstacle.max_x + inflate
    min_y = obstacle.min_y - inflate
    max_y = obstacle.max_y + inflate
    dx = end_x - start_x
    dy = end_y - start_y

    if dx == 0.0 and dy == 0.0:
        if min_x <= start_x <= max_x and min_y <= start_y <= max_y:
            return (0.0, 0.0)
        return None

    u_enter = 0.0
    u_exit = 1.0
    for p, q in (
        (-dx, start_x - min_x),
        (dx, max_x - start_x),
        (-dy, start_y - min_y),
        (dy, max_y - start_y),
    ):
        if abs(p) <= 1e-15:
            if q < 0.0:
                return None
            continue
        u = q / p
        if p < 0:
            u_enter = max(u_enter, u)
        else:
            u_exit = min(u_exit, u)
        if u_enter - u_exit > 1e-12:
            return None
    return (_clamp(u_enter, 0.0, 1.0), _clamp(u_exit, 0.0, 1.0))


def segment_intersects_aabb(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    obstacle: ObstacleFootprint,
    tolerance_m: float = 0.0,
) -> bool:
    return segment_aabb_intersection_interval(start_x, start_y, end_x, end_y, obstacle, 0.0, tolerance_m) is not None


def segment_to_aabb_distance(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    obstacle: ObstacleFootprint,
    tolerance_m: float = 0.0,
) -> SegmentAabbDistance:
    _validate_xy("start", start_x, start_y)
    _validate_xy("end", end_x, end_y)
    require_finite("tolerance_m", tolerance_m)
    if tolerance_m < 0:
        raise ValueError("tolerance_m must be non-negative")
    interval = segment_aabb_intersection_interval(start_x, start_y, end_x, end_y, obstacle, 0.0, tolerance_m)
    if interval is not None:
        u = (interval[0] + interval[1]) / 2.0
        return SegmentAabbDistance(0.0, u, start_x + (end_x - start_x) * u, start_y + (end_y - start_y) * u)

    dx = end_x - start_x
    dy = end_y - start_y
    if abs(dy) <= tolerance_m and abs(dx) > tolerance_m:
        overlap_min = max(min(start_x, end_x), obstacle.min_x)
        overlap_max = min(max(start_x, end_x), obstacle.max_x)
        if overlap_min <= overlap_max + tolerance_m:
            closest_x = (overlap_min + overlap_max) / 2.0
            closest_y = start_y
            if start_y < obstacle.min_y:
                distance = obstacle.min_y - start_y
            elif start_y > obstacle.max_y:
                distance = start_y - obstacle.max_y
            else:
                distance = 0.0
            u = _clamp((closest_x - start_x) / dx, 0.0, 1.0)
            return SegmentAabbDistance(distance, u, closest_x, closest_y)

    if abs(dx) <= tolerance_m and abs(dy) > tolerance_m:
        overlap_min = max(min(start_y, end_y), obstacle.min_y)
        overlap_max = min(max(start_y, end_y), obstacle.max_y)
        if overlap_min <= overlap_max + tolerance_m:
            closest_y = (overlap_min + overlap_max) / 2.0
            closest_x = start_x
            if start_x < obstacle.min_x:
                distance = obstacle.min_x - start_x
            elif start_x > obstacle.max_x:
                distance = start_x - obstacle.max_x
            else:
                distance = 0.0
            u = _clamp((closest_y - start_y) / dy, 0.0, 1.0)
            return SegmentAabbDistance(distance, u, closest_x, closest_y)

    candidates = [
        SegmentAabbDistance(point_to_aabb_distance(start_x, start_y, obstacle), 0.0, start_x, start_y),
        SegmentAabbDistance(point_to_aabb_distance(end_x, end_y, obstacle), 1.0, end_x, end_y),
    ]
    corners = (
        (obstacle.min_x, obstacle.min_y),
        (obstacle.min_x, obstacle.max_y),
        (obstacle.max_x, obstacle.min_y),
        (obstacle.max_x, obstacle.max_y),
    )
    for x, y in corners:
        item = point_to_segment_distance(x, y, start_x, start_y, end_x, end_y)
        candidates.append(SegmentAabbDistance(item.distance_m, item.u, item.closest_x, item.closest_y))
    edges = (
        (obstacle.min_x, obstacle.min_y, obstacle.max_x, obstacle.min_y),
        (obstacle.max_x, obstacle.min_y, obstacle.max_x, obstacle.max_y),
        (obstacle.max_x, obstacle.max_y, obstacle.min_x, obstacle.max_y),
        (obstacle.min_x, obstacle.max_y, obstacle.min_x, obstacle.min_y),
    )
    for edge in edges:
        candidates.append(_segment_to_segment_distance(start_x, start_y, end_x, end_y, *edge, tolerance_m))
    return min(candidates, key=lambda item: item.distance_m)


def validate_trajectory(trajectory: Iterable[TrajectoryPoint]) -> list[TrajectoryPoint]:
    points = list(trajectory)
    if not points:
        raise ValueError("trajectory must contain at least one point")
    previous_time = None
    for index, point in enumerate(points):
        for name in ("time_offset_s", "x", "y", "yaw_rad"):
            require_finite(f"trajectory point {index} {name}", getattr(point, name))
        if point.time_offset_s < 0:
            raise ValueError("time_offset_s must be non-negative")
        if previous_time is not None and point.time_offset_s < previous_time:
            raise ValueError("trajectory time offsets must be non-decreasing")
        previous_time = point.time_offset_s
    return points


def polyline_to_aabb_closest(
    trajectory: Iterable[TrajectoryPoint],
    obstacle: ObstacleFootprint,
    tolerance_m: float = 0.0,
) -> PolylineAabbClosest:
    points = validate_trajectory(trajectory)
    if len(points) == 1:
        point = points[0]
        return PolylineAabbClosest(
            point_to_aabb_distance(point.x, point.y, obstacle),
            point.time_offset_s,
            0,
            point.x,
            point.y,
        )

    best: PolylineAabbClosest | None = None
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        result = segment_to_aabb_distance(start.x, start.y, end.x, end.y, obstacle, tolerance_m)
        time = start.time_offset_s + result.u * (end.time_offset_s - start.time_offset_s)
        candidate = PolylineAabbClosest(result.distance_m, time, index, result.closest_x, result.closest_y)
        if best is None or candidate.distance_m < best.distance_m:
            best = candidate
    assert best is not None
    return best


def corridor_intervals_for_trajectory(
    trajectory: Iterable[TrajectoryPoint],
    obstacle: ObstacleFootprint,
    corridor_radius_m: float,
    tolerance_m: float = 0.0,
) -> list[tuple[float, float]]:
    points = validate_trajectory(trajectory)
    require_finite("corridor_radius_m", corridor_radius_m)
    require_finite("tolerance_m", tolerance_m)
    if corridor_radius_m < 0:
        raise ValueError("corridor_radius_m must be non-negative")
    if tolerance_m < 0:
        raise ValueError("tolerance_m must be non-negative")
    if len(points) == 1:
        point = points[0]
        if point_to_aabb_distance(point.x, point.y, obstacle) <= corridor_radius_m + tolerance_m:
            return [(point.time_offset_s, point.time_offset_s)]
        return []
    intervals: list[tuple[float, float]] = []
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        interval = segment_aabb_intersection_interval(
            start.x,
            start.y,
            end.x,
            end.y,
            obstacle,
            corridor_radius_m,
            tolerance_m,
        )
        if interval is None:
            continue
        enter_u, exit_u = interval
        start_time = start.time_offset_s + enter_u * (end.time_offset_s - start.time_offset_s)
        end_time = start.time_offset_s + exit_u * (end.time_offset_s - start.time_offset_s)
        intervals.append((start_time, end_time))
    return _merge_time_intervals(intervals, tolerance_m)


def _merge_time_intervals(intervals: Sequence[tuple[float, float]], tolerance_s: float) -> list[tuple[float, float]]:
    if not intervals:
        return []
    ordered = sorted((min(a, b), max(a, b)) for a, b in intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end + tolerance_s:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def summarize_corridor_intervals(intervals: Iterable[tuple[float, float]]) -> CorridorIntervalSummary:
    ordered = [(min(a, b), max(a, b)) for a, b in intervals]
    if not ordered:
        return CorridorIntervalSummary(None, 0.0)
    first_entry = min(start for start, _ in ordered)
    duration = sum(max(0.0, end - start) for start, end in ordered)
    return CorridorIntervalSummary(first_entry, duration)
