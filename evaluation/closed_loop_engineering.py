"""Engineering-only 1-D visual communication/perception/control loop."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from communication.closed_loop_policy import *

DT=.05; STEPS=120; ROBOT_RADIUS=.037
DETECTION_RANGE={LOW_BYTES:.025,MEDIUM_BYTES:.050,HIGH_BYTES:.130}

@dataclass(frozen=True)
class Scenario:
    scenario_id:str; obstacle_x_m:float; initial_speed_m_s:float; braking_m_s2:float

def nominal_risks(s:Scenario,method:str):
    x=0.; out=[]
    for _ in range(STEPS):
        clearance=s.obstacle_x_m-x-ROBOT_RADIUS
        out.append(current_risk(clearance) if method=="A0" else predictive_risk(clearance,s.initial_speed_m_s))
        x+=s.initial_speed_m_s*DT
    return out

def run_episode(s:Scenario,method:str,high_frames:int=24,policy_version="offline_quota_v1"):
    risks=[0.]*STEPS if method=="U0" else nominal_risks(s,method); alloc=(matched_causal_schedule if policy_version=="causal_token_v2" else matched_schedule)(method,risks,high_frames)
    x=0.;v=s.initial_speed_m_s;minimum=1e9;detected=False;trajectory=[]
    for i,cost in enumerate(alloc.bytes_per_frame):
        clearance=s.obstacle_x_m-x-ROBOT_RADIUS; visible=0<=clearance<=DETECTION_RANGE[cost]
        if visible: detected=True
        if detected:v=max(0.,v-s.braking_m_s2*DT)
        x+=v*DT;minimum=min(minimum,s.obstacle_x_m-x-ROBOT_RADIUS)
        trajectory.append({"frame":i,"bytes":cost,"x_m":x,"speed_m_s":v,"clearance_m":minimum,"perception_detected":visible})
    return {"scenario":asdict(s),"method":method,"policy_version":policy_version,"total_bytes":alloc.total_bytes,"average_bytes_per_frame":alloc.total_bytes/STEPS,"collision":minimum<=0,"task_success":minimum>0,"minimum_clearance_m":minimum,"first_detection_frame":next((x["frame"] for x in trajectory if x["perception_detected"]),None),"trajectory":trajectory}

def engineering_matrix(policy_version="offline_quota_v1"):
    scenarios=[Scenario(f"E{i:02d}",x,v,b) for i,(x,v,b) in enumerate([(0.26,.11,.16),(0.30,.12,.17),(0.34,.13,.18),(0.38,.14,.20),(0.28,.12,.14),(0.36,.15,.22)],1)]
    return [run_episode(s,m,policy_version=policy_version) for s in scenarios for m in ("U0","A0","A1")]
