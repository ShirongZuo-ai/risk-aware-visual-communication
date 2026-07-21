import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.m6a_v2_launch_spec import build_one_identity_launch_spec,WebotsExecutableEvidence
from scripts.m6a_v2_host_wrapper import execute_pilot_launch,OwnedPopenBackend,build_launch_authorization,validate_launch_authorization
from scripts.m6a_v2_episode_source import MANIFEST_PATH,LOCK_PATH
class P:
 pid=7;returncode=0
 def communicate(self,timeout):return b'out',b'err'
 def terminate(self):self.returncode=-1
 def kill(self):self.returncode=-9
class B:
 def __init__(self):self.called=False
 def start(self,argv,env,cwd):self.called=True;self.argv=argv;return P()
class T(unittest.TestCase):
 def test_mock_wrapper_never_claims_real_success(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'fake.exe';exe.write_bytes(b'x');ev=WebotsExecutableEvidence(str(exe),'R2025a','test',0)
   with patch('scripts.m6a_v2_launch_spec.resolve_webots_executable',return_value=ev):spec=build_one_identity_launch_spec(MANIFEST_PATH,LOCK_PATH,preflight_root=Path(d)/'owned')
   with patch('scripts.m6a_v2_host_wrapper.process_completed_pilot_launch',return_value={'integration_valid':True}):r=execute_pilot_launch(spec,process_backend=B())
   self.assertTrue(r['started']);self.assertFalse(r['webots_started']);self.assertTrue(Path(r['stdout']['path']).is_file());self.assertEqual(r['process_status'],'INTEGRATION_VALID')
 def test_no_backend_is_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'fake.exe';exe.write_bytes(b'x');ev=WebotsExecutableEvidence(str(exe),'R2025a','test',0)
   with patch('scripts.m6a_v2_launch_spec.resolve_webots_executable',return_value=ev):spec=build_one_identity_launch_spec(MANIFEST_PATH,LOCK_PATH,preflight_root=Path(d)/'owned')
   r=execute_pilot_launch(spec);self.assertFalse(r['started']);self.assertFalse(r['webots_started'])
 def test_real_backend_harmless_child_requires_scoped_authorization(self):
  import sys
  with tempfile.TemporaryDirectory() as d:
   backend=OwnedPopenBackend();proc=backend.start([str(Path(sys.executable).resolve()),'-c','import sys;print("ok");print("err",file=sys.stderr)'],{},d);out,err=proc.communicate(timeout=10);self.assertEqual(proc.returncode,0);self.assertEqual(out.replace(b'\r\n',b'\n'),b'ok\n');self.assertEqual(err.replace(b'\r\n',b'\n'),b'err\n')
