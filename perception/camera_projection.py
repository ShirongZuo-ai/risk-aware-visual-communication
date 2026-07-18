"""Pure-Python camera projection geometry for Milestone 4B."""

from __future__ import annotations

import math
from typing import Iterable

from perception.camera_models import (
    BOX_EDGE_INDICES,
    CameraExtrinsics,
    CameraIntrinsics,
    Matrix3,
    ObstacleBox3D,
    ProjectedObstacle,
    ProjectedPoint,
    Vec2,
    Vec3,
    VisibilityStatus,
)


GEOMETRY_EPSILON = 1e-9
"""Small absolute geometry tolerance for point uniqueness and clipping."""

AREA_EPSILON_PX2 = 1e-6
"""Small pixel-area tolerance below which a polygon is considered degenerate."""


def require_finite_vec3(name: str, point: Vec3) -> None:
    """Raise ``ValueError`` unless ``point`` is a finite 3-vector."""

    if len(point) != 3:
        raise ValueError(f"{name} must have exactly 3 values")
    for index, value in enumerate(point):
        if not math.isfinite(value):
            raise ValueError(f"{name}[{index}] must be finite")


def require_finite_vec2(name: str, point: Vec2) -> None:
    """Raise ``ValueError`` unless ``point`` is a finite 2-vector."""

    if len(point) != 2:
        raise ValueError(f"{name} must have exactly 2 values")
    for index, value in enumerate(point):
        if not math.isfinite(value):
            raise ValueError(f"{name}[{index}] must be finite")


def mat_vec_mul(matrix: Matrix3, vector: Vec3) -> Vec3:
    """Multiply a 3x3 matrix by a 3-vector."""

    require_finite_vec3("vector", vector)
    return tuple(sum(matrix[row][column] * vector[column] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def mat_mat_mul(left: Matrix3, right: Matrix3) -> Matrix3:
    """Multiply two 3x3 matrices."""

    return tuple(
        tuple(sum(left[row][k] * right[k][column] for k in range(3)) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def vec_add(left: Vec3, right: Vec3) -> Vec3:
    """Add two 3-vectors."""

    require_finite_vec3("left", left)
    require_finite_vec3("right", right)
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def vec_sub(left: Vec3, right: Vec3) -> Vec3:
    """Subtract two 3-vectors."""

    require_finite_vec3("left", left)
    require_finite_vec3("right", right)
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def dot(left: Vec3, right: Vec3) -> float:
    """Return the dot product of two 3-vectors."""

    require_finite_vec3("left", left)
    require_finite_vec3("right", right)
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def determinant3(matrix: Matrix3) -> float:
    """Return a 3x3 determinant."""

    (a, b, c), (d, e, f), (g, h, i) = matrix
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def transpose(matrix: Matrix3) -> Matrix3:
    """Return the transpose of a 3x3 matrix."""

    return tuple(tuple(matrix[column][row] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def world_to_camera_device_point(point_world: Vec3, extrinsics: CameraExtrinsics) -> Vec3:
    """Transform one world point to Webots camera-device coordinates."""

    return vec_add(mat_vec_mul(extrinsics.world_to_camera_rotation, point_world), extrinsics.world_to_camera_translation)


def camera_device_to_optical_point(point_device: Vec3, extrinsics: CameraExtrinsics) -> Vec3:
    """Transform one camera-device point to the project optical frame."""

    return mat_vec_mul(extrinsics.device_to_optical_rotation, point_device)


def world_to_optical_point(point_world: Vec3, extrinsics: CameraExtrinsics) -> Vec3:
    """Transform one world point to the project optical frame."""

    return camera_device_to_optical_point(world_to_camera_device_point(point_world, extrinsics), extrinsics)


def camera_device_to_world_point(point_device: Vec3, extrinsics: CameraExtrinsics) -> Vec3:
    """Transform one camera-device point back to world coordinates."""

    rotation_inv = transpose(extrinsics.world_to_camera_rotation)
    translated = vec_sub(point_device, extrinsics.world_to_camera_translation)
    return mat_vec_mul(rotation_inv, translated)


def project_optical_point(point_optical: Vec3, intrinsics: CameraIntrinsics) -> ProjectedPoint | None:
    """Project one optical-frame point using the frozen pinhole model.

    Returns ``None`` when the optical depth is smaller than the near clipping
    distance. This avoids infinite coordinates for points behind or too close
    to the camera.
    """

    require_finite_vec3("point_optical", point_optical)
    x, y, z = point_optical
    if z < intrinsics.near_clip_m:
        return None
    u = intrinsics.fx_px * x / z + intrinsics.cx_px
    v = intrinsics.fy_px * y / z + intrinsics.cy_px
    return ProjectedPoint.from_image_coordinates(u, v, z, intrinsics)


def _unique_vec3(points: Iterable[Vec3], epsilon: float = GEOMETRY_EPSILON) -> tuple[Vec3, ...]:
    unique: list[Vec3] = []
    for point in points:
        require_finite_vec3("point", point)
        if not any(
            abs(point[0] - other[0]) <= epsilon and abs(point[1] - other[1]) <= epsilon and abs(point[2] - other[2]) <= epsilon
            for other in unique
        ):
            unique.append(point)
    return tuple(unique)


def _unique_projected(points: Iterable[ProjectedPoint], epsilon: float = GEOMETRY_EPSILON) -> tuple[ProjectedPoint, ...]:
    unique: list[ProjectedPoint] = []
    for point in points:
        if not any(abs(point.u_px - other.u_px) <= epsilon and abs(point.v_px - other.v_px) <= epsilon for other in unique):
            unique.append(point)
    return tuple(unique)


def clip_box_points_to_near_plane(points_optical: tuple[Vec3, ...], near_clip_m: float) -> tuple[tuple[Vec3, ...], bool]:
    """Clip Box corner/edge geometry against the optical near plane."""

    if near_clip_m <= 0 or not math.isfinite(near_clip_m):
        raise ValueError("near_clip_m must be positive and finite")
    kept: list[Vec3] = [point for point in points_optical if point[2] >= near_clip_m - GEOMETRY_EPSILON]
    intersects = any(point[2] < near_clip_m - GEOMETRY_EPSILON for point in points_optical) and any(
        point[2] >= near_clip_m - GEOMETRY_EPSILON for point in points_optical
    )
    for start_index, end_index in BOX_EDGE_INDICES:
        p0 = points_optical[start_index]
        p1 = points_optical[end_index]
        z0 = p0[2]
        z1 = p1[2]
        if abs(z1 - z0) <= GEOMETRY_EPSILON:
            continue
        crosses = (z0 < near_clip_m <= z1) or (z1 < near_clip_m <= z0)
        if not crosses:
            continue
        t = (near_clip_m - z0) / (z1 - z0)
        if -GEOMETRY_EPSILON <= t <= 1.0 + GEOMETRY_EPSILON:
            t = min(1.0, max(0.0, t))
            kept.append(
                (
                    p0[0] + t * (p1[0] - p0[0]),
                    p0[1] + t * (p1[1] - p0[1]),
                    near_clip_m,
                )
            )
    return _unique_vec3(kept), intersects


def convex_hull(points: Iterable[Vec2], epsilon: float = GEOMETRY_EPSILON) -> tuple[Vec2, ...]:
    """Return a deterministic 2D convex hull using the monotonic chain method."""

    unique: list[Vec2] = []
    for point in points:
        require_finite_vec2("point", point)
        if not any(abs(point[0] - other[0]) <= epsilon and abs(point[1] - other[1]) <= epsilon for other in unique):
            unique.append(point)
    ordered = sorted(unique)
    if len(ordered) <= 1:
        return tuple(ordered)

    def cross(origin: Vec2, left: Vec2, right: Vec2) -> float:
        return (left[0] - origin[0]) * (right[1] - origin[1]) - (left[1] - origin[1]) * (right[0] - origin[0])

    lower: list[Vec2] = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= epsilon:
            lower.pop()
        lower.append(point)
    upper: list[Vec2] = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= epsilon:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1] + upper[:-1])


def polygon_area(points: Iterable[Vec2 | ProjectedPoint]) -> float:
    """Return non-negative polygon area using the shoelace formula."""

    normalized = [_as_vec2(point) for point in points]
    if len(normalized) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(normalized):
        nxt = normalized[(index + 1) % len(normalized)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(total) * 0.5


def polygon_bounding_box(points: Iterable[ProjectedPoint]) -> tuple[float, float, float, float] | None:
    """Return ``(min_u, min_v, max_u, max_v)`` for a projected polygon."""

    values = tuple(points)
    if not values:
        return None
    return (
        min(point.u_px for point in values),
        min(point.v_px for point in values),
        max(point.u_px for point in values),
        max(point.v_px for point in values),
    )


def _as_vec2(point: Vec2 | ProjectedPoint) -> Vec2:
    if isinstance(point, ProjectedPoint):
        return (point.u_px, point.v_px)
    return point


def _projected_hull(points: tuple[ProjectedPoint, ...], intrinsics: CameraIntrinsics) -> tuple[ProjectedPoint, ...]:
    by_xy: dict[tuple[int, int], ProjectedPoint] = {}
    scale = 1.0 / GEOMETRY_EPSILON
    for point in points:
        key = (round(point.u_px * scale), round(point.v_px * scale))
        existing = by_xy.get(key)
        if existing is None or point.depth_m < existing.depth_m:
            by_xy[key] = point
    hull_xy = convex_hull((point.u_px, point.v_px) for point in by_xy.values())
    result: list[ProjectedPoint] = []
    for x, y in hull_xy:
        selected = min(by_xy.values(), key=lambda point: (point.u_px - x) ** 2 + (point.v_px - y) ** 2)
        result.append(ProjectedPoint.from_image_coordinates(x, y, selected.depth_m, intrinsics))
    return tuple(result)


def clip_polygon_to_image(polygon: Iterable[ProjectedPoint], intrinsics: CameraIntrinsics) -> tuple[ProjectedPoint, ...]:
    """Clip a convex polygon to the image rectangle using Sutherland-Hodgman."""

    points = tuple(polygon)
    bounds = (
        (lambda point: point.u_px >= -GEOMETRY_EPSILON, lambda a, b: _intersect_at_u(a, b, 0.0, intrinsics)),
        (lambda point: point.u_px <= intrinsics.width_px - 1 + GEOMETRY_EPSILON, lambda a, b: _intersect_at_u(a, b, intrinsics.width_px - 1, intrinsics)),
        (lambda point: point.v_px >= -GEOMETRY_EPSILON, lambda a, b: _intersect_at_v(a, b, 0.0, intrinsics)),
        (lambda point: point.v_px <= intrinsics.height_px - 1 + GEOMETRY_EPSILON, lambda a, b: _intersect_at_v(a, b, intrinsics.height_px - 1, intrinsics)),
    )
    for inside, intersect in bounds:
        if not points:
            return ()
        output: list[ProjectedPoint] = []
        previous = points[-1]
        previous_inside = inside(previous)
        for current in points:
            current_inside = inside(current)
            if current_inside:
                if not previous_inside:
                    output.append(intersect(previous, current))
                output.append(_clamp_to_image(current, intrinsics))
            elif previous_inside:
                output.append(intersect(previous, current))
            previous = current
            previous_inside = current_inside
        points = _unique_projected(output)
    return tuple(_clamp_to_image(point, intrinsics) for point in _unique_projected(points))


def _intersect_at_u(start: ProjectedPoint, end: ProjectedPoint, u: float, intrinsics: CameraIntrinsics) -> ProjectedPoint:
    du = end.u_px - start.u_px
    if abs(du) <= GEOMETRY_EPSILON:
        t = 0.0
    else:
        t = (u - start.u_px) / du
    return _interpolate_projected(start, end, t, intrinsics, u_override=u)


def _intersect_at_v(start: ProjectedPoint, end: ProjectedPoint, v: float, intrinsics: CameraIntrinsics) -> ProjectedPoint:
    dv = end.v_px - start.v_px
    if abs(dv) <= GEOMETRY_EPSILON:
        t = 0.0
    else:
        t = (v - start.v_px) / dv
    return _interpolate_projected(start, end, t, intrinsics, v_override=v)


def _interpolate_projected(
    start: ProjectedPoint,
    end: ProjectedPoint,
    t: float,
    intrinsics: CameraIntrinsics,
    u_override: float | None = None,
    v_override: float | None = None,
) -> ProjectedPoint:
    t = min(1.0, max(0.0, t))
    u = start.u_px + t * (end.u_px - start.u_px) if u_override is None else u_override
    v = start.v_px + t * (end.v_px - start.v_px) if v_override is None else v_override
    depth = start.depth_m + t * (end.depth_m - start.depth_m)
    return ProjectedPoint.from_image_coordinates(u, v, max(depth, intrinsics.near_clip_m), intrinsics)


def _clamp_to_image(point: ProjectedPoint, intrinsics: CameraIntrinsics) -> ProjectedPoint:
    u = min(intrinsics.width_px - 1, max(0.0, point.u_px))
    v = min(intrinsics.height_px - 1, max(0.0, point.v_px))
    return ProjectedPoint.from_image_coordinates(u, v, point.depth_m, intrinsics)


def project_obstacle_box(
    obstacle: ObstacleBox3D,
    intrinsics: CameraIntrinsics,
    extrinsics: CameraExtrinsics,
) -> ProjectedObstacle:
    """Project one world-axis-aligned 3D Box into the camera image."""

    optical_corners = tuple(world_to_optical_point(corner, extrinsics) for corner in obstacle.corners_world)
    if all(point[2] <= 0.0 for point in optical_corners):
        return _empty_obstacle(obstacle.obstacle_id, VisibilityStatus.BEHIND_CAMERA)

    clipped_optical, intersects_near_plane = clip_box_points_to_near_plane(optical_corners, intrinsics.near_clip_m)
    if not clipped_optical:
        return _empty_obstacle(obstacle.obstacle_id, VisibilityStatus.OUTSIDE_FRUSTUM)

    projected = tuple(point for point in (project_optical_point(point, intrinsics) for point in clipped_optical) if point is not None)
    projected = _projected_hull(projected, intrinsics)
    full_area = polygon_area(projected)
    min_depth = min(point[2] for point in clipped_optical)
    max_depth = max(point[2] for point in clipped_optical)
    if len(projected) < 3 or full_area <= AREA_EPSILON_PX2:
        return ProjectedObstacle(
            obstacle_id=obstacle.obstacle_id,
            visibility_status=VisibilityStatus.DEGENERATE_PROJECTION,
            projected_polygon=projected,
            clipped_polygon=(),
            bounding_box=None,
            minimum_depth_m=min_depth,
            maximum_depth_m=max_depth,
            projected_area_px=0.0,
            truncation_fraction=0.0,
        )

    projected_bbox = polygon_bounding_box(projected)
    if projected_bbox is not None and _bbox_outside_image(projected_bbox, intrinsics):
        return ProjectedObstacle(
            obstacle_id=obstacle.obstacle_id,
            visibility_status=VisibilityStatus.OUTSIDE_FRUSTUM,
            projected_polygon=projected,
            clipped_polygon=(),
            bounding_box=None,
            minimum_depth_m=min_depth,
            maximum_depth_m=max_depth,
            projected_area_px=0.0,
            truncation_fraction=1.0,
        )

    clipped = clip_polygon_to_image(projected, intrinsics)
    if not clipped:
        return ProjectedObstacle(
            obstacle_id=obstacle.obstacle_id,
            visibility_status=VisibilityStatus.OUTSIDE_FRUSTUM,
            projected_polygon=projected,
            clipped_polygon=(),
            bounding_box=None,
            minimum_depth_m=min_depth,
            maximum_depth_m=max_depth,
            projected_area_px=0.0,
            truncation_fraction=1.0,
        )
    clipped_area = polygon_area(clipped)
    if clipped_area <= AREA_EPSILON_PX2:
        status = VisibilityStatus.DEGENERATE_PROJECTION
    else:
        truncation = min(1.0, max(0.0, 1.0 - clipped_area / full_area))
        if intersects_near_plane:
            status = VisibilityStatus.INTERSECTS_NEAR_PLANE
        elif truncation > GEOMETRY_EPSILON:
            status = VisibilityStatus.PARTIALLY_VISIBLE
        else:
            status = VisibilityStatus.FULLY_VISIBLE
        return ProjectedObstacle(
            obstacle_id=obstacle.obstacle_id,
            visibility_status=status,
            projected_polygon=projected,
            clipped_polygon=clipped,
            bounding_box=polygon_bounding_box(clipped),
            minimum_depth_m=min_depth,
            maximum_depth_m=max_depth,
            projected_area_px=clipped_area,
            truncation_fraction=truncation,
        )

    return ProjectedObstacle(
        obstacle_id=obstacle.obstacle_id,
        visibility_status=status,
        projected_polygon=projected,
        clipped_polygon=clipped,
        bounding_box=polygon_bounding_box(clipped),
        minimum_depth_m=min_depth,
        maximum_depth_m=max_depth,
        projected_area_px=0.0,
        truncation_fraction=1.0,
    )


def _empty_obstacle(obstacle_id: str, status: VisibilityStatus) -> ProjectedObstacle:
    return ProjectedObstacle(
        obstacle_id=obstacle_id,
        visibility_status=status,
        projected_polygon=(),
        clipped_polygon=(),
        bounding_box=None,
        minimum_depth_m=None,
        maximum_depth_m=None,
        projected_area_px=0.0,
        truncation_fraction=1.0,
    )


def _bbox_outside_image(bounding_box: tuple[float, float, float, float], intrinsics: CameraIntrinsics) -> bool:
    min_u, min_v, max_u, max_v = bounding_box
    return max_u < 0.0 or min_u > intrinsics.width_px - 1 or max_v < 0.0 or min_v > intrinsics.height_px - 1


def polygons_bounding_boxes_overlap(left: ProjectedObstacle, right: ProjectedObstacle) -> bool:
    """Return whether two projected-obstacle bounding boxes overlap."""

    if left.bounding_box is None or right.bounding_box is None:
        return False
    l_min_u, l_min_v, l_max_u, l_max_v = left.bounding_box
    r_min_u, r_min_v, r_max_u, r_max_v = right.bounding_box
    return not (l_max_u < r_min_u or r_max_u < l_min_u or l_max_v < r_min_v or r_max_v < l_min_v)


def rotation_x(angle_rad: float) -> Matrix3:
    """Return a right-handed rotation matrix around x."""

    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def rotation_y(angle_rad: float) -> Matrix3:
    """Return a right-handed rotation matrix around y."""

    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def rotation_z(angle_rad: float) -> Matrix3:
    """Return a right-handed rotation matrix around z."""

    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
