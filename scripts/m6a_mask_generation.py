"""Controlled synthetic-ready M6-A trajectory-to-mask bridge (no Webots IO)."""
from __future__ import annotations
from scripts.m6a_dual_roi import CurrentState,ScheduleEvidence,Method,predict
from scripts.m6a_trusted_artifacts import M6AProjectionConfig,create_generated_risk_mask,digest
def _bridge(trajectory,config,method,input_digest,config_digest):
 config.validate(); values=[0.0]*(config.width_px*config.height_px)
 for p in trajectory:
  u=min(config.width_px-1,max(0,round(config.width_px/2+p.y*100)));v=min(config.height_px-1,max(0,round(config.height_px-1-p.x*100)))
  values[v*config.width_px+u]=1.0
 corridor={'radius_m':config.footprint_half_width_m,'points':[(p.x,p.y) for p in trajectory]};payload=tuple(values)
 return create_generated_risk_mask(method=method,source_predictor='state_only_predictor' if method==Method.STATE_ONLY_RISK_ROI.value else 'command_conditioned_predictor',predictor_input_digest=input_digest,predictor_config_digest=config_digest,trajectory=[p.__dict__ for p in trajectory],trajectory_hash=digest([p.__dict__ for p in trajectory]),corridor=corridor,corridor_hash=digest(corridor),footprint_digest=digest(config.footprint_half_width_m),projection_digest=digest(config.projection_rule),rasterization_digest=digest((config.width_px,config.height_px,config.rasterization_rule)),mask_payload=payload,mask_hash=digest(payload),roi_pixel_count=sum(x>0 for x in payload),roi_area_ratio=sum(x>0 for x in payload)/len(payload),empty=not any(payload),full_frame=all(payload),clipped=False,out_of_view=False,generation_pipeline_version='m6a-bridge-v1')
def generate_state_only_risk_mask(state:CurrentState,config:M6AProjectionConfig):
 t=predict(Method.STATE_ONLY_RISK_ROI,state);return _bridge(t,config,Method.STATE_ONLY_RISK_ROI.value,digest(state.__dict__),config.sha256())
def generate_command_conditioned_risk_mask(state:CurrentState,schedule:ScheduleEvidence,config:M6AProjectionConfig,*,timestamp_s:float):
 t=predict(Method.COMMAND_CONDITIONED_RISK_ROI,state,schedule=schedule,snapshot_time_s=timestamp_s);return _bridge(t,config,Method.COMMAND_CONDITIONED_RISK_ROI.value,digest((state.__dict__,schedule.__dict__)),config.sha256())
