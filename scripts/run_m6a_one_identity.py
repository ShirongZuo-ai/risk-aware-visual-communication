"""Preflight-only first-pilot launcher preparation; deliberately never launches Webots."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:sys.path.insert(0,str(PROJECT_ROOT))
from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import MANIFEST_PATH,LOCK_PATH,load_and_validate_m6a_v2_manifest
def first_pilot(manifest_path=MANIFEST_PATH,lock_path=LOCK_PATH):
 data=load_and_validate_m6a_v2_manifest(manifest_path,lock_path);return data,next(x for x in data['records'] if x['identity']['split']=='pilot')
def plan(manifest_path=MANIFEST_PATH,lock_path=LOCK_PATH):
 data,item=first_pilot(manifest_path,lock_path);return {'v2_manifest_sha256':hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),'source_record_sha256':item['source_record_sha256'],'identity':item['identity'],'expected_episodes':1,'expected_snapshots':4,'expected_methods':2,'expected_budgets':4,'future_reconstruction_cases':32,'webots_started':False,'execution_authorized':False}
def build_one_identity_runtime_config(v2_manifest_path=MANIFEST_PATH,v2_lock_path=LOCK_PATH,*,output_root):
 data,record=first_pilot(v2_manifest_path,v2_lock_path);root=Path(output_root)
 if root.exists() or any(x.lower().startswith('m5') for x in root.parts):raise ValueError('unsafe preflight output root')
 schedule={'schedule_id':record['identity']['episode_id']+'-pre-run','available_time_s':0.0,'segments':record['schedule']}
 cfg={'protocol_version':'m6a-byte-fair-v2','v2_manifest_path':str(Path(v2_manifest_path).resolve()),'v2_manifest_sha256':hashlib.sha256(Path(v2_manifest_path).read_bytes()).hexdigest(),'v2_lock_path':str(Path(v2_lock_path).resolve()),'v2_lock_sha256':hashlib.sha256(Path(v2_lock_path).read_bytes()).hexdigest(),'v1_supersedes_manifest_sha256':data['supersedes_manifest_sha256'],'source_record_sha256':record['source_record_sha256'],'split':'pilot','scene':record['identity']['scenario_id'],'episode_id':record['identity']['episode_id'],'seed':record['identity']['seed'],'snapshots':[{'snapshot_id':str(i),'timestamp_s':float(t)} for i,t in enumerate(record['snapshot_aligned_times_s'])],'schedule':schedule,'schedule_sha256':digest(schedule),'projection_config':record['projection_config'],'projection_config_sha256':record['projection_config_sha256'],'source_world':record['source_world_path'],'source_world_sha256':record['source_world_sha256'],'methods':record['methods'],'budgets':record['budgets'],'expected_snapshots':4,'expected_methods':2,'expected_budgets':4,'expected_future_cases':32,'controller':'m6a_trusted_runtime','robot_def':'ROBOT','camera':'camera','left_motor':'left wheel motor','right_motor':'right wheel motor','output_root':str(root),'actual_future_prohibited':True,'combined_mask_prohibited':True}
 cfg['config_sha256']=digest(cfg);return cfg
def load_v2_runtime_config(config):
 if {'actual_future','actual_future_trajectory','combined','combined_mask','oracle','oracle_mask'}&set(config) or config.get('protocol_version')!='m6a-byte-fair-v2' or config.get('config_sha256')!=digest({k:v for k,v in config.items() if k!='config_sha256'}):raise ValueError('invalid v2 runtime config')
 data,record=first_pilot(Path(config['v2_manifest_path']),Path(config['v2_lock_path']))
 expected_snapshots=[{'snapshot_id':str(i),'timestamp_s':float(t)} for i,t in enumerate(record['snapshot_aligned_times_s'])]
 if (config.get('v2_manifest_sha256')!=hashlib.sha256(Path(config['v2_manifest_path']).read_bytes()).hexdigest() or config.get('v2_lock_sha256')!=hashlib.sha256(Path(config['v2_lock_path']).read_bytes()).hexdigest() or config.get('source_record_sha256')!=record['source_record_sha256'] or config.get('identity') is not None or config.get('split')!='pilot' or config.get('scene')!=record['identity']['scenario_id'] or config.get('episode_id')!=record['identity']['episode_id'] or config.get('seed')!=record['identity']['seed'] or config.get('snapshots')!=expected_snapshots or config.get('schedule')!={'schedule_id':record['identity']['episode_id']+'-pre-run','available_time_s':0.0,'segments':record['schedule']} or config.get('schedule_sha256')!=digest(config['schedule']) or config.get('projection_config')!=record['projection_config'] or config.get('projection_config_sha256')!=record['projection_config_sha256'] or config.get('source_world')!=record['source_world_path'] or config.get('source_world_sha256')!=record['source_world_sha256'] or config.get('methods')!=record['methods'] or config.get('budgets')!=record['budgets'] or config.get('actual_future_prohibited') is not True or config.get('combined_mask_prohibited') is not True):raise ValueError('v2 source mismatch')
 return config
def materialize_runtime_config(config,target):
 target=Path(target);root=target.parent
 if target.exists() or not root.is_dir() or 'm5' in target.parts or 'pilot' in target.parts:raise ValueError('unsafe config target')
 text=json.dumps(config,sort_keys=True,separators=(',',':'))+'\n';tmp=target.with_suffix(target.suffix+'.tmp')
 try:
  tmp.write_text(text,encoding='utf-8');tmp.replace(target)
  load_v2_runtime_config(json.loads(target.read_text(encoding='utf-8')))
 except Exception:
  if tmp.exists():tmp.unlink()
  if target.exists():target.unlink()
  raise
 return target
def main():
 p=argparse.ArgumentParser();p.add_argument('--v2-manifest',type=Path,default=MANIFEST_PATH);p.add_argument('--v2-lock',type=Path,default=LOCK_PATH);p.add_argument('--preflight-root',type=Path);p.add_argument('--dry-run',action='store_true');p.add_argument('--preflight',action='store_true');a=p.parse_args()
 if a.dry_run==a.preflight:p.error('choose exactly one of --dry-run or --preflight')
 out=plan(a.v2_manifest,a.v2_lock);out['mode']='preflight' if a.preflight else 'dry-run'
 if a.preflight:
  if a.preflight_root is None:p.error('--preflight-root is required for --preflight')
  from scripts.m6a_v2_launch_spec import build_one_identity_launch_spec
  spec=build_one_identity_launch_spec(a.v2_manifest,a.v2_lock,preflight_root=a.preflight_root)
  out['launch_spec']=spec
 print(json.dumps(out,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
