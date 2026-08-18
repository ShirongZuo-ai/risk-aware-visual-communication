"""Analyze continuous CVC-P5 held-versus-current timing diagnostics."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cvc_p5_diagnostic.json"
RESULTS = ROOT / "results" / "cvc_p5_diagnostic"
P4_RESULTS = ROOT / "results" / "cvc_p4_webots" / "matrix_summary.json"
P4_ANALYSIS = ROOT / "results" / "cvc_p4_webots" / "development_analysis.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def cumulative_quantile_step(values: list[float], probability: float) -> int | None:
    if not 0.0 < probability < 1.0 or any(value < 0 or not math.isfinite(value) for value in values):
        raise ValueError("invalid cumulative signal")
    total = sum(values)
    if total <= 0:
        return None
    target, running = probability * total, 0.0
    for step, value in enumerate(values):
        running += value
        if running >= target:
            return step
    return len(values) - 1


def lagged_correlation(risk: list[float], signal: list[float], max_lag: int) -> dict:
    if len(risk) != len(signal) or max_lag < 0:
        raise ValueError("invalid cross-correlation input")
    rows = []
    x_all, y_all = np.asarray(risk, dtype=float), np.asarray(signal, dtype=float)
    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            x, y = x_all[:-lag], y_all[lag:]
        elif lag < 0:
            x, y = x_all[-lag:], y_all[:lag]
        else:
            x, y = x_all, y_all
        if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
            correlation = None
        else:
            correlation = float(np.corrcoef(x, y)[0, 1])
        rows.append({"lag_steps": lag, "correlation": correlation})
    finite = [row for row in rows if row["correlation"] is not None and math.isfinite(row["correlation"])]
    peak = max(finite, key=lambda row: (row["correlation"], -abs(row["lag_steps"]))) if finite else None
    return {"peak": peak, "series": rows,
            "lag_sign_convention": "positive lag means the novelty/control signal occurs after risk"}


def timing_category(trigger: int | None, q25: int | None, q75: int | None) -> str:
    if trigger is None or q25 is None or q75 is None:
        return "undefined"
    if trigger < q25:
        return "before"
    if trigger <= q75:
        return "during"
    return "after"


def top_fraction_share(values: list[float], fraction: float = 0.1) -> float | None:
    total = sum(values)
    if total <= 0:
        return None
    count = max(1, math.ceil(len(values) * fraction))
    return sum(sorted(values, reverse=True)[:count]) / total


def first_crossing(rows: list[dict], key: str, threshold: float = 0.14) -> int | None:
    previous = None
    for row in rows:
        current = float(row["sender"][key])
        if previous is not None and previous < threshold <= current:
            return row["step"]
        previous = current
    return None


def signal_summary(values: list[float], quantiles: list[float]) -> dict:
    peak_value = max(values)
    return {
        "cumulative_steps": {str(value): cumulative_quantile_step(values, value) for value in quantiles},
        "peak_step": values.index(peak_value), "peak_value": peak_value,
        "median_value": statistics.median(values), "mean_value": statistics.mean(values),
        "top_10_percent_signal_share": top_fraction_share(values), "total_signal": sum(values),
    }


def median_summary(values: list[float]) -> dict:
    finite_values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return {
        "values": finite_values,
        "median": statistics.median(finite_values) if finite_values else None,
        "minimum": min(finite_values) if finite_values else None,
        "maximum": max(finite_values) if finite_values else None,
    }


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    replay = json.loads((RESULTS / "replay_summary.json").read_text(encoding="utf-8"))
    p4_matrix = json.loads(P4_RESULTS.read_text(encoding="utf-8"))
    p4_analysis = json.loads(P4_ANALYSIS.read_text(encoding="utf-8"))
    p4_runs = {(row["scenario"], row["policy"]): row for row in p4_matrix["runs"]}
    quantiles = [float(value) for value in config["cumulative_signal_quantiles"]]
    episode_rows = []
    representative = {}
    continuous_paths = []
    for path in sorted((RESULTS / "traces").glob("diagnostic__*.jsonl")):
        _, scenario, policy = path.stem.split("__")
        rows = read_jsonl(path)
        continuous_paths.append(str(path.relative_to(ROOT)))
        signals = {
            "visual_mae": [row["counterfactual"]["visual"]["pixel_mae"] for row in rows],
            "visual_rmse": [row["counterfactual"]["visual"]["pixel_rmse"] for row in rows],
            "structural_difference": [row["counterfactual"]["visual"]["structural_difference"] for row in rows],
            "changed_pixel_fraction": [row["counterfactual"]["visual"]["changed_pixel_fraction"] for row in rows],
            "perception_combined": [row["counterfactual"]["perception"]["combined_l2"] for row in rows],
            "delta_bearing": [row["counterfactual"]["perception"]["delta_bearing"] for row in rows],
            "delta_proximity": [row["counterfactual"]["perception"]["delta_proximity"] for row in rows],
            "delta_confidence": [row["counterfactual"]["perception"]["delta_confidence"] for row in rows],
            "control_l2": [row["counterfactual"]["control"]["control_l2"] for row in rows],
            "forward_speed_delta_abs": [abs(row["counterfactual"]["control"]["forward_speed_delta"]) for row in rows],
            "steering_delta_abs": [abs(row["counterfactual"]["control"]["steering_delta"]) for row in rows],
        }
        summaries = {name: signal_summary(values, quantiles) for name, values in signals.items()}
        r0_trigger, r1_trigger = first_crossing(rows, "r0"), first_crossing(rows, "r1")
        actual_adaptive = p4_runs[(scenario, policy)]["adaptive_step"]
        control_q25 = summaries["control_l2"]["cumulative_steps"]["0.25"]
        visual_q25 = summaries["visual_mae"]["cumulative_steps"]["0.25"]
        perception_q25 = summaries["perception_combined"]["cumulative_steps"]["0.25"]
        def values_at(step: int | None) -> dict:
            if step is None:
                return {name: None for name in signals}
            values = {name: series[step] for name, series in signals.items()}
            values.update({
                "forward_speed_delta": rows[step]["counterfactual"]["control"]["forward_speed_delta"],
                "steering_delta": rows[step]["counterfactual"]["control"]["steering_delta"],
                "left_wheel_delta": rows[step]["counterfactual"]["control"]["left_delta"],
                "right_wheel_delta": rows[step]["counterfactual"]["control"]["right_delta"],
            })
            return values
        r1_values, r0_values, adaptive_values = values_at(r1_trigger), values_at(r0_trigger), values_at(actual_adaptive)
        visual_nontrivial = np.asarray(signals["visual_mae"]) > statistics.median(signals["visual_mae"])
        perception_zero = np.asarray(signals["perception_combined"]) <= 1e-12
        control_zero = np.asarray(signals["control_l2"]) <= 1e-12
        visual_count = int(np.sum(visual_nontrivial))
        perception_nonzero = np.asarray(signals["perception_combined"]) > 1e-12
        row = {
            "scenario": scenario, "policy": policy, "steps": len(rows),
            "r0_trigger_step": r0_trigger, "r1_trigger_step": r1_trigger,
            "r1_minus_r0_prediction_lead_steps": (r0_trigger - r1_trigger
                                                   if r0_trigger is not None and r1_trigger is not None else None),
            "actual_adaptive_step": actual_adaptive, "actual_send_steps": p4_runs[(scenario, policy)]["send_steps"],
            "signals": summaries, "values_at_r0_trigger": r0_values,
            "values_at_r1_trigger": r1_values, "values_at_actual_adaptive": adaptive_values,
            "r1_to_visual_q25_steps": visual_q25 - r1_trigger if visual_q25 is not None and r1_trigger is not None else None,
            "r1_to_perception_q25_steps": (perception_q25 - r1_trigger
                                           if perception_q25 is not None and r1_trigger is not None else None),
            "r1_to_control_q25_steps": control_q25 - r1_trigger if control_q25 is not None and r1_trigger is not None else None,
            "r0_to_visual_q25_steps": visual_q25 - r0_trigger if visual_q25 is not None and r0_trigger is not None else None,
            "r0_to_perception_q25_steps": (perception_q25 - r0_trigger
                                           if perception_q25 is not None and r0_trigger is not None else None),
            "r0_to_control_q25_steps": control_q25 - r0_trigger if control_q25 is not None and r0_trigger is not None else None,
            "r1_visual_category": timing_category(r1_trigger, visual_q25,
                                                   summaries["visual_mae"]["cumulative_steps"]["0.75"]),
            "r1_perception_category": timing_category(r1_trigger, perception_q25,
                                                       summaries["perception_combined"]["cumulative_steps"]["0.75"]),
            "r1_control_category": timing_category(r1_trigger, control_q25,
                                                    summaries["control_l2"]["cumulative_steps"]["0.75"]),
            "control_peak_after_actual_adaptive": summaries["control_l2"]["peak_step"] > actual_adaptive,
            "control_trigger_to_peak_steps": (summaries["control_l2"]["peak_step"] - r1_trigger
                                              if r1_trigger is not None else None),
            "control_at_r1_to_peak_ratio": (r1_values["control_l2"] / summaries["control_l2"]["peak_value"]
                                            if r1_trigger is not None and summaries["control_l2"]["peak_value"] > 0 else None),
            "visual_to_perception_bottleneck_fraction": (float(np.sum(visual_nontrivial & perception_zero)) / visual_count
                                                         if visual_count else None),
            "perception_to_control_bottleneck_fraction": (float(np.sum(perception_nonzero & control_zero))
                                                          / int(np.sum(perception_nonzero)) if np.any(perception_nonzero) else None),
            "cross_correlation": {
                "r0_visual": lagged_correlation([r["sender"]["r0"] for r in rows], signals["visual_mae"],
                                                int(config["cross_correlation_max_lag_steps"])),
                "r1_visual": lagged_correlation([r["sender"]["r1"] for r in rows], signals["visual_mae"],
                                                int(config["cross_correlation_max_lag_steps"])),
                "r0_control": lagged_correlation([r["sender"]["r0"] for r in rows], signals["control_l2"],
                                                 int(config["cross_correlation_max_lag_steps"])),
                "r1_control": lagged_correlation([r["sender"]["r1"] for r in rows], signals["control_l2"],
                                                 int(config["cross_correlation_max_lag_steps"])),
            },
            "task_success": (not p4_runs[(scenario, policy)]["collision"]
                             and p4_runs[(scenario, policy)]["forward_progress_m"] >= 0.5),
            "minimum_clearance_m": p4_runs[(scenario, policy)]["min_clearance_m"],
            "forward_progress_m": p4_runs[(scenario, policy)]["forward_progress_m"],
        }
        episode_rows.append(row)
        if scenario in config["representative_scenarios_frozen"] and policy == "A1":
            key_steps = sorted(set(step for step in (
                0, r1_trigger, r0_trigger, visual_q25, perception_q25, control_q25,
                summaries["visual_mae"]["peak_step"], summaries["perception_combined"]["peak_step"],
                summaries["control_l2"]["peak_step"], actual_adaptive, 218
            ) if step is not None))
            representative[scenario] = [{
                "step": step, "r0": rows[step]["sender"]["r0"], "r1": rows[step]["sender"]["r1"],
                "visual_mae": signals["visual_mae"][step],
                "perception_combined": signals["perception_combined"][step],
                "control_l2": signals["control_l2"][step],
                "forward_speed_delta": rows[step]["counterfactual"]["control"]["forward_speed_delta"],
                "steering_delta": rows[step]["counterfactual"]["control"]["steering_delta"],
                "clearance_m": rows[step]["evaluator"]["clearance_m"],
                "actual_transmission": rows[step]["communication"]["transmitted"],
            } for step in key_steps]

    a1_rows = [row for row in episode_rows if row["policy"] == "A1"]
    def finite(field: str) -> list[float]:
        return [float(row[field]) for row in a1_rows if row[field] is not None]

    trigger_metrics = ("visual_mae", "visual_rmse", "structural_difference", "changed_pixel_fraction",
                       "perception_combined", "delta_bearing", "delta_proximity", "delta_confidence",
                       "control_l2", "forward_speed_delta", "steering_delta")
    aggregate = {
        "a1_episode_count": len(a1_rows),
        "r1_timing_categories": {
            signal: {category: sum(row[f"r1_{signal}_category"] == category for row in a1_rows)
                     for category in ("before", "during", "after", "undefined")}
            for signal in ("visual", "perception", "control")
        },
        "r1_to_visual_q25_steps": {"values": finite("r1_to_visual_q25_steps"),
                                    "median": statistics.median(finite("r1_to_visual_q25_steps"))},
        "r1_to_perception_q25_steps": {"values": finite("r1_to_perception_q25_steps"),
                                        "median": statistics.median(finite("r1_to_perception_q25_steps"))},
        "r1_to_control_q25_steps": {"values": finite("r1_to_control_q25_steps"),
                                     "median": statistics.median(finite("r1_to_control_q25_steps"))},
        "r0_to_visual_q25_steps": median_summary(finite("r0_to_visual_q25_steps")),
        "r0_to_perception_q25_steps": median_summary(finite("r0_to_perception_q25_steps")),
        "r0_to_control_q25_steps": median_summary(finite("r0_to_control_q25_steps")),
        "r1_minus_r0_prediction_lead_steps": median_summary(finite("r1_minus_r0_prediction_lead_steps")),
        "values_at_r1_trigger": {
            metric: median_summary([row["values_at_r1_trigger"][metric] for row in a1_rows])
            for metric in trigger_metrics
        },
        "values_at_r0_trigger": {
            metric: median_summary([row["values_at_r0_trigger"][metric] for row in a1_rows])
            for metric in trigger_metrics
        },
        "values_at_a1_adaptive_transmission": {
            metric: median_summary([row["values_at_actual_adaptive"][metric] for row in a1_rows])
            for metric in trigger_metrics
        },
        "control_at_r1_to_peak_ratio": {"values": finite("control_at_r1_to_peak_ratio"),
                                         "median": statistics.median(finite("control_at_r1_to_peak_ratio"))},
        "r1_to_control_peak_steps": median_summary(finite("control_trigger_to_peak_steps")),
        "control_peak_after_adaptive_count": sum(row["control_peak_after_actual_adaptive"] for row in a1_rows),
        "visual_to_perception_bottleneck_median": statistics.median(
            row["visual_to_perception_bottleneck_fraction"] for row in a1_rows
            if row["visual_to_perception_bottleneck_fraction"] is not None),
        "perception_to_control_bottleneck_median": statistics.median(
            row["perception_to_control_bottleneck_fraction"] for row in a1_rows
            if row["perception_to_control_bottleneck_fraction"] is not None),
        "task_successes": sum(row["task_success"] for row in a1_rows),
        "mean_forward_progress_m": statistics.mean(row["forward_progress_m"] for row in a1_rows),
        "mean_minimum_clearance_m": statistics.mean(row["minimum_clearance_m"] for row in a1_rows),
    }
    a0_p4 = [row for row in p4_matrix["runs"] if row["policy"] == "A0"]
    aggregate["a0_task_successes"] = sum((not row["collision"]) and row["forward_progress_m"] >= 0.5 for row in a0_p4)
    aggregate["a0_mean_forward_progress_m"] = statistics.mean(row["forward_progress_m"] for row in a0_p4)
    aggregate["a0_mean_minimum_clearance_m"] = statistics.mean(row["min_clearance_m"] for row in a0_p4)
    a0_rows = [row for row in episode_rows if row["policy"] == "A0"]
    aggregate["a0_values_at_adaptive_transmission"] = {
        metric: median_summary([row["values_at_actual_adaptive"][metric] for row in a0_rows])
        for metric in trigger_metrics
    }
    paired = {(row["scenario"], row["policy"]): row for row in episode_rows}
    clearance_deltas = [paired[(scenario, "A1")]["minimum_clearance_m"] -
                        paired[(scenario, "A0")]["minimum_clearance_m"]
                        for scenario in sorted({row["scenario"] for row in episode_rows})]
    aggregate["a1_minus_a0_minimum_clearance_m"] = median_summary(clearance_deltas)
    aggregate["a1_clearance_wins_losses_ties"] = {
        "wins": sum(value > 1e-12 for value in clearance_deltas),
        "losses": sum(value < -1e-12 for value in clearance_deltas),
        "ties": sum(abs(value) <= 1e-12 for value in clearance_deltas),
    }

    report = {
        "development_only": True, "formal": False, "new_allocator_implemented": False,
        "all_p4_reproduced": replay["all_p4_reproduced"],
        "actual_episode_wire_bytes": replay["actual_episode_wire_bytes"],
        "shadow_packets_charged": replay["shadow_packets_charged"],
        "definitions": config, "continuous_trace_paths": continuous_paths,
        "episode_timing": episode_rows, "aggregate_a1": aggregate,
        "representative_a1_traces": representative,
        "p4_outcome_classification": p4_analysis["classification"],
    }
    (RESULTS / "timing_analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_fields = ["scenario", "policy", "r0_trigger_step", "r1_trigger_step", "actual_adaptive_step",
                  "r1_minus_r0_prediction_lead_steps", "r1_to_visual_q25_steps",
                  "r1_to_perception_q25_steps", "r1_to_control_q25_steps",
                  "r1_visual_category", "r1_perception_category", "r1_control_category",
                  "control_trigger_to_peak_steps", "control_at_r1_to_peak_ratio",
                  "control_peak_after_actual_adaptive", "task_success", "minimum_clearance_m", "forward_progress_m"]
    with (RESULTS / "episode_timing.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in csv_fields} for row in episode_rows)
    print(json.dumps({"aggregate_a1": aggregate,
                      "r1_timing_categories": aggregate["r1_timing_categories"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
