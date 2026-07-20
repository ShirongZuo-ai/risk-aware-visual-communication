import json,unittest
from navigation.trajectory_prediction import CommandSegment
from risk_map.image_risk_map import Mask2D
from scripts.m6a_dual_roi import CurrentState,Method,ScheduleEvidence,predict,provenance,select_mask
from scripts.m6a_dual_roi import SnapshotInput,process_m6a_snapshot,serialize_snapshot
from pathlib import Path
import tempfile
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
 def test_snapshot_and_serializer(self):
  out=process_m6a_snapshot(SnapshotInput('m6a-byte-fair-v1','x','S1','e',1,'0',0,self.s,'frame.png',self.c),state_mask=self.m,command_mask=self.m);self.assertEqual(set(out['methods']),{m.value for m in Method})
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'snapshot';serialize_snapshot(out,p);self.assertTrue((p/'state_only_risk_roi'/'output.json').exists())
   with self.assertRaises(FileExistsError):serialize_snapshot(out,p)
