"""Persistent, non-scientific prepared launch packages for the sole M6-A v2 pilot."""
from __future__ import annotations
import hashlib,json,tempfile,shutil
from pathlib import Path
from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import MANIFEST_PATH,LOCK_PATH
from scripts.m6a_v2_execution_safety import CONTROL_ROOT,attempt_root,attempt_path_plan,validate_prospective_root
from scripts.m6a_v2_launch_spec import resolve_webots_executable,CONTROLLER_PATH,_sha256
from scripts.m6a_v2_scene_wiring import materialize_m6a_temporary_world
from scripts.run_m6a_one_identity import build_one_identity_runtime_config,materialize_runtime_config
def _write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError('immutable package exists')
 p.write_bytes((json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode())
def build_prepared_launch_package(*,head,branch,attempt_id,package_root=CONTROL_ROOT/'prepared'):
 # Stable candidate seed; package digest is computed after all immutable inputs are materialized.
 base=Path(package_root).resolve()/attempt_id
 if base.exists() or base.is_symlink():raise ValueError('unsafe package path')
 provisional='m6a'+digest({'head':head,'attempt':attempt_id,'identity':'m6a_pilot_s1_seed600100'})[:32]
 root=attempt_root(provisional,attempt_id);validate_prospective_root(root,launch_id=provisional,attempt_id=attempt_id);paths=attempt_path_plan(provisional,attempt_id,'m6a_pilot_s1_seed600100','S1',600100)
 runtime=build_one_identity_runtime_config(MANIFEST_PATH,LOCK_PATH,output_root=root);runtime['attempt_paths']={k:v for k,v in paths['artifacts'].items() if k not in {'consumption_record','ownership_marker','stdout','stderr','process_evidence','final_marker'}};runtime['config_sha256']=digest({k:v for k,v in runtime.items() if k!='config_sha256'})
 base.mkdir(parents=True)
 config=materialize_runtime_config(runtime,base/'runtime_config.json')
 with tempfile.TemporaryDirectory(prefix='m6a-package-world-') as d:
  temp=materialize_m6a_temporary_world(runtime,Path(d)/'prepared.wbt'); world=base/'prepared.wbt';shutil.copyfile(temp.temporary_world_path,world)
 exe=resolve_webots_executable()
 spec={'schema_version':'m6a-v2-production-launch-spec-v3','head':head,'branch':branch,'launch_id':provisional,'attempt_id':attempt_id,'identity':{'episode_id':runtime['episode_id'],'scene':runtime['scene'],'seed':runtime['seed']},'preflight_workspace_root':str(base.resolve()),'prospective_attempt_root':str(root),'prospective_attempt_path_plan':paths,'path_plan':paths,'owned_root':str(root),'runtime_config':{'path':str(config.resolve()),'sha256':_sha256(config)},'temporary_world':{'path':str(world.resolve()),'sha256':_sha256(world)},'controller':{'path':str(CONTROLLER_PATH.resolve()),'sha256':_sha256(CONTROLLER_PATH)},'webots':exe.__dict__,'argv':[exe.path,'--batch','--mode=fast',str(world.resolve())],'environment':{'M6A_RUNTIME_CONFIG':str(config.resolve())},'timeout_s':75,'graceful_termination_s':10,'expected':{'episodes':1,'snapshots':4,'methods':2,'budgets':4,'future_cases':32},'manifest_sha256':runtime['v2_manifest_sha256'],'lock_sha256':runtime['v2_lock_sha256'],'execution_authorized':False,'webots_started':False}
 spec['launch_spec_sha256']=digest(spec)
 package={'schema_version':'m6a-v2-prepared-launch-package-v2','kind':'local-control-evidence-not-runtime-result','head':head,'branch':branch,'launch_id':provisional,'attempt_id':attempt_id,'identity_id':runtime['episode_id'],'scene_id':runtime['scene'],'seed':runtime['seed'],'preflight_workspace_root':str(base.resolve()),'preflight_report_path':str((base/'fresh_preflight_report.json').resolve()),'prospective_attempt_root':str(root),'prospective_attempt_path_plan':paths,'launch_spec':spec,'path_plan':paths,'expected_evidence':{k:{'path':v,'required':True,'producer':'runtime-or-host'} for k,v in paths['artifacts'].items()},'launch_spec_sha256':spec['launch_spec_sha256'],'runtime_config_sha256':spec['runtime_config']['sha256'],'temporary_world_sha256':spec['temporary_world']['sha256'],'controller_sha256':spec['controller']['sha256'],'executable':spec['webots'],'argv_sha256':digest(spec['argv']),'manifest_sha256':runtime['v2_manifest_sha256'],'lock_sha256':runtime['v2_lock_sha256'],'planned_output_root':str(root),'authorization_generated':False,'launch_performed':False,'webots_started':False,'scientific_result':False}
 package['package_sha256']=digest(package);_write(base/'package.json',package);return base/'package.json',package
def load_prepared_launch_package(path):
 raw=Path(path).read_bytes();p=json.loads(raw)
 if raw!=(json.dumps(p,sort_keys=True,separators=(',',':'))+'\n').encode() or p.get('package_sha256')!=digest({k:v for k,v in p.items() if k!='package_sha256'}):raise ValueError('package digest')
 s=p['launch_spec'];validate_prospective_root(s['prospective_attempt_root'],launch_id=s['launch_id'],attempt_id=s['attempt_id'])
 if p.get('preflight_workspace_root')!=str(Path(path).parent.resolve()) or not Path(p.get('preflight_report_path','')).resolve().is_relative_to(Path(p['preflight_workspace_root']).resolve()) or p.get('prospective_attempt_root')!=s['prospective_attempt_root'] or p['preflight_workspace_root']==p['prospective_attempt_root'] or Path(p['prospective_attempt_root']).exists():raise ValueError('preflight/attempt boundary')
 for v in ('runtime_config','temporary_world','controller'):
  x=Path(s[v]['path']); key='sha256';
  if not x.is_file() or _sha256(x)!=s[v][key]:raise ValueError('package input hash')
 return p
