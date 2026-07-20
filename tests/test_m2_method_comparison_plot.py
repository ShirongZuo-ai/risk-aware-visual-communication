from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from scripts.plot_m2_method_comparison import read_summary, write_figures


class M2MethodComparisonPlotTests(unittest.TestCase):
    def _write_csv(self, rows: list[dict[str, str]]) -> Path:
        root = Path(tempfile.mkdtemp())
        path = root / "summary.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_valid_rows_generate_png_and_svg(self) -> None:
        rows = [
            {"method": "state_only", "horizon_s": "2.0", "category": "all_stable", "window_count": "4", "ade_mean_m": "0.01", "source_artifact": "x"},
            {"method": "command_conditioned", "horizon_s": "2.0", "category": "all_stable", "window_count": "4", "ade_mean_m": "0.001", "source_artifact": "x"},
        ]
        source = self._write_csv(rows)
        outputs = write_figures(read_summary(source), source.parent / "assets")
        self.assertEqual(4, len(outputs))
        self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in outputs))

    def test_zero_ade_is_rejected_for_log_plot(self) -> None:
        rows = [
            {"method": "state_only", "horizon_s": "2.0", "category": "all_stable", "window_count": "4", "ade_mean_m": "0", "source_artifact": "x"},
            {"method": "command_conditioned", "horizon_s": "2.0", "category": "all_stable", "window_count": "4", "ade_mean_m": "0.001", "source_artifact": "x"},
        ]
        with self.assertRaisesRegex(ValueError, "non-zero"):
            read_summary(self._write_csv(rows))


if __name__ == "__main__":
    unittest.main()
