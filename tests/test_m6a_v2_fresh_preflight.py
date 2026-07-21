import tempfile
import unittest
from pathlib import Path

from scripts.m6a_v2_fresh_preflight import run_fresh_preflight, persist_fresh_preflight_report, load_fresh_preflight_report
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from unittest.mock import patch


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
    def test_authoritative_package_report_round_trip_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.m6a_v2_execution_safety.PILOT_ROOT',Path(directory)/'pilot'):
            package_path,_=build_prepared_launch_package(head='h',branch='main',attempt_id='a1',package_root=Path(directory)/'control')
            report_path=Path(directory)/'control'/'report.json'; report=persist_fresh_preflight_report(report_path,package_path)
            self.assertEqual(load_fresh_preflight_report(report_path,package_path)['outcome'],'pass')
            report_path.write_text('{}')
            with self.assertRaises(ValueError): load_fresh_preflight_report(report_path,package_path)
