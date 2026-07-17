import unittest

from navigation.trajectory_prediction import EPUCK_ROBOT_HALF_WIDTH_M
from navigation.trajectory_uncertainty import (
    ErrorSample,
    corridor_radius,
    position_error,
    quantile,
    summarize_corridors,
    trajectory_corridor_disks,
)


class TrajectoryUncertaintyTests(unittest.TestCase):
    def test_quantile(self):
        self.assertAlmostEqual(quantile([0, 1, 2, 3, 4], 0.5), 2.0)
        self.assertAlmostEqual(quantile([0, 10], 0.9), 9.0)

    def test_insufficient_samples(self):
        summaries = summarize_corridors(
            [ErrorSample("state_only", 1.0, "stable", 1.0, 0.1)],
            horizons_s=[1.0],
            methods=["state_only"],
            min_samples=5,
        )
        self.assertEqual(summaries[0].status, "insufficient_data")
        self.assertIsNone(summaries[0].corridor_radius_m)

    def test_corridor_not_less_than_robot_half_width(self):
        radius = corridor_radius(0.0, safety_margin_m=0.0)
        self.assertGreaterEqual(radius, EPUCK_ROBOT_HALF_WIDTH_M)

    def test_invalid_error_data(self):
        with self.assertRaises(ValueError):
            position_error(float("nan"), 0, 0, 0)
        with self.assertRaises(ValueError):
            corridor_radius(-0.1)
        with self.assertRaises(ValueError):
            quantile([], 0.5)

    def test_units_stay_in_meters(self):
        samples = [ErrorSample("command_conditioned", 0.5, "stable", 0.5, value) for value in [0.01, 0.02, 0.03, 0.04, 0.05]]
        summaries = summarize_corridors(samples, horizons_s=[0.5], methods=["command_conditioned"], min_samples=5)
        summary = summaries[0]
        self.assertEqual(summary.status, "ok")
        self.assertAlmostEqual(summary.position_error_p50_m, 0.03)
        self.assertAlmostEqual(summary.corridor_radius_m, EPUCK_ROBOT_HALF_WIDTH_M + 0.046 + 0.01)

    def test_trajectory_corridor_is_disk_union_along_path(self):
        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        points = [Point(0.0, 0.0), Point(0.1, 0.02), Point(0.2, 0.08)]
        disks = trajectory_corridor_disks(points, 0.04)
        self.assertEqual(len(disks), len(points))
        self.assertEqual([(disk.center_x, disk.center_y) for disk in disks], [(0.0, 0.0), (0.1, 0.02), (0.2, 0.08)])
        self.assertTrue(all(disk.radius_m == 0.04 for disk in disks))

    def test_trajectory_corridor_rejects_invalid_geometry(self):
        with self.assertRaises(ValueError):
            trajectory_corridor_disks([], 0.04)
        with self.assertRaises(ValueError):
            trajectory_corridor_disks([object()], 0.04)
        with self.assertRaises(ValueError):
            trajectory_corridor_disks([type("Point", (), {"x": 0.0, "y": 0.0})()], 0.0)


if __name__ == "__main__":
    unittest.main()
