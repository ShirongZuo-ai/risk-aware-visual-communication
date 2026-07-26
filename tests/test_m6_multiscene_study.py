import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.m6_multiscene_study import analyze_episode_cases, load_analysis_amendment, load_preregistration, run_registered_batch, stratified_bootstrap, validate_analysis_identity_binding
from scripts.run_m6a_one_identity import build_one_identity_runtime_config, load_v2_runtime_config
from scripts.m6a_v3_episode_source import LOCK_PATH, MANIFEST_PATH
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_pilot_completion import BUDGET_ORDER, METHODS, load_codec_aggregate_validation, persist_codec_aggregate_validation


def episode(scene,index,effect=.1):
    cases=[]
    for budget in ("severe","low","medium","high"):
        for method,value in (("state_only_risk_roi",.4),("command_conditioned_risk_roi",.4+effect)):
            cases.append({"method":method,"budget":budget,"eligible_count":5,"recalled_count":round(value*5),"tcobr":value,"full_psnr_db":30+(method.startswith("command")),"full_ssim":.8,"charged_bytes":31000,"roi_area_ratio":.1+(method.startswith("command"))*.01})
    return {"episode_id":f"{scene}-{index}","scene":scene,"seed":index,"cases":cases}


def conditional_episodes(effect=.1):
    amendment=load_analysis_amendment();eligible=set(amendment["conditional_analysis"]["eligible_episode_ids"]);episodes=[]
    for scene in range(1,9):
        for offset in range(4):
            seed=630000+scene*100+offset;item=episode(f"S{scene}",seed,effect);item["episode_id"]=f"m6a_v3_formal_s{scene}_seed{seed}"
            if item["episode_id"] not in eligible:
                for case in item["cases"]:case["eligible_count"]=0;case["recalled_count"]=0;case["tcobr"]=None
            episodes.append(item)
    return episodes


class StudyTests(unittest.TestCase):
    def binding_fixture(self):
        row={"attempt_id":"m6v3f-s1-630100","episode_id":"m6a_v3_formal_s1_seed630100","scene":"S1","seed":630100}
        package={"attempt_id":row["attempt_id"],"identity_id":row["episode_id"],"scene_id":row["scene"],"seed":row["seed"],"manifest_authority_version":"v3","manifest_sha256":"manifest","lock_sha256":"lock","prospective_attempt_root":"Z:/attempt"}
        runtime={"split":"formal","episode_id":row["episode_id"],"scene":row["scene"],"seed":row["seed"],"manifest_authority_version":"v3","v2_manifest_sha256":"manifest","v2_lock_sha256":"lock"}
        identity={"launch_id":"runtime-local","attempt_id":"runtime-local","identity_id":row["episode_id"],"scene_id":row["scene"],"seed":row["seed"]}
        return row,package,runtime,identity

    def test_runtime_local_analysis_identity_binds_to_package(self):
        row,package,runtime,identity=self.binding_fixture();self.assertIs(validate_analysis_identity_binding(identity,package,runtime,row,Path("Z:/attempt")),identity)

    def test_analysis_identity_rejects_package_and_scientific_mismatch(self):
        for target,key,value in (("package","attempt_id","wrong"),("package","identity_id","wrong"),("runtime","split","pilot"),("runtime","scene","S2"),("identity","seed",630101)):
            row,package,runtime,identity=self.binding_fixture();{"package":package,"runtime":runtime,"identity":identity}[target][key]=value
            with self.assertRaises(ValueError):validate_analysis_identity_binding(identity,package,runtime,row,Path("Z:/attempt"))

    def test_recomputed_digest_identity_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runtime=build_one_identity_runtime_config(output_root=root/"uncreated")
            snapshots=[]
            for snapshot in runtime["snapshots"]:
                cases=[]
                for method in METHODS:
                    for budget in BUDGET_ORDER:
                        cases.append({"snapshot_id":snapshot["snapshot_id"],"method":method,"budget":budget,"case_sha256":"case","evaluation_sha256":"evaluation","audit_sha256":"audit","charged_bytes":1,"budget_bytes":runtime["budgets"][budget],"full_mse":1.0,"full_psnr_db":1.0,"full_ssim":0.5,"roi_pixel_count":1,"roi_area_ratio":0.1})
                snapshots.append({"snapshot_id":snapshot["snapshot_id"],"cases":cases,"synthetic_fixture":True})
            cases=[case for snapshot in snapshots for case in snapshot["cases"]]
            aggregate={"schema_version":"m6a-v2-codec-aggregate-v2","launch_id":"aggregate","attempt_id":"runtime-local","identity_id":runtime["episode_id"],"scene":runtime["scene"],"seed":runtime["seed"],"runtime_config_sha256":runtime["config_sha256"],"methods":list(METHODS),"budgets":list(BUDGET_ORDER),"snapshot_evidence":snapshots,"expected_case_count":32,"actual_case_count":32,"case_count":32,"per_method_count":{method:16 for method in METHODS},"per_budget_count":{budget:8 for budget in BUDGET_ORDER},"charged_bytes_total":32,"synthetic_fixture":True,"prohibited_usage":0,"fallback":0,"replacement":0,"producer_identity":"test","produced_at_utc":datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
            aggregate["aggregate_sha256"]=digest(aggregate);(root/"codec_aggregate.json").write_text(json.dumps(aggregate,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
            identity={"launch_id":"runtime-local","attempt_id":"runtime-local","identity_id":runtime["episode_id"],"scene_id":runtime["scene"],"seed":runtime["seed"]}
            persist_codec_aggregate_validation(root/"validation.json",runtime,root/"codec_aggregate.json",root=root,identity=identity)
            value=json.loads((root/"validation.json").read_text());value["identity"]["attempt_id"]="package-attempt";value["report_sha256"]=digest({key:item for key,item in value.items() if key!="report_sha256"});(root/"tampered.json").write_text(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
            with self.assertRaises(ValueError):load_codec_aggregate_validation(root/"tampered.json",runtime,root=root,identity=identity)
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
        analysis=analyze_episode_cases(conditional_episodes(.2))
        self.assertEqual(analysis["original_eight_scene_gate"]["status"],"NOT_EVALUATED");self.assertEqual(len(analysis["included"]),17);self.assertTrue(analysis["conditional_analysis"]["support_gate_passed"]);self.assertGreater(analysis["conditional_analysis"]["primary"]["ci_low"],0);self.assertEqual(analysis["secondary_episode_count"],32)

    def test_no_eligible_episode_excluded_only_by_registered_rule(self):
        analysis=analyze_episode_cases(conditional_episodes(.2))
        self.assertEqual(len(analysis["exclusions"]),15);self.assertEqual({item["reason"] for item in analysis["exclusions"]},{"no_eligible_critical_obstacles"});self.assertEqual(len(analysis["secondary_rows"]),32)

    def test_conditional_bootstrap_uses_five_equal_scene_strata(self):
        analysis=analyze_episode_cases(conditional_episodes(.1));primary=analysis["conditional_analysis"]["primary"]
        self.assertEqual(primary["scenes"],["S2","S3","S4","S5","S6"]);self.assertEqual(primary["scene_weighting"],"equal");self.assertAlmostEqual(primary["estimate"],.1)

    def test_conditional_null_or_negative_finding_is_retained(self):
        analysis=analyze_episode_cases(conditional_episodes(-.1));self.assertFalse(analysis["conditional_analysis"]["support_gate_passed"]);self.assertLess(analysis["conditional_analysis"]["primary"]["estimate"],0)

    @patch("scripts.m6_multiscene_study.run_research_pilot")
    @patch("scripts.m6_multiscene_study.load_prepared_launch_package_for_audit")
    @patch("scripts.m6_multiscene_study.verify_prelaunch_gate")
    def test_batch_stops_on_first_failure_without_retry(self,gate,load,run):
        prereg=load_preregistration();gate.return_value=("a"*40,prereg)
        load.side_effect=lambda path:{"head":"a"*40,"identity_id":next(x["episode_id"] for x in prereg["matrix"] if x["attempt_id"]==path.parent.name)}
        run.return_value={"state":"process_failed","runner_invoked":True}
        with self.assertRaises(RuntimeError):run_registered_batch(package_root="Z:/packages")
        self.assertEqual(run.call_count,1)
