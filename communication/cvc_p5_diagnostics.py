"""Decoded held-versus-current novelty and control-sensitivity diagnostics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
from PIL import Image

from communication.cvc_p2_perception import VisualObstacle, visual_wheel_command
from evaluation.image_quality import compute_ssim


@dataclass(frozen=True)
class VisualNovelty:
    pixel_mae: float
    pixel_rmse: float
    structural_difference: float
    changed_pixel_fraction: float


@dataclass(frozen=True)
class PerceptionNovelty:
    existence_change: float
    delta_bearing: float
    delta_proximity: float
    delta_confidence: float
    centroid_distance_normalized: float
    bbox_one_minus_iou: float
    component_count_delta_normalized: float
    combined_l2: float


@dataclass(frozen=True)
class ControlSensitivity:
    left_delta: float
    right_delta: float
    forward_speed_delta: float
    steering_delta: float
    control_l2: float


def visual_novelty(held: Image.Image, current: Image.Image, changed_threshold: int = 10) -> VisualNovelty:
    if held.size != current.size or not 1 <= changed_threshold <= 255:
        raise ValueError("invalid held/current visual diagnostic input")
    left = np.asarray(held.convert("RGB"), dtype=np.uint8)
    right = np.asarray(current.convert("RGB"), dtype=np.uint8)
    difference = left.astype(np.float64) - right.astype(np.float64)
    absolute = np.abs(difference)
    mae = float(np.mean(absolute))
    rmse = float(math.sqrt(np.mean(difference * difference)))
    changed = float(np.mean(np.max(absolute, axis=2) >= changed_threshold))
    return VisualNovelty(mae, rmse, 1.0 - compute_ssim(left, right), changed)


def _bbox_iou(left: tuple[int, int, int, int] | None, right: tuple[int, int, int, int] | None) -> float:
    if left is None and right is None:
        return 1.0
    if left is None or right is None:
        return 0.0
    x0, y0, x1, y1 = max(left[0], right[0]), max(left[1], right[1]), min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 1.0


def perception_novelty(held: VisualObstacle, current: VisualObstacle,
                       frame_size: tuple[int, int] = (160, 120)) -> PerceptionNovelty:
    existence = float(held.detected != current.detected)
    bearing = abs(float(held.bearing_normalized or 0.0) - float(current.bearing_normalized or 0.0))
    proximity = abs(float(held.apparent_proximity or held.proximity) -
                    float(current.apparent_proximity or current.proximity))
    confidence = abs(held.confidence - current.confidence)
    if held.centroid_xy is None and current.centroid_xy is None:
        centroid = 0.0
    elif held.centroid_xy is None or current.centroid_xy is None:
        centroid = 1.0
    else:
        centroid = math.hypot(held.centroid_xy[0] - current.centroid_xy[0],
                              held.centroid_xy[1] - current.centroid_xy[1]) / math.hypot(*frame_size)
    bbox_change = 1.0 - _bbox_iou(held.bbox_xyxy, current.bbox_xyxy)
    count_delta = min(1.0, abs(held.component_count - current.component_count) / 5.0)
    values = (existence, bearing, proximity, confidence, centroid, bbox_change, count_delta)
    return PerceptionNovelty(existence, bearing, proximity, confidence, centroid, bbox_change,
                             count_delta, math.sqrt(sum(value * value for value in values)))


def control_sensitivity(held: VisualObstacle, current: VisualObstacle, cruise: float) -> ControlSensitivity:
    held_left, held_right = visual_wheel_command(held, cruise)
    current_left, current_right = visual_wheel_command(current, cruise)
    left_delta, right_delta = current_left - held_left, current_right - held_right
    held_speed, current_speed = (held_left + held_right) / 2, (current_left + current_right) / 2
    held_steering, current_steering = (held_left - held_right) / 2, (current_left - current_right) / 2
    return ControlSensitivity(left_delta, right_delta, current_speed - held_speed,
                              current_steering - held_steering,
                              math.hypot(left_delta, right_delta))


def diagnostic_dict(visual: VisualNovelty, perception: PerceptionNovelty,
                    control: ControlSensitivity) -> dict:
    return {"visual": asdict(visual), "perception": asdict(perception), "control": asdict(control)}
