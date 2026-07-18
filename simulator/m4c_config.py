"""Milestone 4C Webots camera-projection validation configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from perception.camera_models import VisibilityStatus


CAMERA_DEVICE_NAME = "camera"
LEFT_WHEEL_DEVICE_NAME = "left wheel motor"
RIGHT_WHEEL_DEVICE_NAME = "right wheel motor"

EXPECTED_CAMERA_WIDTH_PX = 160
EXPECTED_CAMERA_HEIGHT_PX = 120
EXPECTED_HORIZONTAL_FOV_RAD = 0.84
EXPECTED_NEAR_CLIP_M = 0.0055
SNAPSHOT_TIME_S = 0.320

EPISODE_PREFIX = "projection_validation"
M4_LOG_DIR = Path("data/logs/m4")
M4_FRAME_DIR = Path("data/frames/m4")
M4_METADATA_DIR = Path("data/metadata/m4")
M4_RESULTS_DIR = Path("results/m4_projection")

COLOR_DISTANCE_THRESHOLD = 90.0
MIN_ABSENT_COLOR_PIXELS = 8

FULLY_VISIBLE_BBOX_IOU_MIN = 0.80
FULLY_VISIBLE_POLYGON_IOU_MIN = 0.70
FULLY_VISIBLE_CENTER_ERROR_PX_MAX = 2.0
FULLY_VISIBLE_SIZE_REL_ERROR_MAX = 0.12

PARTIAL_BBOX_IOU_MIN = 0.65
PARTIAL_POLYGON_IOU_MIN = 0.55
PARTIAL_CENTER_ERROR_PX_MAX = 3.0
PARTIAL_SIZE_REL_ERROR_MAX = 0.20


@dataclass(frozen=True)
class M4CObstacleSpec:
    def_name: str
    role: str
    target_rgb: tuple[int, int, int]
    size_m: tuple[float, float, float]
    expected_visibility: VisibilityStatus
    auto_color_validation: bool


OBSTACLE_SPECS: tuple[M4CObstacleSpec, ...] = (
    M4CObstacleSpec(
        "M4_CENTER_VISIBLE",
        "CENTER_VISIBLE",
        (235, 40, 35),
        (0.050, 0.050, 0.050),
        VisibilityStatus.FULLY_VISIBLE,
        True,
    ),
    M4CObstacleSpec(
        "M4_LEFT_VISIBLE",
        "LEFT_VISIBLE",
        (40, 220, 55),
        (0.050, 0.050, 0.050),
        VisibilityStatus.FULLY_VISIBLE,
        True,
    ),
    M4CObstacleSpec(
        "M4_RIGHT_VISIBLE",
        "RIGHT_VISIBLE",
        (45, 85, 240),
        (0.050, 0.050, 0.050),
        VisibilityStatus.FULLY_VISIBLE,
        True,
    ),
    M4CObstacleSpec(
        "M4_PARTIAL_IMAGE_EDGE",
        "PARTIAL_IMAGE_EDGE",
        (245, 210, 35),
        (0.060, 0.060, 0.060),
        VisibilityStatus.PARTIALLY_VISIBLE,
        True,
    ),
    M4CObstacleSpec(
        "M4_OUTSIDE_FRUSTUM",
        "OUTSIDE_FRUSTUM",
        (240, 45, 210),
        (0.050, 0.050, 0.050),
        VisibilityStatus.OUTSIDE_FRUSTUM,
        True,
    ),
    M4CObstacleSpec(
        "M4_BEHIND_CAMERA",
        "BEHIND_CAMERA",
        (40, 230, 230),
        (0.050, 0.050, 0.050),
        VisibilityStatus.BEHIND_CAMERA,
        True,
    ),
    M4CObstacleSpec(
        "M4_NEAR_PLANE_INTERSECTION",
        "NEAR_PLANE_INTERSECTION",
        (250, 120, 30),
        (0.006, 0.006, 0.006),
        VisibilityStatus.INTERSECTS_NEAR_PLANE,
        False,
    ),
    M4CObstacleSpec(
        "M4_DEPTH_OVERLAP_FRONT",
        "DEPTH_OVERLAP_FRONT",
        (245, 245, 245),
        (0.045, 0.045, 0.045),
        VisibilityStatus.FULLY_VISIBLE,
        False,
    ),
    M4CObstacleSpec(
        "M4_DEPTH_OVERLAP_BACK",
        "DEPTH_OVERLAP_BACK",
        (120, 70, 245),
        (0.050, 0.050, 0.050),
        VisibilityStatus.FULLY_VISIBLE,
        False,
    ),
)


def obstacle_spec_by_def() -> dict[str, M4CObstacleSpec]:
    return {spec.def_name: spec for spec in OBSTACLE_SPECS}


def obstacle_spec_by_role() -> dict[str, M4CObstacleSpec]:
    return {spec.role: spec for spec in OBSTACLE_SPECS}
