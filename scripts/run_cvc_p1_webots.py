"""Run the CVC-P1 development Webots suite; never creates confirmatory data."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/"simulator"/"worlds"/"cvc_p1_runner.wbt"
WEBOTS=Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
SCENARIOS={
 "fixture_left":{"start":[0,0,0],"duration_s":.5,"objects":[{"id":"TARGET","center":[.35,.12],"physical":False}]},
 "fixture_center":{"start":[0,0,0],"duration_s":.5,"objects":[{"id":"TARGET","center":[.35,0],"physical":False}]},
 "fixture_right":{"start":[0,0,0],"duration_s":.5,"objects":[{"id":"TARGET","center":[.35,-.12],"physical":False}]},
 "fixture_absent":{"start":[0,0,0],"duration_s":.5,"objects":[{"id":"DISTRACTOR","center":[.35,0],"color":[0,0,1],"physical":False}]},
 "straight_obstacle":{"start":[-.65,0,0],"objects":[{"id":"TARGET","center":[.25,0]}]},
 "turning_approach":{"start":[-.6,-.2,.15],"objects":[{"id":"TARGET","center":[.25,.02]}]},
 "turn_toward_danger":{"start":[-.55,-.15,.35],"objects":[{"id":"TARGET","center":[.2,.08]}]},
 "turn_away_danger":{"start":[-.55,.1,-.25],"objects":[{"id":"TARGET","center":[.15,.28]}]},
 "safe_pass":{"start":[-.65,0,0],"objects":[{"id":"TARGET","center":[.15,.20]}]},
 "near_turn_appearance":{"start":[-.55,-.2,.3],"objects":[{"id":"TARGET","center":[.05,.08]}]},
 "command_transition":{"start":[-.65,.15,-.15],"objects":[{"id":"TARGET","center":[.2,0]}]},
 "distractor":{"start":[-.65,0,0],"objects":[{"id":"TARGET","center":[.22,.04]},{"id":"DISTRACTOR","center":[-.05,-.3],"color":[0,0,1],"physical":False}]},
}

def main():
 p=argparse.ArgumentParser();p.add_argument("--mode",choices=["fixtures","sanity","policies","all"],default="all");p.add_argument("--timeout",type=float,default=50);a=p.parse_args()
 root=ROOT/"results"/"cvc_p1_webots";jobs=root/"jobs";logs=root/"logs";traces=root/"traces"
 for d in (jobs,logs,traces):d.mkdir(parents=True,exist_ok=True)
 runs=[]
 if a.mode in ("fixtures","all"):
  runs += [(s,"U0","HIGH") for s in ("fixture_left","fixture_center","fixture_right","fixture_absent")]
 if a.mode in ("sanity","all"):
  runs += [("straight_obstacle","U0",c) for c in ("HIGH","MEDIUM","LOW")]
 if a.mode in ("policies","all"):
  runs += [(s,p,"POLICY") for s in SCENARIOS if not s.startswith("fixture_") for p in ("U0","A0","A1")]
 summaries=[]
 for scenario,policy,condition in runs:
  ident=f"{scenario}__{policy}__{condition}"; cfg={"scenario":scenario,"policy":policy,"condition":condition,"packet_bytes":36000,**SCENARIOS[scenario]}; cfg.setdefault("duration_s",10)
  job=jobs/f"{ident}.json";out=traces/f"{ident}.jsonl";job.write_text(json.dumps(cfg,indent=2)+"\n",encoding="utf-8")
  env=dict(os.environ);env.update(CVC_CONFIG=str(job),CVC_OUTPUT=str(out))
  proc=subprocess.run([str(WEBOTS),"--batch","--mode=fast",str(WORLD)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=a.timeout)
  (logs/f"{ident}.log").write_text(proc.stdout+proc.stderr,encoding="utf-8")
  summary=out.with_suffix(".summary.json")
  if not summary.exists(): raise RuntimeError(f"{ident} failed: {(proc.stdout+proc.stderr)[-3000:]}")
  summaries.append(json.loads(summary.read_text()))
 aggregate={"development_only":True,"run_count":len(summaries),"runs":summaries}
 summary_path=root/f"{a.mode}_summary.json"
 summary_path.write_text(json.dumps(aggregate,indent=2,sort_keys=True)+"\n",encoding="utf-8")
 print(json.dumps({"run_count":len(summaries),"summary":str(summary_path)},indent=2))
if __name__=="__main__":main()
