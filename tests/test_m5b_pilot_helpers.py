import math
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import PIL

from compression.budget_matcher import match_uniform_quality_to_budget
from compression.tiled_jpeg import DEFAULT_M5_GRID
from scripts.run_m5b_uniform_pilot import CSV_FIELDS, sha256_file, suggest_development_budgets, sweep_uniform_quality, write_csv, write_metadata
from scripts.validate_m5b_uniform_pilot import read_csv


def image():
    img = Image.new("RGB", (160, 120))
    pix = img.load()
    for y in range(120):
        for x in range(160):
            pix[x, y] = ((x * 7) % 256, (y * 11) % 256, ((x + y) * 13) % 256)
    return img


class M5BPilotHelperTests(unittest.TestCase):
    def test_sweep_schema_and_values(self):
        rows = sweep_uniform_quality(image())
        self.assertEqual(len(rows), 95)
        self.assertEqual(set(rows[0]), set(CSV_FIELDS))
        self.assertEqual([row["quality"] for row in rows], list(range(1, 96)))
        for row in rows:
            self.assertEqual(row["decoded_width_px"], 160)
            self.assertEqual(row["decoded_height_px"], 120)
            self.assertEqual(row["decoded_mode"], "RGB")
            self.assertEqual(row["deterministic_repeat"], "true")
            self.assertEqual(row["container_round_trip"], "true")
            self.assertTrue(math.isfinite(float(row["encode_time_ms"])))
            self.assertTrue(math.isfinite(float(row["decode_time_ms"])))

    def test_budget_suggestions_are_development_only_and_feasible(self):
        rows = sweep_uniform_quality(image())
        budgets = suggest_development_budgets(rows)
        self.assertGreaterEqual(len(budgets), 4)
        matched = []
        img = image()
        for budget in budgets:
            self.assertTrue(budget["development_only"])
            match = match_uniform_quality_to_budget(img, int(budget["target_bytes"]), DEFAULT_M5_GRID)
            self.assertLessEqual(match.actual_total_bytes, int(budget["target_bytes"]))
            matched.append(match.quality)
        self.assertGreaterEqual(len(set(matched)), 4)

    def test_csv_and_metadata_schema_helpers(self):
        rows = sweep_uniform_quality(image())
        budgets = suggest_development_budgets(rows)
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            frame = root / "frame.png"
            image().save(frame)
            csv_path = root / "pilot.csv"
            metadata_path = root / "pilot.json"
            write_csv(rows, csv_path)
            write_metadata(frame, rows, budgets, metadata_path)
            loaded_rows = read_csv(csv_path)
            metadata = metadata_path.read_text(encoding="utf-8")
            self.assertEqual(len(loaded_rows), 95)
            self.assertIn(PIL.__version__, metadata)
            self.assertEqual(sha256_file(frame), sha256_file(frame))
            self.assertIn("development_only", metadata)
            self.assertIn("source_frame_sha256", metadata)


if __name__ == "__main__":
    unittest.main()
