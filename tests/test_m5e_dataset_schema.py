from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from scripts.m5e_dataset_common import resolve_output_root
from simulator.m5e_dataset_schema import MANIFEST_FIELDS, episode_id, episode_summary, read_manifest, write_manifest
from simulator.m5e_scenarios import config_hash, generate_scenario


class M5EDatasetSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = generate_scenario("S5", "smoke", 9005)

    def test_episode_id_records_original_actual_and_replacement(self) -> None:
        value = episode_id(self.config, original_seed=9005, replacement_index=2)
        self.assertEqual(value, "m5e_smoke_s5_seed9005_actual9005_replacement02")

    def test_episode_summary_marks_no_future_actual(self) -> None:
        summary = episode_summary(self.config, original_seed=9005, replacement_index=0, status="captured", snapshots=[])
        self.assertFalse(summary["actual_future_trajectory_used"])
        self.assertEqual(summary["config_hash"], config_hash(self.config))

    def test_manifest_is_stably_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            rows = []
            for scenario, seed, snapshot in (("S2", 9002, 1), ("S1", 9001, 3), ("S1", 9001, 0)):
                row = {field: "" for field in MANIFEST_FIELDS}
                row.update({"split": "smoke", "scenario_id": scenario, "actual_seed": seed, "snapshot_index": snapshot})
                rows.append(row)
            write_manifest(rows, path)
            loaded = read_manifest(path)
            self.assertEqual([(row["scenario_id"], row["snapshot_index"]) for row in loaded], [("S1", "0"), ("S1", "3"), ("S2", "1")])

    def test_manifest_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            path.write_text("wrong\nvalue\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_manifest(path)

    def test_output_root_must_be_repository_relative(self) -> None:
        with self.assertRaises(ValueError):
            resolve_output_root(str(Path("C:/outside")))

    def test_output_root_cannot_escape_repository(self) -> None:
        with self.assertRaises(ValueError):
            resolve_output_root("../outside")


if __name__ == "__main__":
    unittest.main()
