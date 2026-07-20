"""Preflight-only first-pilot launcher preparation; deliberately never launches Webots."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:sys.path.insert(0,str(PROJECT_ROOT))
from scripts.m6a_common import PROJECT_ROOT,VERSION,METHODS,BUDGETS,SNAPSHOT_PROGRESS,validate
from scripts.m6a_trusted_artifacts import M6AProjectionConfig,digest
from scripts.m6a_webots_adapter import load_m6a_runtime_config
def first_pilot(manifest_path):
 data=json.loads(Path(manifest_path).read_text(encoding='utf-8'));validate(data)
 rows=data['episodes']['pilot'];return data,sorted(rows,key=lambda x:(x['scenario_id'],x['seed'],x['episode_id']))[0]
def plan(manifest_path):
 data,item=first_pilot(manifest_path);return {'manifest_sha256':hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),'identity':item,'expected_episodes':1,'expected_snapshots':4,'expected_methods':len(METHODS),'expected_budgets':len(BUDGETS),'future_reconstruction_cases':32,'webots_started':False,'execution_authorized':False}
def build_one_identity_runtime_config(manifest_path,episode_source,*,output_root,source_world):
 data,identity=first_pilot(manifest_path);source=json.loads(Path(episode_source).read_text(encoding='utf-8'))
 required={'snapshot_times','schedule'}
 if not required<=set(source) or source.get('identity')!=identity:raise ValueError('missing or mismatched frozen episode source')
 times=source['snapshot_times']
 if len(times)!=4 or times!=sorted(times) or len(set(times))!=4:raise ValueError('invalid frozen snapshot times')
 world=Path(source_world);root=Path(output_root)
 if not world.is_file() or 'm5' in root.parts or 'pilot' in root.parts or root.exists():raise ValueError('unsafe output or source world')
 cfg={'protocol_version':VERSION,'manifest_hash':hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),'split':'pilot','scene':identity['scenario_id'],'episode_id':identity['episode_id'],'seed':identity['seed'],'snapshots':[{'snapshot_id':str(i),'timestamp_s':t} for i,t in enumerate(times)],'schedule':source['schedule'],'projection_config':M6AProjectionConfig().canonical(),'output_root':str(root),'controller':'m6a_trusted_runtime','robot_def':'EPUCK','camera':'camera','left_motor':'left wheel motor','right_motor':'right wheel motor','expected_snapshots':4,'source_world':str(world),'source_world_sha256':hashlib.sha256(world.read_bytes()).hexdigest()}
 cfg['schedule_sha256']=digest(cfg['schedule']);cfg['config_sha256']=digest(cfg);return cfg
def materialize_runtime_config(config,target):
 target=Path(target);root=target.parent
 if target.exists() or not root.is_dir() or 'm5' in target.parts or 'pilot' in target.parts:raise ValueError('unsafe config target')
 text=json.dumps(config,sort_keys=True,separators=(',',':'))+'\n';tmp=target.with_suffix(target.suffix+'.tmp')
 try:tmp.write_text(text,encoding='utf-8');tmp.replace(target)
 except Exception:
  if tmp.exists():tmp.unlink()
  raise
 return target
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=PROJECT_ROOT/'docs/results/m6a_manifest.json');p.add_argument('--dry-run',action='store_true');p.add_argument('--preflight',action='store_true');a=p.parse_args()
 if a.dry_run==a.preflight:p.error('choose exactly one of --dry-run or --preflight')
 out=plan(a.manifest);out['mode']='preflight' if a.preflight else 'dry-run';print(json.dumps(out,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
