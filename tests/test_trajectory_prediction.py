import math
import unittest

from navigation.trajectory_prediction import (
    CommandSegment,
    EPUCK_AXLE_LENGTH_M,
    EPUCK_WHEEL_RADIUS_M,
    normalize_angle,
    predict_command_conditioned_trajectory,
    predict_state_only_trajectory,
    wheel_commands_to_twist,
)


class StateOnlyTrajectoryTests(unittest.TestCase):
    def test_stationary(self):
        points = predict_state_only_trajectory(
            x=1.0,
            y=2.0,
            yaw_rad=0.5,
            linear_velocity_m_s=0.0,
            angular_velocity_rad_s=0.0,
            horizon_s=0.5,
            step_s=0.1,
        )
        self.assertAlmostEqual(points[-1].x, 1.0)
        self.assertAlmostEqual(points[-1].y, 2.0)
        self.assertAlmostEqual(points[-1].yaw_rad, 0.5)

    def test_straight(self):
        points = predict_state_only_trajectory(
            x=0.0,
            y=0.0,
            yaw_rad=0.0,
            linear_velocity_m_s=0.2,
            angular_velocity_rad_s=0.0,
            horizon_s=1.0,
            step_s=0.25,
        )
        self.assertAlmostEqual(points[-1].x, 0.2)
        self.assertAlmostEqual(points[-1].y, 0.0)

    def test_left_turn(self):
        points = predict_state_only_trajectory(
            x=0.0,
            y=0.0,
            yaw_rad=0.0,
            linear_velocity_m_s=0.1,
            angular_velocity_rad_s=1.0,
            horizon_s=1.0,
            step_s=0.5,
        )
        self.assertGreater(points[-1].y, 0.0)
        self.assertAlmostEqual(points[-1].yaw_rad, 1.0)

    def test_right_turn(self):
        points = predict_state_only_trajectory(
            x=0.0,
            y=0.0,
            yaw_rad=0.0,
            linear_velocity_m_s=0.1,
            angular_velocity_rad_s=-1.0,
            horizon_s=1.0,
            step_s=0.5,
        )
        self.assertLess(points[-1].y, 0.0)
        self.assertAlmostEqual(points[-1].yaw_rad, -1.0)

    def test_tiny_omega_uses_straight_model(self):
        points = predict_state_only_trajectory(
            x=0.0,
            y=0.0,
            yaw_rad=math.pi / 2,
            linear_velocity_m_s=0.1,
            angular_velocity_rad_s=1e-12,
            horizon_s=1.0,
            step_s=1.0,
        )
        self.assertAlmostEqual(points[-1].x, 0.0, places=9)
        self.assertAlmostEqual(points[-1].y, 0.1, places=9)

    def test_yaw_crosses_positive_pi(self):
        value = normalize_angle(math.pi + 0.1)
        self.assertAlmostEqual(value, -math.pi + 0.1)

    def test_yaw_crosses_negative_pi(self):
        value = normalize_angle(-math.pi - 0.1)
        self.assertAlmostEqual(value, math.pi - 0.1)

    def test_horizon_not_integer_multiple_of_step(self):
        points = predict_state_only_trajectory(
            x=0.0,
            y=0.0,
            yaw_rad=0.0,
            linear_velocity_m_s=1.0,
            angular_velocity_rad_s=0.0,
            horizon_s=0.35,
            step_s=0.2,
        )
        self.assertEqual([p.time_offset_s for p in points], [0.2, 0.35])

    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):
            predict_state_only_trajectory(
                x=0,
                y=0,
                yaw_rad=0,
                linear_velocity_m_s=0,
                angular_velocity_rad_s=0,
                horizon_s=0,
            )

    def test_invalid_step(self):
        with self.assertRaises(ValueError):
            predict_state_only_trajectory(
                x=0,
                y=0,
                yaw_rad=0,
                linear_velocity_m_s=0,
                angular_velocity_rad_s=0,
                horizon_s=1,
                step_s=0,
            )

    def test_nan_and_infinity_rejected(self):
        with self.assertRaises(ValueError):
            normalize_angle(float("nan"))
        with self.assertRaises(ValueError):
            predict_state_only_trajectory(
                x=float("inf"),
                y=0,
                yaw_rad=0,
                linear_velocity_m_s=0,
                angular_velocity_rad_s=0,
                horizon_s=1,
            )


class CommandConditionedTrajectoryTests(unittest.TestCase):
    def test_all_straight(self):
        segment = CommandSegment(0.0, 1.0, 2.0, 2.0)
        points = predict_command_conditioned_trajectory(
            x=0,
            y=0,
            yaw_rad=0,
            command_segments=[segment],
            horizon_s=1.0,
            step_s=0.5,
        )
        self.assertAlmostEqual(points[-1].x, EPUCK_WHEEL_RADIUS_M * 2.0)
        self.assertAlmostEqual(points[-1].y, 0.0)

    def test_straight_then_left(self):
        points = predict_command_conditioned_trajectory(
            x=0,
            y=0,
            yaw_rad=0,
            command_segments=[CommandSegment(0, 0.5, 2, 2), CommandSegment(0.5, 1.0, -1.5, 1.5)],
            horizon_s=1.0,
            step_s=0.5,
        )
        self.assertGreater(points[-1].yaw_rad, 0)

    def test_left_then_right(self):
        points = predict_command_conditioned_trajectory(
            x=0,
            y=0,
            yaw_rad=0,
            command_segments=[CommandSegment(0, 0.5, -1.5, 1.5), CommandSegment(0.5, 1.0, 1.5, -1.5)],
            horizon_s=1.0,
            step_s=0.5,
        )
        self.assertAlmostEqual(points[-1].yaw_rad, 0.0, places=6)

    def test_motion_then_stop(self):
        points = predict_command_conditioned_trajectory(
            x=0,
            y=0,
            yaw_rad=0,
            command_segments=[CommandSegment(0, 0.5, 2, 2), CommandSegment(0.5, 1.0, 0, 0)],
            horizon_s=1.0,
            step_s=0.5,
        )
        self.assertAlmostEqual(points[-1].x, EPUCK_WHEEL_RADIUS_M * 2.0 * 0.5)

    def test_window_crosses_multiple_segments(self):
        points = predict_command_conditioned_trajectory(
            x=0,
            y=0,
            yaw_rad=0,
            command_segments=[
                CommandSegment(0, 0.25, 2, 2),
                CommandSegment(0.25, 0.5, -1.5, 1.5),
                CommandSegment(0.5, 0.75, 1.5, -1.5),
                CommandSegment(0.75, 1.0, 0, 0),
            ],
            horizon_s=1.0,
            step_s=1.0,
        )
        self.assertEqual(len(points), 1)

    def test_gap_overlap_and_unsorted_rejected(self):
        bad_cases = [
            [CommandSegment(0, 0.4, 1, 1), CommandSegment(0.5, 1.0, 1, 1)],
            [CommandSegment(0, 0.6, 1, 1), CommandSegment(0.5, 1.0, 1, 1)],
            [CommandSegment(0.5, 1.0, 1, 1), CommandSegment(0, 0.5, 1, 1)],
        ]
        for segments in bad_cases:
            with self.subTest(segments=segments):
                with self.assertRaises(ValueError):
                    predict_command_conditioned_trajectory(
                        x=0,
                        y=0,
                        yaw_rad=0,
                        command_segments=segments,
                        horizon_s=1.0,
                    )

    def test_wheel_to_twist_sign(self):
        _, omega = wheel_commands_to_twist(-1.5, 1.5)
        self.assertGreater(omega, 0.0)
        _, omega = wheel_commands_to_twist(1.5, -1.5)
        self.assertLess(omega, 0.0)

    def test_equal_wheels_straight(self):
        v, omega = wheel_commands_to_twist(2.0, 2.0)
        self.assertAlmostEqual(v, EPUCK_WHEEL_RADIUS_M * 2.0)
        self.assertAlmostEqual(omega, 0.0)

    def test_opposite_wheels_rotate_in_place(self):
        v, omega = wheel_commands_to_twist(-1.0, 1.0)
        self.assertAlmostEqual(v, 0.0)
        self.assertAlmostEqual(omega, EPUCK_WHEEL_RADIUS_M * 2.0 / EPUCK_AXLE_LENGTH_M)


if __name__ == "__main__":
    unittest.main()
