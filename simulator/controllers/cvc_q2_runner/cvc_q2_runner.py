"""Webots adapter for frozen CVC-Q2 Risk-ARM/Safety-Value-SPEND development."""
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
from communication.cvc_p2_protocol import predictive_risk
from communication.cvc_p3_codec import decode_p3_packet, encode_p3_packet
from communication.cvc_p6_allocator import MirroredHoldingChannel, image_sha256
from communication.cvc_q1_obstacle_memory import CausalObstacleMemory, Pose2D
from communication.cvc_q1_visual_geometry import VisualRangeCalibration, visual_obstacle_estimates
from communication.cvc_q2_allocator import (
    Q2Decision, RiskArmedSafetyValueAllocator, SafetyValueThresholds,
    evaluate_safety_decision_value,
)
from navigation.cvc_q1_local_planner import action_id, plan_local_action
from navigation.trajectory_prediction import normalize_angle


ROBOT_RADIUS_M = 0.037


def obstacle_vrml(item: dict) -> str:
    x, y = item["center"]
    sx, sy = item.get("size", [0.08, 0.08])
    color = item.get("color", [1, 0, 0])
    return f'''DEF {item["id"]} Solid {{ translation {x} {y} 0.04 children [ Shape {{ appearance PBRAppearance {{ baseColor {color[0]} {color[1]} {color[2]} roughness 0.7 }} geometry Box {{ size {sx} {sy} 0.08 }} }} ] boundingObject Box {{ size {sx} {sy} 0.08 }} locked TRUE }}'''


def rgb_frame(camera) -> Image.Image:
    return Image.frombytes("RGBA", (camera.getWidth(), camera.getHeight()), camera.getImage(), "raw", "BGRA").convert("RGB")


def decision_dict(decision) -> dict:
    selected = decision.selected
    return {
        "selected_action_id": action_id(selected.action), "selected_action": asdict(selected.action),
        "selection_mode": decision.selection_mode, "selected_safety_class": selected.safety_class,
        "selected_conservative_margin_m": selected.conservative_min_clearance_m,
        "selected_goal_progress_m": selected.goal_progress_m,
        "safe_action_ids": decision.safe_action_ids, "preferred_action_ids": decision.preferred_action_ids,
        "candidate_count": len(decision.evaluations),
        "candidates": [{"action_id": action_id(item.action), "action": asdict(item.action),
                        "safety_class": item.safety_class, "hard_feasible": item.hard_feasible,
                        "preferred_safe": item.preferred_safe,
                        "conservative_min_clearance_m": item.conservative_min_clearance_m,
                        "goal_progress_m": item.goal_progress_m} for item in decision.evaluations],
        "selected_trajectory": [asdict(point) for point in selected.trajectory],
    }


def uniform_decision(step: int, schedule: tuple[int, ...]) -> Q2Decision:
    transmit = step in schedule
    role = "startup" if step == schedule[0] else ("adaptive" if step == schedule[1] else
            "reserve" if step == schedule[2] else "hold")
    reason = "fixed_uniform" if transmit else "uniform_hold"
    state = "NORMAL" if step < schedule[1] else ("SPENT" if step < schedule[2] else "RESERVE")
    before = 3 - sum(value < step for value in schedule)
    return Q2Decision(transmit, role, reason, state, False, None, None,
                      schedule[1] if step >= schedule[1] else None, False,
                      step < schedule[2], before, before - int(transmit))


robot = Supervisor()
dt_ms = int(robot.getBasicTimeStep())
dt_s = dt_ms / 1000.0
cfg = json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
out = Path(os.environ["CVC_OUTPUT"])
out.parent.mkdir(parents=True, exist_ok=True)
planner_cfg, visual_cfg, q2_cfg = cfg["planner"], cfg["visual_geometry"], cfg["q2"]
policy = cfg["policy"]
self_node = robot.getSelf()
self_node.getField("translation").setSFVec3f([*cfg["start"][:2], 0])
self_node.getField("rotation").setSFRotation([0, 0, 1, cfg["start"][2]])
self_node.resetPhysics()
children = robot.getFromDef("CVC_OBJECTS").getField("children")
for item in cfg["objects"]:
    children.importMFNodeFromString(-1, obstacle_vrml(item))
physical = [(item, robot.getFromDef(item["id"])) for item in cfg["objects"] if item.get("physical", True)]
camera = robot.getDevice("camera"); camera.enable(dt_ms)
left = robot.getDevice("left wheel motor"); right = robot.getDevice("right wheel motor")
left.setPosition(float("inf")); right.setPosition(float("inf"))

calibration = VisualRangeCalibration(
    visual_cfg["inverse_height_coefficient_m_px"], visual_cfg["intercept_m"],
    visual_cfg["uncertainty_bound_m"])
thresholds = SafetyValueThresholds(**q2_cfg["safety_decision_value_thresholds"])
total_steps = int(cfg["duration_s"] * 1000 / dt_ms)
u0_schedule = tuple(q2_cfg["u0_schedule"])
allocator = None if policy == "U0" else RiskArmedSafetyValueAllocator(
    total_steps, q2_cfg["risk_threshold"], q2_cfg["deadline_steps"], q2_cfg["reserve_step"])
channel = MirroredHoldingChannel()
memory = CausalObstacleMemory(int(planner_cfg["obstacle_memory_steps"]))
prior_mirror_image: Image.Image | None = None
prior_mirror_timestamp: int | None = None
previous_r0 = 0.0
has_previous_r0 = False
odom_x, odom_y, odom_yaw = cfg["start"]
pose_history: dict[int, Pose2D] = {}
step_by_timestamp: dict[int, int] = {}
rows = []
wire_total = content_total = metadata_total = padding_total = 0
path_length = 0.0
previous_xy = None

if robot.step(dt_ms) == -1:
    raise RuntimeError("Webots stopped before Q2 camera frame")
for step in range(total_steps):
    now = int(round(robot.getTime() * 1000))
    raw = rgb_frame(camera)
    sender_visual = detect_red_obstacle(raw)
    r0 = sender_visual.apparent_proximity
    r1 = predictive_risk(r0, previous_r0, sender_visual.bearing_normalized) if has_previous_r0 else r0
    previous_r0, has_previous_r0 = r0, True
    selected_risk = r0 if policy in ("U0", "A0") else r1
    shadow_packet = encode_p3_packet(raw, now, selected_risk, policy,
                                     int(cfg["jpeg_quality"]), int(cfg["packet_bytes"]))
    current_image, _ = decode_p3_packet(shadow_packet.payload)
    held_image = current_image.copy() if prior_mirror_image is None else prior_mirror_image.copy()
    held_timestamp = now if prior_mirror_timestamp is None else prior_mirror_timestamp
    current_pose = Pose2D(odom_x, odom_y, odom_yaw)
    pose_history[now] = current_pose; step_by_timestamp[now] = step
    goal_bearing = normalize_angle(math.atan2(cfg["goal"][1] - odom_y, cfg["goal"][0] - odom_x) - odom_yaw)
    held_visual = detect_red_obstacle(held_image)
    current_visual = detect_red_obstacle(current_image)
    held_local = visual_obstacle_estimates(
        held_visual, calibration, camera_horizontal_fov_rad=visual_cfg["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual_cfg["known_obstacle_radius_m"])
    current_local = visual_obstacle_estimates(
        current_visual, calibration, camera_horizontal_fov_rad=visual_cfg["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual_cfg["known_obstacle_radius_m"])
    held_source_pose = pose_history.get(held_timestamp, current_pose)
    held_source_step = step_by_timestamp.get(held_timestamp, step)
    held_obstacles = memory.preview(held_local, held_source_pose, held_source_step, current_pose, step)
    current_obstacles = memory.preview(current_local, current_pose, step, current_pose, step)
    common = dict(horizon_s=planner_cfg["horizon_s"], step_s=planner_cfg["rollout_step_s"],
                  robot_radius_m=planner_cfg["robot_radius_m"],
                  hard_clearance_m=planner_cfg["hard_clearance_m"],
                  preferred_clearance_m=planner_cfg["preferred_clearance_m"],
                  near_slowdown_range_m=planner_cfg["near_slowdown_range_m"],
                  near_max_speed_m_s=planner_cfg["near_max_speed_m_s"])
    held_plan = plan_local_action(held_obstacles, goal_bearing, **common)
    current_plan = plan_local_action(current_obstacles, goal_bearing, **common)
    safety_value = evaluate_safety_decision_value(held_plan, current_plan, thresholds)
    policy_decision = (uniform_decision(step, u0_schedule) if allocator is None else
                       allocator.decide(step, selected_risk, safety_value))
    payload = shadow_packet.payload if policy_decision.transmit else None
    received, mirrored = channel.step(now, payload)
    if policy_decision.transmit:
        wire_total += len(shadow_packet.payload)
        content_total += shadow_packet.content_bytes
        metadata_total += shadow_packet.metadata_bytes
        padding_total += shadow_packet.padding_bytes
    prior_mirror_image, prior_mirror_timestamp = mirrored.image.copy(), mirrored.source_timestamp_ms
    actual_visual = detect_red_obstacle(received.image)
    actual_local = visual_obstacle_estimates(
        actual_visual, calibration, camera_horizontal_fov_rad=visual_cfg["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual_cfg["known_obstacle_radius_m"])
    actual_source_pose = pose_history.get(received.source_timestamp_ms, current_pose)
    actual_source_step = step_by_timestamp.get(received.source_timestamp_ms, step)
    actual_obstacles = memory.preview(actual_local, actual_source_pose, actual_source_step, current_pose, step)
    memory.update(actual_local, actual_source_pose, actual_source_step)
    actual_plan = plan_local_action(actual_obstacles, goal_bearing, **common)
    selected = actual_plan.selected
    left.setVelocity(selected.wheel_left_rad_s); right.setVelocity(selected.wheel_right_rad_s)
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

    # Evaluator-only Webots truth begins after the runtime action.
    position = self_node.getPosition(); xy = (float(position[0]), float(position[1]))
    if previous_xy is not None:
        path_length += math.hypot(xy[0] - previous_xy[0], xy[1] - previous_xy[1])
    previous_xy = xy
    clearances = []
    for item, node in physical:
        sx, sy = item.get("size", [0.08, 0.08]); x, y = item["center"]
        dx, dy = max(abs(xy[0] - x) - sx / 2, 0), max(abs(xy[1] - y) - sy / 2, 0)
        clearances.append(math.hypot(dx, dy) - ROBOT_RADIUS_M)
    clearance = min(clearances) if clearances else 10.0
    collision = bool(physical) and any(node.getContactPoints(True) for _, node in physical) and bool(self_node.getContactPoints(True))
    start_goal = math.hypot(cfg["goal"][0] - cfg["start"][0], cfg["goal"][1] - cfg["start"][1])
    remaining = math.hypot(cfg["goal"][0] - xy[0], cfg["goal"][1] - xy[1])
    rows.append({
        "step": step, "time_s": robot.getTime(), "scenario": cfg["scenario"], "policy": policy,
        "sender": {"r0": r0, "r1": r1, "selected_risk": selected_risk},
        "policy_state": asdict(policy_decision),
        "safety_value": asdict(safety_value),
        "communication": {"transmitted": policy_decision.transmit, "packet_role": policy_decision.packet_role,
                          "reason": policy_decision.reason, "wire_bytes": len(shadow_packet.payload) if policy_decision.transmit else 0,
                          "content_bytes": shadow_packet.content_bytes if policy_decision.transmit else 0,
                          "metadata_bytes": shadow_packet.metadata_bytes if policy_decision.transmit else 0,
                          "padding_bytes": shadow_packet.padding_bytes if policy_decision.transmit else 0,
                          "cumulative_wire_bytes": wire_total, "image_age_ms": received.image_age_ms},
        "counterfactual": {"held_source_timestamp_ms": held_timestamp,
                           "held_image_age_before_decision_ms": now - held_timestamp,
                           "held_image_sha256": image_sha256(held_image),
                           "current_image_sha256": image_sha256(current_image),
                           "held_obstacles": [asdict(item) for item in held_obstacles],
                           "current_obstacles": [asdict(item) for item in current_obstacles],
                           "held_planner": decision_dict(held_plan), "current_planner": decision_dict(current_plan)},
        "receiver": {"held": received.held, "source_timestamp_ms": received.source_timestamp_ms,
                     "image_age_ms": received.image_age_ms, "image_sha256": image_sha256(received.image),
                     "mirror_image_sha256": image_sha256(mirrored.image),
                     "mirror_match": image_sha256(received.image) == image_sha256(mirrored.image)},
        "runtime": {"goal_bearing_rad": goal_bearing, "odometry": {"x_m": odom_x, "y_m": odom_y, "yaw_rad": odom_yaw},
                    "obstacles": [asdict(item) for item in actual_obstacles], "planner": decision_dict(actual_plan),
                    "wheel_left_rad_s": selected.wheel_left_rad_s, "wheel_right_rad_s": selected.wheel_right_rad_s},
        "evaluator": {"x_m": xy[0], "y_m": xy[1], "clearance_m": clearance,
                      "collision": collision, "contact": collision, "path_length_m": path_length,
                      "goal_progress_m": start_goal - remaining, "remaining_goal_distance_m": remaining},
    })

out.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
sends = [row for row in rows if row["communication"]["transmitted"]]
collided = any(row["evaluator"]["collision"] for row in rows)
progress = rows[-1]["evaluator"]["goal_progress_m"]
completion_step = next((row["step"] for row in rows if row["evaluator"]["goal_progress_m"] >= .5), None)
summary = {
    "development_only": True, "formal": False, "scenario": cfg["scenario"], "semantic": cfg["semantic"],
    "seed": cfg["seed"], "policy": policy, "steps": len(rows), "transmissions": len(sends),
    "send_steps": [row["step"] for row in sends], "packet_roles": [row["communication"]["packet_role"] for row in sends],
    "send_reasons": [row["communication"]["reason"] for row in sends],
    "wire_bytes": wire_total, "content_bytes": content_total, "metadata_bytes": metadata_total,
    "padding_bytes": padding_total, "byte_reconciliation": content_total + metadata_total + padding_total == wire_total,
    "arm_step": next((row["policy_state"]["arm_step"] for row in rows if row["policy_state"]["arm_step"] is not None), None),
    "safety_value_step": next((row["step"] for row in rows if row["safety_value"]["triggered"]), None),
    "spend_step": next((row["step"] for row in sends if row["communication"]["packet_role"] == "adaptive"), None),
    "adaptive_reason": next((row["communication"]["reason"] for row in sends if row["communication"]["packet_role"] == "adaptive"), None),
    "deadline_used": any(row["communication"]["reason"] == "arm_deadline" for row in rows),
    "unarmed_fallback_used": any(row["communication"]["reason"] == "unarmed_fallback" for row in rows),
    "reserve_step": next((row["step"] for row in sends if row["communication"]["packet_role"] == "reserve"), None),
    "mirror_all_steps_match": all(row["receiver"]["mirror_match"] for row in rows),
    "safety_value_event_steps": sum(row["safety_value"]["triggered"] for row in rows),
    "safe_set_change_steps": sum(row["safety_value"]["safe_set_changed"] for row in rows),
    "action_change_steps": sum(row["safety_value"]["action_changed"] for row in rows),
    "safety_class_deterioration_steps": sum(row["safety_value"]["safety_class_deterioration"] for row in rows),
    "moving_safe_set_collapse_steps": sum(row["safety_value"]["moving_safe_set_collapse"] for row in rows),
    "collision": collided, "min_clearance_m": min(row["evaluator"]["clearance_m"] for row in rows),
    "mean_clearance_m": sum(row["evaluator"]["clearance_m"] for row in rows) / len(rows),
    "task_success": not collided and progress >= .5, "goal_progress_m": progress,
    "completion_step": completion_step, "completion_time_s": ((completion_step + 1) * dt_s if completion_step is not None else None),
    "path_length_m": path_length, "path_efficiency": progress / path_length if path_length > 0 else None,
}
out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
robot.simulationQuit(0)
