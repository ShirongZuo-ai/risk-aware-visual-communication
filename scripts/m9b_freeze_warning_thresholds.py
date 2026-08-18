"""Derive M9-B warning thresholds from Calibration only; never reads Formal."""
from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
from evaluation.m9a_formal_analysis import load_episode,select_warning_threshold
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"results/m9b_readiness_v3"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def main():
 if (ROOT/"data/logs/m9b/formal").exists():raise RuntimeError("M9-B Formal must remain absent")
 grid=json.loads((ROOT/"docs/results/m9b_calibration_grid_v3.json").read_text())["cells"];episodes=[]
 with tempfile.TemporaryDirectory() as d:
  d=Path(d)
  for c in grid:
   p=d/(c["episode_id"]+".json");write(p,c)
   source=ROOT/"data/logs/m9b/calibration"/(c["episode_id"]+".jsonl");rows=[json.loads(x) for x in source.read_text(encoding="utf-8").splitlines() if x];offset=rows[0]["timestamp_s"]-.032
   for row in rows: row["timestamp_s"]-=offset
   normalized=d/(c["episode_id"]+".jsonl");normalized.write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in rows),encoding="utf-8")
   episodes.append(load_episode(normalized,p,2.0))
 decision={"schema_version":"m9b-warning-decision-v1","study":"m9b-confirmatory-v1","source":"M9-B Calibration only","algorithm_sha256":sha(OUT/"warning_threshold_algorithm.json"),"episode_count":len(episodes),"episode_ids":[e["episode_id"] for e in episodes],"methods":{m:select_warning_threshold(episodes,m) for m in ("R0","R1","R2")}}
 p=OUT/"calibration_warning_decision.json";write(p,decision);p.with_suffix(".json.sha256").write_text(f"{sha(p)}  {p.name}\n")
 contract=json.loads((OUT/"analysis_contract.json").read_text());contract["frozen_inputs"]["calibration_warning_decision_sha256"]=sha(p);contract["warning_calibration"]={"artifact":"results/m9b_readiness_v3/calibration_warning_decision.json","methods":decision["methods"]};write(OUT/"analysis_contract.json",contract);(OUT/"analysis_contract.json.sha256").write_text(f"{sha(OUT/'analysis_contract.json')}  analysis_contract.json\n")
 print(json.dumps({"warning":sha(p),"contract":sha(OUT/"analysis_contract.json"),"methods":decision["methods"]},indent=2))
if __name__=="__main__":main()
