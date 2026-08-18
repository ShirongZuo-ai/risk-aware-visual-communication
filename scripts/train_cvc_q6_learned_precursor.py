"""Grouped development-only learned precursor audit on the frozen Q5 causal dataset."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import make_column_transformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/cvc_q5_analysis/causal_feature_dataset.csv"
OUT = ROOT / "results/cvc_q6_learned_precursor"
HORIZON_STEPS = 16
FEATURES = ["soft_feasibility_mass", "soft_mass_ols8_slope_per_s", "stale_action_margin_m",
            "safety_decision_gap_m", "safe_fraction", "candidate_margin_min_m",
            "candidate_margin_q25_m", "candidate_margin_median_m", "candidate_margin_max_m",
            "obstacle_bearing_rad", "obstacle_proximity_m", "image_age_ms", "action_changed"]

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def targets(frame: pd.DataFrame) -> np.ndarray:
    y = np.zeros(len(frame), dtype=np.int8)
    for _, idx in frame.groupby("episode", sort=False).groups.items():
        indexes = np.asarray(list(idx)); steps = frame.loc[indexes, "step"].to_numpy()
        onsets = steps[frame.loc[indexes, "accepted_onset"].astype(bool).to_numpy()]
        if len(onsets):
            y[indexes] = np.array([any(step < onset <= step + HORIZON_STEPS for onset in onsets)
                                   for step in steps], dtype=np.int8)
    return y

def model(name: str):
    if name == "logistic":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(C=.1, class_weight="balanced", max_iter=1000,
                                                random_state=20260816))
    return make_pipeline(SimpleImputer(strategy="median"),
                         HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=7,
                                                        learning_rate=.05, l2_regularization=1.0,
                                                        class_weight="balanced", random_state=20260816))

def event_metrics(frame: pd.DataFrame, y: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    active = scores >= threshold
    recalled = total = 0
    false_eps = false_active_eps = 0
    for _, idx in frame.groupby("episode", sort=False).groups.items():
        indexes = np.asarray(list(idx)); steps = frame.loc[indexes, "step"].to_numpy()
        onset_steps = steps[frame.loc[indexes, "accepted_onset"].astype(bool).to_numpy()]
        if len(onset_steps):
            total += len(onset_steps)
            recalled += sum(any(active[indexes][(steps >= onset-HORIZON_STEPS) & (steps < onset)])
                            for onset in onset_steps)
        else:
            false_eps += 1; false_active_eps += int(active[indexes].any())
    return {"event_recall": recalled / total if total else None, "events": total,
            "active_fraction": float(active.mean()),
            "false_warning_episode_fraction": false_active_eps / false_eps if false_eps else None,
            "false_warning_episodes": false_active_eps, "event_free_episodes": false_eps}

def choose_threshold(frame, y, scores) -> float:
    candidates = np.unique(np.quantile(scores, np.linspace(.90, .999, 100)))
    ranked = []
    for threshold in candidates:
        metrics = event_metrics(frame, y, scores, float(threshold))
        if metrics["active_fraction"] <= .03:
            ranked.append((metrics["event_recall"] or 0.0,
                           -(metrics["false_warning_episode_fraction"] or 0.0), float(threshold)))
    return max(ranked)[2] if ranked else float(np.quantile(scores, .99))

def main() -> None:
    frame = pd.read_csv(DATA)
    frame["action_changed"] = (frame["held_action_id"] != frame["current_action_id"]).astype(float)
    frame[FEATURES] = frame[FEATURES].replace([np.inf, -np.inf], np.nan)
    y = targets(frame); families = sorted(frame["family"].unique())
    results = {}; oof_by_model = {}
    for name in ("logistic", "hist_gradient_boosting"):
        oof = np.zeros(len(frame)); folds = []
        for family in families:
            test = frame["family"].eq(family).to_numpy(); train = ~test
            estimator = model(name); estimator.fit(frame.loc[train, FEATURES], y[train])
            scores = estimator.predict_proba(frame.loc[test, FEATURES])[:, 1]; oof[test] = scores
            positives = int(y[test].sum())
            folds.append({"held_family": family, "rows": int(test.sum()), "positive_rows": positives,
                          "auprc": float(average_precision_score(y[test], scores)) if positives else None})
        threshold = choose_threshold(frame, y, oof)
        metrics = event_metrics(frame, y, oof, threshold)
        positive_aps = [row["auprc"] for row in folds if row["auprc"] is not None]
        results[name] = {"family_folds": folds, "positive_family_macro_auprc": float(np.mean(positive_aps)),
                         "oof_auprc": float(average_precision_score(y, oof)),
                         "threshold_from_oof_development": threshold, **metrics}
        oof_by_model[name] = oof
    selected = max(results, key=lambda name: (results[name]["positive_family_macro_auprc"],
                                               -results[name]["false_warning_episode_fraction"]))
    final = model(selected); final.fit(frame[FEATURES], y)
    OUT.mkdir(parents=True, exist_ok=True); artifact = OUT / "model.joblib"; joblib.dump(final, artifact)
    np.save(OUT / "oof_scores.npy", oof_by_model[selected])
    report = {"study_id": "cvc-q6-learned-precursor-development-v1", "development_only": True,
              "formal": False, "target": "accepted SafetyValue onset within next 0.512 s",
              "target_uses_evaluator_truth": False, "horizon_steps": HORIZON_STEPS,
              "features": FEATURES, "rows": len(frame), "episodes": int(frame.episode.nunique()),
              "families": families, "positive_rows": int(y.sum()),
              "group_split": "leave-one-physical-family-out; no episode crosses folds",
              "models": results, "selected_model": selected,
              "selected_threshold": results[selected]["threshold_from_oof_development"],
              "model_sha256": sha(artifact), "source_dataset_sha256": sha(DATA),
              "integration_authorized": False,
              "integration_gate": "held-family metrics and event-free false warnings must justify a frozen runtime generation"}
    rp = OUT / "training_report.json"; rp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n")
    rp.with_suffix(".json.sha256").write_text(sha(rp)+"\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__": main()
