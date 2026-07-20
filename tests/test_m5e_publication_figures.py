from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.plot_m5e_publication_figures import load_snapshot, write_publication_figures


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "data/m5e_formal/statistical_analysis"
FORMAL_METRICS = ROOT / "data/m5e_formal/formal_evaluation/m5e_d_formal_quality_metrics.csv"


class M5EPublicationFigureTests(unittest.TestCase):
    def test_snapshot_preserves_frozen_primary_coverage_and_values(self) -> None:
        before = hashlib.sha256(FORMAL_METRICS.read_bytes()).hexdigest()
        snapshot = load_snapshot(ANALYSIS)
        self.assertEqual(snapshot["methods"], ["Uniform", "Center ROI", "Object ROI", "Risk ROI"])
        self.assertEqual(len(snapshot["primary_bootstrap"]), 6)
        self.assertEqual(len(snapshot["scenario_effects"]), 96)
        self.assertEqual({row["scenario_id"] for row in snapshot["scenario_effects"]}, {f"S{i}" for i in range(1, 9)})
        low_object = next(row for row in snapshot["primary_bootstrap"] if row["budget_label"] == "low" and row["baseline_method"] == "object_roi")
        self.assertEqual(low_object["observed_equal_scenario_mean_difference"], "0.1912824025865233")
        self.assertLess(float(low_object["ci_lower_95"]), 0.0)
        self.assertGreater(float(low_object["ci_upper_95"]), 0.0)
        self.assertEqual(before, hashlib.sha256(FORMAL_METRICS.read_bytes()).hexdigest())

    def test_publication_outputs_include_png_svg_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = write_publication_figures(ANALYSIS, root / "assets", root / "snapshot.json")
            self.assertEqual(len(outputs), 8)
            self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in outputs))
            snapshot = json.loads((root / "snapshot.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot["statistical_unit"], "episode")

    def test_readme_public_links_are_relative_and_resolve(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("C:\\Users\\ROG", readme)
        for relative in (
            "docs/assets/m3_world_risk_overview.png",
            "docs/assets/m2_method_comparison_ade.png",
            "docs/assets/m5e_primary_paired_effects.png",
            "docs/assets/m5e_scene_budget_effects.png",
            "docs/m5e_statistical_analysis_report.md",
            "docs/m5e_f_independent_acceptance_report.md",
            "docs/m5e_multiscene_offline_evaluation_protocol.md",
        ):
            self.assertIn(relative, readme)
            self.assertTrue((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
