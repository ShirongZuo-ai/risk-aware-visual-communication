import unittest
from unittest.mock import patch

from scripts.m6_multiscene_study import analyze_episode_cases, load_preregistration, run_registered_batch, stratified_bootstrap
from scripts.run_m6a_one_identity import build_one_identity_runtime_config, load_v2_runtime_config
from scripts.m6a_v3_episode_source import LOCK_PATH, MANIFEST_PATH


def episode(scene,index,effect=.1):
    cases=[]
    for budget in ("severe","low","medium","high"):
        for method,value in (("state_only_risk_roi",.4),("command_conditioned_risk_roi",.4+effect)):
            cases.append({"method":method,"budget":budget,"eligible_count":5,"recalled_count":round(value*5),"tcobr":value,"full_psnr_db":30+(method.startswith("command")),"full_ssim":.8,"charged_bytes":31000,"roi_area_ratio":.1+(method.startswith("command"))*.01})
    return {"episode_id":f"{scene}-{index}","scene":scene,"seed":index,"cases":cases}


class StudyTests(unittest.TestCase):
    def test_committed_matrix_is_exact_frozen_v3_formal_split(self):
        value=load_preregistration();self.assertEqual(len(value["matrix"]),32);self.assertEqual({x["scene"] for x in value["matrix"]},{f"S{i}" for i in range(1,9)});self.assertEqual({x["seed"] for x in value["matrix"]},{630000+s*100+i for s in range(1,9) for i in range(4)})

    def test_formal_identity_runtime_binding(self):
        cfg=build_one_identity_runtime_config(MANIFEST_PATH,LOCK_PATH,output_root="Z:/new-root",episode_id="m6a_v3_formal_s8_seed630803")
        self.assertEqual((cfg["split"],cfg["scene"],cfg["seed"]),("formal","S8",630803));self.assertIs(load_v2_runtime_config(cfg),cfg)

    def test_unknown_and_wrong_identity_fail_closed(self):
        with self.assertRaises(ValueError):build_one_identity_runtime_config(MANIFEST_PATH,LOCK_PATH,output_root="Z:/new-root",episode_id="unknown")

    def test_stratified_bootstrap_is_deterministic(self):
        rows=[{"scene":f"S{s}","value":s/100+i/1000} for s in range(1,9) for i in range(4)]
        self.assertEqual(stratified_bootstrap(rows,"value",replicates=100,seed=7),stratified_bootstrap(rows,"value",replicates=100,seed=7))

    def test_episode_analysis_and_support_gate(self):
        analysis=analyze_episode_cases([episode(f"S{s}",i,.2) for s in range(1,9) for i in range(4)])
        self.assertEqual(len(analysis["included"]),32);self.assertTrue(analysis["support_gate_passed"]);self.assertGreater(analysis["primary"]["ci_low"],0)

    def test_no_eligible_episode_excluded_only_by_registered_rule(self):
        episodes=[episode(f"S{s}",i,.2) for s in range(1,9) for i in range(4)]
        episodes[0]["cases"][0]["eligible_count"]=0
        analysis=analyze_episode_cases(episodes)
        self.assertEqual(analysis["exclusions"],[{"episode_id":"S1-0","reason":"no_eligible_critical_obstacles"}])

    @patch("scripts.m6_multiscene_study.run_research_pilot")
    @patch("scripts.m6_multiscene_study.load_prepared_launch_package_for_audit")
    @patch("scripts.m6_multiscene_study.verify_prelaunch_gate")
    def test_batch_stops_on_first_failure_without_retry(self,gate,load,run):
        prereg=load_preregistration();gate.return_value=("a"*40,prereg)
        load.side_effect=lambda path:{"head":"a"*40,"identity_id":next(x["episode_id"] for x in prereg["matrix"] if x["attempt_id"]==path.parent.name)}
        run.return_value={"state":"process_failed","runner_invoked":True}
        with self.assertRaises(RuntimeError):run_registered_batch(package_root="Z:/packages")
        self.assertEqual(run.call_count,1)
