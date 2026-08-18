from __future__ import annotations

import pytest

from communication.cvc_p2_perception import RedComponent, VisualObstacle
from communication.cvc_q1_visual_geometry import VisualRangeCalibration, visual_obstacle_estimates


def test_inverse_height_range_is_monotonic_and_conservative_metadata_retained() -> None:
    calibration = VisualRangeCalibration(12.0, .05, .04)
    assert calibration.estimate_center_range_m(20) > calibration.estimate_center_range_m(40)
    component = RedComponent(100, (120, 60), (110, 40, 130, 80), .5, .1, 1.0)
    visual = VisualObstacle(True, .5, .1, component.bbox_xyxy, 100, component.centroid_xy,
                            1, 1.0, .1, (component,))
    estimate = visual_obstacle_estimates(visual, calibration)[0]
    assert estimate.x_m > 0
    assert estimate.y_m < 0  # image-right maps to robot-right
    assert estimate.range_uncertainty_m == .04
    assert estimate.source == "decoded_visual_component"


def test_small_components_are_not_promoted_to_planner_obstacles() -> None:
    component = RedComponent(5, (80, 60), (78, 55, 82, 65), 0.0, .01, .1)
    visual = VisualObstacle(False, None, 0.0, None, 5, None, 1, 0.0, 0.0, (component,))
    assert visual_obstacle_estimates(visual, VisualRangeCalibration(12, 0, .04)) == ()
