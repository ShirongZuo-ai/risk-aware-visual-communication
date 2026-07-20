"""Strict, Webots-independent M6-A dual-ROI preparation API.

This module intentionally accepts no actual-future data and exposes no combined
mask mode. Webots capture will call this boundary in a later phase.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib, json
from typing import Iterable
from navigation.trajectory_prediction import CommandSegment, EPUCK_ROBOT_HALF_WIDTH_M, TrajectoryPoint, predict_command_conditioned_trajectory, predict_state_only_trajectory
from risk_map.image_risk_map import Mask2D
from scripts.m6a_common import VERSION

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
