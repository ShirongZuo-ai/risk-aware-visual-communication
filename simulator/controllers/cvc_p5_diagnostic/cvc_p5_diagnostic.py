"""Replay frozen P4 A0/A1 while measuring decoded held-versus-current value."""
from __future__ import annotations

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
from communication.cvc_p3_codec import P3HoldingReceiver, decode_p3_packet, encode_p3_packet
from communication.cvc_p4_allocator import ReserveSpec, SingleAdaptiveReserveAllocator
from communication.cvc_p5_diagnostics import control_sensitivity, diagnostic_dict, perception_novelty, visual_novelty

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


robot = Supervisor()
dt = int(robot.getBasicTimeStep())
cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
if cfg["policy"] not in ("A0", "A1"):
    raise ValueError("P5 diagnostic replays only frozen P4 A0/A1")
self_node = robot.getSelf()
self_node.getField("translation").setSFVec3f([*cfg["start"][:2], 0])
self_node.getField("rotation").setSFRotation([0, 0, 1, cfg["start"][2]])
self_node.resetPhysics()
children = robot.getFromDef("CVC_OBJECTS").getField("children")
for item in cfg["objects"]:
    children.importMFNodeFromString(-1, obstacle_vrml(item))
physical = [(item, robot.getFromDef(item["id"])) for item in cfg["objects"] if item.get("physical", True)]
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
allocator = SingleAdaptiveReserveAllocator(
    total_steps, ReserveSpec("fixed_late", threshold=float(cfg["threshold"]),
                             fixed_late_step=int(cfg["reserve_step"])))
receiver = P3HoldingReceiver()
previous_r0 = 0.0
has_previous = False
prior_received_image: Image.Image | None = None
prior_source_timestamp_ms: int | None = None
cumulative = 0
rows: list[dict] = []

if robot.step(dt) == -1:
    raise RuntimeError("Webots stopped before first camera frame")
for step in range(total_steps):
    now = int(round(robot.getTime() * 1000.0))
    raw = rgb_frame(camera)
    sender_obstacle = detect_red_obstacle(raw)
    r0 = sender_obstacle.proximity
    r1 = predictive_risk(r0, previous_r0, sender_obstacle.bearing_normalized) if has_previous else r0
    previous_r0, has_previous = r0, True
    selected_risk = r0 if policy == "A0" else r1
    decision = allocator.decide(step, selected_risk)

    shadow = encode_p3_packet(raw, now, selected_risk, policy, quality, packet_bytes)
    current_decoded, _ = decode_p3_packet(shadow.payload)
    if prior_received_image is None:
        held_decoded, held_age_ms = current_decoded.copy(), 0
    else:
        held_decoded = prior_received_image.copy()
        held_age_ms = now - int(prior_source_timestamp_ms)
    held_obstacle = detect_red_obstacle(held_decoded)
    current_obstacle = detect_red_obstacle(current_decoded)
    diagnostics = diagnostic_dict(
        visual_novelty(held_decoded, current_decoded, int(cfg["changed_pixel_threshold"])),
        perception_novelty(held_obstacle, current_obstacle, held_decoded.size),
        control_sensitivity(held_obstacle, current_obstacle, cruise),
    )

    packet = shadow.payload if decision.transmit else None
    content = shadow.content_bytes if decision.transmit else 0
    metadata = shadow.metadata_bytes if decision.transmit else 0
    padding = shadow.padding_bytes if decision.transmit else 0
    if packet is not None:
        cumulative += len(packet)
    received = receiver.step(now, packet)
    prior_received_image, prior_source_timestamp_ms = received.image.copy(), received.source_timestamp_ms
    detected = detect_red_obstacle(received.image)
    left_command, right_command = visual_wheel_command(detected, cruise)
    left.setVelocity(left_command)
    right.setVelocity(right_command)
    if robot.step(dt) == -1:
        break
    position = self_node.getPosition()
    clearances = []
    for item, node in physical:
        sx, sy = item.get("size", [0.08, 0.08])
        x, y = item["center"]
        dx = max(abs(position[0] - x) - sx / 2, 0)
        dy = max(abs(position[1] - y) - sy / 2, 0)
        clearances.append(math.hypot(dx, dy) - ROBOT_RADIUS_M)
    collision = any(node.getContactPoints(True) for _, node in physical) and bool(self_node.getContactPoints(True))
    rows.append({
        "step": step, "time_s": robot.getTime(), "scenario": cfg["scenario"], "policy": policy,
        "sender": {"r0": r0, "r1": r1, "selected_risk": selected_risk},
        "communication": {"transmitted": decision.transmit, "packet_role": decision.packet_role,
                          "reason": decision.reason, "trigger_event": decision.adaptive_trigger_event,
                          "reserve_locked": decision.reserve_locked, "tokens_before": decision.tokens_before,
                          "tokens_after": decision.tokens_after, "wire_bytes": len(packet) if packet else 0,
                          "content_bytes": content, "metadata_bytes": metadata, "padding_bytes": padding,
                          "cumulative_wire_bytes": cumulative},
        "counterfactual": {"held_source_timestamp_ms": prior_source_timestamp_ms if not decision.transmit else
                           (now - held_age_ms), "held_image_age_before_decision_ms": held_age_ms,
                           "shadow_wire_bytes": len(shadow.payload), "shadow_charged": False,
                           "held_perception": obstacle_dict(held_obstacle),
                           "current_perception": obstacle_dict(current_obstacle), **diagnostics},
        "receiver": {"image_age_ms": received.image_age_ms, "held": received.held},
        "perception": obstacle_dict(detected),
        "control": {"left_rad_s": left_command, "right_rad_s": right_command},
        "evaluator": {"x_m": position[0], "y_m": position[1],
                      "clearance_m": min(clearances), "collision": collision},
    })

out = Path(os.environ["CVC_OUTPUT"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
sends = [row for row in rows if row["communication"]["transmitted"]]
clearances = [row["evaluator"]["clearance_m"] for row in rows]
summary = {
    "development_only": True, "formal": False, "diagnostic_only": True,
    "scenario": cfg["scenario"], "policy": policy, "steps": len(rows),
    "transmissions": len(sends), "wire_bytes": cumulative,
    "send_steps": [row["step"] for row in sends],
    "adaptive_step": next(row["step"] for row in sends if row["communication"]["packet_role"] == "adaptive"),
    "reserve_step": next(row["step"] for row in sends if row["communication"]["packet_role"] == "reserve"),
    "collision": any(row["evaluator"]["collision"] for row in rows),
    "min_clearance_m": min(clearances), "mean_clearance_m": sum(clearances) / len(clearances),
    "final_x_m": rows[-1]["evaluator"]["x_m"], "final_y_m": rows[-1]["evaluator"]["y_m"],
    "forward_progress_m": rows[-1]["evaluator"]["x_m"] - cfg["start"][0],
    "shadow_packets_evaluated": len(rows), "shadow_packets_charged": 0,
}
out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
robot.simulationQuit(0)
