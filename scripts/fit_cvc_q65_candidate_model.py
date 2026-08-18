"""Fit and serialize the already-selected Q6.5 logistic development model."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.cvc_q65_opportunity import FEATURE_NAMES, models

BASE = ROOT / "results/cvc_q65_development/pilot_v1"
ANALYSIS = BASE / "opportunity_analysis.json"
CORPUS = BASE / "causal_feature_corpus.json"
OUT = BASE / "candidate_opportunity_model.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))["rows"]
    if analysis["selected_predictor"] != "logistic_l2_c1" or not analysis["predictor_gate_pass"]:
        raise RuntimeError("the frozen Q6.5 predictor gate did not select logistic_l2_c1")
    X = np.asarray([[row["features"][name] for name in FEATURE_NAMES] for row in corpus], dtype=float)
    y = np.asarray([row["label"] == "helpful" for row in corpus], dtype=int)
    estimator = models()["logistic_l2_c1"].fit(X, y)
    manifest = {
        "model_id":"cvc-q65-cov-logistic-c1-development-candidate-v1",
        "development_only":True,"formal":False,"selected_before_scheduler_outcomes":True,
        "analysis_sha256":sha(ANALYSIS),"corpus_sha256":sha(CORPUS),
        "feature_names":list(FEATURE_NAMES),
        "imputer_median":estimator.named_steps["impute"].statistics_.tolist(),
        "standardizer_mean":estimator.named_steps["scale"].mean_.tolist(),
        "standardizer_scale":estimator.named_steps["scale"].scale_.tolist(),
        "coefficients":estimator.named_steps["model"].coef_[0].tolist(),
        "intercept":float(estimator.named_steps["model"].intercept_[0]),
        "decision_threshold":0.5,
        "candidate_rule":{"event_onset":True,"fixed_clock_steps":[80,144],
                          "candidate_start_step":24,"candidate_end_step":180},
        "budget":{"packet_bytes":24000,"packet_count":3,"episode_wire_bytes":72000,
                  "fallback_step":217,"reserve_step":218},
        "forbidden_online_inputs":["family","cell_id","seed","evaluator","future_values","branch_outcomes"],
    }
    OUT.write_text(json.dumps(manifest,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    OUT.with_suffix(".json.sha256").write_text(sha(OUT)+"\n",encoding="utf-8")
    print(json.dumps({"model":manifest["model_id"],"sha256":sha(OUT),"features":len(FEATURE_NAMES)},indent=2))


if __name__ == "__main__":
    main()
