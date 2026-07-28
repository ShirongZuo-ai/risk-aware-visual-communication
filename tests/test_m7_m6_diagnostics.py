import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from scripts import m7_m6_diagnostics as diagnostic


class M7M6DiagnosticTests(unittest.TestCase):
    def test_allocation_overlap_distinguishes_pixels_and_tiles(self):
        state = np.zeros((120, 160), dtype=bool)
        command = np.zeros_like(state)
        state[0, 0] = True
        command[0, 1] = True
        result = diagnostic.allocation_overlap(state, command)
        self.assertEqual(result["roi_xor_pixels"], 2)
        self.assertEqual(result["roi_intersection_pixels"], 0)
        self.assertEqual(result["tile_xor_count"], 0)
        self.assertEqual(result["tile_jaccard"], 1.0)

    def test_allocation_overlap_rejects_non_frozen_shape(self):
        with self.assertRaisesRegex(ValueError, "frozen image shape"):
            diagnostic.allocation_overlap(np.zeros((2, 2)), np.zeros((2, 2)))

    def test_checked_sources_cover_the_complete_frozen_study(self):
        data = diagnostic.validate_checked_sources()
        self.assertEqual(data["summary"]["source"]["episodes"], 32)
        self.assertEqual(data["summary"]["source"]["snapshots"], 128)
        self.assertEqual(data["summary"]["source"]["codec_cases"], 1024)
        self.assertEqual(len(data["overlap"]), 512)
        self.assertEqual(len(data["cases"]), 1024)

    def test_checked_sources_preserve_absolute_null_result(self):
        summary = diagnostic.validate_checked_sources()["summary"]
        for budget in diagnostic.BUDGETS:
            state = summary["absolute_tcobr"][budget][diagnostic.METHODS[0]]
            command = summary["absolute_tcobr"][budget][diagnostic.METHODS[1]]
            self.assertEqual(state, command)
            self.assertEqual(state["n_episodes"], 17)

    def test_checked_sources_preserve_empty_scene_mechanisms(self):
        empty = diagnostic.validate_checked_sources()["summary"]["empty_scene_diagnosis"]
        self.assertEqual(empty["S1"]["original_boundary_edges_below_16"], 8)
        self.assertEqual(empty["S7"]["original_boundary_edges_below_16"], 8)
        self.assertEqual(empty["S8"], {"not_trajectory_critical": 16})

    def test_summary_tamper_is_rejected(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "summary.json"
            value = json.loads(diagnostic.SUMMARY_PATH.read_text(encoding="utf-8"))
            value["source"]["episodes"] = 31
            target.write_text(json.dumps(value), encoding="utf-8")
            with patch.object(diagnostic, "SUMMARY_PATH", target):
                with self.assertRaisesRegex(ValueError, "summary digest"):
                    diagnostic.validate_checked_sources()

    def test_m7_documented_artifacts_resolve(self):
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "docs/m7_m6_zero_effect_diagnostic.md",
            "docs/m7_budget_conditioned_voi_design.md",
            "docs/results/m7_m6_diagnostic_summary.json",
        ):
            self.assertTrue((root / relative).is_file(), relative)
        for stem in (
            "m7_allocation_divergence", "m7_absolute_tcobr",
            "m7_critical_region_diagnostics", "m7_empty_scene_diagnosis",
            "m7_scene_budget_failure_patterns",
        ):
            for suffix in (".svg", ".png"):
                self.assertGreater((root / "docs/figures" / f"{stem}{suffix}").stat().st_size, 1000)

    def test_render_is_deterministic_and_high_resolution(self):
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            with patch.object(diagnostic, "FIGURE_DIR", Path(first)):
                stems = diagnostic.render_figures()
            first_hashes = {stem: (Path(first) / f"{stem}.svg").read_bytes() for stem in stems}
            with patch.object(diagnostic, "FIGURE_DIR", Path(second)):
                diagnostic.render_figures()
            for stem in stems:
                self.assertEqual(first_hashes[stem], (Path(second) / f"{stem}.svg").read_bytes())
                with Image.open(Path(second) / f"{stem}.png") as image:
                    self.assertGreaterEqual(image.info["dpi"][0], 350)


if __name__ == "__main__":
    unittest.main()
