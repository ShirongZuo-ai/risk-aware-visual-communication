import json,unittest
from unittest.mock import patch
from navigation.trajectory_prediction import CommandSegment
from risk_map.image_risk_map import Mask2D
from scripts.m6a_dual_roi import CurrentState,Method,ScheduleEvidence,predict,provenance,select_mask
from scripts.m6a_dual_roi import SnapshotInput,process_m6a_snapshot
from scripts.m6a_trusted_artifacts import M6AProjectionConfig
class M6ADualRoiTests(unittest.TestCase):
 def setUp(self): self.s=CurrentState(0,0,0,.1,0);self.m=Mask2D(2,2,(1,0,0,0));self.c=ScheduleEvidence('plan',0,(CommandSegment(0,2,2,2),))
 def test_state_and_command_boundaries(self):
  self.assertTrue(predict(Method.STATE_ONLY_RISK_ROI,self.s))
  with self.assertRaises(ValueError):predict(Method.STATE_ONLY_RISK_ROI,self.s,schedule=self.c)
  with self.assertRaises(ValueError):predict(Method.COMMAND_CONDITIONED_RISK_ROI,self.s)
  with self.assertRaises(ValueError):predict(Method.COMMAND_CONDITIONED_RISK_ROI,self.s,schedule=ScheduleEvidence('late',1,self.c.segments),snapshot_time_s=0)
 def test_leakage_and_combined_rejected(self):
  with self.assertRaises(ValueError):predict(Method.STATE_ONLY_RISK_ROI,self.s,forbidden={'actual_future_trajectory':[]})
  with self.assertRaises(ValueError):select_mask(Method.STATE_ONLY_RISK_ROI,state_mask=self.m,mode='combined')
 def test_provenance_is_deterministic_and_serializable(self):
  t=predict(Method.COMMAND_CONDITIONED_RISK_ROI,self.s,schedule=self.c);a=provenance(method=Method.COMMAND_CONDITIONED_RISK_ROI,state=self.s,trajectory=t,mask=self.m,manifest_hash='x',scene='S1',episode_id='e',seed=1,snapshot_id='0',snapshot_time_s=0,schedule=self.c);b=provenance(method=Method.COMMAND_CONDITIONED_RISK_ROI,state=self.s,trajectory=t,mask=self.m,manifest_hash='x',scene='S1',episode_id='e',seed=1,snapshot_id='0',snapshot_time_s=0,schedule=self.c);json.dumps(a);self.assertEqual(a['mask_sha256'],b['mask_sha256']);self.assertEqual(a['actual_future_usage_count'],0)
 def test_production_snapshot_generates_exactly_two_trusted_artifacts(self):
  item=SnapshotInput('m6a-byte-fair-v1','x','S1','e',1,'0',0,self.s,'frame.png',self.c);config=M6AProjectionConfig();out=process_m6a_snapshot(item,config)
  self.assertEqual(set(out['methods']),{m.value for m in Method});self.assertEqual(out['snapshot']['snapshot_id'],'0')
  state=out['methods'][Method.STATE_ONLY_RISK_ROI.value];command=out['methods'][Method.COMMAND_CONDITIONED_RISK_ROI.value]
  self.assertEqual(state.source_predictor,'state_only_predictor');self.assertEqual(command.source_predictor,'command_conditioned_predictor')
  self.assertEqual(state.predictor_config_digest,command.predictor_config_digest);self.assertEqual(out['comparison']['shared_projection_config_digest'],config.sha256())
  self.assertEqual(out['comparison']['allowed_input_difference'],['predictor identity','predefined_future_command_schedule'])
  self.assertTrue(all(out['comparison'][key]==0 for key in ('actual_future_usage_count','combined_usage_count','raw_mask_usage_count','fallback_count','replacement_count')))
 def test_production_snapshot_calls_each_trusted_generator_once(self):
  from scripts import m6a_mask_generation as bridge
  item=SnapshotInput('m6a-byte-fair-v1','x','S1','e',1,'0',0,self.s,'frame.png',self.c);config=M6AProjectionConfig()
  with patch.object(bridge,'generate_state_only_risk_mask',wraps=bridge.generate_state_only_risk_mask) as state_generator,patch.object(bridge,'generate_command_conditioned_risk_mask',wraps=bridge.generate_command_conditioned_risk_mask) as command_generator:
   process_m6a_snapshot(item,config)
  state_generator.assert_called_once_with(self.s,config);command_generator.assert_called_once_with(self.s,self.c,config,timestamp_s=0)
 def test_production_snapshot_rejects_all_raw_mask_arguments(self):
  item=SnapshotInput('m6a-byte-fair-v1','x','S1','e',1,'0',0,self.s,'frame.png',self.c);config=M6AProjectionConfig()
  with self.assertRaises(TypeError):process_m6a_snapshot(item,config,self.m)
  for name in ('state_mask','command_mask','mask','combined_mask','oracle_mask','actual_future','future_trace'):
   with self.subTest(name=name):
    with self.assertRaises(TypeError):process_m6a_snapshot(item,config,**{name:self.m})
