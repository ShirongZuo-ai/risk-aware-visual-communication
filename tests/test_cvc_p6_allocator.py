from __future__ import annotations

import inspect

from PIL import Image

from communication.cvc_p2_perception import VisualObstacle
from communication.cvc_p3_codec import encode_p3_packet
from communication.cvc_p6_allocator import (
    MirroredHoldingChannel,
    NoveltyThresholds,
    RiskArmedNoveltyAllocator,
    novelty_event,
    task_novelty,
)


THRESHOLDS = NoveltyThresholds(0.1, 0.05, 0.4)


def obstacle(bearing: float = 0.0, proximity: float = 0.1, pixels: int = 480,
             detected: bool = True) -> VisualObstacle:
    return VisualObstacle(detected, bearing if detected else None, proximity if detected else 0.0,
                          (60, 40, 100, 70) if detected else None, pixels if detected else 0,
                          (80.0, 55.0) if detected else None, int(detected), 1.0 if detected else 0.0,
                          proximity if detected else 0.0)


def test_normal_arms_without_immediate_send_when_novelty_is_below_threshold() -> None:
    allocator = RiskArmedNoveltyAllocator(437, 0.14, 96, 218, THRESHOLDS)
    quiet = task_novelty(obstacle(), obstacle(0.01, 0.11, 500))
    allocator.decide(0, 0.10, quiet)
    decision = allocator.decide(1, 0.15, quiet)
    assert decision.armed_this_step and decision.state == "ARMED"
    assert not decision.transmit and decision.reason == "armed_wait"


def test_novelty_event_causes_adaptive_spend_after_arm() -> None:
    allocator = RiskArmedNoveltyAllocator(437, 0.14, 96, 218, THRESHOLDS)
    quiet = task_novelty(obstacle(), obstacle())
    allocator.decide(0, 0.10, quiet)
    allocator.decide(1, 0.15, quiet)
    event = task_novelty(obstacle(), obstacle(0.2, 0.1, 480))
    decision = allocator.decide(2, 0.16, event)
    assert novelty_event(event, THRESHOLDS).reasons == ("bearing",)
    assert decision.transmit and decision.packet_role == "adaptive"
    assert decision.reason == "task_novelty" and decision.state == "SPENT"


def test_deadline_fallback_and_protected_reserve() -> None:
    allocator = RiskArmedNoveltyAllocator(437, 0.14, 3, 8, THRESHOLDS)
    quiet = task_novelty(obstacle(), obstacle())
    decisions = [allocator.decide(step, 0.10 if step == 0 else 0.15, quiet) for step in range(9)]
    sends = [step for step, decision in enumerate(decisions) if decision.transmit]
    assert sends == [0, 4, 8]
    assert decisions[4].reason == "arm_deadline"
    assert decisions[8].packet_role == "reserve" and decisions[8].tokens_after == 0


def test_unarmed_fallback_preserves_exact_packet_count() -> None:
    allocator = RiskArmedNoveltyAllocator(12, 0.14, 3, 8, THRESHOLDS)
    quiet = task_novelty(obstacle(), obstacle())
    decisions = [allocator.decide(step, 0.10, quiet) for step in range(9)]
    sends = [decision for decision in decisions if decision.transmit]
    assert [decision.packet_role for decision in sends] == ["startup", "adaptive", "reserve"]
    assert sends[1].reason == "unarmed_fallback"


def test_receiver_held_mirror_matches_receiver_exactly() -> None:
    channel = MirroredHoldingChannel()
    image = Image.new("RGB", (160, 120), (40, 50, 60))
    packet = encode_p3_packet(image, 32, 0.1, "A1", 45, 24000).payload
    received, mirrored = channel.step(32, packet)
    assert received.image.tobytes() == mirrored.image.tobytes()
    received_hold, mirrored_hold = channel.step(64, None)
    assert received_hold.image.tobytes() == mirrored_hold.image.tobytes()
    assert received_hold.image_age_ms == mirrored_hold.image_age_ms == 32


def test_r0_r1_share_one_allocator_implementation_and_no_evaluator_dependency() -> None:
    source = inspect.getsource(RiskArmedNoveltyAllocator)
    assert "evaluator" not in source and "clearance" not in source and "collision" not in source
    assert "A0" not in source and "A1" not in source


def test_exact_wire_reconciliation_with_three_real_packets() -> None:
    image = Image.new("RGB", (160, 120), (80, 90, 100))
    packets = [encode_p3_packet(image, step * 32, 0.2, "A0", 45, 24000).payload
               for step in (0, 50, 218)]
    assert len(packets) == 3 and sum(map(len, packets)) == 72000
