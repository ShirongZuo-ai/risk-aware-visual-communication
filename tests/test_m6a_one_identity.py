import unittest
from scripts.run_m6a_one_identity import plan
class T(unittest.TestCase):
 def test_first_identity_and_scale(self):
  p=plan();self.assertEqual(p['identity']['episode_id'],'m6a_pilot_s1_seed600100');self.assertEqual((p['expected_episodes'],p['expected_snapshots'],p['expected_methods'],p['expected_budgets'],p['future_reconstruction_cases']),(1,4,2,4,32));self.assertFalse(p['webots_started'])
