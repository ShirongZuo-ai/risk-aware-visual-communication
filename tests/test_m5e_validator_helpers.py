from __future__ import annotations

import unittest

from scripts.validate_m5e_dataset import _combined_mask_hash, _polygon_tile_ids


class M5EValidatorHelperTests(unittest.TestCase):
    def test_combined_mask_hash_is_deterministic(self) -> None:
        values = (0.0, 0.25, 1.0)
        self.assertEqual(_combined_mask_hash(values), _combined_mask_hash(values))
        self.assertNotEqual(_combined_mask_hash(values), _combined_mask_hash((0.0, 0.5, 1.0)))

    def test_polygon_tile_ids_detect_shared_tiles(self) -> None:
        first = {"clipped_polygon": ((18.0, 18.0, 1.0), (25.0, 18.0, 1.0), (25.0, 25.0, 1.0), (18.0, 25.0, 1.0))}
        second = {"clipped_polygon": ((22.0, 22.0, 1.0), (30.0, 22.0, 1.0), (30.0, 30.0, 1.0), (22.0, 30.0, 1.0))}
        self.assertTrue(_polygon_tile_ids(first) & _polygon_tile_ids(second))

    def test_polygon_tile_ids_respect_grid_boundaries(self) -> None:
        record = {"clipped_polygon": ((0.0, 0.0, 1.0), (19.0, 0.0, 1.0), (19.0, 19.0, 1.0), (0.0, 19.0, 1.0))}
        self.assertEqual(_polygon_tile_ids(record), {0})


if __name__ == "__main__":
    unittest.main()
