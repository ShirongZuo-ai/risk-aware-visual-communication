"""Controlled host orchestration.  Real execution is rejected unless separately authorized."""
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from datetime import datetime, timezone
from pathlib import Path
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_launch_spec import validate_launch_spec
from scripts.m6a_v2_pilot_completion import process_completed_pilot_launch

class OwnedPopenBackend:
 """Minimal shell-free backend; callers must pass a valid launch-scoped authorization."""
 def start(self,argv,env,cwd):
  if not isinstance(argv,list) or not argv or not Path(argv[0]).is_absolute():raise ValueError('argv must start with absolute executable')
  return subprocess.Popen(argv,shell=False,cwd=cwd,env={**__import__('os').environ,**env},stdout=subprocess.PIPE,stderr=subprocess.PIPE)


def _utc_now():
 return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ProductionOwnedProcessRunner:
 """Adapter from one validated production package to ``launch_owned_attempt``.

 The adapter owns only process start/wait/log capture. Authorization
 consumption, process evidence, completion, and finalization remain in their
 existing authoritative modules.
 """
 def __init__(self, package_path, *, repository_head, process_backend=None):
  self.package_path=Path(package_path).resolve()
  self.repository_head=repository_head
  self.process_backend=process_backend or OwnedPopenBackend()
  self.start_count=0

 @staticmethod
 def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

 def _validated_spec(self, root, path_plan, owned_attempt_context):
  from scripts.m6a_v2_prepared_launch import load_prepared_launch_package_for_audit
  package=load_prepared_launch_package_for_audit(self.package_path);spec=package['launch_spec']
  if package.get('head')!=self.repository_head or spec.get('head')!=self.repository_head:raise ValueError('launch package HEAD mismatch')
  if spec.get('schema_version')!='m6a-v2-production-launch-spec-v4' or spec.get('launch_spec_sha256')!=digest({k:v for k,v in spec.items() if k!='launch_spec_sha256'}):raise ValueError('invalid production launch specification')
  identity=spec.get('identity',{})
  if any((package.get('launch_id')!=owned_attempt_context['launch_id'],package.get('attempt_id')!=owned_attempt_context['attempt_id'],package.get('identity_id')!=owned_attempt_context['identity_id'],identity.get('episode_id')!=owned_attempt_context['identity_id'])):raise ValueError('launch package/owned context mismatch')
  if Path(spec.get('owned_root','')).resolve()!=Path(root).resolve() or spec.get('path_plan',{}).get('artifacts')!=path_plan:raise ValueError('launch path plan mismatch')
  executable=Path(spec.get('webots',{}).get('path',''))
  argv=spec.get('argv');environment=spec.get('environment');working=Path(spec.get('working_directory',''))
  if not executable.is_absolute() or not executable.is_file() or self._sha(executable)!=spec['webots'].get('executable_sha256'):raise ValueError('launch executable binding')
  expected_argv=[str(executable.resolve()),'--batch','--mode=fast','--stdout','--stderr',spec['temporary_world']['path']]
  fixture=(spec['webots'].get('source')=='temporary-harmless-child' and Path(tempfile.gettempdir()).resolve() in self.package_path.parents)
  safe_argv=(fixture and isinstance(argv,list) and len(argv)==3 and Path(argv[0]).resolve()==executable.resolve() and argv[1]=='-c') or argv==expected_argv
  safe_environment=(set(environment or {})=={'M6A_RUNTIME_CONFIG','PYTHONPATH'} and (fixture or Path(environment['PYTHONPATH']).resolve()==working.resolve()))
  if not safe_argv or not safe_environment:raise ValueError('unsafe launch argv/environment')
  if not working.is_absolute() or not working.is_dir():raise ValueError('unsafe launch working directory')
  if not isinstance(spec.get('timeout_s'),(int,float)) or spec['timeout_s']<=0 or not isinstance(spec.get('graceful_termination_s'),(int,float)) or spec['graceful_termination_s']<=0:raise ValueError('invalid process timeout')
  for name in ('runtime_config','temporary_world','controller'):
   source=Path(spec[name]['path'])
   if not source.is_file() or self._sha(source)!=spec[name]['sha256']:raise ValueError('launch input hash')
  return spec

 @staticmethod
 def _write_log(path, payload):
  path=Path(path)
  if path.exists() or path.is_symlink():raise FileExistsError('refusing process-log overwrite')
  with path.open('xb') as stream:stream.write(payload or b'')

 def run(self, *, root, path_plan, owned_attempt_context):
  spec=self._validated_spec(root,path_plan,owned_attempt_context)
  stdout_path,stderr_path=Path(path_plan['stdout']),Path(path_plan['stderr'])
  if stdout_path.exists() or stderr_path.exists():raise FileExistsError('process log already exists')
  started_at=_utc_now();process=self.process_backend.start(spec['argv'],spec['environment'],spec['working_directory']);self.start_count+=1
  timed_out=False;termination_state='exited';stdout=b'';stderr=b''
  try:
   stdout,stderr=process.communicate(timeout=spec['timeout_s'])
  except subprocess.TimeoutExpired:
   timed_out=True;termination_state='terminated_after_timeout';process.terminate()
   try:stdout,stderr=process.communicate(timeout=spec['graceful_termination_s'])
   except subprocess.TimeoutExpired:
    termination_state='killed_after_timeout';process.kill();stdout,stderr=process.communicate()
  ended_at=_utc_now();return_code=process.returncode
  if not isinstance(return_code,int):raise RuntimeError('owned process did not report a return code')
  self._write_log(stdout_path,stdout);self._write_log(stderr_path,stderr)
  return {'launch_performed':True,'started_at_utc':started_at,'ended_at_utc':ended_at,'return_code':return_code,'timed_out':timed_out,'termination_state':termination_state,'stdout_path':str(stdout_path.resolve()),'stderr_path':str(stderr_path.resolve()),'process_identity':'owned-popen:'+digest({'pid':getattr(process,'pid',None),'executable':spec['webots']['executable_sha256'],'launch_id':owned_attempt_context['launch_id']})}
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
  if set(env)!={'M6A_RUNTIME_CONFIG','PYTHONPATH'} or not isinstance(launch_spec['argv'],list):raise ValueError('unsafe process inputs')
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
