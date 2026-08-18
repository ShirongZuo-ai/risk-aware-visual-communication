from communication.closed_loop_policy import *
from evaluation.closed_loop_engineering import engineering_matrix,STEPS
def test_exact_matched_cost():
 risks=[i/STEPS for i in range(STEPS)]
 assert matched_schedule("U0",risks,24).total_bytes==matched_schedule("A0",risks,24).total_bytes==matched_schedule("A1",risks,24).total_bytes==STEPS*MEDIUM_BYTES
def test_closed_loop_signal_changes_trajectory_and_cost_is_equal():
 rows=engineering_matrix()
 for sid in {x["scenario"]["scenario_id"] for x in rows}:
  q=[x for x in rows if x["scenario"]["scenario_id"]==sid];assert len({x["total_bytes"] for x in q})==1
 assert any(a["first_detection_frame"]!=b["first_detection_frame"] for a,b in zip(rows[::3],rows[2::3]))
