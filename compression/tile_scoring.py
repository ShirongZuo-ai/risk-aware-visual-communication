"""Deterministic, Webots-decoupled tile scoring for Milestone 5C."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from compression.tiled_jpeg import DEFAULT_M5_GRID, TileGrid


METHOD_UNIFORM = "uniform"
METHOD_CENTER = "center_roi"
METHOD_OBJECT = "object_roi"
METHOD_RISK = "risk_roi"
ELIGIBLE_VISIBILITY_STATUSES = frozenset(
    {"fully_visible", "partially_visible", "intersects_near_plane"}
)
CENTER_SIGMA_NORMALIZED = 0.5


@dataclass(frozen=True)
class TileScoreMap:
    """Immutable row-major scores for one allocation method."""

    method: str
    grid: TileGrid
    scores: tuple[float, ...]
    source_description: str

    def __post_init__(self) -> None:
        if not self.method:
            raise ValueError("method must be non-empty")
        if not self.source_description:
            raise ValueError("source_description must be non-empty")
        scores = tuple(self.scores)
        if len(scores) != self.grid.tile_count:
            raise ValueError("scores length must equal grid.tile_count")
        for index, score in enumerate(scores):
            if not math.isfinite(score):
                raise ValueError(f"scores[{index}] must be finite")
            if score < 0.0 or score > 1.0:
                raise ValueError(f"scores[{index}] must be in [0, 1]")
        object.__setattr__(self, "scores", scores)

    def score(self, tile_id: int) -> float:
        if not isinstance(tile_id, int) or tile_id < 0 or tile_id >= self.grid.tile_count:
            raise ValueError("tile_id is outside the grid")
        return self.scores[tile_id]

    @property
    def minimum_score(self) -> float:
        return min(self.scores)

    @property
    def maximum_score(self) -> float:
        return max(self.scores)

    @property
    def mean_score(self) -> float:
        return sum(self.scores) / len(self.scores)

    @property
    def nonzero_tile_count(self) -> int:
        return sum(score > 0.0 for score in self.scores)

    @property
    def stable_ranked_tile_ids(self) -> tuple[int, ...]:
        return tuple(sorted(range(self.grid.tile_count), key=lambda tile_id: (-self.scores[tile_id], tile_id)))


@dataclass(frozen=True)
class ProjectedPolygon:
    """Minimal M4D projection input used by Object ROI without adapter imports."""

    obstacle_id: str
    visibility_status: str
    clipped_polygon: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if not self.obstacle_id:
            raise ValueError("obstacle_id must be non-empty")
        if not self.visibility_status:
            raise ValueError("visibility_status must be non-empty")
        polygon = tuple((float(point[0]), float(point[1])) for point in self.clipped_polygon)
        for point in polygon:
            if not math.isfinite(point[0]) or not math.isfinite(point[1]):
                raise ValueError("clipped polygon values must be finite")
        object.__setattr__(self, "clipped_polygon", polygon)


@dataclass(frozen=True)
class FloatMask:
    """Validated row-major floating-point mask input for Risk ROI."""

    width_px: int
    height_px: int
    values: tuple[float, ...]
    layout: str = "row-major"

    def __post_init__(self) -> None:
        if not isinstance(self.width_px, int) or self.width_px <= 0:
            raise ValueError("width_px must be a positive integer")
        if not isinstance(self.height_px, int) or self.height_px <= 0:
            raise ValueError("height_px must be a positive integer")
        if self.layout != "row-major":
            raise ValueError("mask layout must be row-major")
        values = tuple(float(value) for value in self.values)
        if len(values) != self.width_px * self.height_px:
            raise ValueError("mask values length must equal width_px * height_px")
        for index, value in enumerate(values):
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"mask value {index} must be finite and in [0, 1]")
        object.__setattr__(self, "values", values)

    def value(self, u_px: int, v_px: int) -> float:
        return self.values[v_px * self.width_px + u_px]


def uniform_score_map(grid: TileGrid = DEFAULT_M5_GRID) -> TileScoreMap:
    """Return diagnostics only; Uniform matching never consumes these scores."""

    return TileScoreMap(METHOD_UNIFORM, grid, (0.0,) * grid.tile_count, "Uniform matcher does not use spatial scores")


def center_roi_scores(
    principal_point_px: tuple[float, float],
    grid: TileGrid = DEFAULT_M5_GRID,
    sigma_normalized: float = CENTER_SIGMA_NORMALIZED,
) -> TileScoreMap:
    """Score tile centers with the frozen normalized Gaussian Center ROI."""

    cx_px, cy_px = (float(principal_point_px[0]), float(principal_point_px[1]))
    if not math.isfinite(cx_px) or not math.isfinite(cy_px):
        raise ValueError("principal_point_px must be finite")
    if not math.isfinite(sigma_normalized) or sigma_normalized <= 0.0:
        raise ValueError("sigma_normalized must be a positive finite value")
    scores = []
    for _, _, _, (left, top, right, bottom) in grid.iter_tiles():
        tile_center_x = (left + right - 1) * 0.5
        tile_center_y = (top + bottom - 1) * 0.5
        dx = (tile_center_x - cx_px) / (grid.frame_width_px * 0.5)
        dy = (tile_center_y - cy_px) / (grid.frame_height_px * 0.5)
        scores.append(math.exp(-(dx * dx + dy * dy) / (2.0 * sigma_normalized * sigma_normalized)))
    return TileScoreMap(
        METHOD_CENTER,
        grid,
        tuple(scores),
        "Gaussian tile-center distance to frozen camera principal point",
    )


def object_roi_scores(
    obstacles: Iterable[ProjectedPolygon],
    grid: TileGrid = DEFAULT_M5_GRID,
) -> TileScoreMap:
    """Use max clipped-polygon coverage fraction over eligible visible obstacles."""

    scores = [0.0] * grid.tile_count
    seen_ids: set[str] = set()
    for obstacle in obstacles:
        if obstacle.obstacle_id in seen_ids:
            raise ValueError(f"duplicate obstacle_id: {obstacle.obstacle_id}")
        seen_ids.add(obstacle.obstacle_id)
        if obstacle.visibility_status not in ELIGIBLE_VISIBILITY_STATUSES:
            continue
        if len(obstacle.clipped_polygon) < 3:
            continue
        for tile_id, _, _, bounds in grid.iter_tiles():
            coverage = _polygon_rectangle_coverage(obstacle.clipped_polygon, bounds)
            scores[tile_id] = max(scores[tile_id], coverage)
    return TileScoreMap(
        METHOD_OBJECT,
        grid,
        tuple(scores),
        "Maximum clipped projected-obstacle polygon coverage fraction per tile",
    )


def risk_roi_scores(mask: FloatMask, grid: TileGrid = DEFAULT_M5_GRID) -> TileScoreMap:
    """Use the maximum combined floating-point image risk within each tile."""

    if (mask.width_px, mask.height_px) != (grid.frame_width_px, grid.frame_height_px):
        raise ValueError("mask dimensions must match the tile grid frame dimensions")
    scores = []
    for _, _, _, (left, top, right, bottom) in grid.iter_tiles():
        scores.append(max(mask.value(u_px, v_px) for v_px in range(top, bottom) for u_px in range(left, right)))
    return TileScoreMap(
        METHOD_RISK,
        grid,
        tuple(scores),
        "Maximum accepted combined floating-point image-risk value per tile",
    )


def _polygon_rectangle_coverage(
    polygon: Sequence[tuple[float, float]],
    bounds: tuple[int, int, int, int],
) -> float:
    left, top, right, bottom = bounds
    clipped = list(polygon)
    clipped = _clip_polygon(clipped, lambda point: point[0] >= left, lambda a, b: _vertical_intersection(a, b, left))
    clipped = _clip_polygon(clipped, lambda point: point[0] <= right, lambda a, b: _vertical_intersection(a, b, right))
    clipped = _clip_polygon(clipped, lambda point: point[1] >= top, lambda a, b: _horizontal_intersection(a, b, top))
    clipped = _clip_polygon(clipped, lambda point: point[1] <= bottom, lambda a, b: _horizontal_intersection(a, b, bottom))
    if len(clipped) < 3:
        return 0.0
    return min(1.0, _polygon_area(clipped) / ((right - left) * (bottom - top)))


def _clip_polygon(points, inside, intersection):
    if not points:
        return []
    output = []
    previous = points[-1]
    previous_inside = inside(previous)
    for current in points:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                output.append(intersection(previous, current))
            output.append(current)
        elif previous_inside:
            output.append(intersection(previous, current))
        previous, previous_inside = current, current_inside
    return output


def _vertical_intersection(a: tuple[float, float], b: tuple[float, float], x: float) -> tuple[float, float]:
    if b[0] == a[0]:
        return (x, a[1])
    ratio = (x - a[0]) / (b[0] - a[0])
    return (x, a[1] + ratio * (b[1] - a[1]))


def _horizontal_intersection(a: tuple[float, float], b: tuple[float, float], y: float) -> tuple[float, float]:
    if b[1] == a[1]:
        return (a[0], y)
    ratio = (y - a[1]) / (b[1] - a[1])
    return (a[0] + ratio * (b[0] - a[0]), y)


def _polygon_area(points: Sequence[tuple[float, float]]) -> float:
    return abs(
        sum(
            point[0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * point[1]
            for index, point in enumerate(points)
        )
    ) * 0.5
