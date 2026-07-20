from __future__ import annotations

import unittest

from simulator.m5e_scenarios import generate_scenario
from simulator.m5e_snapshot_protocol import build_trajectories, command_phase_at, future_command_segments, next_crossing, reference_progress


class M5ESnapshotProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = generate_scenario("S5", "smoke", 9005)

    def test_reference_progress_is_time_based_and_clipped(self) -> None:
        self.assertEqual(reference_progress(self.config, -1.0), 0.0)
        self.assertAlmostEqual(reference_progress(self.config, 3.0), 0.5)
        self.assertEqual(reference_progress(self.config, 9.0), 1.0)

    def test_crossing_uses_first_step_at_or_after_target(self) -> None:
        self.assertIsNone(next_crossing(self.config, set(), 1.19, 37))
        crossing = next_crossing(self.config, set(), 1.216, 38)
        self.assertIsNotNone(crossing)
        assert crossing is not None
        self.assertEqual(crossing.snapshot_index, 0)
        self.assertGreaterEqual(crossing.actual_progress, crossing.target_progress)

    def test_completed_crossings_are_not_repeated(self) -> None:
        crossing = next_crossing(self.config, {0, 1}, 4.224, 132)
        self.assertIsNotNone(crossing)
        assert crossing is not None
        self.assertEqual(crossing.snapshot_index, 2)

    def test_future_schedule_covers_full_horizon(self) -> None:
        segments = future_command_segments(self.config, 4.224)
        self.assertAlmostEqual(segments[0].start_offset_s, 0.0)
        self.assertAlmostEqual(segments[-1].end_offset_s, self.config.trajectory_horizon_s)

    def test_command_phase_is_determined_only_by_snapshot_time(self) -> None:
        before = command_phase_at(self.config, 4.224)
        after = command_phase_at(self.config, 4.3)
        self.assertNotEqual(before.name, after.name)

    def test_both_trajectory_models_share_snapshot_state(self) -> None:
        state = {"x": 0.08, "y": 0.07, "yaw_rad": 1.4, "linear_velocity_m_s": 0.03, "angular_velocity_rad_s": 0.35}
        planned, state_only = build_trajectories(self.config, state, 4.224)
        self.assertEqual(len(planned), len(state_only))
        self.assertEqual(planned[-1].time_offset_s, self.config.trajectory_horizon_s)
        self.assertEqual(state_only[-1].time_offset_s, self.config.trajectory_horizon_s)


if __name__ == "__main__":
    unittest.main()
