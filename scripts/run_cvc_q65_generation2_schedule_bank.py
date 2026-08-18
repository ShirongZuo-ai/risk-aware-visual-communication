"""Generate the frozen four-schedule bank for Q6.5 generation 2."""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/"config/cvc_q65_pilot.json";PLANNER=ROOT/"config/cvc_q1_planner_v2.json";WORLD=ROOT/"simulator/worlds/cvc_q65_runner.wbt";OUT=ROOT/"results/cvc_q65_development/generation2_schedule_bank";PROTOCOL=ROOT/"docs/cvc_q65_generation2_target_repair.md";WEBOTS=Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
STEPS=(80,109,144,217)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cells(cfg):return [{**c,"family":f["id"]} for f in cfg["families"] for c in f["cells"]]
def run_one(webots,job,identity,timeout):
 for name in ("jobs","traces","logs"):(OUT/name).mkdir(parents=True,exist_ok=True)
 jp=OUT/"jobs"/f"{identity}.json";tp=OUT/"traces"/f"{identity}.jsonl";sp=tp.with_suffix(".summary.json");canonical=json.dumps(job,indent=2,sort_keys=True)+"\n"
 if sp.exists():
  if jp.read_text(encoding="utf-8")!=canonical:raise RuntimeError("job drift")
  return json.loads(sp.read_text(encoding="utf-8"))
 jp.write_text(canonical,encoding="utf-8");env=os.environ.copy();env.update(CVC_CONFIG=str(jp),CVC_OUTPUT=str(tp));p=subprocess.run([str(webots),"--batch","--mode=fast","--stdout","--stderr",str(WORLD)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout);(OUT/"logs"/f"{identity}.log").write_text(p.stdout+p.stderr,encoding="utf-8")
 if p.returncode or not sp.exists():raise RuntimeError(f"{identity} failed: {(p.stdout+p.stderr)[-2000:]}")
 return json.loads(sp.read_text(encoding="utf-8"))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--webots",type=Path,default=WEBOTS);ap.add_argument("--timeout",type=float,default=180);a=ap.parse_args();cfg=json.loads(SOURCE.read_text(encoding="utf-8"));planner=json.loads(PLANNER.read_text(encoding="utf-8"));cs=cells(cfg);OUT.mkdir(parents=True,exist_ok=True)
 manifest={"study_id":"cvc-q65-generation2-adjacent-opportunity-v1","development_only":True,"formal":False,"cell_ids":[c["id"] for c in cs],"adaptive_steps":list(STEPS),"expected_episodes":len(cs)*len(STEPS),"protocol_sha256":sha(PROTOCOL),"source_sha256":sha(SOURCE),"world_sha256":sha(WORLD),"outcomes_read_before_manifest":False};mp=OUT/"manifest.json";canonical=json.dumps(manifest,indent=2,sort_keys=True)+"\n"; 
 if mp.exists() and mp.read_text(encoding="utf-8")!=canonical:raise RuntimeError("manifest drift")
 mp.write_text(canonical,encoding="utf-8");mp.with_suffix(".json.sha256").write_text(sha(mp)+"\n",encoding="utf-8")
 records=[]
 for ci,c in enumerate(cs):
  for si,step in enumerate(STEPS):
   identity=f"q65-g2-bank__{c['id']}__t{step}";job={**{k:c[k] for k in ("id","seed","start","goal","objects")},"scenario":c["id"],"semantic":c["family"],"role":"generation2_schedule_bank","duration_s":10.0,"policy":"U0","jpeg_quality":45,"packet_bytes":24000,"planner":planner["planner"],"visual_geometry":planner["visual_geometry"],"q3":{"risk_threshold":.14,"validity_steps":25,"fallback_step":217,"reserve_step":218,"u0_schedule":[0,step,218],"safety_decision_value_thresholds":{"safe_set_contraction_fraction":.5,"matched_margin_deterioration_m":.02,"numerical_tolerance":1e-9}},"q65":{"mode":"baseline_a0"}}
   s=run_one(a.webots,job,identity,a.timeout);records.append({"adaptive_step":step,**s});print(json.dumps({"done":ci*4+si+1,"total":len(cs)*4,"cell":c["id"],"step":step,"collision":s["collision"],"clearance":s["min_clearance_m"]}),flush=True)
 result={"manifest_sha256":sha(mp),"records":records,"all_exact_cost":all(r["wire_bytes"]==72000 and r["transmissions"]==3 and r["byte_reconciliation"] for r in records),"all_mirrors_match":all(r["mirror_all_steps_match"] for r in records)};rp=OUT/"results.json";rp.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8");rp.with_suffix(".json.sha256").write_text(sha(rp)+"\n",encoding="utf-8");print(json.dumps({"complete":True,"episodes":len(records),"sha256":sha(rp)},indent=2))
if __name__=="__main__":main()
