"""Causal sender-visible diagnostics for CVC-P7.

The functions in this module consume only decoded held/current perception and
the frozen visual controller.  Physical clearance, contact, and outcomes are
deliberately confined to :mod:`evaluation.cvc_p7_safety`.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from communication.cvc_p2_perception import VisualObstacle, visual_wheel_command


WHEEL_RADIUS_M = 0.0205
AXLE_LENGTH_M = 0.052


@dataclass(frozen=True)
class DirectionalControlDiagnostic:
    held_left_rad_s: float
    held_right_rad_s: float
    send_left_rad_s: float
    send_right_rad_s: float
    v_hold_m_s: float
    v_send_m_s: float
    omega_hold_rad_s: float
    omega_send_rad_s: float
    delta_v_m_s: float
    delta_abs_turn_rad_s: float
    delta_left_rad_s: float
    delta_right_rad_s: float
    steering_sign_change: bool
    slowdown_event: bool
    increased_turn_event: bool
    turn_toward_obstacle: bool
    turn_away_from_obstacle: bool


@dataclass(frozen=True)
class VisualSafetyCue:
    held_detected: bool
    current_detected: bool
    absolute_bearing: float
    bearing_convergence_rate_s: float
    bearing_moving_toward_center: bool
    proximity: float
    proximity_growth_rate_s: float
    approach_rate_s: float
    area_pixels: int
    area_growth_rate_px_s: float
    relative_area_growth_rate_s: float
    bbox_height_px: int
    bbox_height_growth_rate_px_s: float
    component_appearance: bool
    component_disappearance: bool
    component_count_delta: int
    forward_corridor_overlap: float
    conflict_relevant_appearance: bool


def wheel_kinematics(left_rad_s: float, right_rad_s: float) -> tuple[float, float]:
    """Return differential-drive forward velocity and yaw demand."""
    v = WHEEL_RADIUS_M * (left_rad_s + right_rad_s) / 2.0
    omega = WHEEL_RADIUS_M * (right_rad_s - left_rad_s) / AXLE_LENGTH_M
    return v, omega


def _sign(value: float, tolerance: float = 1e-12) -> int:
    return int(value > tolerance) - int(value < -tolerance)


def directional_control_diagnostic(
    held: VisualObstacle,
    current: VisualObstacle,
    cruise_rad_s: float,
    slowdown_threshold_m_s: float = 0.005,
    turn_threshold_rad_s: float = 0.10,
) -> DirectionalControlDiagnostic:
    """Decompose frozen-controller counterfactual control, including direction."""
    held_left, held_right = visual_wheel_command(held, cruise_rad_s)
    send_left, send_right = visual_wheel_command(current, cruise_rad_s)
    v_hold, omega_hold = wheel_kinematics(held_left, held_right)
    v_send, omega_send = wheel_kinematics(send_left, send_right)
    delta_v = v_send - v_hold
    delta_abs_turn = abs(omega_send) - abs(omega_hold)
    bearing = float(current.bearing_normalized or 0.0)
    # Camera bearing is positive to image-right.  Positive robot yaw is left,
    # so opposite signs mean the frozen controller turns toward the component.
    alignment = omega_send * bearing
    return DirectionalControlDiagnostic(
        held_left, held_right, send_left, send_right,
        v_hold, v_send, omega_hold, omega_send,
        delta_v, delta_abs_turn, send_left - held_left, send_right - held_right,
        _sign(omega_hold) != 0 and _sign(omega_send) != 0 and _sign(omega_hold) != _sign(omega_send),
        delta_v <= -abs(slowdown_threshold_m_s),
        delta_abs_turn >= abs(turn_threshold_rad_s),
        current.detected and abs(bearing) > 1e-12 and alignment < 0.0,
        current.detected and abs(bearing) > 1e-12 and alignment > 0.0,
    )


def _proximity(value: VisualObstacle) -> float:
    return float(value.apparent_proximity or value.proximity)


def _bbox_height(value: VisualObstacle) -> int:
    return 0 if value.bbox_xyxy is None else max(0, value.bbox_xyxy[3] - value.bbox_xyxy[1])


def _corridor_overlap(value: VisualObstacle, frame_width: int, corridor_fraction: float) -> float:
    if value.bbox_xyxy is None:
        return 0.0
    corridor_width = frame_width * corridor_fraction
    corridor_left = (frame_width - corridor_width) / 2.0
    corridor_right = corridor_left + corridor_width
    bbox_left, bbox_right = value.bbox_xyxy[0], value.bbox_xyxy[2]
    intersection = max(0.0, min(float(bbox_right), corridor_right) - max(float(bbox_left), corridor_left))
    return intersection / max(1.0, float(bbox_right - bbox_left))


def visual_safety_cue(
    held: VisualObstacle,
    current: VisualObstacle,
    elapsed_s: float,
    frame_size: tuple[int, int] = (160, 120),
    corridor_fraction: float = 0.30,
) -> VisualSafetyCue:
    """Measure interpretable held-to-current visual dynamics without ground truth."""
    if elapsed_s <= 0.0 or not math.isfinite(elapsed_s):
        raise ValueError("elapsed_s must be finite and positive")
    if not 0.0 < corridor_fraction <= 1.0:
        raise ValueError("invalid corridor fraction")
    held_bearing = abs(float(held.bearing_normalized or 0.0))
    current_bearing = abs(float(current.bearing_normalized or 0.0))
    convergence = (held_bearing - current_bearing) / elapsed_s
    held_proximity, current_proximity = _proximity(held), _proximity(current)
    proximity_growth = (current_proximity - held_proximity) / elapsed_s
    area_growth = (current.pixel_count - held.pixel_count) / elapsed_s
    relative_growth = (current.pixel_count - held.pixel_count) / max(held.pixel_count, 1) / elapsed_s
    bbox_growth = (_bbox_height(current) - _bbox_height(held)) / elapsed_s
    appearance = not held.detected and current.detected
    disappearance = held.detected and not current.detected
    overlap = _corridor_overlap(current, frame_size[0], corridor_fraction)
    return VisualSafetyCue(
        held.detected, current.detected, current_bearing, convergence,
        held.detected and current.detected and convergence > 0.0,
        current_proximity, proximity_growth, proximity_growth,
        current.pixel_count, area_growth, relative_growth,
        _bbox_height(current), bbox_growth,
        appearance, disappearance, current.component_count - held.component_count,
        overlap, appearance and overlap > 0.0,
    )
