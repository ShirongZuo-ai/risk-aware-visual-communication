import unittest
from scripts.m6a_common import BUDGETS, METHODS, episodes, manifest, validate
class M6AProtocolTests(unittest.TestCase):
 def test_schedule_is_episode_disjoint_and_complete(self):
  result=validate(manifest()); self.assertEqual(result['formal_episodes'],32); self.assertEqual(result['formal_frames'],128); self.assertEqual(result['formal_cases'],1024)
  self.assertFalse({x.seed for x in episodes('calibration')} & {x.seed for x in episodes('formal')})
 def test_leakage_and_budget_changes_rejected(self):
  data=manifest(); data['actual_future_trajectory_used_by_methods']=True
  with self.assertRaises(ValueError): validate(data)
  data=manifest(); data['target_bytes']={**BUDGETS,'high':34872}
  with self.assertRaises(ValueError): validate(data)
 def test_primary_methods_are_exact(self): self.assertEqual(METHODS,('state_only_risk_roi','command_conditioned_risk_roi'))
