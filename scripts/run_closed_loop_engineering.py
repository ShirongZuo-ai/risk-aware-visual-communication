from __future__ import annotations
import json
from pathlib import Path
from evaluation.closed_loop_engineering import engineering_matrix
ROOT=Path(__file__).resolve().parents[1]
def main():
 studies={v:engineering_matrix(v) for v in ("offline_quota_v1","causal_token_v2")}; rows=sum(studies.values(),[]); summary={"schema_version":"track-b-engineering-v2","scientific_status":"engineering_only_not_C5_evidence","episodes":rows,"aggregate":{v:{m:{"episodes":sum(x["method"]==m for x in q),"collisions":sum(x["method"]==m and x["collision"] for x in q),"successes":sum(x["method"]==m and x["task_success"] for x in q),"total_bytes":sum(x["total_bytes"] for x in q if x["method"]==m)} for m in ("U0","A0","A1")} for v,q in studies.items()}}
 out=ROOT/"results/closed_loop_engineering/summary.json";out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(summary["aggregate"],indent=2))
if __name__=="__main__":main()
