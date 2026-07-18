import json
import unittest

from scripts.m5c_allocation_common import DEVELOPMENT_BUDGETS, grid_json, jpeg_parameters_json, load_m4d_evidence, sha256_file
from scripts.run_m5c_allocation_validation import _base_row


class M5CAllocationHelperTests(unittest.TestCase):
    def test_m4d_evidence_loader_uses_official_snapshot_and_no_future_actual(self):
        image, metadata, rows, mask, polygons = load_m4d_evidence()
        self.assertEqual(image.size, (160, 120))
        self.assertEqual(len(rows), 9)
        self.assertEqual(len(mask.values), 160 * 120)
        self.assertEqual(len(polygons), 9)
        self.assertIs(metadata["trajectory_sources"]["actual_future_trajectory_used"], False)

    def test_development_budget_set_is_frozen(self):
        self.assertEqual(DEVELOPMENT_BUDGETS, (("severe", 31348), ("low", 32105), ("medium", 32729), ("high", 33959)))

    def test_row_schema_uses_json_serializable_shared_identifiers(self):
        row = _base_row("risk_roi", "medium", 32729, "hash")
        self.assertEqual(len(row), 28)
        self.assertEqual(json.loads(row["grid_json"]), grid_json())
        self.assertEqual(json.loads(row["jpeg_parameters_json"]), jpeg_parameters_json())
        self.assertEqual(row["actual_future_trajectory_used"], "false")

    def test_frame_hash_is_stable(self):
        _image, metadata, _rows, _mask, _polygons = load_m4d_evidence()
        from scripts.m5c_allocation_common import PROJECT_ROOT

        path = PROJECT_ROOT / metadata["frame_path"]
        self.assertEqual(sha256_file(path), sha256_file(path))


if __name__ == "__main__":
    unittest.main()
