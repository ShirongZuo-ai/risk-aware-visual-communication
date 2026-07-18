import unittest

from compression.tile_scoring import FloatMask, ProjectedPolygon
from evaluation.region_masks import HIGH_RISK_THRESHOLD, build_evaluation_regions


def mask(values=None):
    values = values or [0.0] * (160 * 120)
    return FloatMask(160, 120, tuple(values))


class RegionMaskTests(unittest.TestCase):
    def test_polygon_union_overlap_and_order_independence(self):
        first = ProjectedPolygon("a", "fully_visible", ((0, 0), (20, 0), (20, 20), (0, 20)))
        second = ProjectedPolygon("b", "fully_visible", ((10, 0), (30, 0), (30, 20), (10, 20)))
        one = build_evaluation_regions(mask(), (first, second))
        two = build_evaluation_regions(mask(), (second, first))
        self.assertEqual(one.eligible_object_union, two.eligible_object_union)
        self.assertGreater(one.eligible_object_union.pixel_count, 400)
        self.assertLess(one.eligible_object_union.pixel_count, 800)

    def test_partial_and_invisible_filtering(self):
        partial = ProjectedPolygon("partial", "partially_visible", ((150, 100), (159, 100), (159, 119), (150, 119)))
        invisible = ProjectedPolygon("behind", "behind_camera", ((0, 0), (159, 0), (159, 119)))
        regions = build_evaluation_regions(mask(), (partial, invisible))
        self.assertEqual(regions.eligible_object_union.pixel_count, 200)

    def test_risk_support_high_risk_boundary_and_background(self):
        values = [0.0] * (160 * 120)
        values[0] = 0.1
        values[1] = HIGH_RISK_THRESHOLD
        polygon = ProjectedPolygon("a", "fully_visible", ((0, 0), (20, 0), (20, 20), (0, 20)))
        regions = build_evaluation_regions(mask(values), (polygon,))
        self.assertEqual(regions.risk_support.pixel_count, 2)
        self.assertEqual(regions.high_risk.pixel_count, 1)
        self.assertEqual(regions.background.pixel_count + regions.eligible_object_union.pixel_count, 160 * 120)

    def test_invalid_threshold_and_duplicate_ids_fail(self):
        polygon = ProjectedPolygon("a", "fully_visible", ((0, 0), (20, 0), (20, 20)))
        with self.assertRaises(ValueError):
            build_evaluation_regions(mask(), (polygon,), 1.1)
        with self.assertRaises(ValueError):
            build_evaluation_regions(mask(), (polygon, polygon))


if __name__ == "__main__":
    unittest.main()
