"""Owned post-runtime B5 codec integration; never starts Webots."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
import numpy as np
from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_codec_audit import SnapshotCodecInput, METHODS, BUDGET_ORDER, build_method_mask, encode_reconstruct_case, evaluate_codec_case, audit_codec_case
from scripts.run_m6a_one_identity import load_v2_runtime_config

def _canon(x): return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()
def _write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError('refusing overwrite')
 t=p.with_suffix(p.suffix+'.tmp');t.write_bytes(_canon(x));t.replace(p)
def _owned(root,path):
 root=Path(root).resolve();p=Path(path).resolve()
 if root not in p.parents:return False
 return True
def build_snapshot_codec_input_from_runtime_artifact(runtime_config,snapshot_record,*,owned_output_root,ownership_marker):
 load_v2_runtime_config(runtime_config);root=Path(owned_output_root).resolve();marker=Path(ownership_marker)
 if not marker.is_file() or not _owned(root,marker):raise ValueError('ownership marker')
 sid=snapshot_record['snapshot_id'];expected=next((x for x in runtime_config['snapshots'] if x['snapshot_id']==sid),None)
 if expected is None or snapshot_record.get('timestamp_s')!=expected['timestamp_s']:raise ValueError('snapshot identity')
 raw=Path(snapshot_record['raw_path']);meta=Path(snapshot_record['metadata_path'])
 if not _owned(root,raw) or not _owned(root,meta) or not raw.is_file() or not meta.is_file():raise ValueError('unsafe artifact path')
 data=raw.read_bytes();m=json.loads(meta.read_text())
 if len(data)!=160*120*3 or hashlib.sha256(data).hexdigest()!=m.get('frame_sha256'):raise ValueError('raw digest')
 state=CurrentState(**m['state']);schedule=ScheduleEvidence(m['schedule_id'],m['schedule_available_time_s'],tuple(CommandSegment(**x) for x in m['schedule_segments']))
 return SnapshotCodecInput.create(runtime_config=runtime_config,snapshot_id=sid,timestamp_s=expected['timestamp_s'],image=np.frombuffer(data,dtype=np.uint8).reshape(120,160,3),state=state,schedule=schedule,synthetic_fixture=bool(m.get('synthetic_fixture',False)))
def process_and_audit_runtime_snapshot(runtime_config,snapshot_record,*,owned_output_root,ownership_marker):
 inp=build_snapshot_codec_input_from_runtime_artifact(runtime_config,snapshot_record,owned_output_root=owned_output_root,ownership_marker=ownership_marker);cases=[]
 for method in METHODS:
  mask,payload=build_method_mask(runtime_config,inp,method)
  for budget in BUDGET_ORDER:
   case=encode_reconstruct_case(runtime_config,inp,mask,payload,budget);ev=evaluate_codec_case(runtime_config,inp,case);audit=audit_codec_case(runtime_config,inp,mask,payload,case,ev);cases.append({'snapshot_id':inp.snapshot_id,'method':method,'budget':budget,'case_sha256':case.case_sha256,'evaluation_sha256':ev.evaluation_sha256,'charged_bytes':case.charged_bytes,'audit_sha256':audit['audit_sha256']})
 if len(cases)!=8:raise ValueError('incomplete snapshot cases')
 path=Path(owned_output_root)/'codec'/f'{inp.snapshot_id}.json';payload={'snapshot_id':inp.snapshot_id,'raw_image_sha256':inp.raw_image_sha256,'cases':cases,'synthetic_fixture':inp.synthetic_fixture};payload['sha256']=digest(payload);_write(path,payload);return payload
def persist_codec_aggregate(runtime_config,snapshot_evidence,*,owned_output_root,ownership_marker):
 if len(snapshot_evidence)!=4 or sum(len(x['cases']) for x in snapshot_evidence)!=32:raise ValueError('incomplete aggregate')
 keys={(c['snapshot_id'],c['method'],c['budget']) for x in snapshot_evidence for c in x['cases']}
 if len(keys)!=32:raise ValueError('duplicate aggregate')
 p={'schema_version':'m6a-v2-codec-aggregate-v1','launch_id':digest({'marker':Path(ownership_marker).read_text(),'runtime':runtime_config['config_sha256']}),'runtime_config_sha256':runtime_config['config_sha256'],'snapshot_evidence':snapshot_evidence,'case_count':32,'synthetic_fixture':all(x['synthetic_fixture'] for x in snapshot_evidence),'prohibited_usage':0,'fallback':0,'replacement':0};p['aggregate_sha256']=digest(p);_write(Path(owned_output_root)/'codec_aggregate.json',p);return p
def validate_pilot_completion(launch_spec,process_result,runtime_summary,codec_aggregate,completion_evidence,*,owned_output_root):
 if not process_result.get('started') or process_result.get('timed_out') or process_result.get('interrupted') or codec_aggregate.get('case_count')!=32 or codec_aggregate.get('runtime_config_sha256')!=completion_evidence.get('runtime_config_sha256') or completion_evidence.get('codec_aggregate_sha256')!=codec_aggregate.get('aggregate_sha256') or completion_evidence.get('runtime_summary_sha256')!=runtime_summary.get('summary_sha256') or completion_evidence.get('launch_id')!=codec_aggregate.get('launch_id') or not _owned(owned_output_root,Path(launch_spec['owner_marker'])):raise ValueError('joint completion failed')
 return {'integration_valid':True,'synthetic_fixture':codec_aggregate['synthetic_fixture'],'scientific_result':False}
