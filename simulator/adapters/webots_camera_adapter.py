"""Webots adapter for Milestone 4C camera projection validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Sequence

from perception.camera_models import CameraExtrinsics, CameraIntrinsics, Matrix3, ObstacleBox3D, Vec3


DEVICE_TO_OPTICAL_ROTATION: Matrix3 = (
    (0.0, -1.0, 0.0),
    (0.0, 0.0, -1.0),
    (1.0, 0.0, 0.0),
)

POSE_MATCH_TOLERANCE = 1e-7
ROTATION_TOLERANCE = 1e-6


@dataclass(frozen=True)
class CameraSnapshot:
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    camera_world_position: Vec3
    camera_to_world_rotation: Matrix3
    camera_pose_matrix: tuple[float, ...]
    horizontal_fov_rad: float
    width_px: int
    height_px: int
    near_clip_m: float


def _require_finite_sequence(name: str, values: Sequence[float], expected_length: int) -> tuple[float, ...]:
    if len(values) != expected_length:
        raise ValueError(f"{name} must have {expected_length} values")
    parsed = tuple(float(value) for value in values)
    for index, value in enumerate(parsed):
        if not math.isfinite(value):
            raise ValueError(f"{name}[{index}] must be finite")
    return parsed


def _matrix_from_rows(rows: Sequence[Sequence[float]]) -> Matrix3:
    if len(rows) != 3:
        raise ValueError("rotation must have 3 rows")
    return tuple(tuple(_require_finite_sequence(f"rotation[{index}]", row, 3)) for index, row in enumerate(rows))  # type: ignore[return-value]


def _is_orthonormal(matrix: Matrix3, tolerance: float = ROTATION_TOLERANCE) -> bool:
    for row in matrix:
        if abs(sum(value * value for value in row) - 1.0) > tolerance:
            return False
    for first in range(3):
        for second in range(first + 1, 3):
            if abs(sum(matrix[first][k] * matrix[second][k] for k in range(3))) > tolerance:
                return False
    return abs(_determinant3(matrix) - 1.0) <= tolerance


def _determinant3(matrix: Matrix3) -> float:
    (a, b, c), (d, e, f), (g, h, i) = matrix
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _close_vec3(left: Vec3, right: Sequence[float], tolerance: float = POSE_MATCH_TOLERANCE) -> bool:
    return all(abs(left[index] - float(right[index])) <= tolerance for index in range(3))


def parse_camera_pose_matrix(
    pose_values: Sequence[float],
    *,
    expected_position: Sequence[float] | None = None,
) -> tuple[Matrix3, Vec3, str]:
    """Parse a Webots 4x4 camera-to-world pose matrix.

    Webots exposes pose as 16 floats. Runtime callers pass ``expected_position``
    from ``Node.getPosition()`` so the helper can reject an unexpected layout
    instead of silently accepting a wrong translation column.
    """

    values = _require_finite_sequence("pose_values", pose_values, 16)
    row_major_rotation = (
        (values[0], values[1], values[2]),
        (values[4], values[5], values[6]),
        (values[8], values[9], values[10]),
    )
    row_major_position = (values[3], values[7], values[11])
    column_major_rotation = (
        (values[0], values[4], values[8]),
        (values[1], values[5], values[9]),
        (values[2], values[6], values[10]),
    )
    column_major_position = (values[12], values[13], values[14])

    candidates: list[tuple[Matrix3, Vec3, str]] = []
    if _is_orthonormal(row_major_rotation):
        candidates.append((row_major_rotation, row_major_position, "row_major_translation_column"))
    if _is_orthonormal(column_major_rotation):
        candidates.append((column_major_rotation, column_major_position, "column_major_translation_row"))

    if expected_position is not None:
        expected = _require_finite_sequence("expected_position", expected_position, 3)
        candidates = [candidate for candidate in candidates if _close_vec3(candidate[1], expected)]

    if not candidates:
        raise ValueError("pose matrix does not contain a supported orthonormal camera-to-world transform")
    return candidates[0]


def camera_pose_to_extrinsics(camera_to_world_rotation: Matrix3, camera_world_position: Vec3) -> CameraExtrinsics:
    return CameraExtrinsics.from_camera_pose_in_world(
        camera_to_world_rotation,
        camera_world_position,
        DEVICE_TO_OPTICAL_ROTATION,
    )


def intrinsics_from_camera_values(width_px: int, height_px: int, horizontal_fov_rad: float, near_clip_m: float) -> CameraIntrinsics:
    return CameraIntrinsics.from_horizontal_fov(width_px, height_px, horizontal_fov_rad, near_clip_m)


def get_camera_node(supervisor, camera):
    tag = getattr(camera, "_tag", None)
    if tag is None:
        raise ValueError("Camera device does not expose a Webots device tag")
    node = supervisor.getFromDevice(tag)
    if node is None:
        raise ValueError("Supervisor.getFromDevice(camera_tag) returned no Camera node")
    return node


def read_camera_snapshot(supervisor, camera) -> CameraSnapshot:
    width = int(camera.getWidth())
    height = int(camera.getHeight())
    horizontal_fov = float(camera.getFov())
    near_clip = float(camera.getNear())
    intrinsics = intrinsics_from_camera_values(width, height, horizontal_fov, near_clip)

    camera_node = get_camera_node(supervisor, camera)
    position = tuple(float(value) for value in camera_node.getPosition())
    pose = tuple(float(value) for value in camera_node.getPose())
    rotation, camera_world_position, _layout = parse_camera_pose_matrix(pose, expected_position=position)
    extrinsics = camera_pose_to_extrinsics(rotation, camera_world_position)
    return CameraSnapshot(
        intrinsics=intrinsics,
        extrinsics=extrinsics,
        camera_world_position=camera_world_position,
        camera_to_world_rotation=rotation,
        camera_pose_matrix=pose,
        horizontal_fov_rad=horizontal_fov,
        width_px=width,
        height_px=height,
        near_clip_m=near_clip,
    )


def obstacle_box_from_fields(
    *,
    obstacle_id: str,
    translation: Sequence[float],
    rotation: Sequence[float],
    size: Sequence[float],
) -> ObstacleBox3D:
    center_x, center_y, center_z = _require_finite_sequence("translation", translation, 3)
    rx, ry, rz, angle = _require_finite_sequence("rotation", rotation, 4)
    size_x, size_y, size_z = _require_finite_sequence("size", size, 3)
    if size_x <= 0.0 or size_y <= 0.0 or size_z <= 0.0:
        raise ValueError("Box sizes must be positive")
    if abs(angle) > 1e-9:
        axis_norm = math.sqrt(rx * rx + ry * ry + rz * rz)
        if axis_norm > 1e-9:
            raise ValueError("Milestone 4C supports only unrotated, world-axis-aligned Boxes")
    return ObstacleBox3D(obstacle_id, center_x, center_y, center_z, size_x, size_y, size_z)


def _get_box_size_from_solid(solid_node) -> tuple[float, float, float]:
    children = solid_node.getField("children")
    if children is None:
        raise ValueError("Solid has no children field")
    for index in range(children.getCount()):
        child = children.getMFNode(index)
        geometry_field = child.getField("geometry") if child is not None else None
        if geometry_field is None:
            continue
        geometry_node = geometry_field.getSFNode()
        if geometry_node is None:
            continue
        if geometry_node.getTypeName() != "Box":
            continue
        size_field = geometry_node.getField("size")
        if size_field is None:
            raise ValueError("Box geometry has no size field")
        return tuple(float(value) for value in size_field.getSFVec3f())
    raise ValueError("Solid does not contain a Shape with Box geometry")


def read_static_box_3d(supervisor, def_name: str, obstacle_id: str) -> ObstacleBox3D:
    node = supervisor.getFromDef(def_name)
    if node is None:
        raise ValueError(f"Missing Webots DEF node: {def_name}")
    translation_field = node.getField("translation")
    rotation_field = node.getField("rotation")
    if translation_field is None:
        raise ValueError(f"{def_name} has no translation field")
    if rotation_field is None:
        raise ValueError(f"{def_name} has no rotation field")
    return obstacle_box_from_fields(
        obstacle_id=obstacle_id,
        translation=translation_field.getSFVec3f(),
        rotation=rotation_field.getSFRotation(),
        size=_get_box_size_from_solid(node),
    )


def save_camera_frame(camera, frame_path: Path, quality: int = 100) -> None:
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    result = camera.saveImage(str(frame_path), quality)
    if result != 0:
        raise RuntimeError(f"camera.saveImage failed with status {result}: {frame_path}")


def write_metadata_json(path: Path, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
