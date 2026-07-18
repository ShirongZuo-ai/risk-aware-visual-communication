from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

from simulator.m5e_physics_diagnostics import (
    PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE,
    diagnostics_path,
    robot_obstacle_relation,
    roll_pitch_yaw,
)


class M5EPhysicsDiagnosticsTests(unittest.TestCase):
    def test_controller_does_not_query_internal_proto_node_ids(self) -> None:
        controller = Path(__file__).resolve().parents[1] / "simulator" / "controllers" / "m5e_dataset_generator" / "m5e_dataset_generator.py"
        source = controller.read_text(encoding="utf-8")
        self.assertNotIn("getFromProtoDef(", source)
        self.assertIn('robot_part_node_ids = {"body": int(self_node.getId())}', source)

    def test_identity_orientation_has_zero_roll_pitch_yaw(self) -> None:
        self.assertEqual(roll_pitch_yaw((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)), (0.0, -0.0, 0.0))

    def test_yaw_rotation_is_recovered(self) -> None:
        angle = 0.75
        orientation = (math.cos(angle), -math.sin(angle), 0.0, math.sin(angle), math.cos(angle), 0.0, 0.0, 0.0, 1.0)
        roll, pitch, yaw = roll_pitch_yaw(orientation)
        self.assertAlmostEqual(roll, 0.0)
        self.assertAlmostEqual(pitch, 0.0)
        self.assertAlmostEqual(yaw, angle)

    def test_relation_detects_clearance_and_overlap(self) -> None:
        clear = robot_obstacle_relation(0.0, 0.0, 0.0, (0.10, 0.0, 0.03), (0.02, 0.02, 0.06))
        self.assertAlmostEqual(clear["body_surface_clearance_m"], 0.053)
        self.assertFalse(clear["aabb_overlap"])
        self.assertFalse(clear["cylinder_box_overlap"])
        overlap = robot_obstacle_relation(0.0, 0.0, 0.0, (0.04, 0.0, 0.03), (0.02, 0.02, 0.06))
        self.assertLess(overlap["body_surface_clearance_m"], 0.0)
        self.assertTrue(overlap["aabb_overlap"])
        self.assertTrue(overlap["cylinder_box_overlap"])

    def test_diagnostics_path_must_be_project_relative_and_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory).resolve()
            environment = {PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE: "data/trace.jsonl"}
            self.assertEqual(diagnostics_path(environment, project_root), project_root / "data" / "trace.jsonl")
            with self.assertRaises(ValueError):
                diagnostics_path({PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE: "../outside.jsonl"}, project_root)
            with self.assertRaises(ValueError):
                diagnostics_path({PHYSICS_DIAGNOSTICS_ENVIRONMENT_VARIABLE: str(project_root / "absolute.jsonl")}, project_root)


if __name__ == "__main__":
    unittest.main()
