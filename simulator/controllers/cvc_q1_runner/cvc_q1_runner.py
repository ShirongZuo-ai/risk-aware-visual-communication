"""Webots adapter for the Q1 causal visual local planner."""
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

from communication.cvc_p2_perception import detect_red_obstacle
from communication.cvc_p3_codec import P3HoldingReceiver, decode_p3_packet, encode_p3_packet
from communication.cvc_q1_obstacle_memory import CausalObstacleMemory, Pose2D
from communication.cvc_q1_visual_geometry import VisualRangeCalibration, visual_obstacle_estimates
from navigation.cvc_q1_local_planner import action_id, compare_decisions, plan_local_action
from navigation.trajectory_prediction import normalize_angle


ROBOT_RADIUS_M = 0.037


def obstacle_vrml(item: dict) -> str:
    x, y = item["center"]
    sx, sy = item.get("size", [0.08, 0.08])
    color = item.get("color", [1, 0, 0])
    return f'''DEF {item["id"]} Solid {{ translation {x} {y} 0.04 children [ Shape {{ appearance PBRAppearance {{ baseColor {color[0]} {color[1]} {color[2]} roughness 0.7 }} geometry Box {{ size {sx} {sy} 0.08 }} }} ] boundingObject Box {{ size {sx} {sy} 0.08 }} locked TRUE }}'''


def rgb_frame(camera) -> Image.Image:
    return Image.frombytes("RGBA", (camera.getWidth(), camera.getHeight()), camera.getImage(), "raw", "BGRA").convert("RGB")


def uniform_schedule(total_steps: int, transmission_count: int) -> tuple[int, ...]:
    if not 1 <= transmission_count <= total_steps:
        raise ValueError("invalid transmission count")
    if transmission_count == 1:
        return (0,)
    return tuple(sorted({round(index * (total_steps - 1) / (transmission_count - 1))
                         for index in range(transmission_count)}))


def decision_dict(decision) -> dict:
    selected = decision.selected
    return {
        "selected_action_id": action_id(selected.action), "selected_action": asdict(selected.action),
        "selection_mode": decision.selection_mode, "selected_safety_class": selected.safety_class,
        "selected_conservative_margin_m": selected.conservative_min_clearance_m,
        "selected_goal_progress_m": selected.goal_progress_m,
        "selected_terminal_heading_error_rad": selected.terminal_heading_error_rad,
        "safe_action_ids": decision.safe_action_ids, "preferred_action_ids": decision.preferred_action_ids,
        "candidate_count": len(decision.evaluations),
        "candidates": [{"action_id": action_id(item.action), "action": asdict(item.action),
                        "safety_class": item.safety_class, "hard_feasible": item.hard_feasible,
                        "preferred_safe": item.preferred_safe,
                        "conservative_min_clearance_m": item.conservative_min_clearance_m,
                        "goal_progress_m": item.goal_progress_m,
                        "terminal_heading_error_rad": item.terminal_heading_error_rad,
                        "terminal": asdict(item.trajectory[-1])} for item in decision.evaluations],
        "selected_trajectory": [asdict(point) for point in selected.trajectory],
    }


robot = Supervisor()
dt_ms = int(robot.getBasicTimeStep())
dt_s = dt_ms / 1000.0
cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
out = Path(os.environ["CVC_OUTPUT"])
progress_path = out.with_suffix(".progress.json")
progress_path.parent.mkdir(parents=True, exist_ok=True)
progress_path.write_text(json.dumps({"state": "initialized", "step": -1}) + "\n", encoding="utf-8")
planner_cfg = cfg["planner"]
visual_cfg = cfg["visual_geometry"]
self_node = robot.getSelf()
self_node.getField("translation").setSFVec3f([*cfg["start"][:2], 0])
self_node.getField("rotation").setSFRotation([0, 0, 1, cfg["start"][2]])
self_node.resetPhysics()
children = robot.getFromDef("CVC_OBJECTS").getField("children")
for item in cfg["objects"]:
    children.importMFNodeFromString(-1, obstacle_vrml(item))
physical = [(item, robot.getFromDef(item["id"])) for item in cfg["objects"] if item.get("physical", True)]
camera = robot.getDevice("camera")
camera.enable(dt_ms)
left = robot.getDevice("left wheel motor")
right = robot.getDevice("right wheel motor")
left.setPosition(float("inf"))
right.setPosition(float("inf"))

calibration = VisualRangeCalibration(
    visual_cfg["inverse_height_coefficient_m_px"], visual_cfg["intercept_m"],
    visual_cfg["uncertainty_bound_m"])
total_steps = int(cfg["duration_s"] * 1000 / dt_ms)
schedule = tuple(range(total_steps)) if cfg["communication_mode"] == "HIGH" else uniform_schedule(
    total_steps, int(cfg["transmission_count"]))
receiver = P3HoldingReceiver()
obstacle_memory = CausalObstacleMemory(int(planner_cfg.get("obstacle_memory_steps", 1)))
prior_image: Image.Image | None = None
prior_timestamp: int | None = None
odom_x, odom_y, odom_yaw = cfg["start"]
pose_history: dict[int, Pose2D] = {}
step_by_timestamp: dict[int, int] = {}
rows = []
wire_total = content_total = metadata_total = padding_total = 0
path_length = 0.0
previous_xy = None

if robot.step(dt_ms) == -1:
    raise RuntimeError("Webots stopped before Q1 camera frame")
for step in range(total_steps):
    if step % 50 == 0:
        progress_path.write_text(json.dumps({"state": "running", "step": step}) + "\n", encoding="utf-8")
    now = int(round(robot.getTime() * 1000))
    raw = rgb_frame(camera)
    if step == 0:
        progress_path.write_text(json.dumps({"state": "frame", "step": step}) + "\n", encoding="utf-8")
    packet = encode_p3_packet(raw, now, 0.0, "U0",
                              int(cfg["jpeg_quality"]), int(cfg["packet_bytes"]))
    if step == 0:
        progress_path.write_text(json.dumps({"state": "encoded", "step": step}) + "\n", encoding="utf-8")
    current_image, _ = decode_p3_packet(packet.payload)
    held_image = current_image.copy() if prior_image is None else prior_image.copy()
    held_timestamp = now if prior_timestamp is None else prior_timestamp
    current_pose = Pose2D(odom_x, odom_y, odom_yaw)
    pose_history[now] = current_pose
    step_by_timestamp[now] = step
    goal_dx, goal_dy = cfg["goal"][0] - odom_x, cfg["goal"][1] - odom_y
    goal_bearing = normalize_angle(math.atan2(goal_dy, goal_dx) - odom_yaw)
    held_visual = detect_red_obstacle(held_image)
    current_visual = detect_red_obstacle(current_image)
    if step == 0:
        progress_path.write_text(json.dumps({"state": "detected", "step": step}) + "\n", encoding="utf-8")
    held_local = visual_obstacle_estimates(
        held_visual, calibration, camera_horizontal_fov_rad=visual_cfg["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual_cfg["known_obstacle_radius_m"])
    current_local = visual_obstacle_estimates(
        current_visual, calibration, camera_horizontal_fov_rad=visual_cfg["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual_cfg["known_obstacle_radius_m"])
    held_source_pose = pose_history.get(held_timestamp, current_pose)
    held_source_step = step_by_timestamp.get(held_timestamp, step)
    held_obstacles = obstacle_memory.preview(
        held_local, held_source_pose, held_source_step, current_pose, step)
    current_obstacles = obstacle_memory.preview(
        current_local, current_pose, step, current_pose, step)
    common = dict(horizon_s=planner_cfg["horizon_s"], step_s=planner_cfg["rollout_step_s"],
                  robot_radius_m=planner_cfg["robot_radius_m"],
                  hard_clearance_m=planner_cfg["hard_clearance_m"],
                  preferred_clearance_m=planner_cfg["preferred_clearance_m"],
                  near_slowdown_range_m=planner_cfg.get("near_slowdown_range_m"),
                  near_max_speed_m_s=planner_cfg.get("near_max_speed_m_s", .045))
    held_decision = plan_local_action(held_obstacles, goal_bearing, **common)
    current_decision = plan_local_action(current_obstacles, goal_bearing, **common)
    if step == 0:
        progress_path.write_text(json.dumps({"state": "counterfactual_planned", "step": step}) + "\n", encoding="utf-8")
    transmit = step in schedule
    payload = packet.payload if transmit else None
    received = receiver.step(now, payload)
    if transmit:
        wire_total += len(packet.payload)
        content_total += packet.content_bytes
        metadata_total += packet.metadata_bytes
        padding_total += packet.padding_bytes
    prior_image, prior_timestamp = received.image.copy(), received.source_timestamp_ms
    actual_visual = detect_red_obstacle(received.image)
    actual_local = visual_obstacle_estimates(
        actual_visual, calibration, camera_horizontal_fov_rad=visual_cfg["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual_cfg["known_obstacle_radius_m"])
    actual_source_pose = pose_history.get(received.source_timestamp_ms, current_pose)
    actual_source_step = step_by_timestamp.get(received.source_timestamp_ms, step)
    actual_obstacles = obstacle_memory.preview(
        actual_local, actual_source_pose, actual_source_step, current_pose, step)
    obstacle_memory.update(actual_local, actual_source_pose, actual_source_step)
    actual_decision = plan_local_action(actual_obstacles, goal_bearing, **common)
    if step == 0:
        progress_path.write_text(json.dumps({"state": "actual_planned", "step": step}) + "\n", encoding="utf-8")
    selected = actual_decision.selected
    left.setVelocity(selected.wheel_left_rad_s)
    right.setVelocity(selected.wheel_right_rad_s)
    # Causal commanded-motion odometry; no Webots pose enters the planner.
    if abs(selected.action.angular_rad_s) < 1e-12:
        odom_x += selected.action.linear_m_s * math.cos(odom_yaw) * dt_s
        odom_y += selected.action.linear_m_s * math.sin(odom_yaw) * dt_s
    else:
        next_yaw = odom_yaw + selected.action.angular_rad_s * dt_s
        radius = selected.action.linear_m_s / selected.action.angular_rad_s
        odom_x += radius * (math.sin(next_yaw) - math.sin(odom_yaw))
        odom_y -= radius * (math.cos(next_yaw) - math.cos(odom_yaw))
        odom_yaw = normalize_angle(next_yaw)
    if robot.step(dt_ms) == -1:
        break

    # Evaluator-only ground truth begins here, after the runtime action.
    position = self_node.getPosition()
    xy = (float(position[0]), float(position[1]))
    if previous_xy is not None:
        path_length += math.hypot(xy[0] - previous_xy[0], xy[1] - previous_xy[1])
    previous_xy = xy
    clearances = []
    for item, node in physical:
        sx, sy = item.get("size", [0.08, 0.08])
        x, y = item["center"]
        dx = max(abs(xy[0] - x) - sx / 2, 0)
        dy = max(abs(xy[1] - y) - sy / 2, 0)
        clearances.append(math.hypot(dx, dy) - ROBOT_RADIUS_M)
    clearance = min(clearances) if clearances else 10.0
    collision = bool(physical) and any(node.getContactPoints(True) for _, node in physical) and bool(self_node.getContactPoints(True))
    start_goal = math.hypot(cfg["goal"][0] - cfg["start"][0], cfg["goal"][1] - cfg["start"][1])
    remaining = math.hypot(cfg["goal"][0] - xy[0], cfg["goal"][1] - xy[1])
    rows.append({
        "step": step, "time_s": robot.getTime(), "scenario": cfg["scenario"],
        "communication": {"mode": cfg["communication_mode"], "transmitted": transmit,
                          "wire_bytes": len(packet.payload) if transmit else 0,
                          "content_bytes": packet.content_bytes if transmit else 0,
                          "metadata_bytes": packet.metadata_bytes if transmit else 0,
                          "padding_bytes": packet.padding_bytes if transmit else 0,
                          "cumulative_wire_bytes": wire_total, "image_age_ms": received.image_age_ms},
        "runtime": {"goal_bearing_rad": goal_bearing,
                    "odometry": {"x_m": odom_x, "y_m": odom_y, "yaw_rad": odom_yaw},
                    "detected_components": actual_visual.component_count,
                    "obstacle_memory_source_step": obstacle_memory.source_step,
                    "obstacles": [asdict(item) for item in actual_obstacles],
                    "planner": decision_dict(actual_decision),
                    "wheel_left_rad_s": selected.wheel_left_rad_s,
                    "wheel_right_rad_s": selected.wheel_right_rad_s},
        "counterfactual": {"held_source_timestamp_ms": held_timestamp,
                           "held_image_age_before_decision_ms": now - held_timestamp,
                           "held_obstacles": [asdict(item) for item in held_obstacles],
                           "current_obstacles": [asdict(item) for item in current_obstacles],
                           "held_planner": decision_dict(held_decision),
                           "current_planner": decision_dict(current_decision),
                           "decision_value": compare_decisions(held_decision, current_decision)},
        "evaluator": {"x_m": xy[0], "y_m": xy[1], "clearance_m": clearance,
                      "collision": collision, "contact": collision, "path_length_m": path_length,
                      "goal_progress_m": start_goal - remaining, "remaining_goal_distance_m": remaining},
    })

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
               encoding="utf-8")
summary = {
    "development_only": True, "formal": False, "scenario": cfg["scenario"],
    "semantic": cfg["semantic"], "seed": cfg["seed"], "communication_mode": cfg["communication_mode"],
    "transmission_count": len(schedule), "send_steps": list(schedule), "wire_bytes": wire_total,
    "content_bytes": content_total, "metadata_bytes": metadata_total, "padding_bytes": padding_total,
    "byte_reconciliation": content_total + metadata_total + padding_total == wire_total,
    "steps": len(rows), "collision": any(row["evaluator"]["collision"] for row in rows),
    "min_clearance_m": min(row["evaluator"]["clearance_m"] for row in rows),
    "mean_clearance_m": sum(row["evaluator"]["clearance_m"] for row in rows) / len(rows),
    "goal_progress_m": rows[-1]["evaluator"]["goal_progress_m"],
    "task_success": rows[-1]["evaluator"]["goal_progress_m"] >= 0.5 and not any(row["evaluator"]["collision"] for row in rows),
    "first_detected_step": next((row["step"] for row in rows if row["runtime"]["obstacles"]), None),
    "first_avoidance_step": next((row["step"] for row in rows
                                  if abs(row["runtime"]["planner"]["selected_action"]["angular_rad_s"]) > 1e-9), None),
    "decision_action_change_steps": sum(row["counterfactual"]["decision_value"]["action_changed"] for row in rows),
    "decision_safe_set_change_steps": sum(row["counterfactual"]["decision_value"]["safe_set_changed"] for row in rows),
}
out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
progress_path.write_text(json.dumps({"state": "complete", "step": len(rows) - 1}) + "\n", encoding="utf-8")
robot.simulationQuit(0)
