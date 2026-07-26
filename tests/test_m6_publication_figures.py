from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from scripts.plot_m6_publication_figures import (
    SOURCE_DIR,
    render_publication_figures,
    validate_publication_source_data,
)


ROOT = Path(__file__).resolve().parents[1]


class M6PublicationFigureTests(unittest.TestCase):
    def test_checked_source_data_preserves_frozen_negative_result(self) -> None:
        source = validate_publication_source_data(SOURCE_DIR)
        self.assertEqual(len(source["eligibility"]), 32)
        self.assertEqual(sum(int(row["eligible"]) for row in source["eligibility"]), 17)
        self.assertEqual(len(source["tcobr"]), 5)
        for row in source["tcobr"]:
            self.assertEqual(float(row["estimate"]), 0.0)
            self.assertEqual(float(row["ci_low"]), 0.0)
            self.assertEqual(float(row["ci_high"]), 0.0)
        low = next(row for row in source["secondary"] if row["budget"] == "low")
        self.assertLess(float(low["psnr_effect_db"]), 0.0)
        self.assertLess(float(low["ssim_effect"]), 0.0)
        self.assertEqual(int(low["n_episodes"]), 32)

    def test_qualitative_source_is_hash_bound_and_not_effect_selected(self) -> None:
        value = validate_publication_source_data(SOURCE_DIR)["qualitative"]
        self.assertEqual(
            value["selection_rule"],
            "lexicographically_first_eligible_episode_then_snapshot_0_then_low_budget",
        )
        self.assertEqual(value["episode_id"], "m6a_v3_formal_s2_seed630200")
        self.assertEqual(value["snapshot_id"], "0")
        self.assertEqual(value["budget"], "low")
        for method, item in value["reconstructions"].items():
            payload = base64.b64decode(item["rgb_base64"], validate=True)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"], method)

    def test_rendered_outputs_include_five_svg_png_pairs_at_publication_dpi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = render_publication_figures(SOURCE_DIR, Path(temporary))
            self.assertEqual(len(outputs), 10)
            self.assertEqual(sum(path.suffix == ".png" for path in outputs), 5)
            self.assertEqual(sum(path.suffix == ".svg" for path in outputs), 5)
            self.assertTrue(all(path.exists() and path.stat().st_size > 1000 for path in outputs))
            for path in (item for item in outputs if item.suffix == ".png"):
                with Image.open(path) as image:
                    self.assertGreaterEqual(image.info["dpi"][0], 300.0)
                    self.assertGreater(image.width, 1000)

    def test_readme_m6_links_are_relative_and_resolve(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("C:\\Users\\ROG", readme)
        for relative in (
            "docs/figures/m6_pipeline.png",
            "docs/figures/m6_episode_eligibility.png",
            "docs/figures/m6_tcobr_budget_forest.png",
            "docs/figures/m6_secondary_budget_effects.png",
            "docs/figures/m6_qualitative_comparison.png",
            "docs/m6_final_report.md",
            "docs/m6_followup_evaluation_protocol.md",
            "docs/results/m6_multiscene_v3_preregistration.json",
        ):
            self.assertIn(relative, readme)
            self.assertTrue((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
