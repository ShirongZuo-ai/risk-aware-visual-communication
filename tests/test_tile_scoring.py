import math
import unittest

from compression.tile_scoring import (
    FloatMask,
    ProjectedPolygon,
    TileScoreMap,
    center_roi_scores,
    object_roi_scores,
    risk_roi_scores,
    uniform_score_map,
)
from compression.tiled_jpeg import DEFAULT_M5_GRID


class TileScoreMapTests(unittest.TestCase):
    def test_validation_and_stable_ranking(self):
        score_map = TileScoreMap("test", DEFAULT_M5_GRID, (0.4, 0.8, 0.8) + (0.0,) * 45, "test")
        self.assertEqual(score_map.stable_ranked_tile_ids[:3], (1, 2, 0))
        self.assertEqual(score_map.nonzero_tile_count, 3)
        self.assertEqual(score_map.score(1), 0.8)
        self.assertAlmostEqual(score_map.mean_score, 2.0 / 48.0)
        with self.assertRaises(ValueError):
            TileScoreMap("test", DEFAULT_M5_GRID, (0.0,) * 47, "test")
        with self.assertRaises(ValueError):
            TileScoreMap("test", DEFAULT_M5_GRID, (math.nan,) + (0.0,) * 47, "test")
        with self.assertRaises(ValueError):
            TileScoreMap("test", DEFAULT_M5_GRID, (1.1,) + (0.0,) * 47, "test")

    def test_uniform_scores_are_diagnostics_only(self):
        score_map = uniform_score_map()
        self.assertEqual(score_map.method, "uniform")
        self.assertEqual(score_map.scores, (0.0,) * 48)


class CenterScoringTests(unittest.TestCase):
    def test_center_is_higher_than_corners(self):
        score_map = center_roi_scores((79.5, 59.5))
        self.assertGreater(score_map.score(27), score_map.score(0))

    def test_center_symmetry(self):
        score_map = center_roi_scores((79.5, 59.5))
        self.assertAlmostEqual(score_map.score(0), score_map.score(7))
        self.assertAlmostEqual(score_map.score(0), score_map.score(40))
        self.assertAlmostEqual(score_map.score(27), score_map.score(28))

    def test_center_depends_only_on_geometry(self):
        first = center_roi_scores((79.5, 59.5))
        second = center_roi_scores((79.5, 59.5))
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            center_roi_scores((math.inf, 59.5))


class ObjectScoringTests(unittest.TestCase):
    def test_polygon_coverage_and_partial_clipping(self):
        full = ProjectedPolygon("full", "fully_visible", ((0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)))
        partial = ProjectedPolygon("partial", "partially_visible", ((150.0, 0.0), (159.0, 0.0), (159.0, 20.0), (150.0, 20.0)))
        scores = object_roi_scores((full, partial))
        self.assertAlmostEqual(scores.score(0), 1.0)
        self.assertAlmostEqual(scores.score(7), 0.45)
        self.assertEqual(scores.score(1), 0.0)

    def test_invisible_and_empty_objects_do_not_score(self):
        obstacles = (
            ProjectedPolygon("outside", "outside_frustum", ((0, 0), (20, 0), (20, 20))),
            ProjectedPolygon("behind", "behind_camera", ((0, 0), (20, 0), (20, 20))),
            ProjectedPolygon("degenerate", "fully_visible", ()),
        )
        self.assertEqual(object_roi_scores(obstacles).nonzero_tile_count, 0)

    def test_object_score_is_order_and_risk_independent(self):
        left = ProjectedPolygon("a", "fully_visible", ((0, 0), (20, 0), (20, 20), (0, 20)))
        right = ProjectedPolygon("b", "fully_visible", ((20, 0), (40, 0), (40, 20), (20, 20)))
        self.assertEqual(object_roi_scores((left, right)), object_roi_scores((right, left)))
        with self.assertRaises(ValueError):
            object_roi_scores((left, left))


class RiskScoringTests(unittest.TestCase):
    def test_tile_max_preserves_small_high_risk_pixel(self):
        values = [0.0] * (160 * 120)
        values[19 * 160 + 19] = 0.37
        mask = FloatMask(160, 120, tuple(values))
        scores = risk_roi_scores(mask)
        self.assertEqual(scores.score(0), 0.37)
        self.assertEqual(scores.maximum_score, 0.37)

    def test_tile_boundary_assigns_pixel_once(self):
        values = [0.0] * (160 * 120)
        values[10 * 160 + 20] = 0.9
        scores = risk_roi_scores(FloatMask(160, 120, tuple(values)))
        self.assertEqual(scores.score(0), 0.0)
        self.assertEqual(scores.score(1), 0.9)

    def test_float_mask_rejects_schema_and_value_errors(self):
        with self.assertRaises(ValueError):
            FloatMask(160, 120, (0.0,) * 19199)
        with self.assertRaises(ValueError):
            FloatMask(160, 120, (1.1,) + (0.0,) * 19199)
        with self.assertRaises(ValueError):
            FloatMask(160, 120, (0.0,) * 19200, "column-major")
        with self.assertRaises(ValueError):
            risk_roi_scores(FloatMask(20, 20, (0.0,) * 400))

    def test_risk_does_not_mutate_input(self):
        values = tuple((index % 7) / 7.0 for index in range(160 * 120))
        mask = FloatMask(160, 120, values)
        risk_roi_scores(mask)
        self.assertEqual(mask.values, values)


if __name__ == "__main__":
    unittest.main()
