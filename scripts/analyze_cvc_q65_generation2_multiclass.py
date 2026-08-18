"""Final bounded safety-asymmetric multiclass analysis for Q6.5."""
from __future__ import annotations
from collections import defaultdict
import hashlib,json,sys
from pathlib import Path
from statistics import mean
import numpy as np
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,balanced_accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from evaluation.cvc_q65_opportunity import FEATURE_NAMES
BASE=ROOT/"results/cvc_q65_development/generation2_schedule_bank";ANALYSIS=BASE/"analysis.json";PROTOCOL=ROOT/"docs/cvc_q65_generation2_multiclass_gate.md";NEAR=.12
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x]
def metric(cell,step):
 t=rows(BASE/"traces"/f"q65-g2-bank__{cell}__t{step}.jsonl");s=json.loads((BASE/"traces"/f"q65-g2-bank__{cell}__t{step}.summary.json").read_text(encoding="utf-8"));return {"collision":bool(s["collision"]),"danger_steps":sum(r["evaluator"]["clearance_m"]<=NEAR for r in t),"min_clearance_m":float(s["min_clearance_m"]),"task_success":bool(s["task_success"]),"progress":float(s["goal_progress_m"])}
def aggregate(es):return {"cells":len(es),"collision_delta_total":sum(e["collision"] for e in es),"mean_danger_steps_delta":mean(e["danger"] for e in es),"danger_improved_tied_adverse":{"improved":sum(e["danger"]<0 for e in es),"tied":sum(e["danger"]==0 for e in es),"adverse":sum(e["danger"]>0 for e in es)},"mean_min_clearance_delta_m":mean(e["clearance"] for e in es),"task_success_delta_total":sum(e["task"] for e in es),"mean_progress_delta_m":mean(e["progress"] for e in es)}
def model(c):return Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",LogisticRegression(C=c,class_weight="balanced",max_iter=3000,random_state=20260818))])
def evaluate(X,y,families,est):
 fam=np.asarray(families);classes=("harmful","helpful","neutral");probs=np.full((len(y),3),np.nan)
 for f in sorted(set(families)):
  test=fam==f;fit=clone(est).fit(X[~test],y[~test]);lookup={name:i for i,name in enumerate(fit.named_steps["model"].classes_)}
  raw=fit.predict_proba(X[test]);probs[test]=np.column_stack([raw[:,lookup[c]] for c in classes])
 helpful=(y=="helpful").astype(int);send=(probs[:,1]>=.5)&(probs[:,0]<=.25);harm=y=="harmful"
 return {"classes":list(classes),"probabilities":probs.tolist(),"send":send.astype(int).tolist(),"helpful_auprc":float(average_precision_score(helpful,probs[:,1])),"three_class_balanced_accuracy":float(balanced_accuracy_score(y,np.asarray(classes)[np.argmax(probs,axis=1)])),"send_balanced_accuracy":float(balanced_accuracy_score(helpful,send)),"helpful_recall":float(send[helpful==1].mean()),"harmful_false_send_rate":float(send[harm].mean()),"neutral_send_rate":float(send[y=="neutral"].mean()),"pass":bool(average_precision_score(helpful,probs[:,1])>=.70 and average_precision_score(helpful,probs[:,1])>=helpful.mean()+.20 and balanced_accuracy_score(helpful,send)>=.65 and send[harm].mean()<=.35)}
def main():
 base=json.loads(ANALYSIS.read_text(encoding="utf-8"));corpus=base["corpus"];X=np.asarray([[r["features"][n] for n in FEATURE_NAMES] for r in corpus]);y=np.asarray([r["label"] for r in corpus]);families=[r["family"] for r in corpus]
 readiness={"frozen_before_scores":True,"protocol_sha256":sha(PROTOCOL),"source_analysis_sha256":sha(ANALYSIS),"models":["multinomial_logistic_c0.1","multinomial_logistic_c1"],"send_rule":{"p_helpful_min":.5,"p_harmful_max":.25},"predictor_gate":{"helpful_auprc_min":.70,"prevalence_margin_min":.20,"send_balanced_accuracy_min":.65,"harmful_false_send_rate_max":.35}};rp=BASE/"multiclass_readiness.json";canonical=json.dumps(readiness,indent=2,sort_keys=True)+"\n";
 if rp.exists() and rp.read_text(encoding="utf-8")!=canonical:raise RuntimeError("readiness drift")
 rp.write_text(canonical,encoding="utf-8");rp.with_suffix(".json.sha256").write_text(sha(rp)+"\n",encoding="utf-8")
 evaluations={f"multinomial_logistic_c{c:g}":evaluate(X,y,families,model(c)) for c in (.1,1.)};ranked=sorted(evaluations,key=lambda n:(evaluations[n]["pass"],evaluations[n]["helpful_auprc"],evaluations[n]["send_balanced_accuracy"]),reverse=True);selected=ranked[0] if evaluations[ranked[0]]["pass"] else None
 policy=[];byfam=defaultdict(list);pooled=None;family_results=None;checks=None;severe=None;scheduler_pass=False
 if selected:
  send=np.asarray(evaluations[selected]["send"],dtype=bool)
  for cell in sorted({r["cell_id"] for r in corpus}):
   indices=[i for i,r in enumerate(corpus) if r["cell_id"]==cell];chosen=next((corpus[i]["step"] for i in indices if send[i]),217);family=corpus[indices[0]]["family"];effects={}
   cm=metric(cell,chosen)
   for b in (109,217):
    bm=metric(cell,b);effects[str(b)]={"collision":int(cm["collision"])-int(bm["collision"]),"danger":cm["danger_steps"]-bm["danger_steps"],"clearance":cm["min_clearance_m"]-bm["min_clearance_m"],"task":int(cm["task_success"])-int(bm["task_success"]),"progress":cm["progress"]-bm["progress"]}
   row={"cell_id":cell,"family":family,"selected_step":chosen,"effects":effects};policy.append(row);byfam[family].append(row)
  pooled={b:aggregate([r["effects"][b] for r in policy]) for b in ("109","217")};family_results={f:{b:aggregate([r["effects"][b] for r in rs]) for b in ("109","217")} for f,rs in sorted(byfam.items())};severe=[f for f,v in family_results.items() if v["109"]["mean_danger_steps_delta"]>0 and v["109"]["mean_min_clearance_delta_m"]<0];u=pooled["109"];checks={"collision":u["collision_delta_total"]<=0,"danger":u["mean_danger_steps_delta"]<0,"clearance":u["mean_min_clearance_delta_m"]>=.005,"families":not severe,"task":u["task_success_delta_total"]>=-1};scheduler_pass=all(checks.values())
 result={"evaluations":evaluations,"selected":selected,"cross_family_policy":{"pooled":pooled,"families":family_results,"severe_adverse_families":severe,"checks":checks,"pass":scheduler_pass,"rows":policy},"freeze_eligible":bool(selected and scheduler_pass)};out=BASE/"multiclass_analysis.json";out.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8");out.with_suffix(".json.sha256").write_text(sha(out)+"\n",encoding="utf-8")
 if result["freeze_eligible"]:
  fit=model(1. if selected.endswith("c1") else .1).fit(X,y);m=fit.named_steps["model"];fm={"method_id":"cvc-q65-g2-multiclass-cov-v1","frozen":True,"analysis_sha256":sha(out),"classes":m.classes_.tolist(),"feature_names":list(FEATURE_NAMES),"imputer_median":fit.named_steps["impute"].statistics_.tolist(),"standardizer_mean":fit.named_steps["scale"].mean_.tolist(),"standardizer_scale":fit.named_steps["scale"].scale_.tolist(),"coefficients":m.coef_.tolist(),"intercepts":m.intercept_.tolist(),"send_rule":{"p_helpful_min":.5,"p_harmful_max":.25},"candidate_steps":[80,109,144],"fallback_step":217,"reserve_step":218,"episode_wire_bytes":72000,"no_q7_tuning":True};fp=BASE/"frozen_method_manifest.json";fp.write_text(json.dumps(fm,indent=2,sort_keys=True)+"\n",encoding="utf-8");fp.with_suffix(".json.sha256").write_text(sha(fp)+"\n",encoding="utf-8")
 print(json.dumps({"models":evaluations,"selected":selected,"policy":result["cross_family_policy"],"freeze_eligible":result["freeze_eligible"],"frozen_sha256":sha(BASE/"frozen_method_manifest.json") if result["freeze_eligible"] else None},indent=2))
if __name__=="__main__":main()
