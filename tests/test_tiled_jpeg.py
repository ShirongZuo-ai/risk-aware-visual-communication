from dataclasses import FrozenInstanceError
import unittest

from PIL import Image

from compression.tiled_jpeg import (
    DEFAULT_M5_GRID,
    EncodedTile,
    decode_tiles_to_rgb,
    encode_rgb_frame_to_tiles,
    encode_uniform_tiled_jpeg,
)


def sample_image(mode="RGB", size=(160, 120)):
    image = Image.new(mode, size)
    pixels = image.load()
    for y in range(size[1]):
        for x in range(size[0]):
            value = (x * 3 + y * 5) % 256
            if mode == "RGB":
                pixels[x, y] = (value, (value + 40) % 256, (value + 80) % 256)
            elif mode == "L":
                pixels[x, y] = value
    return image


class TileGridTests(unittest.TestCase):
    def test_current_grid_and_row_major_bounds(self):
        grid = DEFAULT_M5_GRID
        self.assertEqual((grid.frame_width_px, grid.frame_height_px), (160, 120))
        self.assertEqual((grid.tile_width_px, grid.tile_height_px), (20, 20))
        self.assertEqual((grid.columns, grid.rows, grid.tile_count), (8, 6, 48))
        self.assertEqual(grid.tile_bounds(0), (0, 0, 20, 20))
        self.assertEqual(grid.tile_bounds(7), (140, 0, 160, 20))
        self.assertEqual(grid.tile_bounds(8), (0, 20, 20, 40))
        self.assertEqual(grid.tile_bounds(47), (140, 100, 160, 120))

    def test_grid_complete_coverage_without_overlap(self):
        covered = set()
        for tile_id, row, column, bounds in DEFAULT_M5_GRID.iter_tiles():
            self.assertEqual(tile_id, row * DEFAULT_M5_GRID.columns + column)
            left, top, right, bottom = bounds
            for y in range(top, bottom):
                for x in range(left, right):
                    self.assertNotIn((x, y), covered)
                    covered.add((x, y))
        self.assertEqual(len(covered), 160 * 120)

    def test_invalid_tile_id_rejected(self):
        with self.assertRaises(ValueError):
            DEFAULT_M5_GRID.tile_bounds(-1)
        with self.assertRaises(ValueError):
            DEFAULT_M5_GRID.tile_bounds(48)


class TiledJpegTests(unittest.TestCase):
    def test_rgb_encode_produces_48_row_major_tiles(self):
        tiles = encode_rgb_frame_to_tiles(sample_image(), DEFAULT_M5_GRID, (20,) * 48)
        self.assertEqual(len(tiles), 48)
        self.assertEqual([tile.tile_id for tile in tiles], list(range(48)))
        self.assertTrue(all(tile.jpeg_payload.startswith(b"\xff\xd8") for tile in tiles))

    def test_non_rgb_input_is_converted_without_mutating_source(self):
        image = sample_image("L")
        tiles = encode_rgb_frame_to_tiles(image, DEFAULT_M5_GRID, (30,) * 48)
        self.assertEqual(image.mode, "L")
        decoded = decode_tiles_to_rgb(tiles, DEFAULT_M5_GRID)
        self.assertEqual(decoded.mode, "RGB")
        self.assertEqual(decoded.size, (160, 120))

    def test_quality_length_and_size_validation(self):
        with self.assertRaises(ValueError):
            encode_rgb_frame_to_tiles(sample_image(), DEFAULT_M5_GRID, (10,) * 47)
        with self.assertRaises(ValueError):
            encode_rgb_frame_to_tiles(sample_image(size=(159, 120)), DEFAULT_M5_GRID, (10,) * 48)
        for quality in (0, 96):
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    encode_rgb_frame_to_tiles(sample_image(), DEFAULT_M5_GRID, (quality,) * 48)

    def test_repeated_uniform_encode_is_deterministic(self):
        image = sample_image()
        first = encode_uniform_tiled_jpeg(image, 42, DEFAULT_M5_GRID)
        second = encode_uniform_tiled_jpeg(image, 42, DEFAULT_M5_GRID)
        self.assertEqual(first.container_bytes, second.container_bytes)
        self.assertEqual(first.tile_payload_bytes, second.tile_payload_bytes)

    def test_decode_uses_tile_id_not_input_order(self):
        frame = encode_uniform_tiled_jpeg(sample_image(), 35, DEFAULT_M5_GRID)
        shuffled = tuple(reversed(frame.tiles))
        decoded = decode_tiles_to_rgb(shuffled, DEFAULT_M5_GRID)
        self.assertEqual(decoded.size, (160, 120))
        self.assertEqual(decoded.mode, "RGB")

    def test_decode_rejects_missing_duplicate_and_corrupt_tiles(self):
        frame = encode_uniform_tiled_jpeg(sample_image(), 35, DEFAULT_M5_GRID)
        with self.assertRaises(ValueError):
            decode_tiles_to_rgb(frame.tiles[:-1], DEFAULT_M5_GRID)
        duplicate = frame.tiles[:-1] + (frame.tiles[0],)
        with self.assertRaises(ValueError):
            decode_tiles_to_rgb(duplicate, DEFAULT_M5_GRID)
        bad = EncodedTile(0, 0, 0, 35, b"not-a-jpeg")
        with self.assertRaises(ValueError):
            decode_tiles_to_rgb((bad,) + frame.tiles[1:], DEFAULT_M5_GRID)

    def test_encoded_tile_is_frozen_and_validates_id_quality_payload(self):
        tile = encode_uniform_tiled_jpeg(sample_image(), 20, DEFAULT_M5_GRID).tiles[0]
        with self.assertRaises(FrozenInstanceError):
            tile.quality = 21
        with self.assertRaises(ValueError):
            EncodedTile(1, 0, 0, 20, b"x")
        with self.assertRaises(ValueError):
            EncodedTile(0, 0, 0, 0, b"x")
        with self.assertRaises(ValueError):
            EncodedTile(0, 0, 0, 20, b"")


if __name__ == "__main__":
    unittest.main()
