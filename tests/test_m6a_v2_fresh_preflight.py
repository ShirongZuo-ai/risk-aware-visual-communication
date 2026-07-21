import tempfile
import unittest
from pathlib import Path

from scripts.m6a_v2_fresh_preflight import run_fresh_preflight


class FreshPreflightTests(unittest.TestCase):
    def test_control_preflight_never_authorizes_or_creates_attempt_root(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_fresh_preflight(report_root=Path(directory) / "control")
            self.assertFalse(report["authorization_generated"])
            self.assertFalse(report["execution_authorized"])
            self.assertFalse(report["launch_performed"])
            self.assertFalse(report["webots_started"])
            self.assertFalse(report["scientific_result"])
            self.assertEqual(report["gates"]["attempt_specific_output_root"], "FAIL")
            self.assertFalse(Path(report["prospective_output_root"]).exists())
            self.assertTrue((Path(directory) / "control" / "fresh_preflight.json").is_file())
