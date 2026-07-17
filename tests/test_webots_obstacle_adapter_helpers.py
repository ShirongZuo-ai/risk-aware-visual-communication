import math
import unittest

from simulator.adapters.webots_obstacle_adapter import obstacle_from_box_fields


class WebotsObstacleAdapterHelperTests(unittest.TestCase):
    def test_obstacle_from_box_fields_maps_world_xy_and_size(self):
        obstacle = obstacle_from_box_fields(
            obstacle_id="BOX",
            translation=(0.3, -0.2, 0.025),
            rotation=(0.0, 0.0, 1.0, 0.0),
            size=(0.04, 0.06, 0.05),
        )

        self.assertEqual(obstacle.obstacle_id, "BOX")
        self.assertAlmostEqual(obstacle.center_x, 0.3)
        self.assertAlmostEqual(obstacle.center_y, -0.2)
        self.assertAlmostEqual(obstacle.size_x, 0.04)
        self.assertAlmostEqual(obstacle.size_y, 0.06)
        self.assertAlmostEqual(obstacle.min_x, 0.28)
        self.assertAlmostEqual(obstacle.max_y, -0.17)

    def test_rejects_planar_rotation(self):
        with self.assertRaises(ValueError):
            obstacle_from_box_fields(
                obstacle_id="ROTATED",
                translation=(0.0, 0.0, 0.025),
                rotation=(0.0, 0.0, 1.0, 0.1),
                size=(0.04, 0.04, 0.05),
            )

    def test_rejects_nonfinite_or_nonpositive_size(self):
        with self.assertRaises(ValueError):
            obstacle_from_box_fields(
                obstacle_id="BAD",
                translation=(math.nan, 0.0, 0.025),
                rotation=(0.0, 0.0, 1.0, 0.0),
                size=(0.04, 0.04, 0.05),
            )
        with self.assertRaises(ValueError):
            obstacle_from_box_fields(
                obstacle_id="BAD",
                translation=(0.0, 0.0, 0.025),
                rotation=(0.0, 0.0, 1.0, 0.0),
                size=(0.0, 0.04, 0.05),
            )


if __name__ == "__main__":
    unittest.main()
