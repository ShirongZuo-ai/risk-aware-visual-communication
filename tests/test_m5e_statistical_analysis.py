from __future__ import annotations

import unittest

import numpy as np

from scripts.m5e_statistical_analysis_common import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    METRIC_NAMES,
    aggregate_episode_metrics,
    analysis_role,
    build_paired_effects,
    parse_metric,
    scenario_bootstrap,
    sha256_json,
    stratified_paired_bootstrap,
    summarize_comparisons,
)


METHODS = ("uniform", "center_roi", "object_roi", "risk_roi")


def metric_row(method: str, snapshot: int, value: float = 10.0) -> dict[str, str]:
    row = {
        "scenario_id": "S1",
        "episode_id": "episode_1",
        "original_seed": "200100",
        "actual_seed": "200100",
        "replacement_index": "0",
        "method": method,
        "budget_label": "severe",
        "snapshot_index": str(snapshot),
    }
    for metric in METRIC_NAMES:
        row[metric] = repr(value + snapshot + METHODS.index(method))
    return row


def complete_episode_rows() -> list[dict[str, str]]:
    return [
        metric_row(method, snapshot)
        for method in METHODS
        for snapshot in range(4)
    ]


def primary_pair_rows(values_by_scenario: dict[str, list[float]]) -> list[dict[str, str]]:
    rows = []
    for scenario, values in values_by_scenario.items():
        for index, value in enumerate(values):
            rows.append(
                {
                    "scenario_id": scenario,
                    "episode_id": f"{scenario}_{index}",
                    "original_seed": str(200000 + index),
                    "actual_seed": str(200000 + index),
                    "replacement_index": "0",
                    "budget_label": "severe",
                    "baseline_method": "uniform",
                    "metric_name": "risk_weighted_psnr_db",
                    "metric_role": "primary",
                    "analysis_role": "primary",
                    "risk_episode_metric": repr(20.0 + value),
                    "baseline_episode_metric": "20.0",
                    "paired_difference": repr(value),
                    "risk_valid_frame_count": "4",
                    "baseline_valid_frame_count": "4",
                    "pair_valid": "true",
                    "invalid_reason": "",
                }
            )
    return rows


class M5EStatisticalAnalysisTests(unittest.TestCase):
    def test_episode_aggregation_uses_arithmetic_mean_of_four_frames(self) -> None:
        rows = aggregate_episode_metrics(complete_episode_rows())
        risk = next(
            row for row in rows
            if row["method"] == "risk_roi"
            and row["metric_name"] == "risk_weighted_psnr_db"
        )
        self.assertEqual(float(risk["episode_metric"]), 14.5)
        self.assertEqual(risk["frame_count"], "4")
        self.assertEqual(risk["valid_frame_count"], "4")

    def test_structural_empty_region_is_not_imputed(self) -> None:
        rows = complete_episode_rows()
        for row in rows:
            if row["method"] == "risk_roi":
                row["high_risk_psnr_db"] = "undefined"
        aggregated = aggregate_episode_metrics(rows)
        risk = next(
            row for row in aggregated
            if row["method"] == "risk_roi"
            and row["metric_name"] == "high_risk_psnr_db"
        )
        self.assertEqual(risk["episode_metric"], "undefined")
        self.assertEqual(risk["undefined_frame_count"], "4")

    def test_primary_undefined_frame_is_rejected(self) -> None:
        rows = complete_episode_rows()
        rows[0]["risk_weighted_psnr_db"] = "undefined"
        with self.assertRaises(ValueError):
            aggregate_episode_metrics(rows)

    def test_duplicate_snapshot_rejects_frame_level_pseudoreplication(self) -> None:
        rows = complete_episode_rows()
        duplicate = dict(rows[0])
        rows.append(duplicate)
        with self.assertRaises(ValueError):
            aggregate_episode_metrics(rows)

    def test_paired_matching_uses_same_episode_and_seed(self) -> None:
        episodes = aggregate_episode_metrics(complete_episode_rows())
        pairs = build_paired_effects(episodes)
        primary = [
            row for row in pairs
            if row["metric_name"] == "risk_weighted_psnr_db"
        ]
        self.assertEqual(len(primary), 3)
        self.assertTrue(all(row["pair_valid"] == "true" for row in primary))
        uniform = next(row for row in primary if row["baseline_method"] == "uniform")
        self.assertEqual(float(uniform["paired_difference"]), 3.0)

    def test_missing_method_pair_is_rejected(self) -> None:
        episodes = aggregate_episode_metrics(
            [row for row in complete_episode_rows() if row["method"] != "center_roi"]
        )
        with self.assertRaises(ValueError):
            build_paired_effects(episodes)

    def test_duplicate_episode_method_metric_is_rejected(self) -> None:
        episodes = aggregate_episode_metrics(complete_episode_rows())
        episodes.append(dict(episodes[0]))
        with self.assertRaises(ValueError):
            build_paired_effects(episodes)

    def test_stratified_bootstrap_is_fixed_seed_deterministic(self) -> None:
        values = {f"S{i}": [float(i + j) for j in range(8)] for i in range(1, 9)}
        rows = primary_pair_rows(values)
        first = stratified_paired_bootstrap(rows, iterations=100)
        second = stratified_paired_bootstrap(rows, iterations=100)
        np.testing.assert_array_equal(first, second)

    def test_stratified_bootstrap_preserves_equal_scenario_weighting(self) -> None:
        values = {f"S{i}": [float(i)] * 8 for i in range(1, 9)}
        samples = stratified_paired_bootstrap(primary_pair_rows(values), iterations=20)
        np.testing.assert_array_equal(samples, np.full(20, 4.5))

    def test_scenario_bootstrap_requires_eight_episodes(self) -> None:
        with self.assertRaises(ValueError):
            scenario_bootstrap([1.0] * 7)

    def test_scenario_bootstrap_ci_input_is_reproducible(self) -> None:
        first = scenario_bootstrap(range(8), iterations=100)
        second = scenario_bootstrap(range(8), iterations=100)
        self.assertEqual(
            tuple(np.quantile(first, [0.025, 0.975], method="linear")),
            tuple(np.quantile(second, [0.025, 0.975], method="linear")),
        )

    def test_ties_are_reported_without_positive_substitution(self) -> None:
        values = {f"S{i}": [0.0] * 8 for i in range(1, 9)}
        bootstrap, _, wins = summarize_comparisons(primary_pair_rows(values))
        self.assertEqual(bootstrap[0]["wins"], "0")
        self.assertEqual(bootstrap[0]["ties"], "64")
        self.assertEqual(bootstrap[0]["losses"], "0")
        self.assertEqual(wins[0]["tie_proportion"], "1.0")

    def test_nonfinite_numeric_metric_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_metric("nan")
        self.assertIsNone(parse_metric("undefined"))

    def test_primary_and_exploratory_tags_are_frozen(self) -> None:
        self.assertEqual(analysis_role("risk_weighted_psnr_db", "severe"), "primary")
        self.assertEqual(analysis_role("full_psnr_db", "severe"), "secondary_diagnostic")
        self.assertEqual(analysis_role("risk_weighted_psnr_db", "high"), "exploratory")

    def test_deterministic_json_hash_ignores_dictionary_order(self) -> None:
        self.assertEqual(
            sha256_json({"a": 1, "b": 2}),
            sha256_json({"b": 2, "a": 1}),
        )

    def test_bootstrap_constants_match_preregistration(self) -> None:
        self.assertEqual(BOOTSTRAP_SEED, 20260718)
        self.assertEqual(BOOTSTRAP_ITERATIONS, 10_000)


if __name__ == "__main__":
    unittest.main()
