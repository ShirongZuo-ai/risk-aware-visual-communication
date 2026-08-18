"""Prepare literal, outcome-blind M9-B grids from independently perturbed physical cells."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLASSES=("collision","buffered_near","safe")
COUNTS={"pilot":5,"calibration":6,"formal":10}
BASES={f:("P02","P02","P03") for f in ("F1","F2","F3","F4","F5","F7")}
BASES["F6"]=("P01","P01","P04")
BASE_NAMESPACE={"pilot":940000,"calibration":950000,"formal":960000}

def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def source_cells():
 return {(x["family_id"],x["parameter_set_id"]):x for x in json.loads((ROOT/"docs/results/m9a_i1_scenario_grid.json").read_text())["cells"]}
def adjusted(family,role,base,j,split):
 import copy,math
 c=copy.deepcopy(base); o=c["obstacle"]
 # Distinct longitudinal perturbations preserve the physical class while avoiding duplicate cells.
 angle={"F1":0.,"F2":.45,"F3":.55,"F4":.55,"F5":0.,"F6":.35,"F7":0.}[family]
 delta=(j-(COUNTS[split]-1)/2)*.0003
 o["center_x_m"]+=delta*math.cos(angle);o["center_y_m"]+=delta*math.sin(angle)
 # Translate the validated M9-A near anchor along its closest-point normal.
 if role in ("collision","buffered_near"):
  lp=ROOT/f"data/logs/m9a/calibration/m9a-calibration-{family.lower()}-{BASES[family][1].lower()}-r00.jsonl"
  rows=[json.loads(x) for x in lp.read_text().splitlines()]; q=min(rows,key=lambda x:x["actual_physical_clearance_m"])["robot_state"]
  vx=o["center_x_m"]-q["x_m"];vy=o["center_y_m"]-q["y_m"];norm=math.hypot(vx,vy);ux=vx/norm;uy=vy/norm
  current=min(x["actual_physical_clearance_m"] for x in rows);desired=-.004 if role=="collision" else (.011 if family=="F6" else .006)
  o["center_x_m"]+=(desired-current)*ux;o["center_y_m"]+=(desired-current)*uy
 c.pop("placement_reference_clearance_m",None);c["structural_role"]=role
 return c
def grid(split):
 src=source_cells(); rows=[]; idx=0
 for fi in range(1,8):
  f=f"F{fi}"
  for ri,role in enumerate(CLASSES):
   base=src[(f,BASES[f][ri])]
   for j in range(COUNTS[split]):
    idx+=1;c=adjusted(f,role,base,j,split); pid=f"{role.upper()}-{j+1:02d}"
    c.update(parameter_set_id=pid,episode_id=f"m9b-{split}-{f.lower()}-{role}-{j+1:02d}",seed=BASE_NAMESPACE[split]+(fi-1)*1000+(ri*COUNTS[split]+j)*10,split=split,purpose=f"m9b_{split}")
    rows.append(c)
 if split=="pilot": n=10
 elif split=="calibration": n=18
 else:n=30
 b=src[("F8","P03")]
 for j in range(n):
  import copy
  c=copy.deepcopy(b);c["obstacle"]["center_x_m"]+=(j-(n-1)/2)*.002;c["obstacle"]["center_y_m"]+=(j%3-1)*.003
  c.update(parameter_set_id=f"SAFE-{j+1:02d}",structural_role="safe",episode_id=f"m9b-{split}-f8-safe-{j+1:02d}",seed=BASE_NAMESPACE[split]+7000+j*10,split=split,purpose=f"m9b_{split}");rows.append(c)
 return rows
def main():
 out=ROOT/"results/m9b_readiness_v3";out.mkdir(parents=True,exist_ok=True)
 for s in ("pilot","calibration","formal"):
  p=ROOT/f"docs/results/m9b_{s}_grid_v3.json";write(p,{"schema_version":"m9b-literal-grid-v3","study":"m9b-confirmatory-v1","split":s,"method_independent":True,"construction_inputs":["M9-A physical contact","M9-A actual clearance"],"predictor_outputs_used":False,"cells":grid(s)});p.with_suffix(p.suffix+".sha256").write_text(f"{sha(p)}  {p.name}\n")
 formal=grid("formal");head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
 manifest={"schema_version":"m9b-formal-manifest-v1","study":"m9b-confirmatory-v1","outcome_free":True,"planned_episode_count":240,"git_head_at_seal":head,"episodes":[{"formal_episode_id":c["episode_id"],"family":c["family_id"],"intended_physical_class":c["structural_role"],"seed":c["seed"],"parameter_set_id":c["parameter_set_id"],"config":c,"expected_log_path":f"data/logs/m9b/formal/{c['episode_id']}.jsonl"} for c in formal]}
 mp=out/"formal_manifest.json";write(mp,manifest);mp.with_suffix(".json.sha256").write_text(f"{sha(mp)}  {mp.name}\n")
 ledger=out/"formal_access_ledger.jsonl"
 if not ledger.exists():ledger.write_text(json.dumps({"study":"m9b-confirmatory-v1","prior_state":None,"new_state":"sealed","formal_manifest_sha256":sha(mp),"formal_outcomes_accessed":False},sort_keys=True)+"\n",encoding="utf-8",newline="\n")
 print({s:len(grid(s)) for s in ('pilot','calibration','formal')})
if __name__=="__main__":main()
