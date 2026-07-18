"""Pure-Python camera projection data models.

These models are intentionally independent of Webots, image libraries, and
array libraries. They define the frozen Milestone 4B interface used by the
projection core.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
BoundingBox = tuple[float, float, float, float]

BOX_EDGE_INDICES: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 3),
    (3, 2),
    (2, 0),
    (4, 5),
    (5, 7),
    (7, 6),
    (6, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)
"""The 12 edges of an :class:`ObstacleBox3D`, expressed as corner indices."""


class VisibilityStatus(str, Enum):
    """Single visibility classification for a projected obstacle."""

    FULLY_VISIBLE = "fully_visible"
    PARTIALLY_VISIBLE = "partially_visible"
    OUTSIDE_FRUSTUM = "outside_frustum"
    BEHIND_CAMERA = "behind_camera"
    INTERSECTS_NEAR_PLANE = "intersects_near_plane"
    DEGENERATE_PROJECTION = "degenerate_projection"


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_vec3(name: str, value: Vec3) -> None:
    if len(value) != 3:
        raise ValueError(f"{name} must have exactly 3 values")
    for index, component in enumerate(value):
        _require_finite(f"{name}[{index}]", component)


def _require_matrix3(name: str, value: Matrix3) -> None:
    if len(value) != 3:
        raise ValueError(f"{name} must have exactly 3 rows")
    for row_index, row in enumerate(value):
        if len(row) != 3:
            raise ValueError(f"{name}[{row_index}] must have exactly 3 columns")
        for column_index, component in enumerate(row):
            _require_finite(f"{name}[{row_index}][{column_index}]", component)


def _determinant3(matrix: Matrix3) -> float:
    (a, b, c), (d, e, f), (g, h, i) = matrix
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _dot(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _validate_rotation(name: str, matrix: Matrix3, tolerance: float = 1e-7) -> None:
    _require_matrix3(name, matrix)
    rows = matrix
    for index, row in enumerate(rows):
        norm_sq = _dot(row, row)
        if abs(norm_sq - 1.0) > tolerance:
            raise ValueError(f"{name} row {index} must have unit length")
    for first in range(3):
        for second in range(first + 1, 3):
            if abs(_dot(rows[first], rows[second])) > tolerance:
                raise ValueError(f"{name} rows must be orthogonal")
    determinant = _determinant3(matrix)
    if abs(determinant - 1.0) > tolerance:
        raise ValueError(f"{name} determinant must be approximately +1")


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole camera intrinsics using pixel-center coordinates."""

    width_px: int
    height_px: int
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    near_clip_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.width_px, int) or self.width_px <= 0:
            raise ValueError("width_px must be a positive integer")
        if not isinstance(self.height_px, int) or self.height_px <= 0:
            raise ValueError("height_px must be a positive integer")
        for name in ("fx_px", "fy_px", "cx_px", "cy_px", "near_clip_m"):
            _require_finite(name, getattr(self, name))
        if self.fx_px <= 0:
            raise ValueError("fx_px must be positive")
        if self.fy_px <= 0:
            raise ValueError("fy_px must be positive")
        if self.near_clip_m <= 0:
            raise ValueError("near_clip_m must be positive")

    @property
    def vertical_fov_rad(self) -> float:
        """Return the vertical field of view implied by ``fy_px`` and height."""

        return 2.0 * math.atan(self.height_px / (2.0 * self.fy_px))

    @classmethod
    def from_horizontal_fov(
        cls,
        width_px: int,
        height_px: int,
        horizontal_fov_rad: float,
        near_clip_m: float,
    ) -> "CameraIntrinsics":
        """Create square-pixel intrinsics from a horizontal field of view."""

        if not isinstance(width_px, int) or width_px <= 0:
            raise ValueError("width_px must be a positive integer")
        if not isinstance(height_px, int) or height_px <= 0:
            raise ValueError("height_px must be a positive integer")
        _require_finite("horizontal_fov_rad", horizontal_fov_rad)
        if horizontal_fov_rad <= 0 or horizontal_fov_rad >= math.pi:
            raise ValueError("horizontal_fov_rad must be in (0, pi)")
        fx = width_px / (2.0 * math.tan(horizontal_fov_rad / 2.0))
        return cls(
            width_px=width_px,
            height_px=height_px,
            fx_px=fx,
            fy_px=fx,
            cx_px=(width_px - 1) / 2.0,
            cy_px=(height_px - 1) / 2.0,
            near_clip_m=near_clip_m,
        )


@dataclass(frozen=True)
class CameraExtrinsics:
    """World-to-camera-device and camera-device-to-optical transforms.

    ``world_to_camera_translation`` is not the camera world position. If the
    camera center in world coordinates is ``C_world``, then:

    ``world_to_camera_translation = -(world_to_camera_rotation @ C_world)``.
    """

    world_to_camera_rotation: Matrix3
    world_to_camera_translation: Vec3
    device_to_optical_rotation: Matrix3

    def __post_init__(self) -> None:
        _validate_rotation("world_to_camera_rotation", self.world_to_camera_rotation)
        _require_vec3("world_to_camera_translation", self.world_to_camera_translation)
        _validate_rotation("device_to_optical_rotation", self.device_to_optical_rotation)

    @classmethod
    def identity(cls, device_to_optical_rotation: Matrix3) -> "CameraExtrinsics":
        """Return identity world-to-device extrinsics with explicit optical axes."""

        return cls(
            world_to_camera_rotation=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            world_to_camera_translation=(0.0, 0.0, 0.0),
            device_to_optical_rotation=device_to_optical_rotation,
        )

    @classmethod
    def from_camera_pose_in_world(
        cls,
        camera_to_world_rotation: Matrix3,
        camera_center_world: Vec3,
        device_to_optical_rotation: Matrix3,
    ) -> "CameraExtrinsics":
        """Create extrinsics from camera pose in world coordinates."""

        _validate_rotation("camera_to_world_rotation", camera_to_world_rotation)
        _require_vec3("camera_center_world", camera_center_world)
        rotation = tuple(zip(*camera_to_world_rotation))
        world_to_camera_rotation = tuple(tuple(float(value) for value in row) for row in rotation)  # type: ignore[assignment]
        translation = tuple(
            -sum(world_to_camera_rotation[row][column] * camera_center_world[column] for column in range(3))
            for row in range(3)
        )
        return cls(world_to_camera_rotation, translation, device_to_optical_rotation)


@dataclass(frozen=True)
class ObstacleBox3D:
    """World-axis-aligned 3D Box.

    Corner order is fixed as nested signs over x, y, then z:
    ``(-x,-y,-z), (-x,-y,+z), (-x,+y,-z), (-x,+y,+z),
    (+x,-y,-z), (+x,-y,+z), (+x,+y,-z), (+x,+y,+z)``.
    """

    obstacle_id: str
    center_x: float
    center_y: float
    center_z: float
    size_x: float
    size_y: float
    size_z: float

    def __post_init__(self) -> None:
        if not self.obstacle_id:
            raise ValueError("obstacle_id must be non-empty")
        for name in ("center_x", "center_y", "center_z", "size_x", "size_y", "size_z"):
            _require_finite(name, getattr(self, name))
        if self.size_x <= 0:
            raise ValueError("size_x must be positive")
        if self.size_y <= 0:
            raise ValueError("size_y must be positive")
        if self.size_z <= 0:
            raise ValueError("size_z must be positive")

    @property
    def center_world(self) -> Vec3:
        """Return the Box center in world coordinates."""

        return (self.center_x, self.center_y, self.center_z)

    @property
    def size(self) -> Vec3:
        """Return the Box size along world x, y, and z."""

        return (self.size_x, self.size_y, self.size_z)

    @property
    def corners_world(self) -> tuple[Vec3, ...]:
        """Return the eight world corners in the documented deterministic order."""

        hx = self.size_x / 2.0
        hy = self.size_y / 2.0
        hz = self.size_z / 2.0
        return (
            (self.center_x - hx, self.center_y - hy, self.center_z - hz),
            (self.center_x - hx, self.center_y - hy, self.center_z + hz),
            (self.center_x - hx, self.center_y + hy, self.center_z - hz),
            (self.center_x - hx, self.center_y + hy, self.center_z + hz),
            (self.center_x + hx, self.center_y - hy, self.center_z - hz),
            (self.center_x + hx, self.center_y - hy, self.center_z + hz),
            (self.center_x + hx, self.center_y + hy, self.center_z - hz),
            (self.center_x + hx, self.center_y + hy, self.center_z + hz),
        )


@dataclass(frozen=True)
class ProjectedPoint:
    """A projected image point with positive optical depth."""

    u_px: float
    v_px: float
    depth_m: float
    inside_image: bool

    def __post_init__(self) -> None:
        for name in ("u_px", "v_px", "depth_m"):
            _require_finite(name, getattr(self, name))
        if self.depth_m <= 0:
            raise ValueError("depth_m must be positive")
        if not isinstance(self.inside_image, bool):
            raise ValueError("inside_image must be a bool")

    @classmethod
    def from_image_coordinates(cls, u_px: float, v_px: float, depth_m: float, intrinsics: CameraIntrinsics) -> "ProjectedPoint":
        """Construct a point and classify whether it lies inside the image."""

        return cls(
            u_px=u_px,
            v_px=v_px,
            depth_m=depth_m,
            inside_image=0.0 <= u_px <= intrinsics.width_px - 1 and 0.0 <= v_px <= intrinsics.height_px - 1,
        )


@dataclass(frozen=True)
class ProjectedObstacle:
    """Projection result for one obstacle Box.

    ``projected_polygon`` is the near-plane-clipped polygon before image
    clipping. ``clipped_polygon`` is clipped to image bounds. ``projected_area``
    is the clipped polygon area in pixel squared.
    """

    obstacle_id: str
    visibility_status: VisibilityStatus
    projected_polygon: tuple[ProjectedPoint, ...]
    clipped_polygon: tuple[ProjectedPoint, ...]
    bounding_box: BoundingBox | None
    minimum_depth_m: float | None
    maximum_depth_m: float | None
    projected_area_px: float
    truncation_fraction: float

    def __post_init__(self) -> None:
        if not self.obstacle_id:
            raise ValueError("obstacle_id must be non-empty")
        if not isinstance(self.visibility_status, VisibilityStatus):
            raise ValueError("visibility_status must be a VisibilityStatus")
        if not isinstance(self.projected_polygon, tuple):
            raise ValueError("projected_polygon must be a tuple")
        if not isinstance(self.clipped_polygon, tuple):
            raise ValueError("clipped_polygon must be a tuple")
        for point in self.projected_polygon + self.clipped_polygon:
            if not isinstance(point, ProjectedPoint):
                raise ValueError("polygons must contain ProjectedPoint values")
        if self.bounding_box is not None:
            if len(self.bounding_box) != 4:
                raise ValueError("bounding_box must have four values")
            for index, value in enumerate(self.bounding_box):
                _require_finite(f"bounding_box[{index}]", value)
        for name in ("minimum_depth_m", "maximum_depth_m"):
            value = getattr(self, name)
            if value is not None:
                _require_finite(name, value)
                if value <= 0:
                    raise ValueError(f"{name} must be positive")
        if self.minimum_depth_m is not None and self.maximum_depth_m is not None and self.minimum_depth_m > self.maximum_depth_m:
            raise ValueError("minimum_depth_m must be <= maximum_depth_m")
        _require_finite("projected_area_px", self.projected_area_px)
        if self.projected_area_px < 0:
            raise ValueError("projected_area_px must be non-negative")
        _require_finite("truncation_fraction", self.truncation_fraction)
        if self.truncation_fraction < 0 or self.truncation_fraction > 1:
            raise ValueError("truncation_fraction must be in [0, 1]")

