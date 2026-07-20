"""Injected, Webots-import-free M6-A runtime boundary (mock-testable)."""
from __future__ import annotations
from dataclasses import asdict,dataclass
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
