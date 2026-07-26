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
        self.assertEqual([row["milestone"] for row in source["capability"]], [f"M{i}" for i in range(1, 7)])
        self.assertEqual(
            {row["metric"]: int(row["value"]) for row in source["scale"]},
            {"scenes": 8, "episodes": 32, "snapshots": 128, "codec_cases": 1024,
             "finalized": 32, "retries": 0},
        )
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
        absolute = {(row["budget"], row["method"]): row for row in source["absolute"]}
        self.assertEqual(int(absolute[("severe", "state_only_risk_roi")]["target_bytes"]), 31466)
        self.assertEqual(int(absolute[("high", "state_only_risk_roi")]["target_bytes"]), 34871)
        self.assertGreater(
            float(absolute[("high", "state_only_risk_roi")]["mean_full_psnr_db"]),
            float(absolute[("severe", "state_only_risk_roi")]["mean_full_psnr_db"]),
        )

    def test_m5_context_preserves_all_baselines_and_adverse_severe_results(self) -> None:
        rows = validate_publication_source_data(SOURCE_DIR)["m5"]
        values = {(row["budget"], row["baseline"]): float(row["risk_minus_baseline_rw_psnr_db"])
                  for row in rows}
        self.assertAlmostEqual(values[("low", "uniform")], 1.7978625401129522)
        self.assertAlmostEqual(values[("low", "center_roi")], 2.9642030404201005)
        self.assertAlmostEqual(values[("low", "object_roi")], 0.1912824025865233)
        self.assertAlmostEqual(values[("severe", "uniform")], -1.1220193547447121)
        self.assertAlmostEqual(values[("severe", "center_roi")], 0.5203346036803809)
        self.assertAlmostEqual(values[("severe", "object_roi")], -0.8831735704736349)

    def test_qualitative_source_is_hash_bound_and_not_effect_selected(self) -> None:
        value = validate_publication_source_data(SOURCE_DIR)["qualitative"]
        self.assertEqual(
            value["selection_rule"],
            "lexicographically_first_eligible_episode_then_snapshot_0_then_state_only_then_budget_endpoints",
        )
        self.assertEqual(value["episode_id"], "m6a_v3_formal_s2_seed630200")
        self.assertEqual(value["snapshot_id"], "0")
        self.assertEqual(value["method"], "state_only_risk_roi")
        self.assertEqual(value["budgets"], ["severe", "high"])
        for budget, item in value["reconstructions"].items():
            payload = base64.b64decode(item["rgb_base64"], validate=True)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"], budget)
        self.assertGreater(value["reconstructions"]["high"]["full_psnr_db"],
                           value["reconstructions"]["severe"]["full_psnr_db"])
        self.assertGreater(value["reconstructions"]["high"]["full_ssim"],
                           value["reconstructions"]["severe"]["full_ssim"])

    def test_rendered_outputs_include_nine_svg_png_pairs_at_publication_dpi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = render_publication_figures(SOURCE_DIR, Path(temporary))
            self.assertEqual(len(outputs), 18)
            self.assertEqual(sum(path.suffix == ".png" for path in outputs), 9)
            self.assertEqual(sum(path.suffix == ".svg" for path in outputs), 9)
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
            "docs/figures/m6_capability_evolution.png",
            "docs/figures/m6_study_scale_validation.png",
            "docs/figures/m6_absolute_budget_quality.png",
            "docs/figures/m5_primary_baseline_effects.png",
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
