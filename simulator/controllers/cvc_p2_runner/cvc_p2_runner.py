"""Webots CVC-P2 development runner: camera -> wire -> decoded pixels -> control."""
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

from communication.cvc_p2_protocol import ExactQuotaScheduler, predictive_risk, spatial_qualities
from communication.cvc_p2_perception import detect_red_obstacle, visual_wheel_command
from communication.cvc_protocol import AllocationDecision, HoldingReceiver, SenderObservation, encode_packet

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

total_steps = int(cfg.get("duration_s", 10.0) * 1000 / dt)
quota = int(cfg["transmissions"])
mechanism = cfg["mechanism"]
risk_signal = cfg["risk_signal"]
scheduler = ExactQuotaScheduler(total_steps, quota, mechanism in ("T", "TS"))
receiver = HoldingReceiver()
target_bytes = int(cfg.get("packet_bytes", 36000))
previous_r0 = 0.0
has_previous_r0 = False
cumulative = 0
rows: list[dict] = []

if robot.step(dt) == -1:
    raise RuntimeError("Webots stopped before the first camera frame")
for step in range(total_steps):
    now = int(round(robot.getTime() * 1000.0))
    raw = rgb_frame(camera)
    sender_obstacle = detect_red_obstacle(raw)
    r0 = sender_obstacle.proximity
    r1 = predictive_risk(r0, previous_r0, sender_obstacle.bearing_normalized) if has_previous_r0 else r0
    previous_r0 = r0
    has_previous_r0 = True
    risk = 0.0 if risk_signal == "NONE" else (r0 if risk_signal == "R0" else r1)
    send, send_reason = scheduler.decide(step, risk)
    qualities, roi = spatial_qualities(raw, mechanism, risk)
    packet = None
    content = metadata = padding = 0
    if send:
        decision = AllocationDecision("U0", True, qualities, target_bytes)
        encoded = encode_packet(SenderObservation(now, raw, risk), decision)
        packet = encoded.payload
        content, metadata, padding = encoded.content_bytes, encoded.metadata_bytes, encoded.padding_bytes
        cumulative += len(packet)
    received = receiver.step(now, packet)
    detected = detect_red_obstacle(received.image)
    left_command, right_command = visual_wheel_command(detected, float(cfg.get("cruise_rad_s", 4.2)))
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
        "step": step, "time_s": robot.getTime(), "scenario": cfg["scenario"],
        "mechanism": mechanism, "risk_signal": risk_signal,
        "sender": {"r0": r0, "r1": r1, "selected_risk": risk,
                   "bearing": sender_obstacle.bearing_normalized, "proximity": sender_obstacle.proximity},
        "communication": {"transmitted": send, "reason": send_reason, "wire_bytes": len(packet) if packet else 0,
                          "content_bytes": content, "metadata_bytes": metadata, "padding_bytes": padding,
                          "cumulative_wire_bytes": cumulative, "roi_tile_ids": list(roi),
                          "quality_min": min(qualities), "quality_max": max(qualities)},
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
detections = [row["perception"]["detected"] for row in rows]
summary = {
    "development_only": True, "scenario": cfg["scenario"], "mechanism": mechanism,
    "risk_signal": risk_signal, "steps": len(rows), "transmissions": scheduler.sent,
    "packet_bytes": target_bytes, "wire_bytes": cumulative,
    "collision": any(row["evaluator"]["collision"] for row in rows),
    "min_clearance_m": min(valid_clearance) if valid_clearance else None,
    "mean_image_age_ms": sum(ages) / len(ages), "max_image_age_ms": max(ages),
    "detection_fraction": sum(detections) / len(detections),
    "final_x_m": rows[-1]["evaluator"]["x_m"], "final_y_m": rows[-1]["evaluator"]["y_m"],
    "forward_progress_m": rows[-1]["evaluator"]["x_m"] - cfg["start"][0],
}
out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
robot.simulationQuit(0)
