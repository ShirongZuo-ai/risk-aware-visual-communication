"""Run unchanged P6-v1 U0/A0/A1 policies with additional P7 diagnostics."""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image
from controller import Supervisor

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_protocol import predictive_risk
from communication.cvc_p2_perception import VisualObstacle, detect_red_obstacle, visual_wheel_command
from communication.cvc_p3_codec import decode_p3_packet, encode_p3_packet
from communication.cvc_p5_diagnostics import control_sensitivity, diagnostic_dict, perception_novelty, visual_novelty
from communication.cvc_p6_allocator import (
    MirroredHoldingChannel,
    NoveltyThresholds,
    P6Decision,
    RiskArmedNoveltyAllocator,
    image_sha256,
    novelty_event,
    task_novelty,
)
from communication.cvc_p7_diagnostics import directional_control_diagnostic, visual_safety_cue


ROBOT_RADIUS_M = 0.037


def rgb_frame(camera) -> Image.Image:
    return Image.frombytes("RGBA", (camera.getWidth(), camera.getHeight()), camera.getImage(), "raw", "BGRA").convert("RGB")


def obstacle_vrml(item: dict) -> str:
    x, y = item["center"]
    sx, sy = item.get("size", [0.08, 0.08])
    color = item.get("color", [1, 0, 0])
    return f'''DEF {item["id"]} Solid {{ translation {x} {y} 0.04 children [ Shape {{ appearance PBRAppearance {{ baseColor {color[0]} {color[1]} {color[2]} roughness 0.7 }} geometry Box {{ size {sx} {sy} 0.08 }} }} ] boundingObject Box {{ size {sx} {sy} 0.08 }} locked TRUE }}'''


def obstacle_dict(value: VisualObstacle) -> dict:
    return {"detected": value.detected, "bearing": value.bearing_normalized,
            "proximity": value.apparent_proximity or value.proximity, "confidence": value.confidence,
            "centroid_xy": value.centroid_xy, "bbox_xyxy": value.bbox_xyxy,
            "component_count": value.component_count, "pixel_count": value.pixel_count}


def uniform_decision(step: int, schedule: tuple[int, int, int], novelty_triggered: bool,
                     novelty_reasons: tuple[str, ...]) -> P6Decision:
    send = step in schedule
    if step == schedule[0]:
        role, reason, state = "startup", "fixed_startup", "NORMAL"
    elif step == schedule[1]:
        role, reason, state = "adaptive", "fixed_uniform", "SPENT"
    elif step == schedule[2]:
        role, reason, state = "reserve", "fixed_reserve", "RESERVE"
    else:
        role, reason = "hold", "fixed_hold"
        state = "NORMAL" if step < schedule[1] else ("SPENT" if step < schedule[2] else "RESERVE")
    sent_before = sum(value < step for value in schedule)
    return P6Decision(send, role, reason, state, False, None, None,
                      novelty_triggered, novelty_reasons, False, step < schedule[2],
                      3 - sent_before, 3 - sent_before - int(send))


robot = Supervisor()
dt = int(robot.getBasicTimeStep())
cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
if cfg["policy"] not in ("U0", "A0", "A1"):
    raise ValueError("P7 comparison supports only frozen P6 U0/A0/A1")
self_node = robot.getSelf()
self_node.getField("translation").setSFVec3f([*cfg["start"][:2], 0])
self_node.getField("rotation").setSFRotation([0, 0, 1, cfg["start"][2]])
self_node.resetPhysics()
children = robot.getFromDef("CVC_OBJECTS").getField("children")
for item in cfg["objects"]:
    children.importMFNodeFromString(-1, obstacle_vrml(item))
physical = [(item, robot.getFromDef(item["id"])) for item in cfg["objects"] if item.get("physical", True)]
if not physical:
    raise RuntimeError("P7 evaluator requires at least one physical reference object")
camera = robot.getDevice("camera")
camera.enable(dt)
left = robot.getDevice("left wheel motor")
right = robot.getDevice("right wheel motor")
left.setPosition(float("inf"))
right.setPosition(float("inf"))

total_steps = int(cfg["duration_s"] * 1000 / dt)
policy = cfg["policy"]
packet_bytes = int(cfg["packet_bytes"])
quality = int(cfg["jpeg_quality"])
cruise = float(cfg["cruise_rad_s"])
thresholds = NoveltyThresholds(**cfg["novelty_thresholds"])
diagnostic_thresholds = cfg["diagnostic_thresholds"]
allocator = None if policy == "U0" else RiskArmedNoveltyAllocator(
    total_steps, float(cfg["risk_threshold"]), int(cfg["deadline_steps"]),
    int(cfg["reserve_step"]), thresholds)
u0_schedule = tuple(int(value) for value in cfg["u0_schedule"])
channel = MirroredHoldingChannel()
previous_r0 = 0.0
has_previous = False
prior_mirror_image: Image.Image | None = None
prior_mirror_timestamp_ms: int | None = None
cumulative = 0
content_total = metadata_total = padding_total = 0
rows: list[dict] = []
path_length = 0.0
previous_position: tuple[float, float] | None = None
completion_step: int | None = None

if robot.step(dt) == -1:
    raise RuntimeError("Webots stopped before first camera frame")
for step in range(total_steps):
    now = int(round(robot.getTime() * 1000.0))
    raw = rgb_frame(camera)
    sender_obstacle = detect_red_obstacle(raw)
    r0 = sender_obstacle.proximity
    r1 = predictive_risk(r0, previous_r0, sender_obstacle.bearing_normalized) if has_previous else r0
    previous_r0, has_previous = r0, True
    selected_risk = r0 if policy in ("U0", "A0") else r1
    shadow = encode_p3_packet(raw, now, selected_risk, policy, quality, packet_bytes)
    current_decoded, _ = decode_p3_packet(shadow.payload)
    if prior_mirror_image is None:
        held_decoded, held_age_ms, held_timestamp = current_decoded.copy(), 0, now
    else:
        held_decoded = prior_mirror_image.copy()
        held_timestamp = int(prior_mirror_timestamp_ms)
        held_age_ms = now - held_timestamp
    held_obstacle = detect_red_obstacle(held_decoded)
    current_obstacle = detect_red_obstacle(current_decoded)
    novelty = task_novelty(held_obstacle, current_obstacle, held_decoded.size)
    event = novelty_event(novelty, thresholds)
    decision = (uniform_decision(step, u0_schedule, event.triggered, event.reasons) if allocator is None
                else allocator.decide(step, selected_risk, novelty))
    diagnostics = diagnostic_dict(
        visual_novelty(held_decoded, current_decoded, int(cfg["changed_pixel_threshold"])),
        perception_novelty(held_obstacle, current_obstacle, held_decoded.size),
        control_sensitivity(held_obstacle, current_obstacle, cruise),
    )
    elapsed_s = max(dt / 1000.0, held_age_ms / 1000.0)
    directional = directional_control_diagnostic(
        held_obstacle, current_obstacle, cruise,
        float(diagnostic_thresholds["slowdown_m_s"]),
        float(diagnostic_thresholds["increased_turn_rad_s"]),
    )
    safety_cue = visual_safety_cue(
        held_obstacle, current_obstacle, elapsed_s, held_decoded.size,
        float(diagnostic_thresholds["forward_corridor_fraction"]),
    )
    packet = shadow.payload if decision.transmit else None
    if packet is not None:
        cumulative += len(packet)
        content_total += shadow.content_bytes
        metadata_total += shadow.metadata_bytes
        padding_total += shadow.padding_bytes
    received, mirrored = channel.step(now, packet)
    if image_sha256(received.image) != image_sha256(mirrored.image):
        raise RuntimeError("held mirror identity mismatch")
    prior_mirror_image, prior_mirror_timestamp_ms = mirrored.image.copy(), mirrored.source_timestamp_ms
    detected = detect_red_obstacle(received.image)
    left_command, right_command = visual_wheel_command(detected, cruise)
    left.setVelocity(left_command)
    right.setVelocity(right_command)
    if robot.step(dt) == -1:
        break

    # Evaluator-only block starts after sender, decision, receive, perception,
    # and control.  None of these values can feed the policy or controller.
    position = self_node.getPosition()
    xy = (float(position[0]), float(position[1]))
    if previous_position is not None:
        path_length += math.hypot(xy[0] - previous_position[0], xy[1] - previous_position[1])
    previous_position = xy
    forward_progress = xy[0] - float(cfg["start"][0])
    if completion_step is None and forward_progress >= 0.5:
        completion_step = step
    clearances = []
    for item, node in physical:
        sx, sy = item.get("size", [0.08, 0.08])
        x, y = item["center"]
        dx = max(abs(xy[0] - x) - sx / 2, 0)
        dy = max(abs(xy[1] - y) - sy / 2, 0)
        clearances.append(math.hypot(dx, dy) - ROBOT_RADIUS_M)
    collision = any(node.getContactPoints(True) for _, node in physical) and bool(self_node.getContactPoints(True))
    rows.append({
        "step": step, "time_s": robot.getTime(), "scenario": cfg["scenario"], "policy": policy,
        "sender": {"r0": r0, "r1": r1, "selected_risk": selected_risk},
        "policy_state": {"state": decision.state, "arm_step": decision.arm_step,
                         "arm_reason": decision.arm_reason, "armed_this_step": decision.armed_this_step,
                         "deadline_due": decision.deadline_due},
        "task_novelty": {**asdict(novelty), "event": decision.novelty_event,
                         "event_reasons": decision.novelty_reasons, "thresholds": asdict(thresholds)},
        "visual_safety_cue": asdict(safety_cue),
        "directional_control": asdict(directional),
        "communication": {"transmitted": decision.transmit, "packet_role": decision.packet_role,
                          "reason": decision.reason, "reserve_locked": decision.reserve_locked,
                          "tokens_before": decision.tokens_before, "tokens_after": decision.tokens_after,
                          "wire_bytes": len(packet) if packet else 0,
                          "content_bytes": shadow.content_bytes if packet else 0,
                          "metadata_bytes": shadow.metadata_bytes if packet else 0,
                          "padding_bytes": shadow.padding_bytes if packet else 0,
                          "cumulative_wire_bytes": cumulative},
        "counterfactual": {"held_source_timestamp_ms": held_timestamp,
                           "held_image_age_before_decision_ms": held_age_ms,
                           "held_image_sha256": image_sha256(held_decoded),
                           "current_image_sha256": image_sha256(current_decoded),
                           "held_perception": obstacle_dict(held_obstacle),
                           "current_perception": obstacle_dict(current_obstacle), **diagnostics},
        "receiver": {"image_age_ms": received.image_age_ms, "held": received.held,
                     "source_timestamp_ms": received.source_timestamp_ms,
                     "image_sha256": image_sha256(received.image),
                     "mirror_image_sha256": image_sha256(mirrored.image), "mirror_match": True},
        "perception": obstacle_dict(detected),
        "control": {"left_rad_s": left_command, "right_rad_s": right_command},
        "evaluator": {"category": cfg["category"], "seed": cfg["seed"],
                      "x_m": xy[0], "y_m": xy[1], "forward_progress_m": forward_progress,
                      "path_length_m": path_length, "clearance_m": min(clearances),
                      "collision": collision, "contact": collision},
    })

out = Path(os.environ["CVC_OUTPUT"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
               encoding="utf-8")
sends = [row for row in rows if row["communication"]["transmitted"]]
clearances = [row["evaluator"]["clearance_m"] for row in rows]
collided = any(row["evaluator"]["collision"] for row in rows)
forward_progress = rows[-1]["evaluator"]["forward_progress_m"]
summary = {
    "development_only": True, "formal": False, "scenario": cfg["scenario"],
    "category": cfg["category"], "seed": cfg["seed"], "policy": policy,
    "steps": len(rows), "transmissions": len(sends), "wire_bytes": cumulative,
    "content_bytes": content_total, "metadata_bytes": metadata_total, "padding_bytes": padding_total,
    "byte_reconciliation": content_total + metadata_total + padding_total == cumulative,
    "send_steps": [row["step"] for row in sends],
    "packet_roles": [row["communication"]["packet_role"] for row in sends],
    "arm_step": next((row["policy_state"]["arm_step"] for row in rows
                      if row["policy_state"]["arm_step"] is not None), None),
    "adaptive_step": next(row["step"] for row in sends if row["communication"]["packet_role"] == "adaptive"),
    "adaptive_reason": next(row["communication"]["reason"] for row in sends
                            if row["communication"]["packet_role"] == "adaptive"),
    "reserve_step": next(row["step"] for row in sends if row["communication"]["packet_role"] == "reserve"),
    "budget_exhaustion_step": sends[-1]["step"],
    "deadline_used": any(row["communication"]["reason"] == "arm_deadline" for row in rows),
    "unarmed_fallback_used": any(row["communication"]["reason"] == "unarmed_fallback" for row in rows),
    "mirror_all_steps_match": all(row["receiver"]["mirror_match"] for row in rows),
    "collision": collided, "task_success": (not collided and forward_progress >= 0.5),
    "min_clearance_m": min(clearances), "mean_clearance_m": sum(clearances) / len(clearances),
    "final_x_m": rows[-1]["evaluator"]["x_m"], "final_y_m": rows[-1]["evaluator"]["y_m"],
    "forward_progress_m": forward_progress, "completion_step": completion_step,
    "completion_time_s": (completion_step + 1) * dt / 1000 if completion_step is not None else None,
    "path_length_m": rows[-1]["evaluator"]["path_length_m"],
}
out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
robot.simulationQuit(0)
