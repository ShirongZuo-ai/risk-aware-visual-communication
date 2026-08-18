"""Run COV, U0, and A0 on the new Q6.5 development cells."""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"config/cvc_q65_scheduler_development.json"
CELLS=ROOT/"config/cvc_q65_pilot.json"
PLANNER=ROOT/"config/cvc_q1_planner_v2.json"
WORLD=ROOT/"simulator/worlds/cvc_q65_runner.wbt"
OUT=ROOT/"results/cvc_q65_scheduler_development/v1"
DEFAULT_WEBOTS=Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def flat_cells(cfg): return [{**cell,"family":family["id"]} for family in cfg["families"] for cell in family["cells"]]

def run_one(webots,job,identity,timeout):
    for name in ("jobs","traces","logs"):(OUT/name).mkdir(parents=True,exist_ok=True)
    jp=OUT/"jobs"/f"{identity}.json"; tp=OUT/"traces"/f"{identity}.jsonl"; sp=tp.with_suffix(".summary.json")
    canonical=json.dumps(job,indent=2,sort_keys=True)+"\n"
    if sp.exists():
        if not jp.exists() or jp.read_text(encoding="utf-8")!=canonical: raise RuntimeError(f"job drift: {identity}")
        return json.loads(sp.read_text(encoding="utf-8"))
    jp.write_text(canonical,encoding="utf-8")
    env=os.environ.copy();env.update(CVC_CONFIG=str(jp),CVC_OUTPUT=str(tp))
    process=subprocess.run([str(webots),"--batch","--mode=fast","--stdout","--stderr",str(WORLD)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
    (OUT/"logs"/f"{identity}.log").write_text(process.stdout+process.stderr,encoding="utf-8")
    if process.returncode or not sp.exists(): raise RuntimeError(f"{identity} failed: {(process.stdout+process.stderr)[-3000:]}")
    return json.loads(sp.read_text(encoding="utf-8"))

def job(cell,cfg,planner,policy):
    timing=cfg["scheduler"]
    mode="utility_scheduler" if policy=="COV" else "baseline_a0"
    runtime_policy="A1" if policy=="COV" else policy
    return {**{k:cell[k] for k in ("id","seed","start","goal","objects")},"scenario":cell["id"],
        "semantic":cell["family"],"role":"scheduler_development","duration_s":cfg["duration_s"],
        "policy":runtime_policy,"jpeg_quality":cfg["communication"]["jpeg_quality"],"packet_bytes":cfg["communication"]["packet_bytes"],
        "planner":planner["planner"],"visual_geometry":planner["visual_geometry"],
        "q3":{"risk_threshold":.14,"validity_steps":25,"fallback_step":timing["fallback_step"],"reserve_step":timing["reserve_step"],
              "u0_schedule":cfg["communication"]["u0_schedule"],"safety_decision_value_thresholds":{"safe_set_contraction_fraction":.5,"matched_margin_deterioration_m":.02,"numerical_tolerance":1e-9}},
        "q65":{"mode":mode,"model_path":cfg["candidate_model"],"candidate_start_step":timing["candidate_start_step"],
               "candidate_end_step":timing["candidate_end_step"],"clock_steps":timing["clock_steps"],"fallback_step":timing["fallback_step"],"reserve_step":timing["reserve_step"]}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--webots",type=Path,default=DEFAULT_WEBOTS);parser.add_argument("--timeout",type=float,default=180);parser.add_argument("--limit",type=int);args=parser.parse_args()
    cfg=json.loads(CONFIG.read_text(encoding="utf-8")); cells=flat_cells(json.loads(CELLS.read_text(encoding="utf-8"))); planner=json.loads(PLANNER.read_text(encoding="utf-8"))
    if args.limit: cells=cells[:args.limit]
    OUT.mkdir(parents=True,exist_ok=True)
    manifest={"study_id":cfg["study_id"],"development_only":True,"formal":False,"cells":[c["id"] for c in cells],"policies":cfg["policies"],
      "config_sha256":sha(CONFIG),"cells_sha256":sha(CELLS),"model_sha256":sha(ROOT/cfg["candidate_model"]),
      "controller_sha256":sha(ROOT/"simulator/controllers/cvc_q65_runner/cvc_q65_runner.py"),"scheduler_sha256":sha(ROOT/"communication/cvc_q65_scheduler.py"),"world_sha256":sha(WORLD),
      "outcomes_read_before_manifest":False}
    mp=OUT/"matrix_manifest.json";canonical=json.dumps(manifest,indent=2,sort_keys=True)+"\n"
    if mp.exists() and mp.read_text(encoding="utf-8")!=canonical: raise RuntimeError("scheduler manifest drift")
    mp.write_text(canonical,encoding="utf-8");mp.with_suffix(".json.sha256").write_text(sha(mp)+"\n",encoding="utf-8")
    records=[]
    for pindex,policy in enumerate(cfg["policies"]):
      for cindex,cell in enumerate(cells):
        identity=f"q65-scheduler-v1__{cell['id']}__{policy}"; summary=run_one(args.webots,job(cell,cfg,planner,policy),identity,args.timeout)
        records.append({"policy_id":policy,**summary});print(json.dumps({"done":pindex*len(cells)+cindex+1,"total":len(cells)*len(cfg["policies"]),"cell":cell["id"],"policy":policy,"sends":summary["send_steps"],"collision":summary["collision"],"clearance":summary["min_clearance_m"]}),flush=True)
    result={"study_id":cfg["study_id"],"manifest_sha256":sha(mp),"records":records,
      "all_exact_cost":all(r["wire_bytes"]==72000 and r["transmissions"]==3 and r["byte_reconciliation"] for r in records),
      "all_mirrors_match":all(r["mirror_all_steps_match"] for r in records)}
    rp=OUT/"matrix_results.json";rp.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8");rp.with_suffix(".json.sha256").write_text(sha(rp)+"\n",encoding="utf-8")
    print(json.dumps({"complete":True,"episodes":len(records),"all_exact_cost":result["all_exact_cost"],"all_mirrors_match":result["all_mirrors_match"],"sha256":sha(rp)},indent=2))
if __name__=="__main__":main()
