"""Webots static Box obstacle adapter for the world-risk core."""

from __future__ import annotations

import math
from typing import Sequence

from risk_map.models import ObstacleFootprint


def _require_vector(name: str, values: Sequence[float], expected_length: int) -> tuple[float, ...]:
    if len(values) != expected_length:
        raise ValueError(f"{name} must have {expected_length} values")
    parsed = tuple(float(value) for value in values)
    for value in parsed:
        if not math.isfinite(value):
            raise ValueError(f"{name} values must be finite")
    return parsed


def obstacle_from_box_fields(
    *,
    obstacle_id: str,
    translation: Sequence[float],
    rotation: Sequence[float],
    size: Sequence[float],
) -> ObstacleFootprint:
    x, y, _z = _require_vector("translation", translation, 3)
    rx, ry, rz, angle = _require_vector("rotation", rotation, 4)
    size_x, size_y, _size_z = _require_vector("size", size, 3)
    if size_x <= 0 or size_y <= 0:
        raise ValueError("Box size_x and size_y must be positive")
    if abs(angle) > 1e-9 and (abs(rx) > 1e-9 or abs(ry) > 1e-9 or abs(abs(rz) - 1.0) > 1e-9):
        raise ValueError("Box rotation must not tilt the obstacle")
    if abs(angle) > 1e-9:
        raise ValueError("Box must not have planar rotation")
    return ObstacleFootprint(obstacle_id, x, y, size_x, size_y)


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
        type_name = geometry_node.getTypeName()
        if type_name != "Box":
            raise ValueError(f"Expected Box geometry, got {type_name}")
        size_field = geometry_node.getField("size")
        if size_field is None:
            raise ValueError("Box geometry has no size field")
        return tuple(size_field.getSFVec3f())
    raise ValueError("Solid does not contain a Shape with Box geometry")


def read_static_box_obstacle(supervisor, def_name: str, obstacle_id: str) -> ObstacleFootprint:
    node = supervisor.getFromDef(def_name)
    if node is None:
        raise ValueError(f"Missing Webots DEF node: {def_name}")
    translation_field = node.getField("translation")
    rotation_field = node.getField("rotation")
    if translation_field is None:
        raise ValueError(f"{def_name} has no translation field")
    if rotation_field is None:
        raise ValueError(f"{def_name} has no rotation field")
    translation = translation_field.getSFVec3f()
    rotation = rotation_field.getSFRotation()
    size = _get_box_size_from_solid(node)
    return obstacle_from_box_fields(
        obstacle_id=obstacle_id,
        translation=translation,
        rotation=rotation,
        size=size,
    )
