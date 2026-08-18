"""Unblind and qualify the exact frozen CVC-Q4 precursor on CVC-Q5."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from time import perf_counter
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.cvc_q4_precursor import (  # noqa: E402
    causal_trend, decision_space_signals, profile_call, rolling_causal_trends,
)
from evaluation.cvc_q5_qualification import gate_results, onset_opportunity  # noqa: E402
from evaluation.cvc_q5_support import safety_value_from_planners  # noqa: E402


STEP_S = .032
WINDOW = 8
MAX_LEAD_STEPS = 63
OUT = ROOT / "results/cvc_q5_analysis"
FIGURES = ROOT / "figures/cvc_q5"
MANIFEST = ROOT / "results/cvc_q5_readiness/manifest.json"
Q4_ANALYSIS = ROOT / "results/cvc_q4_analysis/analysis.json"
Q4_IMPL = ROOT / "evaluation/cvc_q4_precursor.py"
BLUE, GOLD, INK, GREY, LIGHT = "#2563A6", "#C69214", "#20252B", "#7A828A", "#D9DEE3"

CHART_CONTRACTS = {
    "representative_success": {"question": "Does the frozen rule create a usable opportunity before an onset?", "takeaway": "Show exact level/slope conjunction and onset timing.", "family": "trend", "data": "one frozen positive trace", "renderer": "Matplotlib PNG"},
    "representative_miss": {"question": "Where does the rule miss or provide its weakest warning?", "takeaway": "Expose failure without retuning.", "family": "trend", "data": "one missed or weakest-covered onset", "renderer": "Matplotlib PNG"},
    "event_free": {"question": "What activation occurs without accepted SafetyValue onset?", "takeaway": "Expose false activation on a complete event-free episode.", "family": "trend", "data": "one event-free trace", "renderer": "Matplotlib PNG"},
    "family_summary": {"question": "Does coverage transfer across physical mechanisms?", "takeaway": "Compare coverage and covered-onset lead by family.", "family": "comparison", "data": "all frozen families", "renderer": "Matplotlib PNG"},
    "persistence": {"question": "Are precursor opportunities isolated or persistent?", "takeaway": "Show opportunity class and strict jitter robustness.", "family": "distribution", "data": "all accepted onsets", "renderer": "Matplotlib PNG"},
    "false_activation": {"question": "Is aggregate and event-free activation sparse?", "takeaway": "Compare active time and false-episode activation to frozen gates.", "family": "comparison", "data": "all samples and event-free episodes", "renderer": "Matplotlib PNG"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    return value


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def validate_freeze(manifest: dict) -> None:
    sidecar = Path(str(MANIFEST) + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != sha(MANIFEST):
        raise RuntimeError("CVC-Q5 manifest sidecar mismatch")
    for relative, expected in manifest["protected_sha256"].items():
        path = ROOT / relative
        if not path.exists() or sha(path) != expected:
            raise RuntimeError(f"protected evidence drift: {relative}")
    for record in manifest["complete_attempted_corpus"]:
        for folder, key, suffix in (("traces", "trace_sha256", ".jsonl"), ("jobs", "job_sha256", ".json")):
            path = ROOT / f"results/cvc_q5_stage_a/{folder}/{record['cell_id']}{suffix}"
            if sha(path) != record[key]:
                raise RuntimeError(f"frozen Q5 artifact drift: {path}")


def active_runs(flags: list[bool]) -> list[tuple[int, int]]:
    indices = [i for i, value in enumerate(flags) if value]
    if not indices: return []
    runs, start, previous = [], indices[0], indices[0]
    for index in indices[1:]:
        if index != previous + 1:
            runs.append((start, previous)); start = index
        previous = index
    return runs + [(start, previous)]


def distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "min": None, "q25": None,
                "median": None, "q75": None, "max": None}
    array = np.asarray(values, dtype=np.float64)
    return {"count": len(values), "mean": float(np.mean(array)), "min": float(np.min(array)),
            "q25": float(np.quantile(array, .25)), "median": float(np.median(array)),
            "q75": float(np.quantile(array, .75)), "max": float(np.max(array))}


def trace_plot(trace: dict, onset: int | None, path: Path, title: str, note: str) -> None:
    time = np.arange(len(trace["flags"])) * STEP_S
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, constrained_layout=True)
    axes[0].plot(time, trace["soft"], color=BLUE, lw=1.5, label="soft feasibility mass")
    axes[0].axhline(trace["level_threshold"], color=GOLD, ls="--", label="frozen level")
    axes[1].plot(time, trace["slopes"], color=BLUE, lw=1.5, label="OLS-8 slope")
    axes[1].axhline(-trace["slope_threshold"], color=GOLD, ls="--", label="frozen slope")
    for axis in axes:
        axis.fill_between(time, 0, 1, where=trace["flags"], transform=axis.get_xaxis_transform(), color=GOLD, alpha=.18, label="precursor active")
        if onset is not None: axis.axvline(onset * STEP_S, color=INK, ls=":", lw=1.6, label="SafetyValue onset")
        axis.grid(axis="y", color=LIGHT, lw=.7); axis.legend(loc="best", fontsize=8)
    axes[0].set_ylabel("Feasibility mass"); axes[1].set_ylabel("Slope (/s)"); axes[1].set_xlabel("Episode time (s)")
    fig.suptitle(f"{title}\n{note}", color=INK, fontsize=13)
    fig.savefig(path, dpi=180, facecolor="white"); plt.close(fig)


def make_figures(traces: list[dict], opportunities: list[dict], family: dict, metrics: dict) -> list[str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    covered = [row for row in opportunities if row["covered"]]
    success = max(covered, key=lambda row: (row["lead_s"], row["active_samples"]))
    t = next(row for row in traces if row["cell_id"] == success["cell_id"])
    path = FIGURES / "representative_success.png"; trace_plot(t, success["onset_step"], path, f"Representative covered onset — {success['cell_id']}", f"Lead {success['lead_s']:.3f} s; longest run {success['longest_run_samples']} samples"); outputs.append(path)
    missed = [row for row in opportunities if not row["covered"]]
    weakest = missed[0] if missed else min(covered, key=lambda row: (row["active_samples"], row["lead_s"]))
    t = next(row for row in traces if row["cell_id"] == weakest["cell_id"])
    note = "Frozen rule missed this onset" if missed else "No misses; weakest covered onset shown without substitution"
    path = FIGURES / "representative_miss_or_weakest.png"; trace_plot(t, weakest["onset_step"], path, f"Representative failure/weakest case — {weakest['cell_id']}", note); outputs.append(path)
    event_free = [row for row in traces if not row["onsets"]]
    chosen = max(event_free, key=lambda row: sum(row["flags"]))
    path = FIGURES / "event_free_activation.png"; trace_plot(chosen, None, path, f"Event-free episode — {chosen['cell_id']}", f"Active samples {sum(chosen['flags'])}; no accepted SafetyValue onset"); outputs.append(path)

    names = list(family)
    labels = [name.replace("_", "\n") for name in names]
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    coverage = [family[name]["coverage"] * 100 if family[name]["onset_count"] else 0 for name in names]
    bars = ax.bar(np.arange(len(names)), coverage, color=[BLUE if family[n]["onset_count"] else LIGHT for n in names])
    ax.axhline(50, color=GOLD, ls="--", label="family gate 50%")
    ax.set_xticks(np.arange(len(names)), labels, fontsize=8); ax.set_ylabel("Onset coverage (%)"); ax.set_ylim(0, 108); ax.grid(axis="y", color=LIGHT)
    for bar, name in zip(bars, names): ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+2, f"n={family[name]['onset_count']}\nlead={family[name]['median_lead_s'] if family[name]['median_lead_s'] is not None else '—'}", ha="center", fontsize=7)
    ax.legend(); ax.set_title("Frozen precursor coverage and lead across Q5 families", color=INK)
    path = FIGURES / "per_family_coverage_lead.png"; fig.savefig(path, dpi=180, facecolor="white"); plt.close(fig); outputs.append(path)

    counts = Counter(row["opportunity_class"] for row in opportunities)
    jitter = [sum(row["strict_jitter_robustness"][key] for row in opportunities) for key in ("plus_minus_1_step", "plus_minus_2_steps", "plus_minus_3_steps")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), constrained_layout=True)
    cats = ["missed", "isolated", "intermittent", "stable"]
    axes[0].bar(cats, [counts[x] for x in cats], color=[GREY, GOLD, GOLD, BLUE]); axes[0].set_ylabel("Accepted onsets"); axes[0].set_title("Opportunity persistence")
    axes[1].bar(["±1", "±2", "±3"], jitter, color=BLUE); axes[1].set_ylabel("Strictly robust onsets"); axes[1].set_title("Scheduler-phase jitter robustness")
    for ax in axes: ax.grid(axis="y", color=LIGHT)
    path = FIGURES / "opportunity_persistence.png"; fig.savefig(path, dpi=180, facecolor="white"); plt.close(fig); outputs.append(path)

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    values = [metrics["active_fraction"] * 100, metrics["event_free_episode_activation_fraction"] * 100]
    gates = [2, 25]
    x = np.arange(2); ax.bar(x, values, color=BLUE, width=.55); ax.scatter(x, gates, marker="_", s=700, color=GOLD, linewidth=3, label="frozen maximum")
    ax.set_xticks(x, ["All-sample active time", "Event-free episodes activated"]); ax.set_ylabel("Percent"); ax.grid(axis="y", color=LIGHT); ax.legend(); ax.set_title("Activation burden and event-free false activation", color=INK)
    for i, value in enumerate(values): ax.text(i, value + max(values + gates)*.025, f"{value:.2f}%", ha="center")
    path = FIGURES / "active_time_false_activation.png"; fig.savefig(path, dpi=180, facecolor="white"); plt.close(fig); outputs.append(path)
    return [path.relative_to(ROOT).as_posix() for path in outputs]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")); validate_freeze(manifest)
    q4 = json.loads(Q4_ANALYSIS.read_text(encoding="utf-8"))
    if manifest["protected_sha256"]["evaluation/cvc_q4_precursor.py"] != sha(Q4_IMPL): raise RuntimeError("Q4 implementation changed")
    threshold = q4["thresholds"]
    if (q4["chosen_estimator"].get("method"), q4["chosen_estimator"].get("window_samples")) != ("ols", 8): raise RuntimeError("unexpected Q4 estimator")
    level_t, slope_t = threshold["soft_mass_attention_q01"], threshold["tau_soft_mass_per_s"]
    if round(level_t, 6) != .654345 or round(slope_t, 6) != .118766: raise RuntimeError("Q4 display thresholds disagree")

    OUT.mkdir(parents=True, exist_ok=True)
    all_traces, opportunities, feature_rows = [], [], []
    analysis_start = perf_counter()
    for record in manifest["complete_attempted_corpus"]:
        rows = load_rows(ROOT / f"results/cvc_q5_stage_a/traces/{record['cell_id']}.jsonl")
        signals, safety = [], []
        for row in rows:
            cf = row["counterfactual"]
            signals.append(decision_space_signals(cf["held_planner"], cf["current_planner"]))
            safety.append(safety_value_from_planners(cf["held_planner"], cf["current_planner"]))
        soft = [item.soft_feasibility_mass for item in signals]
        trends = rolling_causal_trends(soft, window_samples=WINDOW, step_s=STEP_S, method="ols")
        slopes = [math.nan if item is None else item.slope_per_s for item in trends]
        flags = [bool(value <= level_t and math.isfinite(slope) and slope < -slope_t) for value, slope in zip(soft, slopes)]
        onsets = [item["step"] for item in record["support"]["accepted_onsets"]]
        for onset in onsets:
            opportunity = onset_opportunity(flags, onset, max_lead_steps=MAX_LEAD_STEPS, step_s=STEP_S)
            opportunity.update({"cell_id": record["cell_id"], "family": record["family"], "role": record["role"]})
            opportunities.append(opportunity)
        all_traces.append({"cell_id": record["cell_id"], "family": record["family"], "role": record["role"], "onsets": onsets, "soft": soft, "slopes": slopes, "flags": flags, "level_threshold": level_t, "slope_threshold": slope_t})
        for index, (row, signal, value, slope, flag) in enumerate(zip(rows, signals, safety, slopes, flags)):
            current = row["counterfactual"]["current_planner"]
            margins = [float(item["conservative_min_clearance_m"]) for item in current["candidates"]]
            finite = [x for x in margins if math.isfinite(x)]
            obstacles = row["counterfactual"]["current_obstacles"]
            nearest = min(obstacles, key=lambda o: math.hypot(float(o["x_m"]), float(o["y_m"]))) if obstacles else None
            feature_rows.append({
                "family": record["family"], "episode": record["cell_id"], "role": record["role"], "seed": record["seed"], "step": index, "time_s": row["time_s"],
                "r1_risk": None, "soft_feasibility_mass": signal.soft_feasibility_mass, "soft_mass_ols8_slope_per_s": slope if math.isfinite(slope) else None, "precursor_active": flag,
                "stale_action_margin_m": signal.stale_action_margin_m, "safety_decision_gap_m": signal.safety_decision_gap_m, "safe_count": signal.safe_count, "candidate_count": signal.candidate_count, "safe_fraction": signal.safe_fraction,
                "candidate_margin_min_m": min(finite) if finite else None, "candidate_margin_q25_m": signal.lower_quartile_margin_m, "candidate_margin_median_m": statistics.median(finite) if finite else None, "candidate_margin_max_m": max(finite) if finite else None,
                "obstacle_bearing_rad": math.atan2(float(nearest["y_m"]), float(nearest["x_m"])) if nearest else None, "obstacle_proximity_m": math.hypot(float(nearest["x_m"]), float(nearest["y_m"])) if nearest else None,
                "component_area_px": None, "component_area_status": "not_logged_by_frozen_q1_controller", "image_age_ms": row["communication"]["image_age_ms"],
                "safety_value_triggered": value.triggered, "safety_value_priority": value.priority, "safety_value_primary_reason": value.primary_reason, "accepted_onset": index in onsets,
                "held_action_id": signal.held_action_id, "current_action_id": signal.current_selected_action_id,
            })
    elapsed = perf_counter() - analysis_start
    total_onsets, covered = len(opportunities), [row for row in opportunities if row["covered"]]
    per_family = {}
    for name in sorted({row["family"] for row in all_traces}):
        family_traces = [row for row in all_traces if row["family"] == name]
        subset = [row for row in opportunities if row["family"] == name]
        covered_subset = [row for row in subset if row["covered"]]
        family_event_free = [row for row in family_traces if not row["onsets"]]
        lead_values = [row["lead_s"] for row in covered_subset]
        per_family[name] = {
            "episode_count": len(family_traces),
            "safety_value_positive_episodes": sum(bool(row["onsets"]) for row in family_traces),
            "onset_count": len(subset), "covered_onsets": len(covered_subset),
            "coverage": len(covered_subset) / len(subset) if subset else 0.0,
            "lead_distribution_s": distribution(lead_values),
            "median_lead_s": statistics.median(lead_values) if lead_values else None,
            "lead_fraction_all_onsets": {
                "ge_0_25_s": sum(value >= .25 for value in lead_values) / len(subset) if subset else 0.0,
                "ge_0_50_s": sum(value >= .50 for value in lead_values) / len(subset) if subset else 0.0,
                "ge_1_00_s": sum(value >= 1.0 for value in lead_values) / len(subset) if subset else 0.0,
            },
            "active_fraction": sum(sum(row["flags"]) for row in family_traces) / sum(len(row["flags"]) for row in family_traces),
            "event_free_episodes": len(family_event_free),
            "event_free_activated_episodes": sum(any(row["flags"]) for row in family_event_free),
            "event_free_activation_fraction": sum(any(row["flags"]) for row in family_event_free) / len(family_event_free) if family_event_free else 0.0,
            "opportunity_classes": dict(Counter(row["opportunity_class"] for row in subset)),
            "usable_covered_fraction": sum(row["usable_opportunity"] for row in covered_subset) / len(covered_subset) if covered_subset else 0.0,
            "jitter_robust_fraction_all_onsets": {key: sum(row["strict_jitter_robustness"][key] for row in subset) / len(subset) if subset else 0.0 for key in ("plus_minus_1_step", "plus_minus_2_steps", "plus_minus_3_steps")},
        }
    active_samples = sum(sum(row["flags"]) for row in all_traces); sample_count = sum(len(row["flags"]) for row in all_traces)
    event_free = [row for row in all_traces if not row["onsets"]]; false_episodes = [row for row in event_free if any(row["flags"])]
    false_runs = [(row["cell_id"], row["family"], start, end) for row in event_free for start, end in active_runs(row["flags"])]
    false_run_lengths = [end - start + 1 for _, _, start, end in false_runs]
    lead_values = [row["lead_s"] for row in covered]
    metrics = {
        "episode_count": len(all_traces), "accepted_onset_count": total_onsets, "covered_onsets": len(covered), "pooled_coverage": len(covered) / total_onsets,
        "lead_times_s": lead_values, "lead_distribution_s": distribution(lead_values), "median_lead_s": statistics.median(lead_values) if covered else None,
        "lead_fraction_all_onsets": {
            "ge_0_25_s": sum(value >= .25 for value in lead_values) / total_onsets,
            "ge_0_50_s": sum(value >= .50 for value in lead_values) / total_onsets,
            "ge_1_00_s": sum(value >= 1.0 for value in lead_values) / total_onsets,
        },
        "active_samples": active_samples, "sample_count": sample_count, "active_fraction": active_samples / sample_count,
        "event_free_episode_count": len(event_free), "event_free_activated_episodes": len(false_episodes), "event_free_episode_activation_fraction": len(false_episodes) / len(event_free),
        "covered_usable_count": sum(row["usable_opportunity"] for row in covered), "covered_usable_fraction": sum(row["usable_opportunity"] for row in covered) / len(covered) if covered else 0.0,
        "opportunity_width": {
            "active_duration_s": distribution([row["active_duration_s"] for row in covered]),
            "longest_contiguous_run_s": distribution([row["longest_run_s"] for row in covered]),
            "last_activation_gap_s": distribution([row["last_gap_s"] for row in covered]),
            "persistent_2_fraction_all_onsets": sum(row["persistent_2_samples"] for row in opportunities) / total_onsets,
            "persistent_3_fraction_all_onsets": sum(row["persistent_3_samples"] for row in opportunities) / total_onsets,
            "isolated_one_step_fraction_all_onsets": sum(row["opportunity_class"] == "isolated" for row in opportunities) / total_onsets,
        },
        "jitter_robust_onset_counts": {key: sum(row["strict_jitter_robustness"][key] for row in opportunities) for key in ("plus_minus_1_step", "plus_minus_2_steps", "plus_minus_3_steps")},
        "opportunity_classes": dict(Counter(row["opportunity_class"] for row in opportunities)), "per_family": per_family,
        "event_free_family_summary": {name: {"episodes": sum(r["family"] == name for r in event_free), "activated": sum(r["family"] == name and any(r["flags"]) for r in event_free)} for name in per_family},
        "false_activation": {
            "run_count": len(false_runs),
            "activations_per_event_free_episode": len(false_runs) / len(event_free),
            "run_duration_s": distribution([length * STEP_S for length in false_run_lengths]),
            "longest_run_s": max(false_run_lengths, default=0) * STEP_S,
            "isolated_run_count": sum(length == 1 for length in false_run_lengths),
            "persistent_run_count": sum(length >= 2 for length in false_run_lengths),
            "family_run_count": dict(Counter(family for _, family, _, _ in false_runs)),
        },
    }
    gates = gate_results(metrics, manifest["generalization_gates"])

    fields = list(feature_rows[0]); csv_path = OUT / "causal_feature_dataset.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(feature_rows)
    jsonl_path = OUT / "causal_feature_dataset.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(clean(row), sort_keys=True, separators=(",", ":")) for row in feature_rows) + "\n", encoding="utf-8")

    exemplar = all_traces[0]
    exemplar_row = load_rows(ROOT / "results/cvc_q5_stage_a/traces" / f"{exemplar['cell_id']}.jsonl")[-1]
    exemplar_cf = exemplar_row["counterfactual"]
    runtime = profile_call(lambda: (
        decision_space_signals(exemplar_cf["held_planner"], exemplar_cf["current_planner"]),
        causal_trend(exemplar["soft"][-8:], step_s=STEP_S, method="ols"),
    ), repetitions=1000)
    figures = make_figures(all_traces, opportunities, per_family, metrics)
    result = {
        "study_id": manifest["study_id"], "development_only": True, "formal": False,
        "conclusion_case": "CASE_A" if all(gates.values()) else "CASE_B" if gates["A_pooled_coverage"] and gates["B_cross_family_coverage"] else "CASE_C" if metrics["pooled_coverage"] > 0 else "CASE_D",
        "frozen_manifest_sha256": sha(MANIFEST), "q4_analysis_sha256": sha(Q4_ANALYSIS), "q4_implementation_sha256": sha(Q4_IMPL),
        "rule": {"exact": f"soft_feasibility_mass <= {level_t!r} AND OLS-8 slope < {-slope_t!r} /s", "level_threshold": level_t, "slope_threshold_magnitude_per_s": slope_t, "window_samples": WINDOW, "method": "ols", "changed_or_refit": False},
        "anti_contamination": {"stage_a_completed_before_unblinding": True, "all_attempts_retained": True, "precursor_used_in_scenario_construction": False},
        "support": {"positive_families": manifest["positive_families"], "family_support": manifest["family_support"]},
        "metrics": metrics, "opportunities": opportunities, "generalization_gates": manifest["generalization_gates"], "gate_results": gates, "all_gates_pass": all(gates.values()),
        "runtime": {"corpus_analysis_s": elapsed, "samples_per_s": sample_count / elapsed, "online_composite_profile": runtime},
        "causal_feature_dataset": {"csv": csv_path.relative_to(ROOT).as_posix(), "csv_sha256": sha(csv_path), "jsonl": jsonl_path.relative_to(ROOT).as_posix(), "jsonl_sha256": sha(jsonl_path), "rows": len(feature_rows), "evaluator_fields_included": False, "unavailable_fields": {"r1_risk": "not logged by frozen Q1 runtime", "component_area_px": "not logged by frozen Q1 runtime"}, "split_hygiene": "family and episode identities retained; no train/test split or model fitting performed"},
        "chart_contracts": CHART_CONTRACTS, "figures": figures,
        "scheduler_or_policy_integration_performed": False, "a0_a1_comparison_performed": False, "machine_learning_used": False,
    }
    result_path = OUT / "analysis.json"; result_path.write_text(json.dumps(clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "analysis.json.sha256").write_text(sha(result_path) + "\n", encoding="utf-8")
    print(json.dumps({"case": result["conclusion_case"], "metrics": clean(metrics), "gates": gates, "analysis_sha256": sha(result_path), "figures": figures}, indent=2))


if __name__ == "__main__": main()
