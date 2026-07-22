"""Fail-closed ownership, authorization, and final-result gates for M6-A v2.

This module never starts a process.  The host wrapper is the only caller that
may invoke its launch-time acquisition functions.
"""
from __future__ import annotations

import json, os, socket, tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest

PILOT_ROOT = PROJECT_ROOT / "data" / "m6a" / "pilot"
CONTROL_ROOT = PROJECT_ROOT / "results" / "m6a_v2_control"
OWNER = ".m6a_v2_ownership.json"
FINAL = "m6a_v2_final_success.json"

@dataclass(frozen=True)
class ValidatedExecutionContext:
 """B2-produced authority boundary; tests may use the explicit temporary fixture."""
 authorization_id:str;authorization_sha256:str;launch_id:str;attempt_id:str;identity_id:str;scene_id:str;seed:int;launch_spec_sha256:str;runtime_config_sha256:str;prospective_attempt_root:str;validated_at_utc:str;test_fixture:bool=False
 def validate(self):
  if self.test_fixture is not True or not all(isinstance(x,str) and x for x in (self.authorization_id,self.authorization_sha256,self.launch_id,self.attempt_id,self.identity_id,self.scene_id,self.launch_spec_sha256,self.runtime_config_sha256)):raise ValueError('invalid validated execution context')
  root=validate_prospective_root(self.prospective_attempt_root,launch_id=self.launch_id,attempt_id=self.attempt_id)
  if Path(tempfile.gettempdir()).resolve() not in PILOT_ROOT.resolve().parents and PILOT_ROOT.resolve() != Path(tempfile.gettempdir()).resolve():raise ValueError('test context requires temporary pilot root')
  return root
 @classmethod
 def test_fixture_for(cls,*,launch_id,attempt_id,identity_id,scene_id,seed,launch_spec_sha256,runtime_config_sha256):
  root=attempt_root(launch_id,attempt_id)
  return cls('test-'+digest({'l':launch_id,'a':attempt_id}),digest({'l':launch_id,'a':attempt_id,'fixture':True}),launch_id,attempt_id,identity_id,scene_id,seed,launch_spec_sha256,runtime_config_sha256,str(root),_utc(),True)

def materialize_authorized_attempt(package,context,*,launcher_identity='m6a-v2-host',mode='test',prepared_package_path=None):
 """The only B2-to-attempt transition; never called by preflight or wrapper planning."""
 if mode=='test':
  if not isinstance(context,ValidatedExecutionContext):raise TypeError('TestValidatedExecutionContext required')
  root=context.validate(); auth={'authorization_id':context.authorization_id,'authorization_sha256':context.authorization_sha256,'launch_id':context.launch_id,'attempt_id':context.attempt_id,'identity_id':context.identity_id,'scene_id':context.scene_id,'seed':context.seed,'launch_spec_sha256':context.launch_spec_sha256,'nonce':digest({'test_context':context.authorization_id})}
 elif mode=='production':
  from scripts.m6a_v2_execution_authorization import ExternallyValidatedExecutionContext,build_expected_authorization_binding
  if not isinstance(context,ExternallyValidatedExecutionContext):raise TypeError('ExternallyValidatedExecutionContext required')
  if prepared_package_path is None:raise ValueError('production materialization requires authoritative prepared package path')
  binding=build_expected_authorization_binding(prepared_package_path,package['preflight_report_path']);context.validate(binding); root=Path(context.data['prospective_attempt_root']);auth={'authorization_id':context.data['authorization_id'],'authorization_sha256':context.data['authorization_artifact_digest'],'launch_id':context.data['launch_id'],'attempt_id':context.data['attempt_id'],'identity_id':context.data['identity_id'],'scene_id':package['scene_id'],'seed':package['seed'],'launch_spec_sha256':context.data['launch_spec_digest'],'nonce':context.data['nonce']}
 else: raise ValueError('unknown materialization mode')
 if package.get('launch_id')!=auth['launch_id'] or package.get('attempt_id')!=auth['attempt_id'] or package.get('identity_id')!=auth['identity_id'] or package.get('prospective_attempt_root')!=str(root):raise ValueError('package/context mismatch')
 paths=attempt_path_plan(auth['launch_id'],auth['attempt_id'],auth['identity_id'],auth['scene_id'],auth['seed'])['artifacts']
 if Path(root).exists() or any(Path(paths[key]).exists() for key in ('ownership_marker','consumption_record','process_evidence','final_marker')):raise ValueError('attempt or execution evidence already exists')
 ownership=acquire_ownership(root,auth,launcher_identity=launcher_identity)
 owned={'schema_version':'m6a-v2-owned-attempt-context-v1','attempt_root':str(root),'ownership':ownership,'launch_id':auth['launch_id'],'attempt_id':auth['attempt_id'],'identity_id':auth['identity_id'],'authorization_id':auth['authorization_id'],'nonce':auth['nonce'],'execution_mode':mode,'test_fixture':mode=='test'};owned['canonical_digest']=digest(owned);return owned

def _load_ownership(path, root, *, owner_identity):
 value=json.loads(Path(path).read_text(encoding='utf-8'))
 if value.get('sha256')!=digest({k:v for k,v in value.items() if k!='sha256'}) or value.get('output_root')!=str(Path(root)) or value.get('launcher_identity')!=owner_identity or value.get('state')!='owned_pre_spawn':raise ValueError('invalid ownership evidence')
 return value

def _validate_owned_context(value, *, mode):
 if not isinstance(value,dict) or value.get('schema_version')!='m6a-v2-owned-attempt-context-v1' or value.get('canonical_digest')!=digest({k:v for k,v in value.items() if k!='canonical_digest'}) or value.get('execution_mode')!=mode or value.get('test_fixture')!=(mode=='test'):raise ValueError('invalid owned attempt context')
 root=validate_prospective_root(value['attempt_root'],launch_id=value['launch_id'],attempt_id=value['attempt_id']) if not Path(value['attempt_root']).exists() else Path(value['attempt_root']).resolve()
 if not _under(root, PILOT_ROOT) or mode=='test' and Path(tempfile.gettempdir()).resolve() not in PILOT_ROOT.resolve().parents and PILOT_ROOT.resolve()!=Path(tempfile.gettempdir()).resolve():raise ValueError('unsafe owned attempt root')
 ownership=_load_ownership(root/OWNER,root,owner_identity='m6a-v2-host')
 if ownership['launch_id']!=value['launch_id'] or ownership['attempt_id']!=value['attempt_id'] or ownership['identity_id']!=value['identity_id'] or ownership['authorization_id']!=value['authorization_id'] or ownership['sha256']!=value['ownership']['sha256']:raise ValueError('owned context mismatch')
 return root,ownership

def load_owned_attempt_context(value,*,mode='production'):
 """Reload the persisted ownership marker and return one validated owned context."""
 root,ownership=_validate_owned_context(value,mode=mode)
 loaded=dict(value);loaded['attempt_root']=str(root);loaded['ownership']=ownership
 if loaded.get('canonical_digest')!=digest({k:v for k,v in loaded.items() if k!='canonical_digest'}):raise ValueError('owned context reload digest')
 return loaded

def launch_owned_attempt(owned_attempt_context, process_runner, *, mode='test'):
 """Launch boundary for an already-owned attempt; never calls completion or Webots directly."""
 from scripts.m6a_v2_runtime_evidence import persist_process_evidence,load_process_evidence
 root,ownership=_validate_owned_context(owned_attempt_context,mode=mode)
 paths=attempt_path_plan(owned_attempt_context['launch_id'],owned_attempt_context['attempt_id'],owned_attempt_context['identity_id'],ownership['scene'],ownership['seed'])['artifacts']
 consumption=Path(paths['consumption_record']); evidence=Path(paths['process_evidence']); final=Path(paths['final_marker'])
 if final.exists():raise ValueError('attempt already finalized')
 if consumption.exists() and evidence.exists():return {'schema_version':'m6a-v2-launched-attempt-context-v1','idempotent':True,'consumption':load_consumption(consumption,owned_attempt_context),'process_evidence':load_process_evidence(evidence,_identity(owned_attempt_context))}
 if consumption.exists() or evidence.exists():raise ValueError('incomplete launch evidence; retry forbidden')
 if not hasattr(process_runner,'run'):raise TypeError('process runner with run() required')
 result=process_runner.run(root=root,path_plan=paths,owned_attempt_context=owned_attempt_context)
 required={'launch_performed','started_at_utc','ended_at_utc','return_code','timed_out','termination_state','stdout_path','stderr_path','process_identity'}
 if not isinstance(result,dict) or not required <= set(result) or not isinstance(result['launch_performed'],bool):raise ValueError('invalid process runner result')
 if not result['launch_performed']:raise RuntimeError('process did not launch; authorization remains unconsumed')
 auth={'authorization_id':owned_attempt_context['authorization_id'],'authorization_sha256':ownership['authorization_sha256'],'launch_id':owned_attempt_context['launch_id'],'attempt_id':owned_attempt_context['attempt_id'],'identity_id':owned_attempt_context['identity_id'],'scene_id':ownership['scene'],'seed':ownership['seed'],'launch_spec_sha256':ownership['launch_spec_sha256'],'nonce':owned_attempt_context['nonce']}
 consumed=consume_authorization(auth,ownership,launch_performed_at_utc=result['started_at_utc'],path=consumption)
 persisted=persist_process_evidence(evidence,_identity(owned_attempt_context),result['stdout_path'],result['stderr_path'],launch_performed=True,process_identity=result['process_identity'],timed_out=result['timed_out'],termination_state=result['termination_state'],started_at_utc=result['started_at_utc'],ended_at_utc=result['ended_at_utc'],return_code=result['return_code'],owner_identity=ownership['launcher_identity'],authorization_id=auth['authorization_id'],nonce=auth['nonce'])
 loaded=load_process_evidence(evidence,_identity(owned_attempt_context));reloaded=load_consumption(consumption,owned_attempt_context)
 launched={'schema_version':'m6a-v2-launched-attempt-context-v1','launch_id':auth['launch_id'],'attempt_id':auth['attempt_id'],'identity_id':auth['identity_id'],'authorization_id':auth['authorization_id'],'nonce':auth['nonce'],'owner_identity':ownership['launcher_identity'],'attempt_root':str(root),'ownership_digest':ownership['sha256'],'consumption_path':str(consumption),'consumption_digest':reloaded['sha256'],'process_evidence_path':str(evidence),'process_evidence_digest':loaded['sha256'],'launch_performed':True,'process_outcome':{'return_code':result['return_code'],'timed_out':result['timed_out'],'termination_state':result['termination_state']},'started_at_utc':result['started_at_utc'],'ended_at_utc':result['ended_at_utc'],'execution_mode':mode};launched['canonical_digest']=digest(launched);return launched

def _identity(context):return {'launch_id':context['launch_id'],'attempt_id':context['attempt_id'],'identity_id':context['identity_id'],'scene_id':context['ownership']['scene'],'seed':context['ownership']['seed']}

def _canon(x): return (json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)+"\n").encode()
def _utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _new(path: Path, value: dict):
 path.parent.mkdir(parents=True, exist_ok=True)
 value=dict(value); value["sha256"]=digest(value)
 fd=os.open(str(path), os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 with os.fdopen(fd,"wb") as f:f.write(_canon(value))
 return value
def _under(path: Path, root: Path):
 return path.is_absolute() and path.resolve().is_relative_to(root.resolve())
def attempt_root(launch_id,attempt_id):
 if not all(isinstance(x,str) and x and x.replace("-","").isalnum() for x in (launch_id,attempt_id)):raise ValueError("unsafe launch/attempt id")
 return (PILOT_ROOT/launch_id/attempt_id).resolve()
def attempt_path_plan(launch_id,attempt_id,identity_id,scene_id,seed):
 root=attempt_root(launch_id,attempt_id); items={'ownership_marker':root/OWNER,'ownership_terminal':root/'.m6a_v2_ownership_terminal.json','stdout':root/'host_stdout.log','stderr':root/'host_stderr.log','process_evidence':root/'host_process_result.json','runtime_summary':root/'episode_runtime_summary.json','runtime_status':root/'episode_runtime_status.json','runtime_diagnostic':root/'episode_runtime_failure.json','runtime_manifest':root/'runtime_artifacts.json','snapshot_root':root/'snapshots','codec_root':root/'codec','codec_aggregate':root/'codec_aggregate.json','aggregate_validation':root/'codec_aggregate_validation.json','joint_report':root/'joint_validation.json','final_marker':root/FINAL,'consumption_record':CONTROL_ROOT/'consumption'/(digest({'launch':launch_id,'attempt':attempt_id})+'.json')}
 if len({str(x.resolve()).lower() for x in items.values()})!=len(items):raise ValueError('artifact path alias')
 for name,path in items.items():
  if name!='consumption_record' and not _under(path,root):raise ValueError('artifact path escape')
 return {'schema_version':'m6a-v2-attempt-path-plan-v1','launch_id':launch_id,'attempt_id':attempt_id,'identity_id':identity_id,'scene_id':scene_id,'seed':seed,'attempt_root':str(root),'artifacts':{k:str(v.resolve()) for k,v in items.items()}}
def validate_prospective_root(root,*,launch_id,attempt_id):
 root=Path(root)
 if root != attempt_root(launch_id,attempt_id) or root.exists() or not _under(root,PILOT_ROOT) or CONTROL_ROOT.resolve() in root.parents:raise ValueError("unsafe or reused attempt root")
 if any(part in {".",".."} for part in root.parts):raise ValueError("path traversal")
 parent=root.parent
 while parent != PILOT_ROOT.parent:
  if parent.exists() and parent.is_symlink():raise ValueError("symlink escape")
  parent=parent.parent
 return root
def acquire_ownership(root,authorization,*,launcher_identity="m6a-v2-host"):
 root=validate_prospective_root(root,launch_id=authorization["launch_id"],attempt_id=authorization["attempt_id"])
 root.mkdir(parents=True,exist_ok=False)
 marker={"schema_version":"m6a-v2-ownership-v1","launch_id":authorization["launch_id"],"attempt_id":authorization["attempt_id"],"authorization_id":authorization["authorization_id"],"identity_id":authorization["identity_id"],"scene":authorization["scene_id"],"seed":authorization["seed"],"launch_spec_sha256":authorization["launch_spec_sha256"],"authorization_sha256":authorization["authorization_sha256"],"output_root":str(root),"launcher_identity":launcher_identity,"host":socket.gethostname(),"acquired_at_utc":_utc(),"state":"owned_pre_spawn","launch_performed":False,"webots_started":False,"scientific_result":False}
 try:return _new(root/OWNER,marker)
 except Exception:
  if root.is_dir() and not any(root.iterdir()):root.rmdir()
  raise
def build_authorization(package,*,head,branch,attempt_id,valid_minutes=30):
 launch_id=digest({"package":package["package_sha256"],"attempt":attempt_id})
 root=attempt_root(launch_id,attempt_id)
 value={"schema_version":"m6a-v2-authorization-v2","authorization_id":digest({"launch":launch_id,"attempt":attempt_id,"head":head}),"launch_id":launch_id,"attempt_id":attempt_id,"identity_id":package["identity_id"],"scene_id":package["scene_id"],"seed":package["seed"],"repository_root":str(PROJECT_ROOT),"authorized_head":head,"branch":branch,"prepared_package_sha256":package["package_sha256"],"launch_spec_sha256":package["launch_spec_sha256"],"runtime_config_sha256":package["runtime_config_sha256"],"temporary_world_sha256":package["temporary_world_sha256"],"controller_sha256":package["controller_sha256"],"executable":package["executable"],"argv_sha256":package["argv_sha256"],"manifest_sha256":package["manifest_sha256"],"lock_sha256":package["lock_sha256"],"owned_output_root":str(root),"purpose":"single-identity M6-A v2 pilot smoke","authorized_at_utc":_utc(),"valid_until_utc":(datetime.now(timezone.utc)+timedelta(minutes=valid_minutes)).replace(microsecond=0).isoformat(),"execution_authorized":True,"consumed":False,"launch_performed":False,"webots_started":False,"scientific_result":False,"test_fixture":False}
 value["authorization_sha256"]=digest(value); return value
def validate_authorization(a,package,*,head,branch):
 if a.get("authorization_sha256")!=digest({k:v for k,v in a.items() if k!="authorization_sha256"}) or not a.get("execution_authorized") or a.get("test_fixture") or a.get("consumed") or a.get("launch_performed") or a.get("scientific_result") or a.get("prepared_package_sha256")!=package["package_sha256"] or a.get("authorized_head")!=head or a.get("branch")!=branch or datetime.fromisoformat(a["valid_until_utc"])<=datetime.now(timezone.utc):raise PermissionError("invalid authorization")
 validate_prospective_root(a["owned_output_root"],launch_id=a["launch_id"],attempt_id=a["attempt_id"]);return a
def consume_authorization(a,ownership,*,launch_performed_at_utc=None,path=None):
 path=Path(path) if path is not None else CONTROL_ROOT/"consumption"/(a["authorization_id"]+".json")
 root=a.get('owned_output_root',ownership.get('output_root'))
 return _new(path,{"schema_version":"m6a-v2-consumption-v1","authorization_id":a["authorization_id"],"authorization_sha256":a["authorization_sha256"],"nonce":a.get('nonce','legacy-no-nonce'),"launch_id":a["launch_id"],"attempt_id":a["attempt_id"],"identity_id":a["identity_id"],"output_root":root,"launch_spec_sha256":a["launch_spec_sha256"],"ownership_sha256":ownership["sha256"],"owner_identity":ownership['launcher_identity'],"launch_performed_at_utc":launch_performed_at_utc or _utc(),"consumed_at_utc":_utc(),"state":"consumed_post_launch"})
def load_consumption(path,context):
 value=json.loads(Path(path).read_text(encoding='utf-8'))
 if value.get('sha256')!=digest({k:v for k,v in value.items() if k!='sha256'}) or any(value.get(k)!=context[k] for k in ('authorization_id','launch_id','attempt_id','identity_id')) or value.get('nonce')!=context['nonce'] or value.get('state')!='consumed_post_launch':raise ValueError('invalid consumption evidence')
 return value
def write_final_marker(root,evidence):
 required={"launch_id","attempt_id","authorization_id","ownership_sha256","consumption_sha256","process_sha256","runtime_sha256","snapshot_validation_sha256","b5_sha256","aggregate_sha256","joint_validator_sha256","manifest_sha256","lock_sha256"}
 if not required <= set(evidence) or evidence.get("joint_pass") is not True:raise ValueError("joint validation required")
 return _new(Path(root)/FINAL,{"schema_version":"m6a-v2-final-success-v1",**evidence,"created_at_utc":_utc(),"scientific_result":False})

def _load_final_marker(path, launched):
 value=json.loads(Path(path).read_text(encoding='utf-8'))
 if value.get('sha256')!=digest({k:v for k,v in value.items() if k!='sha256'}) or any(value.get(k)!=launched[k] for k in ('launch_id','attempt_id','authorization_id')) or value.get('scientific_result') is not False:raise ValueError('invalid final marker')
 return value

def _terminal(path, launched, ownership, final):
 return _new(path,{'schema_version':'m6a-v2-ownership-terminal-v1','launch_id':launched['launch_id'],'attempt_id':launched['attempt_id'],'authorization_id':launched['authorization_id'],'owner_identity':ownership['launcher_identity'],'ownership_sha256':ownership['sha256'],'final_marker_sha256':final['sha256'],'state':'completed','completed_at_utc':_utc()})

def finalize_launched_attempt(launched_attempt_context, completion_spec, *, mode='test', completion_runner=None):
 """Close a launched attempt only after reloading launch evidence; never launches a process."""
 value=launched_attempt_context
 if not isinstance(value,dict) or value.get('schema_version')!='m6a-v2-launched-attempt-context-v1' or value.get('canonical_digest')!=digest({k:v for k,v in value.items() if k!='canonical_digest'}) or value.get('execution_mode')!=mode:raise ValueError('invalid launched attempt context')
 root=Path(value['attempt_root']).resolve(); ownership=_load_ownership(root/OWNER,root,owner_identity=value['owner_identity']);identity={'launch_id':value['launch_id'],'attempt_id':value['attempt_id'],'identity_id':value['identity_id'],'scene_id':ownership['scene'],'seed':ownership['seed']}
 paths=attempt_path_plan(value['launch_id'],value['attempt_id'],value['identity_id'],ownership['scene'],ownership['seed'])['artifacts']; consumption=load_consumption(paths['consumption_record'],value)
 from scripts.m6a_v2_runtime_evidence import load_process_evidence
 process=load_process_evidence(paths['process_evidence'],identity)
 if process['sha256']!=value['process_evidence_digest'] or consumption['sha256']!=value['consumption_digest']:raise ValueError('launched evidence mismatch')
 final_path,terminal_path=Path(paths['final_marker']),Path(paths['ownership_terminal'])
 if final_path.exists():
  final=_load_final_marker(final_path,value)
  if terminal_path.exists():return {'schema_version':'m6a-v2-finalized-attempt-result-v1','idempotent':True,'final_marker':final,'terminal':json.loads(terminal_path.read_text())}
  terminal=_terminal(terminal_path,value,ownership,final);return {'schema_version':'m6a-v2-finalized-attempt-result-v1','idempotent':True,'final_marker':final,'terminal':terminal}
 if terminal_path.exists():raise ValueError('completed ownership without final marker')
 if process['return_code']!=0 or process['timed_out'] or process['termination_state']!='exited':raise RuntimeError('process not eligible for completion')
 if completion_runner is None:
  from scripts.m6a_v2_pilot_completion import process_completed_pilot_launch
  completion_runner=process_completed_pilot_launch
 result=completion_runner(completion_spec,{'started':True,'timed_out':False,'interrupted':False},owned_output_root=root)
 evidence=result.get('final_evidence') if isinstance(result,dict) else None
 if not result.get('integration_valid') or not isinstance(evidence,dict):raise ValueError('completion did not provide validated final evidence')
 evidence={**evidence,'launch_id':value['launch_id'],'attempt_id':value['attempt_id'],'authorization_id':value['authorization_id'],'ownership_sha256':ownership['sha256'],'consumption_sha256':consumption['sha256'],'process_sha256':process['sha256'],'joint_pass':True}
 final=write_final_marker(root,evidence);final=_load_final_marker(final_path,value);terminal=_terminal(terminal_path,value,ownership,final)
 finalized={'schema_version':'m6a-v2-finalized-attempt-result-v1','launch_id':value['launch_id'],'attempt_id':value['attempt_id'],'identity_id':value['identity_id'],'authorization_id':value['authorization_id'],'attempt_root':str(root),'owner_identity':ownership['launcher_identity'],'consumption_digest':consumption['sha256'],'process_evidence_digest':process['sha256'],'runtime_manifest_digest':evidence['runtime_sha256'],'aggregate_validation_digest':evidence['b5_sha256'],'joint_report_digest':evidence['joint_validator_sha256'],'final_marker_digest':final['sha256'],'final_outcome':'success','completed_at_utc':terminal['completed_at_utc'],'execution_mode':mode};finalized['canonical_digest']=digest(finalized);return finalized
