"""Deterministic tiled-JPEG encode/decode helpers for Milestone 5B."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

from PIL import Image


JPEG_FORMAT = "JPEG"
JPEG_QUALITY_MIN = 1
JPEG_QUALITY_MAX = 95
JPEG_PROGRESSIVE = False
JPEG_OPTIMIZE = False
JPEG_SUBSAMPLING = 0


def validate_quality(quality: int) -> int:
    if not isinstance(quality, int):
        raise ValueError("quality must be an integer")
    if quality < JPEG_QUALITY_MIN or quality > JPEG_QUALITY_MAX:
        raise ValueError("quality must be in [1, 95]")
    return quality


@dataclass(frozen=True)
class TileGrid:
    """Fixed non-overlapping tile grid with row-major tile IDs."""

    frame_width_px: int
    frame_height_px: int
    tile_width_px: int
    tile_height_px: int
    columns: int
    rows: int
    tile_count: int

    def __post_init__(self) -> None:
        for name in (
            "frame_width_px",
            "frame_height_px",
            "tile_width_px",
            "tile_height_px",
            "columns",
            "rows",
            "tile_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.frame_width_px != self.tile_width_px * self.columns:
            raise ValueError("frame width must equal tile_width_px * columns")
        if self.frame_height_px != self.tile_height_px * self.rows:
            raise ValueError("frame height must equal tile_height_px * rows")
        if self.tile_count != self.columns * self.rows:
            raise ValueError("tile_count must equal columns * rows")

    def tile_bounds(self, tile_id: int) -> tuple[int, int, int, int]:
        if not isinstance(tile_id, int) or tile_id < 0 or tile_id >= self.tile_count:
            raise ValueError("tile_id is outside the grid")
        row = tile_id // self.columns
        column = tile_id % self.columns
        left = column * self.tile_width_px
        top = row * self.tile_height_px
        return (left, top, left + self.tile_width_px, top + self.tile_height_px)

    def iter_tiles(self) -> tuple[tuple[int, int, int, tuple[int, int, int, int]], ...]:
        return tuple(
            (tile_id, tile_id // self.columns, tile_id % self.columns, self.tile_bounds(tile_id))
            for tile_id in range(self.tile_count)
        )


DEFAULT_M5_GRID = TileGrid(
    frame_width_px=160,
    frame_height_px=120,
    tile_width_px=20,
    tile_height_px=20,
    columns=8,
    rows=6,
    tile_count=48,
)


@dataclass(frozen=True)
class EncodedTile:
    """One independently encoded JPEG tile."""

    tile_id: int
    row: int
    column: int
    quality: int
    jpeg_payload: bytes

    def __post_init__(self) -> None:
        validate_quality(self.quality)
        if not isinstance(self.tile_id, int) or self.tile_id < 0:
            raise ValueError("tile_id must be a non-negative integer")
        if not isinstance(self.row, int) or self.row < 0:
            raise ValueError("row must be a non-negative integer")
        if not isinstance(self.column, int) or self.column < 0:
            raise ValueError("column must be a non-negative integer")
        if self.tile_id != self.row * DEFAULT_M5_GRID.columns + self.column:
            # The first implementation freezes the M5 grid; reject ambiguous IDs.
            raise ValueError("tile_id must equal row * 8 + column")
        if not isinstance(self.jpeg_payload, bytes) or not self.jpeg_payload:
            raise ValueError("jpeg_payload must be non-empty bytes")


@dataclass(frozen=True)
class EncodedTiledFrame:
    """Uniform encoded tiled frame plus serialized transmitted container."""

    grid: TileGrid
    tiles: tuple[EncodedTile, ...]
    container_bytes: bytes

    @property
    def qualities(self) -> tuple[int, ...]:
        return tuple(tile.quality for tile in self.tiles)

    @property
    def tile_payload_bytes(self) -> tuple[int, ...]:
        return tuple(len(tile.jpeg_payload) for tile in self.tiles)

    @property
    def total_bytes(self) -> int:
        return len(self.container_bytes)

    @property
    def container_overhead_bytes(self) -> int:
        return self.total_bytes - sum(self.tile_payload_bytes)


def encode_rgb_frame_to_tiles(
    image: Image.Image,
    grid: TileGrid,
    qualities: Sequence[int],
) -> tuple[EncodedTile, ...]:
    """Encode one RGB frame into row-major JPEG tile payloads without IO."""

    if image.size != (grid.frame_width_px, grid.frame_height_px):
        raise ValueError("image size must match the tile grid")
    if len(qualities) != grid.tile_count:
        raise ValueError("qualities length must equal grid.tile_count")
    checked_qualities = tuple(validate_quality(int(quality)) for quality in qualities)
    rgb = image.convert("RGB")
    encoded: list[EncodedTile] = []
    for tile_id, row, column, bounds in grid.iter_tiles():
        tile = rgb.crop(bounds)
        buffer = BytesIO()
        tile.save(
            buffer,
            format=JPEG_FORMAT,
            quality=checked_qualities[tile_id],
            progressive=JPEG_PROGRESSIVE,
            optimize=JPEG_OPTIMIZE,
            subsampling=JPEG_SUBSAMPLING,
        )
        encoded.append(EncodedTile(tile_id, row, column, checked_qualities[tile_id], buffer.getvalue()))
    return tuple(encoded)


def decode_tiles_to_rgb(encoded_tiles: Sequence[EncodedTile], grid: TileGrid) -> Image.Image:
    """Decode all JPEG tiles and rebuild the full RGB frame by tile ID."""

    by_id: dict[int, EncodedTile] = {}
    for tile in encoded_tiles:
        if tile.tile_id in by_id:
            raise ValueError(f"duplicate tile_id: {tile.tile_id}")
        by_id[tile.tile_id] = tile
    expected = set(range(grid.tile_count))
    if set(by_id) != expected:
        missing = sorted(expected - set(by_id))
        extra = sorted(set(by_id) - expected)
        raise ValueError(f"tile set mismatch; missing={missing}, extra={extra}")

    output = Image.new("RGB", (grid.frame_width_px, grid.frame_height_px))
    for tile_id in range(grid.tile_count):
        encoded = by_id[tile_id]
        try:
            with Image.open(BytesIO(encoded.jpeg_payload)) as tile_image:
                decoded = tile_image.convert("RGB")
                decoded.load()
        except Exception as exc:  # Pillow raises several concrete decoder errors.
            raise ValueError(f"tile {tile_id} is not a decodable JPEG") from exc
        if decoded.size != (grid.tile_width_px, grid.tile_height_px):
            raise ValueError(f"tile {tile_id} decoded to the wrong size: {decoded.size}")
        output.paste(decoded, grid.tile_bounds(tile_id)[:2])
    return output


def encode_uniform_tiled_jpeg(image: Image.Image, quality: int, grid: TileGrid = DEFAULT_M5_GRID) -> EncodedTiledFrame:
    """Encode all tiles at one quality and serialize the shared container."""

    checked_quality = validate_quality(quality)
    tiles = encode_rgb_frame_to_tiles(image, grid, (checked_quality,) * grid.tile_count)
    from compression.tile_container import serialize_tiled_frame

    container_bytes = serialize_tiled_frame(grid, tiles)
    return EncodedTiledFrame(grid=grid, tiles=tiles, container_bytes=container_bytes)
