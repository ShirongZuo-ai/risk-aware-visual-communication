from __future__ import annotations

import unittest

from simulator.m5e_config import SCENARIO_IDS, primary_seed, replacement_seed
from simulator.m5e_scenarios import config_hash, generate_scenario, validate_config


class M5EScenarioTests(unittest.TestCase):
    def test_all_smoke_scenarios_are_deterministic(self) -> None:
        for index, scenario_id in enumerate(SCENARIO_IDS, start=1):
            seed = primary_seed("smoke", index, 0)
            first = generate_scenario(scenario_id, "smoke", seed)
            second = generate_scenario(scenario_id, "smoke", seed)
            self.assertEqual(first, second)
            self.assertEqual(config_hash(first), config_hash(second))

    def test_all_obstacles_are_static_unrotated_aabbs(self) -> None:
        for index, scenario_id in enumerate(SCENARIO_IDS, start=1):
            config = generate_scenario(scenario_id, "smoke", primary_seed("smoke", index, 0))
            validate_config(config)
            self.assertTrue(config.obstacle_specs)
            self.assertTrue(all(item.orientation == (0.0, 0.0, 1.0, 0.0) for item in config.obstacle_specs))

    def test_snapshot_progress_targets_are_frozen(self) -> None:
        config = generate_scenario("S1", "smoke", 9001)
        self.assertEqual(config.snapshot_progress_targets, (0.20, 0.45, 0.70, 0.90))

    def test_s3_s4_are_mirrored(self) -> None:
        left = generate_scenario("S3", "smoke", 9003)
        right = generate_scenario("S4", "smoke", 9004)
        self.assertEqual(tuple(abs(item.left_rad_s) for item in left.command_schedule), tuple(abs(item.right_rad_s) for item in right.command_schedule))
        self.assertEqual(tuple(abs(item.right_rad_s) for item in left.command_schedule), tuple(abs(item.left_rad_s) for item in right.command_schedule))

    def test_s5_has_distinct_branch_roles(self) -> None:
        config = generate_scenario("S5", "smoke", 9005)
        roles = {item.role for item in config.obstacle_specs}
        self.assertIn("planned_branch_obstacle", roles)
        self.assertIn("state_branch_obstacle", roles)

    def test_primary_seed_namespaces_are_disjoint(self) -> None:
        calibration = {primary_seed("calibration", index, seed_index) for index in range(1, 9) for seed_index in (0, 1)}
        formal = {primary_seed("formal", index, seed_index) for index in range(1, 9) for seed_index in range(8)}
        smoke = {primary_seed("smoke", index, 0) for index in range(1, 9)}
        self.assertFalse(calibration & formal)
        self.assertFalse(calibration & smoke)
        self.assertFalse(formal & smoke)

    def test_replacement_seeds_are_ascending_and_distinct(self) -> None:
        values = [replacement_seed("smoke", 5, index) for index in range(8)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(len(values), len(set(values)))

    def test_calibration_and_formal_boundary_configs_are_valid(self) -> None:
        for scenario_index, scenario_id in enumerate(SCENARIO_IDS, start=1):
            for split, indices in (("calibration", (0, 1)), ("formal", (0, 7))):
                for seed_index in indices:
                    validate_config(generate_scenario(scenario_id, split, primary_seed(split, scenario_index, seed_index)))


if __name__ == "__main__":
    unittest.main()
