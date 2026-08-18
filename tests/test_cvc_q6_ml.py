import hashlib
import json
from pathlib import Path
import pandas as pd

from scripts.train_cvc_q6_learned_precursor import HORIZON_STEPS, targets

ROOT = Path(__file__).resolve().parents[1]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_future_target_is_strictly_future_and_episode_bounded():
    frame = pd.DataFrame({"episode": ["a"] * 5 + ["b"] * 3,
                          "step": [0, 1, 2, 3, 4, 0, 1, 2],
                          "accepted_onset": [False, False, False, True, False, False, False, False]})
    y = targets(frame)
    assert y.tolist() == [1, 1, 1, 0, 0, 0, 0, 0]
    assert HORIZON_STEPS == 16

def test_learned_report_is_grouped_and_not_integrated():
    report = json.loads((ROOT / "results/cvc_q6_learned_precursor/training_report.json").read_text())
    assert report["target_uses_evaluator_truth"] is False
    assert report["group_split"].startswith("leave-one-physical-family-out")
    assert report["integration_authorized"] is False
    assert report["episodes"] == 70 and len(report["families"]) == 8
    assert report["model_sha256"] == sha(ROOT / "results/cvc_q6_learned_precursor/model.joblib")

def test_terminal_status_blocks_q7_formal_and_robot():
    status = json.loads((ROOT / "results/cvc_q6_final_status.json").read_text())
    assert status["classification"] == "Q6-C"
    assert status["method_selected"] is False
    assert status["q7_authorized"] is False
    assert status["formal_authorized"] is False
    assert status["real_robot_authorized"] is False
