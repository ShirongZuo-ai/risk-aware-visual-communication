"""Verifier-neutral, explicitly unverified M6-A v2 authorization inputs."""
from __future__ import annotations
import base64, hashlib, json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Protocol
from pathlib import Path
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_prepared_launch import load_prepared_launch_package
from scripts.m6a_v2_fresh_preflight import load_fresh_preflight_report

SCHEMA='m6a-v2-execution-authorization-artifact-v1'
RECEIPT_SCHEMA='m6a-v2-verified-authorization-receipt-v1'
CONTEXT_SCHEMA='m6a-v2-externally-validated-execution-context-v1'; _TOKEN=object()
ED25519_DOMAIN=b'RAVC-M6A-V2-EXECUTION-AUTHORIZATION\x00'
def _b(x): return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()
def _time(x): return datetime.fromisoformat(x)
def _read(path):
 raw=Path(path).read_bytes(); value=json.loads(raw)
 if raw!=_b(value): raise ValueError('noncanonical authorization artifact')
 return value
@dataclass(frozen=True)
class ExpectedAuthorizationBinding:
 launch_id:str;attempt_id:str;identity_id:str;prepared_package_digest:str;fresh_preflight_report_digest:str;launch_spec_digest:str;runtime_config_digest:str;prospective_attempt_root:str
def build_expected_authorization_binding(package_path,preflight_path,*,now=None):
 p=load_prepared_launch_package(package_path); r=load_fresh_preflight_report(preflight_path,package_path,now=now)
 return ExpectedAuthorizationBinding(p['launch_id'],p['attempt_id'],p['identity_id'],p['package_sha256'],r['canonical_digest'],p['launch_spec_sha256'],p['runtime_config_sha256'],p['prospective_attempt_root'])
def validate_execution_authorization_artifact(value,*,now=None):
 if not isinstance(value,dict) or value.get('schema_version')!=SCHEMA or value.get('canonical_artifact_digest')!=digest({k:v for k,v in value.items() if k!='canonical_artifact_digest'}): raise ValueError('authorization artifact digest')
 payload={k:v for k,v in value.items() if k not in {'payload_digest','canonical_artifact_digest'}}
 if value.get('payload_digest')!=digest(payload) or any(not value.get(k) for k in ('authorization_id','nonce','issuer_claim','authorization_policy_version')): raise ValueError('authorization payload')
 env=value.get('authenticator_envelope',{})
 legacy=set(env)=={'scheme','issuer_reference','key_reference','assertion_or_signature'}
 ed=set(env) in ({'scheme','key_id','signature_base64'},{'scheme','key_id','signature_base64','claimed_public_key_fingerprint'})
 if not isinstance(env,dict) or not (legacy or ed) or any(not item or 'placeholder' in str(item).lower() for item in env.values()): raise ValueError('authorization authenticator')
 now=now or datetime.now(timezone.utc); issued,expires=_time(value['issued_at_utc']),_time(value['expires_at_utc'])
 if issued>now or expires<=issued or expires<=now or value.get('execution_authorized') is True: raise ValueError('authorization timing/semantics')
 return value
def validate_authorization_binding(value,binding):
 validate_execution_authorization_artifact(value)
 binding=asdict(binding) if isinstance(binding,ExpectedAuthorizationBinding) else (_ for _ in ()).throw(TypeError('ExpectedAuthorizationBinding required'))
 if any(value.get(k)!=v for k,v in binding.items()) or Path(binding['prospective_attempt_root']).exists(): raise ValueError('authorization binding')
 return {'structurally_valid':True,'binding_valid':True,'trust_verified':False,'execution_authorized':False}
def load_execution_authorization_artifact(path): return validate_execution_authorization_artifact(_read(path))
def persist_test_execution_authorization_artifact(path,binding,*,issued_at_utc,expires_at_utc):
 binding=asdict(binding) if isinstance(binding,ExpectedAuthorizationBinding) else (_ for _ in ()).throw(TypeError('ExpectedAuthorizationBinding required'))
 p={'schema_version':SCHEMA,'authorization_id':'test-auth-1','launch_id':binding['launch_id'],'attempt_id':binding['attempt_id'],'identity_id':binding['identity_id'],'prepared_package_digest':binding['prepared_package_digest'],'fresh_preflight_report_digest':binding['fresh_preflight_report_digest'],'launch_spec_digest':binding['launch_spec_digest'],'runtime_config_digest':binding['runtime_config_digest'],'prospective_attempt_root':binding['prospective_attempt_root'],'issued_at_utc':issued_at_utc,'expires_at_utc':expires_at_utc,'issuer_claim':'test-only-fixture','authorization_policy_version':'test-v1','nonce':'test-nonce-1','authenticator_envelope':{'scheme':'test-only','issuer_reference':'test','key_reference':'test','assertion_or_signature':'test-assertion'}};p['payload_digest']=digest(p);p['canonical_artifact_digest']=digest(p);Path(path).write_bytes(_b(p));return load_execution_authorization_artifact(path)

@dataclass(frozen=True)
class VerifiedAuthorizationReceipt:
 data:dict
 def validate(self,binding):
  d=self.data
  if d.get('schema_version')!=RECEIPT_SCHEMA or d.get('canonical_receipt_digest')!=digest({k:v for k,v in d.items() if k!='canonical_receipt_digest'}) or d.get('verification_class')=='test' and d.get('trust_domain')!='test-only':raise ValueError('receipt digest/class')
  if any(d.get(k)!=v for k,v in asdict(binding).items()) or d.get('verified_at_utc')>datetime.now(timezone.utc).isoformat() or _time(d['expires_at_utc'])<=datetime.now(timezone.utc):raise ValueError('receipt binding/freshness')
  return self
class AuthorizationVerifier(Protocol):
 verifier_identity:str;verification_class:str;trust_domain:str
 def verify(self,authorization,expected_binding)->VerifiedAuthorizationReceipt: ...
def authorization_canonical_payload_bytes(value):
 payload={k:v for k,v in value.items() if k not in {'authenticator_envelope','payload_digest','canonical_artifact_digest'}}
 return _b(payload)
def authorization_signed_message(value):return ED25519_DOMAIN+authorization_canonical_payload_bytes(value)
def ed25519_public_key_fingerprint(public_key):
 from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
 return hashlib.sha256(public_key.public_bytes(Encoding.Raw,PublicFormat.Raw)).hexdigest()
def _receipt(authorization,binding,verifier_identity,verification_class,trust_domain):
 d={'schema_version':RECEIPT_SCHEMA,'verifier_identity':verifier_identity,'verification_class':verification_class,'trust_domain':trust_domain,'authorization_id':authorization['authorization_id'],'issuer_claim':authorization['issuer_claim'],'authorization_payload_digest':authorization['payload_digest'],'authenticator_digest':digest(authorization['authenticator_envelope']),**asdict(binding),'issued_at_utc':authorization['issued_at_utc'],'expires_at_utc':authorization['expires_at_utc'],'verified_at_utc':datetime.now(timezone.utc).isoformat(),'nonce':authorization['nonce'],'authorization_policy_version':authorization['authorization_policy_version']};d['canonical_receipt_digest']=digest(d);return VerifiedAuthorizationReceipt(d)
class Ed25519AuthorizationVerifier:
 verification_class='external'
 def __init__(self,*,public_key_bytes=None,public_key_path=None,expected_public_key_fingerprint,expected_key_id,expected_issuer,expected_policy_version,verifier_identity,trust_domain):
  if (public_key_bytes is None)==(public_key_path is None):raise ValueError('exactly one trusted public key source required')
  required=(expected_public_key_fingerprint,expected_key_id,expected_issuer,expected_policy_version,verifier_identity,trust_domain)
  if any(not isinstance(item,str) or not item or 'placeholder' in item.lower() for item in required):raise ValueError('complete non-placeholder verifier configuration required')
  raw=bytes(public_key_bytes) if public_key_bytes is not None else Path(public_key_path).read_bytes()
  try:
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
   from cryptography.hazmat.primitives.serialization import load_pem_public_key,load_der_public_key
   if len(raw)==32:key=Ed25519PublicKey.from_public_bytes(raw)
   else:
    try:key=load_pem_public_key(raw)
    except ValueError:key=load_der_public_key(raw)
   if not isinstance(key,Ed25519PublicKey):raise ValueError('trusted key is not Ed25519')
  except (TypeError,ValueError) as exc:raise ValueError('invalid trusted Ed25519 public key') from exc
  fingerprint=ed25519_public_key_fingerprint(key)
  if len(expected_public_key_fingerprint)!=64 or fingerprint!=expected_public_key_fingerprint.lower():raise ValueError('trusted public key fingerprint mismatch')
  self._public_key=key;self.public_key_fingerprint=fingerprint;self.expected_key_id=expected_key_id;self.expected_issuer=expected_issuer;self.expected_policy_version=expected_policy_version;self.verifier_identity=verifier_identity;self.trust_domain=trust_domain
 def verify(self,authorization,expected_binding):
  validate_authorization_binding(authorization,expected_binding);env=authorization['authenticator_envelope']
  if set(env) not in ({'scheme','key_id','signature_base64'},{'scheme','key_id','signature_base64','claimed_public_key_fingerprint'}) or env.get('scheme')!='ed25519' or env.get('key_id')!=self.expected_key_id or authorization.get('issuer_claim')!=self.expected_issuer or authorization.get('authorization_policy_version')!=self.expected_policy_version:raise PermissionError('authorization signer policy mismatch')
  if 'claimed_public_key_fingerprint' in env and env['claimed_public_key_fingerprint'].lower()!=self.public_key_fingerprint:raise PermissionError('claimed fingerprint mismatch')
  try:signature=base64.b64decode(env['signature_base64'],validate=True)
  except Exception as exc:raise PermissionError('invalid Ed25519 signature encoding') from exc
  if len(signature)!=64:raise PermissionError('invalid Ed25519 signature length')
  try:self._public_key.verify(signature,authorization_signed_message(authorization))
  except Exception as exc:raise PermissionError('invalid Ed25519 authorization signature') from exc
  return _receipt(authorization,expected_binding,self.verifier_identity,self.verification_class,self.trust_domain)
class TestOnlyAuthorizationVerifier:
 verifier_identity='m6a-v2-test-verifier';verification_class='test';trust_domain='test-only'
 def verify(self,authorization,expected_binding):
  validate_authorization_binding(authorization,expected_binding);return _receipt(authorization,expected_binding,self.verifier_identity,self.verification_class,self.trust_domain)
def verify_execution_authorization(package_path,preflight_path,authorization_path,verifier,*,mode='production'):
 if verifier is None:raise ValueError('trusted authorization verifier is not configured')
 if mode!='test' and getattr(verifier,'verification_class',None)=='test':raise PermissionError('test verifier rejected in production mode')
 binding=build_expected_authorization_binding(package_path,preflight_path); authorization=load_execution_authorization_artifact(authorization_path); validate_authorization_binding(authorization,binding); receipt=verifier.verify(authorization,binding)
 if not isinstance(receipt,VerifiedAuthorizationReceipt):raise TypeError('verifier must return VerifiedAuthorizationReceipt')
 return receipt.validate(binding)

class ExternallyValidatedExecutionContext:
 def __init__(self,token,data):
  if token is not _TOKEN: raise TypeError('externally validated context factory required')
  self.data=data
 def validate(self,binding):
  d=self.data
  if d.get('schema_version')!=CONTEXT_SCHEMA or d.get('canonical_context_digest')!=digest({k:v for k,v in d.items() if k!='canonical_context_digest'}) or d.get('verification_class')=='test':raise ValueError('context provenance')
  receipt=VerifiedAuthorizationReceipt(d.get('verified_receipt',{})).validate(binding)
  for key,value in asdict(binding).items():
   if d.get(key)!=value:raise ValueError('context binding')
  if d.get('authorization_id')!=receipt.data['authorization_id'] or d.get('verified_receipt_digest')!=receipt.data['canonical_receipt_digest'] or _time(d['context_created_at_utc'])<_time(receipt.data['verified_at_utc']) or _time(d['expires_at_utc'])<=datetime.now(timezone.utc) or Path(d['prospective_attempt_root']).exists():raise ValueError('context freshness')
  return self
def build_externally_validated_execution_context(package_path,preflight_path,authorization_path,receipt,*,now_utc=None):
 binding=build_expected_authorization_binding(package_path,preflight_path); authorization=load_execution_authorization_artifact(authorization_path); validate_authorization_binding(authorization,binding)
 if not isinstance(receipt,VerifiedAuthorizationReceipt):raise TypeError('VerifiedAuthorizationReceipt required')
 receipt.validate(binding)
 if receipt.data['verification_class']=='test':raise ValueError('test receipt cannot create external context')
 now=now_utc or datetime.now(timezone.utc); d={'schema_version':CONTEXT_SCHEMA,'authorization_id':authorization['authorization_id'],'authorization_artifact_digest':authorization['canonical_artifact_digest'],'authorization_payload_digest':authorization['payload_digest'],'verified_receipt':receipt.data,'verified_receipt_digest':receipt.data['canonical_receipt_digest'],'verifier_identity':receipt.data['verifier_identity'],'verification_class':receipt.data['verification_class'],'trust_domain':receipt.data['trust_domain'],**asdict(binding),'issued_at_utc':authorization['issued_at_utc'],'expires_at_utc':authorization['expires_at_utc'],'verified_at_utc':receipt.data['verified_at_utc'],'context_created_at_utc':now.isoformat(),'nonce':authorization['nonce'],'authorization_policy_version':authorization['authorization_policy_version']};d['canonical_context_digest']=digest(d);return ExternallyValidatedExecutionContext(_TOKEN,d).validate(binding)
