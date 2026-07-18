from __future__ import annotations

import unittest

from PIL import Image

from compression.spatial_allocation import (
    AllocationSearchSpace,
    build_tile_cache,
    iter_spatial_allocation_candidates,
    match_spatial_allocations_to_budgets,
)
from compression.tile_scoring import center_roi_scores
from scripts.m5e_calibration_common import CandidateEndpoint, FeasibleRange, common_interval, frozen_budgets
from scripts.run_m5e_calibration_dataset import _planned_configs
from simulator.m5e_config import primary_seed, primary_seed_indices


def _range(frame_id: str, method: str, minimum: int, maximum: int) -> FeasibleRange:
    endpoint = CandidateEndpoint(minimum, {"quality": 1})
    maximum_endpoint = CandidateEndpoint(maximum, {"quality": 95})
    return FeasibleRange(frame_id, "S1", "episode", 0, method, endpoint, maximum_endpoint, 95, "frame", "mask", "config")


class M5ECalibrationHelperTests(unittest.TestCase):
    def test_planned_calibration_protocol_has_16_disjoint_primary_episodes(self) -> None:
        configs = _planned_configs()
        self.assertEqual(len(configs), 16)
        self.assertEqual({config.split for config in configs}, {"calibration"})
        self.assertEqual(len({config.seed for config in configs}), 16)
        expected = {
            primary_seed("calibration", scenario_index, seed_index)
            for scenario_index in range(1, 9)
            for seed_index in primary_seed_indices("calibration")
        }
        self.assertEqual({config.seed for config in configs}, expected)
        formal = {primary_seed("formal", scenario_index, seed_index) for scenario_index in range(1, 9) for seed_index in primary_seed_indices("formal")}
        self.assertFalse(expected & formal)

    def test_common_interval_records_lower_and_upper_witnesses(self) -> None:
        ranges = [_range("a", "uniform", 120, 500), _range("b", "risk_roi", 150, 420), _range("c", "center_roi", 130, 390)]
        lower, upper, lower_witness, upper_witness = common_interval(ranges)
        self.assertEqual((lower, upper), (150, 390))
        self.assertEqual(lower_witness.frame_id, "b")
        self.assertEqual(upper_witness.frame_id, "c")

    def test_frozen_budget_rounding_is_strict_and_inside_interval(self) -> None:
        budgets = frozen_budgets(1000, 1101)
        self.assertEqual(budgets, {"severe": 1005, "low": 1025, "medium": 1050, "high": 1080})
        self.assertEqual(list(budgets.values()), sorted(budgets.values()))
        self.assertTrue(all(1000 <= value <= 1101 for value in budgets.values()))

    def test_too_narrow_interval_is_rejected_when_budget_labels_collapse(self) -> None:
        with self.assertRaises(ValueError):
            frozen_budgets(1000, 1001)

    def test_candidate_iterator_uses_the_same_frozen_space_as_matcher(self) -> None:
        image = Image.new("RGB", (160, 120), color=(48, 96, 144))
        cache = build_tile_cache(image, quality_min=1, quality_max=4)
        search = AllocationSearchSpace(
            background_quality_min=1,
            background_quality_max=3,
            enhancement_quality_min=2,
            enhancement_quality_max=4,
            top_k_min=1,
            top_k_max=2,
        )
        scores = center_roi_scores((80.0, 60.0))
        candidates = list(iter_spatial_allocation_candidates(scores, cache, search))
        target = max(total for total, _ in candidates)
        match = match_spatial_allocations_to_budgets(scores, cache, (target,), search)[0]
        self.assertEqual(match.candidate_count, len(candidates))
        self.assertEqual(match.actual_total_bytes, target)


if __name__ == "__main__":
    unittest.main()
