"""Injected, Webots-import-free M6-A runtime boundary (mock-testable)."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import os
import math
import hashlib,json,math,shutil
from pathlib import Path
from scripts.m6a_dual_roi import CurrentState,ScheduleEvidence,SnapshotInput,process_m6a_snapshot,serialize_snapshot
from scripts.m6a_trusted_artifacts import M6AProjectionConfig,digest
from scripts.m6a_common import VERSION
def build_snapshot(*,manifest_hash,scene,episode_id,seed,snapshot_id,timestamp_s,state_reader,frame_reference,schedule):
 state=CurrentState(**state_reader())
 return SnapshotInput('m6a-byte-fair-v1',manifest_hash,scene,episode_id,seed,snapshot_id,timestamp_s,state,frame_reference,schedule)
@dataclass(frozen=True)
class StateSample: state:CurrentState;timestamp_s:float
@dataclass(frozen=True)
class CameraFrame: rgb:bytes;timestamp_s:float;width_px:int=160;height_px:int=120
@dataclass(frozen=True)
class M6ARuntimeConfig:
 manifest_hash:str;scene:str;episode_id:str;seed:int;snapshots:tuple[tuple[str,float],...];output_root:Path;projection_config:M6AProjectionConfig;alignment_tolerance_s:float=.032;protocol_version:str=VERSION
 def validate(self):
  if self.protocol_version!=VERSION or not self.manifest_hash or not self.scene or not self.episode_id or len(self.snapshots)!=4:raise ValueError('invalid M6-A runtime identity')
  times=[x[1] for x in self.snapshots]
  if len({x[0] for x in self.snapshots})!=4 or any(not x[0] for x in self.snapshots) or times!=sorted(times) or any(not math.isfinite(x) for x in times):raise ValueError('invalid snapshot lifecycle')
  self.projection_config.validate()
@dataclass(frozen=True)
class EpisodeRuntimeSummary:
 identity:dict;expected_snapshot_count:int;actual_snapshot_count:int;serialized_snapshot_paths:tuple[str,...];frame_hashes:tuple[str,...];method_set:tuple[str,...];actual_future_usage:int;combined_usage:int;raw_mask_usage:int;fallback:int;replacement:int;success:bool
class M6AWebotsRuntimeAdapter:
 def __init__(self,config,facade,*,state_reader,frame_reader,schedule):
  config.validate();self.config=config;self.facade=facade;self.state_reader=state_reader;self.frame_reader=frame_reader;self.schedule=schedule;self.done=[]
  if schedule.available_time_s>config.snapshots[0][1]:raise ValueError('schedule unavailable at first snapshot')
  root=Path(config.output_root).resolve()
  if not root.is_dir() or any(part.lower().startswith('m5') for part in root.parts):raise ValueError('unsafe output root')
  self.root=root
 def _canonical_write(self,path,data):path.write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
 def _capture(self,snapshot_id,target_time,simulation_time):
  if snapshot_id in self.done or len(self.done)>=len(self.config.snapshots):raise ValueError('duplicate snapshot')
  if abs(simulation_time-target_time)>self.config.alignment_tolerance_s:raise ValueError('missed snapshot target')
  state=self.state_reader();frame=self.frame_reader()
  if not isinstance(state,StateSample) or not isinstance(frame,CameraFrame) or len(frame.rgb)!=160*120*3 or frame.width_px!=160 or frame.height_px!=120:raise ValueError('unavailable or invalid state/frame')
  if max(abs(state.timestamp_s-target_time),abs(frame.timestamp_s-target_time),abs(state.timestamp_s-frame.timestamp_s))>self.config.alignment_tolerance_s:raise ValueError('state/frame timestamp misalignment')
  if self.schedule.available_time_s>target_time:raise ValueError('late predefined schedule')
  raw_dir=self.root/'raw';snapshot_dir=self.root/'snapshots'/snapshot_id;raw_dir.mkdir(exist_ok=True);(self.root/'snapshots').mkdir(exist_ok=True)
  raw_path=raw_dir/(snapshot_id+'.rgb');meta_path=raw_dir/(snapshot_id+'.json')
  if raw_path.exists() or meta_path.exists() or snapshot_dir.exists():raise FileExistsError('refusing snapshot overwrite')
  try:
   raw_path.write_bytes(frame.rgb);frame_hash=hashlib.sha256(frame.rgb).hexdigest();reference=str(raw_path.relative_to(self.root)).replace('\\','/')
   self._canonical_write(meta_path,{'frame_reference':reference,'frame_sha256':frame_hash,'width_px':160,'height_px':120,'simulation_timestamp_s':simulation_time,'state_timestamp_s':state.timestamp_s,'frame_timestamp_s':frame.timestamp_s,'target_timestamp_s':target_time,'state':asdict(state.state),'schedule_available_time_s':self.schedule.available_time_s,'schedule_sha256':digest(asdict(self.schedule))})
   item=SnapshotInput(VERSION,self.config.manifest_hash,self.config.scene,self.config.episode_id,self.config.seed,snapshot_id,target_time,state.state,reference,self.schedule)
   output=process_m6a_snapshot(item,self.config.projection_config);serialize_snapshot(output,snapshot_dir,manifest_hash=self.config.manifest_hash,protocol_version=VERSION)
  except Exception:
   for path in (raw_path,meta_path):
    if path.exists():path.unlink()
   if snapshot_dir.exists():shutil.rmtree(snapshot_dir)
   raise
  self.done.append((snapshot_id,str(snapshot_dir),frame_hash,output))
 def run(self):
  pending=list(self.config.snapshots)
  while pending:
   simulation_time=self.facade.step()
   if simulation_time is None:break
   ident,target=pending[0]
   if simulation_time>target+self.config.alignment_tolerance_s:raise ValueError('missing snapshot')
   if simulation_time>=target:self._capture(ident,target,simulation_time);pending.pop(0)
  if pending:raise ValueError('episode finalized before all snapshots')
  outputs=[x[3] for x in self.done]
  return EpisodeRuntimeSummary({'manifest_hash':self.config.manifest_hash,'scene':self.config.scene,'episode_id':self.config.episode_id,'seed':self.config.seed},len(self.config.snapshots),len(self.done),tuple(x[1] for x in self.done),tuple(x[2] for x in self.done),tuple(sorted(outputs[0].methods)),0,0,0,0,0,True)
def run_m6a_webots_episode(runtime_config,robot_facade,*,state_reader,frame_reader,predefined_schedule):
 return M6AWebotsRuntimeAdapter(runtime_config,robot_facade,state_reader=state_reader,frame_reader=frame_reader,schedule=predefined_schedule).run()
class WebotsRobotFacade:
 """Concrete Webots wrapper; constructed only after the controller's delayed import."""
 def __init__(self,robot,*,pose_reader):
  self.robot=robot;self.pose_reader=pose_reader;self.timestep_ms=robot.getBasicTimeStep();self.camera=robot.getDevice('camera')
  if not self.timestep_ms or self.camera is None:raise ValueError('required Webots devices unavailable')
  self.camera.enable(int(self.timestep_ms))
 def step(self):
  return None if self.robot.step(int(self.timestep_ms))==-1 else self.robot.getTime()
 def state_sample(self):
  pose=self.pose_reader();return StateSample(CurrentState(**pose),self.robot.getTime())
 def frame_sample(self):
  raw=self.camera.getImage();return CameraFrame(webots_bgra_to_rgb(raw,160,120),self.robot.getTime())
class WebotsCurrentStateReader:
 """Supervisor-only, current-timestep e-puck state source; never reads a trace."""
 WHEEL_RADIUS_M=.02;AXLE_LENGTH_M=.052
 def __init__(self,supervisor,*,robot_def='EPUCK',left_motor='left wheel motor',right_motor='right wheel motor'):
  self.supervisor=supervisor;self.node=supervisor.getFromDef(robot_def)
  if self.node is None:raise ValueError('M6-A robot DEF not found')
  self.translation=self.node.getField('translation');self.rotation=self.node.getField('rotation');self.left=supervisor.getDevice(left_motor);self.right=supervisor.getDevice(right_motor)
  if None in (self.translation,self.rotation,self.left,self.right):raise ValueError('M6-A pose or wheel device unavailable')
  self.last_time=None
 def __call__(self):
  t=self.supervisor.getTime()
  if self.last_time is not None and t<=self.last_time:raise ValueError('non-increasing current state timestamp')
  p=self.translation.getSFVec3f();r=self.rotation.getSFRotation()
  if len(p)!=3 or len(r)!=4 or not all(math.isfinite(x) for x in (*p,*r,t)):raise ValueError('invalid current pose')
  # Existing worlds use z-up; the axis-angle yaw is signed only for the z axis.
  if abs(r[0])>1e-9 or abs(r[1])>1e-9:raise ValueError('unsupported non-z-up robot rotation')
  yaw=r[3] if r[2]>=0 else -r[3];left=self.left.getVelocity();right=self.right.getVelocity()
  if not all(math.isfinite(x) for x in (left,right)):raise ValueError('invalid current wheel velocity')
  self.last_time=t;linear=self.WHEEL_RADIUS_M*(left+right)/2;angular=self.WHEEL_RADIUS_M*(right-left)/self.AXLE_LENGTH_M
  return StateSample(CurrentState(p[0],p[1],yaw,linear,angular),t)
def webots_bgra_to_rgb(raw,width=160,height=120):
 if not isinstance(raw,(bytes,bytearray)) or len(raw)!=width*height*4:raise ValueError('invalid Webots BGRA frame')
 out=bytearray(width*height*3)
 for i in range(width*height):
  b,g,r,_=raw[i*4:i*4+4];out[i*3:i*3+3]=bytes((r,g,b))
 return bytes(out)
def load_m6a_runtime_config(path,*,expected_manifest_hash):
 from navigation.trajectory_prediction import CommandSegment
 data=json.loads(Path(path).read_text(encoding='utf-8'))
 forbidden={'actual_future','actual_future_trajectory','combined','combined_mask','oracle','oracle_mask'}
 if data.get('split')!='pilot' or forbidden&set(data) or data.get('manifest_hash')!=expected_manifest_hash:raise ValueError('unsafe M6-A controller configuration')
 schedule=data.get('schedule',{});segments=tuple(CommandSegment(**x) for x in schedule.get('segments',[]))
 evidence=ScheduleEvidence(schedule.get('schedule_id',''),schedule.get('available_time_s'),segments)
 if not evidence.schedule_id or evidence.available_time_s is None:raise ValueError('invalid predefined schedule')
 config=M6ARuntimeConfig(data['manifest_hash'],data['scene'],data['episode_id'],data['seed'],tuple((x['snapshot_id'],x['timestamp_s']) for x in data['snapshots']),Path(data['output_root']),M6AProjectionConfig(**data.get('projection_config',{})),protocol_version=data.get('protocol_version',VERSION));config.validate()
 return config,evidence
def initialize_m6a_v2_scene_from_runtime_config(path,supervisor):
 """Controller pre-motion gate: it must succeed before devices or snapshots start."""
 from scripts.m6a_v2_scene_wiring import initialize_v2_scene_before_motion
 from scripts.run_m6a_one_identity import load_v2_runtime_config
 data=json.loads(Path(path).read_text(encoding='utf-8'));load_v2_runtime_config(data)
 return initialize_v2_scene_before_motion(data,supervisor)
def main_m6a_webots_controller():
 """Webots-only entry: host passes M6A_RUNTIME_CONFIG; no defaults or fallback."""
 config_path=os.environ.get('M6A_RUNTIME_CONFIG')
 if not config_path:return 2
 try:
  from controller import Supervisor
  from navigation.trajectory_prediction import CommandSegment
  from scripts.m6a_v2_runtime_summary import run_v2_controller_lifecycle
  runtime=json.loads(Path(config_path).read_text(encoding='utf-8'));holder={}
  def devices(supervisor,cfg):
   reader=WebotsCurrentStateReader(supervisor,robot_def='ROBOT',left_motor=cfg['left_motor'],right_motor=cfg['right_motor']);holder['reader']=reader;holder['facade']=WebotsRobotFacade(supervisor,pose_reader=lambda:asdict(reader().state))
  def episode(supervisor,cfg):
   from scripts.m6a_dual_roi import ScheduleEvidence
   schedule=ScheduleEvidence(cfg['schedule']['schedule_id'],cfg['schedule']['available_time_s'],tuple(CommandSegment(x['start_s'],x['end_s'],x['left_rad_s'],x['right_rad_s']) for x in cfg['schedule']['segments']))
   root=Path(cfg['output_root']);root.mkdir(parents=True,exist_ok=True)
   legacy=M6ARuntimeConfig(cfg['v2_manifest_sha256'],cfg['scene'],cfg['episode_id'],cfg['seed'],tuple((x['snapshot_id'],x['timestamp_s']) for x in cfg['snapshots']),root,M6AProjectionConfig(**cfg['projection_config']))
   result=run_m6a_webots_episode(legacy,holder['facade'],state_reader=holder['reader'],frame_reader=holder['facade'].frame_sample,predefined_schedule=schedule)
   return [{'snapshot_id':item['snapshot_id'],'timestamp_s':item['timestamp_s'],'path':path,'methods':list(result.method_set),'actual_future_usage':0,'combined_usage':0,'raw_mask_usage':0,'fallback':0,'replacement':0} for item,path in zip(cfg['snapshots'],result.serialized_snapshot_paths)]
  root=Path(runtime['output_root']);code,_=run_v2_controller_lifecycle(config_path,supervisor_factory=Supervisor,devices_initializer=devices,episode_runner=episode,summary_path=root/'episode_runtime_summary.json',status_path=root/'episode_runtime_status.json');return code
 except Exception:return 1
