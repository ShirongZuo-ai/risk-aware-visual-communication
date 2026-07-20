import unittest
from scripts.m6a_dual_roi import CurrentState,ScheduleEvidence
from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_trusted_artifacts import M6AProjectionConfig
from scripts.m6a_mask_generation import *
class T(unittest.TestCase):
 def test_generators(self):
  s=CurrentState(0,0,0,.1,0);c=M6AProjectionConfig();q=ScheduleEvidence('x',0,(CommandSegment(0,2,1,2),))
  a=generate_state_only_risk_mask(s,c);b=generate_command_conditioned_risk_mask(s,q,c,timestamp_s=0)
  self.assertEqual(a.footprint_digest,b.footprint_digest);self.assertNotEqual(a.source_predictor,b.source_predictor)
 def test_late_schedule(self):
  with self.assertRaises(ValueError):generate_command_conditioned_risk_mask(CurrentState(0,0,0,0,0),ScheduleEvidence('x',1,(CommandSegment(0,2,1,1),)),M6AProjectionConfig(),timestamp_s=0)
 def test_schedule_digest_is_canonical_and_sensitive(self):
  s=CurrentState(0,0,0,.1,0);c=M6AProjectionConfig()
  one=ScheduleEvidence('x',0,(CommandSegment(0,1,1,2),CommandSegment(1,2,2,1)))
  same=ScheduleEvidence('x',0,(CommandSegment(0,1,1,2),CommandSegment(1,2,2,1)))
  changed=ScheduleEvidence('x',0,(CommandSegment(0,1,1,3),CommandSegment(1,2,2,1)))
  a=generate_command_conditioned_risk_mask(s,one,c,timestamp_s=0);b=generate_command_conditioned_risk_mask(s,same,c,timestamp_s=0);d=generate_command_conditioned_risk_mask(s,changed,c,timestamp_s=0)
  self.assertEqual(a.predictor_input_digest,b.predictor_input_digest);self.assertNotEqual(a.predictor_input_digest,d.predictor_input_digest)
