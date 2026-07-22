import base64,json,tempfile,unittest
from dataclasses import asdict
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_execution_authorization import *
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
def seal(value):
 value['payload_digest']=digest({k:v for k,v in value.items() if k not in {'payload_digest','canonical_artifact_digest'}});value['canonical_artifact_digest']=digest({k:v for k,v in value.items() if k!='canonical_artifact_digest'});return value
def signed_artifact(path,binding,private,*,domain=ED25519_DOMAIN):
 n=datetime.now(timezone.utc);p=persist_test_execution_authorization_artifact(path,binding,issued_at_utc=n.isoformat(),expires_at_utc=(n+timedelta(minutes=2)).isoformat());p['issuer_claim']='offline-test-issuer';p['authorization_policy_version']='m6a-v2-policy-1';p.pop('payload_digest');p.pop('canonical_artifact_digest');message=domain+authorization_canonical_payload_bytes(p);p['authenticator_envelope']={'scheme':'ed25519','key_id':'test-key-1','signature_base64':base64.b64encode(private.sign(message)).decode()};seal(p);Path(path).write_bytes((json.dumps(p,sort_keys=True,separators=(',',':'))+'\n').encode());return p
class T(unittest.TestCase):
 def test_explicit_test_verifier_returns_bound_receipt_only_in_test_mode(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'):
   pp,p=build_prepared_launch_package(head='h',branch='main',attempt_id='a4',package_root=Path(d)/'control');run_fresh_preflight_for_prepared_launch(pp);b=build_expected_authorization_binding(pp,p['preflight_report_path']);n=datetime.now(timezone.utc);a=Path(d)/'a.json';persist_test_execution_authorization_artifact(a,b,issued_at_utc=n.isoformat(),expires_at_utc=(n+timedelta(minutes=1)).isoformat());r=verify_execution_authorization(pp,p['preflight_report_path'],a,TestOnlyAuthorizationVerifier(),mode='test');self.assertEqual(r.data['verification_class'],'test')
   with self.assertRaises(PermissionError):verify_execution_authorization(pp,p['preflight_report_path'],a,TestOnlyAuthorizationVerifier())
   with self.assertRaises(ValueError):verify_execution_authorization(pp,p['preflight_report_path'],a,None,mode='test')
 def test_ed25519_production_verifier_and_signature_failures(self):
  with tempfile.TemporaryDirectory() as d,patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(d)/'pilot'):
   pp,p=build_prepared_launch_package(head='h',branch='main',attempt_id='ed1',package_root=Path(d)/'control');run_fresh_preflight_for_prepared_launch(pp);binding=build_expected_authorization_binding(pp,p['preflight_report_path']);private=Ed25519PrivateKey.generate();public=private.public_key();raw=public.public_bytes(Encoding.Raw,PublicFormat.Raw);fingerprint=ed25519_public_key_fingerprint(public);artifact=Path(d)/'signed.json';signed_artifact(artifact,binding,private)
   verifier=Ed25519AuthorizationVerifier(public_key_bytes=raw,expected_public_key_fingerprint=fingerprint,expected_key_id='test-key-1',expected_issuer='offline-test-issuer',expected_policy_version='m6a-v2-policy-1',verifier_identity='ed25519-test-verifier',trust_domain='ephemeral-test-domain');receipt=verify_execution_authorization(pp,p['preflight_report_path'],artifact,verifier);self.assertEqual(receipt.data['verification_class'],'external');self.assertFalse(Path(binding.prospective_attempt_root).exists())
   mutations=[('wrong_scheme',lambda x:x['authenticator_envelope'].__setitem__('scheme','rsa')),('wrong_key',lambda x:x['authenticator_envelope'].__setitem__('key_id','wrong')),('wrong_issuer',lambda x:x.__setitem__('issuer_claim','wrong')),('wrong_policy',lambda x:x.__setitem__('authorization_policy_version','wrong')),('bad_base64',lambda x:x['authenticator_envelope'].__setitem__('signature_base64','%%%')),('truncated',lambda x:x['authenticator_envelope'].__setitem__('signature_base64',base64.b64encode(b'x').decode())),('signature_tamper',lambda x:x['authenticator_envelope'].__setitem__('signature_base64',base64.b64encode(bytes([base64.b64decode(x['authenticator_envelope']['signature_base64'])[0]^1])+base64.b64decode(x['authenticator_envelope']['signature_base64'])[1:]).decode())),('claimed_fingerprint',lambda x:x['authenticator_envelope'].__setitem__('claimed_public_key_fingerprint','0'*64)),('payload_tamper',lambda x:x.__setitem__('nonce','changed'))]
   original=json.loads(artifact.read_text())
   for name,change in mutations:
    with self.subTest(name=name):
     candidate=json.loads(json.dumps(original));change(candidate);seal(candidate);artifact.write_bytes((json.dumps(candidate,sort_keys=True,separators=(',',':'))+'\n').encode())
     with self.assertRaises((PermissionError,ValueError)):verify_execution_authorization(pp,p['preflight_report_path'],artifact,verifier)
   signed_artifact(artifact,binding,private,domain=b'RAVC-M6A-V3-WRONG\x00')
   with self.assertRaises(PermissionError):verify_execution_authorization(pp,p['preflight_report_path'],artifact,verifier)
 def test_ed25519_trust_configuration_fails_closed(self):
  private=Ed25519PrivateKey.generate();raw=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw);fingerprint=ed25519_public_key_fingerprint(private.public_key())
  common={'expected_public_key_fingerprint':fingerprint,'expected_key_id':'key','expected_issuer':'issuer','expected_policy_version':'policy','verifier_identity':'verifier','trust_domain':'domain'}
  with self.assertRaises(ValueError):Ed25519AuthorizationVerifier(public_key_bytes=None,public_key_path=None,**common)
  with self.assertRaises(ValueError):Ed25519AuthorizationVerifier(public_key_bytes=raw,expected_public_key_fingerprint='0'*64,expected_key_id='key',expected_issuer='issuer',expected_policy_version='policy',verifier_identity='verifier',trust_domain='domain')
  other=Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
  with self.assertRaises(ValueError):Ed25519AuthorizationVerifier(public_key_bytes=other,**common)
