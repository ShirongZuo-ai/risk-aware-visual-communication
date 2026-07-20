"""Validated M6-A trusted mask artifacts; generators are intentionally pending."""
from __future__ import annotations
from dataclasses import dataclass,asdict
import hashlib,json,math
from scripts.m6a_common import VERSION
from navigation.trajectory_prediction import EPUCK_ROBOT_HALF_WIDTH_M
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
@dataclass(frozen=True)
class M6AProjectionConfig:
 horizon_s:float=2.;step_s:float=.032;footprint_half_width_m:float=EPUCK_ROBOT_HALF_WIDTH_M;corridor_rule:str='m5-risk-parameters';projection_rule:str='m5-camera-projection';clipping_rule:str='m5-clipped-polygons';width_px:int=160;height_px:int=120;rasterization_rule:str='pixel-center-max';protocol_version:str=VERSION
 def validate(self):
  if self.protocol_version!=VERSION or self.horizon_s!=2. or self.step_s!=.032 or self.width_px<=0 or self.height_px<=0:raise ValueError('invalid frozen M6-A configuration')
  if not all(math.isfinite(x) and x>0 for x in (self.horizon_s,self.step_s,self.footprint_half_width_m)):raise ValueError('nonfinite configuration')
  if not all((self.corridor_rule,self.projection_rule,self.clipping_rule,self.rasterization_rule)):raise ValueError('incomplete configuration')
 def canonical(self):self.validate();return asdict(self)
 def sha256(self):return digest(self.canonical())
@dataclass(frozen=True)
class GeneratedRiskMask:
 method:str;source_predictor:str;predictor_input_digest:str;predictor_config_digest:str;trajectory:object;trajectory_hash:str;corridor:object;corridor_hash:str;footprint_digest:str;projection_digest:str;rasterization_digest:str;mask_payload:tuple[float,...];mask_hash:str;roi_pixel_count:int;roi_area_ratio:float;empty:bool;full_frame:bool;clipped:bool;out_of_view:bool;generation_pipeline_version:str;actual_future_usage:int=0;combined_usage:int=0;raw_external_mask_usage:int=0;fallback:bool=False;replacement:bool=False;synthetic_test_only:bool=False
def create_generated_risk_mask(**k):
 pairs={'state_only_risk_roi':'state_only_predictor','command_conditioned_risk_roi':'command_conditioned_predictor'}
 if k.get('method') not in pairs or pairs[k['method']]!=k.get('source_predictor'):raise ValueError('illegal method/source')
 if any(x in str(k.get('source_predictor')) for x in ('combined','m5','oracle','actual','raw','unknown')):raise ValueError('illegal source')
 if any(not k.get(x) for x in ('predictor_input_digest','predictor_config_digest','trajectory_hash','corridor_hash','footprint_digest','projection_digest','rasterization_digest','mask_hash','generation_pipeline_version')):raise ValueError('missing provenance')
 if any(k.get(x) for x in ('actual_future_usage','combined_usage','raw_external_mask_usage','fallback','replacement')):raise ValueError('unsafe artifact')
 payload=tuple(k['mask_payload'])
 if digest(payload)!=k['mask_hash'] or digest(k['trajectory'])!=k['trajectory_hash'] or digest(k['corridor'])!=k['corridor_hash']:raise ValueError('payload hash mismatch')
 if k['roi_pixel_count']<0 or not 0<=k['roi_area_ratio']<=1 or k['roi_pixel_count']!=sum(x>0 for x in payload):raise ValueError('invalid ROI')
 return GeneratedRiskMask(**k)
