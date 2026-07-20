"""Deterministic binary container for tiled-JPEG frame payloads."""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Sequence

from compression.tiled_jpeg import EncodedTile, TileGrid


MAGIC = b"RAVCJT1"
VERSION = 1
HEADER_FORMAT = ">7s8H"
INDEX_ENTRY_FORMAT = ">HI"
HEADER_BYTES = struct.calcsize(HEADER_FORMAT)
INDEX_ENTRY_BYTES = struct.calcsize(INDEX_ENTRY_FORMAT)


@dataclass(frozen=True)
class DeserializedTiledFrame:
    grid: TileGrid
    tiles: tuple[EncodedTile, ...]
    container_bytes: bytes

    @property
    def tile_payload_bytes(self) -> tuple[int, ...]:
        return tuple(len(tile.jpeg_payload) for tile in self.tiles)

    @property
    def total_bytes(self) -> int:
        return len(self.container_bytes)

    @property
    def container_overhead_bytes(self) -> int:
        return self.total_bytes - sum(self.tile_payload_bytes)


def _validate_tiles_for_grid(grid: TileGrid, tiles: Sequence[EncodedTile]) -> tuple[EncodedTile, ...]:
    if len(tiles) != grid.tile_count:
        raise ValueError("tiles length must equal grid.tile_count")
    ordered = sorted(tiles, key=lambda tile: tile.tile_id)
    for expected_id, tile in enumerate(ordered):
        if tile.tile_id != expected_id:
            raise ValueError("tile IDs must be complete and row-major")
        if tile.row != expected_id // grid.columns or tile.column != expected_id % grid.columns:
            raise ValueError("tile row/column does not match grid")
    return tuple(ordered)


def serialize_tiled_frame(grid: TileGrid, tiles: Sequence[EncodedTile]) -> bytes:
    """Serialize a tiled JPEG frame with only decode-required metadata."""

    ordered = _validate_tiles_for_grid(grid, tiles)
    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        grid.frame_width_px,
        grid.frame_height_px,
        grid.tile_width_px,
        grid.tile_height_px,
        grid.columns,
        grid.rows,
        grid.tile_count,
    )
    index = b"".join(struct.pack(INDEX_ENTRY_FORMAT, tile.tile_id, len(tile.jpeg_payload)) for tile in ordered)
    payloads = b"".join(tile.jpeg_payload for tile in ordered)
    return header + index + payloads


def deserialize_tiled_frame(payload: bytes) -> DeserializedTiledFrame:
    """Parse and validate a tiled JPEG container."""

    if not isinstance(payload, bytes):
        raise ValueError("payload must be bytes")
    if len(payload) < HEADER_BYTES:
        raise ValueError("truncated container header")
    header_values = struct.unpack(HEADER_FORMAT, payload[:HEADER_BYTES])
    magic = header_values[0]
    if magic != MAGIC:
        raise ValueError("invalid container magic")
    version = header_values[1]
    if version != VERSION:
        raise ValueError("unsupported container version")
    grid = TileGrid(
        frame_width_px=header_values[2],
        frame_height_px=header_values[3],
        tile_width_px=header_values[4],
        tile_height_px=header_values[5],
        columns=header_values[6],
        rows=header_values[7],
        tile_count=header_values[8],
    )
    index_start = HEADER_BYTES
    index_end = index_start + grid.tile_count * INDEX_ENTRY_BYTES
    if len(payload) < index_end:
        raise ValueError("truncated tile index")

    entries: list[tuple[int, int]] = []
    seen: set[int] = set()
    offset = index_start
    for expected_id in range(grid.tile_count):
        tile_id, payload_length = struct.unpack(INDEX_ENTRY_FORMAT, payload[offset : offset + INDEX_ENTRY_BYTES])
        offset += INDEX_ENTRY_BYTES
        if tile_id != expected_id:
            raise ValueError("tile index entries must be row-major and complete")
        if tile_id in seen:
            raise ValueError("duplicate tile_id")
        seen.add(tile_id)
        if payload_length <= 0:
            raise ValueError("tile payload length must be positive")
        entries.append((tile_id, payload_length))

    payload_offset = index_end
    tiles: list[EncodedTile] = []
    for tile_id, payload_length in entries:
        end = payload_offset + payload_length
        if end > len(payload):
            raise ValueError("truncated tile payload")
        jpeg_payload = payload[payload_offset:end]
        tiles.append(
            EncodedTile(
                tile_id=tile_id,
                row=tile_id // grid.columns,
                column=tile_id % grid.columns,
                quality=1,
                jpeg_payload=jpeg_payload,
            )
        )
        payload_offset = end
    if payload_offset != len(payload):
        raise ValueError("container has trailing bytes")
    return DeserializedTiledFrame(grid=grid, tiles=tuple(tiles), container_bytes=payload)


def container_overhead_bytes(grid: TileGrid) -> int:
    return HEADER_BYTES + grid.tile_count * INDEX_ENTRY_BYTES
