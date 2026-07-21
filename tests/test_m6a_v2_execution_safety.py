import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.m6a_v2_execution_safety import *
class R:
 def __init__(self,launched=True,code=0):self.calls=0;self.launched=launched;self.code=code
 def run(self,*,root,path_plan,owned_attempt_context):
  self.calls+=1
  base={'launch_performed':self.launched,'started_at_utc':'2026-01-01T00:00:00+00:00','ended_at_utc':'2026-01-01T00:00:01+00:00','return_code':self.code,'timed_out':False,'termination_state':'exited','stdout_path':'','stderr_path':'','process_identity':'test-only-runner'}
  if self.launched:
   Path(path_plan['stdout']).write_bytes(b'out');Path(path_plan['stderr']).write_bytes(b'err');base.update(stdout_path=path_plan['stdout'],stderr_path=path_plan['stderr'])
  return base
def completion(spec,process,*,owned_output_root):
 return {'integration_valid':True,'final_evidence':{'runtime_sha256':'runtime','snapshot_validation_sha256':'snapshots','b5_sha256':'aggregate-validation','aggregate_sha256':'aggregate','joint_validator_sha256':'joint','manifest_sha256':'manifest','lock_sha256':'lock'}}
class T(unittest.TestCase):
 def package(self):return {"package_sha256":"p","identity_id":"m6a_pilot_s1_seed600100","scene_id":"S1","seed":600100,"launch_spec_sha256":"s","runtime_config_sha256":"r","temporary_world_sha256":"w","controller_sha256":"c","executable":{"path":"x"},"argv_sha256":"a","manifest_sha256":"m","lock_sha256":"l"}
 def test_preflight_root_and_concurrent_consumption(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'),patch('scripts.m6a_v2_execution_safety.CONTROL_ROOT',Path(d)/'control'):
   a=build_authorization(self.package(),head='h',branch='main',attempt_id='attempt1');self.assertFalse(Path(a['owned_output_root']).exists());validate_authorization(a,self.package(),head='h',branch='main');o=acquire_ownership(a['owned_output_root'],a);out=[]
   def f():
    try:out.append(consume_authorization(a,o))
    except FileExistsError:out.append('used')
   ts=[threading.Thread(target=f) for _ in range(2)]
   [x.start() for x in ts];[x.join() for x in ts];self.assertEqual(sum(x=='used' for x in out),1);self.assertEqual(sum(isinstance(x,dict) for x in out),1)
 def test_final_is_exclusive(self):
  with tempfile.TemporaryDirectory() as d:
   e={k:'x' for k in ('launch_id','attempt_id','authorization_id','ownership_sha256','consumption_sha256','process_sha256','runtime_sha256','snapshot_validation_sha256','b5_sha256','aggregate_sha256','joint_validator_sha256','manifest_sha256','lock_sha256')};e['joint_pass']=True;write_final_marker(d,e)
   with self.assertRaises(FileExistsError):write_final_marker(d,e)
 def test_test_context_materializes_only_temporary_attempt_once(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'):
   launch='launch1';attempt='attempt1';ctx=ValidatedExecutionContext.test_fixture_for(launch_id=launch,attempt_id=attempt,identity_id='episode',scene_id='S1',seed=1,launch_spec_sha256='spec',runtime_config_sha256='runtime');package={'launch_id':launch,'attempt_id':attempt,'identity_id':'episode','scene_id':'S1','seed':1,'launch_spec_sha256':'spec','runtime_config_sha256':'runtime','prospective_attempt_root':ctx.prospective_attempt_root}
   owned=materialize_authorized_attempt(package,ctx);self.assertTrue(Path(owned['attempt_root']).is_dir());self.assertTrue((Path(owned['attempt_root'])/OWNER).is_file())
   with self.assertRaises(ValueError):materialize_authorized_attempt(package,ctx)
   with self.assertRaises(TypeError):materialize_authorized_attempt(package,{})
 def test_owned_launch_consumes_after_injected_launch_and_is_idempotent(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'),patch('scripts.m6a_v2_execution_safety.CONTROL_ROOT',Path(d)/'control'):
   ctx=ValidatedExecutionContext.test_fixture_for(launch_id='launch2',attempt_id='attempt2',identity_id='episode',scene_id='S1',seed=1,launch_spec_sha256='spec',runtime_config_sha256='runtime');p={'launch_id':'launch2','attempt_id':'attempt2','identity_id':'episode','scene_id':'S1','seed':1,'launch_spec_sha256':'spec','runtime_config_sha256':'runtime','prospective_attempt_root':ctx.prospective_attempt_root};owned=materialize_authorized_attempt(p,ctx);runner=R();launched=launch_owned_attempt(owned,runner);self.assertTrue(launched['launch_performed']);self.assertEqual(runner.calls,1);self.assertTrue(Path(launched['consumption_path']).is_file());self.assertTrue(Path(launched['process_evidence_path']).is_file());again=launch_owned_attempt(owned,runner);self.assertTrue(again['idempotent']);self.assertEqual(runner.calls,1)
 def test_prelaunch_failure_does_not_consume(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'),patch('scripts.m6a_v2_execution_safety.CONTROL_ROOT',Path(d)/'control'):
   ctx=ValidatedExecutionContext.test_fixture_for(launch_id='launch3',attempt_id='attempt3',identity_id='episode',scene_id='S1',seed=1,launch_spec_sha256='spec',runtime_config_sha256='runtime');p={'launch_id':'launch3','attempt_id':'attempt3','identity_id':'episode','scene_id':'S1','seed':1,'launch_spec_sha256':'spec','runtime_config_sha256':'runtime','prospective_attempt_root':ctx.prospective_attempt_root};owned=materialize_authorized_attempt(p,ctx)
   with self.assertRaises(RuntimeError):launch_owned_attempt(owned,R(False))
   self.assertFalse((Path(d)/'control'/'consumption').exists())
 def test_finalization_closes_mocked_completion_and_recovers_idempotently(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'),patch('scripts.m6a_v2_execution_safety.CONTROL_ROOT',Path(d)/'control'):
   ctx=ValidatedExecutionContext.test_fixture_for(launch_id='launch4',attempt_id='attempt4',identity_id='episode',scene_id='S1',seed=1,launch_spec_sha256='spec',runtime_config_sha256='runtime');p={'launch_id':'launch4','attempt_id':'attempt4','identity_id':'episode','scene_id':'S1','seed':1,'launch_spec_sha256':'spec','runtime_config_sha256':'runtime','prospective_attempt_root':ctx.prospective_attempt_root};owned=materialize_authorized_attempt(p,ctx);launched=launch_owned_attempt(owned,R());final=finalize_launched_attempt(launched,{},completion_runner=completion);self.assertEqual(final['final_outcome'],'success');self.assertTrue((Path(final['attempt_root'])/FINAL).is_file());again=finalize_launched_attempt(launched,{},completion_runner=completion);self.assertTrue(again['idempotent'])
 def test_failed_process_cannot_finalize(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'),patch('scripts.m6a_v2_execution_safety.CONTROL_ROOT',Path(d)/'control'):
   ctx=ValidatedExecutionContext.test_fixture_for(launch_id='launch5',attempt_id='attempt5',identity_id='episode',scene_id='S1',seed=1,launch_spec_sha256='spec',runtime_config_sha256='runtime');p={'launch_id':'launch5','attempt_id':'attempt5','identity_id':'episode','scene_id':'S1','seed':1,'launch_spec_sha256':'spec','runtime_config_sha256':'runtime','prospective_attempt_root':ctx.prospective_attempt_root};owned=materialize_authorized_attempt(p,ctx);launched=launch_owned_attempt(owned,R(code=1))
   with self.assertRaises(RuntimeError):finalize_launched_attempt(launched,{},completion_runner=completion)
