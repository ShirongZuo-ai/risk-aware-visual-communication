import unittest

from navigation.trajectory_prediction import TrajectoryPoint
from risk_map.models import ObstacleFootprint, RiskParameters, TrajectorySource
from risk_map.trajectory_obstacle_risk import (
    analyze_dual_trajectory_obstacle,
    analyze_trajectory_obstacle,
    compute_trajectory_disagreement,
    interpolate_trajectory_position,
)


class TrajectoryObstacleRiskTests(unittest.TestCase):
    def setUp(self):
        self.parameters = RiskParameters(
            corridor_radius_m=0.5,
            sigma_distance_m=0.5,
            tau_time_s=1.0,
            maximum_horizon_s=5.0,
            geometry_tolerance_m=1e-9,
        )

    def test_analyze_trajectory_enters_corridor(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        trajectory = [TrajectoryPoint(0.0, -2.0, 0.0, 0.0), TrajectoryPoint(4.0, 2.0, 0.0, 0.0)]
        result = analyze_trajectory_obstacle(trajectory, obstacle, TrajectorySource.PLANNED, self.parameters)
        self.assertTrue(result.enters_corridor)
        self.assertAlmostEqual(result.minimum_centerline_distance_m, 0.0)
        self.assertAlmostEqual(result.minimum_clearance_m, -0.5)
        self.assertAlmostEqual(result.first_corridor_entry_time_s, 1.0)
        self.assertAlmostEqual(result.corridor_overlap_duration_s, 2.0)

    def test_analyze_trajectory_never_enters_reports_closest_time(self):
        obstacle = ObstacleFootprint("box", 0.0, 2.0, 1.0, 1.0)
        trajectory = [TrajectoryPoint(0.0, -2.0, 0.0, 0.0), TrajectoryPoint(4.0, 2.0, 0.0, 0.0)]
        result = analyze_trajectory_obstacle(trajectory, obstacle, TrajectorySource.STATE, self.parameters)
        self.assertFalse(result.enters_corridor)
        self.assertIsNone(result.first_corridor_entry_time_s)
        self.assertAlmostEqual(result.closest_time_s, 2.0)
        self.assertEqual(result.corridor_overlap_duration_s, 0.0)

    def test_large_obstacle_edge_enters_while_center_outside(self):
        obstacle = ObstacleFootprint("wide", 5.0, 1.2, 2.0, 2.0)
        trajectory = [TrajectoryPoint(0.0, 0.0, 0.0, 0.0), TrajectoryPoint(5.0, 10.0, 0.0, 0.0)]
        result = analyze_trajectory_obstacle(trajectory, obstacle, TrajectorySource.PLANNED, self.parameters)
        self.assertTrue(result.enters_corridor)
        self.assertLess(result.minimum_clearance_m, 0.0)

    def test_tangent_boundary_enters_with_tolerance(self):
        obstacle = ObstacleFootprint("tangent", 0.0, 1.0, 1.0, 1.0)
        trajectory = [TrajectoryPoint(0.0, -1.0, 0.0, 0.0), TrajectoryPoint(2.0, 1.0, 0.0, 0.0)]
        result = analyze_trajectory_obstacle(trajectory, obstacle, TrajectorySource.PLANNED, self.parameters)
        self.assertTrue(result.enters_corridor)
        self.assertAlmostEqual(result.minimum_clearance_m, 0.0)

    def test_single_point_trajectory(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        trajectory = [TrajectoryPoint(2.0, 0.0, 0.0, 0.0)]
        result = analyze_trajectory_obstacle(trajectory, obstacle, TrajectorySource.STATE, self.parameters)
        self.assertTrue(result.enters_corridor)
        self.assertAlmostEqual(result.closest_time_s, 2.0)
        self.assertAlmostEqual(result.first_corridor_entry_time_s, 2.0)
        self.assertAlmostEqual(result.corridor_overlap_duration_s, 0.0)

    def test_interpolate_trajectory_position(self):
        trajectory = [TrajectoryPoint(0.0, 0.0, 0.0, 0.0), TrajectoryPoint(2.0, 2.0, 4.0, 0.0)]
        self.assertEqual(interpolate_trajectory_position(trajectory, 1.0), (1.0, 2.0))
        with self.assertRaises(ValueError):
            interpolate_trajectory_position(trajectory, 3.0)

    def test_trajectory_disagreement_with_different_sampling(self):
        planned = [TrajectoryPoint(0.0, 0.0, 0.0, 0.0), TrajectoryPoint(2.0, 2.0, 0.0, 0.0)]
        state = [
            TrajectoryPoint(0.0, 0.0, 0.0, 0.0),
            TrajectoryPoint(1.0, 1.0, 1.0, 0.0),
            TrajectoryPoint(2.0, 2.0, 2.0, 0.0),
        ]
        self.assertAlmostEqual(compute_trajectory_disagreement(planned, planned), 0.0)
        self.assertAlmostEqual(compute_trajectory_disagreement(planned, state), 2.0)

    def test_trajectory_disagreement_no_common_range_errors(self):
        planned = [TrajectoryPoint(0.0, 0.0, 0.0, 0.0), TrajectoryPoint(1.0, 1.0, 0.0, 0.0)]
        state = [TrajectoryPoint(2.0, 0.0, 0.0, 0.0), TrajectoryPoint(3.0, 1.0, 0.0, 0.0)]
        with self.assertRaises(ValueError):
            compute_trajectory_disagreement(planned, state)

    def test_dual_trajectory_analysis(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        planned = [TrajectoryPoint(0.0, -2.0, 0.0, 0.0), TrajectoryPoint(4.0, 2.0, 0.0, 0.0)]
        state = [TrajectoryPoint(0.0, -2.0, 2.0, 0.0), TrajectoryPoint(4.0, 2.0, 2.0, 0.0)]
        result = analyze_dual_trajectory_obstacle(planned, state, obstacle, self.parameters)
        self.assertEqual(result.planned_result.trajectory_source, TrajectorySource.PLANNED)
        self.assertEqual(result.state_result.trajectory_source, TrajectorySource.STATE)
        self.assertAlmostEqual(
            result.combined_risk_score,
            max(result.planned_result.risk_score, result.state_result.risk_score),
        )
        self.assertGreater(result.trajectory_disagreement_m, 0.0)

    def test_invalid_trajectory_inputs(self):
        obstacle = ObstacleFootprint("box", 0.0, 0.0, 1.0, 1.0)
        too_long = [TrajectoryPoint(0.0, 0, 0, 0), TrajectoryPoint(6.0, 1, 0, 0)]
        with self.assertRaises(ValueError):
            analyze_trajectory_obstacle(too_long, obstacle, TrajectorySource.PLANNED, self.parameters)
        with self.assertRaises(ValueError):
            analyze_trajectory_obstacle([], obstacle, TrajectorySource.PLANNED, self.parameters)


if __name__ == "__main__":
    unittest.main()
