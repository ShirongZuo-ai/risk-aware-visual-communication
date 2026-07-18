import struct
import unittest

from PIL import Image

from compression.tile_container import (
    HEADER_BYTES,
    INDEX_ENTRY_BYTES,
    MAGIC,
    VERSION,
    container_overhead_bytes,
    deserialize_tiled_frame,
    serialize_tiled_frame,
)
from compression.tiled_jpeg import DEFAULT_M5_GRID, encode_uniform_tiled_jpeg


def image():
    return Image.new("RGB", (160, 120), (12, 34, 56))


class TileContainerTests(unittest.TestCase):
    def test_serialization_round_trip_preserves_jpeg_payloads(self):
        encoded = encode_uniform_tiled_jpeg(image(), 50, DEFAULT_M5_GRID)
        parsed = deserialize_tiled_frame(encoded.container_bytes)
        self.assertEqual(parsed.grid, DEFAULT_M5_GRID)
        self.assertEqual(tuple(tile.jpeg_payload for tile in parsed.tiles), tuple(tile.jpeg_payload for tile in encoded.tiles))
        self.assertEqual(parsed.container_bytes, encoded.container_bytes)

    def test_header_index_and_overhead_are_explicit(self):
        encoded = encode_uniform_tiled_jpeg(image(), 50, DEFAULT_M5_GRID)
        self.assertEqual(encoded.container_bytes[: len(MAGIC)], MAGIC)
        self.assertEqual(encoded.container_overhead_bytes, HEADER_BYTES + 48 * INDEX_ENTRY_BYTES)
        self.assertEqual(container_overhead_bytes(DEFAULT_M5_GRID), encoded.container_overhead_bytes)
        version = struct.unpack(">H", encoded.container_bytes[len(MAGIC) : len(MAGIC) + 2])[0]
        self.assertEqual(version, VERSION)

    def test_deterministic_serialization(self):
        encoded = encode_uniform_tiled_jpeg(image(), 50, DEFAULT_M5_GRID)
        self.assertEqual(serialize_tiled_frame(DEFAULT_M5_GRID, encoded.tiles), encoded.container_bytes)
        self.assertEqual(serialize_tiled_frame(DEFAULT_M5_GRID, encoded.tiles), encoded.container_bytes)

    def test_invalid_magic_version_and_truncation(self):
        encoded = bytearray(encode_uniform_tiled_jpeg(image(), 50, DEFAULT_M5_GRID).container_bytes)
        bad_magic = bytes(b"BADMAGC" + encoded[7:])
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bad_magic)
        bad_version = bytearray(encoded)
        bad_version[7:9] = struct.pack(">H", 99)
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(bad_version))
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(encoded[: HEADER_BYTES - 1]))
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(encoded[: HEADER_BYTES + INDEX_ENTRY_BYTES - 1]))
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(encoded[:-1]))

    def test_invalid_index_entries_and_trailing_bytes(self):
        encoded = bytearray(encode_uniform_tiled_jpeg(image(), 50, DEFAULT_M5_GRID).container_bytes)
        first_index = HEADER_BYTES
        bad_id = bytearray(encoded)
        bad_id[first_index : first_index + 2] = struct.pack(">H", 1)
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(bad_id))

        bad_length = bytearray(encoded)
        bad_length[first_index + 2 : first_index + 6] = struct.pack(">I", 0)
        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(bad_length))

        with self.assertRaises(ValueError):
            deserialize_tiled_frame(bytes(encoded) + b"x")

    def test_serialize_rejects_missing_or_bad_tiles(self):
        encoded = encode_uniform_tiled_jpeg(image(), 50, DEFAULT_M5_GRID)
        with self.assertRaises(ValueError):
            serialize_tiled_frame(DEFAULT_M5_GRID, encoded.tiles[:-1])
        duplicate = encoded.tiles[:-1] + (encoded.tiles[0],)
        with self.assertRaises(ValueError):
            serialize_tiled_frame(DEFAULT_M5_GRID, duplicate)


if __name__ == "__main__":
    unittest.main()
