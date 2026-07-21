"""Fail-closed ownership, authorization, and final-result gates for M6-A v2.

This module never starts a process.  The host wrapper is the only caller that
may invoke its launch-time acquisition functions.
"""
from __future__ import annotations

import json, os, socket, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest

PILOT_ROOT = PROJECT_ROOT / "data" / "m6a" / "pilot"
CONTROL_ROOT = PROJECT_ROOT / "results" / "m6a_v2_control"
OWNER = ".m6a_v2_ownership.json"
FINAL = "m6a_v2_final_success.json"

def _canon(x): return (json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)+"\n").encode()
def _utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _new(path: Path, value: dict):
 path.parent.mkdir(parents=True, exist_ok=True)
 value=dict(value); value["sha256"]=digest(value)
 fd=os.open(str(path), os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 with os.fdopen(fd,"wb") as f:f.write(_canon(value))
 return value
def _under(path: Path, root: Path):
 return path.is_absolute() and path.resolve().is_relative_to(root.resolve())
def attempt_root(launch_id,attempt_id):
 if not all(isinstance(x,str) and x and x.replace("-","").isalnum() for x in (launch_id,attempt_id)):raise ValueError("unsafe launch/attempt id")
 return (PILOT_ROOT/launch_id/attempt_id).resolve()
def attempt_path_plan(launch_id,attempt_id,identity_id,scene_id,seed):
 root=attempt_root(launch_id,attempt_id); items={'ownership_marker':root/OWNER,'stdout':root/'host_stdout.log','stderr':root/'host_stderr.log','process_evidence':root/'host_process_result.json','runtime_summary':root/'episode_runtime_summary.json','runtime_status':root/'episode_runtime_status.json','runtime_diagnostic':root/'episode_runtime_failure.json','runtime_manifest':root/'runtime_artifacts.json','snapshot_root':root/'snapshots','codec_root':root/'codec','codec_aggregate':root/'codec_aggregate.json','aggregate_validation':root/'codec_aggregate_validation.json','joint_report':root/'joint_validation.json','final_marker':root/FINAL,'consumption_record':CONTROL_ROOT/'consumption'/(digest({'launch':launch_id,'attempt':attempt_id})+'.json')}
 if len({str(x.resolve()).lower() for x in items.values()})!=len(items):raise ValueError('artifact path alias')
 for name,path in items.items():
  if name!='consumption_record' and not _under(path,root):raise ValueError('artifact path escape')
 return {'schema_version':'m6a-v2-attempt-path-plan-v1','launch_id':launch_id,'attempt_id':attempt_id,'identity_id':identity_id,'scene_id':scene_id,'seed':seed,'attempt_root':str(root),'artifacts':{k:str(v.resolve()) for k,v in items.items()}}
def validate_prospective_root(root,*,launch_id,attempt_id):
 root=Path(root)
 if root != attempt_root(launch_id,attempt_id) or root.exists() or not _under(root,PILOT_ROOT) or CONTROL_ROOT.resolve() in root.parents:raise ValueError("unsafe or reused attempt root")
 if any(part in {".",".."} for part in root.parts):raise ValueError("path traversal")
 parent=root.parent
 while parent != PILOT_ROOT.parent:
  if parent.exists() and parent.is_symlink():raise ValueError("symlink escape")
  parent=parent.parent
 return root
def acquire_ownership(root,authorization,*,launcher_identity="m6a-v2-host"):
 root=validate_prospective_root(root,launch_id=authorization["launch_id"],attempt_id=authorization["attempt_id"])
 root.mkdir(parents=True,exist_ok=False)
 marker={"schema_version":"m6a-v2-ownership-v1","launch_id":authorization["launch_id"],"attempt_id":authorization["attempt_id"],"authorization_id":authorization["authorization_id"],"identity_id":authorization["identity_id"],"scene":authorization["scene_id"],"seed":authorization["seed"],"launch_spec_sha256":authorization["launch_spec_sha256"],"authorization_sha256":authorization["authorization_sha256"],"output_root":str(root),"launcher_identity":launcher_identity,"host":socket.gethostname(),"acquired_at_utc":_utc(),"state":"owned_pre_spawn","launch_performed":False,"webots_started":False,"scientific_result":False}
 return _new(root/OWNER,marker)
def build_authorization(package,*,head,branch,attempt_id,valid_minutes=30):
 launch_id=digest({"package":package["package_sha256"],"attempt":attempt_id})
 root=attempt_root(launch_id,attempt_id)
 value={"schema_version":"m6a-v2-authorization-v2","authorization_id":digest({"launch":launch_id,"attempt":attempt_id,"head":head}),"launch_id":launch_id,"attempt_id":attempt_id,"identity_id":package["identity_id"],"scene_id":package["scene_id"],"seed":package["seed"],"repository_root":str(PROJECT_ROOT),"authorized_head":head,"branch":branch,"prepared_package_sha256":package["package_sha256"],"launch_spec_sha256":package["launch_spec_sha256"],"runtime_config_sha256":package["runtime_config_sha256"],"temporary_world_sha256":package["temporary_world_sha256"],"controller_sha256":package["controller_sha256"],"executable":package["executable"],"argv_sha256":package["argv_sha256"],"manifest_sha256":package["manifest_sha256"],"lock_sha256":package["lock_sha256"],"owned_output_root":str(root),"purpose":"single-identity M6-A v2 pilot smoke","authorized_at_utc":_utc(),"valid_until_utc":(datetime.now(timezone.utc)+timedelta(minutes=valid_minutes)).replace(microsecond=0).isoformat(),"execution_authorized":True,"consumed":False,"launch_performed":False,"webots_started":False,"scientific_result":False,"test_fixture":False}
 value["authorization_sha256"]=digest(value); return value
def validate_authorization(a,package,*,head,branch):
 if a.get("authorization_sha256")!=digest({k:v for k,v in a.items() if k!="authorization_sha256"}) or not a.get("execution_authorized") or a.get("test_fixture") or a.get("consumed") or a.get("launch_performed") or a.get("scientific_result") or a.get("prepared_package_sha256")!=package["package_sha256"] or a.get("authorized_head")!=head or a.get("branch")!=branch or datetime.fromisoformat(a["valid_until_utc"])<=datetime.now(timezone.utc):raise PermissionError("invalid authorization")
 validate_prospective_root(a["owned_output_root"],launch_id=a["launch_id"],attempt_id=a["attempt_id"]);return a
def consume_authorization(a,ownership):
 path=CONTROL_ROOT/"consumption"/(a["authorization_id"]+".json")
 return _new(path,{"schema_version":"m6a-v2-consumption-v1","authorization_id":a["authorization_id"],"authorization_sha256":a["authorization_sha256"],"launch_id":a["launch_id"],"attempt_id":a["attempt_id"],"output_root":a["owned_output_root"],"launch_spec_sha256":a["launch_spec_sha256"],"ownership_sha256":ownership["sha256"],"consumed_at_utc":_utc(),"state":"consumed_pre_spawn"})
def write_final_marker(root,evidence):
 required={"launch_id","attempt_id","authorization_id","ownership_sha256","consumption_sha256","process_sha256","runtime_sha256","snapshot_validation_sha256","b5_sha256","aggregate_sha256","joint_validator_sha256","manifest_sha256","lock_sha256"}
 if not required <= set(evidence) or evidence.get("joint_pass") is not True:raise ValueError("joint validation required")
 return _new(Path(root)/FINAL,{"schema_version":"m6a-v2-final-success-v1",**evidence,"created_at_utc":_utc(),"scientific_result":False})
