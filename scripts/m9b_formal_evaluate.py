"""Locked M9-B Formal analysis over the frozen manifest; no replacement logic."""
from __future__ import annotations
import hashlib,json,math,sys
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evaluation.m9a_formal_analysis import HORIZONS, correlations, family_macro_auprc, load_episode, paired_bootstrap, warning_runs

READY=ROOT/"results/m9b_readiness_v3";OUT=ROOT/"results/m9b_formal";LOGS=ROOT/"data/logs/m9b/formal"
def write(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ap(y,s):
 y=np.asarray(y,dtype=np.int8);s=np.asarray(s,float);order=np.argsort(-s,kind="mergesort");y=y[order];s=s[order];ends=np.r_[np.flatnonzero(np.diff(s)),len(s)-1];tp=np.cumsum(y)[ends];fp=(ends+1)-tp
 if tp[-1]==0:return math.nan
 recall=tp/tp[-1];precision=tp/(tp+fp);return float(np.sum(np.diff(np.r_[0.,recall])*precision))
def weighted_ap_batches(group,method,counts,batch=200):
 ys=[];scores=[];episode=[]
 for i,e in enumerate(group):
  ys.extend(x["danger"] for x in e["samples"]);scores.extend(x[method] for x in e["samples"]);episode.extend([i]*len(e["samples"]))
 y=np.asarray(ys,dtype=float);s=np.asarray(scores,float);episode=np.asarray(episode);order=np.argsort(-s,kind="mergesort");y=y[order];s=s[order];episode=episode[order];ends=np.r_[np.flatnonzero(np.diff(s)),len(s)-1];out=[]
 for lo in range(0,len(counts),batch):
  w=counts[lo:lo+batch,episode];tp=np.cumsum(w*y,axis=1)[:,ends];fp=np.cumsum(w*(1-y),axis=1)[:,ends];recall=tp/tp[:,-1,None];precision=np.divide(tp,tp+fp,out=np.zeros_like(tp),where=(tp+fp)>0);out.extend(np.sum(np.diff(np.c_[np.zeros(len(tp)),recall],axis=1)*precision,axis=1))
 return np.asarray(out)
def fast_bootstrap(episodes,a,b):
 groups=[[e for e in episodes if e["family"]==f] for f in [f"F{i}" for i in range(1,8)]];n=len(groups[0]);rng=np.random.default_rng(20261001);draw=rng.integers(0,n,size=(10000,7,n));counts=np.zeros((10000,7,n),dtype=np.int16)
 for i in range(n):counts[:,:,i]=(draw==i).sum(axis=2)
 av=[];bv=[]
 for fi,g in enumerate(groups):av.append(weighted_ap_batches(g,a,counts[:,fi,:]));bv.append(weighted_ap_batches(g,b,counts[:,fi,:]))
 v=np.mean(av,axis=0)-np.mean(bv,axis=0);return {"lower":float(np.percentile(v,2.5)),"upper":float(np.percentile(v,97.5)),"valid_replicates":len(v)}
def prepare_inputs(records):
 d=OUT/"analysis_inputs";d.mkdir(parents=True,exist_ok=True);pairs=[]
 for e in records:
  eid=e["formal_episode_id"];cfg=d/(eid+".json");log=d/(eid+".jsonl");write(cfg,e["config"])
  raw=[json.loads(x) for x in (LOGS/(eid+".jsonl")).read_text().splitlines()]
  if len(raw)!=188 or [x["timestep_index"] for x in raw]!=list(range(188)):raise RuntimeError(f"invalid dense log {eid}")
  for i,r in enumerate(raw):r["timestamp_s"]=i*r["basic_timestep_s"]
  log.write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in raw),encoding="utf-8",newline="\n");pairs.append((e,log,cfg,raw))
 return pairs
def main():
 manifest=json.loads((READY/"formal_manifest.json").read_text());records=manifest["episodes"]
 if len(records)!=240 or len({e["formal_episode_id"] for e in records})!=240:raise RuntimeError("manifest identity failure")
 pairs=prepare_inputs(records);eps=[load_episode(log,cfg,2.0) for _,log,cfg,_ in pairs]
 fam={};tot={"collision":0,"buffered_near":0,"safe":0}
 for f in [f"F{i}" for i in range(1,9)]:
  q=[e for e in eps if e["family"]==f];z={"collision":sum(e["episode_collision"] for e in q),"buffered_near":sum(not e["episode_collision"] and .003<=e["episode_min_clearance_m"]<=.010 for e in q),"safe":sum(not e["episode_collision"] and e["episode_min_clearance_m"]>=.020 for e in q)};fam[f]=z
  for k in tot:tot[k]+=z[k]
 support=len(eps)>=216 and tot["collision"]>=56 and tot["buffered_near"]>=56 and tot["safe"]>=80 and all(min(fam[f].values())>=8 for f in [f"F{i}" for i in range(1,8)]) and fam["F8"]["safe"]>=24
 primary={m:family_macro_auprc([e for e in eps if e["family"]!="F8"],m) for m in ("R0","R1","R2")};contrasts={}
 for name,a,b in (("primary_R1_minus_R0","R1","R0"),("secondary_R2_minus_R1","R2","R1")):
  d=primary[a]-primary[b];ci=fast_bootstrap([e for e in eps if e["family"]!="F8"],a,b);decision=("PASS" if support and d>=.05 and ci["lower"]>0 else ("insufficient_support" if not support else "FAIL")) if name.startswith("primary") else "descriptive_only";contrasts[name]={"delta":d,"ci95":ci,"decision":decision}
 samples=[x for e in eps for x in e["samples"]];warning=json.loads((READY/"calibration_warning_decision.json").read_text())["methods"]
 secondary={m:{**correlations(samples,m),"warning_events":sum(len(warning_runs(e["samples"],m,warning[m]["threshold"])) for e in eps)} for m in ("R0","R1","R2")}
 result={"schema_version":"m9b-formal-results-v1","study":"m9b-confirmatory-v1","authorization_id":"M9B-FORMAL20260814ZS01","manifest_sha256":sha(READY/"formal_manifest.json"),"valid_episodes":len(eps),"excluded_episodes":[],"composition":tot,"family_support":fam,"support_pass":support,"primary_2s_auprc":primary,"contrasts":contrasts,"clearance_and_warning":secondary}
 write(OUT/"formal_results.json",result);(OUT/"formal_results.json.sha256").write_text(f"{sha(OUT/'formal_results.json')}  formal_results.json\n");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
