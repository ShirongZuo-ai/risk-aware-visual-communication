import tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_execution_authorization import *
class T(unittest.TestCase):
 def test_explicit_test_verifier_returns_bound_receipt_only_in_test_mode(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'):
   pp,p=build_prepared_launch_package(head='h',branch='main',attempt_id='a4',package_root=Path(d)/'control');run_fresh_preflight_for_prepared_launch(pp);b=build_expected_authorization_binding(pp,p['preflight_report_path']);n=datetime.now(timezone.utc);a=Path(d)/'a.json';persist_test_execution_authorization_artifact(a,b,issued_at_utc=n.isoformat(),expires_at_utc=(n+timedelta(minutes=1)).isoformat());r=verify_execution_authorization(pp,p['preflight_report_path'],a,TestOnlyAuthorizationVerifier(),mode='test');self.assertEqual(r.data['verification_class'],'test')
   with self.assertRaises(PermissionError):verify_execution_authorization(pp,p['preflight_report_path'],a,TestOnlyAuthorizationVerifier())
   with self.assertRaises(ValueError):verify_execution_authorization(pp,p['preflight_report_path'],a,None,mode='test')
