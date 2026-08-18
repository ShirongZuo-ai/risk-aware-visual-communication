"""Webots CVC-P1 development runner: pixels -> wire -> pixels -> control."""
from __future__ import annotations
import json, math, os, sys
from pathlib import Path
from PIL import Image
from controller import Supervisor

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from communication.cvc_protocol import (AllocationDecision, HoldingReceiver, SenderObservation,
                                         encode_packet)
from communication.cvc_perception import detect_red_obstacle, visual_wheel_command
from compression.tiled_jpeg import DEFAULT_M5_GRID, encode_rgb_frame_to_tiles
from compression.tile_container import serialize_tiled_frame

RADIUS = 0.037

def rgb_frame(camera) -> Image.Image:
    return Image.frombytes("RGBA", (camera.getWidth(), camera.getHeight()), camera.getImage(), "raw", "BGRA").convert("RGB")

def current_visual_risk(image: Image.Image) -> float:
    return detect_red_obstacle(image).proximity

def predictive_visual_risk(current: float, previous: float) -> float:
    # Causal constant-growth predictor using only current/prior camera-derived state.
    return min(1.0, max(current, current + 4.0 * max(0.0, current - previous)))

def obstacle_vrml(item: dict) -> str:
    x,y=item["center"]; sx,sy=item.get("size",[.08,.08]); color=item.get("color",[1,0,0])
    return f'''DEF {item["id"]} Solid {{ translation {x} {y} 0.04 children [ Shape {{ appearance PBRAppearance {{ baseColor {color[0]} {color[1]} {color[2]} roughness 0.7 }} geometry Box {{ size {sx} {sy} 0.08 }} }} ] boundingObject Box {{ size {sx} {sy} 0.08 }} locked TRUE }}'''

robot=Supervisor(); dt=int(robot.getBasicTimeStep())
cfg=json.loads(Path(os.environ["CVC_CONFIG"]).read_text(encoding="utf-8"))
self_node=robot.getSelf(); self_node.getField("translation").setSFVec3f([*cfg["start"][:2],0]); self_node.getField("rotation").setSFRotation([0,0,1,cfg["start"][2]]); self_node.resetPhysics()
children=robot.getFromDef("CVC_OBJECTS").getField("children")
for item in cfg["objects"]: children.importMFNodeFromString(-1, obstacle_vrml(item))
physical=[(o,robot.getFromDef(o["id"])) for o in cfg["objects"] if o.get("physical",True)]
camera=robot.getDevice("camera"); camera.enable(dt)
left=robot.getDevice("left wheel motor"); right=robot.getDevice("right wheel motor")
left.setPosition(float("inf"));right.setPosition(float("inf"))
receiver=HoldingReceiver(); policy=cfg["policy"]; condition=cfg.get("condition","POLICY")
target=int(cfg.get("packet_bytes",36000)); interval={"HIGH":1,"MEDIUM":18,"LOW":1_000_000}.get(condition,6)
previous_risk=0.; cumulative=0; transmitted=0; rows=[]; first=True
if robot.step(dt)==-1: raise RuntimeError("Webots stopped before the first camera frame")
for step in range(int(cfg.get("duration_s",10)*1000/dt)):
    now=int(round(robot.getTime()*1000.0)); raw=rgb_frame(camera); r0=current_visual_risk(raw); r1=predictive_visual_risk(r0,previous_risk); previous_risk=r0
    if step in (0,150,300):
        diagnostic=Path(os.environ["CVC_OUTPUT"]).with_suffix(f".frame{step:03d}.png"); diagnostic.parent.mkdir(parents=True,exist_ok=True); raw.save(diagnostic)
    risk=0.0 if policy=="U0" else (r0 if policy=="A0" else r1)
    # Same causal token cadence and exact packet size for all policies. Adaptive
    # policies change spatial quality, never future transmission opportunities.
    send=first or step % interval == 0; first=False
    if policy=="U0": qualities=(42,)*48
    else:
        hi=72 if risk>=.12 else 42; lo=18 if risk>=.12 else 32
        qualities=tuple(hi if row>=3 and 2<=col<6 else lo for _,row,col,_ in DEFAULT_M5_GRID.iter_tiles())
    packet=None; content=metadata=padding=0
    if send:
        # If a severe-quality sanity condition is requested, use a real low-quality JPEG.
        if condition=="LOW": qualities=(3,)*48
        elif condition=="HIGH": qualities=(90,)*48
        probe=serialize_tiled_frame(DEFAULT_M5_GRID,encode_rgb_frame_to_tiles(raw,DEFAULT_M5_GRID,qualities))
        # Metadata length is deterministic enough to discover exact content by one generous target.
        decision=AllocationDecision(policy,True,qualities,target)
        try: encoded=encode_packet(SenderObservation(now,raw,risk),decision)
        except ValueError:
            target=max(target,len(probe)+4096); decision=AllocationDecision(policy,True,qualities,target); encoded=encode_packet(SenderObservation(now,raw,risk),decision)
        packet=encoded.payload; content=encoded.content_bytes; metadata=encoded.metadata_bytes; padding=encoded.padding_bytes
        cumulative+=len(packet); transmitted+=1
    received=receiver.step(now,packet); detected=detect_red_obstacle(received.image); lc,rc=visual_wheel_command(detected,3.5)
    left.setVelocity(lc);right.setVelocity(rc)
    if robot.step(dt)==-1: break
    pos=self_node.getPosition(); clear=[]
    for item,node in physical:
        sx,sy=item.get("size",[.08,.08]); x,y=item["center"]
        dx=max(abs(pos[0]-x)-sx/2,0);dy=max(abs(pos[1]-y)-sy/2,0);clear.append(math.hypot(dx,dy)-RADIUS)
    collision=any(node.getContactPoints(True) for _,node in physical) and bool(self_node.getContactPoints(True))
    rows.append({"step":step,"time_s":robot.getTime(),"scenario":cfg["scenario"],"policy":policy,"condition":condition,
      "sender":{"r0":r0,"r1":r1},"communication":{"transmitted":send,"wire_bytes":len(packet) if packet else 0,"content_bytes":content,"metadata_bytes":metadata,"padding_bytes":padding,"cumulative_wire_bytes":cumulative},
      "receiver":{"image_age_ms":received.image_age_ms,"held":received.held},"perception":{"detected":detected.detected,"bearing":detected.bearing_normalized,"proximity":detected.proximity,"pixels":detected.pixel_count},
      "control":{"left_rad_s":lc,"right_rad_s":rc},"evaluator":{"x_m":pos[0],"y_m":pos[1],"clearance_m":min(clear) if clear else None,"collision":collision}})
out=Path(os.environ["CVC_OUTPUT"]);out.parent.mkdir(parents=True,exist_ok=True)
out.write_text("\n".join(json.dumps(r,sort_keys=True,separators=(",",":")) for r in rows)+"\n",encoding="utf-8")
valid_clearance=[r["evaluator"]["clearance_m"] for r in rows if r["evaluator"]["clearance_m"] is not None]
summary={"scenario":cfg["scenario"],"policy":policy,"condition":condition,"steps":len(rows),"wire_bytes":cumulative,"transmitted_frames":transmitted,"collision":any(r["evaluator"]["collision"] for r in rows),"min_clearance_m":min(valid_clearance) if valid_clearance else None,"mean_image_age_ms":sum(r["receiver"]["image_age_ms"] for r in rows)/len(rows),"final_x_m":rows[-1]["evaluator"]["x_m"]}
out.with_suffix(".summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
robot.simulationQuit(0)
