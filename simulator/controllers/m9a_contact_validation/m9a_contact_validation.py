"""M9-A-I2 contact-validation controller; writes engineering-only dense JSONL."""
from controller import Supervisor
import hashlib
import json
import math
import os
from pathlib import Path

PHYSICAL_RADIUS_M = 0.037
UNCERTAINTY_RADIUS_M = 0.037592257  # provenance only; never used in clearance.

robot = Supervisor()
dt_ms = int(robot.getBasicTimeStep()); dt_s = dt_ms / 1000.0
fixture = robot.getCustomData()
output_path = Path(os.environ["M9A_FIXTURE_OUTPUT"])
output_path.parent.mkdir(parents=True, exist_ok=True)
episode_id = os.environ["M9A_FIXTURE_EPISODE_ID"]
git_head = os.environ["M9A_GIT_HEAD"]
webots_version = os.environ["M9A_WEBOTS_VERSION"]
world_sha = os.environ["M9A_WORLD_SHA256"]
controller_sha = os.environ["M9A_CONTROLLER_SHA256"]

left = robot.getDevice("left wheel motor"); right = robot.getDevice("right wheel motor")
left.setPosition(float("inf")); right.setPosition(float("inf"))
speed = 0.0 if fixture == "stationary_no_contact" else 3.0
left.setVelocity(speed); right.setVelocity(speed)
self_node = robot.getSelf()
if hasattr(self_node, "enableContactPointsTracking"):
    self_node.enableContactPointsTracking(dt_ms)

target_def = ({"obstacle_collision":"M9A_OBSTACLE", "safe_close_pass":"M9A_OBSTACLE", "wall_collision":"M9A_WALL"}).get(fixture)
target_node = robot.getFromDef(target_def) if target_def else None
target_id = target_node.getId() if target_node else None
target_kind = "wall" if fixture == "wall_collision" else "obstacle"

def sha256_text(value): return hashlib.sha256(value.encode("utf-8")).hexdigest()
def yaw(orientation): return math.atan2(orientation[3], orientation[0])
def clearance(x, y):
    if fixture == "wall_collision":
        return 0.19 - x - PHYSICAL_RADIUS_M
    if fixture in {"obstacle_collision", "safe_close_pass"}:
        cy = 0.0 if fixture == "obstacle_collision" else 0.060
        dx=max(abs(x-.16)-.02,0.0); dy=max(abs(y-cy)-(.04 if fixture=="obstacle_collision" else .02),0.0)
        return math.hypot(dx,dy)-PHYSICAL_RADIUS_M
    return 0.5-PHYSICAL_RADIUS_M

previous_position = self_node.getPosition(); previous_yaw = yaw(self_node.getOrientation())
records=[]
for step in range(160):
    if robot.step(dt_ms) == -1: break
    timestamp=robot.getTime(); position=self_node.getPosition(); heading=yaw(self_node.getOrientation())
    velocity=self_node.getVelocity()
    raw=[]
    for index, point in enumerate(self_node.getContactPoints(includeDescendants=True)):
        node_id=getattr(point,"node_id",None); xyz=list(getattr(point,"point",(0.0,0.0,0.0)))
        node=robot.getFromId(node_id) if node_id is not None and hasattr(robot,"getFromId") else None
        counterpart_def=node.getDef() if node else None
        raw.append({"x_m":xyz[0],"y_m":xyz[1],"z_m":xyz[2],"associated_node_id":node_id,"associated_def":counterpart_def or None})
    counterpart_raw=[]
    if target_node:
        for point in target_node.getContactPoints(includeDescendants=True):
            counterpart_raw.append({"x_m":point.point[0],"y_m":point.point[1],"z_m":point.point[2],"associated_node_id":point.node_id})
    distances=[math.dist((a["x_m"],a["y_m"],a["z_m"]),(b["x_m"],b["y_m"],b["z_m"])) for a in raw for b in counterpart_raw]
    nearest=min(distances) if distances else None; matched_distances=sorted(d for d in distances if d <= 1e-6); matches=len(matched_distances)
    collision=matches > 0
    record={
      "schema_version":"m9a-fixture-step-log-v1","purpose":"fixture_validation_only","protocol_version":"m9a-p-v1","episode_id":episode_id,
      "split":"fixture_validation","scenario_family":"FIXTURE","parameter_set_id":fixture,"seed":None,
      "timestep_index":step,"timestamp_s":timestamp,"basic_timestep_s":dt_s,
      "robot_state":{"x_m":position[0],"y_m":position[1],"yaw_rad":heading,"linear_velocity_m_s":math.hypot(velocity[0],velocity[1]),"angular_velocity_rad_s":velocity[5]},
      "applied_command":{"left_wheel_rad_s":speed,"right_wheel_rad_s":speed,"segment_id":"fixture_motion"},
      "future_command_schedule":{"available_at_s":0.0,"schedule_sha256":sha256_text(f"{speed},{speed}"),"segments":[{"start_s":0.0,"end_s":5.12,"left_wheel_rad_s":speed,"right_wheel_rad_s":speed}]},
      "obstacles":[{"obstacle_id":target_def,"node_id":target_id,"kind":target_kind}] if target_def else [],
      "robot_footprint":{"identity":"webots-r2025a-epuck-collision-cylinder-v1","shape":"circle","physical_radius_m":PHYSICAL_RADIUS_M,"predictor_uncertainty_corridor_radius_m":UNCERTAINTY_RADIUS_M},
      "raw_contact_observation":{"api":"Node.getContactPoints","queried_robot_node_id":self_node.getId(),"include_descendants":True,"stream_available":True,"raw_contact_point_count":len(raw),"points":raw},
      "eligible_counterpart_contact_sets":[{"root_def":target_def,"root_node_id":target_id,"kind":target_kind,"raw_contact_point_count":len(counterpart_raw),"points":counterpart_raw}] if target_def else [],
      "contact_matching":{"epsilon_contact_m":1e-6,"nearest_distance_by_def_m":{target_def:nearest} if target_def else {},"matched_pair_distances_m":{target_def:matched_distances} if target_def else {},"match_count_by_def":{target_def:matches} if target_def else {},"matched_counterpart_defs":[target_def] if collision else [],"validated_pair_contact":collision},
      "validated_collision_event":{"collision_active":collision,"matched_counterpart_defs":[target_def] if collision else []},
      "actual_physical_clearance_m":clearance(position[0],position[1]),
      "provenance":{"purpose":"contact_validation_only","git_commit":git_head,"webots_version":webots_version,"world_sha256":world_sha,"controller_sha256":controller_sha,"config_sha256":sha256_text(fixture),"protocol_version":"m9a-p-v1"}}
    records.append(record)
    previous_position=position; previous_yaw=heading

with output_path.open("w",encoding="utf-8",newline="\n") as handle:
    for record in records: handle.write(json.dumps(record,sort_keys=True,separators=(",",":"))+"\n")
left.setVelocity(0); right.setVelocity(0)
robot.simulationQuit(0)
