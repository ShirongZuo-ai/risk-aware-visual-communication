import unittest

from PIL import Image

from compression.spatial_allocation import (
    AllocationSearchSpace,
    InfeasibleSpatialBudgetError,
    SpatialAllocationConfig,
    build_tile_cache,
    match_spatial_allocation_to_budget,
    match_spatial_allocations_to_budgets,
    qualities_for_config,
)
from compression.tile_scoring import TileScoreMap
from compression.tiled_jpeg import DEFAULT_M5_GRID, encode_rgb_frame_to_tiles


def image():
    result = Image.new("RGB", (160, 120))
    pixels = result.load()
    for y in range(120):
        for x in range(160):
            pixels[x, y] = ((x * 13 + y) % 256, (y * 17) % 256, (x + y * 3) % 256)
    return result


def score_map(values=None):
    return TileScoreMap("test", DEFAULT_M5_GRID, tuple(values or [index / 47.0 for index in range(48)]), "test")


class SpatialAllocationTests(unittest.TestCase):
    def setUp(self):
        self.space = AllocationSearchSpace(1, 4, 2, 5, 1, 4)
        self.cache = build_tile_cache(image(), quality_min=1, quality_max=5)

    def test_cache_matches_direct_tile_encoding(self):
        direct = encode_rgb_frame_to_tiles(image(), DEFAULT_M5_GRID, (3,) * 48)
        cached = self.cache.encode((3,) * 48)
        self.assertEqual(tuple(tile.jpeg_payload for tile in direct), tuple(tile.jpeg_payload for tile in cached.tiles))

    def test_quality_mapping_is_monotonic_and_stable(self):
        scores = [0.0] * 48
        scores[0] = scores[1] = 0.9
        scores[2] = 0.1
        mapped = qualities_for_config(score_map(scores), SpatialAllocationConfig(2, 5, 2))
        self.assertEqual(mapped[:3], (5, 5, 2))
        self.assertEqual(len(mapped), 48)

    def test_match_never_exceeds_budget_and_is_repeatable(self):
        all_high = self.cache.encode((5,) * 48)
        first = match_spatial_allocation_to_budget(score_map(), self.cache, all_high.total_bytes, self.space)
        second = match_spatial_allocation_to_budget(score_map(), self.cache, all_high.total_bytes, self.space)
        self.assertLessEqual(first.actual_total_bytes, all_high.total_bytes)
        self.assertEqual(first.qualities, second.qualities)
        self.assertEqual(first.container_bytes, second.container_bytes)

    def test_match_reports_all_candidates_and_feasible_count(self):
        target = self.cache.encode((4,) * 48).total_bytes
        match = match_spatial_allocation_to_budget(score_map(), self.cache, target, self.space)
        self.assertEqual(match.candidate_count, 40)
        self.assertGreater(match.feasible_candidate_count, 0)
        self.assertEqual(len(match.qualities), 48)

    def test_all_equal_scores_degrade_to_uniform_candidates(self):
        target = self.cache.encode((3,) * 48).total_bytes
        flat = score_map([0.0] * 48)
        match = match_spatial_allocation_to_budget(flat, self.cache, target, self.space)
        self.assertEqual(match.selected_config.top_k, 0)
        self.assertEqual(len(set(match.qualities)), 1)
        self.assertEqual(match.candidate_count, 5)

    def test_infeasible_budget_is_explicit(self):
        minimum = self.cache.encode((1,) * 48).total_bytes
        with self.assertRaises(InfeasibleSpatialBudgetError):
            match_spatial_allocation_to_budget(score_map(), self.cache, minimum - 1, self.space)

    def test_batch_matches_equal_individual_matches(self):
        targets = (self.cache.encode((2,) * 48).total_bytes, self.cache.encode((4,) * 48).total_bytes)
        batch = match_spatial_allocations_to_budgets(score_map(), self.cache, targets, self.space)
        singles = tuple(match_spatial_allocation_to_budget(score_map(), self.cache, target, self.space) for target in targets)
        self.assertEqual([item.actual_total_bytes for item in batch], [item.actual_total_bytes for item in singles])

    def test_invalid_cache_and_config_inputs_fail(self):
        with self.assertRaises(ValueError):
            qualities_for_config(score_map(), SpatialAllocationConfig(1, 5, 49))
        with self.assertRaises(ValueError):
            match_spatial_allocation_to_budget(score_map(), self.cache, 0, self.space)
        with self.assertRaises(ValueError):
            AllocationSearchSpace(4, 1, 2, 5, 1, 4)


if __name__ == "__main__":
    unittest.main()
