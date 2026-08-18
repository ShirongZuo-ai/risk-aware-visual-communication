"""Outcome-blind preparation, one-shot execution, and locked M9-A analysis."""
from __future__ import annotations
import argparse,json,os,subprocess
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve
from evaluation.m9a_formal_analysis import *
from scripts.m9a_formal_access import authorize_once,sha256_file
from simulator.m9a_config import seed_for,Split,ScenarioFamily
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"results/m9a_formal";LOGS=ROOT/"data/logs/m9a/formal"
FROZEN={"protocol":"5a3e95a0b1c7b0196541261a826ab77486e38ddaec451bf7f9f18fc32ae81f86","physical_footprint":"adc36e15393b94438ba74174ead90291b87e1635cd56e5de45e7f457e3241f4a","scenario_grid":"0c0b4e54b0867bc95206830db207bda176b3865770b5370dd4fbec3eca0a89c9","seed_mapping":"05941f211896bdc82238721871ba24dc1ff1c31757111c825911d7dee325d008","log_schema":"677110fe25a5053d11ab5b691beba140bdf04ad04aeef88a7aca538506dc7ff0","calibration_near":"1bf9778cb73551f437c8c322214a98b48dcad21d41b66098bab537b23046f349"}
def write(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def side(path):d=sha256_file(path);path.with_suffix(path.suffix+".sha256").write_text(f"{d}  {path.name}\n");return d
def cells():return json.loads((ROOT/"docs/results/m9a_i1_scenario_grid.json").read_text())["cells"]
def prepare():
 if LOGS.exists() and any(LOGS.iterdir()):raise RuntimeError("formal outcome directory nonempty")
 records=[];head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
 for c in cells():
  for r in range(3):
   cfg={k:v for k,v in c.items() if k not in ("episode_id","seed")};eid=f"m9a-formal-{c['family_id'].lower()}-{c['parameter_set_id'].lower()}-r{r:02d}";cfg.update(episode_id=eid,seed=seed_for(Split.FORMAL,ScenarioFamily(c["family_id"]),c["parameter_set_id"],r),split="formal",purpose="formal_evaluation");cp=OUT/"configs"/(eid+".json");write(cp,cfg)
   records.append({"formal_episode_id":eid,"family":c["family_id"],"parameter_cell":c["parameter_set_id"],"replicate":r,"seed":cfg["seed"],"scenario_parameters":cfg,"world":"simulator/worlds/m9a_pilot_runner.wbt","config_path":cp.relative_to(ROOT).as_posix(),"expected_log_path":LOGS.joinpath(eid+".jsonl").relative_to(ROOT).as_posix(),"protocol_version":"m9a-p-v2","scenario_grid_version":"m9a-i1-grid-v7","physical_footprint_version":"webots-r2025a-epuck-collision-cylinder-v1","simulator_timestep_s":.032,"generation_implementation_identity":{"controller_sha256":sha256_file(ROOT/"simulator/controllers/m9a_pilot_runner/m9a_pilot_runner.py"),"git_head":head}})
 manifest=OUT/"formal_manifest.json";write(manifest,{"schema_version":"m9a-formal-manifest-v1","planned_episode_count":len(records),"outcome_free":True,"episodes":records});md=side(manifest)
 alg=OUT/"warning_threshold_algorithm.json";write(alg,{"version":"m9a-warning-v1","source":"calibration_only","candidate_thresholds":"unique observed scores descending","objective":"maximum episode detection with false warnings <=0.5/min","tie_break":"higher threshold","debounce_steps":3,"refractory_s":.5});side(alg)
 cal=[load_episode(ROOT/"data/logs/m9a/calibration"/(p.stem+".jsonl"),p,2.) for p in sorted((ROOT/"results/m9a_calibration/configs").glob("*.json"))];dec={m:select_warning_threshold(cal,m) for m in ("R0","R1","R2")};wd=OUT/"calibration_warning_decision.json";write(wd,{"schema_version":"m9a-calibration-warning-v1","algorithm_sha256":sha256_file(alg),"calibration_episode_ids":[e["episode_id"] for e in cal],"methods":dec});wdd=side(wd)
 boot=OUT/"bootstrap_config.json";write(boot,{"version":"m9a-bootstrap-v1","replicates":10000,"rng":"numpy-PCG64","seed":20260901,"ci":"percentile","unit":"episode","strata":"family","paired":True,"pooling":"macro average family AP","no_positive_family":"omit; fail if none"});bd=side(boot)
 impl=sha256_file(ROOT/"evaluation/m9a_formal_analysis.py");contract=OUT/"analysis_contract.json";write(contract,{"schema_version":"m9a-formal-analysis-contract-v1","frozen_inputs":{**FROZEN,"formal_manifest":md,"warning":wdd,"bootstrap":bd},"implementations":{"module_sha256":impl,"R0":"negative current physical clearance","R1":"M2 state-only to negative minimum physical clearance","R2":"M2 command-conditioned to identical geometry","labels":"dense actual trajectory plus bilateral contact","auprc":"sklearn 1.7.2 average_precision_score; positive=True; tied thresholds grouped; no weights; NaN without positives"},"primary":{"horizon_s":2.,"label":"danger","effect_floor":.05,"C2":["R1","R0"],"C3":["R2","R1"],"pass":"delta>=.05 and CI lower>0"},"geometry":{"physical_radius_m":.037,"near_m":.013,"m3_corridor_radius_m":.037592257,"m3_supplementary_only":True},"bootstrap":json.loads(boot.read_text()),"warnings":dec,"support":{"valid":120,"collision":32,"near":32,"safe":40,"F1_F7_each":4,"F8_safe":12,"transition_danger":16,"lead_time_each":24},"secondary":["detection","false_warnings/min","lead_time","misses","Spearman","MAE"],"supplementary":["0.5s","1.0s","collision/near AUPRC","AUROC","RMSE","Pearson","TTCf","corridor","M3"]});cd=side(contract)
 assert auprc([1,1,0,0],[4,3,2,1])==1 and auprc([1,0,1,0],[1,1,1,1])==.5;write(OUT/"dry_run_report.json",{"passed":True,"synthetic_cases":["perfect","manual","all-tied"],"contract_sha256":cd})
def authorize():
 paths={"protocol":ROOT/"docs/m9a_p_future_danger_protocol.md","physical_footprint":ROOT/"docs/m9a_physical_footprint_review.md","scenario_grid":ROOT/"docs/results/m9a_i1_scenario_grid.json","seed_mapping":ROOT/"docs/m9a_i1_seed_mapping.md","log_schema":ROOT/"docs/results/m9a_p_step_log_schema.json","calibration_near":ROOT/"results/m9a_calibration/calibration_decision.json","formal_manifest":OUT/"formal_manifest.json","calibration_warning_threshold":OUT/"calibration_warning_decision.json","analysis_contract":OUT/"analysis_contract.json"};expected={k:sha256_file(v) for k,v in paths.items()}
 for k,v in FROZEN.items():
  if expected[k]!=v:raise RuntimeError(f"frozen digest mismatch {k}: {expected[k]}")
 authorize_once(formal_unlock=True,authorization_id="M9A-FORMAL20260813ZS01",actor="codex-m9a-fr",ledger=OUT/"formal_access_ledger.jsonl",expected_digests=expected,artifact_paths=paths)
def generate():
 es=json.loads((OUT/"formal_manifest.json").read_text())["episodes"];exe=Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe");LOGS.mkdir(parents=True,exist_ok=False);runtime=OUT/"runtime";runtime.mkdir(exist_ok=True);head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
 for n,e in enumerate(es,1):
  env=os.environ.copy();env.update(M9A_PILOT_CONFIG=str(ROOT/e["config_path"]),M9A_PILOT_OUTPUT=str(ROOT/e["expected_log_path"]),M9A_GIT_HEAD=head);p=subprocess.run([str(exe),"--batch","--mode=fast",str(ROOT/e["world"])],cwd=ROOT,env=env,capture_output=True,text=True,timeout=90);(runtime/(e["formal_episode_id"]+".stdout.txt")).write_text(p.stdout);(runtime/(e["formal_episode_id"]+".stderr.txt")).write_text(p.stderr)
  if p.returncode or not (ROOT/e["expected_log_path"]).exists():raise RuntimeError(f"episode failure {e['formal_episode_id']}")
  if n%12==0:print(f"generated {n}/144",flush=True)
def analyze():
 es=json.loads((OUT/"formal_manifest.json").read_text())["episodes"];byh={h:[load_episode(ROOT/e["expected_log_path"],ROOT/e["config_path"],h) for e in es] for h in HORIZONS};eps=byh[2.];comp={"valid":len(eps),"collision":sum(e["episode_collision"] for e in eps),"near":sum(not e["episode_collision"] and e["episode_min_clearance_m"]<NEAR_M for e in eps),"safe":sum(e["episode_min_clearance_m"]>=NEAR_M for e in eps),"families":{}}
 for f in sorted({e["family"] for e in eps}):
  q=[e for e in eps if e["family"]==f];comp["families"][f]={"collision":sum(e["episode_collision"] for e in q),"near":sum(not e["episode_collision"] and e["episode_min_clearance_m"]<NEAR_M for e in q),"safe":sum(e["episode_min_clearance_m"]>=NEAR_M for e in q)}
 support=comp["valid"]>=120 and comp["collision"]>=32 and comp["near"]>=32 and comp["safe"]>=40 and all(min(comp["families"][f].values())>=4 for f in [f"F{i}" for i in range(1,8)]) and comp["families"]["F8"]["safe"]>=12;primary={m:family_macro_auprc(eps,m) for m in ("R0","R1","R2")};contr={}
 for c,a,b in (("C2","R1","R0"),("C3","R2","R1")):
  d=primary[a]-primary[b];ci=paired_bootstrap(eps,a,b);contr[c]={"delta":d,"ci95":ci,"decision":"PASS" if support and d>=.05 and ci["lower"]>0 else ("insufficient_support" if not support else "FAIL")}
 samples=[x for e in eps for x in e["samples"]];th=json.loads((OUT/"calibration_warning_decision.json").read_text())["methods"];sec={m:{**correlations(samples,m),"warning_events":sum(len(warning_runs(e["samples"],m,th[m]["threshold"])) for e in eps)} for m in ("R0","R1","R2")};res={"composition":comp,"support_pass":support,"primary_auprc":primary,"contrasts":contr,"secondary":sec,"supplementary_horizon_auprc":{str(h):{m:family_macro_auprc(q,m) for m in ("R0","R1","R2")} for h,q in byh.items()}};write(OUT/"formal_results.json",res);side(OUT/"formal_results.json")
 tab=OUT/"tables";write(tab/"table1_corpus.json",comp);write(tab/"table2_primary.json",{"auprc":primary,"contrasts":contr});write(tab/"table3_secondary.json",sec);write(tab/"table4_stratified.json",{f:{m:family_macro_auprc([e for e in eps if e["family"]==f],m) for m in ("R0","R1","R2")} for f in comp["families"]});fig=OUT/"figures";fig.mkdir(exist_ok=True);plt.figure()
 for m in ("R0","R1","R2"):
  p,r,_=precision_recall_curve([x["danger"] for x in samples],[x[m] for x in samples]);plt.plot(r,p,label=m);write(fig/"source"/("pr_"+m+".json"),{"recall":r.tolist(),"precision":p.tolist()})
 plt.legend();plt.xlabel("Recall");plt.ylabel("Precision");plt.savefig(fig/"primary_pr_curves.png",dpi=200);plt.close();ledger=OUT/"formal_access_ledger.jsonl";ledger.write_text(ledger.read_text()+json.dumps({"command":"analysis_complete","prior_state":"authorized_once","new_state":"evaluated","results_sha256":sha256_file(OUT/"formal_results.json")},sort_keys=True)+"\n");return res
def main():
 a=argparse.ArgumentParser();a.add_argument("stage",choices=["prepare","authorize","generate","analyze","all"]);s=a.parse_args().stage
 if s in ("prepare","all"):prepare()
 if s in ("authorize","all"):authorize()
 if s in ("generate","all"):generate()
 if s in ("analyze","all"):print(json.dumps(analyze(),indent=2))
if __name__=="__main__":main()
