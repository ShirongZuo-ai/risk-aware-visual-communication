"""M6-A v2 causal episode-source records; no Webots or output generation."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from decimal import Decimal,ROUND_FLOOR
import hashlib,json
from pathlib import Path
from scripts.m6a_common import VERSION as V1,METHODS,BUDGETS,PROJECT_ROOT,validate
from scripts.m6a_trusted_artifacts import M6AProjectionConfig,digest
from simulator import m5e_scenarios as primitive
VERSION='m6a-byte-fair-v2';WORLD=PROJECT_ROOT/'simulator/worlds/m5e_dataset_generator.wbt';PROGRESS=(Decimal('.20'),Decimal('.45'),Decimal('.70'),Decimal('.90'));STEP=Decimal('.032');DURATION=Decimal('6.0')
def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _schedule(scene):
 if scene in {'S1','S2','S6'}:return primitive._approach_turn_schedule()
 if scene=='S3':return primitive._turn_schedule('left')
 if scene=='S4':return primitive._turn_schedule('right')
 if scene=='S5':return primitive._disagreement_schedule()
 if scene=='S7':return primitive._partial_visibility_schedule()
 if scene=='S8':return primitive._straight_schedule()
 raise ValueError('unknown scene')
@dataclass(frozen=True)
class M6AV2EpisodeSource:
 protocol_version:str;supersedes:str;identity:dict;source_world_path:str;source_world_sha256:str;scene_generator_path:str;scene_generator_sha256:str;scene_generator_version:str;scene_config:dict;scene_config_sha256:str;timestep_s:str;duration_s:str;schedule:tuple[dict,...];schedule_sha256:str;schedule_available_time_s:str;snapshot_progress:tuple[str,...];snapshot_raw_times_s:tuple[str,...];snapshot_step_indices:tuple[int,...];snapshot_aligned_times_s:tuple[str,...];projection_config:dict;projection_config_sha256:str;methods:tuple[str,...];budgets:dict;causal_pre_run_source:bool=True;derived_from_actual_trace:bool=False;actual_future_prohibited:bool=True;combined_mask_prohibited:bool=True
 def canonical(self):return asdict(self)
 def sha256(self):return digest(self.canonical())
 def validate(self):
  if self.protocol_version!=VERSION or self.supersedes!=V1 or self.identity['split'] not in {'pilot','calibration','formal'}:raise ValueError('invalid v2 identity')
  if self.source_world_sha256.upper()!='52F79BF99E84D5264BB18AE9CDF05B976B4089AB4EA9A4018CD76A2A76D3863A' or self.timestep_s!='0.032' or self.duration_s!='6.0':raise ValueError('frozen world/timing mismatch')
  if self.snapshot_step_indices!=(38,84,131,169) or self.snapshot_aligned_times_s!=('1.216','2.688','4.192','5.408'):raise ValueError('alignment mismatch')
  if not self.causal_pre_run_source or self.derived_from_actual_trace or not self.actual_future_prohibited or not self.combined_mask_prohibited:raise ValueError('unsafe provenance')
def build_m6a_v2_episode_source(record):
 if record.get('split') not in {'pilot','calibration','formal'}:raise ValueError('not a frozen M6 identity')
 schedule=tuple(asdict(x) for x in _schedule(record['scenario_id']));previous=0
 for phase in schedule:
  if phase['start_s']!=previous or phase['end_s']<=previous:raise ValueError('invalid primitive schedule')
  previous=phase['end_s']
 if previous!=6.0:raise ValueError('schedule does not cover duration')
 raw=tuple(p*DURATION for p in PROGRESS);indices=tuple(int((x/STEP+Decimal('.5')).to_integral_value(rounding=ROUND_FLOOR)) for x in raw);aligned=tuple(Decimal(i)*STEP for i in indices)
 scene={'scene_id':record['scenario_id'],'seed':record['seed'],'initial_pose':[0.,0.,0.],'schedule':schedule,'duration_s':'6.0','primitive_authority':'simulator.m5e_scenarios'};config=M6AProjectionConfig().canonical();source=M6AV2EpisodeSource(VERSION,V1,dict(record),str(WORLD.relative_to(PROJECT_ROOT)).replace('\\','/'),_sha(WORLD),'simulator/m5e_scenarios.py',_sha(PROJECT_ROOT/'simulator/m5e_scenarios.py'),primitive.M5E_GENERATOR_VERSION,scene,digest(scene),'0.032','6.0',schedule,digest(schedule),'0.0',tuple(str(x) for x in PROGRESS),tuple(str(x) for x in raw),indices,tuple(str(x) for x in aligned),config,digest(config),METHODS,BUDGETS);source.validate();return source
def build_all(manifest_path=PROJECT_ROOT/'docs/results/m6a_manifest.json'):
 data=json.loads(Path(manifest_path).read_text(encoding='utf-8'));validate(data);return tuple(build_m6a_v2_episode_source(x) for split in ('calibration','pilot','formal') for x in data['episodes'][split])
MANIFEST_PATH=PROJECT_ROOT/'docs/results/m6a_v2_episode_source_manifest.json';LOCK_PATH=PROJECT_ROOT/'docs/results/m6a_v2_episode_source_manifest.lock.json'
def _bytes(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('utf-8')
def manifest_payload():
 records=build_all();v1=PROJECT_ROOT/'docs/results/m6a_manifest.json'
 return {'protocol_version':VERSION,'manifest_schema_version':'m6a-v2-source-manifest-v1','status':'immutable','supersedes_protocol':V1,'supersedes_manifest_sha256':_sha(v1),'v1_status':'historical_execution_incomplete','canonical_json_rule':'utf-8; sort_keys; separators=comma/colon; trailing-newline','record_sort_rule':'split calibration,pilot,formal; manifest order; scene/seed stable','source_adapter_path':'scripts/m6a_v2_episode_source.py','source_adapter_sha256':_sha(Path(__file__)),'scene_generator_path':'simulator/m5e_scenarios.py','scene_generator_sha256':_sha(PROJECT_ROOT/'simulator/m5e_scenarios.py'),'base_world_path':str(WORLD.relative_to(PROJECT_ROOT)).replace('\\','/'),'base_world_sha256':_sha(WORLD),'timestep_s':'0.032','duration_s':'6.0','snapshot_progress':['0.20','0.45','0.70','0.90'],'snapshot_step_indices':[38,84,131,169],'snapshot_aligned_times_s':['1.216','2.688','4.192','5.408'],'methods':list(METHODS),'budgets':BUDGETS,'split_counts':{'calibration':16,'pilot':8,'formal':32},'total_records':56,'actual_future_prohibited':True,'combined_mask_prohibited':True,'records':[dict(x.canonical(),source_record_sha256=x.sha256()) for x in records]}
def lock_payload(payload):
 raw=_bytes(payload);return {'lock_schema_version':'m6a-v2-source-lock-v1','protocol_version':VERSION,'status':'immutable','manifest_relative_path':'docs/results/m6a_v2_episode_source_manifest.json','manifest_sha256':hashlib.sha256(raw).hexdigest(),'canonical_byte_length':len(raw),'total_records':56,'split_counts':payload['split_counts'],'v1_manifest_sha256':payload['supersedes_manifest_sha256'],'base_world_sha256':payload['base_world_sha256'],'source_adapter_sha256':payload['source_adapter_sha256'],'scene_generator_sha256':payload['scene_generator_sha256'],'canonical_json_rule':payload['canonical_json_rule']}
def write_manifest():
 payload=manifest_payload();lock=lock_payload(payload)
 for path,value in ((MANIFEST_PATH,payload),(LOCK_PATH,lock)):
  raw=_bytes(value)
  if path.exists() and path.read_bytes()!=raw:raise FileExistsError('refusing to replace immutable v2 artifact')
  path.write_bytes(raw)
 return payload,lock
def load_and_validate_m6a_v2_manifest(manifest_path=MANIFEST_PATH,lock_path=LOCK_PATH):
 raw=Path(manifest_path).read_bytes();payload=json.loads(raw);lock=json.loads(Path(lock_path).read_text(encoding='utf-8'))
 if raw!=_bytes(payload) or hashlib.sha256(raw).hexdigest()!=lock.get('manifest_sha256') or payload.get('total_records')!=56 or payload.get('split_counts')!={'calibration':16,'pilot':8,'formal':32}:raise ValueError('invalid v2 manifest/lock')
 expected=json.loads(_bytes(manifest_payload()).decode('utf-8'))
 if payload!=expected or lock!=lock_payload(payload):raise ValueError('tampered or nonreproducible v2 manifest')
 return payload
