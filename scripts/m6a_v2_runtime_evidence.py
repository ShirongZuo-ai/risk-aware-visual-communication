"""Canonical, reloadable M6-A v2 runtime evidence; no Webots import or launch."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from scripts.m6a_trusted_artifacts import digest
def _b(x):return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()
def _sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def persist(path,payload):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError('immutable evidence')
 x=dict(payload);x['sha256']=digest(x);p.write_bytes(_b(x));return x
def load(path,schema,identity):
 raw=Path(path).read_bytes();x=json.loads(raw)
 if raw!=_b(x) or x.get('schema_version')!=schema or x.get('sha256')!=digest({k:v for k,v in x.items() if k!='sha256'}) or x.get('identity')!=identity:raise ValueError('invalid evidence')
 return x
def file_entry(role,path,root):
 p=Path(path).resolve();r=Path(root).resolve()
 if not p.is_file() or not p.is_relative_to(r):raise ValueError('unsafe artifact')
 return {'role':role,'path':str(p),'relative_path':str(p.relative_to(r)),'bytes':p.stat().st_size,'sha256':_sha(p)}
def persist_runtime_manifest(path,identity,root,artifacts):
 entries=[file_entry(k,v,root) for k,v in artifacts.items()]
 if len(entries)<3 or len({e['path'].lower() for e in entries})!=len(entries):raise ValueError('incomplete/alias runtime artifacts')
 return persist(path,{'schema_version':'m6a-v2-runtime-artifact-manifest-v1','identity':identity,'artifact_count':len(entries),'artifacts':entries})
def load_runtime_manifest(path,identity,root):
 x=load(path,'m6a-v2-runtime-artifact-manifest-v1',identity)
 for e in x['artifacts']:
  actual=file_entry(e['role'],e['path'],root)
  if actual!=e:raise ValueError('runtime artifact tamper')
 return x
def persist_validation(path,schema,identity,source,passed,errors=()):
 if not isinstance(passed,bool):raise ValueError('validation result')
 return persist(path,{'schema_version':schema,'identity':identity,'source_path':str(Path(source).resolve()),'source_sha256':_sha(source),'passed':passed,'errors':list(errors)})
def load_validation(path,schema,identity):
 x=load(path,schema,identity)
 if _sha(x['source_path'])!=x['source_sha256'] or not x['passed']:raise ValueError('validation failed')
 return x
def persist_joint_report(path,identity,upstream):
 actual=[]
 for role,p in upstream.items():
  x=json.loads(Path(p).read_text());actual.append({'role':role,'path':str(Path(p).resolve()),'sha256':x.get('sha256')})
 if any(not x['sha256'] for x in actual):raise ValueError('missing upstream digest')
 return persist(path,{'schema_version':'m6a-v2-joint-report-v1','identity':identity,'upstream':actual,'passed':True,'errors':[]})
def persist_process_evidence(path,identity,stdout,stderr,**fields):
 out=file_entry('stdout',stdout,Path(path).parent);err=file_entry('stderr',stderr,Path(path).parent)
 if fields.get('ended_at_utc','') < fields.get('started_at_utc','') or not isinstance(fields.get('return_code'),int):raise ValueError('invalid process timing/code')
 return persist(path,{'schema_version':'m6a-v2-process-evidence-v1','identity':identity,'stdout':out,'stderr':err,**fields})
def load_process_evidence(path,identity):
 x=load(path,'m6a-v2-process-evidence-v1',identity);root=Path(path).parent
 if file_entry('stdout',x['stdout']['path'],root)!=x['stdout'] or file_entry('stderr',x['stderr']['path'],root)!=x['stderr'] or x['ended_at_utc']<x['started_at_utc'] or not isinstance(x['return_code'],int) or any(not v for v in (x['stdout']['sha256'],x['stderr']['sha256'])):raise ValueError('invalid process evidence')
 return x
