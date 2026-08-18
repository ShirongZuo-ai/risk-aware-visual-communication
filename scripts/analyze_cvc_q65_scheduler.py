"""Analyze the Q6.5 matched-byte scheduler development matrix."""
from __future__ import annotations

from collections import defaultdict
import hashlib,json
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"results/cvc_q65_scheduler_development/v1"
CONFIG=ROOT/"config/cvc_q65_scheduler_development.json"
MATRIX=BASE/"matrix_results.json"
NEAR=.12
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]
def metrics(trace,summary):
 return {"collision":bool(summary["collision"]),"danger_steps":sum(r["evaluator"]["clearance_m"]<=NEAR for r in trace),
 "min_clearance_m":float(summary["min_clearance_m"]),"goal_progress_m":float(summary["goal_progress_m"]),"task_success":bool(summary["task_success"]),
 "send_steps":summary["send_steps"],"deadline_miss_steps":sum(r["runtime_profile_ms"]["communication_decision_total"]>32 for r in trace),
 "scheduler_p95_ms":float(summary["runtime_profile"]["scheduler_decision"]["p95_ms"])}
def trace_effect(a,b):
 return {"receiver_image_different_steps":sum(x["receiver"]["image_sha256"]!=y["receiver"]["image_sha256"] for x,y in zip(a,b)),
 "planner_action_different_steps":sum(x["runtime"]["planner"]["selected_action_id"]!=y["runtime"]["planner"]["selected_action_id"] for x,y in zip(a,b)),
 "wheel_command_different_steps":sum(abs(x["runtime"]["wheel_left_rad_s"]-y["runtime"]["wheel_left_rad_s"])>1e-9 or abs(x["runtime"]["wheel_right_rad_s"]-y["runtime"]["wheel_right_rad_s"])>1e-9 for x,y in zip(a,b))}
def aggregate(items):
 return {"cells":len(items),"collision_delta_total":sum(i["collision_delta"] for i in items),
 "mean_danger_steps_delta":mean(i["danger_steps_delta"] for i in items),
 "danger_improved_tied_adverse":{"improved":sum(i["danger_steps_delta"]<0 for i in items),"tied":sum(i["danger_steps_delta"]==0 for i in items),"adverse":sum(i["danger_steps_delta"]>0 for i in items)},
 "mean_min_clearance_delta_m":mean(i["min_clearance_delta_m"] for i in items),
 "mean_progress_delta_m":mean(i["goal_progress_delta_m"] for i in items),"task_success_delta_total":sum(i["task_success_delta"] for i in items),
 "send_timing_different_cells":sum(i["send_steps_different"] for i in items),"receiver_changed_cells":sum(i["receiver_image_different_steps"]>0 for i in items),
 "planner_changed_cells":sum(i["planner_action_different_steps"]>0 for i in items),"wheel_changed_cells":sum(i["wheel_command_different_steps"]>0 for i in items)}
def main():
 cfg=json.loads(CONFIG.read_text(encoding="utf-8")); matrix=json.loads(MATRIX.read_text(encoding="utf-8")); summaries={(r["scenario"],r["policy_id"]):r for r in matrix["records"]}
 cells=sorted({c for c,_ in summaries}); pairs=[];byfamily=defaultdict(list)
 for cell in cells:
  traces={p:rows(BASE/"traces"/f"q65-scheduler-v1__{cell}__{p}.jsonl") for p in cfg["policies"]}
  m={p:metrics(traces[p],summaries[cell,p]) for p in cfg["policies"]}
  comparisons={}
  for baseline in ("U0","A0"):
   e=trace_effect(traces["COV"],traces[baseline]);e.update({"collision_delta":int(m["COV"]["collision"])-int(m[baseline]["collision"]),
    "danger_steps_delta":m["COV"]["danger_steps"]-m[baseline]["danger_steps"],"min_clearance_delta_m":m["COV"]["min_clearance_m"]-m[baseline]["min_clearance_m"],
    "goal_progress_delta_m":m["COV"]["goal_progress_m"]-m[baseline]["goal_progress_m"],"task_success_delta":int(m["COV"]["task_success"])-int(m[baseline]["task_success"]),
    "send_steps_different":m["COV"]["send_steps"]!=m[baseline]["send_steps"]});comparisons[baseline]=e
  family=summaries[cell,"COV"]["semantic"];row={"cell_id":cell,"family":family,"policy_metrics":m,"COV_minus":comparisons};pairs.append(row);byfamily[family].append(row)
 pooled={b:aggregate([r["COV_minus"][b] for r in pairs]) for b in ("U0","A0")}
 families={f:{b:aggregate([r["COV_minus"][b] for r in rs]) for b in ("U0","A0")} for f,rs in sorted(byfamily.items())}
 severe=[f for f,v in families.items() if v["U0"]["mean_danger_steps_delta"]>0 and v["U0"]["mean_min_clearance_delta_m"]<0]
 gate=cfg["development_success_gate_frozen_before_outcomes"];u=pooled["U0"]
 checks={"collision":u["collision_delta_total"]<=gate["collision_delta_total_max"],"danger":u["mean_danger_steps_delta"]<gate["mean_danger_steps_delta_strict_max"],
 "clearance":u["mean_min_clearance_delta_m"]>=gate["mean_min_clearance_delta_m_min"],"families":len(severe)<=gate["severe_adverse_family_count_max"],
 "task":u["task_success_delta_total"]>=gate["task_success_delta_min"],"bytes":bool(matrix["all_exact_cost"]),"mirror":bool(matrix["all_mirrors_match"])}
 result={"study_id":cfg["study_id"],"development_only":True,"formal":False,"matrix_sha256":sha(MATRIX),"near_boundary_m":NEAR,"pooled":pooled,"families":families,
 "severe_adverse_families_vs_U0":severe,"gate_checks":checks,"development_gate_pass":all(checks.values()),"classification":"METHOD_CANDIDATE_FREEZE_ELIGIBLE" if all(checks.values()) else "METHOD_CANDIDATE_REJECTED",
 "COV_runtime":{"deadline_miss_steps":sum(r["policy_metrics"]["COV"]["deadline_miss_steps"] for r in pairs),"maximum_scheduler_p95_ms":max(r["policy_metrics"]["COV"]["scheduler_p95_ms"] for r in pairs)},"pairs":pairs}
 out=BASE/"analysis.json";out.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8");out.with_suffix(".json.sha256").write_text(sha(out)+"\n",encoding="utf-8")
 print(json.dumps({k:result[k] for k in ("pooled","severe_adverse_families_vs_U0","gate_checks","classification","COV_runtime")},indent=2))
if __name__=="__main__":main()
