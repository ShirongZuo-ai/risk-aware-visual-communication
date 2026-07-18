import math
import unittest

from perception.camera_projection import camera_device_to_world_point, world_to_camera_device_point
from simulator.adapters.webots_camera_adapter import (
    DEVICE_TO_OPTICAL_ROTATION,
    camera_pose_to_extrinsics,
    intrinsics_from_camera_values,
    obstacle_box_from_fields,
    parse_camera_pose_matrix,
)
from simulator.m4c_config import OBSTACLE_SPECS


IDENTITY_POSE = (
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
)


def row_major_pose(rotation, position):
    return (
        rotation[0][0],
        rotation[0][1],
        rotation[0][2],
        position[0],
        rotation[1][0],
        rotation[1][1],
        rotation[1][2],
        position[1],
        rotation[2][0],
        rotation[2][1],
        rotation[2][2],
        position[2],
        0.0,
        0.0,
        0.0,
        1.0,
    )


class WebotsCameraAdapterHelperTests(unittest.TestCase):
    def test_parse_identity_pose(self):
        rotation, position, layout = parse_camera_pose_matrix(IDENTITY_POSE, expected_position=(0.0, 0.0, 0.0))
        self.assertEqual(rotation, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        self.assertEqual(position, (0.0, 0.0, 0.0))
        self.assertEqual(layout, "row_major_translation_column")

    def test_parse_translated_pose_and_translation_sign(self):
        pose = row_major_pose(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (1.0, 2.0, 3.0))
        rotation, position, _layout = parse_camera_pose_matrix(pose, expected_position=(1.0, 2.0, 3.0))
        extrinsics = camera_pose_to_extrinsics(rotation, position)
        self.assertEqual(extrinsics.world_to_camera_translation, (-1.0, -2.0, -3.0))
        self.assertEqual(world_to_camera_device_point((2.0, 4.0, 6.0), extrinsics), (1.0, 2.0, 3.0))

    def test_round_trip_for_yaw_pitch_and_roll(self):
        rotations = (
            ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
            ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
        )
        for rotation in rotations:
            pose = row_major_pose(rotation, (0.1, -0.2, 0.3))
            parsed_rotation, position, _layout = parse_camera_pose_matrix(pose, expected_position=(0.1, -0.2, 0.3))
            extrinsics = camera_pose_to_extrinsics(parsed_rotation, position)
            point_world = (0.4, -0.5, 0.7)
            round_trip = camera_device_to_world_point(world_to_camera_device_point(point_world, extrinsics), extrinsics)
            for actual, expected in zip(round_trip, point_world):
                self.assertAlmostEqual(actual, expected, places=12)

    def test_device_to_optical_rotation_is_frozen(self):
        self.assertEqual(DEVICE_TO_OPTICAL_ROTATION, ((0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)))

    def test_intrinsics_from_camera_values(self):
        intrinsics = intrinsics_from_camera_values(160, 120, 0.84, 0.0055)
        self.assertAlmostEqual(intrinsics.fx_px, 179.142225973, places=9)
        self.assertEqual(intrinsics.width_px, 160)
        self.assertEqual(intrinsics.height_px, 120)

    def test_obstacle_box_from_fields(self):
        obstacle = obstacle_box_from_fields(
            obstacle_id="box",
            translation=(1.0, 2.0, 3.0),
            rotation=(0.0, 0.0, 1.0, 0.0),
            size=(0.1, 0.2, 0.3),
        )
        self.assertEqual(obstacle.center_world, (1.0, 2.0, 3.0))
        self.assertEqual(obstacle.size, (0.1, 0.2, 0.3))

    def test_invalid_pose_length_nonfinite_and_rotation(self):
        with self.assertRaises(ValueError):
            parse_camera_pose_matrix((1.0, 2.0))
        values = list(IDENTITY_POSE)
        values[0] = math.nan
        with self.assertRaises(ValueError):
            parse_camera_pose_matrix(values)
        bad_rotation = row_major_pose(((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            parse_camera_pose_matrix(bad_rotation, expected_position=(0.0, 0.0, 0.0))

    def test_reject_nonfinite_and_rotated_boxes(self):
        with self.assertRaises(ValueError):
            obstacle_box_from_fields(obstacle_id="bad", translation=(math.inf, 0.0, 0.0), rotation=(0, 0, 1, 0), size=(1, 1, 1))
        with self.assertRaises(ValueError):
            obstacle_box_from_fields(obstacle_id="bad", translation=(0, 0, 0), rotation=(0, 0, 1, 0), size=(0, 1, 1))
        with self.assertRaises(ValueError):
            obstacle_box_from_fields(obstacle_id="bad", translation=(0, 0, 0), rotation=(0, 0, 1, 0.1), size=(1, 1, 1))

    def test_role_config_completeness(self):
        roles = [spec.role for spec in OBSTACLE_SPECS]
        defs = [spec.def_name for spec in OBSTACLE_SPECS]
        self.assertEqual(len(OBSTACLE_SPECS), 9)
        self.assertEqual(len(set(roles)), 9)
        self.assertEqual(len(set(defs)), 9)
        self.assertIn("CENTER_VISIBLE", roles)
        self.assertIn("DEPTH_OVERLAP_BACK", roles)
        self.assertTrue(all(len(spec.target_rgb) == 3 for spec in OBSTACLE_SPECS))


if __name__ == "__main__":
    unittest.main()
