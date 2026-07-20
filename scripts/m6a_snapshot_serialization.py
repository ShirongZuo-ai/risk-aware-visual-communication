"""Strict, atomic on-disk schema for trusted M6-A snapshot provenance."""
from __future__ import annotations
from dataclasses import asdict
import json, math, shutil, uuid
from pathlib import Path
from scripts.m6a_common import VERSION
from scripts.m6a_trusted_artifacts import GeneratedRiskMask,create_generated_risk_mask,digest

SCHEMA_VERSION='m6a-trusted-snapshot-v1'
METHODS=('state_only_risk_roi','command_conditioned_risk_roi')
ROOT_FILES={'snapshot_metadata.json','comparison.json','frame_reference.json',*METHODS}
METHOD_FILES={'predictor.json','trajectory.json','corridor.json','mask.json','provenance.json'}
def _write(path,data):path.write_text(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n',encoding='utf-8')
def _read(path):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError) as exc:raise ValueError(f'invalid serialized snapshot file: {path.name}') from exc
def _artifact_parts(artifact):
 raw=asdict(artifact)
 return ({key:raw[key] for key in ('method','source_predictor','predictor_input_digest','predictor_config_digest')},{'trajectory':raw.pop('trajectory'),'trajectory_hash':raw.pop('trajectory_hash')},{'corridor':raw.pop('corridor'),'corridor_hash':raw.pop('corridor_hash')},{'mask_payload':raw.pop('mask_payload'),'mask_hash':raw.pop('mask_hash')},raw)
def _validate_artifact(artifact,method):
 if not isinstance(artifact,GeneratedRiskMask) or artifact.method!=method or artifact.synthetic_test_only:raise ValueError('untrusted or synthetic artifact')
 try:create_generated_risk_mask(**asdict(artifact))
 except (TypeError,ValueError) as exc:raise ValueError('invalid artifact provenance chain') from exc
 if not artifact.predictor_input_digest or any((artifact.actual_future_usage,artifact.combined_usage,artifact.raw_external_mask_usage,artifact.fallback,artifact.replacement)):raise ValueError('unsafe artifact provenance')
def _validate_output(output,manifest_hash,protocol_version):
 from scripts.m6a_dual_roi import DualROISnapshotOutput
 if not isinstance(output,DualROISnapshotOutput):raise ValueError('serializer accepts only DualROISnapshotOutput')
 if protocol_version!=VERSION or output.protocol_version!=protocol_version or output.manifest_hash!=manifest_hash:raise ValueError('protocol or manifest mismatch')
 if not all((output.scene,output.episode_id,output.snapshot_id,output.frame_reference)) or not math.isfinite(output.timestamp_s):raise ValueError('incomplete snapshot metadata')
 methods=output.methods
 if set(methods)!=set(METHODS):raise ValueError('illegal method set')
 comparison=output.comparison
 required={'shared_current_state_digest','shared_projection_config_digest','horizon_digest','step_digest','footprint_digest','corridor_digest','projection_digest','rasterization_digest'}
 if not required<=set(comparison) or any(not comparison[key] for key in required):raise ValueError('missing comparison provenance')
 if comparison.get('allowed_input_difference')!=['predictor identity','predefined_future_command_schedule'] or any(comparison.get(key)!=0 for key in ('actual_future_usage_count','combined_usage_count','raw_mask_usage_count','fallback_count','replacement_count')):raise ValueError('unsafe comparison provenance')
 for method,artifact in methods.items():
  _validate_artifact(artifact,method)
  if artifact.predictor_config_digest!=comparison['shared_projection_config_digest'] or artifact.footprint_digest!=comparison['footprint_digest'] or artifact.projection_digest!=comparison['projection_digest'] or artifact.rasterization_digest!=comparison['rasterization_digest']:raise ValueError('shared provenance digest mismatch')
 if methods['state_only_risk_roi'].predictor_input_digest!=comparison['shared_current_state_digest']:raise ValueError('state digest mismatch')
def _safe_target(target):
 target=Path(target).resolve()
 if target==target.parent or target==Path.cwd().resolve() or any(part.lower().startswith('m5') for part in target.parts):raise ValueError('unsafe or frozen output root')
 if not target.parent.is_dir():raise ValueError('target parent must already exist')
 if target.exists():raise FileExistsError('refusing overwrite or non-empty target')
 return target
def serialize_snapshot(output,target,*,manifest_hash,protocol_version):
 _validate_output(output,manifest_hash,protocol_version);target=_safe_target(target);temporary=target.with_name('.'+target.name+'.tmp-'+uuid.uuid4().hex)
 try:
  temporary.mkdir()
  _write(temporary/'snapshot_metadata.json',{'schema_version':SCHEMA_VERSION,'protocol_version':output.protocol_version,'manifest_hash':output.manifest_hash,'scene':output.scene,'episode_id':output.episode_id,'seed':output.seed,'snapshot_id':output.snapshot_id,'timestamp_s':output.timestamp_s})
  _write(temporary/'comparison.json',output.comparison);_write(temporary/'frame_reference.json',{'frame_reference':output.frame_reference})
  for method,artifact in output.methods.items():
   directory=temporary/method;directory.mkdir();predictor,trajectory,corridor,mask,provenance=_artifact_parts(artifact)
   _write(directory/'predictor.json',predictor);_write(directory/'trajectory.json',trajectory);_write(directory/'corridor.json',corridor);_write(directory/'mask.json',{'width_px':160,'height_px':120,**mask});_write(directory/'provenance.json',provenance)
  temporary.replace(target)
 except Exception:
  if temporary.exists():shutil.rmtree(temporary)
  raise
def _load_artifact(directory,method):
 if {p.name for p in directory.iterdir()}!=METHOD_FILES:raise ValueError('missing or unknown method file')
 predictor=_read(directory/'predictor.json');trajectory=_read(directory/'trajectory.json');corridor=_read(directory/'corridor.json');mask=_read(directory/'mask.json');provenance=_read(directory/'provenance.json')
 if mask.pop('width_px',None)!=160 or mask.pop('height_px',None)!=120:raise ValueError('invalid mask dimensions')
 raw={**predictor,**trajectory,**corridor,**mask,**provenance}
 if raw.get('method')!=method:raise ValueError('method directory mismatch')
 try:return create_generated_risk_mask(**raw)
 except (TypeError,ValueError) as exc:raise ValueError('tampered artifact') from exc
def load_and_validate_serialized_snapshot(target,expected_manifest_hash):
 from scripts.m6a_dual_roi import DualROISnapshotOutput
 target=Path(target)
 if not target.is_dir() or {p.name for p in target.iterdir()}!=ROOT_FILES:raise ValueError('missing or unknown snapshot output')
 metadata=_read(target/'snapshot_metadata.json');comparison=_read(target/'comparison.json');frame=_read(target/'frame_reference.json')
 if metadata.get('schema_version')!=SCHEMA_VERSION or metadata.get('manifest_hash')!=expected_manifest_hash or set(frame)!={'frame_reference'}:raise ValueError('metadata schema or manifest mismatch')
 state=_load_artifact(target/METHODS[0],METHODS[0]);command=_load_artifact(target/METHODS[1],METHODS[1])
 output=DualROISnapshotOutput(metadata.get('protocol_version'),metadata.get('manifest_hash'),metadata.get('scene'),metadata.get('episode_id'),metadata.get('seed'),metadata.get('snapshot_id'),metadata.get('timestamp_s'),frame['frame_reference'],state,command,comparison)
 _validate_output(output,expected_manifest_hash,VERSION);return output
