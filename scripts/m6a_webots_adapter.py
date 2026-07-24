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
from scripts.m6a_v2_runtime_summary import (FailureStage,Lifecycle,LifecycleState,
 build_runtime_failure_status,emit_runtime_failure_status,run_controller_stage)
def build_snapshot(*,manifest_hash,scene,episode_id,seed,snapshot_id,timestamp_s,state_reader,frame_reference,schedule):
 state=CurrentState(**state_reader())
 return SnapshotInput('m6a-byte-fair-v1',manifest_hash,scene,episode_id,seed,snapshot_id,timestamp_s,state,frame_reference,schedule)
@dataclass(frozen=True)
class StateSample: state:CurrentState;timestamp_s:float
@dataclass(frozen=True)
class CameraFrame: rgb:bytes;timestamp_s:float;width_px:int=160;height_px:int=120;camera_context:dict|None=None
@dataclass(frozen=True)
class M6ARuntimeConfig:
 manifest_hash:str;scene:str;episode_id:str;seed:int;snapshots:tuple[tuple[str,float],...];output_root:Path;projection_config:M6AProjectionConfig;alignment_tolerance_s:float=.032;protocol_version:str=VERSION;split:str='pilot'
 def validate(self):
  if self.protocol_version!=VERSION or not self.manifest_hash or not self.scene or not self.episode_id or len(self.snapshots)!=4:raise ValueError('invalid M6-A runtime identity')
  times=[x[1] for x in self.snapshots]
  if len({x[0] for x in self.snapshots})!=4 or any(not x[0] for x in self.snapshots) or times!=sorted(times) or any(not math.isfinite(x) for x in times):raise ValueError('invalid snapshot lifecycle')
  self.projection_config.validate()
@dataclass(frozen=True)
class EpisodeRuntimeSummary:
 identity:dict;expected_snapshot_count:int;actual_snapshot_count:int;serialized_snapshot_paths:tuple[str,...];frame_hashes:tuple[str,...];method_set:tuple[str,...];actual_future_usage:int;combined_usage:int;raw_mask_usage:int;fallback:int;replacement:int;success:bool;snapshot_records:tuple[dict,...]=()
class M6AWebotsRuntimeAdapter:
 def __init__(self,config,facade,*,state_reader,frame_reader,schedule):
  config.validate();self.config=config;self.facade=facade;self.state_reader=state_reader;self.frame_reader=frame_reader;self.schedule=schedule;self.done=[]
  if schedule.available_time_s>config.snapshots[0][1] or not schedule.segments or schedule.segments[-1].end_offset_s<config.snapshots[-1][1]:raise ValueError('schedule unavailable or incomplete')
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
   if self.config.split=='formal' and frame.camera_context is None:raise ValueError('formal snapshot requires authoritative camera context')
   self._canonical_write(meta_path,{'schema_version':'m6a-v2-raw-snapshot-metadata-v2','snapshot_id':snapshot_id,'snapshot_index':len(self.done),'scene':self.config.scene,'seed':self.config.seed,'frame_reference':reference,'frame_sha256':frame_hash,'width_px':160,'height_px':120,'simulation_timestamp_s':simulation_time,'state_timestamp_s':state.timestamp_s,'frame_timestamp_s':frame.timestamp_s,'target_timestamp_s':target_time,'state':asdict(state.state),'schedule_id':self.schedule.schedule_id,'schedule_available_time_s':self.schedule.available_time_s,'schedule_segments':[asdict(x) for x in self.schedule.segments],'schedule_sha256':digest(asdict(self.schedule)),'camera_context':frame.camera_context})
   item=SnapshotInput(VERSION,self.config.manifest_hash,self.config.scene,self.config.episode_id,self.config.seed,snapshot_id,target_time,state.state,reference,self.schedule)
   output=process_m6a_snapshot(item,self.config.projection_config);serialize_snapshot(output,snapshot_dir,manifest_hash=self.config.manifest_hash,protocol_version=VERSION)
  except Exception:
   for path in (raw_path,meta_path):
    if path.exists():path.unlink()
   if snapshot_dir.exists():shutil.rmtree(snapshot_dir)
   raise
  record={'schema_version':'m6a-v2-authoritative-snapshot-record-v1','snapshot_id':snapshot_id,'snapshot_index':len(self.done),'scene':self.config.scene,'seed':self.config.seed,'capture_time_s':simulation_time,'raw_rgb_path':str(raw_path.resolve()),'metadata_json_path':str(meta_path.resolve()),'serialized_snapshot_path':str(snapshot_dir.resolve()),'producer_identity':'m6a_webots_runtime_adapter','producer_frame_hash':frame_hash}
  if not raw_path.is_file() or not meta_path.is_file() or not snapshot_dir.is_dir():raise ValueError('snapshot artifact contract')
  self.done.append((snapshot_id,str(snapshot_dir),frame_hash,output,record))
 def run(self):
  pending=list(self.config.snapshots)
  try:
   simulation_time=None
   while pending:
    simulation_time=self.facade.step()
    if simulation_time is None:break
    ident,target=pending[0]
    if simulation_time>target+self.config.alignment_tolerance_s:raise ValueError('missing snapshot')
    if simulation_time>=target:self._capture(ident,target,simulation_time);pending.pop(0)
   episode_end=self.schedule.segments[-1].end_offset_s
   while not pending and simulation_time is not None and simulation_time<episode_end:
    simulation_time=self.facade.step()
    if simulation_time is None:break
  finally:
   if hasattr(self.facade,'stop'):self.facade.stop()
  if pending:raise ValueError('episode finalized before all snapshots')
  if simulation_time is None or simulation_time+self.config.alignment_tolerance_s<self.schedule.segments[-1].end_offset_s:raise ValueError('episode finalized before frozen schedule end')
  outputs=[x[3] for x in self.done]
  records=tuple(x[4] for x in self.done)
  return EpisodeRuntimeSummary({'manifest_hash':self.config.manifest_hash,'scene':self.config.scene,'episode_id':self.config.episode_id,'seed':self.config.seed},len(self.config.snapshots),len(self.done),tuple(x['serialized_snapshot_path'] for x in records),tuple(x['producer_frame_hash'] for x in records),tuple(sorted(outputs[0].methods)),0,0,0,0,0,True,records)
def run_m6a_webots_episode(runtime_config,robot_facade,*,state_reader,frame_reader,predefined_schedule):
 return M6AWebotsRuntimeAdapter(runtime_config,robot_facade,state_reader=state_reader,frame_reader=frame_reader,schedule=predefined_schedule).run()
class WebotsRobotFacade:
 """Concrete Webots wrapper; constructed only after the controller's delayed import."""
 def __init__(self,robot,*,pose_reader,command_actuator=None):
  self.robot=robot;self.pose_reader=pose_reader;self.command_actuator=command_actuator;self.timestep_ms=robot.getBasicTimeStep();self.camera=robot.getDevice('camera')
  if not self.timestep_ms or self.camera is None:raise ValueError('required Webots devices unavailable')
  self.camera.enable(int(self.timestep_ms))
 def step(self):
  if self.command_actuator is not None:self.command_actuator.apply(self.robot.getTime())
  return None if self.robot.step(int(self.timestep_ms))==-1 else self.robot.getTime()
 def stop(self):
  if self.command_actuator is not None:self.command_actuator.stop()
 def state_sample(self):
  pose=self.pose_reader();return StateSample(CurrentState(**pose),self.robot.getTime())
 def frame_sample(self):
  from simulator.adapters.webots_camera_adapter import read_camera_snapshot
  from scripts.m6_tcobr import camera_context_from_snapshot
  raw=self.camera.getImage();context=None
  if all(hasattr(self.camera,name) for name in ('getWidth','getHeight','getFov','getNear')):
   context=camera_context_from_snapshot(read_camera_snapshot(self.robot,self.camera))
  return CameraFrame(webots_bgra_to_rgb(raw,160,120),self.robot.getTime(),camera_context=context)
class WebotsCurrentStateReader:
 """Supervisor-only, current-timestep e-puck state source; never reads a trace."""
 WHEEL_RADIUS_M=.02;AXLE_LENGTH_M=.052
 def __init__(self,supervisor,*,robot_def='EPUCK',left_motor='left wheel motor',right_motor='right wheel motor'):
  self.supervisor=supervisor;self.node=supervisor.getFromDef(robot_def)
  if self.node is None:raise ValueError('M6-A robot DEF not found')
  self.left=supervisor.getDevice(left_motor);self.right=supervisor.getDevice(right_motor)
  if self.left is None or self.right is None or not callable(getattr(self.node,'getPosition',None)) or not callable(getattr(self.node,'getOrientation',None)):raise ValueError('M6-A pose or wheel device unavailable')
  self.last_time=None
 def __call__(self):
  t=self.supervisor.getTime()
  if self.last_time is not None and t<=self.last_time:raise ValueError('non-increasing current state timestamp')
  p=self.node.getPosition();orientation=self.node.getOrientation()
  if len(p)!=3 or len(orientation)!=9 or not all(math.isfinite(x) for x in (*p,*orientation,t)):raise ValueError('invalid current pose')
  # Use the same z-up orientation-matrix yaw extraction as the accepted M2-M5 controllers.
  yaw=math.atan2(orientation[3],orientation[0]);left=self.left.getVelocity();right=self.right.getVelocity()
  if not all(math.isfinite(x) for x in (left,right)):raise ValueError('invalid current wheel velocity')
  self.last_time=t;linear=self.WHEEL_RADIUS_M*(left+right)/2;angular=self.WHEEL_RADIUS_M*(right-left)/self.AXLE_LENGTH_M
  return StateSample(CurrentState(p[0],p[1],yaw,linear,angular),t)
class WebotsScheduleActuator:
 """Apply the frozen predefined schedule before each Webots step."""
 def __init__(self,supervisor,schedule,*,left_motor,right_motor,required_until_s):
  self.left=supervisor.getDevice(left_motor);self.right=supervisor.getDevice(right_motor);self.schedule=schedule
  if self.left is None or self.right is None or not schedule.segments or schedule.available_time_s>0:raise ValueError('unavailable schedule actuator inputs')
  previous=0.0
  for segment in schedule.segments:
   values=(segment.start_offset_s,segment.end_offset_s,segment.left_wheel_command_rad_s,segment.right_wheel_command_rad_s)
   if not all(math.isfinite(x) for x in values) or abs(segment.start_offset_s-previous)>1e-9 or segment.end_offset_s<=segment.start_offset_s:raise ValueError('invalid schedule actuator coverage')
   previous=segment.end_offset_s
  if previous+1e-9<required_until_s:raise ValueError('schedule does not cover final snapshot')
  self.left.setPosition(float('inf'));self.right.setPosition(float('inf'));self.left.setVelocity(0.0);self.right.setVelocity(0.0)
 def apply(self,simulation_time_s):
  if not math.isfinite(simulation_time_s):raise ValueError('invalid actuation time')
  segment=next((item for item in self.schedule.segments if item.start_offset_s<=simulation_time_s<item.end_offset_s),None)
  if segment is None:raise ValueError('no frozen command at simulation time')
  self.left.setVelocity(segment.left_wheel_command_rad_s);self.right.setVelocity(segment.right_wheel_command_rad_s)
 def stop(self):
  self.left.setVelocity(0.0);self.right.setVelocity(0.0)
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
def _schedule_from_runtime(cfg):
 from navigation.trajectory_prediction import CommandSegment
 return ScheduleEvidence(cfg['schedule']['schedule_id'],cfg['schedule']['available_time_s'],tuple(CommandSegment(x['start_s'],x['end_s'],x['left_rad_s'],x['right_rad_s']) for x in cfg['schedule']['segments']))
def _emit_unpersisted_controller_failure(stage,error,*,lifecycle=None,runtime=None,authoritative_root=None):
 transitions=list(lifecycle.transitions) if lifecycle is not None else []
 already_failed=bool(transitions and transitions[-1]==LifecycleState.FAILED.value)
 previous=LifecycleState(transitions[-2]) if already_failed and len(transitions)>1 else (None if already_failed else (lifecycle.state if lifecycle is not None else None))
 failed=Lifecycle(LifecycleState.FAILED,transitions+([] if already_failed else [LifecycleState.FAILED.value]))
 payload=build_runtime_failure_status(failed,error,failure_stage=stage,last_completed_state=previous,runtime_config=runtime,authoritative_root=authoritative_root)
 emit_runtime_failure_status(payload)
def run_configured_m6a_controller(config_path,*,supervisor_factory,lifecycle_runner=None):
 """Run one bound controller lifecycle, then request Webots process exit."""
 from scripts.m6a_v2_runtime_summary import run_v2_controller_lifecycle
 supervisor=None;runtime=None;lifecycle=None;outer_stage=FailureStage.SUPERVISOR_INITIALIZATION;code=1
 try:
  supervisor=supervisor_factory();holder={'supervisor':supervisor};outer_stage=FailureStage.CONFIG_LOADING
  runtime=json.loads(Path(config_path).read_text(encoding='utf-8'));schedule=_schedule_from_runtime(runtime)
  lifecycle_runner=lifecycle_runner or run_v2_controller_lifecycle
  def make_supervisor():return supervisor
  def devices(supervisor,cfg):
   reader=run_controller_stage(FailureStage.STATE_READER_SETUP,lambda:WebotsCurrentStateReader(supervisor,robot_def='ROBOT',left_motor=cfg['left_motor'],right_motor=cfg['right_motor']))
   actuator=run_controller_stage(FailureStage.ACTUATOR_SCHEDULE_SETUP,lambda:WebotsScheduleActuator(supervisor,schedule,left_motor=cfg['left_motor'],right_motor=cfg['right_motor'],required_until_s=cfg['snapshots'][-1]['timestamp_s']))
   facade=run_controller_stage(FailureStage.CAMERA_SETUP,lambda:WebotsRobotFacade(supervisor,pose_reader=lambda:asdict(reader().state),command_actuator=actuator))
   holder['reader']=reader;holder['facade']=facade
  def episode(supervisor,cfg):
   root=Path(cfg['output_root']);root.mkdir(parents=True,exist_ok=True)
   legacy=M6ARuntimeConfig(cfg['v2_manifest_sha256'],cfg['scene'],cfg['episode_id'],cfg['seed'],tuple((x['snapshot_id'],x['timestamp_s']) for x in cfg['snapshots']),root,M6AProjectionConfig(**cfg['projection_config']),split=cfg['split'])
   result=run_m6a_webots_episode(legacy,holder['facade'],state_reader=holder['reader'],frame_reader=holder['facade'].frame_sample,predefined_schedule=schedule)
   return [{'snapshot_id':item['snapshot_id'],'timestamp_s':item['timestamp_s'],'path':record['serialized_snapshot_path'],'snapshot_record':record,'methods':list(result.method_set),'actual_future_usage':0,'combined_usage':0,'raw_mask_usage':0,'fallback':0,'replacement':0} for item,record in zip(cfg['snapshots'],result.snapshot_records)]
  paths=runtime.get('attempt_paths')
  if not isinstance(paths,dict):raise ValueError('authoritative runtime paths required')
  outer_stage=FailureStage.RUNTIME_OUTPUT_PATH_VALIDATION
  code,lifecycle=lifecycle_runner(config_path,supervisor_factory=make_supervisor,devices_initializer=devices,episode_runner=episode,summary_path=paths['runtime_summary'],status_path=paths['runtime_status'],diagnostic_path=paths['runtime_diagnostic'],runtime_manifest_path=paths['runtime_manifest'])
 except Exception as error:
  root=Path(runtime['output_root']) if isinstance(runtime,dict) and runtime.get('output_root') else None
  _emit_unpersisted_controller_failure(outer_stage,error,lifecycle=lifecycle,runtime=runtime,authoritative_root=root);code=1
 finally:
  if supervisor is not None:
   try:supervisor.simulationQuit(code)
   except Exception as error:
    root=Path(runtime['output_root']) if isinstance(runtime,dict) and runtime.get('output_root') else None
    _emit_unpersisted_controller_failure(FailureStage.CONTROLLED_SHUTDOWN,error,lifecycle=lifecycle,runtime=runtime,authoritative_root=root);code=1
 return code
def main_m6a_webots_controller():
 """Webots-only entry: host passes bound config/project paths; no fallback."""
 config_path=os.environ.get('M6A_RUNTIME_CONFIG')
 if not config_path:return 2
 try:
  from controller import Supervisor
  return run_configured_m6a_controller(config_path,supervisor_factory=Supervisor)
 except Exception as error:
  _emit_unpersisted_controller_failure(FailureStage.SUPERVISOR_INITIALIZATION,error);return 1
