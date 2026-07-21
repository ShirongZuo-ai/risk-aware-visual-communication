import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.m6a_v2_execution_safety import *
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
