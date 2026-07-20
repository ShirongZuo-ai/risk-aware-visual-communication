"""M4D-consistent region masks for M5D fixed-frame evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from compression.tile_scoring import ELIGIBLE_VISIBILITY_STATUSES, FloatMask, ProjectedPolygon


HIGH_RISK_THRESHOLD = 0.20
POLYGON_EPSILON = 1e-9


@dataclass(frozen=True)
class RegionMask:
    width_px: int
    height_px: int
    values: tuple[bool, ...]

    def __post_init__(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError("mask dimensions must be positive")
        values = tuple(bool(value) for value in self.values)
        if len(values) != self.width_px * self.height_px:
            raise ValueError("region mask length must match dimensions")
        object.__setattr__(self, "values", values)

    @property
    def pixel_count(self) -> int:
        return sum(self.values)

    @property
    def fraction(self) -> float:
        return self.pixel_count / len(self.values)


@dataclass(frozen=True)
class EvaluationRegions:
    eligible_object_union: RegionMask
    risk_support: RegionMask
    high_risk: RegionMask
    background: RegionMask


def build_evaluation_regions(
    combined_mask: FloatMask,
    polygons: Iterable[ProjectedPolygon],
    high_risk_threshold: float = HIGH_RISK_THRESHOLD,
) -> EvaluationRegions:
    if not math.isfinite(high_risk_threshold) or not 0.0 <= high_risk_threshold <= 1.0:
        raise ValueError("high_risk_threshold must be in [0, 1]")
    width, height = combined_mask.width_px, combined_mask.height_px
    object_values = [False] * (width * height)
    seen_ids: set[str] = set()
    for obstacle in polygons:
        if obstacle.obstacle_id in seen_ids:
            raise ValueError(f"duplicate obstacle_id: {obstacle.obstacle_id}")
        seen_ids.add(obstacle.obstacle_id)
        if obstacle.visibility_status not in ELIGIBLE_VISIBILITY_STATUSES:
            continue
        for u_px, v_px in _rasterize_polygon(obstacle.clipped_polygon, width, height):
            object_values[v_px * width + u_px] = True
    risk_support = tuple(value > 0.0 for value in combined_mask.values)
    high_risk = tuple(value >= high_risk_threshold for value in combined_mask.values)
    object_mask = RegionMask(width, height, tuple(object_values))
    return EvaluationRegions(
        eligible_object_union=object_mask,
        risk_support=RegionMask(width, height, risk_support),
        high_risk=RegionMask(width, height, high_risk),
        background=RegionMask(width, height, tuple(not value for value in object_values)),
    )


def _rasterize_polygon(
    polygon: Sequence[tuple[float, float]], width_px: int, height_px: int
) -> tuple[tuple[int, int], ...]:
    if len(polygon) < 3:
        return ()
    if any(not math.isfinite(u) or not math.isfinite(v) for u, v in polygon):
        raise ValueError("polygon coordinates must be finite")
    min_u = max(0, math.ceil(min(u for u, _ in polygon) - POLYGON_EPSILON))
    max_u = min(width_px - 1, math.floor(max(u for u, _ in polygon) + POLYGON_EPSILON))
    min_v = max(0, math.ceil(min(v for _, v in polygon) - POLYGON_EPSILON))
    max_v = min(height_px - 1, math.floor(max(v for _, v in polygon) + POLYGON_EPSILON))
    pixels = []
    for v_px in range(min_v, max_v + 1):
        for u_px in range(min_u, max_u + 1):
            if _point_in_polygon_or_boundary(float(u_px), float(v_px), polygon):
                pixels.append((u_px, v_px))
    return tuple(pixels)


def _point_in_polygon_or_boundary(x: float, y: float, polygon: Sequence[tuple[float, float]]) -> bool:
    for index, start in enumerate(polygon):
        if _point_on_segment(x, y, start, polygon[(index + 1) % len(polygon)]):
            return True
    inside = False
    previous = polygon[-1]
    for current in polygon:
        xi, yi = current
        xj, yj = previous
        if (yi > y) != (yj > y):
            x_intersect = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x <= x_intersect + POLYGON_EPSILON:
                inside = not inside
        previous = current
    return inside


def _point_on_segment(x: float, y: float, start: tuple[float, float], end: tuple[float, float]) -> bool:
    x0, y0 = start
    x1, y1 = end
    cross = (x - x0) * (y1 - y0) - (y - y0) * (x1 - x0)
    if abs(cross) > POLYGON_EPSILON:
        return False
    return min(x0, x1) - POLYGON_EPSILON <= x <= max(x0, x1) + POLYGON_EPSILON and min(y0, y1) - POLYGON_EPSILON <= y <= max(y0, y1) + POLYGON_EPSILON
