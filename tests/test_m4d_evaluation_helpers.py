import unittest

from perception.camera_models import ProjectedObstacle, ProjectedPoint, VisibilityStatus
from risk_map.image_risk_map import ImageRiskMasks, Mask2D
from scripts.m4d_image_risk_common import (
    assert_no_future_actual_leakage,
    decode_masks_json,
    encode_masks_json,
    exact_join_risk_projection,
    exclusive_pixels,
    overlap_pixels,
    parse_optional_float,
    point_rows,
    polygon_json,
    quantize_mask_value,
    role_config_complete,
    visibility_eligible,
)
from simulator.m4d_config import OBSTACLE_SPECS, OVERLAP_PAIR


def projection(obstacle_id: str) -> ProjectedObstacle:
    pts = (
        ProjectedPoint(1, 1, 1, True),
        ProjectedPoint(2, 1, 1, True),
        ProjectedPoint(2, 2, 1, True),
    )
    return ProjectedObstacle(
        obstacle_id,
        VisibilityStatus.FULLY_VISIBLE,
        pts,
        pts,
        (1, 1, 2, 2),
        1.0,
        1.0,
        1.0,
        0.0,
    )


class M4DEvaluationHelperTests(unittest.TestCase):
    def test_exact_join_uses_ids_not_order(self):
        joined = exact_join_risk_projection({"b": 2, "a": 1}, {"a": projection("a"), "b": projection("b")})
        self.assertEqual([item[0] for item in joined], ["b", "a"])

    def test_exact_join_rejects_missing_risk_or_projection(self):
        with self.assertRaises(ValueError):
            exact_join_risk_projection({"a": 1}, {"a": projection("a"), "b": projection("b")})
        with self.assertRaises(ValueError):
            exact_join_risk_projection({"a": 1, "b": 2}, {"a": projection("a")})

    def test_mask_json_round_trip_preserves_row_major_values(self):
        masks = ImageRiskMasks(
            Mask2D(2, 2, (0.0, 0.1, 0.2, 0.3)),
            Mask2D(2, 2, (0.3, 0.2, 0.1, 0.0)),
            Mask2D(2, 2, (0.3, 0.2, 0.2, 0.3)),
            (),
        )
        decoded = decode_masks_json(encode_masks_json(masks))
        self.assertEqual(decoded.planned.values, masks.planned.values)
        self.assertEqual(decoded.planned.rows(), ((0.0, 0.1), (0.2, 0.3)))

    def test_quantize_mask_value(self):
        self.assertEqual(quantize_mask_value(0.0), 0)
        self.assertEqual(quantize_mask_value(1.0), 255)
        self.assertEqual(quantize_mask_value(0.5), 128)
        for value in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                quantize_mask_value(value)

    def test_polygon_and_optional_serialization_helpers(self):
        pts = projection("a").clipped_polygon
        self.assertEqual(point_rows(pts), [[1, 1, 1], [2, 1, 1], [2, 2, 1]])
        self.assertEqual(polygon_json("[[1,2,3],[4,5,6]]"), [(1.0, 2.0), (4.0, 5.0)])
        self.assertIsNone(parse_optional_float(""))
        self.assertEqual(parse_optional_float("1.25"), 1.25)

    def test_exclusive_and_overlap_pixels(self):
        left = {(0, 0), (1, 0), (2, 0)}
        right = {(2, 0), (3, 0)}
        self.assertEqual(overlap_pixels(left, right), {(2, 0)})
        self.assertEqual(exclusive_pixels(left, [right]), {(0, 0), (1, 0)})

    def test_visibility_eligibility(self):
        self.assertTrue(visibility_eligible(VisibilityStatus.FULLY_VISIBLE))
        self.assertTrue(visibility_eligible("partially_visible"))
        self.assertTrue(visibility_eligible("intersects_near_plane"))
        self.assertFalse(visibility_eligible("outside_frustum"))
        self.assertFalse(visibility_eligible("behind_camera"))

    def test_metadata_future_actual_leakage_guard(self):
        assert_no_future_actual_leakage({"trajectory_sources": {"actual_future_trajectory_used": False}})
        with self.assertRaises(ValueError):
            assert_no_future_actual_leakage({"trajectory_sources": {"actual_future_trajectory_used": True}})
        with self.assertRaises(ValueError):
            assert_no_future_actual_leakage(
                {
                    "trajectory_sources": {"actual_future_trajectory_used": False},
                    "future_actual_position": [1, 2],
                }
            )

    def test_role_configuration_complete(self):
        self.assertTrue(role_config_complete())
        self.assertEqual(len(OBSTACLE_SPECS), 9)
        ids = {spec.obstacle_id for spec in OBSTACLE_SPECS}
        self.assertIn(OVERLAP_PAIR[0], ids)
        self.assertIn(OVERLAP_PAIR[1], ids)


if __name__ == "__main__":
    unittest.main()
