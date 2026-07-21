"""Verifier-neutral, explicitly unverified M6-A v2 authorization inputs."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_prepared_launch import load_prepared_launch_package
from scripts.m6a_v2_fresh_preflight import load_fresh_preflight_report

SCHEMA='m6a-v2-execution-authorization-artifact-v1'
def _b(x): return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()
def _time(x): return datetime.fromisoformat(x)
def _read(path):
 raw=Path(path).read_bytes(); value=json.loads(raw)
 if raw!=_b(value): raise ValueError('noncanonical authorization artifact')
 return value
def build_expected_authorization_binding(package_path,preflight_path):
 p=load_prepared_launch_package(package_path); r=load_fresh_preflight_report(preflight_path,package_path)
 return {'launch_id':p['launch_id'],'attempt_id':p['attempt_id'],'identity_id':p['identity_id'],'prepared_package_digest':p['package_sha256'],'fresh_preflight_report_digest':r['canonical_digest'],'launch_spec_digest':p['launch_spec_sha256'],'runtime_config_digest':p['runtime_config_sha256'],'prospective_attempt_root':p['prospective_attempt_root']}
def validate_execution_authorization_artifact(value,*,now=None):
 if not isinstance(value,dict) or value.get('schema_version')!=SCHEMA or value.get('canonical_artifact_digest')!=digest({k:v for k,v in value.items() if k!='canonical_artifact_digest'}): raise ValueError('authorization artifact digest')
 payload={k:v for k,v in value.items() if k not in {'payload_digest','canonical_artifact_digest'}}
 if value.get('payload_digest')!=digest(payload) or any(not value.get(k) for k in ('authorization_id','nonce','issuer_claim','authorization_policy_version')): raise ValueError('authorization payload')
 env=value.get('authenticator_envelope',{})
 if not isinstance(env,dict) or set(env)!={'scheme','issuer_reference','key_reference','assertion_or_signature'} or any(not env[k] or 'placeholder' in str(env[k]).lower() for k in env): raise ValueError('authorization authenticator')
 now=now or datetime.now(timezone.utc); issued,expires=_time(value['issued_at_utc']),_time(value['expires_at_utc'])
 if issued>now or expires<=issued or expires<=now or value.get('execution_authorized') is True: raise ValueError('authorization timing/semantics')
 return value
def validate_authorization_binding(value,binding):
 validate_execution_authorization_artifact(value)
 if any(value.get(k)!=v for k,v in binding.items()) or Path(binding['prospective_attempt_root']).exists(): raise ValueError('authorization binding')
 return {'structurally_valid':True,'binding_valid':True,'trust_verified':False,'execution_authorized':False}
def load_execution_authorization_artifact(path): return validate_execution_authorization_artifact(_read(path))
def persist_test_execution_authorization_artifact(path,binding,*,issued_at_utc,expires_at_utc):
 p={'schema_version':SCHEMA,'authorization_id':'test-auth-1','launch_id':binding['launch_id'],'attempt_id':binding['attempt_id'],'identity_id':binding['identity_id'],'prepared_package_digest':binding['prepared_package_digest'],'fresh_preflight_report_digest':binding['fresh_preflight_report_digest'],'launch_spec_digest':binding['launch_spec_digest'],'runtime_config_digest':binding['runtime_config_digest'],'prospective_attempt_root':binding['prospective_attempt_root'],'issued_at_utc':issued_at_utc,'expires_at_utc':expires_at_utc,'issuer_claim':'test-only-fixture','authorization_policy_version':'test-v1','nonce':'test-nonce-1','authenticator_envelope':{'scheme':'test-only','issuer_reference':'test','key_reference':'test','assertion_or_signature':'test-assertion'}};p['payload_digest']=digest(p);p['canonical_artifact_digest']=digest(p);Path(path).write_bytes(_b(p));return load_execution_authorization_artifact(path)
