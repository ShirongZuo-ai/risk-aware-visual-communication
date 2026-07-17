import math
import unittest

from risk_map.models import (
    DualTrajectoryRiskResult,
    ObstacleFootprint,
    RiskParameters,
    TrajectoryConflictResult,
    TrajectorySource,
)


class RiskModelTests(unittest.TestCase):
    def test_obstacle_bounds(self):
        obstacle = ObstacleFootprint("box", 2.0, 3.0, 0.4, 0.8)
        self.assertAlmostEqual(obstacle.min_x, 1.8)
        self.assertAlmostEqual(obstacle.max_x, 2.2)
        self.assertAlmostEqual(obstacle.min_y, 2.6)
        self.assertAlmostEqual(obstacle.max_y, 3.4)

    def test_obstacle_validation(self):
        with self.assertRaises(ValueError):
            ObstacleFootprint("", 0.0, 0.0, 1.0, 1.0)
        with self.assertRaises(ValueError):
            ObstacleFootprint("bad", 0.0, 0.0, 0.0, 1.0)
        with self.assertRaises(ValueError):
            ObstacleFootprint("bad", 0.0, 0.0, 1.0, -1.0)
        with self.assertRaises(ValueError):
            ObstacleFootprint("bad", math.nan, 0.0, 1.0, 1.0)
        with self.assertRaises(ValueError):
            ObstacleFootprint("bad", 0.0, math.inf, 1.0, 1.0)

    def test_risk_parameters_validation(self):
        RiskParameters(0.2, 0.5, 1.0, 2.0, 0.0)
        bad_values = [
            (0.0, 0.5, 1.0, 2.0, 0.0),
            (0.2, 0.0, 1.0, 2.0, 0.0),
            (0.2, 0.5, 0.0, 2.0, 0.0),
            (0.2, 0.5, 1.0, 0.0, 0.0),
            (0.2, 0.5, 1.0, 2.0, -1e-3),
            (math.nan, 0.5, 1.0, 2.0, 0.0),
        ]
        for values in bad_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    RiskParameters(*values)

    def test_conflict_result_none_semantics(self):
        TrajectoryConflictResult(
            "box",
            TrajectorySource.PLANNED,
            1.0,
            0.8,
            0.5,
            False,
            None,
            0.0,
            0.2,
            0.3,
            0.06,
        )
        with self.assertRaises(ValueError):
            TrajectoryConflictResult("box", TrajectorySource.PLANNED, 0, -0.1, 0, True, None, 0, 1, 1, 1)
        with self.assertRaises(ValueError):
            TrajectoryConflictResult("box", TrajectorySource.PLANNED, 1, 1, 0, False, 0.1, 0, 1, 1, 1)
        with self.assertRaises(ValueError):
            TrajectoryConflictResult("box", TrajectorySource.PLANNED, 1, 1, 0, False, None, 0, 1, 1, 1.5)

    def test_dual_result_validation(self):
        planned = TrajectoryConflictResult("box", TrajectorySource.PLANNED, 0, -0.1, 0, True, 0, 0.5, 1, 1, 1)
        state = TrajectoryConflictResult("box", TrajectorySource.STATE, 1, 0.8, 1, False, None, 0, 0.2, 0.5, 0.1)
        DualTrajectoryRiskResult("box", planned, state, 0.3, 1.0)
        with self.assertRaises(ValueError):
            DualTrajectoryRiskResult("other", planned, state, 0.3, 1.0)
        with self.assertRaises(ValueError):
            DualTrajectoryRiskResult("box", state, planned, 0.3, 1.0)


if __name__ == "__main__":
    unittest.main()
