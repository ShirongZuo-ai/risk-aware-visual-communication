import math
import unittest

from perception.camera_models import CameraExtrinsics, CameraIntrinsics, ObstacleBox3D, ProjectedPoint, VisibilityStatus
from perception.camera_projection import (
    AREA_EPSILON_PX2,
    camera_device_to_optical_point,
    camera_device_to_world_point,
    clip_box_points_to_near_plane,
    clip_polygon_to_image,
    convex_hull,
    mat_mat_mul,
    polygon_area,
    polygon_bounding_box,
    polygons_bounding_boxes_overlap,
    project_obstacle_box,
    project_optical_point,
    rotation_x,
    rotation_y,
    rotation_z,
    world_to_camera_device_point,
    world_to_optical_point,
)


IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
DEVICE_TO_OPTICAL = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))


class TransformTests(unittest.TestCase):
    def test_identity_translation_and_round_trip(self):
        extrinsics = CameraExtrinsics.from_camera_pose_in_world(IDENTITY, (1.0, 2.0, 3.0), IDENTITY)
        device = world_to_camera_device_point((2.0, 4.0, 6.0), extrinsics)
        self.assertEqual(device, (1.0, 2.0, 3.0))
        world = camera_device_to_world_point(device, extrinsics)
        for actual, expected in zip(world, (2.0, 4.0, 6.0)):
            self.assertAlmostEqual(actual, expected)

    def test_yaw_pitch_roll_transforms_are_valid(self):
        for rotation in (rotation_z(math.pi / 2), rotation_y(math.pi / 2), rotation_x(math.pi / 2)):
            extrinsics = CameraExtrinsics.from_camera_pose_in_world(rotation, (0.1, -0.2, 0.3), IDENTITY)
            point = (0.7, 0.8, 0.9)
            round_trip = camera_device_to_world_point(world_to_camera_device_point(point, extrinsics), extrinsics)
            for actual, expected in zip(round_trip, point):
                self.assertAlmostEqual(actual, expected, places=12)

    def test_device_to_optical_axis_transform(self):
        extrinsics = CameraExtrinsics.identity(DEVICE_TO_OPTICAL)
        self.assertEqual(camera_device_to_optical_point((1.0, 2.0, -3.0), extrinsics), (1.0, -2.0, 3.0))
        self.assertEqual(world_to_optical_point((1.0, 2.0, -3.0), extrinsics), (1.0, -2.0, 3.0))

    def test_matrix_matrix_multiply(self):
        self.assertEqual(mat_mat_mul(IDENTITY, rotation_z(0.3)), rotation_z(0.3))

    def test_world_to_camera_rejects_nonfinite_point(self):
        extrinsics = CameraExtrinsics.identity(IDENTITY)
        with self.assertRaises(ValueError):
            world_to_camera_device_point((math.inf, 0.0, 1.0), extrinsics)


class PointProjectionTests(unittest.TestCase):
    def setUp(self):
        self.intrinsics = CameraIntrinsics.from_horizontal_fov(160, 120, 0.84, 0.0055)

    def test_principal_point_right_down_and_depth_scaling(self):
        center = project_optical_point((0.0, 0.0, 1.0), self.intrinsics)
        right = project_optical_point((0.1, 0.0, 1.0), self.intrinsics)
        down = project_optical_point((0.0, 0.1, 1.0), self.intrinsics)
        far = project_optical_point((0.1, 0.0, 2.0), self.intrinsics)
        self.assertIsNotNone(center)
        self.assertAlmostEqual(center.u_px, self.intrinsics.cx_px)
        self.assertAlmostEqual(center.v_px, self.intrinsics.cy_px)
        self.assertGreater(right.u_px, center.u_px)
        self.assertGreater(down.v_px, center.v_px)
        self.assertLess(far.u_px - center.u_px, right.u_px - center.u_px)

    def test_horizontal_and_vertical_fov_boundaries(self):
        z = 1.0
        x_edge = z * math.tan(0.84 / 2.0)
        y_edge = z * math.tan(self.intrinsics.vertical_fov_rad / 2.0)
        right_edge = project_optical_point((x_edge, 0.0, z), self.intrinsics)
        bottom_edge = project_optical_point((0.0, y_edge, z), self.intrinsics)
        self.assertAlmostEqual(right_edge.u_px, self.intrinsics.cx_px + self.intrinsics.width_px / 2.0)
        self.assertAlmostEqual(bottom_edge.v_px, self.intrinsics.cy_px + self.intrinsics.height_px / 2.0)

    def test_near_plane_and_invalid_points(self):
        self.assertIsNotNone(project_optical_point((0.0, 0.0, self.intrinsics.near_clip_m), self.intrinsics))
        self.assertIsNone(project_optical_point((0.0, 0.0, self.intrinsics.near_clip_m * 0.5), self.intrinsics))
        self.assertIsNone(project_optical_point((0.0, 0.0, -1.0), self.intrinsics))
        with self.assertRaises(ValueError):
            project_optical_point((math.nan, 0.0, 1.0), self.intrinsics)


class PolygonHelperTests(unittest.TestCase):
    def setUp(self):
        self.intrinsics = CameraIntrinsics(100, 80, 50.0, 50.0, 49.5, 39.5, 0.1)

    def point(self, u, v):
        return ProjectedPoint.from_image_coordinates(u, v, 1.0, self.intrinsics)

    def test_convex_hull_duplicates_and_collinear(self):
        hull = convex_hull([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0), (0.5, 0.5)])
        self.assertEqual(hull, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
        self.assertEqual(convex_hull([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]), ((0.0, 0.0), (2.0, 0.0)))

    def test_polygon_area_and_bounding_box(self):
        polygon = (self.point(2, 2), self.point(6, 2), self.point(6, 5), self.point(2, 5))
        self.assertAlmostEqual(polygon_area(polygon), 12.0)
        self.assertEqual(polygon_bounding_box(polygon), (2, 2, 6, 5))
        self.assertEqual(polygon_area((self.point(1, 1), self.point(2, 2))), 0.0)

    def test_clip_polygon_inside_partial_outside_and_large(self):
        inside = (self.point(10, 10), self.point(20, 10), self.point(20, 20), self.point(10, 20))
        self.assertEqual(clip_polygon_to_image(inside, self.intrinsics), inside)
        partial = (self.point(-10, 10), self.point(20, 10), self.point(20, 20), self.point(-10, 20))
        clipped = clip_polygon_to_image(partial, self.intrinsics)
        self.assertTrue(all(0 <= point.u_px <= 99 and 0 <= point.v_px <= 79 for point in clipped))
        self.assertAlmostEqual(polygon_area(clipped), 200.0)
        outside = (self.point(-30, 10), self.point(-20, 10), self.point(-20, 20), self.point(-30, 20))
        self.assertEqual(clip_polygon_to_image(outside, self.intrinsics), ())
        huge = (self.point(-100, -100), self.point(200, -100), self.point(200, 200), self.point(-100, 200))
        huge_clipped = clip_polygon_to_image(huge, self.intrinsics)
        self.assertAlmostEqual(polygon_area(huge_clipped), 99 * 79)

    def test_clip_polygon_touching_boundary_remains_valid(self):
        touching = (self.point(0, 10), self.point(20, 10), self.point(20, 20), self.point(0, 20))
        clipped = clip_polygon_to_image(touching, self.intrinsics)
        self.assertAlmostEqual(polygon_area(clipped), 200.0)
        self.assertTrue(all(point.inside_image for point in clipped))


class NearPlaneClippingTests(unittest.TestCase):
    def test_clip_edges_crossing_near_plane(self):
        points = (
            (-1.0, -1.0, 0.05),
            (-1.0, -1.0, 0.2),
            (-1.0, 1.0, 0.05),
            (-1.0, 1.0, 0.2),
            (1.0, -1.0, 0.05),
            (1.0, -1.0, 0.2),
            (1.0, 1.0, 0.05),
            (1.0, 1.0, 0.2),
        )
        clipped, intersects = clip_box_points_to_near_plane(points, 0.1)
        self.assertTrue(intersects)
        self.assertTrue(all(point[2] >= 0.1 - 1e-9 for point in clipped))
        self.assertTrue(any(abs(point[2] - 0.1) < 1e-9 for point in clipped))

    def test_clip_edges_parallel_to_near_plane(self):
        points = (
            (-1.0, -1.0, 0.2),
            (-1.0, -1.0, 0.2),
            (-1.0, 1.0, 0.2),
            (-1.0, 1.0, 0.2),
            (1.0, -1.0, 0.2),
            (1.0, -1.0, 0.2),
            (1.0, 1.0, 0.2),
            (1.0, 1.0, 0.2),
        )
        clipped, intersects = clip_box_points_to_near_plane(points, 0.1)
        self.assertFalse(intersects)
        self.assertEqual(len(clipped), 4)


class ObstacleProjectionTests(unittest.TestCase):
    def setUp(self):
        self.intrinsics = CameraIntrinsics(100, 80, 50.0, 50.0, 49.5, 39.5, 0.1)
        self.extrinsics = CameraExtrinsics.identity(IDENTITY)

    def assert_valid_visible_invariants(self, result):
        self.assertTrue(all(math.isfinite(point.u_px) and math.isfinite(point.v_px) for point in result.projected_polygon))
        self.assertTrue(all(0 <= point.u_px <= 99 and 0 <= point.v_px <= 79 for point in result.clipped_polygon))
        self.assertIsNotNone(result.bounding_box)
        min_u, min_v, max_u, max_v = result.bounding_box
        for point in result.clipped_polygon:
            self.assertLessEqual(min_u - 1e-9, point.u_px)
            self.assertGreaterEqual(max_u + 1e-9, point.u_px)
            self.assertLessEqual(min_v - 1e-9, point.v_px)
            self.assertGreaterEqual(max_v + 1e-9, point.v_px)
        self.assertGreaterEqual(result.minimum_depth_m, self.intrinsics.near_clip_m)
        self.assertLessEqual(result.minimum_depth_m, result.maximum_depth_m)
        self.assertGreaterEqual(result.truncation_fraction, 0.0)
        self.assertLessEqual(result.truncation_fraction, 1.0)

    def test_center_left_and_right_visible_boxes(self):
        center = project_obstacle_box(ObstacleBox3D("CENTER_VISIBLE", 0.0, 0.0, 2.0, 0.4, 0.4, 0.4), self.intrinsics, self.extrinsics)
        left = project_obstacle_box(ObstacleBox3D("LEFT_VISIBLE", -0.8, 0.0, 3.0, 0.3, 0.3, 0.3), self.intrinsics, self.extrinsics)
        right = project_obstacle_box(ObstacleBox3D("RIGHT_VISIBLE", 0.8, 0.0, 3.0, 0.3, 0.3, 0.3), self.intrinsics, self.extrinsics)
        self.assertEqual(center.visibility_status, VisibilityStatus.FULLY_VISIBLE)
        self.assertEqual(left.visibility_status, VisibilityStatus.FULLY_VISIBLE)
        self.assertEqual(right.visibility_status, VisibilityStatus.FULLY_VISIBLE)
        self.assertLess(left.bounding_box[2], center.bounding_box[0])
        self.assertGreater(right.bounding_box[0], center.bounding_box[2])
        self.assertAlmostEqual(center.truncation_fraction, 0.0)
        self.assert_valid_visible_invariants(center)

    def test_partial_outside_behind_and_near_plane_roles(self):
        partial = project_obstacle_box(ObstacleBox3D("PARTIAL_IMAGE_EDGE", 1.9, 0.0, 2.0, 0.7, 0.4, 0.4), self.intrinsics, self.extrinsics)
        outside = project_obstacle_box(ObstacleBox3D("OUTSIDE_FRUSTUM", 8.0, 0.0, 2.0, 0.4, 0.4, 0.4), self.intrinsics, self.extrinsics)
        behind = project_obstacle_box(ObstacleBox3D("BEHIND_CAMERA", 0.0, 0.0, -1.0, 0.4, 0.4, 0.4), self.intrinsics, self.extrinsics)
        near = project_obstacle_box(ObstacleBox3D("NEAR_PLANE_INTERSECTION", 0.0, 0.0, 0.12, 0.04, 0.04, 0.12), self.intrinsics, self.extrinsics)
        self.assertEqual(partial.visibility_status, VisibilityStatus.PARTIALLY_VISIBLE)
        self.assertGreater(partial.truncation_fraction, 0.0)
        self.assert_valid_visible_invariants(partial)
        self.assertEqual(outside.visibility_status, VisibilityStatus.OUTSIDE_FRUSTUM)
        self.assertEqual(outside.clipped_polygon, ())
        self.assertEqual(behind.visibility_status, VisibilityStatus.BEHIND_CAMERA)
        self.assertEqual(behind.projected_polygon, ())
        self.assertEqual(near.visibility_status, VisibilityStatus.INTERSECTS_NEAR_PLANE)
        self.assert_valid_visible_invariants(near)

    def test_degenerate_and_depth_overlap_roles(self):
        tiny = project_obstacle_box(ObstacleBox3D("TINY", 0.0, 0.0, 1000000.0, 0.001, 0.001, 0.001), self.intrinsics, self.extrinsics)
        self.assertEqual(tiny.visibility_status, VisibilityStatus.DEGENERATE_PROJECTION)
        self.assertLessEqual(tiny.projected_area_px, AREA_EPSILON_PX2)
        near_box = project_obstacle_box(ObstacleBox3D("DEPTH_OVERLAP_NEAR", 0.0, 0.0, 2.0, 0.5, 0.5, 0.5), self.intrinsics, self.extrinsics)
        far_box = project_obstacle_box(ObstacleBox3D("DEPTH_OVERLAP_FAR", 0.05, 0.0, 3.0, 0.5, 0.5, 0.5), self.intrinsics, self.extrinsics)
        self.assertEqual(near_box.visibility_status, VisibilityStatus.FULLY_VISIBLE)
        self.assertEqual(far_box.visibility_status, VisibilityStatus.FULLY_VISIBLE)
        self.assertTrue(polygons_bounding_boxes_overlap(near_box, far_box))


if __name__ == "__main__":
    unittest.main()
