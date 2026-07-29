import unittest
from unittest.mock import patch

from scripts.m7_v1_corpus import run_registered_batch


class M7V1CorpusBatchTests(unittest.TestCase):
    def matrix(self):
        return {"matrix":[{"attempt_id":f"m7-{i}","episode_id":f"episode-{i}","scene":"M7C1","seed":710100+i} for i in range(16)]}

    @patch("scripts.m7_v1_corpus.PACKAGE_ROOT")
    @patch("scripts.m7_v1_corpus.run_research_pilot")
    @patch("scripts.m7_v1_corpus.audit_registered_packages")
    @patch("scripts.m7_v1_corpus.audit_historical_disjointness")
    @patch("scripts.m7_v1_corpus.load_preregistration")
    def test_batch_launches_each_registered_identity_once_without_retry(self, prereg, disjoint, packages, run, package_root):
        prereg.return_value=self.matrix(); run.side_effect=[{"state":"finalized","runner_invoked":True} for _ in range(16)]
        result=run_registered_batch(head="a"*40)
        self.assertEqual(len(result),16);self.assertEqual(run.call_count,16)
        self.assertEqual([call.kwargs["confirm_attempt"] for call in run.call_args_list],[f"m7-{i}" for i in range(16)])

    @patch("scripts.m7_v1_corpus.PACKAGE_ROOT")
    @patch("scripts.m7_v1_corpus.run_research_pilot")
    @patch("scripts.m7_v1_corpus.audit_registered_packages")
    @patch("scripts.m7_v1_corpus.audit_historical_disjointness")
    @patch("scripts.m7_v1_corpus.load_preregistration")
    def test_batch_stops_immediately_on_first_failure(self, prereg, disjoint, packages, run, package_root):
        prereg.return_value=self.matrix();run.side_effect=[{"state":"finalized","runner_invoked":True},{"state":"process_failed","runner_invoked":True}]
        with self.assertRaises(RuntimeError):run_registered_batch(head="a"*40)
        self.assertEqual(run.call_count,2)

    @patch("scripts.m7_v1_corpus.PACKAGE_ROOT")
    @patch("scripts.m7_v1_corpus.run_research_pilot")
    @patch("scripts.m7_v1_corpus.audit_registered_packages")
    @patch("scripts.m7_v1_corpus.audit_historical_disjointness")
    @patch("scripts.m7_v1_corpus.load_preregistration")
    def test_idempotent_or_noninvoked_result_is_not_accepted_as_new_launch(self, prereg, disjoint, packages, run, package_root):
        prereg.return_value=self.matrix();run.return_value={"state":"already_finalized","runner_invoked":False}
        with self.assertRaises(RuntimeError):run_registered_batch(head="a"*40)
        self.assertEqual(run.call_count,1)
