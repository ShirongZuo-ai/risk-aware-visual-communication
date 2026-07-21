import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_launch_spec import (WebotsExecutableEvidence, build_one_identity_launch_spec, owned_cleanup_plan, resolve_webots_executable, validate_one_identity_launch_result)
from scripts.m6a_v2_runtime_summary import Lifecycle, LifecycleState, SceneInitializationEvidence, build_episode_runtime_summary, persist_episode_runtime_summary
from scripts.m6a_v2_episode_source import LOCK_PATH, MANIFEST_PATH, load_and_validate_m6a_v2_manifest

class T(unittest.TestCase):
 def test_executable_detection_uses_safe_list_probe_and_rejects_bad_version(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'Webots R2025a.exe';exe.write_bytes(b'fake')
   with patch('scripts.m6a_v2_launch_spec._probe_version',return_value='R2025a') as probe:
    evidence=resolve_webots_executable(exe);self.assertEqual(evidence.path,str(exe.resolve()));probe.assert_called_once_with(exe)
   with patch('scripts.m6a_v2_launch_spec._probe_version',side_effect=ValueError('unsupported')):
    with self.assertRaises(ValueError):resolve_webots_executable(exe)
  with self.assertRaises(ValueError):resolve_webots_executable('relative.exe')
 def spec(self):
  d=tempfile.TemporaryDirectory();base=Path(d.name);exe=base/'Webots R2025a.exe';exe.write_bytes(b'fake');root=base/'launch root'
  evidence=WebotsExecutableEvidence(str(exe.resolve()),'R2025a','test',0)
  with patch('scripts.m6a_v2_launch_spec.resolve_webots_executable',return_value=evidence):spec=build_one_identity_launch_spec(MANIFEST_PATH,LOCK_PATH,preflight_root=root,webots_executable=exe)
  return d,spec
 def test_launch_spec_is_preflight_only_and_owned(self):
  d,spec=self.spec();self.addCleanup(d.cleanup);self.assertFalse(spec['execution_authorized']);self.assertFalse(spec['webots_started']);self.assertIsInstance(spec['argv'],list);self.assertEqual(spec['argv'][0],spec['webots']['path']);self.assertEqual(spec['environment_keys'],['M6A_RUNTIME_CONFIG']);self.assertEqual(spec['expected'],{'episodes':1,'snapshots':4,'methods':2,'budgets':4,'future_cases':32});self.assertTrue(all(str(path).startswith(spec['owned_root']) for path in owned_cleanup_plan(spec)))
 def test_synthetic_success_requires_summary_and_rejects_host_code_alone(self):
  d,spec=self.spec();self.addCleanup(d.cleanup)
  with self.assertRaises(ValueError):validate_one_identity_launch_result(spec,{'started':True,'returncode':0,'timed_out':False,'interrupted':False})
  runtime=json.loads(Path(spec['runtime_config']['path']).read_text());record=next(x for x in load_and_validate_m6a_v2_manifest()['records'] if x['source_record_sha256']==runtime['source_record_sha256']);evidence=SceneInitializationEvidence(runtime['source_record_sha256'],runtime['seed'],record['scene_config_sha256'],record['scene_config_sha256'],'obstacle','pose',True);records=[]
  root=Path(spec['owned_root'])
  for item in runtime['snapshots']:
   path=root/'snapshots'/item['snapshot_id'];path.mkdir(parents=True);records.append({'snapshot_id':item['snapshot_id'],'timestamp_s':item['timestamp_s'],'path':str(path),'methods':['state_only_risk_roi','command_conditioned_risk_roi'],'actual_future_usage':0,'combined_usage':0,'raw_mask_usage':0,'fallback':0,'replacement':0})
  life=Lifecycle()
  for state in (LifecycleState.CONFIG_VALIDATED,LifecycleState.SCENE_INITIALIZED,LifecycleState.DEVICES_READY,LifecycleState.EPISODE_RUNNING,LifecycleState.EPISODE_COMPLETED):life.transition(state)
  summary=build_episode_runtime_summary(runtime,evidence,records,life);summary['lifecycle_final_state']='SUMMARY_COMMITTED';summary['summary_sha256']=digest({k:v for k,v in summary.items() if k!='summary_sha256'});persist_episode_runtime_summary(summary,spec['summary_path'],spec['status_path'],runtime)
  self.assertTrue(validate_one_identity_launch_result(spec,{'started':True,'returncode':0,'timed_out':False,'interrupted':False})['success'])
  with self.assertRaises(ValueError):validate_one_identity_launch_result(spec,{'started':True,'returncode':0,'timed_out':True,'interrupted':False})
