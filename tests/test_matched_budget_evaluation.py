import unittest

import numpy as np

from evaluation.matched_budget_evaluation import tile_allocation_diagnostics


class MatchedBudgetEvaluationTests(unittest.TestCase):
    def test_tile_diagnostics_use_risk_mass_and_fixed_threshold(self):
        qualities = tuple([10, 90] + [20] * 46)
        tile_bytes = tuple([600, 800] + [650] * 46)
        mask = [0.0] * (160 * 120)
        mask[0] = 0.5
        mask[20] = 0.1
        diagnostics = tile_allocation_diagnostics(qualities, tile_bytes, tuple(mask))
        self.assertEqual(diagnostics.high_risk_tile_count, 1)
        self.assertEqual(diagnostics.high_risk_tile_mean_quality, 10.0)
        self.assertEqual(diagnostics.zero_risk_tile_count, 46)
        self.assertAlmostEqual(diagnostics.risk_weighted_mean_quality, (0.5 * 10 + 0.1 * 90) / 0.6)

    def test_tile_diagnostics_reject_bad_lengths_and_empty_risk(self):
        with self.assertRaises(ValueError):
            tile_allocation_diagnostics((1,) * 47, (1,) * 48, (0.1,) * (160 * 120))
        with self.assertRaises(ValueError):
            tile_allocation_diagnostics((1,) * 48, (1,) * 48, (0.0,) * (160 * 120))


if __name__ == "__main__":
    unittest.main()
