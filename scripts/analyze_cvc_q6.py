"""Analyze the complete CVC-Q6 causal chain without treating frames as trials."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


ROOT = Path(__file__).resolve().parents[1]
WEBOTS = ROOT / "results/cvc_q6_webots"
OUT = ROOT / "results/cvc_q6_analysis"
NEAR_M = 0.12


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def action_id(row: dict) -> str:
    planner = row["runtime"]["planner"]
    return str(planner["selected_action_id"])


def safety_class(row: dict) -> str:
    planner = row["runtime"]["planner"]
    return str(planner["selected_safety_class"])


def paired_trace_effect(a: list[dict], b: list[dict]) -> dict:
    if len(a) != len(b) or any(x["step"] != y["step"] for x, y in zip(a, b)):
        raise RuntimeError("unaligned paired traces")
    image = sum(x["receiver"]["image_sha256"] != y["receiver"]["image_sha256"] for x, y in zip(a, b))
    selected = sum(action_id(x) != action_id(y) for x, y in zip(a, b))
    classes = sum(safety_class(x) != safety_class(y) for x, y in zip(a, b))
    wheels = sum(abs(x["runtime"]["wheel_left_rad_s"] - y["runtime"]["wheel_left_rad_s"]) > 1e-9
                 or abs(x["runtime"]["wheel_right_rad_s"] - y["runtime"]["wheel_right_rad_s"]) > 1e-9
                 for x, y in zip(a, b))
    safe_set = sum(len(x["runtime"]["planner"]["safe_action_ids"])
                   != len(y["runtime"]["planner"]["safe_action_ids"])
                   for x, y in zip(a, b))
    margin = []
    for x, y in zip(a, b):
        left = float(x["runtime"]["planner"]["selected_conservative_margin_m"])
        right = float(y["runtime"]["planner"]["selected_conservative_margin_m"])
        if math.isfinite(left) and math.isfinite(right):
            margin.append(left - right)
    return {"receiver_image_hash_different_steps": image,
            "selected_action_different_steps": selected,
            "safety_class_different_steps": classes,
            "wheel_command_different_steps": wheels,
            "safe_set_different_steps": safe_set,
            "mean_conservative_margin_delta_m": mean(margin) if margin else 0.0,
            "mean_receiver_age_delta_ms": mean(x["receiver"]["image_age_ms"] - y["receiver"]["image_age_ms"]
                                                    for x, y in zip(a, b))}


def episode_metrics(trace: list[dict], summary: dict) -> dict:
    danger_steps = sum(row["evaluator"]["clearance_m"] <= NEAR_M for row in trace)
    sends = [row for row in trace if row["communication"]["transmitted"]]
    adaptive = next((row for row in sends if row["communication"]["packet_role"] == "adaptive"), None)
    return {
        "collision": bool(summary["collision"]), "min_clearance_m": summary["min_clearance_m"],
        "danger_steps": danger_steps, "danger_time_s": danger_steps * .032,
        "goal_progress_m": summary["goal_progress_m"], "task_success": summary["task_success"],
        "path_efficiency": summary["path_efficiency"], "adaptive_step": adaptive["step"],
        "adaptive_reason": adaptive["communication"]["reason"],
        "arm_step": next((row["policy_state"].get("arm_step") for row in trace
                          if row["policy_state"].get("arm_step") is not None), None),
        "precursor_steps": sum(bool(row["policy_state"].get("precursor_active")) for row in trace),
        "scheduler_deadline_miss_steps": sum(
            row["runtime_profile_ms"]["communication_decision_total"] > 32.0 for row in trace),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--control-variant")
    args = parser.parse_args()
    base = WEBOTS / args.variant
    matrix_path = base / "matrix_results.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    summaries = {(row["scenario"], row["policy"]): row for row in matrix["records"]}
    cells = sorted({cell for cell, _ in summaries})
    traces = {}
    for cell in cells:
        for policy in ("U0", "A0", "A1"):
            trace_variant = (args.control_variant if policy in ("U0", "A0") and args.control_variant
                             else args.variant)
            traces[cell, policy] = rows(WEBOTS / trace_variant / "traces"
                                       / f"{trace_variant}__{cell}__{policy}.jsonl")
    pairs = []
    family_rows: dict[str, list[dict]] = defaultdict(list)
    for cell in cells:
        metrics = {policy: episode_metrics(traces[cell, policy], summaries[cell, policy])
                   for policy in ("U0", "A0", "A1")}
        effect_a0 = paired_trace_effect(traces[cell, "A1"], traces[cell, "A0"])
        effect_u0 = paired_trace_effect(traces[cell, "A1"], traces[cell, "U0"])
        row = {
            "cell_id": cell, "family": summaries[cell, "A1"]["semantic"], "policy_metrics": metrics,
            "A1_minus_A0": {
                **effect_a0,
                "adaptive_timing_shift_steps": metrics["A1"]["adaptive_step"] - metrics["A0"]["adaptive_step"],
                "danger_steps_delta": metrics["A1"]["danger_steps"] - metrics["A0"]["danger_steps"],
                "min_clearance_delta_m": metrics["A1"]["min_clearance_m"] - metrics["A0"]["min_clearance_m"],
                "collision_delta": int(metrics["A1"]["collision"]) - int(metrics["A0"]["collision"]),
                "progress_delta_m": metrics["A1"]["goal_progress_m"] - metrics["A0"]["goal_progress_m"],
            },
            "A1_minus_U0": {
                **effect_u0,
                "adaptive_timing_shift_steps": metrics["A1"]["adaptive_step"] - metrics["U0"]["adaptive_step"],
                "danger_steps_delta": metrics["A1"]["danger_steps"] - metrics["U0"]["danger_steps"],
                "min_clearance_delta_m": metrics["A1"]["min_clearance_m"] - metrics["U0"]["min_clearance_m"],
                "collision_delta": int(metrics["A1"]["collision"]) - int(metrics["U0"]["collision"]),
                "progress_delta_m": metrics["A1"]["goal_progress_m"] - metrics["U0"]["goal_progress_m"],
            },
        }
        pairs.append(row); family_rows[row["family"]].append(row)

    def aggregate(subset: list[dict], comparator: str) -> dict:
        key = f"A1_minus_{comparator}"
        effects = [row[key] for row in subset]
        return {
            "cells": len(subset),
            "schedule_different_pairs": sum(e["adaptive_timing_shift_steps"] != 0 for e in effects),
            "median_timing_shift_steps": median(e["adaptive_timing_shift_steps"] for e in effects),
            "receiver_information_different_pairs": sum(e["receiver_image_hash_different_steps"] > 0 for e in effects),
            "planner_action_different_pairs": sum(e["selected_action_different_steps"] > 0 for e in effects),
            "wheel_command_different_pairs": sum(e["wheel_command_different_steps"] > 0 for e in effects),
            "mean_danger_steps_delta": mean(e["danger_steps_delta"] for e in effects),
            "danger_improved_tied_adverse": {
                "improved": sum(e["danger_steps_delta"] < 0 for e in effects),
                "tied": sum(e["danger_steps_delta"] == 0 for e in effects),
                "adverse": sum(e["danger_steps_delta"] > 0 for e in effects),
            },
            "mean_min_clearance_delta_m": mean(e["min_clearance_delta_m"] for e in effects),
            "collision_delta_total": sum(e["collision_delta"] for e in effects),
            "mean_progress_delta_m": mean(e["progress_delta_m"] for e in effects),
        }
    pooled = {comp: aggregate(pairs, comp) for comp in ("A0", "U0")}
    families = {name: {comp: aggregate(subset, comp) for comp in ("A0", "U0")}
                for name, subset in sorted(family_rows.items())}
    a0 = pooled["A0"]
    u0 = pooled["U0"]
    serious_adverse_families = [
        name for name, result in families.items()
        if result["U0"]["mean_danger_steps_delta"] > 0
        and result["U0"]["mean_min_clearance_delta_m"] < 0
    ]
    intervention_cells = sum(row["A1_minus_A0"]["adaptive_timing_shift_steps"] != 0 for row in pairs)
    control_false_spends = sum(
        row["cell_id"].endswith("c01") and row["A1_minus_A0"]["adaptive_timing_shift_steps"] != 0
        for row in pairs
    )
    deadline_miss_steps = sum(row["policy_metrics"]["A1"]["scheduler_deadline_miss_steps"] for row in pairs)
    strongest_baseline_nonadverse = (
        u0["mean_danger_steps_delta"] < 0
        and u0["mean_min_clearance_delta_m"] >= 0
        and u0["collision_delta_total"] <= 0
        and not serious_adverse_families
    )
    chain = {
        "send_timing": a0["schedule_different_pairs"] > 0,
        "receiver_information": a0["receiver_information_different_pairs"] > 0,
        "planner_control": a0["planner_action_different_pairs"] > 0 and a0["wheel_command_different_pairs"] > 0,
        "A0_safety_signal": a0["mean_danger_steps_delta"] < 0 and a0["collision_delta_total"] <= 0
                            and a0["mean_min_clearance_delta_m"] >= 0,
        "strongest_U0_baseline_nonadverse": strongest_baseline_nonadverse,
    }
    if all(chain.values()):
        classification = "Q6-A-CANDIDATE"
        failures = []
    else:
        failures = []
        if not chain["send_timing"]: failures.append("F1")
        if chain["send_timing"] and not chain["receiver_information"]: failures.append("F2")
        if chain["receiver_information"] and not chain["planner_control"]: failures.append("F3")
        if chain["planner_control"] and not chain["A0_safety_signal"]: failures.append("F4")
        if sum(row["policy_metrics"]["A1"]["adaptive_reason"].endswith("fallback") for row in pairs) >= len(pairs) / 2:
            failures.append("F6")
        if serious_adverse_families:
            failures.append("F9")
        if u0["mean_progress_delta_m"] < 0 and u0["mean_danger_steps_delta"] < 0:
            failures.append("F10")
        classification = "Q6-NEGATIVE-CHAIN-LOCALIZED"
    result = {
        "variant_id": args.variant, "development_only": True, "formal": False,
        "matrix_sha256": sha(matrix_path), "exact_matched_cost": matrix["all_exact_cost"],
        "mirror_integrity": matrix["all_mirrors_match"], "near_boundary_m": NEAR_M,
        "adaptive_reason_counts_A1": dict(Counter(row["policy_metrics"]["A1"]["adaptive_reason"] for row in pairs)),
        "pooled": pooled, "families": families, "causal_chain": chain,
        "serious_adverse_families_vs_U0": serious_adverse_families,
        "intervention_cells": intervention_cells, "control_false_spends": control_false_spends,
        "A1_scheduler_deadline_miss_steps": deadline_miss_steps,
        "classification": classification, "failure_classes": failures, "pairs": pairs,
        "frame_counts_are_mechanistic_only": True, "inferential_unit": "physical scenario cell",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.variant}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    path.with_suffix(".json.sha256").write_text(sha(path) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("variant_id", "exact_matched_cost", "pooled",
                                                   "causal_chain", "classification", "failure_classes")},
                     indent=2))


if __name__ == "__main__":
    main()
