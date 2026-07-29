import unittest
from unittest.mock import patch

from scripts.m7_v1_corpus import run_registered_batch, validate_runtime_local_identity_binding


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


class M7V1CorpusIdentityBindingTests(unittest.TestCase):
    def setUp(self):
        self.item = {"attempt_id":"m7v1d-m7c1-710100","episode_id":"m7_v1_development_m7c1_seed710100","scene":"M7C1","seed":710100}
        self.package = {"launch_id":"m6a-launch","attempt_id":self.item["attempt_id"],"identity_id":self.item["episode_id"],"scene_id":self.item["scene"],"seed":self.item["seed"]}
        self.runtime = {"manifest_authority_version":"m7v1","split":"development","episode_id":self.item["episode_id"],"scene":self.item["scene"],"seed":self.item["seed"]}
        self.runtime_identity = {"launch_id":"runtime-local","attempt_id":"runtime-local","identity_id":self.item["episode_id"],"scene_id":self.item["scene"],"seed":self.item["seed"]}

    def bind(self, **changes):
        values = {"item":self.item,"package":self.package,"runtime":self.runtime,"runtime_identity":self.runtime_identity}
        values.update(changes)
        return validate_runtime_local_identity_binding(**values)

    def changed(self, value, **changes):
        return {**value, **changes}

    def test_accepts_exact_runtime_local_to_package_binding(self):
        self.assertEqual(self.bind(), {"launch_id":"m6a-launch","attempt_id":self.item["attempt_id"],"identity_id":self.item["episode_id"],"scene_id":"M7C1","seed":710100})

    def test_rejects_nonlocal_runtime_launch_or_attempt(self):
        for field in ("launch_id", "attempt_id"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(runtime_identity=self.changed(self.runtime_identity, **{field:"m6a-launch"}))

    def test_rejects_package_manifest_identity_mismatch(self):
        for field, value in (("identity_id","other"),("scene_id","M7C2"),("seed",710101),("attempt_id","other")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(package=self.changed(self.package, **{field:value}))

    def test_rejects_runtime_identity_mismatch_even_with_recomputed_evidence_digest(self):
        for field, value in (("identity_id","other"),("scene_id","M7C2"),("seed",710101)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(runtime_identity=self.changed(self.runtime_identity, **{field:value}))

    def test_rejects_split_scene_episode_seed_or_authority_mismatch(self):
        changes = (("split","pilot"),("scene","M7C2"),("episode_id","other"),("seed",710101),("manifest_authority_version","m6v3"))
        for field, value in changes:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(runtime=self.changed(self.runtime, **{field:value}))
