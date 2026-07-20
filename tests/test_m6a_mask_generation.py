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
