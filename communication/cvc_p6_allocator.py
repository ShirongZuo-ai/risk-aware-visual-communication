"""Causal CVC-P6 risk-arm/task-novelty-spend primitives."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

from PIL import Image

from communication.cvc_p2_perception import VisualObstacle
from communication.cvc_p3_codec import P3HoldingReceiver, P3ReceivedFrame


@dataclass(frozen=True)
class NoveltyThresholds:
    bearing: float
    proximity: float
    area_relative: float

    def __post_init__(self) -> None:
        if not 0.0 < self.bearing <= 2.0:
            raise ValueError("invalid bearing novelty threshold")
        if not 0.0 < self.proximity <= 1.0:
            raise ValueError("invalid proximity novelty threshold")
        if not 0.0 < self.area_relative <= 1.0:
            raise ValueError("invalid area novelty threshold")


@dataclass(frozen=True)
class TaskNovelty:
    delta_bearing: float
    delta_proximity: float
    delta_area_relative: float
    component_event: bool
    component_count_delta: int
    centroid_distance_normalized: float
    bbox_one_minus_iou: float


@dataclass(frozen=True)
class NoveltyEvent:
    triggered: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class P6Decision:
    transmit: bool
    packet_role: str
    reason: str
    state: str
    armed_this_step: bool
    arm_step: int | None
    arm_reason: str | None
    novelty_event: bool
    novelty_reasons: tuple[str, ...]
    deadline_due: bool
    reserve_locked: bool
    tokens_before: int
    tokens_after: int


def _bbox_iou(left: tuple[int, int, int, int] | None,
              right: tuple[int, int, int, int] | None) -> float:
    if left is None and right is None:
        return 1.0
    if left is None or right is None:
        return 0.0
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 1.0


def task_novelty(held: VisualObstacle, current: VisualObstacle,
                 frame_size: tuple[int, int] = (160, 120)) -> TaskNovelty:
    held_bearing = float(held.bearing_normalized or 0.0)
    current_bearing = float(current.bearing_normalized or 0.0)
    held_proximity = float(held.apparent_proximity or held.proximity)
    current_proximity = float(current.apparent_proximity or current.proximity)
    area_denominator = max(held.pixel_count, current.pixel_count, 1)
    area_relative = abs(current.pixel_count - held.pixel_count) / area_denominator
    component_event = held.detected != current.detected
    if held.centroid_xy is None and current.centroid_xy is None:
        centroid = 0.0
    elif held.centroid_xy is None or current.centroid_xy is None:
        centroid = 1.0
    else:
        centroid = math.hypot(held.centroid_xy[0] - current.centroid_xy[0],
                              held.centroid_xy[1] - current.centroid_xy[1]) / math.hypot(*frame_size)
    return TaskNovelty(
        delta_bearing=abs(current_bearing - held_bearing),
        delta_proximity=abs(current_proximity - held_proximity),
        delta_area_relative=area_relative,
        component_event=component_event,
        component_count_delta=abs(current.component_count - held.component_count),
        centroid_distance_normalized=centroid,
        bbox_one_minus_iou=1.0 - _bbox_iou(held.bbox_xyxy, current.bbox_xyxy),
    )


def novelty_event(value: TaskNovelty, thresholds: NoveltyThresholds) -> NoveltyEvent:
    reasons: list[str] = []
    if value.component_event:
        reasons.append("component_event")
    if value.delta_bearing > thresholds.bearing:
        reasons.append("bearing")
    if value.delta_proximity > thresholds.proximity:
        reasons.append("proximity")
    if value.delta_area_relative > thresholds.area_relative:
        reasons.append("area_relative")
    return NoveltyEvent(bool(reasons), tuple(reasons))


class RiskArmedNoveltyAllocator:
    """Startup, one risk-armed novelty/deadline spend, and fixed protected reserve."""

    def __init__(self, total_steps: int, risk_threshold: float, deadline_steps: int,
                 reserve_step: int, thresholds: NoveltyThresholds) -> None:
        if total_steps <= reserve_step or not 1 <= deadline_steps < reserve_step:
            raise ValueError("invalid P6 timing")
        if not 0.0 < risk_threshold < 1.0:
            raise ValueError("invalid risk threshold")
        self.total_steps = total_steps
        self.risk_threshold = risk_threshold
        self.deadline_steps = deadline_steps
        self.reserve_step = reserve_step
        self.thresholds = thresholds
        self.adaptive_fallback_step = reserve_step - 1
        self.previous_risk: float | None = None
        self.arm_step: int | None = None
        self.arm_reason: str | None = None
        self.adaptive_step: int | None = None
        self.sent = 0
        self.last_step = -1

    def decide(self, step: int, risk: float, novelty: TaskNovelty) -> P6Decision:
        if step != self.last_step + 1 or not 0 <= step < self.total_steps:
            raise ValueError("steps must be consecutive and in range")
        if not 0.0 <= risk <= 1.0:
            raise ValueError("risk must be in [0,1]")
        self.last_step = step
        crossing = self.previous_risk is not None and self.previous_risk < self.risk_threshold <= risk
        self.previous_risk = risk
        armed_this_step = False
        if self.arm_step is None and crossing and self.adaptive_step is None:
            self.arm_step, self.arm_reason, armed_this_step = step, "risk_crossing", True
        event = novelty_event(novelty, self.thresholds)
        deadline_due = (self.arm_step is not None and self.adaptive_step is None and
                        step - self.arm_step >= self.deadline_steps)
        before = 3 - self.sent
        if step == 0:
            transmit, role, reason = True, "startup", "initial"
        elif self.adaptive_step is None and self.arm_step is not None and event.triggered:
            transmit, role, reason = True, "adaptive", "task_novelty"
            self.adaptive_step = step
        elif self.adaptive_step is None and deadline_due:
            transmit, role, reason = True, "adaptive", "arm_deadline"
            self.adaptive_step = step
        elif self.adaptive_step is None and step == self.adaptive_fallback_step:
            transmit, role, reason = True, "adaptive", "unarmed_fallback"
            self.adaptive_step = step
        elif step == self.reserve_step:
            if self.adaptive_step is None:
                raise RuntimeError("adaptive packet missing before protected reserve")
            transmit, role, reason = True, "reserve", "reserve_fixed_late"
        else:
            transmit, role = False, "hold"
            reason = "normal_hold" if self.arm_step is None else ("armed_wait" if self.adaptive_step is None else "spent_hold")
        if transmit:
            self.sent += 1
        if step >= self.reserve_step:
            state = "RESERVE"
        elif self.adaptive_step is not None:
            state = "SPENT"
        elif self.arm_step is not None:
            state = "ARMED"
        else:
            state = "NORMAL"
        return P6Decision(
            transmit, role, reason, state, armed_this_step, self.arm_step, self.arm_reason,
            event.triggered, event.reasons, deadline_due, step < self.reserve_step,
            before, 3 - self.sent,
        )


def image_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


class MirroredHoldingChannel:
    """Independent receiver and sender mirror; divergence is a hard error."""

    def __init__(self) -> None:
        self.receiver = P3HoldingReceiver()
        self.sender_mirror = P3HoldingReceiver()

    def step(self, now_ms: int, payload: bytes | None) -> tuple[P3ReceivedFrame, P3ReceivedFrame]:
        received = self.receiver.step(now_ms, payload)
        mirrored = self.sender_mirror.step(now_ms, payload)
        if (received.source_timestamp_ms != mirrored.source_timestamp_ms or
                received.image_age_ms != mirrored.image_age_ms or
                received.wire_bytes != mirrored.wire_bytes or
                received.held != mirrored.held or
                image_sha256(received.image) != image_sha256(mirrored.image)):
            raise RuntimeError("sender-held mirror diverged from receiver")
        return received, mirrored
