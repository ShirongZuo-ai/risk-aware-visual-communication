"""Causal decoded-visual obstacle geometry for the Q1 local planner."""
from __future__ import annotations

from dataclasses import dataclass
import math

from communication.cvc_p2_perception import VisualObstacle
from navigation.cvc_q1_local_planner import LocalObstacleEstimate


@dataclass(frozen=True)
class VisualRangeCalibration:
    inverse_height_coefficient_m_px: float
    intercept_m: float
    uncertainty_bound_m: float
    minimum_bbox_height_px: int = 2

    def estimate_center_range_m(self, bbox_height_px: int) -> float:
        height = max(int(bbox_height_px), self.minimum_bbox_height_px)
        return max(0.04, self.inverse_height_coefficient_m_px / height + self.intercept_m)


def visual_obstacle_estimates(
    observation: VisualObstacle,
    calibration: VisualRangeCalibration,
    *,
    camera_horizontal_fov_rad: float = 0.84,
    known_obstacle_radius_m: float = 0.04,
    minimum_component_pixels: int = 12,
) -> tuple[LocalObstacleEstimate, ...]:
    """Convert decoded connected components to conservative robot-local circles."""
    estimates: list[LocalObstacleEstimate] = []
    for component in observation.components:
        if component.area < minimum_component_pixels:
            continue
        height = max(1, component.bbox_xyxy[3] - component.bbox_xyxy[1])
        center_range = calibration.estimate_center_range_m(height)
        bearing_rad = -float(component.bearing_normalized) * camera_horizontal_fov_rad / 2.0
        estimates.append(LocalObstacleEstimate(
            center_range * math.cos(bearing_rad),
            center_range * math.sin(bearing_rad),
            known_obstacle_radius_m,
            calibration.uncertainty_bound_m,
            "decoded_visual_component",
        ))
    return tuple(estimates)
