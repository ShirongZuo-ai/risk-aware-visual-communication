import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_m8a_design import (
    DEFAULT_MATRIX,
    DEFAULT_RULES,
    expand_matrix,
    validate_design,
)


class M8ADesignTests(unittest.TestCase):
    def test_authoritative_proposal_passes(self) -> None:
        result = validate_design()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["identity_count"], 108)
        self.assertEqual(
            result["split_counts"],
            {"calibration": 28, "development": 40, "formal": 40},
        )
        self.assertEqual(result["prior_seed_overlap"], [])
        self.assertEqual(result["gate_count"], 9)

    def test_expansion_is_unique_and_deterministic(self) -> None:
        with DEFAULT_MATRIX.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        first = expand_matrix(rows)
        second = expand_matrix(rows)
        self.assertEqual(first, second)
        self.assertEqual(len({item.seed for item in first}), 108)
        self.assertEqual(len({item.identity_id for item in first}), 108)
        self.assertEqual(first[0].identity_id, "m8a-cal-m8c1-810100")
        self.assertEqual(first[-1].identity_id, "m8a-formal-m8g2-831003")

    def test_matrix_range_tamper_is_rejected(self) -> None:
        text = DEFAULT_MATRIX.read_text(encoding="utf-8")
        tampered = text.replace(
            "3,810100,810102,m8a-cal-m8c1-{seed}",
            "3,810100,810103,m8a-cal-m8c1-{seed}",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.csv"
            path.write_text(tampered, encoding="utf-8", newline="")
            with self.assertRaisesRegex(ValueError, "non-contiguous"):
                validate_design(path, DEFAULT_RULES)

    def test_matrix_identity_overlap_is_rejected(self) -> None:
        text = DEFAULT_MATRIX.read_text(encoding="utf-8")
        tampered = text.replace("810100,810102", "710100,710102", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.csv"
            path.write_text(tampered, encoding="utf-8", newline="")
            with self.assertRaisesRegex(ValueError, "overlaps authoritative prior seeds"):
                validate_design(path, DEFAULT_RULES)

    def test_proxy_gate_tamper_is_rejected(self) -> None:
        payload = json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
        payload["gates"].pop()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact nine proxy gates"):
                validate_design(DEFAULT_MATRIX, path)

    def test_allocator_outcome_selection_is_rejected(self) -> None:
        payload = json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
        payload["selection_rule"]["allocator_outcomes_may_select_proxy"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not select"):
                validate_design(DEFAULT_MATRIX, path)

    def test_tcobr_primary_role_is_rejected(self) -> None:
        payload = json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
        payload["tcobr_role"] = "primary_optimization_target"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-degradation safety"):
                validate_design(DEFAULT_MATRIX, path)


if __name__ == "__main__":
    unittest.main()
