"""Webots camera conversion and CVC-P1 visual acceptance diagnostics."""
from __future__ import annotations

from dataclasses import dataclass
from PIL import Image, ImageStat

from communication.cvc_perception import VisualObstacle, detect_red_obstacle, visual_wheel_command


def webots_bgra_to_rgb(raw: bytes | bytearray | memoryview | None, width: int, height: int) -> Image.Image:
    """Convert Webots Camera.getImage() BGRA bytes without channel ambiguity."""
    if width <= 0 or height <= 0:
        raise ValueError("camera dimensions must be positive")
    if raw is None:
        raise ValueError("camera returned no image; enable it and step before reading")
    payload = bytes(raw)
    expected = width * height * 4
    if len(payload) != expected:
        raise ValueError(f"camera buffer length {len(payload)} does not match BGRA size {expected}")
    return Image.frombytes("RGBA", (width, height), payload, "raw", "BGRA").convert("RGB")


@dataclass(frozen=True)
class CameraAcceptance:
    accepted: bool
    reason: str
    channel_ranges: tuple[int, int, int]
    luminance_mean: float
    obstacle: VisualObstacle


def assess_control_frame(image: Image.Image, *, min_channel_range: int = 4, min_luminance: float = 2.0) -> CameraAcceptance:
    """Reject frames that cannot establish image-dependent CVC control.

    This is a development acceptance diagnostic, not a runtime source of hidden
    geometry and not an evaluator metric.
    """
    rgb = image.convert("RGB")
    extrema = rgb.getextrema()
    ranges = tuple(int(high - low) for low, high in extrema)
    luminance = float(ImageStat.Stat(rgb.convert("L")).mean[0])
    obstacle = detect_red_obstacle(rgb)
    if luminance < min_luminance:
        return CameraAcceptance(False, "underexposed_or_black", ranges, luminance, obstacle)
    if max(ranges) < min_channel_range:
        return CameraAcceptance(False, "spatially_uniform", ranges, luminance, obstacle)
    return CameraAcceptance(True, "usable", ranges, luminance, obstacle)


def control_is_image_dependent(reference: Image.Image, counterfactual: Image.Image) -> bool:
    """Acceptance check: changing only received pixels must change wheel output."""
    reference_command = visual_wheel_command(detect_red_obstacle(reference))
    counterfactual_command = visual_wheel_command(detect_red_obstacle(counterfactual))
    return reference_command != counterfactual_command
