import math
import unittest

from risk_map.risk_formulation import combine_risk_scores, compute_risk_score, spatial_score, temporal_score


class RiskFormulaTests(unittest.TestCase):
    def test_spatial_score_monotonic(self):
        near = spatial_score(0.1, 0.5)
        far = spatial_score(1.0, 0.5)
        self.assertGreater(near, far)
        self.assertEqual(spatial_score(0.0, 0.5), 1.0)
        self.assertEqual(spatial_score(-0.1, 0.5), 1.0)

    def test_temporal_score_monotonic(self):
        early = temporal_score(0.1, 1.0)
        late = temporal_score(2.0, 1.0)
        self.assertGreater(early, late)

    def test_compute_risk_uses_entry_time_when_available(self):
        with_entry = compute_risk_score(
            clearance_m=0.2,
            closest_time_s=1.5,
            first_entry_time_s=0.2,
            sigma_distance_m=0.5,
            tau_time_s=1.0,
        )
        no_entry = compute_risk_score(
            clearance_m=0.2,
            closest_time_s=1.5,
            first_entry_time_s=None,
            sigma_distance_m=0.5,
            tau_time_s=1.0,
        )
        self.assertAlmostEqual(with_entry.relevant_time_s, 0.2)
        self.assertAlmostEqual(no_entry.relevant_time_s, 1.5)
        self.assertGreater(with_entry.risk_score, no_entry.risk_score)

    def test_risk_range_and_invalid_inputs(self):
        result = compute_risk_score(
            clearance_m=-1.0,
            closest_time_s=0.0,
            first_entry_time_s=0.0,
            sigma_distance_m=0.5,
            tau_time_s=1.0,
        )
        self.assertGreaterEqual(result.risk_score, 0.0)
        self.assertLessEqual(result.risk_score, 1.0)
        for func, args in (
            (spatial_score, (1.0, 0.0)),
            (temporal_score, (-1.0, 1.0)),
            (temporal_score, (1.0, 0.0)),
            (combine_risk_scores, (math.nan, 0.5)),
            (combine_risk_scores, (1.2, 0.5)),
        ):
            with self.subTest(func=func.__name__, args=args):
                with self.assertRaises(ValueError):
                    func(*args)

    def test_combined_risk_is_max(self):
        self.assertAlmostEqual(combine_risk_scores(0.2, 0.7), 0.7)
        self.assertAlmostEqual(combine_risk_scores(0.8, 0.3), 0.8)


if __name__ == "__main__":
    unittest.main()
