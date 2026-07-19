"""Shared episode-level analysis for the frozen M5E-D formal metric table."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable

import numpy as np

from scripts.m5e_dataset_common import sha256_file
from scripts.m5e_formal_evaluation_common import (
    EXPECTED_FORMAL_EPISODES,
    EXPECTED_FORMAL_FRAMES,
    EXPECTED_FORMAL_RECONSTRUCTIONS,
    EXPECTED_FROZEN_BUDGETS,
    FORMAL_BUDGET_LABELS,
    formal_paths,
    read_csv_rows,
)
from scripts.m5e_calibration_common import METHOD_ORDER
from simulator.m5e_config import SCENARIO_IDS


ANALYSIS_PROTOCOL_VERSION = "m5e-e-episode-statistics-v1"
BOOTSTRAP_SEED = 20260718
BOOTSTRAP_ITERATIONS = 10_000
PRIMARY_METHOD = "risk_roi"
BASELINE_METHODS = ("uniform", "center_roi", "object_roi")
PRIMARY_BUDGETS = ("severe", "low")
TIE_TOLERANCE = 0.0

METRIC_SPECS = (
    ("risk_weighted_psnr_db", "primary"),
    ("full_psnr_db", "secondary"),
    ("full_ssim", "secondary"),
    ("object_psnr_db", "secondary"),
    ("risk_support_psnr_db", "secondary"),
    ("high_risk_psnr_db", "secondary"),
    ("background_psnr_db", "secondary"),
    ("risk_weighted_mean_quality", "secondary"),
    ("actual_total_bytes", "secondary"),
    ("unused_bytes", "secondary"),
    ("utilization", "secondary"),
    ("total_tile_payload_bytes", "secondary"),
)
METRIC_NAMES = tuple(name for name, _ in METRIC_SPECS)
METRIC_ROLES = dict(METRIC_SPECS)

EPISODE_FIELDS = [
    "scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index",
    "method", "budget_label", "metric_name", "metric_role", "analysis_role",
    "frame_count", "valid_frame_count", "undefined_frame_count", "aggregation_rule",
    "episode_metric",
]
PAIR_FIELDS = [
    "scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index",
    "budget_label", "baseline_method", "metric_name", "metric_role", "analysis_role",
    "risk_episode_metric", "baseline_episode_metric", "paired_difference",
    "risk_valid_frame_count", "baseline_valid_frame_count", "pair_valid",
    "invalid_reason",
]
BOOTSTRAP_FIELDS = [
    "metric_name", "metric_role", "analysis_role", "budget_label", "baseline_method",
    "episode_count", "scenario_count", "observed_equal_scenario_mean_difference",
    "episode_median_difference", "episode_q1", "episode_q3", "ci_lower_95",
    "ci_upper_95", "episode_positive_proportion", "episode_tie_proportion",
    "bootstrap_positive_proportion", "wins", "ties", "losses",
    "bootstrap_seed", "bootstrap_iterations", "bootstrap_sample_sha256",
    "mean_actual_byte_difference", "actual_byte_fairness_limit",
    "actual_byte_fairness_passed", "leave_one_scenario_out_sign_reversal",
    "max_absolute_scenario_contribution", "single_scenario_dominance",
]
SCENARIO_FIELDS = [
    "scenario_id", "metric_name", "metric_role", "analysis_role", "budget_label",
    "baseline_method", "episode_count", "risk_mean", "baseline_mean",
    "paired_mean_difference", "paired_median_difference", "ci_lower_95",
    "ci_upper_95", "wins", "ties", "losses", "bootstrap_seed",
    "bootstrap_iterations",
]
WIN_FIELDS = [
    "scope", "scenario_id", "metric_name", "analysis_role", "budget_label",
    "baseline_method", "episode_count", "wins", "ties", "losses",
    "win_proportion", "tie_proportion",
]
FIGURE_INPUT_FIELDS = [
    "scenario_id", "episode_id", "original_seed", "budget_label", "baseline_method",
    "risk_weighted_difference", "full_psnr_difference", "background_psnr_difference",
    "risk_weighted_risk_value", "risk_weighted_baseline_value",
    "episode_mean_risk_sum", "episode_mean_trajectory_disagreement_m",
]


def analysis_paths(analysis_root: Path) -> dict[str, Path]:
    return {
        "root": analysis_root,
        "episode_metrics": analysis_root / "episode_level_metrics.csv",
        "paired_effects": analysis_root / "paired_effects.csv",
        "bootstrap_results": analysis_root / "bootstrap_results.csv",
        "scenario_diagnostics": analysis_root / "scenario_diagnostics.csv",
        "win_tie_loss": analysis_root / "win_tie_loss.csv",
        "figure_inputs": analysis_root / "figure_inputs.csv",
        "statistical_summary": analysis_root / "statistical_summary.json",
        "analysis_manifest": analysis_root / "analysis_manifest.json",
        "failure_log": analysis_root / "failure_log.json",
        "figure_manifest": analysis_root / "figure_manifest.json",
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _float_cell(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "undefined"
    return repr(float(value))


def parse_metric(value: str) -> float | None:
    if value in ("", "undefined"):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite metric is not allowed: {value!r}")
    return parsed


def analysis_role(metric_name: str, budget_label: str) -> str:
    if metric_name == "risk_weighted_psnr_db" and budget_label in PRIMARY_BUDGETS:
        return "primary"
    if budget_label in PRIMARY_BUDGETS:
        return "secondary_diagnostic"
    return "exploratory"


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_dataset_manifest(formal_root: Path) -> list[dict[str, str]]:
    path = formal_root / "logs" / "m5" / "m5e_dataset_manifest.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_formal_inputs(
    metric_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> None:
    if len(metric_rows) != EXPECTED_FORMAL_RECONSTRUCTIONS:
        raise ValueError("formal metric table must contain exactly 4096 rows")
    if len(manifest_rows) != EXPECTED_FORMAL_FRAMES:
        raise ValueError("formal dataset manifest must contain exactly 256 rows")
    frame_keys = {
        (row["frame_id"], row["method"], row["budget_label"]) for row in metric_rows
    }
    if len(frame_keys) != len(metric_rows):
        raise ValueError("formal metric table contains duplicate frame-method-budget rows")
    expected_frames = {
        (row["scenario_id"], row["episode_id"], row["original_seed"], row["snapshot_index"])
        for row in manifest_rows
    }
    if len(expected_frames) != EXPECTED_FORMAL_FRAMES:
        raise ValueError("formal manifest frame identities are duplicated")
    episodes: dict[tuple[str, str, str], set[int]] = {}
    for row in manifest_rows:
        if row["split"] != "formal" or row["valid_for_formal"] != "true":
            raise ValueError("non-formal or invalid frame entered M5E-E")
        if row["actual_future_trajectory_used"] != "false":
            raise ValueError("future actual trajectory leakage detected")
        key = (row["scenario_id"], row["episode_id"], row["original_seed"])
        episodes.setdefault(key, set()).add(int(row["snapshot_index"]))
    if len(episodes) != EXPECTED_FORMAL_EPISODES:
        raise ValueError("formal input must contain exactly 64 episode identities")
    if any(indices != {0, 1, 2, 3} for indices in episodes.values()):
        raise ValueError("every formal episode must contain snapshots 0..3 exactly once")
    scenario_counts = {
        scenario: sum(1 for key in episodes if key[0] == scenario)
        for scenario in SCENARIO_IDS
    }
    if set(scenario_counts.values()) != {8}:
        raise ValueError("formal episodes must preserve eight episodes per scenario")
    expected_result_keys = {
        (scenario, episode, seed, str(snapshot), method, budget)
        for scenario, episode, seed in episodes
        for snapshot in range(4)
        for method in METHOD_ORDER
        for budget in FORMAL_BUDGET_LABELS
    }
    actual_result_keys = {
        (
            row["scenario_id"], row["episode_id"], row["original_seed"],
            row["snapshot_index"], row["method"], row["budget_label"],
        )
        for row in metric_rows
    }
    if actual_result_keys != expected_result_keys:
        raise ValueError("formal method-budget-frame matrix is incomplete or mispaired")
    for row in metric_rows:
        if int(row["target_bytes"]) != EXPECTED_FROZEN_BUDGETS[row["budget_label"]]:
            raise ValueError("formal target differs from the M5E-C frozen budget")
        if row["actual_future_trajectory_used"] != "false":
            raise ValueError("formal metric row uses actual future trajectory")
        for metric_name in METRIC_NAMES:
            parse_metric(row[metric_name])


def aggregate_episode_metrics(
    metric_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in metric_rows:
        key = (
            row["scenario_id"], row["episode_id"], row["original_seed"],
            row["actual_seed"], row["replacement_index"], row["method"],
            row["budget_label"],
        )
        groups.setdefault(key, []).append(row)
    output: list[dict[str, str]] = []
    for key in sorted(
        groups,
        key=lambda value: (
            SCENARIO_IDS.index(value[0]), int(value[2]), METHOD_ORDER.index(value[5]),
            FORMAL_BUDGET_LABELS.index(value[6]),
        ),
    ):
        rows = sorted(groups[key], key=lambda row: int(row["snapshot_index"]))
        if [int(row["snapshot_index"]) for row in rows] != [0, 1, 2, 3]:
            raise ValueError("episode aggregation rejected incomplete or duplicate snapshots")
        for metric_name in METRIC_NAMES:
            values = [parse_metric(row[metric_name]) for row in rows]
            valid = [value for value in values if value is not None]
            if metric_name == "risk_weighted_psnr_db" and len(valid) != 4:
                raise ValueError("primary metric cannot use available-case frame aggregation")
            episode_value = float(np.mean(valid)) if valid else None
            rule = (
                "arithmetic_mean_of_four_frames"
                if len(valid) == 4
                else "arithmetic_mean_of_defined_structural_region_frames"
            )
            output.append(
                {
                    "scenario_id": key[0],
                    "episode_id": key[1],
                    "original_seed": key[2],
                    "actual_seed": key[3],
                    "replacement_index": key[4],
                    "method": key[5],
                    "budget_label": key[6],
                    "metric_name": metric_name,
                    "metric_role": METRIC_ROLES[metric_name],
                    "analysis_role": analysis_role(metric_name, key[6]),
                    "frame_count": "4",
                    "valid_frame_count": str(len(valid)),
                    "undefined_frame_count": str(4 - len(valid)),
                    "aggregation_rule": rule,
                    "episode_metric": _float_cell(episode_value),
                }
            )
    return output


def build_paired_effects(
    episode_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    index: dict[tuple[str, str, str, str], dict[str, dict[str, str]]] = {}
    for row in episode_rows:
        key = (row["episode_id"], row["budget_label"], row["metric_name"], row["scenario_id"])
        method_rows = index.setdefault(key, {})
        if row["method"] in method_rows:
            raise ValueError("duplicate episode-method metric row")
        method_rows[row["method"]] = row
    output: list[dict[str, str]] = []
    for key in sorted(
        index,
        key=lambda value: (
            SCENARIO_IDS.index(value[3]), value[0],
            FORMAL_BUDGET_LABELS.index(value[1]), METRIC_NAMES.index(value[2]),
        ),
    ):
        methods = index[key]
        if set(methods) != set(METHOD_ORDER):
            raise ValueError("missing method in episode-level matrix")
        risk = methods[PRIMARY_METHOD]
        for baseline in BASELINE_METHODS:
            base = methods[baseline]
            for identity_field in ("scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index"):
                if risk[identity_field] != base[identity_field]:
                    raise ValueError("cross-episode or cross-seed pairing rejected")
            risk_value = parse_metric(risk["episode_metric"])
            base_value = parse_metric(base["episode_metric"])
            valid = risk_value is not None and base_value is not None
            if risk["analysis_role"] == "primary" and not valid:
                raise ValueError("missing primary pair is not allowed")
            output.append(
                {
                    "scenario_id": risk["scenario_id"],
                    "episode_id": risk["episode_id"],
                    "original_seed": risk["original_seed"],
                    "actual_seed": risk["actual_seed"],
                    "replacement_index": risk["replacement_index"],
                    "budget_label": risk["budget_label"],
                    "baseline_method": baseline,
                    "metric_name": risk["metric_name"],
                    "metric_role": risk["metric_role"],
                    "analysis_role": risk["analysis_role"],
                    "risk_episode_metric": risk["episode_metric"],
                    "baseline_episode_metric": base["episode_metric"],
                    "paired_difference": _float_cell(
                        None if not valid else risk_value - base_value
                    ),
                    "risk_valid_frame_count": risk["valid_frame_count"],
                    "baseline_valid_frame_count": base["valid_frame_count"],
                    "pair_valid": "true" if valid else "false",
                    "invalid_reason": "" if valid else "undefined_structural_region_metric",
                }
            )
    pair_keys = [
        (
            row["scenario_id"], row["episode_id"], row["original_seed"],
            row["budget_label"], row["baseline_method"], row["metric_name"],
        )
        for row in output
    ]
    if len(pair_keys) != len(set(pair_keys)):
        raise ValueError("duplicate paired effect identity")
    return output


def _bootstrap_hash(samples: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(samples, dtype="<f8").tobytes()).hexdigest()


def stratified_paired_bootstrap(
    rows: list[dict[str, str]],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    if iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    strata: list[np.ndarray] = []
    for scenario_id in SCENARIO_IDS:
        values = [
            parse_metric(row["paired_difference"])
            for row in rows
            if row["scenario_id"] == scenario_id and row["pair_valid"] == "true"
        ]
        if len(values) != 8 or any(value is None for value in values):
            raise ValueError("stratified bootstrap requires eight valid episodes per scenario")
        strata.append(np.asarray(values, dtype=np.float64))
    rng = np.random.default_rng(seed)
    scenario_means = np.empty((iterations, len(strata)), dtype=np.float64)
    for index, values in enumerate(strata):
        sampled = rng.integers(0, len(values), size=(iterations, len(values)))
        scenario_means[:, index] = values[sampled].mean(axis=1)
    return scenario_means.mean(axis=1)


def scenario_bootstrap(
    values: Iterable[float],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    array = np.asarray(tuple(values), dtype=np.float64)
    if len(array) != 8:
        raise ValueError("scenario bootstrap requires eight episode values")
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(array), size=(iterations, len(array)))
    return array[sampled].mean(axis=1)


def _counts(values: np.ndarray) -> tuple[int, int, int]:
    wins = int(np.sum(values > TIE_TOLERANCE))
    losses = int(np.sum(values < -TIE_TOLERANCE))
    ties = int(len(values) - wins - losses)
    return wins, ties, losses


def _comparison_groups(pair_rows: list[dict[str, str]]) -> list[tuple[tuple[str, str, str], list[dict[str, str]]]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in pair_rows:
        groups.setdefault(
            (row["metric_name"], row["budget_label"], row["baseline_method"]), []
        ).append(row)
    order = sorted(
        groups,
        key=lambda key: (
            0 if analysis_role(key[0], key[1]) == "primary" else 1,
            METRIC_NAMES.index(key[0]), FORMAL_BUDGET_LABELS.index(key[1]),
            BASELINE_METHODS.index(key[2]),
        ),
    )
    return [(key, groups[key]) for key in order]


def summarize_comparisons(
    pair_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    bootstrap_rows: list[dict[str, str]] = []
    scenario_rows: list[dict[str, str]] = []
    win_rows: list[dict[str, str]] = []
    byte_lookup = {
        (row["scenario_id"], row["episode_id"], row["budget_label"], row["baseline_method"]):
        parse_metric(row["paired_difference"])
        for row in pair_rows
        if row["metric_name"] == "actual_total_bytes" and row["pair_valid"] == "true"
    }
    for (metric_name, budget_label, baseline), rows in _comparison_groups(pair_rows):
        valid = [row for row in rows if row["pair_valid"] == "true"]
        if not valid:
            continue
        values = np.asarray(
            [parse_metric(row["paired_difference"]) for row in valid],
            dtype=np.float64,
        )
        scenario_means = {
            scenario: float(np.mean([
                parse_metric(row["paired_difference"])
                for row in valid if row["scenario_id"] == scenario
            ]))
            for scenario in SCENARIO_IDS
            if any(row["scenario_id"] == scenario for row in valid)
        }
        if len(valid) == 64 and len(scenario_means) == 8:
            samples = stratified_paired_bootstrap(valid)
            observed = float(np.mean(tuple(scenario_means.values())))
            ci_lower, ci_upper = np.quantile(samples, [0.025, 0.975], method="linear")
            sample_hash = _bootstrap_hash(samples)
            bootstrap_positive = float(np.mean(samples > 0.0))
        else:
            observed = float(np.mean(values))
            ci_lower = ci_upper = math.nan
            sample_hash = ""
            bootstrap_positive = math.nan
        wins, ties, losses = _counts(values)
        byte_diffs = [
            byte_lookup[(row["scenario_id"], row["episode_id"], budget_label, baseline)]
            for row in valid
            if (row["scenario_id"], row["episode_id"], budget_label, baseline) in byte_lookup
        ]
        mean_byte_diff = float(np.mean(byte_diffs)) if byte_diffs else math.nan
        byte_limit = EXPECTED_FROZEN_BUDGETS[budget_label] * 0.005
        leave_one_reversal = False
        max_contribution = math.nan
        dominance = False
        if len(scenario_means) == 8:
            absolute_sum = sum(abs(value) for value in scenario_means.values())
            max_contribution = (
                max(abs(value) for value in scenario_means.values()) / absolute_sum
                if absolute_sum > 0.0 else 0.0
            )
            if observed > 0.0:
                leave_one_reversal = any(
                    float(np.mean([value for name, value in scenario_means.items() if name != removed])) <= 0.0
                    for removed in SCENARIO_IDS
                )
            dominance = leave_one_reversal or max_contribution > 0.5
        bootstrap_rows.append(
            {
                "metric_name": metric_name,
                "metric_role": METRIC_ROLES[metric_name],
                "analysis_role": analysis_role(metric_name, budget_label),
                "budget_label": budget_label,
                "baseline_method": baseline,
                "episode_count": str(len(valid)),
                "scenario_count": str(len(scenario_means)),
                "observed_equal_scenario_mean_difference": _float_cell(observed),
                "episode_median_difference": _float_cell(float(np.median(values))),
                "episode_q1": _float_cell(float(np.quantile(values, 0.25, method="linear"))),
                "episode_q3": _float_cell(float(np.quantile(values, 0.75, method="linear"))),
                "ci_lower_95": _float_cell(float(ci_lower)),
                "ci_upper_95": _float_cell(float(ci_upper)),
                "episode_positive_proportion": _float_cell(wins / len(values)),
                "episode_tie_proportion": _float_cell(ties / len(values)),
                "bootstrap_positive_proportion": _float_cell(bootstrap_positive),
                "wins": str(wins),
                "ties": str(ties),
                "losses": str(losses),
                "bootstrap_seed": str(BOOTSTRAP_SEED),
                "bootstrap_iterations": str(BOOTSTRAP_ITERATIONS),
                "bootstrap_sample_sha256": sample_hash,
                "mean_actual_byte_difference": _float_cell(mean_byte_diff),
                "actual_byte_fairness_limit": _float_cell(byte_limit),
                "actual_byte_fairness_passed": (
                    "true" if math.isfinite(mean_byte_diff) and abs(mean_byte_diff) <= byte_limit else "false"
                ),
                "leave_one_scenario_out_sign_reversal": str(leave_one_reversal).lower(),
                "max_absolute_scenario_contribution": _float_cell(max_contribution),
                "single_scenario_dominance": str(dominance).lower(),
            }
        )
        win_rows.append(
            {
                "scope": "overall",
                "scenario_id": "ALL",
                "metric_name": metric_name,
                "analysis_role": analysis_role(metric_name, budget_label),
                "budget_label": budget_label,
                "baseline_method": baseline,
                "episode_count": str(len(values)),
                "wins": str(wins),
                "ties": str(ties),
                "losses": str(losses),
                "win_proportion": _float_cell(wins / len(values)),
                "tie_proportion": _float_cell(ties / len(values)),
            }
        )
        for scenario in SCENARIO_IDS:
            subset = [row for row in valid if row["scenario_id"] == scenario]
            if not subset:
                continue
            deltas = np.asarray(
                [parse_metric(row["paired_difference"]) for row in subset],
                dtype=np.float64,
            )
            risk_values = np.asarray(
                [parse_metric(row["risk_episode_metric"]) for row in subset],
                dtype=np.float64,
            )
            baseline_values = np.asarray(
                [parse_metric(row["baseline_episode_metric"]) for row in subset],
                dtype=np.float64,
            )
            samples = scenario_bootstrap(deltas)
            lower, upper = np.quantile(samples, [0.025, 0.975], method="linear")
            sw, st, sl = _counts(deltas)
            scenario_rows.append(
                {
                    "scenario_id": scenario,
                    "metric_name": metric_name,
                    "metric_role": METRIC_ROLES[metric_name],
                    "analysis_role": analysis_role(metric_name, budget_label),
                    "budget_label": budget_label,
                    "baseline_method": baseline,
                    "episode_count": str(len(deltas)),
                    "risk_mean": _float_cell(float(np.mean(risk_values))),
                    "baseline_mean": _float_cell(float(np.mean(baseline_values))),
                    "paired_mean_difference": _float_cell(float(np.mean(deltas))),
                    "paired_median_difference": _float_cell(float(np.median(deltas))),
                    "ci_lower_95": _float_cell(float(lower)),
                    "ci_upper_95": _float_cell(float(upper)),
                    "wins": str(sw),
                    "ties": str(st),
                    "losses": str(sl),
                    "bootstrap_seed": str(BOOTSTRAP_SEED),
                    "bootstrap_iterations": str(BOOTSTRAP_ITERATIONS),
                }
            )
            win_rows.append(
                {
                    "scope": "scenario",
                    "scenario_id": scenario,
                    "metric_name": metric_name,
                    "analysis_role": analysis_role(metric_name, budget_label),
                    "budget_label": budget_label,
                    "baseline_method": baseline,
                    "episode_count": str(len(deltas)),
                    "wins": str(sw),
                    "ties": str(st),
                    "losses": str(sl),
                    "win_proportion": _float_cell(sw / len(deltas)),
                    "tie_proportion": _float_cell(st / len(deltas)),
                }
            )
    return bootstrap_rows, scenario_rows, win_rows


def build_figure_inputs(
    pair_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    episode_covariates: dict[tuple[str, str], dict[str, float]] = {}
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in manifest_rows:
        groups.setdefault((row["scenario_id"], row["episode_id"]), []).append(row)
    for key, rows in groups.items():
        episode_covariates[key] = {
            "risk": float(np.mean([float(row["combined_risk_sum"]) for row in rows])),
            "disagreement": float(np.mean([float(row["trajectory_disagreement_m"]) for row in rows])),
        }
    pair_index = {
        (
            row["scenario_id"], row["episode_id"], row["original_seed"],
            row["budget_label"], row["baseline_method"], row["metric_name"],
        ): row
        for row in pair_rows
    }
    output: list[dict[str, str]] = []
    for scenario in SCENARIO_IDS:
        episode_ids = sorted({
            row["episode_id"] for row in pair_rows
            if row["scenario_id"] == scenario and row["analysis_role"] == "primary"
        })
        for episode_id in episode_ids:
            seed = next(
                row["original_seed"] for row in pair_rows
                if row["scenario_id"] == scenario and row["episode_id"] == episode_id
            )
            for budget in PRIMARY_BUDGETS:
                for baseline in BASELINE_METHODS:
                    def get(metric: str) -> dict[str, str]:
                        return pair_index[(scenario, episode_id, seed, budget, baseline, metric)]
                    rw = get("risk_weighted_psnr_db")
                    full = get("full_psnr_db")
                    background = get("background_psnr_db")
                    covariates = episode_covariates[(scenario, episode_id)]
                    output.append(
                        {
                            "scenario_id": scenario,
                            "episode_id": episode_id,
                            "original_seed": seed,
                            "budget_label": budget,
                            "baseline_method": baseline,
                            "risk_weighted_difference": rw["paired_difference"],
                            "full_psnr_difference": full["paired_difference"],
                            "background_psnr_difference": background["paired_difference"],
                            "risk_weighted_risk_value": rw["risk_episode_metric"],
                            "risk_weighted_baseline_value": rw["baseline_episode_metric"],
                            "episode_mean_risk_sum": _float_cell(covariates["risk"]),
                            "episode_mean_trajectory_disagreement_m": _float_cell(covariates["disagreement"]),
                        }
                    )
    return output


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) < 2 or np.std(x) == 0.0 or np.std(y) == 0.0:
        return None
    return float(np.corrcoef(np.asarray(x), np.asarray(y))[0, 1])


def diagnostic_correlations(figure_inputs: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for budget in PRIMARY_BUDGETS:
        for baseline in BASELINE_METHODS:
            rows = [
                row for row in figure_inputs
                if row["budget_label"] == budget and row["baseline_method"] == baseline
            ]
            gain = [float(row["risk_weighted_difference"]) for row in rows]
            for covariate in (
                "episode_mean_risk_sum",
                "episode_mean_trajectory_disagreement_m",
            ):
                values = [float(row[covariate]) for row in rows]
                output.append(
                    {
                        "budget_label": budget,
                        "baseline_method": baseline,
                        "covariate": covariate,
                        "outcome": "risk_weighted_difference",
                        "episode_count": len(rows),
                        "pearson_correlation": _pearson(values, gain),
                        "role": "exploratory",
                    }
                )
    return output


def hypothesis_summary(
    bootstrap_rows: list[dict[str, str]],
    scenario_rows: list[dict[str, str]],
) -> dict[str, Any]:
    primary = {
        (row["budget_label"], row["baseline_method"]): row
        for row in bootstrap_rows if row["analysis_role"] == "primary"
    }
    h1_checks = []
    for budget in PRIMARY_BUDGETS:
        for baseline in BASELINE_METHODS:
            row = primary[(budget, baseline)]
            h1_checks.append(
                {
                    "budget_label": budget,
                    "baseline_method": baseline,
                    "mean_positive": float(row["observed_equal_scenario_mean_difference"]) > 0.0,
                    "interval_wholly_above_zero": float(row["ci_lower_95"]) > 0.0,
                }
            )
    scenario_index = {
        (row["scenario_id"], row["budget_label"], row["baseline_method"]): float(row["paired_mean_difference"])
        for row in scenario_rows
        if row["metric_name"] == "risk_weighted_psnr_db"
    }
    h2 = []
    for budget in PRIMARY_BUDGETS:
        focal = np.mean([
            scenario_index[(scenario, budget, "object_roi")] for scenario in ("S2", "S6")
        ])
        reference = np.mean([
            scenario_index[(scenario, budget, "object_roi")] for scenario in ("S1", "S8")
        ])
        h2.append(
            {
                "budget_label": budget,
                "focal_s2_s6_mean": float(focal),
                "reference_s1_s8_mean": float(reference),
                "contrast": float(focal - reference),
                "direction_supported": bool(focal - reference > 0.0),
            }
        )
    h3 = []
    for budget in PRIMARY_BUDGETS:
        reference = scenario_index[("S1", budget, "center_roi")]
        for scenario in ("S2", "S3", "S4"):
            contrast = scenario_index[(scenario, budget, "center_roi")] - reference
            h3.append(
                {
                    "budget_label": budget,
                    "scenario_id": scenario,
                    "scenario_difference": scenario_index[(scenario, budget, "center_roi")],
                    "s1_reference_difference": reference,
                    "contrast": contrast,
                    "direction_supported": bool(contrast > 0.0),
                }
            )
    return {
        "H1": {
            "verbatim": "At severe and low budgets, Risk ROI has higher continuous risk-weighted PSNR than Uniform, Center ROI, and Object ROI.",
            "checks": h1_checks,
            "fully_supported": all(
                item["mean_positive"] and item["interval_wholly_above_zero"]
                for item in h1_checks
            ),
        },
        "H2": {
            "verbatim": "Risk ROI's advantage over Object ROI is larger when visible object area and future-trajectory collision relevance disagree.",
            "operational_contrasts": h2,
            "direction_supported_at_both_primary_budgets": all(
                item["direction_supported"] for item in h2
            ),
        },
        "H3": {
            "verbatim": "Center ROI can be a strong baseline for straight motion with risk near the principal point, but its advantage should weaken for off-trajectory distractors and left/right turns.",
            "operational_contrasts": h3,
            "direction_supported_for_all_frozen_contrasts": all(
                item["direction_supported"] for item in h3
            ),
        },
    }


def _git_commit() -> str:
    executable = shutil.which("git")
    if executable is None:
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git" / "cmd" / "git.exe"
        if candidate.exists():
            executable = str(candidate)
    if executable is None:
        return "unavailable"
    result = subprocess.run(
        [executable, "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def software_versions() -> dict[str, str]:
    import matplotlib

    return {
        "python": os.sys.version.split()[0],
        "numpy": np.__version__,
        "matplotlib": matplotlib.__version__,
    }


def build_analysis(
    formal_root: Path,
) -> dict[str, Any]:
    source_paths = formal_paths(formal_root)
    metric_rows = read_csv_rows(source_paths["metrics_csv"])
    manifest_rows = _read_dataset_manifest(formal_root)
    validate_formal_inputs(metric_rows, manifest_rows)
    episodes = aggregate_episode_metrics(metric_rows)
    pairs = build_paired_effects(episodes)
    bootstrap, scenarios, wins = summarize_comparisons(pairs)
    figure_inputs = build_figure_inputs(pairs, manifest_rows)
    primary_pairs = [row for row in pairs if row["analysis_role"] == "primary"]
    if len(primary_pairs) != EXPECTED_FORMAL_EPISODES * len(PRIMARY_BUDGETS) * len(BASELINE_METHODS):
        raise ValueError("primary pair count must be 384")
    if any(row["pair_valid"] != "true" for row in primary_pairs):
        raise ValueError("all primary pairs must be valid")
    summary = {
        "milestone": "5E-E",
        "protocol_version": ANALYSIS_PROTOCOL_VERSION,
        "statistical_unit": "episode",
        "episode_count": EXPECTED_FORMAL_EPISODES,
        "frames_per_episode": 4,
        "primary_pair_count": len(primary_pairs),
        "primary_comparison_count": len(PRIMARY_BUDGETS) * len(BASELINE_METHODS),
        "bootstrap": {
            "procedure": "paired scenario-stratified bootstrap with equal-weight scenario means",
            "seed": BOOTSTRAP_SEED,
            "iterations": BOOTSTRAP_ITERATIONS,
            "confidence_interval": "percentile_95",
            "resampling_unit": "episode",
        },
        "hypotheses": hypothesis_summary(bootstrap, scenarios),
        "primary_results": [
            row for row in bootstrap if row["analysis_role"] == "primary"
        ],
        "diagnostic_correlations": diagnostic_correlations(figure_inputs),
        "multiple_comparisons": {
            "p_values_computed": False,
            "primary_comparisons_reported_separately": True,
            "other_metric_budget_scenario_results": "secondary_diagnostic_or_exploratory",
        },
        "empty_region_handling": (
            "undefined frame values remain undefined; episode high-risk metrics average only "
            "defined structural-region frames and record valid/undefined counts; no value is imputed"
        ),
        "scientific_boundary": [
            "offline image quality only",
            "risk is a heuristic proxy, not collision probability",
            "no perception, navigation, network, machine-learning, or closed-loop claim",
        ],
    }
    return {
        "metric_rows": metric_rows,
        "manifest_rows": manifest_rows,
        "episodes": episodes,
        "pairs": pairs,
        "bootstrap": bootstrap,
        "scenarios": scenarios,
        "wins": wins,
        "figure_inputs": figure_inputs,
        "summary": summary,
    }


def write_analysis_tables(
    formal_root: Path,
    analysis_root: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    paths = analysis_paths(analysis_root)
    if paths["analysis_manifest"].exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite analysis: {analysis_root}")
    analysis_root.mkdir(parents=True, exist_ok=True)
    built = build_analysis(formal_root)
    _write_csv(paths["episode_metrics"], EPISODE_FIELDS, built["episodes"])
    _write_csv(paths["paired_effects"], PAIR_FIELDS, built["pairs"])
    _write_csv(paths["bootstrap_results"], BOOTSTRAP_FIELDS, built["bootstrap"])
    _write_csv(paths["scenario_diagnostics"], SCENARIO_FIELDS, built["scenarios"])
    _write_csv(paths["win_tie_loss"], WIN_FIELDS, built["wins"])
    _write_csv(paths["figure_inputs"], FIGURE_INPUT_FIELDS, built["figure_inputs"])
    paths["statistical_summary"].write_text(
        json.dumps(built["summary"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_metrics = formal_paths(formal_root)["metrics_csv"]
    source_manifest = formal_root / "logs" / "m5" / "m5e_dataset_manifest.csv"
    failure_csv = formal_root / "logs" / "m5" / "m5e_formal_failure_log.csv"
    failure_rows = []
    if failure_csv.exists():
        with failure_csv.open(newline="", encoding="utf-8") as handle:
            failure_rows = list(csv.DictReader(handle))
    failure_log = {
        "formal_failure_record_count": len(failure_rows),
        "formal_failure_records": failure_rows,
        "excluded_formal_episode_count": 0,
        "missing_primary_pair_count": 0,
        "duplicate_pair_count": 0,
        "frame_level_inference_performed": False,
        "unfavorable_result_exclusion_performed": False,
    }
    paths["failure_log"].write_text(
        json.dumps(failure_log, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "milestone": "5E-E",
        "protocol_version": ANALYSIS_PROTOCOL_VERSION,
        "source_formal_metric_sha256": sha256_file(source_metrics),
        "source_formal_manifest_sha256": sha256_file(source_manifest),
        "source_formal_metadata_sha256": sha256_file(formal_paths(formal_root)["run_metadata"]),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "aggregation_rule": "mean four same-episode snapshots; structural empty regions retained as undefined",
        "overall_estimator": "equal-weight mean of eight scenario means",
        "software_versions": software_versions(),
        "git_commit": _git_commit(),
        "generated_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "formal_episode_count": EXPECTED_FORMAL_EPISODES,
        "formal_frame_count": EXPECTED_FORMAL_FRAMES,
        "formal_result_count": EXPECTED_FORMAL_RECONSTRUCTIONS,
        "primary_pair_count": 384,
        "frozen_budgets": EXPECTED_FROZEN_BUDGETS,
        "output_schema": {
            "episode_level_metrics": EPISODE_FIELDS,
            "paired_effects": PAIR_FIELDS,
            "bootstrap_results": BOOTSTRAP_FIELDS,
            "scenario_diagnostics": SCENARIO_FIELDS,
            "win_tie_loss": WIN_FIELDS,
            "figure_inputs": FIGURE_INPUT_FIELDS,
        },
    }
    paths["analysis_manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**built, "manifest": manifest, "failure_log": failure_log}
