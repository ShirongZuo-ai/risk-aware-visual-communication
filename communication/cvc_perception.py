"""Deterministic classical perception operating only on receiver images."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class VisualObstacle:
    detected: bool
    bearing_normalized: float | None
    proximity: float
    bbox_xyxy: tuple[int, int, int, int] | None
    pixel_count: int


def detect_red_obstacle(decoded_rgb: Image.Image, min_pixels: int = 12) -> VisualObstacle:
    """Detect saturated red controlled-scene obstacles from decoded pixels."""
    rgb = np.asarray(decoded_rgb.convert("RGB"), dtype=np.int16)
    mask = (rgb[..., 0] >= 90) & (rgb[..., 0] >= rgb[..., 1] * 3 // 2 + 20) & (rgb[..., 0] >= rgb[..., 2] * 3 // 2 + 20)
    ys, xs = np.nonzero(mask)
    count = int(xs.size)
    if count < min_pixels:
        return VisualObstacle(False, None, 0.0, None, count)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    bearing = float((xs.mean() - (rgb.shape[1] - 1) / 2) / (rgb.shape[1] / 2))
    proximity = float(min(1.0, count / (rgb.shape[0] * rgb.shape[1] * 0.25)))
    return VisualObstacle(True, bearing, proximity, (x0, y0, x1, y1), count)


def visual_wheel_command(obstacle: VisualObstacle, cruise: float = 3.0) -> tuple[float, float]:
    """Interpretable image-dependent steering/braking command."""
    if not obstacle.detected:
        return cruise, cruise
    speed = cruise * max(0.1, 1.0 - obstacle.proximity)
    turn = float(obstacle.bearing_normalized or 0.0) * 2.0
    # Turn away from the obstacle: right-side obstacle slows right wheel.
    return max(0.0, speed + turn), max(0.0, speed - turn)
