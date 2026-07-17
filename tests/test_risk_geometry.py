import unittest

from navigation.trajectory_prediction import TrajectoryPoint
from risk_map.geometry import (
    corridor_intervals_for_trajectory,
    point_to_aabb_distance,
    point_to_segment_distance,
    polyline_to_aabb_closest,
    segment_aabb_intersection_interval,
    segment_intersects_aabb,
    segment_to_aabb_distance,
    summarize_corridor_intervals,
    validate_trajectory,
)
from risk_map.models import ObstacleFootprint


class RiskGeometryTests(unittest.TestCase):
    def test_point_to_segment_distance_on_segment(self):
        result = point_to_segment_distance(1.0, 0.0, 0.0, 0.0, 2.0, 0.0)
        self.assertAlmostEqual(result.distance_m, 0.0)
        self.assertAlmostEqual(result.u, 0.5)
        self.assertAlmostEqual(result.closest_x, 1.0)

    def test_point_to_segment_distance_outside_endpoint(self):
        result = point_to_segment_distance(3.0, 1.0, 0.0, 0.0, 2.0, 0.0)
        self.assertAlmostEqual(result.u, 1.0)
        self.assertAlmostEqual(result.closest_x, 2.0)
        self.assertAlmostEqual(result.distance_m, 2 ** 0.5)

    def test_horizontal_vertical_and_zero_length_segments(self):
        horizontal = point_to_segment_distance(1.0, 2.0, 0.0, 0.0, 4.0, 0.0)
        vertical = point_to_segment_distance(2.0, 1.0, 0.0, 0.0, 0.0, 4.0)
        zero = point_to_segment_distance(1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(horizontal.distance_m, 2.0)
        self.assertAlmostEqual(vertical.distance_m, 2.0)
        self.assertAlmostEqual(zero.u, 0.0)
        self.assertAlmostEqual(zero.distance_m, 2 ** 0.5)

    def test_point_to_aabb_distance_inside_and_outside(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 2.0, 2.0)
        self.assertAlmostEqual(point_to_aabb_distance(0.5, 0.5, obstacle), 0.0)
        self.assertAlmostEqual(point_to_aabb_distance(3.0, 0.0, obstacle), 2.0)

    def test_segment_intersects_aabb_cases(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 2.0, 2.0)
        self.assertTrue(segment_intersects_aabb(-2.0, 0.0, 2.0, 0.0, obstacle))
        self.assertTrue(segment_intersects_aabb(0.0, 0.0, 3.0, 3.0, obstacle))
        self.assertTrue(segment_intersects_aabb(-2.0, 1.0, 2.0, 1.0, obstacle))
        self.assertFalse(segment_intersects_aabb(-2.0, 2.0, 2.0, 2.0, obstacle))
        self.assertTrue(segment_intersects_aabb(0.5, 0.5, 0.5, 0.5, obstacle))

    def test_segment_to_aabb_distance_uses_segment_middle(self):
        obstacle = ObstacleFootprint("box", 2.0, 0.0, 1.0, 1.0)
        result = segment_to_aabb_distance(0.0, 2.0, 4.0, 2.0, obstacle)
        self.assertAlmostEqual(result.distance_m, 1.5)
        self.assertAlmostEqual(result.u, 0.5)
        self.assertAlmostEqual(result.closest_x, 2.0)

    def test_segment_aabb_intersection_interval_with_inflation(self):
        obstacle = ObstacleFootprint("box", 0.5, 0.5, 1.0, 1.0)
        interval = segment_aabb_intersection_interval(-1.0, 0.5, 2.0, 0.5, obstacle)
        self.assertIsNotNone(interval)
        self.assertAlmostEqual(interval[0], 1.0 / 3.0)
        self.assertAlmostEqual(interval[1], 2.0 / 3.0)
        inflated = segment_aabb_intersection_interval(-1.0, 0.5, 2.0, 0.5, obstacle, inflation_radius_m=0.5)
        self.assertAlmostEqual(inflated[0], 1.0 / 6.0)
        self.assertAlmostEqual(inflated[1], 5.0 / 6.0)

    def test_segment_aabb_interval_edge_cases(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 2.0, 2.0)
        self.assertEqual(segment_aabb_intersection_interval(0.0, 0.0, 0.0, 0.0, obstacle), (0.0, 0.0))
        self.assertIsNone(segment_aabb_intersection_interval(3.0, 3.0, 3.0, 3.0, obstacle))
        self.assertIsNone(segment_aabb_intersection_interval(-2.0, 2.0, 2.0, 2.0, obstacle))
        self.assertIsNotNone(segment_aabb_intersection_interval(-2.0, 1.0, 2.0, 1.0, obstacle))

    def test_polyline_closest_time_uses_segment_interpolation(self):
        obstacle = ObstacleFootprint("box", 2.0, 0.0, 1.0, 1.0)
        trajectory = [
            TrajectoryPoint(0.0, 0.0, 2.0, 0.0),
            TrajectoryPoint(4.0, 4.0, 2.0, 0.0),
        ]
        closest = polyline_to_aabb_closest(trajectory, obstacle)
        self.assertAlmostEqual(closest.distance_m, 1.5)
        self.assertAlmostEqual(closest.closest_time_s, 2.0)
        self.assertEqual(closest.segment_index, 0)

    def test_corridor_intervals_and_overlap_duration(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        trajectory = [
            TrajectoryPoint(0.0, -2.0, 0.0, 0.0),
            TrajectoryPoint(4.0, 2.0, 0.0, 0.0),
        ]
        intervals = corridor_intervals_for_trajectory(trajectory, obstacle, 0.5)
        self.assertEqual(len(intervals), 1)
        self.assertAlmostEqual(intervals[0][0], 1.0)
        self.assertAlmostEqual(intervals[0][1], 3.0)
        summary = summarize_corridor_intervals(intervals)
        self.assertAlmostEqual(summary.first_entry_time_s, 1.0)
        self.assertAlmostEqual(summary.overlap_duration_s, 2.0)

    def test_corridor_multiple_entries_and_never_enters(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        trajectory = [
            TrajectoryPoint(0.0, -3.0, 0.0, 0.0),
            TrajectoryPoint(1.0, 0.0, 0.0, 0.0),
            TrajectoryPoint(2.0, 3.0, 0.0, 0.0),
            TrajectoryPoint(3.0, 3.0, 3.0, 0.0),
            TrajectoryPoint(4.0, 0.0, 0.0, 0.0),
        ]
        intervals = corridor_intervals_for_trajectory(trajectory, obstacle, 0.0)
        summary = summarize_corridor_intervals(intervals)
        self.assertAlmostEqual(summary.first_entry_time_s, 5.0 / 6.0)
        self.assertGreater(summary.overlap_duration_s, 0.0)
        never = corridor_intervals_for_trajectory(
            [TrajectoryPoint(0.0, 3.0, 3.0, 0.0), TrajectoryPoint(1.0, 4.0, 3.0, 0.0)],
            obstacle,
            0.0,
        )
        self.assertEqual(never, [])
        self.assertIsNone(summarize_corridor_intervals(never).first_entry_time_s)

    def test_single_point_trajectory_and_time_validation(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        inside = [TrajectoryPoint(2.0, 0.0, 0.0, 0.0)]
        outside = [TrajectoryPoint(2.0, 3.0, 3.0, 0.0)]
        self.assertEqual(corridor_intervals_for_trajectory(inside, obstacle, 0.0), [(2.0, 2.0)])
        self.assertEqual(corridor_intervals_for_trajectory(outside, obstacle, 0.0), [])
        with self.assertRaises(ValueError):
            validate_trajectory([TrajectoryPoint(2.0, 0, 0, 0), TrajectoryPoint(1.0, 1, 0, 0)])


if __name__ == "__main__":
    unittest.main()
