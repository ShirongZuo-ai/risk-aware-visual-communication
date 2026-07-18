import math
import unittest
from dataclasses import FrozenInstanceError

from perception.camera_models import (
    CameraExtrinsics,
    CameraIntrinsics,
    ObstacleBox3D,
    ProjectedObstacle,
    ProjectedPoint,
    VisibilityStatus,
)
from perception.camera_projection import project_obstacle_box
from risk_map.image_risk_map import (
    Mask2D,
    ProjectedObstacleRisk,
    RISK_EPSILON,
    bind_projection_to_risk,
    build_image_risk_masks,
)


def point(u, v, depth=1.0):
    return ProjectedPoint(u, v, depth, 0.0 <= u <= 9.0 and 0.0 <= v <= 9.0)


def projection(obstacle_id, vertices, status=VisibilityStatus.FULLY_VISIBLE, projected_vertices=None):
    clipped = tuple(point(u, v) for u, v in vertices)
    projected = tuple(point(u, v) for u, v in (projected_vertices or vertices))
    return ProjectedObstacle(
        obstacle_id=obstacle_id,
        visibility_status=status,
        projected_polygon=projected,
        clipped_polygon=clipped,
        bounding_box=None if not clipped else (
            min(p.u_px for p in clipped),
            min(p.v_px for p in clipped),
            max(p.u_px for p in clipped),
            max(p.v_px for p in clipped),
        ),
        minimum_depth_m=1.0 if clipped else None,
        maximum_depth_m=1.0 if clipped else None,
        projected_area_px=1.0 if len(clipped) >= 3 else 0.0,
        truncation_fraction=0.0,
    )


def risk(obstacle_id, vertices, planned=0.2, state=0.7, status=VisibilityStatus.FULLY_VISIBLE, projected_vertices=None):
    proj = projection(obstacle_id, vertices, status, projected_vertices=projected_vertices)
    return ProjectedObstacleRisk(obstacle_id, proj, planned, state, max(planned, state))


class Mask2DTests(unittest.TestCase):
    def test_mask_accepts_valid_tuple_and_list_values(self):
        mask = Mask2D(2, 2, [0.0, 0.2, 0.4, 1.0])
        self.assertEqual(mask.values, (0.0, 0.2, 0.4, 1.0))
        self.assertEqual(mask.get(1, 1), 1.0)

    def test_mask_rejects_invalid_dimensions(self):
        for width, height in [(0, 1), (1, 0), (-1, 1), (1.5, 2)]:
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    Mask2D(width, height, (0.0,))

    def test_mask_rejects_wrong_value_length(self):
        with self.assertRaises(ValueError):
            Mask2D(2, 2, (0.0, 0.0, 0.0))

    def test_mask_rejects_nan_inf_and_out_of_range_values(self):
        for value in [math.nan, math.inf, -0.1, 1.1]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Mask2D(1, 1, (value,))

    def test_mask_get_rejects_non_integer_or_out_of_bounds_indices(self):
        mask = Mask2D(2, 2, (0.0, 0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            mask.get(0.5, 0)
        for u, v in [(-1, 0), (2, 0), (0, -1), (0, 2)]:
            with self.subTest(u=u, v=v):
                with self.assertRaises(IndexError):
                    mask.get(u, v)

    def test_mask_rows_statistics_and_immutability(self):
        mask = Mask2D(2, 2, (0.0, 0.5, 0.0, 1.0))
        self.assertEqual(mask.rows(), ((0.0, 0.5), (0.0, 1.0)))
        self.assertEqual(mask.nonzero_pixel_count, 2)
        self.assertEqual(mask.maximum_value, 1.0)
        self.assertAlmostEqual(mask.mean_value, 0.375)
        with self.assertRaises(FrozenInstanceError):
            mask.width_px = 5


class ProjectedObstacleRiskTests(unittest.TestCase):
    def test_risk_binding_validates_id_and_combined_score(self):
        proj = projection("box", [(1, 1), (3, 1), (3, 3), (1, 3)])
        bound = bind_projection_to_risk(proj, 0.2, 0.5, 0.5)
        self.assertEqual(bound.obstacle_id, "box")
        self.assertIs(bound.projection, proj)

    def test_projected_obstacle_risk_rejects_id_mismatch(self):
        proj = projection("box", [(1, 1), (3, 1), (3, 3), (1, 3)])
        with self.assertRaises(ValueError):
            ProjectedObstacleRisk("other", proj, 0.2, 0.5, 0.5)

    def test_projected_obstacle_risk_rejects_invalid_scores(self):
        proj = projection("box", [(1, 1), (3, 1), (3, 3), (1, 3)])
        cases = [(-0.1, 0.0, 0.0), (1.1, 0.0, 1.1), (math.nan, 0.0, 0.0), (0.0, math.inf, 0.0)]
        for planned, state, combined in cases:
            with self.subTest(planned=planned, state=state, combined=combined):
                with self.assertRaises(ValueError):
                    ProjectedObstacleRisk("box", proj, planned, state, combined)

    def test_projected_obstacle_risk_combined_mismatch_and_epsilon(self):
        proj = projection("box", [(1, 1), (3, 1), (3, 3), (1, 3)])
        ProjectedObstacleRisk("box", proj, 0.4, 0.6, 0.6 + RISK_EPSILON * 0.5)
        with self.assertRaises(ValueError):
            ProjectedObstacleRisk("box", proj, 0.4, 0.6, 0.7)


class RasterizationTests(unittest.TestCase):
    def test_integer_rectangle_uses_integer_pixel_centers_and_boundaries(self):
        masks = build_image_risk_masks(6, 6, [risk("rect", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.4, 0.1)])
        self.assertEqual(masks.planned.nonzero_pixel_count, 9)
        self.assertEqual(masks.planned.get(1, 1), 0.4)
        self.assertEqual(masks.planned.get(3, 3), 0.4)
        self.assertEqual(masks.planned.get(4, 3), 0.0)

    def test_noninteger_rectangle_does_not_fill_entire_bbox(self):
        masks = build_image_risk_masks(6, 6, [risk("rect", [(1.2, 1.2), (3.2, 1.2), (3.2, 3.2), (1.2, 3.2)], 0.5, 0.0)])
        self.assertEqual(masks.planned.nonzero_pixel_count, 4)
        self.assertEqual(masks.planned.get(2, 2), 0.5)
        self.assertEqual(masks.planned.get(1, 1), 0.0)

    def test_triangle_rasterizes_interior_not_bbox(self):
        masks = build_image_risk_masks(6, 6, [risk("tri", [(1, 1), (4, 1), (1, 4)], 0.8, 0.0)])
        self.assertEqual(masks.planned.get(2, 2), 0.8)
        self.assertEqual(masks.planned.get(4, 4), 0.0)
        self.assertLess(masks.planned.nonzero_pixel_count, 16)

    def test_clockwise_and_counterclockwise_polygons_match(self):
        ccw = build_image_risk_masks(6, 6, [risk("a", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.4, 0.0)])
        cw = build_image_risk_masks(6, 6, [risk("a", [(1, 1), (1, 3), (3, 3), (3, 1)], 0.4, 0.0)])
        self.assertEqual(ccw.planned.values, cw.planned.values)

    def test_horizontal_vertical_edges_and_image_boundaries_are_supported(self):
        masks = build_image_risk_masks(4, 4, [risk("edge", [(0, 0), (3, 0), (3, 3), (0, 3)], 0.3, 0.0)])
        self.assertEqual(masks.planned.nonzero_pixel_count, 16)
        self.assertEqual(masks.planned.get(0, 0), 0.3)
        self.assertEqual(masks.planned.get(3, 3), 0.3)

    def test_consecutive_duplicate_vertices_are_removed(self):
        masks = build_image_risk_masks(6, 6, [risk("dup", [(1, 1), (3, 1), (3, 1), (3, 3), (1, 3), (1, 1)], 0.3, 0.0)])
        self.assertEqual(masks.contributions[0].polygon_vertex_count, 4)
        self.assertEqual(masks.planned.nonzero_pixel_count, 9)

    def test_too_few_collinear_and_tiny_polygons_skip(self):
        cases = [
            [(1, 1), (2, 2)],
            [(1, 1), (2, 2), (3, 3)],
            [(1.0, 1.0), (1.000001, 1.0), (1.0, 1.000001)],
        ]
        for index, vertices in enumerate(cases):
            with self.subTest(vertices=vertices):
                masks = build_image_risk_masks(6, 6, [risk(f"bad{index}", vertices, 1.0, 1.0)])
                self.assertEqual(masks.combined.nonzero_pixel_count, 0)
                self.assertFalse(masks.contributions[0].eligible_for_mask)

    def test_output_pixels_are_within_image(self):
        masks = build_image_risk_masks(5, 5, [risk("box", [(0, 1), (4, 1), (4, 4), (0, 4)], 0.5, 0.5)])
        self.assertEqual(len(masks.planned.values), 25)
        self.assertGreater(masks.planned.nonzero_pixel_count, 0)


class VisibilityAndChannelTests(unittest.TestCase):
    def test_visible_partial_and_near_plane_statuses_write_masks(self):
        for status in [
            VisibilityStatus.FULLY_VISIBLE,
            VisibilityStatus.PARTIALLY_VISIBLE,
            VisibilityStatus.INTERSECTS_NEAR_PLANE,
        ]:
            with self.subTest(status=status):
                masks = build_image_risk_masks(6, 6, [risk("box", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.2, 0.6, status)])
                self.assertTrue(masks.contributions[0].eligible_for_mask)
                self.assertEqual(masks.combined.get(2, 2), 0.6)

    def test_invisible_statuses_skip_even_when_high_risk(self):
        for status in [
            VisibilityStatus.OUTSIDE_FRUSTUM,
            VisibilityStatus.BEHIND_CAMERA,
            VisibilityStatus.DEGENERATE_PROJECTION,
        ]:
            with self.subTest(status=status):
                masks = build_image_risk_masks(6, 6, [risk("box", [(1, 1), (3, 1), (3, 3), (1, 3)], 1.0, 1.0, status)])
                self.assertFalse(masks.contributions[0].eligible_for_mask)
                self.assertEqual(masks.contributions[0].skip_reason, status.value)
                self.assertEqual(masks.combined.nonzero_pixel_count, 0)

    def test_empty_input_returns_zero_masks_and_no_contributions(self):
        masks = build_image_risk_masks(3, 2, [])
        self.assertEqual(masks.planned.values, (0.0,) * 6)
        self.assertEqual(masks.state.values, (0.0,) * 6)
        self.assertEqual(masks.combined.values, (0.0,) * 6)
        self.assertEqual(masks.contributions, ())

    def test_channels_are_independent_and_combined_is_pixelwise_max(self):
        masks = build_image_risk_masks(6, 6, [risk("box", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.2, 0.7)])
        self.assertEqual(masks.planned.get(2, 2), 0.2)
        self.assertEqual(masks.state.get(2, 2), 0.7)
        self.assertEqual(masks.combined.get(2, 2), 0.7)
        for planned, state, combined in zip(masks.planned.values, masks.state.values, masks.combined.values):
            self.assertEqual(combined, max(planned, state))

    def test_projected_polygon_is_not_used_for_mask_writing(self):
        masks = build_image_risk_masks(
            10,
            10,
            [risk("box", [(1, 1), (2, 1), (2, 2), (1, 2)], 0.9, 0.0, projected_vertices=[(1, 1), (8, 1), (8, 8), (1, 8)])],
        )
        self.assertEqual(masks.planned.get(2, 2), 0.9)
        self.assertEqual(masks.planned.get(8, 8), 0.0)

    def test_duplicate_obstacle_ids_are_rejected(self):
        obstacles = [
            risk("dup", [(1, 1), (2, 1), (2, 2), (1, 2)], 0.3, 0.0),
            risk("dup", [(3, 3), (4, 3), (4, 4), (3, 4)], 0.4, 0.0),
        ]
        with self.assertRaises(ValueError):
            build_image_risk_masks(6, 6, obstacles)


class OverlapAndInvariantTests(unittest.TestCase):
    def test_overlap_uses_max_and_later_low_risk_cannot_lower_existing_values(self):
        high = risk("high", [(1, 1), (4, 1), (4, 4), (1, 4)], 0.8, 0.1)
        low = risk("low", [(2, 2), (5, 2), (5, 5), (2, 5)], 0.2, 0.7)
        masks = build_image_risk_masks(7, 7, [high, low])
        self.assertEqual(masks.planned.get(2, 2), 0.8)
        self.assertEqual(masks.state.get(2, 2), 0.7)
        self.assertEqual(masks.combined.get(2, 2), 0.8)
        self.assertEqual(masks.contributions[1].planned_written_pixel_count, 7)
        self.assertEqual(masks.contributions[1].state_written_pixel_count, 16)

    def test_masks_are_input_order_invariant_but_contributions_preserve_order(self):
        a = risk("a", [(1, 1), (4, 1), (4, 4), (1, 4)], 0.8, 0.1)
        b = risk("b", [(2, 2), (5, 2), (5, 5), (2, 5)], 0.2, 0.7)
        first = build_image_risk_masks(7, 7, [a, b])
        second = build_image_risk_masks(7, 7, [b, a])
        self.assertEqual(first.planned.values, second.planned.values)
        self.assertEqual(first.state.values, second.state.values)
        self.assertEqual(first.combined.values, second.combined.values)
        self.assertEqual([c.obstacle_id for c in first.contributions], ["a", "b"])
        self.assertEqual([c.obstacle_id for c in second.contributions], ["b", "a"])

    def test_contribution_candidate_and_written_counts_are_diagnostic(self):
        first = risk("first", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.5, 0.5)
        second = risk("second", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.4, 0.8)
        masks = build_image_risk_masks(6, 6, [first, second])
        self.assertEqual(masks.contributions[0].candidate_pixel_count, 9)
        self.assertEqual(masks.contributions[0].planned_written_pixel_count, 9)
        self.assertEqual(masks.contributions[1].candidate_pixel_count, 9)
        self.assertEqual(masks.contributions[1].planned_written_pixel_count, 0)
        self.assertEqual(masks.contributions[1].state_written_pixel_count, 9)
        self.assertEqual(masks.contributions[1].combined_written_pixel_count, 9)

    def test_input_projection_is_not_mutated(self):
        obstacle = risk("box", [(1, 1), (3, 1), (3, 3), (1, 3)], 0.2, 0.3)
        before = obstacle.projection.clipped_polygon
        build_image_risk_masks(6, 6, [obstacle])
        self.assertIs(obstacle.projection.clipped_polygon, before)


class RealProjectionIntegrationTests(unittest.TestCase):
    def test_real_project_obstacle_box_output_can_feed_image_mask_core(self):
        intrinsics = CameraIntrinsics.from_horizontal_fov(160, 120, 0.84, 0.0055)
        extrinsics = CameraExtrinsics.identity(
            (
                (0.0, -1.0, 0.0),
                (0.0, 0.0, -1.0),
                (1.0, 0.0, 0.0),
            )
        )
        box = ObstacleBox3D("real_projection", 1.0, 0.0, 0.0, 0.2, 0.2, 0.2)
        projected = project_obstacle_box(box, intrinsics, extrinsics)
        self.assertIn(projected.visibility_status, (VisibilityStatus.FULLY_VISIBLE, VisibilityStatus.PARTIALLY_VISIBLE))
        masks = build_image_risk_masks(160, 120, [bind_projection_to_risk(projected, 0.3, 0.6, 0.6)])
        self.assertGreater(masks.combined.nonzero_pixel_count, 0)
        self.assertEqual(masks.contributions[0].obstacle_id, "real_projection")
        for planned, state, combined in zip(masks.planned.values, masks.state.values, masks.combined.values):
            self.assertEqual(combined, max(planned, state))


if __name__ == "__main__":
    unittest.main()
