import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_runtime_summary import (Lifecycle, LifecycleState, SceneInitializationEvidence, build_episode_runtime_summary, load_and_validate_episode_runtime_summary, run_v2_controller_lifecycle, validate_episode_runtime_summary)
from scripts.run_m6a_one_identity import build_one_identity_runtime_config
from scripts.m6a_v2_episode_source import load_and_validate_m6a_v2_manifest

class T(unittest.TestCase):
 def fixture(self,episode_id='m6a_pilot_s1_seed600100'):
  d=tempfile.TemporaryDirectory();root=Path(d.name);cfg=build_one_identity_runtime_config(output_root=root/'episode_output',episode_id=episode_id);path=root/'runtime.json';path.write_text(json.dumps(cfg));record=next(x for x in load_and_validate_m6a_v2_manifest()['records'] if x['source_record_sha256']==cfg['source_record_sha256']);evidence=SceneInitializationEvidence(cfg['source_record_sha256'],cfg['seed'],record['scene_config_sha256'],record['scene_config_sha256'],'obstacle','pose',True);records=[]
  for item in cfg['snapshots']:
   p=root/'snapshots'/item['snapshot_id'];p.mkdir(parents=True);raw=root/'raw';raw.mkdir(exist_ok=True);rgb=raw/(item['snapshot_id']+'.rgb');meta=raw/(item['snapshot_id']+'.json');rgb.write_bytes(b'rgb');meta.write_text('{}');snap={'schema_version':'m6a-v2-authoritative-snapshot-record-v1','snapshot_id':item['snapshot_id'],'snapshot_index':int(item['snapshot_id']),'scene':cfg['scene'],'seed':cfg['seed'],'raw_rgb_path':str(rgb),'metadata_json_path':str(meta),'serialized_snapshot_path':str(p)};records.append({'snapshot_id':item['snapshot_id'],'timestamp_s':item['timestamp_s'],'path':str(p),'snapshot_record':snap,'methods':['state_only_risk_roi','command_conditioned_risk_roi'],'actual_future_usage':0,'combined_usage':0,'raw_mask_usage':0,'fallback':0,'replacement':0})
  return d,root,cfg,path,evidence,records
 def test_lifecycle_enforces_scene_before_devices_and_persists_summary(self):
  d,root,cfg,path,evidence,records=self.fixture();self.addCleanup(d.cleanup);calls=[]
  def init(supervisor,config):calls.append('scene');return evidence
  def devices(supervisor,config):calls.append('devices')
  def episode(supervisor,config):calls.append('episode');return records
  with patch('scripts.m6a_v2_runtime_summary.initialize_v2_scene_before_motion',init):code,lifecycle=run_v2_controller_lifecycle(path,supervisor_factory=lambda:(calls.append('supervisor') or object()),devices_initializer=devices,episode_runner=episode,summary_path=root/'summary.json',status_path=root/'status.json')
  self.assertEqual(code,0);self.assertEqual(calls,['supervisor','scene','devices','episode']);self.assertEqual(lifecycle.transitions,['CONFIG_VALIDATED','SCENE_INITIALIZED','DEVICES_READY','EPISODE_RUNNING','EPISODE_COMPLETED','SUMMARY_COMMITTED']);summary=load_and_validate_episode_runtime_summary(root/'summary.json',cfg,require_paths=True);self.assertEqual(summary['actual_snapshot_count'],4);self.assertEqual(summary['method_set'],['command_conditioned_risk_roi','state_only_risk_roi'])
 def test_tampering_duplicate_and_failure_never_create_success_summary(self):
  d,root,cfg,path,evidence,records=self.fixture();self.addCleanup(d.cleanup);life=Lifecycle();life.transition(LifecycleState.CONFIG_VALIDATED);life.transition(LifecycleState.SCENE_INITIALIZED);life.transition(LifecycleState.DEVICES_READY);life.transition(LifecycleState.EPISODE_RUNNING);life.transition(LifecycleState.EPISODE_COMPLETED)
  summary=build_episode_runtime_summary(cfg,evidence,records,life);summary['method_set']=['state_only_risk_roi']
  with self.assertRaises(ValueError):validate_episode_runtime_summary(summary,cfg)
  with self.assertRaises(ValueError):build_episode_runtime_summary(cfg,evidence,records[:3],life)
  def fail_devices(supervisor,config):raise ValueError('device failure')
  with patch('scripts.m6a_v2_runtime_summary.initialize_v2_scene_before_motion',lambda supervisor,config:evidence),redirect_stderr(io.StringIO()):code,lifecycle=run_v2_controller_lifecycle(path,supervisor_factory=object,devices_initializer=fail_devices,episode_runner=lambda *_:records,summary_path=root/'failure_summary.json',status_path=root/'failure_status.json')
  self.assertEqual(code,1);self.assertEqual(lifecycle.state,LifecycleState.FAILED);self.assertFalse((root/'failure_summary.json').exists());self.assertFalse(json.loads((root/'failure_status.json').read_text())['success'])
 def test_pilot_and_formal_splits_bind_exactly_and_tamper_fails(self):
  for episode_id in ('m6a_pilot_s1_seed600100','m6a_formal_s1_seed620101'):
   d,root,cfg,path,evidence,records=self.fixture(episode_id);self.addCleanup(d.cleanup);life=Lifecycle()
   for state in (LifecycleState.CONFIG_VALIDATED,LifecycleState.SCENE_INITIALIZED,LifecycleState.DEVICES_READY,LifecycleState.EPISODE_RUNNING,LifecycleState.EPISODE_COMPLETED):life.transition(state)
   summary=build_episode_runtime_summary(cfg,evidence,records,life);self.assertEqual(validate_episode_runtime_summary(summary,cfg)['identity']['split'],cfg['split'])
   summary['identity']={**summary['identity'],'split':'formal' if cfg['split']=='pilot' else 'pilot'};summary['summary_sha256']=digest({key:value for key,value in summary.items() if key!='summary_sha256'})
   with self.assertRaises(ValueError):validate_episode_runtime_summary(summary,cfg)
