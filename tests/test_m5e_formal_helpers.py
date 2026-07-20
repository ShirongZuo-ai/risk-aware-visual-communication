from __future__ import annotations

import unittest

from scripts.m5e_formal_evaluation_common import (
    EXPECTED_FORMAL_FRAMES,
    EXPECTED_FORMAL_RECONSTRUCTIONS,
    EXPECTED_FROZEN_BUDGETS,
    expected_result_count,
    metadata_normalized_sha256,
    validate_frozen_budget_manifest,
)
from scripts.run_m5e_formal_dataset import planned_formal_configs
from simulator.m5e_config import primary_seed, primary_seed_indices, replacement_seed


class M5EFormalHelperTests(unittest.TestCase):
    def test_planned_formal_protocol_has_64_disjoint_primary_episodes(self) -> None:
        configs = planned_formal_configs()
        self.assertEqual(len(configs), 64)
        self.assertEqual({config.split for config in configs}, {"formal"})
        expected = {
            primary_seed("formal", scenario_index, seed_index)
            for scenario_index in range(1, 9)
            for seed_index in primary_seed_indices("formal")
        }
        self.assertEqual({config.seed for config in configs}, expected)
        calibration = {
            primary_seed("calibration", scenario_index, seed_index)
            for scenario_index in range(1, 9)
            for seed_index in primary_seed_indices("calibration")
        }
        self.assertFalse(expected & calibration)

    def test_formal_replacement_pool_uses_reserved_non_overlapping_offsets(self) -> None:
        replacements = {replacement_seed("formal", 3, index) for index in range(30)}
        primary = {primary_seed("formal", 3, seed_index) for seed_index in primary_seed_indices("formal")}
        self.assertEqual(min(replacements), 200350)
        self.assertEqual(max(replacements), 200379)
        self.assertFalse(replacements & primary)

    def test_expected_formal_matrix_size_is_4096(self) -> None:
        self.assertEqual(expected_result_count(EXPECTED_FORMAL_FRAMES), EXPECTED_FORMAL_RECONSTRUCTIONS)
        self.assertEqual(EXPECTED_FORMAL_RECONSTRUCTIONS, 4096)

    def test_frozen_budget_manifest_values_are_guarded(self) -> None:
        validate_frozen_budget_manifest(
            {
                "L_common": 31240,
                "U_common": 35779,
                "budgets": EXPECTED_FROZEN_BUDGETS,
                "actual_future_trajectory_used": False,
            }
        )
        with self.assertRaises(ValueError):
            validate_frozen_budget_manifest(
                {
                    "L_common": 31240,
                    "U_common": 35779,
                    "budgets": {**EXPECTED_FROZEN_BUDGETS, "high": 34872},
                    "actual_future_trajectory_used": False,
                }
            )

    def test_metadata_hash_ignores_path_only_fields(self) -> None:
        left = {"frame_path": "a.png", "nested": {"masks_path": "a.json", "value": 3}}
        right = {"frame_path": "b.png", "nested": {"masks_path": "b.json", "value": 3}}
        changed = {"frame_path": "b.png", "nested": {"masks_path": "b.json", "value": 4}}
        self.assertEqual(metadata_normalized_sha256(left), metadata_normalized_sha256(right))
        self.assertNotEqual(metadata_normalized_sha256(left), metadata_normalized_sha256(changed))


if __name__ == "__main__":
    unittest.main()
