"""Controlled host orchestration.  Real execution is rejected unless separately authorized."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_launch_spec import validate_launch_spec
from scripts.m6a_v2_pilot_completion import process_completed_pilot_launch

class OwnedPopenBackend:
 """Minimal shell-free backend; callers must pass a valid launch-scoped authorization."""
 def start(self,argv,env,cwd):
  if not isinstance(argv,list) or not argv or not Path(argv[0]).is_absolute():raise ValueError('argv must start with absolute executable')
  return subprocess.Popen(argv,shell=False,cwd=cwd,env={**__import__('os').environ,**env},stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def build_launch_authorization(launch_spec,*,attempt_id,execution_authorized=False):
 value={'schema_version':'m6a-v2-launch-authorization-v1','launch_id':digest({'marker':launch_spec['owner_sha256'],'spec':launch_spec['launch_spec_sha256']}),'identity_id':launch_spec['identity']['episode_id'],'scene_id':launch_spec['identity']['scene'],'seed':launch_spec['identity']['seed'],'attempt_id':attempt_id,'launch_spec_sha256':launch_spec['launch_spec_sha256'],'runtime_config_sha256':launch_spec['runtime_config']['sha256'],'temporary_world_sha256':launch_spec['temporary_world']['temporary_world_sha256'],'argv_sha256':digest(launch_spec['argv']),'owned_output_root':launch_spec['owned_root'],'execution_authorized':execution_authorized,'scientific_result':False};value['authorization_sha256']=digest(value);return value
def validate_launch_authorization(launch_spec,authorization):
 if authorization is None or authorization.get('authorization_sha256')!=digest({k:v for k,v in authorization.items() if k!='authorization_sha256'}) or not authorization.get('execution_authorized') or authorization.get('scientific_result') or authorization.get('launch_spec_sha256')!=launch_spec['launch_spec_sha256'] or authorization.get('runtime_config_sha256')!=launch_spec['runtime_config']['sha256']:raise PermissionError('invalid launch-scoped authorization')
 return authorization

def _write(path,data):
 p=Path(path)
 if p.exists():raise FileExistsError('refusing overwrite')
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n');t.replace(p)
def _blob(root,name,value):
 p=Path(root)/name;p.write_bytes(value);return {'path':str(p),'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value),'truncated':False}
def execute_pilot_launch(launch_spec,*,process_backend=None,authorization=None):
 """Production entry; process_backend is mandatory while authorization is false."""
 validate_launch_spec(launch_spec);root=Path(launch_spec['owned_root'])
 result={'schema_version':'m6a-v2-host-process-v1','launch_id':digest({'marker':launch_spec['owner_sha256'],'spec':launch_spec['launch_spec_sha256']}),'started':False,'timeout':False,'interrupted':False,'return_code':None,'process_status':'FAILED','failure_stage':None,'mock_process':process_backend is not None,'execution_authorized':False,'webots_started':False,'scientific_result':False}
 try:
  if process_backend is None:raise PermissionError('real process execution is not authorized')
  if isinstance(process_backend,OwnedPopenBackend):validate_launch_authorization(launch_spec,authorization)
  env=launch_spec['environment']
  if set(env)!={'M6A_RUNTIME_CONFIG'} or not isinstance(launch_spec['argv'],list):raise ValueError('unsafe process inputs')
  proc=process_backend.start(launch_spec['argv'],env,launch_spec['working_directory']);result['started']=True;result['pid']=getattr(proc,'pid',None)
  try:out,err=proc.communicate(timeout=launch_spec['timeout_s'])
  except TimeoutError:
   result['timeout']=True;result['terminate_attempted']=True;proc.terminate()
   try:out,err=proc.communicate(timeout=launch_spec['graceful_termination_s'])
   except TimeoutError:result['kill_attempted']=True;proc.kill();out,err=proc.communicate(timeout=1)
  result['stdout']=_blob(root,'host_stdout.log',out or b'');result['stderr']=_blob(root,'host_stderr.log',err or b'');result['return_code']=getattr(proc,'returncode',None)
  if result['timeout'] or result['return_code']!=0:raise RuntimeError('process termination or return code')
  joint=process_completed_pilot_launch(launch_spec,{'started':True,'returncode':0,'timed_out':False,'interrupted':False},owned_output_root=root);result['joint']=joint;result['process_status']='INTEGRATION_VALID';result['failure_stage']=None
 except Exception as exc:
  result['failure_stage']=result['failure_stage'] or type(exc).__name__
 finally:
  result['process_sha256']=digest(result);_write(root/'host_process_result.json',result)
 return result
