import math
import unittest

from perception.camera_models import (
    BOX_EDGE_INDICES,
    CameraExtrinsics,
    CameraIntrinsics,
    ObstacleBox3D,
    ProjectedObstacle,
    ProjectedPoint,
    VisibilityStatus,
)


DEVICE_TO_OPTICAL = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))


class CameraIntrinsicsTests(unittest.TestCase):
    def test_from_horizontal_fov_matches_current_epuck_camera(self):
        intrinsics = CameraIntrinsics.from_horizontal_fov(160, 120, 0.84, 0.0055)
        self.assertAlmostEqual(intrinsics.fx_px, 179.142225973, places=9)
        self.assertAlmostEqual(intrinsics.fy_px, 179.142225973, places=9)
        self.assertAlmostEqual(intrinsics.cx_px, 79.5)
        self.assertAlmostEqual(intrinsics.cy_px, 59.5)
        self.assertAlmostEqual(intrinsics.vertical_fov_rad, 0.646372669, places=9)

    def test_intrinsics_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            CameraIntrinsics(0, 120, 1.0, 1.0, 0.0, 0.0, 0.1)
        with self.assertRaises(ValueError):
            CameraIntrinsics(160, -1, 1.0, 1.0, 0.0, 0.0, 0.1)
        with self.assertRaises(ValueError):
            CameraIntrinsics(160, 120, 0.0, 1.0, 0.0, 0.0, 0.1)
        with self.assertRaises(ValueError):
            CameraIntrinsics(160, 120, 1.0, -1.0, 0.0, 0.0, 0.1)
        with self.assertRaises(ValueError):
            CameraIntrinsics(160, 120, 1.0, 1.0, 0.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            CameraIntrinsics(160, 120, math.nan, 1.0, 0.0, 0.0, 0.1)
        with self.assertRaises(ValueError):
            CameraIntrinsics.from_horizontal_fov(160, 120, math.inf, 0.1)
        with self.assertRaises(ValueError):
            CameraIntrinsics.from_horizontal_fov(160, 120, math.pi, 0.1)


class CameraExtrinsicsTests(unittest.TestCase):
    def test_identity_and_explicit_device_to_optical(self):
        extrinsics = CameraExtrinsics.identity(DEVICE_TO_OPTICAL)
        self.assertEqual(extrinsics.world_to_camera_translation, (0.0, 0.0, 0.0))
        self.assertEqual(extrinsics.device_to_optical_rotation, DEVICE_TO_OPTICAL)

    def test_from_camera_pose_translation_semantics(self):
        extrinsics = CameraExtrinsics.from_camera_pose_in_world(
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            (1.0, 2.0, 3.0),
            DEVICE_TO_OPTICAL,
        )
        self.assertEqual(extrinsics.world_to_camera_translation, (-1.0, -2.0, -3.0))

    def test_extrinsics_reject_bad_rotations(self):
        with self.assertRaises(ValueError):
            CameraExtrinsics(((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0), DEVICE_TO_OPTICAL)
        with self.assertRaises(ValueError):
            CameraExtrinsics(((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0), DEVICE_TO_OPTICAL)
        with self.assertRaises(ValueError):
            CameraExtrinsics(((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0), DEVICE_TO_OPTICAL)
        with self.assertRaises(ValueError):
            CameraExtrinsics(((1.0, 0.0), (0.0, 1.0), (0.0, 0.0)), (0.0, 0.0, 0.0), DEVICE_TO_OPTICAL)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            CameraExtrinsics(((1.0, 0.0, 0.0), (0.0, math.nan, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0), DEVICE_TO_OPTICAL)


class ObstacleBox3DTests(unittest.TestCase):
    def test_center_size_corners_and_edges(self):
        box = ObstacleBox3D("box", 1.0, 2.0, 3.0, 2.0, 4.0, 6.0)
        self.assertEqual(box.center_world, (1.0, 2.0, 3.0))
        self.assertEqual(box.size, (2.0, 4.0, 6.0))
        self.assertEqual(
            box.corners_world,
            (
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 6.0),
                (0.0, 4.0, 0.0),
                (0.0, 4.0, 6.0),
                (2.0, 0.0, 0.0),
                (2.0, 0.0, 6.0),
                (2.0, 4.0, 0.0),
                (2.0, 4.0, 6.0),
            ),
        )
        self.assertEqual(len(BOX_EDGE_INDICES), 12)
        self.assertTrue(all(0 <= start < 8 and 0 <= end < 8 for start, end in BOX_EDGE_INDICES))

    def test_obstacle_validation(self):
        with self.assertRaises(ValueError):
            ObstacleBox3D("", 0.0, 0.0, 1.0, 1.0, 1.0, 1.0)
        with self.assertRaises(ValueError):
            ObstacleBox3D("bad", 0.0, 0.0, 1.0, 0.0, 1.0, 1.0)
        with self.assertRaises(ValueError):
            ObstacleBox3D("bad", 0.0, 0.0, 1.0, 1.0, -1.0, 1.0)
        with self.assertRaises(ValueError):
            ObstacleBox3D("bad", 0.0, math.inf, 1.0, 1.0, 1.0, 1.0)


class ProjectedModelTests(unittest.TestCase):
    def test_projected_point_inside_image(self):
        intrinsics = CameraIntrinsics(10, 8, 5.0, 5.0, 4.5, 3.5, 0.1)
        inside = ProjectedPoint.from_image_coordinates(9.0, 7.0, 1.0, intrinsics)
        outside = ProjectedPoint.from_image_coordinates(10.0, 7.0, 1.0, intrinsics)
        self.assertTrue(inside.inside_image)
        self.assertFalse(outside.inside_image)
        with self.assertRaises(ValueError):
            ProjectedPoint(0.0, 0.0, 0.0, True)

    def test_projected_obstacle_validation(self):
        point = ProjectedPoint(1.0, 1.0, 1.0, True)
        obstacle = ProjectedObstacle("box", VisibilityStatus.FULLY_VISIBLE, (point,), (point,), (1.0, 1.0, 1.0, 1.0), 1.0, 1.0, 0.0, 0.0)
        self.assertEqual(obstacle.visibility_status, VisibilityStatus.FULLY_VISIBLE)
        with self.assertRaises(ValueError):
            ProjectedObstacle("", VisibilityStatus.FULLY_VISIBLE, (), (), None, None, None, 0.0, 0.0)
        with self.assertRaises(ValueError):
            ProjectedObstacle("box", "fully_visible", (), (), None, None, None, 0.0, 0.0)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ProjectedObstacle("box", VisibilityStatus.FULLY_VISIBLE, (), (), None, None, None, -1.0, 0.0)
        with self.assertRaises(ValueError):
            ProjectedObstacle("box", VisibilityStatus.FULLY_VISIBLE, (), (), None, None, None, 0.0, 1.5)


if __name__ == "__main__":
    unittest.main()

