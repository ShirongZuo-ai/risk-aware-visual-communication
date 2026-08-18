"""CVC-P3 Webots loop for the frozen threshold actuation mechanism."""
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
from communication.cvc_p2_perception import detect_red_obstacle, visual_wheel_command
from communication.cvc_p3_allocator import AllocatorSpec, CausalRiskAllocator, uniform_schedule
from communication.cvc_p3_codec import P3HoldingReceiver, encode_p3_packet

ROBOT_RADIUS_M = 0.037


def rgb_frame(camera) -> Image.Image:
    return Image.frombytes("RGBA", (camera.getWidth(), camera.getHeight()), camera.getImage(), "raw", "BGRA").convert("RGB")


def obstacle_vrml(item: dict) -> str:
    x, y = item["center"]
    sx, sy = item.get("size", [0.08, 0.08])
    color = item.get("color", [1, 0, 0])
    return f'''DEF {item["id"]} Solid {{ translation {x} {y} 0.04 children [ Shape {{ appearance PBRAppearance {{ baseColor {color[0]} {color[1]} {color[2]} roughness 0.7 }} geometry Box {{ size {sx} {sy} 0.08 }} }} ] boundingObject Box {{ size {sx} {sy} 0.08 }} locked TRUE }}'''


robot = Supervisor()
dt = int(robot.getBasicTimeStep())
cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
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
transmissions = int(cfg["transmissions"])
packet_bytes = int(cfg["packet_bytes"])
policy = cfg["policy"]
quality = int(cfg["jpeg_quality"])
threshold = float(cfg["threshold"])
allocator = None if policy == "U0" else CausalRiskAllocator(
    total_steps, transmissions, AllocatorSpec("threshold", threshold=threshold, dt_s=dt / 1000.0)
)
uniform_steps = set(uniform_schedule(total_steps, transmissions))
receiver = P3HoldingReceiver()
previous_r0 = 0.0
has_previous = False
cumulative = 0
rows: list[dict] = []

if robot.step(dt) == -1:
    raise RuntimeError("Webots stopped before the first camera frame")
for step in range(total_steps):
    now = int(round(robot.getTime() * 1000.0))
    raw = rgb_frame(camera)
    sender_obstacle = detect_red_obstacle(raw)
    r0 = sender_obstacle.proximity
    r1 = predictive_risk(r0, previous_r0, sender_obstacle.bearing_normalized) if has_previous else r0
    previous_r0, has_previous = r0, True
    selected_risk = 0.0 if policy == "U0" else (r0 if policy == "A0" else r1)
    if policy == "U0":
        send = step in uniform_steps
        reason = "initial" if step == 0 else ("uniform" if send else "uniform_hold")
        trigger_event = False
        tokens_before = transmissions - sum(1 for prior in uniform_steps if prior < step)
        tokens_after = tokens_before - int(send)
    else:
        decision = allocator.decide(step, selected_risk)
        send, reason, trigger_event = decision.transmit, decision.reason, decision.trigger_event
        tokens_before, tokens_after = decision.tokens_before, decision.tokens_after
    packet = None
    content = metadata = padding = 0
    if send:
        encoded = encode_p3_packet(raw, now, selected_risk, policy, quality, packet_bytes)
        packet = encoded.payload
        content, metadata, padding = encoded.content_bytes, encoded.metadata_bytes, encoded.padding_bytes
        cumulative += len(packet)
    received = receiver.step(now, packet)
    detected = detect_red_obstacle(received.image)
    left_command, right_command = visual_wheel_command(detected, float(cfg["cruise_rad_s"]))
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
        "sender": {"r0": r0, "r1": r1, "selected_risk": selected_risk,
                   "bearing": sender_obstacle.bearing_normalized, "proximity": sender_obstacle.proximity},
        "communication": {"transmitted": send, "reason": reason, "trigger_event": trigger_event,
                          "wire_bytes": len(packet) if packet else 0, "content_bytes": content,
                          "metadata_bytes": metadata, "padding_bytes": padding,
                          "cumulative_wire_bytes": cumulative, "jpeg_quality": quality,
                          "tokens_before": tokens_before, "tokens_after": tokens_after},
        "receiver": {"image_age_ms": received.image_age_ms, "held": received.held},
        "perception": {"detected": detected.detected, "bearing": detected.bearing_normalized,
                       "proximity": detected.proximity, "pixels": detected.pixel_count,
                       "bbox_xyxy": detected.bbox_xyxy, "confidence": detected.confidence,
                       "component_count": detected.component_count},
        "control": {"left_rad_s": left_command, "right_rad_s": right_command},
        "evaluator": {"x_m": position[0], "y_m": position[1],
                      "clearance_m": min(clearances) if clearances else None, "collision": collision},
    })

out = Path(os.environ["CVC_OUTPUT"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
valid_clearance = [row["evaluator"]["clearance_m"] for row in rows if row["evaluator"]["clearance_m"] is not None]
ages = [row["receiver"]["image_age_ms"] for row in rows]
summary = {
    "development_only": True, "formal": False, "scenario": cfg["scenario"], "policy": policy,
    "steps": len(rows), "transmissions": sum(row["communication"]["transmitted"] for row in rows),
    "packet_bytes": packet_bytes, "wire_bytes": cumulative,
    "collision": any(row["evaluator"]["collision"] for row in rows),
    "min_clearance_m": min(valid_clearance), "mean_image_age_ms": sum(ages) / len(ages),
    "max_image_age_ms": max(ages),
    "detection_fraction": sum(row["perception"]["detected"] for row in rows) / len(rows),
    "final_x_m": rows[-1]["evaluator"]["x_m"], "final_y_m": rows[-1]["evaluator"]["y_m"],
    "forward_progress_m": rows[-1]["evaluator"]["x_m"] - cfg["start"][0],
    "send_steps": [row["step"] for row in rows if row["communication"]["transmitted"]],
    "send_reasons": [row["communication"]["reason"] for row in rows if row["communication"]["transmitted"]],
}
out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
robot.simulationQuit(0)
