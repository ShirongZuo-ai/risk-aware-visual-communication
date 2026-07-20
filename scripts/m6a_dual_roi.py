"""Strict, Webots-independent M6-A dual-ROI preparation API.

This module intentionally accepts no actual-future data and exposes no combined
mask mode. Webots capture will call this boundary in a later phase.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib, json
from typing import Iterable
import math
from navigation.trajectory_prediction import CommandSegment, EPUCK_ROBOT_HALF_WIDTH_M, TrajectoryPoint, predict_command_conditioned_trajectory, predict_state_only_trajectory
from risk_map.image_risk_map import Mask2D
from scripts.m6a_common import VERSION
from pathlib import Path

HORIZON_S=2.0; STEP_S=0.032
class Method(str,Enum):
 STATE_ONLY_RISK_ROI='state_only_risk_roi'; COMMAND_CONDITIONED_RISK_ROI='command_conditioned_risk_roi'
FORBIDDEN_MODES={'combined','planned_state_combined','oracle','actual_future','m5_risk_roi'}
@dataclass(frozen=True)
class CurrentState: x:float; y:float; yaw_rad:float; linear_velocity_m_s:float; angular_velocity_rad_s:float
@dataclass(frozen=True)
class ScheduleEvidence: schedule_id:str; available_time_s:float; segments:tuple[CommandSegment,...]
def _hash(value:object)->str: return hashlib.sha256(json.dumps(value,sort_keys=True,default=lambda x:asdict(x),separators=(',',':')).encode()).hexdigest()
def _reject(payload:dict|None)->None:
 if payload and any(key in payload for key in ('actual_future_trajectory','future_trace','future_pose','combined_mask','oracle_mask')): raise ValueError('actual-future or combined input is forbidden in M6-A')
def predict(method:Method,state:CurrentState,*,schedule:ScheduleEvidence|None=None,snapshot_time_s:float=0.0,forbidden:dict|None=None)->tuple[TrajectoryPoint,...]:
 _reject(forbidden)
 if method is Method.STATE_ONLY_RISK_ROI:
  if schedule is not None: raise ValueError('state-only must not receive a command schedule')
  return tuple(predict_state_only_trajectory(**asdict(state),horizon_s=HORIZON_S,step_s=STEP_S))
 if method is not Method.COMMAND_CONDITIONED_RISK_ROI: raise ValueError('unsupported M6-A method')
 if schedule is None or not schedule.segments: raise ValueError('command-conditioned requires a legal schedule')
 if schedule.available_time_s>snapshot_time_s: raise ValueError('schedule was not available at decision time')
 return tuple(predict_command_conditioned_trajectory(x=state.x,y=state.y,yaw_rad=state.yaw_rad,command_segments=schedule.segments,horizon_s=HORIZON_S,step_s=STEP_S))
def select_mask(method:Method,*,state_mask:Mask2D|None=None,command_mask:Mask2D|None=None,mode:str|None=None)->Mask2D:
 if mode in FORBIDDEN_MODES: raise ValueError('combined/oracle mode is forbidden in M6-A')
 if method is Method.STATE_ONLY_RISK_ROI and state_mask is not None and command_mask is None:return state_mask
 if method is Method.COMMAND_CONDITIONED_RISK_ROI and command_mask is not None and state_mask is None:return command_mask
 raise ValueError('methods must select exactly their own independent mask')
def provenance(*,method:Method,state:CurrentState,trajectory:Iterable[TrajectoryPoint],mask:Mask2D,manifest_hash:str,scene:str,episode_id:str,seed:int,snapshot_id:str,snapshot_time_s:float,schedule:ScheduleEvidence|None=None)->dict:
 points=tuple(trajectory); selected=select_mask(method,state_mask=mask if method is Method.STATE_ONLY_RISK_ROI else None,command_mask=mask if method is Method.COMMAND_CONDITIONED_RISK_ROI else None)
 return {'protocol_version':VERSION,'manifest_sha256':manifest_hash,'scene':scene,'episode_id':episode_id,'seed':seed,'snapshot_id':snapshot_id,'snapshot_timestamp_s':snapshot_time_s,'method':method.value,'allowed_input_fields':['current_state']+(['predefined_future_command_schedule'] if method is Method.COMMAND_CONDITIONED_RISK_ROI else []),'forbidden_input_count':0,'current_state_digest':_hash(asdict(state)),'command_schedule_digest':None if schedule is None else _hash(asdict(schedule)),'schedule_available_at_decision':None if schedule is None else schedule.available_time_s<=snapshot_time_s,'horizon_s':HORIZON_S,'step_s':STEP_S,'footprint_half_width_m':EPUCK_ROBOT_HALF_WIDTH_M,'risk_projection_parameters':'shared M5 geometry/projection/rasterization configuration','trajectory_sha256':_hash([asdict(p) for p in points]),'mask_sha256':_hash(selected.values),'roi_pixel_count':selected.nonzero_pixel_count,'roi_area_ratio':selected.nonzero_pixel_count/(selected.width_px*selected.height_px),'empty_mask':selected.nonzero_pixel_count==0,'full_mask':selected.nonzero_pixel_count==selected.width_px*selected.height_px,'clipped_mask':False,'actual_future_usage_count':0,'combined_mask_usage_count':0,'fallback':False,'replacement':False}

@dataclass(frozen=True)
class SnapshotInput:
 protocol_version:str; manifest_hash:str; scene:str; episode_id:str; seed:int; snapshot_id:str; timestamp_s:float; state:CurrentState; frame_reference:str; schedule:ScheduleEvidence
def process_m6a_snapshot(item:SnapshotInput,projection_config)->dict:
 """Generate the only two M6-A production masks from allowed snapshot inputs.

 This deliberately has no mask parameters: callers cannot supply raw, M5,
 combined, oracle, or actual-future masks through the production boundary.
 """
 from scripts.m6a_mask_generation import generate_command_conditioned_risk_mask,generate_state_only_risk_mask
 from scripts.m6a_trusted_artifacts import GeneratedRiskMask,digest
 if not isinstance(item,SnapshotInput) or item.protocol_version!=VERSION: raise ValueError('invalid M6-A snapshot input')
 if not item.manifest_hash or not item.scene or not item.episode_id or not item.snapshot_id or not item.frame_reference: raise ValueError('incomplete snapshot metadata')
 if not math.isfinite(item.timestamp_s): raise ValueError('invalid snapshot timestamp')
 projection_config.validate()
 state=generate_state_only_risk_mask(item.state,projection_config)
 command=generate_command_conditioned_risk_mask(item.state,item.schedule,projection_config,timestamp_s=item.timestamp_s)
 expected={Method.STATE_ONLY_RISK_ROI.value:'state_only_predictor',Method.COMMAND_CONDITIONED_RISK_ROI.value:'command_conditioned_predictor'}
 config_digests={
  'horizon_digest':digest(projection_config.horizon_s),'step_digest':digest(projection_config.step_s),
  'footprint_digest':digest(projection_config.footprint_half_width_m),'corridor_digest':digest(projection_config.corridor_rule),
  'projection_digest':digest(projection_config.projection_rule),'rasterization_digest':digest((projection_config.width_px,projection_config.height_px,projection_config.rasterization_rule)),
 }
 for artifact in (state,command):
  if not isinstance(artifact,GeneratedRiskMask) or expected.get(artifact.method)!=artifact.source_predictor: raise ValueError('trusted method/source pairing failed')
  if artifact.predictor_config_digest!=projection_config.sha256(): raise ValueError('projection configuration mismatch')
  if any((artifact.actual_future_usage,artifact.combined_usage,artifact.raw_external_mask_usage,artifact.fallback,artifact.replacement)): raise ValueError('unsafe trusted artifact')
 if state.footprint_digest!=config_digests['footprint_digest'] or command.footprint_digest!=config_digests['footprint_digest'] or state.projection_digest!=config_digests['projection_digest'] or command.projection_digest!=config_digests['projection_digest'] or state.rasterization_digest!=config_digests['rasterization_digest'] or command.rasterization_digest!=config_digests['rasterization_digest']: raise ValueError('shared bridge configuration mismatch')
 methods={Method.STATE_ONLY_RISK_ROI.value:state,Method.COMMAND_CONDITIONED_RISK_ROI.value:command}
 if set(methods)!=set(expected): raise ValueError('M6-A requires exactly two independent methods')
 return {'snapshot':{'manifest_hash':item.manifest_hash,'scene':item.scene,'episode_id':item.episode_id,'seed':item.seed,'snapshot_id':item.snapshot_id,'timestamp_s':item.timestamp_s},'frame_reference':item.frame_reference,'methods':methods,'comparison':{'shared_current_state_digest':_hash(asdict(item.state)),'shared_projection_config_digest':projection_config.sha256(),**config_digests,'allowed_input_difference':['predictor identity','predefined_future_command_schedule'],'actual_future_usage_count':0,'combined_usage_count':0,'raw_mask_usage_count':0,'fallback_count':0,'replacement_count':0}}
def serialize_snapshot(output:dict,target:Path)->None:
 if 'm5' in target.parts: raise ValueError('M5 output roots are forbidden')
 if target.exists(): raise FileExistsError('refusing overwrite')
 for method,data in output['methods'].items():
  path=target/method; path.mkdir(parents=True); (path/'output.json').write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
