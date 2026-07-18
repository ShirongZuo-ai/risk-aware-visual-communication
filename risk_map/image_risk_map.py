"""Pure-Python image-space risk masks for projected obstacles.

The mask core is deliberately decoupled from Webots and image libraries. Pixel
coordinates use integer pixel centers: pixel ``(u, v)`` is tested at exactly
``(u, v)``, not at ``(u + 0.5, v + 0.5)``. Only
``ProjectedObstacle.clipped_polygon`` is rasterized.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from perception.camera_models import ProjectedObstacle, ProjectedPoint, VisibilityStatus


RISK_EPSILON = 1e-9
"""Tolerance for risk consistency and combined-mask invariants."""

POLYGON_EPSILON = 1e-9
"""Tolerance for polygon boundary and image-bound checks."""

POLYGON_AREA_EPSILON_PX2 = 1e-6
"""Minimum polygon area required before rasterization."""


_ELIGIBLE_STATUSES = {
    VisibilityStatus.FULLY_VISIBLE,
    VisibilityStatus.PARTIALLY_VISIBLE,
    VisibilityStatus.INTERSECTS_NEAR_PLANE,
}


@dataclass(frozen=True)
class Mask2D:
    """Immutable row-major floating-point image mask."""

    width_px: int
    height_px: int
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.width_px, int) or self.width_px <= 0:
            raise ValueError("width_px must be a positive integer")
        if not isinstance(self.height_px, int) or self.height_px <= 0:
            raise ValueError("height_px must be a positive integer")
        values = tuple(self.values)
        if len(values) != self.width_px * self.height_px:
            raise ValueError("values length must equal width_px * height_px")
        for index, value in enumerate(values):
            if not math.isfinite(value):
                raise ValueError(f"values[{index}] must be finite")
            if value < 0.0 or value > 1.0:
                raise ValueError(f"values[{index}] must be in [0, 1]")
        object.__setattr__(self, "values", values)

    def get(self, u_px: int, v_px: int) -> float:
        """Return one mask value using integer pixel-center indices."""

        if not isinstance(u_px, int) or not isinstance(v_px, int):
            raise ValueError("u_px and v_px must be integers")
        if u_px < 0 or u_px >= self.width_px or v_px < 0 or v_px >= self.height_px:
            raise IndexError("pixel index is outside the mask")
        return self.values[v_px * self.width_px + u_px]

    def rows(self) -> tuple[tuple[float, ...], ...]:
        """Return immutable row tuples in top-to-bottom image order."""

        return tuple(
            self.values[row_start : row_start + self.width_px]
            for row_start in range(0, len(self.values), self.width_px)
        )

    @property
    def nonzero_pixel_count(self) -> int:
        return sum(1 for value in self.values if value > RISK_EPSILON)

    @property
    def maximum_value(self) -> float:
        return max(self.values)

    @property
    def mean_value(self) -> float:
        return sum(self.values) / len(self.values)


@dataclass(frozen=True)
class ProjectedObstacleRisk:
    """Risk scores bound to one projected obstacle."""

    obstacle_id: str
    projection: ProjectedObstacle
    planned_risk: float
    state_risk: float
    combined_risk: float

    def __post_init__(self) -> None:
        if not self.obstacle_id:
            raise ValueError("obstacle_id must be non-empty")
        if self.obstacle_id != self.projection.obstacle_id:
            raise ValueError("obstacle_id must match projection.obstacle_id")
        for name in ("planned_risk", "state_risk", "combined_risk"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        expected = max(self.planned_risk, self.state_risk)
        if abs(self.combined_risk - expected) > RISK_EPSILON:
            raise ValueError("combined_risk must equal max(planned_risk, state_risk)")


@dataclass(frozen=True)
class ObstacleMaskContribution:
    """Per-obstacle diagnostics for mask writing."""

    obstacle_id: str
    visibility_status: VisibilityStatus
    eligible_for_mask: bool
    skip_reason: str | None
    polygon_vertex_count: int
    candidate_pixel_count: int
    planned_written_pixel_count: int
    state_written_pixel_count: int
    combined_written_pixel_count: int
    planned_risk: float
    state_risk: float
    combined_risk: float

    def __post_init__(self) -> None:
        if self.eligible_for_mask and self.skip_reason is not None:
            raise ValueError("eligible contribution must not have a skip_reason")
        if not self.eligible_for_mask and not self.skip_reason:
            raise ValueError("skipped contribution must have a skip_reason")


@dataclass(frozen=True)
class ImageRiskMasks:
    """Planned, state, and combined image risk masks plus diagnostics."""

    planned: Mask2D
    state: Mask2D
    combined: Mask2D
    contributions: tuple[ObstacleMaskContribution, ...]

    def __post_init__(self) -> None:
        size = (self.planned.width_px, self.planned.height_px)
        if (self.state.width_px, self.state.height_px) != size:
            raise ValueError("state mask dimensions must match planned mask")
        if (self.combined.width_px, self.combined.height_px) != size:
            raise ValueError("combined mask dimensions must match planned mask")
        for index, (planned, state, combined) in enumerate(zip(self.planned.values, self.state.values, self.combined.values)):
            if abs(combined - max(planned, state)) > RISK_EPSILON:
                raise ValueError(f"combined mask value {index} must equal max(planned, state)")
        object.__setattr__(self, "contributions", tuple(self.contributions))


def bind_projection_to_risk(
    projection: ProjectedObstacle,
    planned_risk: float,
    state_risk: float,
    combined_risk: float,
) -> ProjectedObstacleRisk:
    """Bind already-computed risk scores to a projection without fuzzy lookup."""

    return ProjectedObstacleRisk(
        obstacle_id=projection.obstacle_id,
        projection=projection,
        planned_risk=planned_risk,
        state_risk=state_risk,
        combined_risk=combined_risk,
    )


def build_image_risk_masks(
    width_px: int,
    height_px: int,
    obstacles: Sequence[ProjectedObstacleRisk],
) -> ImageRiskMasks:
    """Rasterize projected-obstacle risks into image-space masks.

    Duplicate obstacle IDs are rejected. Contributions preserve input order, but
    mask values are order-invariant because overlaps use a pixelwise maximum.
    """

    _validate_dimensions(width_px, height_px)
    seen_ids: set[str] = set()
    planned_values = [0.0] * (width_px * height_px)
    state_values = [0.0] * (width_px * height_px)
    combined_values = [0.0] * (width_px * height_px)
    contributions: list[ObstacleMaskContribution] = []

    for obstacle in obstacles:
        if obstacle.obstacle_id in seen_ids:
            raise ValueError(f"duplicate obstacle_id: {obstacle.obstacle_id}")
        seen_ids.add(obstacle.obstacle_id)

        pixels, skip_reason = _eligible_pixels(obstacle.projection, width_px, height_px)
        if skip_reason is not None:
            contributions.append(
                ObstacleMaskContribution(
                    obstacle_id=obstacle.obstacle_id,
                    visibility_status=obstacle.projection.visibility_status,
                    eligible_for_mask=False,
                    skip_reason=skip_reason,
                    polygon_vertex_count=len(obstacle.projection.clipped_polygon),
                    candidate_pixel_count=0,
                    planned_written_pixel_count=0,
                    state_written_pixel_count=0,
                    combined_written_pixel_count=0,
                    planned_risk=obstacle.planned_risk,
                    state_risk=obstacle.state_risk,
                    combined_risk=obstacle.combined_risk,
                )
            )
            continue

        planned_written = _raise_pixels(planned_values, width_px, pixels, obstacle.planned_risk)
        state_written = _raise_pixels(state_values, width_px, pixels, obstacle.state_risk)
        combined_written = _raise_pixels(combined_values, width_px, pixels, obstacle.combined_risk)
        contributions.append(
            ObstacleMaskContribution(
                obstacle_id=obstacle.obstacle_id,
                visibility_status=obstacle.projection.visibility_status,
                eligible_for_mask=True,
                skip_reason=None,
                polygon_vertex_count=len(_clean_polygon(obstacle.projection.clipped_polygon)),
                candidate_pixel_count=len(pixels),
                planned_written_pixel_count=planned_written,
                state_written_pixel_count=state_written,
                combined_written_pixel_count=combined_written,
                planned_risk=obstacle.planned_risk,
                state_risk=obstacle.state_risk,
                combined_risk=obstacle.combined_risk,
            )
        )

    return ImageRiskMasks(
        planned=Mask2D(width_px, height_px, tuple(planned_values)),
        state=Mask2D(width_px, height_px, tuple(state_values)),
        combined=Mask2D(width_px, height_px, tuple(combined_values)),
        contributions=tuple(contributions),
    )


def _validate_dimensions(width_px: int, height_px: int) -> None:
    if not isinstance(width_px, int) or width_px <= 0:
        raise ValueError("width_px must be a positive integer")
    if not isinstance(height_px, int) or height_px <= 0:
        raise ValueError("height_px must be a positive integer")


def _eligible_pixels(
    projection: ProjectedObstacle,
    width_px: int,
    height_px: int,
) -> tuple[tuple[tuple[int, int], ...], str | None]:
    if projection.visibility_status not in _ELIGIBLE_STATUSES:
        return (), projection.visibility_status.value
    polygon = _clean_polygon(projection.clipped_polygon)
    if not polygon:
        return (), "invalid_polygon"
    if len(polygon) < 3:
        return (), "empty_clipped_polygon"
    if not _polygon_within_image(polygon, width_px, height_px):
        return (), "invalid_polygon"
    if _polygon_area(polygon) <= POLYGON_AREA_EPSILON_PX2:
        return (), "degenerate_projection"
    pixels = _rasterize_polygon(polygon, width_px, height_px)
    if not pixels:
        return (), "empty_clipped_polygon"
    return pixels, None


def _clean_polygon(points: Iterable[ProjectedPoint]) -> tuple[tuple[float, float], ...]:
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if not math.isfinite(point.u_px) or not math.isfinite(point.v_px):
            return ()
        candidate = (point.u_px, point.v_px)
        if not cleaned or not _same_point(cleaned[-1], candidate):
            cleaned.append(candidate)
    if len(cleaned) > 1 and _same_point(cleaned[0], cleaned[-1]):
        cleaned.pop()
    return tuple(cleaned)


def _same_point(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return abs(left[0] - right[0]) <= POLYGON_EPSILON and abs(left[1] - right[1]) <= POLYGON_EPSILON


def _polygon_within_image(polygon: Sequence[tuple[float, float]], width_px: int, height_px: int) -> bool:
    return all(
        -POLYGON_EPSILON <= u <= width_px - 1 + POLYGON_EPSILON
        and -POLYGON_EPSILON <= v <= height_px - 1 + POLYGON_EPSILON
        for u, v in polygon
    )


def _polygon_area(polygon: Sequence[tuple[float, float]]) -> float:
    if len(polygon) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(polygon):
        nxt = polygon[(index + 1) % len(polygon)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(total) * 0.5


def _rasterize_polygon(
    polygon: Sequence[tuple[float, float]],
    width_px: int,
    height_px: int,
) -> tuple[tuple[int, int], ...]:
    min_u = max(0, math.ceil(min(point[0] for point in polygon) - POLYGON_EPSILON))
    max_u = min(width_px - 1, math.floor(max(point[0] for point in polygon) + POLYGON_EPSILON))
    min_v = max(0, math.ceil(min(point[1] for point in polygon) - POLYGON_EPSILON))
    max_v = min(height_px - 1, math.floor(max(point[1] for point in polygon) + POLYGON_EPSILON))
    pixels: list[tuple[int, int]] = []
    for v_px in range(min_v, max_v + 1):
        for u_px in range(min_u, max_u + 1):
            if _point_in_polygon_or_boundary(float(u_px), float(v_px), polygon):
                pixels.append((u_px, v_px))
    return tuple(pixels)


def _point_in_polygon_or_boundary(x: float, y: float, polygon: Sequence[tuple[float, float]]) -> bool:
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        if _point_on_segment(x, y, start, end):
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


def _point_on_segment(
    x: float,
    y: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    x0, y0 = start
    x1, y1 = end
    cross = (x - x0) * (y1 - y0) - (y - y0) * (x1 - x0)
    if abs(cross) > POLYGON_EPSILON:
        return False
    return (
        min(x0, x1) - POLYGON_EPSILON <= x <= max(x0, x1) + POLYGON_EPSILON
        and min(y0, y1) - POLYGON_EPSILON <= y <= max(y0, y1) + POLYGON_EPSILON
    )


def _raise_pixels(
    values: list[float],
    width_px: int,
    pixels: Iterable[tuple[int, int]],
    risk: float,
) -> int:
    written = 0
    for u_px, v_px in pixels:
        index = v_px * width_px + u_px
        if risk > values[index] + RISK_EPSILON:
            values[index] = risk
            written += 1
    return written
