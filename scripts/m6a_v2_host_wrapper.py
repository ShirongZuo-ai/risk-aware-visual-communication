"""Controlled host orchestration.  Real execution is rejected unless separately authorized."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_launch_spec import validate_launch_spec
from scripts.m6a_v2_pilot_completion import process_completed_pilot_launch

def _write(path,data):
 p=Path(path)
 if p.exists():raise FileExistsError('refusing overwrite')
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n');t.replace(p)
def _blob(root,name,value):
 p=Path(root)/name;p.write_bytes(value);return {'path':str(p),'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value),'truncated':False}
def execute_pilot_launch(launch_spec,*,process_backend=None):
 """Production entry; process_backend is mandatory while authorization is false."""
 validate_launch_spec(launch_spec);root=Path(launch_spec['owned_root'])
 result={'schema_version':'m6a-v2-host-process-v1','launch_id':digest({'marker':launch_spec['owner_sha256'],'spec':launch_spec['launch_spec_sha256']}),'started':False,'timeout':False,'interrupted':False,'return_code':None,'process_status':'FAILED','failure_stage':None,'mock_process':process_backend is not None,'execution_authorized':False,'webots_started':False,'scientific_result':False}
 try:
  if process_backend is None:raise PermissionError('real process execution is not authorized')
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
