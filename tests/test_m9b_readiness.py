import json
from pathlib import Path
from evaluation.m9b_readiness import classify,validate
def row(hit=False,c=.02,i=0):return {"timestep_index":i,"actual_physical_clearance_m":c,"contact_matching":{"validated_pair_contact":hit}}
def test_physical_classes():
 assert classify([row(True,.1)])[0]=="collision"
 assert classify([row(False,.006)])[0]=="buffered_near"
 assert classify([row(False,.02)])[0]=="safe"
 assert classify([row(False,.011)])[0]=="invalid_band"
def test_calibration_artifact_passes():
 root=Path(__file__).parents[1]
 assert validate(root/"docs/results/m9b_calibration_grid_v3.json",root/"data/logs/m9b/calibration")["passed"]
def test_authorized_formal_corpus_is_exactly_frozen_size():
 root=Path(__file__).parents[1]
 logs=list((root/"data/logs/m9b/formal").glob("*.jsonl"))
 ledger=[json.loads(x) for x in (root/"results/m9b_readiness_v3/formal_access_ledger.jsonl").read_text().splitlines()]
 assert len(logs)==240
 assert ledger[-1]["new_state"]=="evaluated"
