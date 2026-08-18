"""Build the Q6.5 causal feature corpus and evaluate interpretable models."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.cvc_q65_opportunity import (FEATURE_NAMES, extract_causal_features,
                                             fitted_runtime_ms, grouped_leave_family_out,
                                             models)

BASE = ROOT / "results/cvc_q65_development/pilot_v1"
CONFIG = ROOT / "config/cvc_q65_pilot.json"
PAIRS = BASE / "paired_results.json"
MANIFEST = BASE / "opportunity_manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    paired = json.loads(PAIRS.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pair_map = {row["opportunity_id"]: row for row in paired["pairs"]}
    corpus = []
    for opportunity in manifest["opportunities"]:
        pair = pair_map[opportunity["opportunity_id"]]
        discovery = rows(BASE / "traces" / f"q65-discovery__{opportunity['cell_id']}.jsonl")
        feature = extract_causal_features(discovery, int(opportunity["step"]),
                                          config["intervention"]["fallback_step"])
        corpus.append({
            "opportunity_id": opportunity["opportunity_id"], "cell_id": opportunity["cell_id"],
            "family": opportunity["family"], "candidate_source_audit_only": opportunity["source"],
            "label": pair["utility"]["label"], "utility": pair["utility"], "features": feature,
        })
    counts = Counter(row["label"] for row in corpus)
    family_labels = defaultdict(Counter)
    for row in corpus:
        family_labels[row["family"]][row["label"]] += 1
    support = {
        "counts": dict(counts),
        "families": {name: dict(values) for name, values in sorted(family_labels.items())},
        "helpful_families": sum(values["helpful"] > 0 for values in family_labels.values()),
        "harmful_families": sum(values["harmful"] > 0 for values in family_labels.values()),
    }
    gate_cfg = config["support_gate"]
    support["pass"] = bool(
        counts["helpful"] >= gate_cfg["helpful_min"] and
        counts["harmful"] >= gate_cfg["harmful_min"] and
        counts["neutral"] >= gate_cfg["neutral_min"] and
        support["helpful_families"] >= gate_cfg["helpful_families_min"] and
        support["harmful_families"] >= gate_cfg["harmful_families_min"]
    )
    if not support["pass"]:
        raise RuntimeError("Q6.5 support gate failed; predictor fitting is prohibited")
    readiness_path = BASE / "model_readiness_manifest.json"
    readiness = {
        "study_id": config["study_id"], "development_only": True, "formal": False,
        "paired_results_sha256": sha(PAIRS), "opportunity_manifest_sha256": sha(MANIFEST),
        "feature_names": list(FEATURE_NAMES), "forbidden_predictors": [
            "family", "cell_id", "seed", "candidate_source", "evaluator", "future_values", "branch_outcomes"
        ],
        "grouping_unit": "physical_cell", "outer_validation": "leave_one_family_out",
        "selection_gate_frozen_before_model_scores": {
            "pooled_auprc_min": .70, "prevalence_margin_min": .20,
            "balanced_accuracy_min": .65, "harmful_false_send_rate_max": .35,
            "sequential_family_helpful_recall_min": .50, "runtime_p95_ms_max": 3.2
        },
        "support": support,
    }
    canonical = json.dumps(readiness, indent=2, sort_keys=True) + "\n"
    if readiness_path.exists() and readiness_path.read_text(encoding="utf-8") != canonical:
        raise RuntimeError("Q6.5 model readiness drift")
    readiness_path.write_text(canonical, encoding="utf-8")
    readiness_path.with_suffix(".json.sha256").write_text(sha(readiness_path) + "\n", encoding="utf-8")

    X = np.asarray([[row["features"][name] for name in FEATURE_NAMES] for row in corpus], dtype=float)
    y = np.asarray([row["label"] == "helpful" for row in corpus], dtype=int)
    families = [row["family"] for row in corpus]
    cell_groups = [row["cell_id"] for row in corpus]
    if any(family in FEATURE_NAMES for family in set(families)) or any(cell in FEATURE_NAMES for cell in set(cell_groups)):
        raise RuntimeError("identity leakage into feature names")
    evaluations = {}
    estimators = models()
    for name, estimator in estimators.items():
        evaluations[name] = grouped_leave_family_out(X, y, families, estimator)
        fitted = estimator.fit(X, y)
        evaluations[name]["runtime"] = fitted_runtime_ms(fitted, X)
        terminal = fitted.named_steps["model"]
        if hasattr(terminal, "coef_"):
            evaluations[name]["full_development_fit_standardized_coefficients"] = {
                feature: float(value) for feature, value in zip(FEATURE_NAMES, terminal.coef_[0])
            }
            evaluations[name]["full_development_fit_intercept"] = float(terminal.intercept_[0])
        if hasattr(terminal, "feature_importances_"):
            evaluations[name]["full_development_fit_feature_importances"] = {
                feature: float(value) for feature, value in zip(FEATURE_NAMES, terminal.feature_importances_)
            }
    prevalence = float(y.mean())
    harmful = np.asarray([row["label"] == "harmful" for row in corpus])
    gate = readiness["selection_gate_frozen_before_model_scores"]
    for result in evaluations.values():
        predictions = np.asarray(result["predictions"])
        harmful_false_rate = float(predictions[harmful].mean()) if harmful.any() else 0.0
        sequential = ["delayed_second_hazard", "alternating_four_stage", "split_gate_then_chicane", "narrow_exit_reveal"]
        sequential_recall = [result["per_family"][family]["recall"] for family in sequential
                             if result["per_family"][family]["helpful"] >= 2]
        result["harmful_false_send_rate"] = harmful_false_rate
        result["minimum_sequential_family_helpful_recall"] = min(sequential_recall) if sequential_recall else None
        result["passes_frozen_gate"] = bool(
            result["pooled_auprc"] >= gate["pooled_auprc_min"] and
            result["pooled_auprc"] >= prevalence + gate["prevalence_margin_min"] and
            result["balanced_accuracy"] >= gate["balanced_accuracy_min"] and
            harmful_false_rate <= gate["harmful_false_send_rate_max"] and
            (not sequential_recall or min(sequential_recall) >= gate["sequential_family_helpful_recall_min"]) and
            result["runtime"]["p95_ms"] <= gate["runtime_p95_ms_max"]
        )
    ranked = sorted(evaluations, key=lambda name:(evaluations[name]["passes_frozen_gate"],
                                                  evaluations[name]["pooled_auprc"],
                                                  evaluations[name]["balanced_accuracy"]), reverse=True)
    selected = ranked[0] if evaluations[ranked[0]]["passes_frozen_gate"] else None
    result = {
        "study_id": config["study_id"], "development_only": True, "formal": False,
        "readiness_sha256": sha(readiness_path), "support": support,
        "helpful_prevalence": prevalence, "feature_names": list(FEATURE_NAMES),
        "evaluations": evaluations, "selected_predictor": selected,
        "predictor_gate_pass": selected is not None,
        "temporal_neural_model_justified": False,
        "feature_class_means": {
            feature: {
                "helpful": float(X[y == 1, index].mean()),
                "nonhelpful": float(X[y == 0, index].mean()),
            }
            for index, feature in enumerate(FEATURE_NAMES)
        },
        "corpus": corpus,
    }
    corpus_path = BASE / "causal_feature_corpus.json"
    corpus_path.write_text(json.dumps({"feature_names":list(FEATURE_NAMES),"rows":corpus},indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    corpus_path.with_suffix(".json.sha256").write_text(sha(corpus_path)+"\n",encoding="utf-8")
    output = BASE / "opportunity_analysis.json"
    output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    output.with_suffix(".json.sha256").write_text(sha(output)+"\n",encoding="utf-8")
    print(json.dumps({"support":support,"prevalence":prevalence,"models":{
        name:{key:row[key] for key in ("pooled_auprc","balanced_accuracy","harmful_false_send_rate","passes_frozen_gate")}
        for name,row in evaluations.items()},"selected_predictor":selected},indent=2))


if __name__ == "__main__":
    main()
