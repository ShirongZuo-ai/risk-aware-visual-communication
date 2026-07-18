"""Milestone 4D image-risk validation configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from perception.camera_models import VisibilityStatus
from simulator.m3c_config import (
    ANALYSIS_TIME_S,
    COMMAND_SCHEDULE,
    PREDICTION_HORIZON_S,
    PREDICTION_STEP_S,
    RISK_PARAMETERS,
)
from simulator.m4c_config import (
    CAMERA_DEVICE_NAME,
    COLOR_DISTANCE_THRESHOLD,
    EXPECTED_CAMERA_HEIGHT_PX,
    EXPECTED_CAMERA_WIDTH_PX,
    EXPECTED_HORIZONTAL_FOV_RAD,
    EXPECTED_NEAR_CLIP_M,
    FULLY_VISIBLE_BBOX_IOU_MIN,
    FULLY_VISIBLE_CENTER_ERROR_PX_MAX,
    FULLY_VISIBLE_POLYGON_IOU_MIN,
    LEFT_WHEEL_DEVICE_NAME,
    PARTIAL_BBOX_IOU_MIN,
    PARTIAL_CENTER_ERROR_PX_MAX,
    PARTIAL_POLYGON_IOU_MIN,
    RIGHT_WHEEL_DEVICE_NAME,
)


EPISODE_PREFIX = "image_risk_validation"
M4_LOG_DIR = Path("data/logs/m4")
M4_FRAME_DIR = Path("data/frames/m4")
M4_METADATA_DIR = Path("data/metadata/m4")
M4_MASK_DIR = Path("data/masks/m4")
M4_RESULTS_DIR = Path("results/m4_image_risk")

SNAPSHOT_TIME_S = ANALYSIS_TIME_S
DOMINANCE_MARGIN = 0.04
VISIBILITY_DOMINANCE_MARGIN = 0.005
SHARED_RISK_MIN = 0.05
LOW_RISK_MAX = 0.02
RISK_TOLERANCE = 1e-8
GEOMETRY_TOLERANCE_PX = 1e-6


@dataclass(frozen=True)
class M4DObstacleSpec:
    def_name: str
    obstacle_id: str
    role: str
    target_rgb: tuple[int, int, int]
    center_m: tuple[float, float, float]
    size_m: tuple[float, float, float]
    expected_visibility: VisibilityStatus
    auto_color_validation: bool
    require_exclusive_pixel: bool


OBSTACLE_SPECS: tuple[M4DObstacleSpec, ...] = (
    M4DObstacleSpec(
        "M4D_PLANNED_DOMINANT_VISIBLE",
        "M4D_PLANNED_DOMINANT_VISIBLE",
        "PLANNED_DOMINANT_VISIBLE",
        (235, 40, 35),
        (0.296386, 0.141991, 0.025),
        (0.025, 0.025, 0.050),
        VisibilityStatus.PARTIALLY_VISIBLE,
        True,
        True,
    ),
    M4DObstacleSpec(
        "M4D_STATE_DOMINANT_VISIBLE",
        "M4D_STATE_DOMINANT_VISIBLE",
        "STATE_DOMINANT_VISIBLE",
        (40, 220, 55),
        (0.229254, 0.164200, 0.025),
        (0.025, 0.025, 0.050),
        VisibilityStatus.PARTIALLY_VISIBLE,
        True,
        True,
    ),
    M4DObstacleSpec(
        "M4D_SHARED_RISK_VISIBLE",
        "M4D_SHARED_RISK_VISIBLE",
        "SHARED_RISK_VISIBLE",
        (45, 85, 240),
        (0.267615, 0.208113, 0.020),
        (0.040, 0.040, 0.040),
        VisibilityStatus.FULLY_VISIBLE,
        True,
        True,
    ),
    M4DObstacleSpec(
        "M4D_LOW_RISK_VISIBLE",
        "M4D_LOW_RISK_VISIBLE",
        "LOW_RISK_VISIBLE",
        (245, 210, 35),
        (0.227992, 0.326983, 0.015),
        (0.025, 0.025, 0.030),
        VisibilityStatus.FULLY_VISIBLE,
        True,
        True,
    ),
    M4DObstacleSpec(
        "M4D_PARTIAL_VISIBLE",
        "M4D_PARTIAL_VISIBLE",
        "PARTIAL_VISIBLE",
        (240, 45, 210),
        (0.395318, 0.296950, 0.015),
        (0.025, 0.025, 0.030),
        VisibilityStatus.PARTIALLY_VISIBLE,
        True,
        True,
    ),
    M4DObstacleSpec(
        "M4D_OUTSIDE_VIEW",
        "M4D_OUTSIDE_VIEW",
        "OUTSIDE_VIEW",
        (40, 230, 230),
        (-0.034733, 0.221741, 0.025),
        (0.025, 0.025, 0.050),
        VisibilityStatus.OUTSIDE_FRUSTUM,
        True,
        False,
    ),
    M4DObstacleSpec(
        "M4D_BEHIND_CAMERA",
        "M4D_BEHIND_CAMERA",
        "BEHIND_CAMERA",
        (250, 120, 30),
        (0.225216, -0.028112, 0.025),
        (0.025, 0.025, 0.050),
        VisibilityStatus.BEHIND_CAMERA,
        True,
        False,
    ),
    M4DObstacleSpec(
        "M4D_OVERLAP_BACK",
        "M4D_OVERLAP_BACK",
        "OVERLAP_BACK",
        (120, 70, 245),
        (0.271149, 0.227799, 0.020),
        (0.040, 0.040, 0.040),
        VisibilityStatus.FULLY_VISIBLE,
        False,
        False,
    ),
    M4DObstacleSpec(
        "M4D_OVERLAP_FRONT",
        "M4D_OVERLAP_FRONT",
        "OVERLAP_FRONT",
        (245, 245, 245),
        (0.262694, 0.208997, 0.0175),
        (0.035, 0.035, 0.035),
        VisibilityStatus.FULLY_VISIBLE,
        False,
        False,
    ),
)

OVERLAP_PAIR = ("M4D_OVERLAP_FRONT", "M4D_OVERLAP_BACK")
ROLE_ORDER = tuple(spec.role for spec in OBSTACLE_SPECS)


def obstacle_spec_by_id() -> dict[str, M4DObstacleSpec]:
    return {spec.obstacle_id: spec for spec in OBSTACLE_SPECS}


def obstacle_spec_by_role() -> dict[str, M4DObstacleSpec]:
    return {spec.role: spec for spec in OBSTACLE_SPECS}
