"""Physical-only M9-B support validation; contains no predictor scoring."""
from __future__ import annotations
import json
from collections import Counter,defaultdict
from pathlib import Path

def classify(rows):
 hit=any(r["contact_matching"]["validated_pair_contact"] for r in rows)
 clearance=min(r["actual_physical_clearance_m"] for r in rows)
 if hit:return "collision",clearance
 if .003<=clearance<=.010:return "buffered_near",clearance
 if clearance>=.020:return "safe",clearance
 return "invalid_band",clearance
def validate(grid_path:Path,log_dir:Path):
 grid=json.loads(grid_path.read_text());total=Counter();families=defaultdict(Counter);episodes=[]
 for cell in grid["cells"]:
  p=log_dir/(cell["episode_id"]+".jsonl");rows=[json.loads(x) for x in p.read_text().splitlines()]
  if len(rows)!=188 or [x["timestep_index"] for x in rows]!=list(range(188)):raise ValueError(cell["episode_id"])
  role,clearance=classify(rows);total[role]+=1;families[cell["family_id"]][role]+=1;episodes.append({"episode_id":cell["episode_id"],"family":cell["family_id"],"intended":cell["structural_role"],"observed":role,"minimum_clearance_m":clearance})
 expected=5 if grid["split"]=="pilot" else 6
 passed=all(families[f][r]>=expected for f in [f"F{i}" for i in range(1,8)] for r in ("collision","buffered_near","safe")) and families["F8"]["safe"]>=(10 if grid["split"]=="pilot" else 15)
 return {"split":grid["split"],"passed":passed,"total":dict(total),"families":{k:dict(v) for k,v in families.items()},"episodes":episodes}
