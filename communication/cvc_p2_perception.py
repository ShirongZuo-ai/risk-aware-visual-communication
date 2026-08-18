"""CVC-P2 deterministic connected-component perception and control."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class RedComponent:
    area: int
    centroid_xy: tuple[float, float]
    bbox_xyxy: tuple[int, int, int, int]
    bearing_normalized: float
    apparent_proximity: float
    confidence: float


@dataclass(frozen=True)
class VisualObstacle:
    detected: bool
    bearing_normalized: float | None
    proximity: float
    bbox_xyxy: tuple[int, int, int, int] | None
    pixel_count: int
    centroid_xy: tuple[float, float] | None = None
    component_count: int = 0
    confidence: float = 0.0
    apparent_proximity: float = 0.0
    components: tuple[RedComponent, ...] = ()


def _connected_components(mask: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return deterministic 8-connected components in row-major seed order."""
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[tuple[np.ndarray, np.ndarray]] = []
    for seed_y, seed_x in zip(*np.nonzero(mask)):
        if visited[seed_y, seed_x]:
            continue
        stack = [(int(seed_y), int(seed_x))]
        visited[seed_y, seed_x] = True
        ys: list[int] = []
        xs: list[int] = []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if (dy or dx) and 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
        components.append((np.asarray(ys, dtype=np.int32), np.asarray(xs, dtype=np.int32)))
    return components


def detect_red_obstacle(decoded_rgb: Image.Image, min_pixels: int = 12) -> VisualObstacle:
    """Detect the largest coherent red obstacle using decoded pixels only."""
    rgb = np.asarray(decoded_rgb.convert("RGB"), dtype=np.int16)
    mask = ((rgb[..., 0] >= 90) & (rgb[..., 0] >= rgb[..., 1] * 3 // 2 + 20) &
            (rgb[..., 0] >= rgb[..., 2] * 3 // 2 + 20))
    components = _connected_components(mask)
    measured: list[RedComponent] = []
    frame_area = rgb.shape[0] * rgb.shape[1]
    for component_ys, component_xs in components:
        area = int(component_xs.size)
        x0, x1 = int(component_xs.min()), int(component_xs.max()) + 1
        y0, y1 = int(component_ys.min()), int(component_ys.max()) + 1
        bearing = float((component_xs.mean() - (rgb.shape[1] - 1) / 2) / (rgb.shape[1] / 2))
        proximity = float(min(1.0, area / (frame_area * 0.25)))
        fill = area / max(1, (x1 - x0) * (y1 - y0))
        confidence = float(min(1.0, (area / max(min_pixels, 1)) / 4.0) * min(1.0, fill / 0.55))
        measured.append(RedComponent(area, (float(component_xs.mean()), float(component_ys.mean())),
                                     (x0, y0, x1, y1), bearing, proximity, confidence))
    measured.sort(key=lambda item: (-item.area, -item.centroid_xy[1], item.centroid_xy[0]))
    viable = [component for component in measured if component.area >= min_pixels]
    total_red = int(mask.sum())
    if not viable:
        return VisualObstacle(False, None, 0.0, None, total_red, None, len(components), 0.0, 0.0, tuple(measured))
    primary = viable[0]
    return VisualObstacle(True, primary.bearing_normalized, primary.apparent_proximity,
                          primary.bbox_xyxy, primary.area, primary.centroid_xy,
                          len(components), primary.confidence, primary.apparent_proximity,
                          tuple(measured))


def visual_wheel_command(obstacle: VisualObstacle, cruise: float = 3.0) -> tuple[float, float]:
    """Use only decoded bearing and proximity for steering, speed, and braking."""
    if not obstacle.detected:
        return cruise, cruise
    proximity = obstacle.apparent_proximity or obstacle.proximity
    speed = 0.0 if proximity >= 0.34 else cruise * max(0.12, 1.0 - 2.35 * proximity)
    turn = float(obstacle.bearing_normalized or 0.0) * min(2.4, 0.8 + 8.0 * proximity)
    return max(0.0, speed + turn), max(0.0, speed - turn)
