"""Literal M9-A pilot grid v2; method outputs are not inputs."""
from __future__ import annotations
import json
import math
from pathlib import Path
from simulator.m9a_config import ScenarioFamily, Split, seed_for

def schedule(kind,direction=1):
    if kind=='straight': return [{'start_s':0.,'end_s':6.,'left_rad_s':3.,'right_rad_s':3.}]
    if kind=='arc': return [{'start_s':0.,'end_s':6.,'left_rad_s':2.2 if direction>0 else 3.8,'right_rad_s':3.8 if direction>0 else 2.2}]
    if kind=='turn': return [{'start_s':0.,'end_s':1.5,'left_rad_s':3.,'right_rad_s':3.},{'start_s':1.5,'end_s':6.,'left_rad_s':1.5 if direction>0 else 4.5,'right_rad_s':4.5 if direction>0 else 1.5}]
    if kind=='brake': return [{'start_s':0.,'end_s':2.5,'left_rad_s':4.,'right_rad_s':4.},{'start_s':2.5,'end_s':6.,'left_rad_s':0.,'right_rad_s':0.}]
    return [{'start_s':0.,'end_s':2.,'left_rad_s':2.,'right_rad_s':4.},{'start_s':2.,'end_s':6.,'left_rad_s':4.,'right_rad_s':2.}]

SPECS={
'F1':('straight',[(.28,0),(.28,.059),(.28,.090),(.34,0),(.34,.059),(.34,.090)]),
'F2':('arc',[(.22,.08),(.24,.11),(.27,.15),(.22,-.08),(.24,-.11),(.27,-.15)]),
'F3':('turn',[(.24,.08),(.28,.10),(.32,.14),(.24,-.08),(.28,-.10),(.32,-.14)]),
'F4':('turn',[(.25,.02),(.30,.055),(.34,.09),(.25,-.02),(.30,-.055),(.34,-.09)]),
'F5':('brake',[(.18,0),(.22,0),(.27,0),(.18,.06),(.22,.06),(.27,.06)]),
'F6':('opposite',[(.20,.05),(.25,.07),(.30,.10),(.20,-.05),(.25,-.07),(.30,-.10)]),
'F7':('straight',[(.28,0),(.28,.059),(.28,.09),(.34,0),(.34,.059),(.34,.09)]),
'F8':('turn',[(.22,.11),(.26,.14),(.30,.18),(.22,-.11),(.26,-.14),(.30,-.18)]),}

def reference_pose(segments,t=2.5,dt=.001):
 x=y=yaw=now=0.
 while now<t:
  seg=next(s for s in segments if s['start_s']<=now<s['end_s']); h=min(dt,t-now)
  v=.01*(seg['left_rad_s']+seg['right_rad_s']); w=.02*(seg['right_rad_s']-seg['left_rad_s'])/.052
  mid=yaw+w*h/2; x+=v*math.cos(mid)*h; y+=v*math.sin(mid)*h; yaw+=w*h; now+=h
 return x,y,yaw

def build():
 cells=[]
 for family in ScenarioFamily:
  kind,_=SPECS[family.value]
  for i in range(6):
   pid=f'P{i+1:02d}'; direction=1 if i<3 else -1
   commands=schedule(kind,direction); x,y,yaw=reference_pose(commands)
   offsets=(.0,.065,.105,.0,-.065,-.105) if family.value!='F8' else (.09,.12,.16,-.09,-.12,-.16)
   off=offsets[i]; x+=-math.sin(yaw)*off; y+=math.cos(yaw)*off
   cells.append({'family_id':family.value,'parameter_set_id':pid,'structural_role':(('collision_path','near_offset','safe_offset')[i%3] if family.value!='F8' else ('safe_near','safe_mid','safe_far')[i%3]),'initial_robot_pose':{'x_m':0.,'y_m':0.,'yaw_rad':0.},'obstacle':{'id':'TARGET','kind':'obstacle','center_x_m':round(x,9),'center_y_m':round(y,9),'size_x_m':.04,'size_y_m':.04},'distractors':[{'id':'DISTRACTOR','kind':'obstacle','center_x_m':.12,'center_y_m':-.28 if direction>0 else .28,'size_x_m':.05,'size_y_m':.05}] if family.value=='F7' else [],'command_schedule':commands,'turn_direction':direction,'seed':seed_for(Split.PILOT,family,pid,0),'episode_id':f'm9a-pilot-v2-{family.value.lower()}-{pid.lower()}-r00'})
 return tuple(cells)
SCENARIO_GRID=build()
def write_artifact(path:Path): path.write_text(json.dumps({'schema_version':'m9a-scenario-grid-v3','method_independent':True,'placement_rule':'command kinematics at 2.5 s plus fixed normal offset','physical_footprint_radius_m':.037,'cells':SCENARIO_GRID},indent=2,sort_keys=True)+'\n')
if __name__=='__main__':write_artifact(Path('docs/results/m9a_i1_scenario_grid.json'))
