import unittest

from PIL import Image

from compression.budget_matcher import (
    InfeasibleBudgetError,
    BudgetCandidate,
    choose_best_under_budget,
    enumerate_uniform_quality_candidates,
    match_uniform_quality_to_budget,
)
from compression.tiled_jpeg import DEFAULT_M5_GRID, EncodedTiledFrame, encode_uniform_tiled_jpeg


def image():
    img = Image.new("RGB", (160, 120))
    pix = img.load()
    for y in range(120):
        for x in range(160):
            pix[x, y] = ((x + y) % 256, (x * 2) % 256, (y * 3) % 256)
    return img


class BudgetMatcherTests(unittest.TestCase):
    def test_match_never_exceeds_budget_and_prefers_largest_legal_bytes(self):
        img = image()
        candidates = enumerate_uniform_quality_candidates(img, DEFAULT_M5_GRID, 1, 10)
        target = candidates[5][0].actual_total_bytes
        match = match_uniform_quality_to_budget(img, target, DEFAULT_M5_GRID, 1, 10)
        legal = [candidate.actual_total_bytes for candidate, _ in candidates if candidate.actual_total_bytes <= target]
        self.assertLessEqual(match.actual_total_bytes, target)
        self.assertEqual(match.actual_total_bytes, max(legal))

    def test_exact_match_and_quality_boundaries(self):
        img = image()
        q1 = encode_uniform_tiled_jpeg(img, 1, DEFAULT_M5_GRID)
        q95 = encode_uniform_tiled_jpeg(img, 95, DEFAULT_M5_GRID)
        low = match_uniform_quality_to_budget(img, q1.total_bytes, DEFAULT_M5_GRID, 1, 95)
        high = match_uniform_quality_to_budget(img, q95.total_bytes, DEFAULT_M5_GRID, 1, 95)
        self.assertEqual(low.actual_total_bytes, q1.total_bytes)
        self.assertGreaterEqual(low.quality, 1)
        self.assertLessEqual(high.actual_total_bytes, q95.total_bytes)
        self.assertGreaterEqual(high.quality, 1)

    def test_tie_break_prefers_higher_quality(self):
        encoded = encode_uniform_tiled_jpeg(image(), 1, DEFAULT_M5_GRID)
        candidates = (
            (BudgetCandidate(quality=1, actual_total_bytes=100, tile_payload_bytes_sum=50, container_overhead_bytes=50), encoded),
            (BudgetCandidate(quality=2, actual_total_bytes=100, tile_payload_bytes_sum=50, container_overhead_bytes=50), encoded),
        )
        best, _ = choose_best_under_budget(candidates, 100)
        self.assertEqual(best.quality, 2)

    def test_infeasible_and_invalid_targets(self):
        img = image()
        minimum = encode_uniform_tiled_jpeg(img, 1, DEFAULT_M5_GRID).total_bytes
        with self.assertRaises(InfeasibleBudgetError):
            match_uniform_quality_to_budget(img, minimum - 1, DEFAULT_M5_GRID, 1, 95)
        for target in (0, -1, 1.5):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    match_uniform_quality_to_budget(img, target, DEFAULT_M5_GRID, 1, 95)

    def test_repeat_is_stable_and_candidates_are_exhaustive(self):
        img = image()
        target = encode_uniform_tiled_jpeg(img, 20, DEFAULT_M5_GRID).total_bytes
        first = match_uniform_quality_to_budget(img, target, DEFAULT_M5_GRID, 1, 20)
        second = match_uniform_quality_to_budget(img, target, DEFAULT_M5_GRID, 1, 20)
        self.assertEqual(first.quality, second.quality)
        self.assertEqual(first.encoded_frame.container_bytes, second.encoded_frame.container_bytes)
        self.assertEqual([candidate.quality for candidate in first.candidates], list(range(1, 21)))

    def test_invalid_quality_range(self):
        with self.assertRaises(ValueError):
            enumerate_uniform_quality_candidates(image(), DEFAULT_M5_GRID, 10, 1)
        with self.assertRaises(ValueError):
            enumerate_uniform_quality_candidates(image(), DEFAULT_M5_GRID, 0, 95)


if __name__ == "__main__":
    unittest.main()
