"""Engineering/Pilot/Calibration batch runner. Formal paths are rejected."""
from controller import Supervisor
import json,math,os
from pathlib import Path
R=.037;EPS=1e-6
robot=Supervisor();dt=int(robot.getBasicTimeStep());gp=Path(os.environ['M9B_GRID']);outdir=Path(os.environ['M9B_OUTPUT']);grid=json.loads(gp.read_text())
if grid['split']=='formal' or 'formal' in str(outdir).lower():
 if os.environ.get('M9B_FORMAL_AUTHORIZATION')!='M9B-FORMAL20260814ZS01':raise RuntimeError('M9-B Formal is sealed')
selfn=robot.getSelf();tf=selfn.getField('translation');rf=selfn.getField('rotation');children=robot.getRoot().getField('children')
left=robot.getDevice('left wheel motor');right=robot.getDevice('right wheel motor');left.setPosition(float('inf'));right.setPosition(float('inf'));outdir.mkdir(parents=True,exist_ok=True)
def pd(p):return {'x_m':p.point[0],'y_m':p.point[1],'z_m':p.point[2],'associated_node_id':p.node_id}
for cfg in grid['cells']:
 pose=cfg['initial_robot_pose'];tf.setSFVec3f([pose['x_m'],pose['y_m'],0]);rf.setSFRotation([0,0,1,pose['yaw_rad']]);selfn.resetPhysics()
 names=[]
 for k,o in enumerate([cfg['obstacle'],*cfg['distractors']]):
  name=f"M9B_{k}";names.append(name);children.importMFNodeFromString(-1,f'DEF {name} Solid {{ translation {o["center_x_m"]} {o["center_y_m"]} 0.03 children [ Shape {{ geometry Box {{ size {o["size_x_m"]} {o["size_y_m"]} 0.06 }} }} ] boundingObject Box {{ size {o["size_x_m"]} {o["size_y_m"]} 0.06 }} locked TRUE }}')
 targets=[(n,robot.getFromDef(n),o) for n,o in zip(names,[cfg['obstacle'],*cfg['distractors']])];rows=[]
 for step in range(188):
  t=step*dt/1000; seg=next((s for s in cfg['command_schedule'] if s['start_s']<=t<s['end_s']),None);lc=seg['left_rad_s'] if seg else 0.;rc=seg['right_rad_s'] if seg else 0.;left.setVelocity(lc);right.setVelocity(rc)
  if robot.step(dt)==-1:raise RuntimeError('Webots stopped')
  pos=selfn.getPosition();ori=selfn.getOrientation();vel=selfn.getVelocity();rp=[pd(p) for p in selfn.getContactPoints(True)];sets=[];matched=[];nearest={};cls=[]
  for name,node,o in targets:
   pts=[pd(p) for p in node.getContactPoints(True)];ds=[math.dist((a['x_m'],a['y_m'],a['z_m']),(b['x_m'],b['y_m'],b['z_m'])) for a in rp for b in pts];near=min(ds) if ds else None;nearest[name]=near
   sets.append({'root_def':name,'root_node_id':node.getId(),'kind':'obstacle','raw_contact_point_count':len(pts),'points':pts})
   if near is not None and near<=EPS:matched.append(name)
   dx=max(abs(pos[0]-o['center_x_m'])-o['size_x_m']/2,0);dy=max(abs(pos[1]-o['center_y_m'])-o['size_y_m']/2,0);cls.append(math.hypot(dx,dy)-R)
  rows.append({'schema_version':'m9b-step-v1','study':'m9b-confirmatory-v1','purpose':cfg['purpose'],'split':cfg['split'],'episode_id':cfg['episode_id'],'scenario_family':cfg['family_id'],'parameter_set_id':cfg['parameter_set_id'],'seed':cfg['seed'],'timestep_index':step,'timestamp_s':robot.getTime(),'basic_timestep_s':dt/1000,'robot_state':{'x_m':pos[0],'y_m':pos[1],'yaw_rad':math.atan2(ori[3],ori[0]),'linear_velocity_m_s':math.hypot(vel[0],vel[1]),'angular_velocity_rad_s':vel[5]},'applied_command':{'left_wheel_rad_s':lc,'right_wheel_rad_s':rc},'actual_physical_clearance_m':min(cls),'contact_matching':{'epsilon_contact_m':EPS,'nearest_distance_by_def_m':nearest,'matched_counterpart_defs':matched,'validated_pair_contact':bool(matched)},'raw_contact_observation':{'raw_contact_point_count':len(rp),'points':rp},'eligible_counterpart_contact_sets':sets})
  
 p=outdir/(cfg['episode_id']+'.jsonl');p.write_text(''.join(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n' for x in rows),encoding='utf-8',newline='\n')
 left.setVelocity(0);right.setVelocity(0)
 for name,_,_ in targets: robot.getFromDef(name).remove()
 robot.step(dt)
 print('M9B_DONE',cfg['episode_id'],flush=True)
robot.simulationQuit(0)
