"""Frozen M9-A formal analysis primitives; physical and M3 geometry are separate."""
from __future__ import annotations
import json, math
from pathlib import Path
from typing import Iterable
import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import average_precision_score
from navigation.trajectory_prediction import CommandSegment, TrajectoryPoint, predict_command_conditioned_trajectory, predict_state_only_trajectory
from risk_map.geometry import point_to_aabb_distance, polyline_to_aabb_closest
from risk_map.models import ObstacleFootprint
from simulator.m9a_config import PHYSICAL_RADIUS_M, PREDICTOR_UNCERTAINTY_CORRIDOR_RADIUS_M

HORIZONS=(0.5,1.0,2.0); NEAR_M=0.013

def obstacles_from_config(cfg):
    return tuple(ObstacleFootprint(o["id"],o["center_x_m"],o["center_y_m"],o["size_x_m"],o["size_y_m"]) for o in (cfg["obstacle"],*cfg.get("distractors",[])))

def physical_clearance(points,obstacles,*,physical_radius_m=PHYSICAL_RADIUS_M):
    if physical_radius_m != PHYSICAL_RADIUS_M: raise ValueError("M9 physical radius is frozen at 0.037 m")
    pts=list(points); return min(polyline_to_aabb_closest(pts,o).distance_m-physical_radius_m for o in obstacles)

def m3_corridor_clearance(points,obstacles):
    pts=list(points); return min(polyline_to_aabb_closest(pts,o).distance_m-PREDICTOR_UNCERTAINTY_CORRIDOR_RADIUS_M for o in obstacles)

def command_segments(cfg,decision_s,horizon_s):
    out=[]
    for seg in cfg["command_schedule"]:
        lo=max(decision_s,seg["start_s"]); hi=min(decision_s+horizon_s,seg["end_s"])
        if hi>lo+1e-12: out.append(CommandSegment(max(0.0,lo-decision_s),min(horizon_s,hi-decision_s),seg["left_rad_s"],seg["right_rad_s"]))
    if not out or out[0].start_offset_s>1e-9 or out[-1].end_offset_s<horizon_s-1e-8: raise ValueError("command schedule does not cover horizon")
    if out[-1].end_offset_s < horizon_s:
        last=out[-1];out[-1]=CommandSegment(last.start_offset_s,horizon_s,last.left_wheel_command_rad_s,last.right_wheel_command_rad_s)
    return out

def load_episode(log_path:Path,cfg_path:Path,horizon_s:float):
    rows=[json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x]; cfg=json.loads(cfg_path.read_text(encoding="utf-8")); obs=obstacles_from_config(cfg)
    times=np.array([r["timestamp_s"] for r in rows]); xs=np.array([r["robot_state"]["x_m"] for r in rows]); ys=np.array([r["robot_state"]["y_m"] for r in rows]); contacts=np.array([r["contact_matching"]["validated_pair_contact"] for r in rows],bool); samples=[]
    for i,r in enumerate(rows):
        target=times[i]+horizon_s; j=int(np.searchsorted(times,target,side="left"))
        if j>=len(rows): break
        # Scientific decisions require both a bracketing actual sample and a
        # command schedule covering the full nominal predictive horizon.
        if target > cfg["command_schedule"][-1]["end_s"] + 1e-9: break
        future=np.array([rr["actual_physical_clearance_m"] for rr in rows[i:j+1]],float)
        if times[j]>target+1e-12:
            f=(target-times[j-1])/(times[j]-times[j-1]); x=xs[j-1]+f*(xs[j]-xs[j-1]); y=ys[j-1]+f*(ys[j]-ys[j-1]); future[-1]=min(point_to_aabb_distance(x,y,o)-PHYSICAL_RADIUS_M for o in obs)
        actual=float(future.min()); collision=bool(contacts[i+1:j+1].any()); danger=collision or (not collision and actual<NEAR_M); current=min(point_to_aabb_distance(xs[i],ys[i],o)-PHYSICAL_RADIUS_M for o in obs)
        state=[TrajectoryPoint(0,xs[i],ys[i],r["robot_state"]["yaw_rad"]),*predict_state_only_trajectory(x=xs[i],y=ys[i],yaw_rad=r["robot_state"]["yaw_rad"],linear_velocity_m_s=r["robot_state"]["linear_velocity_m_s"],angular_velocity_rad_s=r["robot_state"]["angular_velocity_rad_s"],horizon_s=horizon_s)]
        cmd=[TrajectoryPoint(0,xs[i],ys[i],r["robot_state"]["yaw_rad"]),*predict_command_conditioned_trajectory(x=xs[i],y=ys[i],yaw_rad=r["robot_state"]["yaw_rad"],command_segments=command_segments(cfg,times[i],horizon_s),horizon_s=horizon_s)]
        r1=physical_clearance(state,obs);r2=physical_clearance(cmd,obs); candidates=[times[k] for k in range(i+1,j+1) if contacts[k] and not contacts[k-1]]
        for k in range(i+1,j+1):
            if future[k-i]<NEAR_M and future[k-i-1]>=NEAR_M:candidates.append(times[k])
        samples.append({"episode_id":cfg["episode_id"],"family":cfg["family_id"],"parameter":cfg["parameter_set_id"],"time_s":float(times[i]),"horizon_s":horizon_s,"actual_clearance_m":actual,"collision":collision,"near":not collision and actual<NEAR_M,"danger":danger,"danger_onset_s":float(min(candidates)) if candidates else None,"R0_clearance_m":current,"R1_clearance_m":r1,"R2_clearance_m":r2,"R0":-current,"R1":-r1,"R2":-r2,"R1_m3_corridor_m":m3_corridor_clearance(state,obs),"R2_m3_corridor_m":m3_corridor_clearance(cmd,obs)})
    return {"episode_id":cfg["episode_id"],"family":cfg["family_id"],"parameter":cfg["parameter_set_id"],"episode_collision":bool(contacts.any()),"episode_min_clearance_m":float(min(r["actual_physical_clearance_m"] for r in rows)),"samples":samples}

def auprc(labels,scores,weights=None):
    y=np.asarray(labels,int);s=np.asarray(scores,float)
    return math.nan if len(y)==0 or not np.isfinite(s).all() or y.sum()==0 else float(average_precision_score(y,s,sample_weight=weights))

def family_macro_auprc(episodes,method,label="danger"):
    vals=[]
    for family in sorted({e["family"] for e in episodes}):
        ss=[x for e in episodes if e["family"]==family for x in e["samples"]];v=auprc([x[label] for x in ss],[x[method] for x in ss])
        if math.isfinite(v):vals.append(v)
    return float(np.mean(vals)) if vals else math.nan

def paired_bootstrap(episodes,a,b,replicates=10000,seed=20260901):
    groups={f:[e for e in episodes if e["family"]==f] for f in sorted({e["family"] for e in episodes})};rng=np.random.default_rng(seed);values=[]
    for _ in range(replicates):
        draw=[]
        for es in groups.values():draw += [es[i] for i in rng.integers(0,len(es),len(es))]
        values.append(family_macro_auprc(draw,a)-family_macro_auprc(draw,b))
    v=np.asarray([x for x in values if math.isfinite(x)]);return {"lower":float(np.percentile(v,2.5)),"upper":float(np.percentile(v,97.5)),"valid_replicates":len(v)}

def warning_runs(samples,method,threshold):
    active=False;above=below=0;start=0.;runs=[];refractory=-math.inf
    for x in samples:
        hit=x[method]>=threshold;above=above+1 if hit else 0;below=below+1 if not hit else 0
        if not active and above>=3 and x["time_s"]>=refractory:active=True;start=x["time_s"]-.064
        if active and below>=3:active=False;end=x["time_s"]-.064;runs.append((start,end));refractory=end+.5
    if active:runs.append((start,samples[-1]["time_s"]))
    return runs

def select_warning_threshold(episodes,method):
    safe=[e for e in episodes if not e["episode_collision"] and e["episode_min_clearance_m"]>=NEAR_M];danger=[e for e in episodes if e not in safe and any(x["danger"] for x in e["samples"])];candidates=sorted({x[method] for e in episodes for x in e["samples"]},reverse=True);best=None
    for threshold in candidates:
        false=sum(len(warning_runs(e["samples"],method,threshold)) for e in safe);minutes=sum((e["samples"][-1]["time_s"]-e["samples"][0]["time_s"])/60 for e in safe);rate=false/minutes if minutes else math.inf;det=sum(bool(warning_runs(e["samples"],method,threshold)) for e in danger)/len(danger) if danger else 0
        if rate<=.5+1e-12 and (best is None or (det,threshold)>best[:2]):best=(det,threshold,rate)
    return {"threshold":best[1] if best else math.inf,"false_warnings_per_min":best[2] if best else 0.,"event_detection_rate":best[0] if best else 0.,"safe_episode_count":len(safe),"danger_episode_count":len(danger),"debounce_steps":3,"refractory_s":.5}

def correlations(samples,method):
    a=np.array([x["actual_clearance_m"] for x in samples]);p=np.array([-x[method] for x in samples]);e=p-a
    return {"mae_m":float(np.mean(abs(e))),"rmse_m":float(np.sqrt(np.mean(e*e))),"spearman":float(spearmanr(p,a).statistic),"pearson":float(pearsonr(p,a).statistic)}
