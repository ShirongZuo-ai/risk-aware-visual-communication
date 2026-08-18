"""Capture controlled range fixtures; geometry is calibration-only output."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image
from controller import Supervisor

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_perception import detect_red_obstacle


robot = Supervisor()
dt = int(robot.getBasicTimeStep())
camera = robot.getDevice("camera")
camera.enable(dt)
self_node = robot.getSelf()
distances = [0.18, 0.22, 0.26, 0.30, 0.36, 0.42, 0.50, 0.60, 0.72, 0.84]
rows = []
for distance in distances:
    self_node.getField("translation").setSFVec3f([-distance, 0.0, 0.0])
    self_node.getField("rotation").setSFRotation([0, 0, 1, 0])
    self_node.resetPhysics()
    for _ in range(4):
        if robot.step(dt) == -1:
            raise RuntimeError("Webots stopped during range calibration")
    image = Image.frombytes("RGBA", (camera.getWidth(), camera.getHeight()), camera.getImage(), "raw", "BGRA").convert("RGB")
    obstacle = detect_red_obstacle(image)
    height = 0 if obstacle.bbox_xyxy is None else obstacle.bbox_xyxy[3] - obstacle.bbox_xyxy[1]
    rows.append({"robot_to_obstacle_center_m": distance, "bbox_height_px": height,
                 "pixel_count": obstacle.pixel_count, "bearing": obstacle.bearing_normalized,
                 "detected": obstacle.detected})
out = Path(os.environ["CVC_OUTPUT"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"development_only": True, "formal": False, "rows": rows},
                          indent=2, sort_keys=True) + "\n", encoding="utf-8")
robot.simulationQuit(0)
