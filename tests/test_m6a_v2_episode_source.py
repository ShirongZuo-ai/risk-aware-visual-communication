import unittest
from scripts.m6a_v2_episode_source import build_all,manifest_payload,lock_payload
class T(unittest.TestCase):
 def test_all_sources(self):
  rows=build_all();self.assertEqual(len(rows),56);self.assertEqual(tuple(sum(x.identity['split']==s for x in rows) for s in ('calibration','pilot','formal')),(16,8,32));self.assertEqual(rows[0].snapshot_aligned_times_s,('1.216','2.688','4.192','5.408'));self.assertEqual(rows[0].sha256(),build_all()[0].sha256())
 def test_manifest_is_deterministic(self):
  a=manifest_payload();self.assertEqual(a,manifest_payload());self.assertEqual(lock_payload(a),lock_payload(a));self.assertEqual(a['records'][16]['identity']['episode_id'],'m6a_pilot_s1_seed600100')
