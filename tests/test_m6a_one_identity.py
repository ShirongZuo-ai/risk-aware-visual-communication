import json,subprocess,unittest
from scripts.m6a_common import PROJECT_ROOT
from scripts.run_m6a_one_identity import plan
class T(unittest.TestCase):
 def test_first_identity_and_scale(self):
  p=plan(PROJECT_ROOT/'docs/results/m6a_manifest.json');self.assertEqual(p['identity']['episode_id'],'m6a_pilot_s1_seed600100');self.assertEqual((p['expected_episodes'],p['expected_snapshots'],p['expected_methods'],p['expected_budgets'],p['future_reconstruction_cases']),(1,4,2,4,32));self.assertFalse(p['webots_started'])
