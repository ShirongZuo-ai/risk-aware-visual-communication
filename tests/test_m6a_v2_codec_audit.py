import tempfile
import unittest
from pathlib import Path

import numpy as np

from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_v2_codec_audit import (SnapshotCodecInput, build_and_audit_one_identity_cases, build_method_mask, encode_reconstruct_case, evaluate_codec_case, audit_codec_case)
from scripts.run_m6a_one_identity import build_one_identity_runtime_config

class T(unittest.TestCase):
 def fixture(self):
  d=tempfile.TemporaryDirectory();root=Path(d.name);cfg=build_one_identity_runtime_config(output_root=root/'episode_output');schedule=ScheduleEvidence('frozen',0.,tuple(CommandSegment(x['start_s'],x['end_s'],x['left_rad_s'],x['right_rad_s']) for x in cfg['schedule']['segments']));image=np.zeros((120,160,3),dtype=np.uint8);image[:,:,0]=np.arange(160,dtype=np.uint8);state=CurrentState(0.,0.,0.,.04,0.);snapshots=[SnapshotCodecInput.create(runtime_config=cfg,snapshot_id=item['snapshot_id'],timestamp_s=item['timestamp_s'],image=image,state=state,schedule=schedule,synthetic_fixture=True) for item in cfg['snapshots']];return d,root,cfg,snapshots
 def test_frozen_schema_masks_codec_and_audit_are_deterministic(self):
  d,root,cfg,snapshots=self.fixture();self.addCleanup(d.cleanup);self.assertEqual(tuple(cfg['methods']),('state_only_risk_roi','command_conditioned_risk_roi'));self.assertEqual(cfg['budgets'],{'severe':31466,'low':32374,'medium':33509,'high':34871})
  evidence,payload=build_method_mask(cfg,snapshots[0],'state_only_risk_roi');case=encode_reconstruct_case(cfg,snapshots[0],evidence,payload,'severe');evaluation=evaluate_codec_case(cfg,snapshots[0],case);self.assertLessEqual(case.charged_bytes,case.budget_bytes);self.assertTrue(audit_codec_case(cfg,snapshots[0],evidence,payload,case,evaluation)['passed']);self.assertEqual(case.case_sha256,encode_reconstruct_case(cfg,snapshots[0],evidence,payload,'severe').case_sha256)
 def test_forbidden_input_and_overrides_fail_closed(self):
  d,root,cfg,snapshots=self.fixture();self.addCleanup(d.cleanup);schedule=snapshots[0].schedule
  with self.assertRaises(ValueError):SnapshotCodecInput.create(runtime_config=cfg,snapshot_id='0',timestamp_s=1.216,image=snapshots[0].image,state=snapshots[0].state,schedule=schedule,actual_future_trace=[])
  with self.assertRaises(ValueError):build_method_mask(cfg,snapshots[0],'oracle')
  evidence,payload=build_method_mask(cfg,snapshots[0],'state_only_risk_roi')
  with self.assertRaises(ValueError):encode_reconstruct_case(cfg,snapshots[0],evidence,payload,'arbitrary')
 def test_exact_synthetic_32_case_matrix(self):
  d,root,cfg,snapshots=self.fixture();self.addCleanup(d.cleanup);aggregate=build_and_audit_one_identity_cases(cfg,snapshots,safe_output_root=root/'synthetic-audit');self.assertEqual(aggregate['case_count'],32);self.assertTrue(aggregate['synthetic_fixture']);self.assertFalse(aggregate['scientific_result']);self.assertFalse(aggregate['execution_authorized']);self.assertEqual(aggregate['prohibited_usage'],0)
