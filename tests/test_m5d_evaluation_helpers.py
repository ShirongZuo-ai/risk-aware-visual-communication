import unittest

from scripts.m5d_evaluation_common import CSV_FIELDS, DEVELOPMENT_BUDGETS, METHOD_ORDER, dependency_versions, load_fixed_evaluation_inputs, read_m5c_rows


class M5DEvaluationHelperTests(unittest.TestCase):
    def test_fixed_m5c_matrix_and_dependency_versions(self):
        rows = read_m5c_rows()
        self.assertEqual(len(rows), 16)
        self.assertEqual({row["method"] for row in rows}, set(METHOD_ORDER))
        self.assertEqual({row["budget_id"] for row in rows}, {label for label, _ in DEVELOPMENT_BUDGETS})
        versions = dependency_versions()
        self.assertIn("pillow", versions)
        self.assertIn("numpy", versions)
        self.assertIn("scikit_image", versions)

    def test_m4d_inputs_are_fixed_and_regions_are_nonempty(self):
        source, metadata, mask, polygons, regions = load_fixed_evaluation_inputs()
        self.assertEqual(source.shape, (120, 160, 3))
        self.assertIs(metadata["trajectory_sources"]["actual_future_trajectory_used"], False)
        self.assertEqual(len(mask.values), 160 * 120)
        self.assertEqual(len(polygons), 9)
        self.assertGreater(regions.eligible_object_union.pixel_count, 0)
        self.assertGreater(regions.high_risk.pixel_count, 0)

    def test_csv_schema_includes_fixed_metrics_and_fairness_fields(self):
        for field in ("full_psnr_db", "full_ssim", "risk_weighted_psnr_db", "object_psnr_db", "high_risk_psnr_db", "background_psnr_db", "tile_qualities_json", "actual_future_trajectory_used"):
            self.assertIn(field, CSV_FIELDS)


if __name__ == "__main__":
    unittest.main()
