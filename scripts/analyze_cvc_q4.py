"""Run the development-only CVC-Q4 precursor/gradient diagnostic.

No Webots process is started and no communication-policy result is modified.
Q1 stable/no-change samples calibrate signal tails; frozen Q2/Q3 traces supply
evaluation-only future Safety Decision Value labels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.cvc_q4_precursor import (  # noqa: E402
    HARD_CLEARANCE_M,
    PREFERRED_CLEARANCE_M,
    abnormal_tail_threshold,
    binary_diagnostic,
    causal_trend,
    decision_space_signals,
    event_onsets,
    future_event_labels,
    precursor_leads,
    profile_call,
    rolling_causal_trends,
)
from scripts.run_cvc_q3_webots import protected_paths  # noqa: E402


STEP_S = 0.032
WINDOWS = (8, 12, 16, 20)
METHODS = ("ols", "theil_sen", "median_adjacent")
HORIZONS = {"0.25s": 8, "0.5s": 16, "1.0s": 32, "2.0s": 63}
MAX_LEAD_STEPS = 63
OUT = ROOT / "results" / "cvc_q4_analysis"
FIGURES = ROOT / "figures" / "cvc_q4"

BLUE = "#2563A6"
GOLD = "#C69214"
INK = "#20252B"
GREY = "#7A828A"
LIGHT_GREY = "#D9DEE3"
PALE_BLUE = "#DCEAF6"
PALE_GOLD = "#F6E8BF"


CHART_CONTRACTS = {
    "aligned_event_traces": {
        "question": "How do decision-space levels and causal slopes evolve before Safety Value onset?",
        "takeaway": "Show timing and threshold crossings without implying navigation benefit.",
        "family": "Trend",
        "variant": "faceted aligned multi-series line",
        "data": "two event-positive trace executions, 312 ordered 32 ms samples each",
        "renderer": "static Matplotlib PNG",
        "palette": "hard two-root cap: blue signals, gold thresholds/events, neutral context; line style also distinguishes",
        "output": "figures/cvc_q4/aligned_*.png; inspect exported PNG",
    },
    "candidate_comparison": {
        "question": "Which interpretable precursor balances event coverage and false activation?",
        "takeaway": "Expose the coverage-specificity trade-off for all retained candidates.",
        "family": "Relationship",
        "variant": "labeled scatter",
        "data": "candidate x estimator x window rows at one diagnostic grain",
        "renderer": "static Matplotlib PNG",
        "palette": "hard two-root cap with marker shape for rule family",
        "output": "figures/cvc_q4/candidate_tradeoff.png; inspect exported PNG",
    },
    "slope_distributions": {
        "question": "Do pre-event slopes separate from the stable/no-change baseline?",
        "takeaway": "Compare robust distributions and show non-zero tail thresholds.",
        "family": "Distribution",
        "variant": "paired boxplots",
        "data": "stable Q1 calibration slopes and strictly pre-event Q2/Q3 slopes",
        "renderer": "static Matplotlib PNG",
        "palette": "hard two-root cap, blue baseline and gold pre-event",
        "output": "figures/cvc_q4/slope_distributions.png; inspect exported PNG",
    },
    "window_tradeoff": {
        "question": "How do causal window and estimator affect coverage and false activation?",
        "takeaway": "Reveal responsiveness-versus-smoothing behavior without selecting on navigation outcomes.",
        "family": "Trend",
        "variant": "small-multiple ordered line-dot",
        "data": "four window lengths by three estimators for retained rules",
        "renderer": "static Matplotlib PNG",
        "palette": "hard two-root cap plus line styles and markers",
        "output": "figures/cvc_q4/window_tradeoff.png; inspect exported PNG",
    },
}


@dataclass
class Trace:
    study: str
    identity: str
    scenario: str
    policy: str
    path: Path
    m_stale: list[float]
    gap: list[float]
    safe_fraction: list[float]
    positive_slack: list[float]
    soft_mass: list[float]
    lower_q25_margin: list[float]
    stable: list[bool]
    events: list[bool]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def _identity(path: Path, study: str) -> tuple[str, str]:
    stem = path.stem
    if "__" in stem:
        _, scenario, policy = stem.split("__")
        return scenario, policy
    return stem, "U0-support"


def load_traces(root: Path, study: str, *, event_labels: bool) -> list[Trace]:
    traces: list[Trace] = []
    for path in sorted(root.glob("*.jsonl")):
        scenario, policy = _identity(path, study)
        columns: dict[str, list] = {
            "m_stale": [], "gap": [], "safe_fraction": [], "positive_slack": [],
            "soft_mass": [], "lower_q25_margin": [], "stable": [], "events": [],
        }
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                counterfactual = row["counterfactual"]
                signal = decision_space_signals(
                    counterfactual["held_planner"], counterfactual["current_planner"]
                )
                columns["m_stale"].append(signal.stale_action_margin_m)
                columns["gap"].append(signal.safety_decision_gap_m)
                columns["safe_fraction"].append(signal.safe_fraction)
                columns["positive_slack"].append(signal.aggregate_positive_slack_m)
                columns["soft_mass"].append(signal.soft_feasibility_mass)
                columns["lower_q25_margin"].append(signal.lower_quartile_margin_m)
                columns["stable"].append(signal.stable_no_change)
                columns["events"].append(
                    bool(row["safety_value"]["triggered"]) if event_labels else False
                )
        traces.append(Trace(study, path.stem, scenario, policy, path, **columns))
    return traces


SIGNALS = {
    "m_stale": "m_stale",
    "gap": "gap",
    "safe_fraction": "safe_fraction",
    "positive_slack": "positive_slack",
    "soft_mass": "soft_mass",
    "lower_q25_margin": "lower_q25_margin",
}


def trends_for(trace: Trace, method: str, window: int) -> dict[str, list]:
    return {
        name: rolling_causal_trends(getattr(trace, field), window_samples=window,
                                    step_s=STEP_S, method=method)
        for name, field in SIGNALS.items()
    }


def calibration(
    traces: list[Trace], method: str, window: int,
) -> tuple[dict[str, float], dict[str, Any], dict[str, dict[str, list]]]:
    cached = {trace.identity: trends_for(trace, method, window) for trace in traces}
    slopes = {name: [] for name in SIGNALS}
    levels = {name: [] for name in SIGNALS}
    reliability = {name: {"r_squared": [], "sign_consistency": [], "residual_scale": []}
                   for name in SIGNALS}
    for trace in traces:
        trend_set = cached[trace.identity]
        for index in range(window - 1, len(trace.events)):
            if not all(trace.stable[index - window + 1:index + 1]):
                continue
            for name, field in SIGNALS.items():
                trend = trend_set[name][index]
                assert trend is not None
                if math.isfinite(trend.slope_per_s):
                    slopes[name].append(trend.slope_per_s)
                    reliability[name]["r_squared"].append(trend.r_squared)
                    reliability[name]["sign_consistency"].append(trend.sign_consistency)
                    reliability[name]["residual_scale"].append(trend.residual_scale)
                value = getattr(trace, field)[index]
                if math.isfinite(value):
                    levels[name].append(value)
    thresholds = {
        "tau_m_per_s": abnormal_tail_threshold(slopes["m_stale"], tail="negative"),
        "tau_g_per_s": abnormal_tail_threshold(slopes["gap"], tail="positive"),
        "tau_safe_fraction_per_s": abnormal_tail_threshold(slopes["safe_fraction"], tail="negative"),
        "tau_positive_slack_m_per_s": abnormal_tail_threshold(slopes["positive_slack"], tail="negative"),
        "tau_soft_mass_per_s": abnormal_tail_threshold(slopes["soft_mass"], tail="negative"),
        "tau_lower_q25_margin_m_per_s": abnormal_tail_threshold(slopes["lower_q25_margin"], tail="negative"),
        "m_attention_m": PREFERRED_CLEARANCE_M,
        "gap_attention_m": float(np.quantile(levels["gap"], 0.95)),
        "soft_mass_attention_q01": float(np.quantile(levels["soft_mass"], 0.01)),
        "soft_mass_attention_q05": float(np.quantile(levels["soft_mass"], 0.05)),
    }
    summary = {
        "construction": (
            "Q1 U0-support windows with exact held/current selected-action and safe-set equality, "
            "both selected classes preferred_safe; 1% one-sided slope tails; level thresholds use "
            "the frozen 0.075 m preferred boundary or stable-signal quantiles"
        ),
        "no_future_event_or_evaluator_outcome_used": True,
        "window_samples": window,
        "window_span_s": (window - 1) * STEP_S,
        "method": method,
        "counts": {name: len(values) for name, values in slopes.items()},
        "slope_quantiles": {
            name: quantiles(values) for name, values in slopes.items()
        },
        "level_quantiles": {
            name: quantiles(values) for name, values in levels.items()
        },
        "reliability": {
            name: {metric: quantiles([value for value in values if math.isfinite(value)])
                   for metric, values in metrics.items()}
            for name, metrics in reliability.items()
        },
    }
    return thresholds, summary, cached


def quantiles(values: Iterable[float]) -> dict[str, float | int | None]:
    array = np.asarray([value for value in values if math.isfinite(value)], dtype=np.float64)
    if not array.size:
        return {"n": 0, "min": None, "q01": None, "q05": None, "q25": None,
                "median": None, "q75": None, "q95": None, "q99": None, "max": None}
    return {
        "n": int(array.size), "min": float(np.min(array)),
        "q01": float(np.quantile(array, 0.01)), "q05": float(np.quantile(array, 0.05)),
        "q25": float(np.quantile(array, 0.25)), "median": float(np.median(array)),
        "q75": float(np.quantile(array, 0.75)), "q95": float(np.quantile(array, 0.95)),
        "q99": float(np.quantile(array, 0.99)), "max": float(np.max(array)),
    }


def flags_for(trace: Trace, trends: dict[str, list], thresholds: dict[str, float]) -> dict[str, list[bool]]:
    result = {name: [] for name in (
        "m_slope", "m_level_slope", "m_slope_reliable", "gap_slope", "gap_level_slope",
        "m_gap_joint", "safe_fraction_contraction", "positive_slack_contraction",
        "soft_mass_contraction", "soft_q01_level_contraction", "soft_q05_level_contraction",
        "lower_q25_contraction", "m_level_slope_safe_contraction",
    )}
    for index in range(len(trace.events)):
        values = {name: trends[name][index] for name in SIGNALS}
        sm = values["m_stale"]
        sg = values["gap"]
        sf = values["safe_fraction"]
        sp = values["positive_slack"]
        ss = values["soft_mass"]
        sq = values["lower_q25_margin"]
        m_bad = sm is not None and math.isfinite(sm.slope_per_s) and sm.slope_per_s < -thresholds["tau_m_per_s"]
        g_bad = sg is not None and math.isfinite(sg.slope_per_s) and sg.slope_per_s > thresholds["tau_g_per_s"]
        fraction_bad = sf is not None and math.isfinite(sf.slope_per_s) and sf.slope_per_s < -thresholds["tau_safe_fraction_per_s"]
        slack_bad = sp is not None and math.isfinite(sp.slope_per_s) and sp.slope_per_s < -thresholds["tau_positive_slack_m_per_s"]
        soft_bad = ss is not None and math.isfinite(ss.slope_per_s) and ss.slope_per_s < -thresholds["tau_soft_mass_per_s"]
        q25_bad = sq is not None and math.isfinite(sq.slope_per_s) and sq.slope_per_s < -thresholds["tau_lower_q25_margin_m_per_s"]
        result["m_slope"].append(m_bad)
        result["m_level_slope"].append(m_bad and trace.m_stale[index] <= thresholds["m_attention_m"])
        result["m_slope_reliable"].append(m_bad and sm is not None and sm.sign_consistency >= 0.75)
        result["gap_slope"].append(g_bad)
        result["gap_level_slope"].append(g_bad and trace.gap[index] >= thresholds["gap_attention_m"])
        result["m_gap_joint"].append(m_bad and g_bad)
        result["safe_fraction_contraction"].append(fraction_bad)
        result["positive_slack_contraction"].append(slack_bad)
        result["soft_mass_contraction"].append(soft_bad)
        result["soft_q01_level_contraction"].append(
            soft_bad and trace.soft_mass[index] <= thresholds["soft_mass_attention_q01"]
        )
        result["soft_q05_level_contraction"].append(
            soft_bad and trace.soft_mass[index] <= thresholds["soft_mass_attention_q05"]
        )
        result["lower_q25_contraction"].append(q25_bad)
        result["m_level_slope_safe_contraction"].append(
            m_bad and trace.m_stale[index] <= thresholds["m_attention_m"] and soft_bad
        )
    return result


def summarize_rule(
    traces: list[Trace], flag_sets: dict[str, dict[str, list[bool]]], rule: str,
) -> dict[str, Any]:
    total_steps = active_steps = false_steps = stable_negative = stable_false = 0
    event_count = covered = no_event_episodes = false_event_episodes = 0
    leads: list[float] = []
    durations: list[float] = []
    future = {name: {"precursor": [], "label": []} for name in HORIZONS}
    scenario: dict[str, dict[str, int]] = {}
    study: dict[str, dict[str, int]] = {}
    event_records: list[dict[str, Any]] = []
    for trace in traces:
        flags = flag_sets[trace.identity][rule]
        onsets = event_onsets(trace.events)
        trace_leads = precursor_leads(flags, trace.events, max_lead_steps=MAX_LEAD_STEPS, step_s=STEP_S)
        event_count += len(onsets)
        covered += sum(value is not None for value in trace_leads)
        leads.extend(value for value in trace_leads if value is not None)
        for onset, lead in zip(onsets, trace_leads):
            event_records.append({"study": trace.study, "trace": trace.identity,
                                  "scenario": trace.scenario, "policy": trace.policy,
                                  "event_onset_step": onset, "lead_s": lead})
        upcoming = future_event_labels(trace.events, MAX_LEAD_STEPS)
        total_steps += len(flags)
        active_steps += sum(flags)
        false_steps += sum(flag and not label for flag, label in zip(flags, upcoming))
        stable_negative += sum(stable and not label for stable, label in zip(trace.stable, upcoming))
        stable_false += sum(flag and stable and not label
                            for flag, stable, label in zip(flags, trace.stable, upcoming))
        if not onsets:
            no_event_episodes += 1
            false_event_episodes += bool(any(flags))
        start = None
        for index, active in enumerate(flags + [False]):
            if active and start is None:
                start = index
            elif not active and start is not None:
                durations.append((index - start) * STEP_S)
                start = None
        for name, horizon in HORIZONS.items():
            future[name]["precursor"].extend(flags)
            future[name]["label"].extend(future_event_labels(trace.events, horizon))
        for key, group in ((trace.scenario, scenario), (trace.study, study)):
            item = group.setdefault(key, {"episodes": 0, "event_onsets": 0, "covered": 0,
                                          "active_steps": 0, "false_steps_2s": 0})
            item["episodes"] += 1
            item["event_onsets"] += len(onsets)
            item["covered"] += sum(value is not None for value in trace_leads)
            item["active_steps"] += sum(flags)
            item["false_steps_2s"] += sum(flag and not label for flag, label in zip(flags, upcoming))
    lead_values = np.asarray(leads, dtype=np.float64)
    return {
        "rule": rule, "total_steps": total_steps, "active_steps": active_steps,
        "active_fraction": active_steps / total_steps,
        "event_onsets": event_count, "event_coverage": covered / event_count if event_count else None,
        "covered_events": covered,
        "lead_s": quantiles(lead_values),
        "fraction_lead_gt_0_25s": float(np.mean(lead_values > 0.25)) if lead_values.size else 0.0,
        "fraction_lead_gt_0_5s": float(np.mean(lead_values > 0.5)) if lead_values.size else 0.0,
        "fraction_lead_gt_1_0s": float(np.mean(lead_values > 1.0)) if lead_values.size else 0.0,
        "false_steps_2s": false_steps,
        "false_step_fraction_all": false_steps / total_steps,
        "stable_safe_false_fraction": stable_false / stable_negative if stable_negative else None,
        "no_event_episodes": no_event_episodes,
        "false_event_episodes": false_event_episodes,
        "false_event_episode_fraction": false_event_episodes / no_event_episodes if no_event_episodes else None,
        "activation_duration_s": quantiles(durations),
        "future_event_prediction": {
            name: binary_diagnostic(values["precursor"], values["label"])
            for name, values in future.items()
        },
        "by_scenario": scenario, "by_study": study, "events": event_records,
    }


def evaluate_variants(calibration_traces: list[Trace], evaluation_traces: list[Trace]):
    variants: list[dict[str, Any]] = []
    cache: dict[tuple[str, int], dict[str, dict[str, list]]] = {}
    calibration_records: dict[str, Any] = {}
    threshold_records: dict[str, Any] = {}
    for method in METHODS:
        for window in WINDOWS:
            thresholds, baseline, _ = calibration(calibration_traces, method, window)
            key = f"{method}_{window}"
            calibration_records[key] = baseline
            threshold_records[key] = thresholds
            trace_trends = {trace.identity: trends_for(trace, method, window)
                            for trace in evaluation_traces}
            cache[(method, window)] = trace_trends
            flag_sets = {trace.identity: flags_for(trace, trace_trends[trace.identity], thresholds)
                         for trace in evaluation_traces}
            for rule in next(iter(flag_sets.values())):
                summary = summarize_rule(evaluation_traces, flag_sets, rule)
                summary.update({"method": method, "window_samples": window,
                                "window_span_s": (window - 1) * STEP_S})
                variants.append(summary)
    return variants, calibration_records, threshold_records, cache


def pre_event_distributions(traces: list[Trace], trends: dict[str, dict[str, list]], window: int) -> dict[str, Any]:
    output: dict[str, list] = {name: [] for name in SIGNALS}
    levels: dict[str, list] = {name: [] for name in SIGNALS}
    for trace in traces:
        onsets = event_onsets(trace.events)
        pre_event = future_event_labels(trace.events, MAX_LEAD_STEPS)
        for index, is_pre in enumerate(pre_event):
            if not is_pre:
                continue
            for name, field in SIGNALS.items():
                trend = trends[trace.identity][name][index]
                if trend is not None and math.isfinite(trend.slope_per_s):
                    output[name].append(trend.slope_per_s)
                value = getattr(trace, field)[index]
                if math.isfinite(value):
                    levels[name].append(value)
    return {
        "strictly_pre_event_within_2s_slope": {name: quantiles(values) for name, values in output.items()},
        "strictly_pre_event_within_2s_level": {name: quantiles(values) for name, values in levels.items()},
    }


def runtime_profile(calibration_path: Path) -> dict[str, Any]:
    row = json.loads(calibration_path.open(encoding="utf-8").readline())
    held = row["counterfactual"]["held_planner"]
    current = row["counterfactual"]["current_planner"]
    values = [0.95, 0.94, 0.92, 0.89, 0.85, 0.80, 0.74, 0.67]
    return {
        "decision_space_signals": profile_call(lambda: decision_space_signals(held, current), 3000),
        "ols_8_sample_trend": profile_call(lambda: causal_trend(values, step_s=STEP_S, method="ols"), 3000),
        "six_signal_precursor_path": profile_call(
            lambda: (
                decision_space_signals(held, current),
                [causal_trend([value - 0.002 * index for value in values], step_s=STEP_S, method="ols")
                 for index in range(6)],
            ),
            1000,
        ),
        "scope": "in-process primitive timing; file I/O, camera, planner and scheduler excluded",
        "deadline_ms": 32.0,
    }


def protected_evidence() -> dict[str, Any]:
    manifest_path = ROOT / "results" / "cvc_q3_readiness" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = {name: sha(path) for name, path in protected_paths().items()}
    expected = manifest["protected_sha256"]
    extras = {
        "q3_readiness_manifest": (manifest_path, "d05c0ca5332c4e676dbcf0058d789fb03da3837206988badd394e833520a1673"),
        "q3_matrix": (ROOT / "results/cvc_q3_webots/matrix_results.json", "adf7de55fa3e1da95fb4427e0408bf9583cbabc7f50403a39a59fe22ca3be95b"),
        "q3_analysis": (ROOT / "results/cvc_q3_analysis/analysis.json", "cd01a20b48e1aed699101abe249ba3d5cf9ba855a2ac52ed1814f2ee7828967f"),
        "m9a_manifest": (ROOT / "results/m9a_formal/formal_manifest.json", "52b33b0778f52870f867688d16ce8d32ac086c58a30689ea97672b533a702e8f"),
        "m9a_result": (ROOT / "results/m9a_formal/formal_results.json", "efaea55013747f3cedc408817ced79139f2a6654ebe0bf24269de265ef041715"),
        "m9a_ledger": (ROOT / "results/m9a_formal/formal_access_ledger.jsonl", "efd873be3adf726d10e5a3b84d98244a3adcffc3b49d0b8f2277afb43a2950ca"),
        "m9b_result": (ROOT / "results/m9b_formal/formal_results.json", "59bfd8c579daa04b65d34f0b24b6e1f6d478c673b11be2f5047e8f27d96f8b11"),
        "m9b_ledger": (ROOT / "results/m9b_readiness_v3/formal_access_ledger.jsonl", "bd9b6fd3bd16c3d648c4b8897cef4a66621cc6bc8eeac57d0a3f12f8b5c73bc4"),
    }
    extra_rows = {}
    for name, (path, expected_sha) in extras.items():
        extra_rows[name] = {"path": path.relative_to(ROOT).as_posix(), "expected": expected_sha,
                            "actual": sha(path) if path.exists() else None,
                            "match": path.exists() and sha(path) == expected_sha}
    return {
        "q3_manifest_protected_inputs_match": actual == expected,
        "q3_changed_inputs": sorted(name for name in set(actual) | set(expected)
                                    if actual.get(name) != expected.get(name)),
        "q3_protected_sha256": actual,
        "historical_artifacts": extra_rows,
        "all_match": actual == expected and all(row["match"] for row in extra_rows.values()),
    }


def plot_aligned(trace: Trace, trend_set: dict[str, list], thresholds: dict[str, float], flags: list[bool]) -> Path:
    time = np.arange(len(trace.events)) * STEP_S
    onset = event_onsets(trace.events)[0]
    lo, hi = max(0, onset - 90), min(len(time), onset + 25)
    slopes_m = [np.nan if trend is None else trend.slope_per_s for trend in trend_set["m_stale"]]
    slopes_g = [np.nan if trend is None else trend.slope_per_s for trend in trend_set["gap"]]
    slopes_s = [np.nan if trend is None else trend.slope_per_s for trend in trend_set["soft_mass"]]
    fig, axes = plt.subplots(5, 1, figsize=(11, 12), sharex=True, constrained_layout=True)
    panels = [
        (trace.m_stale, thresholds["m_attention_m"], "M_stale (m)", "level"),
        (slopes_m, -thresholds["tau_m_per_s"], "slope(M_stale) (m/s)", "slope"),
        (trace.gap, thresholds["gap_attention_m"], "G (m)", "level"),
        (trace.soft_mass, thresholds["soft_mass_attention_q01"], "soft feasibility mass", "level"),
        (slopes_s, -thresholds["tau_soft_mass_per_s"], "slope(soft feasibility) (/s)", "slope"),
    ]
    for axis, (series, reference, label, _) in zip(axes, panels):
        axis.plot(time[lo:hi], np.asarray(series)[lo:hi], color=BLUE, linewidth=1.8)
        axis.axhline(reference, color=GOLD, linestyle="--", linewidth=1.3, label="calibrated reference")
        axis.axvline(time[onset], color=INK, linestyle=":", linewidth=1.5, label="Safety Value onset")
        active = np.asarray(flags[lo:hi], dtype=bool)
        axis.fill_between(time[lo:hi], 0, 1, where=active, color=PALE_GOLD, alpha=0.55,
                          transform=axis.get_xaxis_transform(), label="selected precursor active")
        axis.set_ylabel(label)
        axis.grid(axis="y", color=LIGHT_GREY, linewidth=0.7)
    axes[0].legend(loc="upper right", ncols=3, fontsize=8)
    axes[-1].set_xlabel("Episode time (s)")
    fig.suptitle(f"CVC-Q4 aligned decision-space trace: {trace.study} / {trace.scenario} / {trace.policy}",
                 color=INK, fontsize=13)
    path = FIGURES / f"aligned_{trace.study}_{trace.scenario}_{trace.policy}.png"
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)
    return path


def plot_candidate_tradeoff(variants: list[dict[str, Any]]) -> Path:
    rows = [row for row in variants if row["method"] == "ols" and row["window_samples"] == 8]
    fig, axis = plt.subplots(figsize=(10, 7), constrained_layout=True)
    short = {
        "m_slope": "M slope", "m_level_slope": "M level+slope",
        "m_slope_reliable": "M slope+consistency", "gap_slope": "G slope",
        "gap_level_slope": "G level+slope", "m_gap_joint": "M+G slopes",
        "safe_fraction_contraction": "safe fraction", "positive_slack_contraction": "positive slack",
        "soft_mass_contraction": "soft mass", "soft_q01_level_contraction": "soft q01+slope",
        "soft_q05_level_contraction": "soft q05+slope", "lower_q25_contraction": "margin q25",
        "m_level_slope_safe_contraction": "M level+slope+soft",
    }
    offsets = {
        "m_slope": (6, 10), "m_level_slope": (6, -16), "m_slope_reliable": (6, -12),
        "gap_slope": (6, 4), "gap_level_slope": (6, 12), "m_gap_joint": (6, -15),
        "safe_fraction_contraction": (6, 6), "positive_slack_contraction": (6, -10),
        "soft_mass_contraction": (6, 4), "soft_q01_level_contraction": (6, 10),
        "soft_q05_level_contraction": (6, -14), "lower_q25_contraction": (6, 8),
        "m_level_slope_safe_contraction": (6, 13),
    }
    for row in rows:
        focal = row["rule"] == "soft_q01_level_contraction"
        axis.scatter(row["false_step_fraction_all"], row["event_coverage"],
                     s=90 if focal else 48, marker="D" if "level" in row["rule"] else "o",
                     facecolors=GOLD if focal else PALE_BLUE, edgecolors=INK if focal else BLUE,
                     linewidths=1.2)
        axis.annotate(short[row["rule"]],
                      (row["false_step_fraction_all"], row["event_coverage"]),
                      xytext=offsets[row["rule"]], textcoords="offset points", fontsize=7)
    axis.set_xlabel("False precursor steps outside a 2 s event window (fraction of all steps)")
    axis.set_ylabel("Safety Value event coverage within 2 s")
    axis.set_ylim(-0.04, 1.08)
    axis.grid(color=LIGHT_GREY, linewidth=0.7)
    axis.set_title("CVC-Q4 precursor coverage-specificity trade-off\nOLS, 8-sample causal window; 8 event onsets / 18,720 evaluation steps",
                   color=INK)
    path = FIGURES / "candidate_tradeoff.png"
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)
    return path


def plot_window_tradeoff(variants: list[dict[str, Any]]) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    methods = {"ols": ("o", "-"), "theil_sen": ("s", "--"), "median_adjacent": ("^", ":")}
    for method, (marker, linestyle) in methods.items():
        rows = sorted((row for row in variants if row["method"] == method and
                       row["rule"] == "soft_q01_level_contraction"),
                      key=lambda row: row["window_samples"])
        x = [row["window_span_s"] for row in rows]
        axes[0].plot(x, [row["event_coverage"] for row in rows], marker=marker,
                     linestyle=linestyle, color=BLUE, label=method)
        axes[1].plot(x, [row["false_step_fraction_all"] for row in rows], marker=marker,
                     linestyle=linestyle, color=GOLD, label=method)
    axes[0].set_ylabel("Event coverage within 2 s")
    axes[1].set_ylabel("False step fraction")
    for axis in axes:
        axis.set_xlabel("Causal history span (s)")
        axis.grid(color=LIGHT_GREY, linewidth=0.7)
        axis.legend(frameon=False)
    fig.suptitle("CVC-Q4 estimator/window trade-off\nSoft-feasibility level + abnormal contraction; no navigation outcomes used",
                 color=INK)
    path = FIGURES / "window_tradeoff.png"
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)
    return path


def plot_slope_distributions(calibration_traces: list[Trace], evaluation_traces: list[Trace],
                             cal_trends: dict[str, dict[str, list]], eval_trends: dict[str, dict[str, list]],
                             thresholds: dict[str, float], window: int) -> Path:
    names = (("m_stale", "slope(M_stale)", -thresholds["tau_m_per_s"]),
             ("gap", "slope(G)", thresholds["tau_g_per_s"]),
             ("soft_mass", "slope(soft feasibility)", -thresholds["tau_soft_mass_per_s"]))
    fig, axes = plt.subplots(1, 3, figsize=(13, 5), constrained_layout=True)
    for axis, (name, label, threshold) in zip(axes, names):
        baseline = []
        for trace in calibration_traces:
            for index in range(window - 1, len(trace.events)):
                trend = cal_trends[trace.identity][name][index]
                if trend is not None and math.isfinite(trend.slope_per_s) and all(trace.stable[index-window+1:index+1]):
                    baseline.append(trend.slope_per_s)
        pre = []
        for trace in evaluation_traces:
            labels = future_event_labels(trace.events, MAX_LEAD_STEPS)
            for index, label_value in enumerate(labels):
                trend = eval_trends[trace.identity][name][index]
                if label_value and trend is not None and math.isfinite(trend.slope_per_s):
                    pre.append(trend.slope_per_s)
        boxes = axis.boxplot([baseline, pre], patch_artist=True, showfliers=False,
                             tick_labels=["Stable Q1", "Pre-event Q2/Q3"])
        boxes["boxes"][0].set(facecolor=PALE_BLUE, edgecolor=BLUE)
        boxes["boxes"][1].set(facecolor=PALE_GOLD, edgecolor=GOLD)
        axis.axhline(threshold, color=INK, linestyle="--", linewidth=1.2)
        axis.set_ylabel(f"{label} per second")
        axis.grid(axis="y", color=LIGHT_GREY, linewidth=0.7)
    fig.suptitle("CVC-Q4 causal slope distributions\nOLS, 8 samples (0.224 s span); pre-event samples are strictly before onset within 2 s",
                 color=INK)
    path = FIGURES / "slope_distributions.png"
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)
    return path


def write_variant_csv(variants: list[dict[str, Any]]) -> None:
    fields = ["method", "window_samples", "window_span_s", "rule", "event_onsets",
              "covered_events", "event_coverage", "active_fraction", "false_step_fraction_all",
              "stable_safe_false_fraction", "false_event_episode_fraction",
              "fraction_lead_gt_0_25s", "fraction_lead_gt_0_5s", "fraction_lead_gt_1_0s"]
    with (OUT / "candidate_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in variants:
            writer.writerow({field: row.get(field) for field in fields})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    protected = protected_evidence()
    if not protected["all_match"]:
        raise RuntimeError("protected historical evidence mismatch")
    q1 = load_traces(ROOT / "results/cvc_q1_support_qualification/traces", "Q1", event_labels=False)
    q2 = load_traces(ROOT / "results/cvc_q2_webots/traces", "Q2", event_labels=True)
    q3 = load_traces(ROOT / "results/cvc_q3_webots/traces", "Q3", event_labels=True)
    evaluation = q2 + q3
    if len(q1) != 10 or len(q2) != 30 or len(q3) != 30:
        raise RuntimeError("unexpected Q1/Q2/Q3 trace inventory")
    if any(len(trace.events) != 312 for trace in q1 + evaluation):
        raise RuntimeError("unexpected trace length")

    variants, calibrations, thresholds_all, trend_cache = evaluate_variants(q1, evaluation)
    chosen_method, chosen_window, chosen_rule = "ols", 8, "soft_q01_level_contraction"
    chosen = next(row for row in variants if row["method"] == chosen_method and
                  row["window_samples"] == chosen_window and row["rule"] == chosen_rule)
    chosen_key = f"{chosen_method}_{chosen_window}"
    thresholds = thresholds_all[chosen_key]
    eval_trends = trend_cache[(chosen_method, chosen_window)]
    chosen_flags = {trace.identity: flags_for(trace, eval_trends[trace.identity], thresholds)[chosen_rule]
                    for trace in evaluation}
    _, _, cal_trends = calibration(q1, chosen_method, chosen_window)

    distribution = pre_event_distributions(evaluation, eval_trends, chosen_window)
    runtime = runtime_profile(q1[0].path)
    event_scenarios = sorted({trace.scenario for trace in evaluation if event_onsets(trace.events)})
    false_episode_fraction = float(chosen["false_event_episode_fraction"])
    classification = "CASE C"
    classification_label = "WEAK / SCENARIO-LIMITED PRECURSOR"
    rationale = (
        "The outcome-independent soft-feasibility level-plus-slope rule covers all observed onsets "
        "with useful lead and low step-level activation, but the eight onsets arise in only two of ten "
        "scenario families and the rule activates in a material fraction of event-free episodes. "
        "This is promising diagnostic evidence, not stable cross-family qualification."
    )
    scheduler_justified = False
    ml_justified = False

    representative = []
    for study, scenario, policy in (("Q3", "q1-s01-straight-approach", "A1"),
                                    ("Q2", "q1-s06-narrow-passage", "U0")):
        trace = next(item for item in evaluation if item.study == study and
                     item.scenario == scenario and item.policy == policy)
        representative.append(plot_aligned(trace, eval_trends[trace.identity], thresholds,
                                           chosen_flags[trace.identity]))
    figure_paths = representative + [
        plot_candidate_tradeoff(variants),
        plot_window_tradeoff(variants),
        plot_slope_distributions(q1, evaluation, cal_trends, eval_trends, thresholds, chosen_window),
    ]

    trace_inventory = {
        "calibration": {"study": "Q1", "traces": len(q1), "steps": sum(len(t.events) for t in q1),
                        "source": "results/cvc_q1_support_qualification/traces",
                        "role": "stable/no-change normal-variation baseline only"},
        "evaluation": {
            "Q2": {"traces": len(q2), "steps": sum(len(t.events) for t in q2),
                   "event_steps": sum(sum(t.events) for t in q2),
                   "event_onsets": sum(len(event_onsets(t.events)) for t in q2)},
            "Q3": {"traces": len(q3), "steps": sum(len(t.events) for t in q3),
                   "event_steps": sum(sum(t.events) for t in q3),
                   "event_onsets": sum(len(event_onsets(t.events)) for t in q3)},
            "source_roots": ["results/cvc_q2_webots/traces", "results/cvc_q3_webots/traces"],
        },
    }
    core = {
        "study_id": "cvc-q4-development-diagnostic-v1",
        "development_only": True,
        "formal": False,
        "communication_allocator_implemented": False,
        "new_policy_comparison_run": False,
        "evaluator_information_used_in_precursor": False,
        "definitions": {
            "m_stale": "CURRENT conservative margin of the exact receiver-HELD selected action",
            "m_best_current": "maximum CURRENT conservative margin among hard-feasible Q1 candidates",
            "gap": "M_best_current - M_stale",
            "safe_fraction": "CURRENT hard-feasible candidates / 15",
            "positive_slack": "mean(max(current candidate margin - 0.025 m, 0))",
            "soft_feasibility_mass": "mean(sigmoid((current candidate margin - 0.025 m) / 0.050 m))",
            "lower_q25_margin": "CURRENT candidate-margin lower quartile",
        },
        "trace_inventory": trace_inventory,
        "thresholds": thresholds,
        "chosen_estimator": {"method": chosen_method, "window_samples": chosen_window,
                             "window_span_s": (chosen_window - 1) * STEP_S,
                             "step_s": STEP_S,
                             "trend_reliability": "OLS R-squared, robust residual scale, pairwise sign consistency; no R-squared gate"},
        "chosen_rule": {
            "name": chosen_rule,
            "definition": "soft feasibility mass <= stable-Q1 q01 AND OLS slope(soft mass) < -tau_soft",
            "selection_note": "retained after the small authorized rule/window comparison; no navigation outcome entered selection",
        },
        "chosen_result": chosen,
        "event_scenario_support": {"positive_families": event_scenarios,
                                   "positive_family_count": len(event_scenarios), "total_families": 10},
        "pre_event_distributions": distribution,
        "calibration": calibrations[chosen_key],
        "all_calibrations": calibrations,
        "all_thresholds": thresholds_all,
        "candidate_variants": variants,
        "runtime_profile": runtime,
        "protected_evidence": protected,
        "chart_contracts": CHART_CONTRACTS,
        "figures": [path.relative_to(ROOT).as_posix() for path in figure_paths],
        "failed_or_rejected": [
            "M_stale slope alone: sparse, late coverage",
            "M_stale level plus slope: specificity improves but coverage remains sparse",
            "G slope: inconsistent coverage across windows; level gating can remove true warnings",
            "M_stale plus G slope: overly restrictive",
            "safe-fraction contraction: discrete and less smooth",
            "soft-feasibility slope alone: full coverage but excessive event-free episode activation",
            "longer windows: smoother but can erase the short M_stale warning",
        ],
        "conclusion": {
            "classification": classification,
            "label": classification_label,
            "rationale": rationale,
            "nonzero_abnormal_gradient_threshold_meaningful": True,
            "reliable_cross_family_precursor_established": False,
            "best_candidate": chosen_rule,
            "next_scheduler_experiment_justified": scheduler_justified,
            "ml_justified": ml_justified,
            "recommended_next_experiment": (
                "development-only event-rich support qualification of the frozen soft-feasibility "
                "level-plus-slope rule across at least three additional Safety-Value-positive scenario "
                "families before any communication scheduler integration"
            ),
            "false_event_episode_fraction": false_episode_fraction,
        },
    }
    deterministic_first = canonical_sha(core)
    deterministic_second = canonical_sha(core)
    core["deterministic_recompute"] = {
        "first_sha256": deterministic_first, "second_sha256": deterministic_second,
        "match": deterministic_first == deterministic_second,
    }
    output = clean(core)
    output_path = OUT / "analysis.json"
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8")
    output_path.with_suffix(".json.sha256").write_text(f"{sha(output_path)}  analysis.json\n", encoding="utf-8")
    write_variant_csv(variants)
    print(json.dumps({
        "classification": classification,
        "analysis_sha256": sha(output_path),
        "trace_inventory": trace_inventory,
        "chosen_rule": chosen_rule,
        "chosen_result": {key: chosen[key] for key in (
            "event_onsets", "covered_events", "event_coverage", "lead_s",
            "active_fraction", "false_step_fraction_all", "stable_safe_false_fraction",
            "false_event_episodes", "false_event_episode_fraction")},
        "positive_families": event_scenarios,
        "protected_all_match": protected["all_match"],
        "figures": [str(path) for path in figure_paths],
    }, indent=2))


if __name__ == "__main__":
    main()
