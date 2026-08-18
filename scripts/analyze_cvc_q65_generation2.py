"""Analyze adjacent-opportunity labels and cross-family scheduler replay."""
from __future__ import annotations
from collections import Counter,defaultdict
import hashlib,json,sys
from pathlib import Path
from statistics import mean
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from communication.cvc_q65_intervention import opportunity_label
from evaluation.cvc_q65_opportunity import FEATURE_NAMES,extract_causal_features,grouped_leave_family_out,models
BASE=ROOT/"results/cvc_q65_development/generation2_schedule_bank";DISC=ROOT/"results/cvc_q65_development/pilot_v1";SOURCE=ROOT/"config/cvc_q65_pilot.json";PROTOCOL=ROOT/"docs/cvc_q65_generation2_target_repair.md";RESULTS=BASE/"results.json";STEPS=(80,109,144,217);NEAR=.12
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x]
def metric(trace,summary):return {"collision":bool(summary["collision"]),"danger_steps":sum(r["evaluator"]["clearance_m"]<=NEAR for r in trace),"min_clearance_m":float(summary["min_clearance_m"]),"goal_progress_m":float(summary["goal_progress_m"]),"task_success":bool(summary["task_success"]),"send_steps":summary["send_steps"]}
def prefix(a,b,t):
 keys=("step","time_s","sender","safety_value","counterfactual","receiver","runtime","evaluator")
 return all({k:a[i][k] for k in keys}=={k:b[i][k] for k in keys} for i in range(t))
def agg(es):return {"cells":len(es),"collision_delta_total":sum(e["collision_delta"] for e in es),"mean_danger_steps_delta":mean(e["danger_steps_delta"] for e in es),"danger_improved_tied_adverse":{"improved":sum(e["danger_steps_delta"]<0 for e in es),"tied":sum(e["danger_steps_delta"]==0 for e in es),"adverse":sum(e["danger_steps_delta"]>0 for e in es)},"mean_min_clearance_delta_m":mean(e["min_clearance_delta_m"] for e in es),"task_success_delta_total":sum(e["task_success_delta"] for e in es),"mean_progress_delta_m":mean(e["progress_delta_m"] for e in es)}
def main():
 source=json.loads(SOURCE.read_text(encoding="utf-8"));bank=json.loads(RESULTS.read_text(encoding="utf-8"));summaries={(r["scenario"],r["adaptive_step"]):r for r in bank["records"]};family={c["id"]:f["id"] for f in source["families"] for c in f["cells"]};corpus=[]
 for cell in sorted(family):
  discovery=rows(DISC/"traces"/f"q65-discovery__{cell}.jsonl")
  traces={t:rows(BASE/"traces"/f"q65-g2-bank__{cell}__t{t}.jsonl") for t in STEPS}
  for early,later in zip(STEPS,STEPS[1:]):
   if not prefix(traces[early],traces[later],early):raise RuntimeError(f"prefix mismatch {cell} {early}/{later}")
   sm,hm=metric(traces[early],summaries[cell,early]),metric(traces[later],summaries[cell,later]);label=opportunity_label(sm,hm)
   corpus.append({"opportunity_id":f"{cell}__t{early}","cell_id":cell,"family":family[cell],"step":early,"next_step":later,"label":label["label"],"utility":label,"features":extract_causal_features(discovery,early,217)})
 counts=Counter(r["label"] for r in corpus);fl=defaultdict(Counter)
 for r in corpus:fl[r["family"]][r["label"]]+=1
 support={"counts":dict(counts),"families":{f:dict(c) for f,c in sorted(fl.items())},"helpful_families":sum(c["helpful"]>0 for c in fl.values()),"harmful_families":sum(c["harmful"]>0 for c in fl.values())}
 support["pass"]=counts["helpful"]>=6 and counts["harmful"]>=6 and counts["neutral"]>=6 and support["helpful_families"]>=3 and support["harmful_families"]>=3
 if not support["pass"]:raise RuntimeError("generation2 support gate failed")
 readiness={"study_id":"cvc-q65-generation2-adjacent-opportunity-v1","frozen_before_model_scores":True,"results_sha256":sha(RESULTS),"protocol_sha256":sha(PROTOCOL),"feature_names":list(FEATURE_NAMES),"grouping":"leave_one_family_out","predictor_gate":{"pooled_auprc_min":.70,"prevalence_margin_min":.20,"balanced_accuracy_min":.65,"harmful_false_send_rate_max":.35},"scheduler_gate":{"collision_delta_total_max":0,"mean_danger_steps_delta_strict_max":0,"mean_min_clearance_delta_m_min":.005,"severe_adverse_family_count_max":0,"task_success_delta_min":-1},"support":support};rp=BASE/"readiness.json";canonical=json.dumps(readiness,indent=2,sort_keys=True)+"\n";
 if rp.exists() and rp.read_text(encoding="utf-8")!=canonical:raise RuntimeError("readiness drift")
 rp.write_text(canonical,encoding="utf-8");rp.with_suffix(".json.sha256").write_text(sha(rp)+"\n",encoding="utf-8")
 X=np.asarray([[r["features"][n] for n in FEATURE_NAMES] for r in corpus]);y=np.asarray([r["label"]=="helpful" for r in corpus],dtype=int);families=[r["family"] for r in corpus];harm=np.asarray([r["label"]=="harmful" for r in corpus]);evaluations={}
 for name,est in models().items():
  e=grouped_leave_family_out(X,y,families,est);pred=np.asarray(e["predictions"]);e["harmful_false_send_rate"]=float(pred[harm].mean());e["passes_gate"]=e["pooled_auprc"]>=.70 and e["pooled_auprc"]>=y.mean()+.20 and e["balanced_accuracy"]>=.65 and e["harmful_false_send_rate"]<=.35;evaluations[name]=e
 ranked=sorted(evaluations,key=lambda n:(evaluations[n]["passes_gate"],evaluations[n]["pooled_auprc"],evaluations[n]["balanced_accuracy"]),reverse=True);selected=ranked[0] if evaluations[ranked[0]]["passes_gate"] else None
 policy_rows=[];byfam=defaultdict(list);pooled=None;family_results=None;severe=None;checks=None;scheduler_pass=False
 if selected:
  probs=evaluations[selected]["probabilities"]
  for cell in sorted(family):
   indices=[i for i,r in enumerate(corpus) if r["cell_id"]==cell];chosen=217
   for i in indices:
    if probs[i]>=.5:chosen=corpus[i]["step"];break
   chosen_m=metric(rows(BASE/"traces"/f"q65-g2-bank__{cell}__t{chosen}.jsonl"),summaries[cell,chosen]);comparisons={}
   for baseline in (109,217):
    bm=metric(rows(BASE/"traces"/f"q65-g2-bank__{cell}__t{baseline}.jsonl"),summaries[cell,baseline]);comparisons[str(baseline)]={"collision_delta":int(chosen_m["collision"])-int(bm["collision"]),"danger_steps_delta":chosen_m["danger_steps"]-bm["danger_steps"],"min_clearance_delta_m":chosen_m["min_clearance_m"]-bm["min_clearance_m"],"task_success_delta":int(chosen_m["task_success"])-int(bm["task_success"]),"progress_delta_m":chosen_m["goal_progress_m"]-bm["goal_progress_m"]}
   row={"cell_id":cell,"family":family[cell],"selected_step":chosen,"comparisons":comparisons};policy_rows.append(row);byfam[family[cell]].append(row)
  pooled={b:agg([r["comparisons"][b] for r in policy_rows]) for b in ("109","217")};family_results={f:{b:agg([r["comparisons"][b] for r in rs]) for b in ("109","217")} for f,rs in sorted(byfam.items())};severe=[f for f,v in family_results.items() if v["109"]["mean_danger_steps_delta"]>0 and v["109"]["mean_min_clearance_delta_m"]<0];u=pooled["109"];sg=readiness["scheduler_gate"];checks={"collision":u["collision_delta_total"]<=0,"danger":u["mean_danger_steps_delta"]<0,"clearance":u["mean_min_clearance_delta_m"]>=.005,"families":len(severe)==0,"task":u["task_success_delta_total"]>=-1,"bytes":bank["all_exact_cost"],"mirror":bank["all_mirrors_match"]};scheduler_pass=all(checks.values())
 result={"support":support,"helpful_prevalence":float(y.mean()),"evaluations":evaluations,"selected_predictor":selected,"cross_family_policy":{"pooled":pooled if selected else None,"families":family_results if selected else None,"severe_adverse_families_vs_U0":severe if selected else None,"gate_checks":checks if selected else None,"pass":scheduler_pass if selected else False,"rows":policy_rows},"freeze_eligible":bool(selected and scheduler_pass),"corpus":corpus};out=BASE/"analysis.json";out.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8");out.with_suffix(".json.sha256").write_text(sha(out)+"\n",encoding="utf-8")
 if result["freeze_eligible"]:
  fit=models()[selected].fit(X,y);manifest={"method_id":"cvc-q65-g2-adjacent-cov-v1","frozen":True,"formal":False,"analysis_sha256":sha(out),"feature_names":list(FEATURE_NAMES),"imputer_median":fit.named_steps["impute"].statistics_.tolist(),"standardizer_mean":fit.named_steps["scale"].mean_.tolist(),"standardizer_scale":fit.named_steps["scale"].scale_.tolist(),"coefficients":fit.named_steps["model"].coef_[0].tolist(),"intercept":float(fit.named_steps["model"].intercept_[0]),"decision_threshold":.5,"candidate_steps":[80,109,144],"fallback_step":217,"reserve_step":218,"packet_bytes":24000,"episode_wire_bytes":72000,"planner_frozen":True,"no_q7_tuning":True};fm=BASE/"frozen_method_manifest.json";fm.write_text(json.dumps(manifest,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8");fm.with_suffix(".json.sha256").write_text(sha(fm)+"\n",encoding="utf-8")
 print(json.dumps({"support":support,"models":{n:{"auprc":e["pooled_auprc"],"balanced_accuracy":e["balanced_accuracy"],"harmful_false_send_rate":e["harmful_false_send_rate"],"pass":e["passes_gate"]} for n,e in evaluations.items()},"selected":selected,"policy":result["cross_family_policy"],"freeze_eligible":result["freeze_eligible"],"frozen_manifest_sha256":sha(BASE/"frozen_method_manifest.json") if result["freeze_eligible"] else None},indent=2))
if __name__=="__main__":main()
