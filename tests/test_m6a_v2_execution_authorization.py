import tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_execution_authorization import *
class T(unittest.TestCase):
 def test_unverified_artifact_binds_package_and_preflight(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'):
   pp,p=build_prepared_launch_package(head='h',branch='main',attempt_id='a3',package_root=Path(d)/'control');r=run_fresh_preflight_for_prepared_launch(pp);b=build_expected_authorization_binding(pp,p['preflight_report_path']);now=datetime.now(timezone.utc);x=persist_test_execution_authorization_artifact(Path(d)/'auth.json',b,issued_at_utc=now.isoformat(),expires_at_utc=(now+timedelta(minutes=1)).isoformat());self.assertTrue(validate_authorization_binding(x,b)['binding_valid']);self.assertFalse(validate_authorization_binding(x,b)['execution_authorized']);Path(d,'auth.json').write_text('{}');
   with self.assertRaises(ValueError):load_execution_authorization_artifact(Path(d)/'auth.json')
