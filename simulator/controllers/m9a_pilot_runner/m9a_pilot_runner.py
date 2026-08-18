"""M9-A pilot-only dense runner driven by one frozen JSON configuration."""
from controller import Supervisor
import json, math, os
from pathlib import Path

RADIUS=0.037; EPS=1e-6
robot=Supervisor(); dt=int(robot.getBasicTimeStep()); cfg=json.loads(Path(os.environ['M9A_PILOT_CONFIG']).read_text())
self_node=robot.getSelf(); translation=self_node.getField('translation'); rotation=self_node.getField('rotation')
pose=cfg['initial_robot_pose']; translation.setSFVec3f([pose['x_m'],pose['y_m'],0]); rotation.setSFRotation([0,0,1,pose['yaw_rad']]); self_node.resetPhysics()
children=robot.getRoot().getField('children')
for obstacle in [cfg['obstacle'],*cfg['distractors']]:
    sx=obstacle['size_x_m']; sy=obstacle['size_y_m']; cx=obstacle['center_x_m']; cy=obstacle['center_y_m']; name=obstacle['id']
    children.importMFNodeFromString(-1,f'DEF {name} Solid {{ translation {cx} {cy} 0.03 children [ Shape {{ geometry Box {{ size {sx} {sy} 0.06 }} }} ] boundingObject Box {{ size {sx} {sy} 0.06 }} locked TRUE }}')
targets=[(o['id'],robot.getFromDef(o['id'])) for o in [cfg['obstacle'],*cfg['distractors']]]
left=robot.getDevice('left wheel motor');right=robot.getDevice('right wheel motor');left.setPosition(float('inf'));right.setPosition(float('inf'))
out=Path(os.environ['M9A_PILOT_OUTPUT']);out.parent.mkdir(parents=True,exist_ok=True); records=[]
def command(t):
    for s in cfg['command_schedule']:
        if s['start_s'] <= t < s['end_s']: return s['left_rad_s'],s['right_rad_s']
    return 0.,0.
def point_dict(p): return {'x_m':p.point[0],'y_m':p.point[1],'z_m':p.point[2],'associated_node_id':p.node_id}
for step in range(188):
    t=step*dt/1000; lc,rc=command(t);left.setVelocity(lc);right.setVelocity(rc)
    if robot.step(dt)==-1: break
    pos=self_node.getPosition();ori=self_node.getOrientation();vel=self_node.getVelocity();rpts=[point_dict(p) for p in self_node.getContactPoints(True)]
    sets=[]; matched=[]; nearest={}
    for name,node in targets:
        pts=[point_dict(p) for p in node.getContactPoints(True)]; distances=[math.dist((a['x_m'],a['y_m'],a['z_m']),(b['x_m'],b['y_m'],b['z_m'])) for a in rpts for b in pts]; near=min(distances) if distances else None
        sets.append({'root_def':name,'root_node_id':node.getId(),'kind':'obstacle','raw_contact_point_count':len(pts),'points':pts});nearest[name]=near
        if near is not None and near<=EPS: matched.append(name)
    clearances=[]
    for o in [cfg['obstacle'],*cfg['distractors']]:
        dx=max(abs(pos[0]-o['center_x_m'])-o['size_x_m']/2,0);dy=max(abs(pos[1]-o['center_y_m'])-o['size_y_m']/2,0);clearances.append(math.hypot(dx,dy)-RADIUS)
    records.append({'schema_version':'m9a-pilot-step-v1','purpose':cfg.get('purpose','pilot_feasibility'),'split':cfg.get('split','pilot'),'protocol_version':'m9a-p-v2','episode_id':cfg['episode_id'],'scenario_family':cfg['family_id'],'parameter_set_id':cfg['parameter_set_id'],'seed':cfg['seed'],'timestep_index':step,'timestamp_s':robot.getTime(),'basic_timestep_s':dt/1000,'robot_state':{'x_m':pos[0],'y_m':pos[1],'yaw_rad':math.atan2(ori[3],ori[0]),'linear_velocity_m_s':math.hypot(vel[0],vel[1]),'angular_velocity_rad_s':vel[5]},'applied_command':{'left_wheel_rad_s':lc,'right_wheel_rad_s':rc},'obstacles':[{'obstacle_id':n,'node_id':node.getId()} for n,node in targets],'robot_footprint':{'identity':'webots-r2025a-epuck-collision-cylinder-v1','physical_radius_m':RADIUS,'predictor_uncertainty_corridor_radius_m':.037592257},'raw_contact_observation':{'raw_contact_point_count':len(rpts),'points':rpts},'eligible_counterpart_contact_sets':sets,'contact_matching':{'epsilon_contact_m':EPS,'nearest_distance_by_def_m':nearest,'matched_counterpart_defs':sorted(matched),'validated_pair_contact':bool(matched)},'actual_physical_clearance_m':min(clearances),'provenance':{'purpose':cfg.get('purpose','pilot_feasibility'),'git_commit':os.environ['M9A_GIT_HEAD'],'webots_version':'R2025a'}})
with out.open('w',encoding='utf-8',newline='\n') as h:
    for r in records:h.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
robot.simulationQuit(0)
