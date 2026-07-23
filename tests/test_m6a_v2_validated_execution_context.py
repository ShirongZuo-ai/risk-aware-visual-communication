import tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_execution_authorization import *
from scripts.m6a_v2_execution_safety import materialize_authorized_attempt
from scripts.m6a_v2_detached_authorization import authoritative_detached_authorization_paths,persist_verified_authorization_receipt
class External:
 verifier_identity='mock-external';verification_class='external';trust_domain='test-double'
 def verify(self,a,b):
  d={'schema_version':RECEIPT_SCHEMA,'verifier_identity':self.verifier_identity,'verification_class':self.verification_class,'trust_domain':self.trust_domain,'authorization_id':a['authorization_id'],'issuer_claim':a['issuer_claim'],'authorization_payload_digest':a['payload_digest'],'authenticator_digest':digest(a['authenticator_envelope']),**asdict(b),'issued_at_utc':a['issued_at_utc'],'expires_at_utc':a['expires_at_utc'],'verified_at_utc':datetime.now(timezone.utc).isoformat(),'nonce':a['nonce'],'authorization_policy_version':a['authorization_policy_version']};d['canonical_receipt_digest']=digest(d);return VerifiedAuthorizationReceipt(d)
class T(unittest.TestCase):
 def test_external_receipt_creates_controlled_context_only(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'):
   pp,p=build_prepared_launch_package(head='h',branch='main',attempt_id='a5',package_root=Path(d)/'control');run_fresh_preflight_for_prepared_launch(pp);b=build_expected_authorization_binding(pp,p['preflight_report_path']);n=datetime.now(timezone.utc);a=Path(d)/'a.json';persist_test_execution_authorization_artifact(a,b,issued_at_utc=n.isoformat(),expires_at_utc=(n+timedelta(minutes=1)).isoformat());r=verify_execution_authorization(pp,p['preflight_report_path'],a,External(),mode='test');persist_verified_authorization_receipt(authoritative_detached_authorization_paths(pp)['verified_receipt'],r,b);c=build_externally_validated_execution_context(pp,p['preflight_report_path'],a,r);self.assertEqual(c.data['verification_class'],'external');owned=materialize_authorized_attempt(p,c,mode='production',prepared_package_path=pp,repository_head='h');self.assertEqual(owned['execution_mode'],'production')
   with self.assertRaises(TypeError):ExternallyValidatedExecutionContext(None,{})
 def test_external_context_rejects_test_mode(self):
  with self.assertRaises(TypeError):materialize_authorized_attempt({}, {}, mode='production')
