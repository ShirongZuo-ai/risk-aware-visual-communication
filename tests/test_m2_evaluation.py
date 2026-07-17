import unittest

from scripts.evaluate_m2_trajectory import (
    PROFILES,
    TRANSITION_GUARD_END_S,
    TRANSITION_GUARD_START_S,
    category_for_window,
    command_segments_for_window,
)


class M2EvaluationTests(unittest.TestCase):
    def test_arc_transition_guard_marks_only_post_switch_guard(self):
        profile = PROFILES["arc"]
        transition = category_for_window(7.90, 0.30, profile)
        self.assertEqual(transition, "transition_forward_left_arc_to_forward_right_arc")
        self.assertIsNone(category_for_window(4.032, 0.05, profile))
        self.assertEqual(category_for_window(4.224, 0.5, profile), "stable_forward_left_arc")

    def test_transition_guard_constants_match_documented_window(self):
        self.assertAlmostEqual(TRANSITION_GUARD_START_S, 0.10)
        self.assertAlmostEqual(TRANSITION_GUARD_END_S, 0.20)

    def test_arc_command_segments_use_forward_arc_commands(self):
        segments = command_segments_for_window(3.8, 1.0, PROFILES["arc"])
        commands = [(segment.left_wheel_command_rad_s, segment.right_wheel_command_rad_s) for segment in segments]
        self.assertIn((2.0, 2.0), commands)
        self.assertIn((1.0, 2.0), commands)


if __name__ == "__main__":
    unittest.main()
