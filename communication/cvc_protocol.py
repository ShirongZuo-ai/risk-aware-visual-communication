"""CVC-P1 causal sender/receiver primitives with explicit wire accounting.

This module intentionally does not import simulator/evaluator geometry.  A sender
accepts only a camera frame, a timestamp and a scalar risk already computed from
allowed causal state.  A receiver accepts only wire bytes and its held frame.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import struct
from typing import Literal, Sequence

from PIL import Image

from compression.tile_container import deserialize_tiled_frame, serialize_tiled_frame
from compression.tiled_jpeg import DEFAULT_M5_GRID, TileGrid, decode_tiles_to_rgb, encode_rgb_frame_to_tiles


PolicyName = Literal["U0", "A0", "A1"]
MAGIC = b"CVCP1\x00\x01\x00"
PREFIX = ">8sII"
PREFIX_BYTES = struct.calcsize(PREFIX)


@dataclass(frozen=True)
class SenderObservation:
    timestamp_ms: int
    rgb: Image.Image
    risk: float

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0 or not 0.0 <= self.risk <= 1.0:
            raise ValueError("invalid causal sender observation")


@dataclass(frozen=True)
class AllocationDecision:
    policy: PolicyName
    transmit: bool
    qualities: tuple[int, ...]
    target_wire_bytes: int


@dataclass(frozen=True)
class WirePacket:
    payload: bytes
    content_bytes: int
    metadata_bytes: int
    padding_bytes: int

    @property
    def wire_bytes(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class ReceivedFrame:
    image: Image.Image
    source_timestamp_ms: int
    image_age_ms: int
    wire_bytes: int
    held: bool


class CausalBudgetPolicy:
    """Token-bucket policy; decisions never borrow future bytes.

    Every tick earns ``bytes_per_tick``. U0 transmits uniformly when affordable.
    A0/A1 select a low/high spatial quality profile from their supplied causal
    risk. The policy has no access to images, outcomes, or evaluator state.
    """

    def __init__(self, name: PolicyName, bytes_per_tick: int, grid: TileGrid = DEFAULT_M5_GRID) -> None:
        if name not in ("U0", "A0", "A1") or bytes_per_tick <= 0:
            raise ValueError("invalid policy configuration")
        self.name, self.bytes_per_tick, self.grid = name, bytes_per_tick, grid
        self.available_bytes = 0
        self.spent_bytes = 0

    def decide(self, risk: float, estimated_wire_bytes: int) -> AllocationDecision:
        if not 0.0 <= risk <= 1.0 or estimated_wire_bytes <= 0:
            raise ValueError("invalid causal decision input")
        self.available_bytes += self.bytes_per_tick
        transmit = estimated_wire_bytes <= self.available_bytes
        if self.name == "U0":
            qualities = (42,) * self.grid.tile_count
        else:
            # Bottom/central tiles are the controlled-scene obstacle ROI.  Risk
            # changes only current allocation; it cannot select future frames.
            high = 72 if risk >= 0.5 else 42
            low = 18 if risk >= 0.5 else 32
            qualities = tuple(
                high if row >= self.grid.rows // 2 and 2 <= col < self.grid.columns - 2 else low
                for _, row, col, _ in self.grid.iter_tiles()
            )
        if transmit:
            self.available_bytes -= estimated_wire_bytes
            self.spent_bytes += estimated_wire_bytes
        return AllocationDecision(self.name, transmit, qualities, estimated_wire_bytes)


def encode_packet(observation: SenderObservation, decision: AllocationDecision, *, grid: TileGrid = DEFAULT_M5_GRID) -> WirePacket:
    """Encode a complete packet and deterministically pad to the target size."""
    if not decision.transmit:
        raise ValueError("cannot encode a skipped decision")
    tiles = encode_rgb_frame_to_tiles(observation.rgb, grid, decision.qualities)
    tiled = serialize_tiled_frame(grid, tiles)
    metadata = json.dumps(
        {"policy": decision.policy, "risk": observation.risk, "timestamp_ms": observation.timestamp_ms,
         "qualities": list(decision.qualities), "tiled_sha256": hashlib.sha256(tiled).hexdigest()},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    content_bytes = PREFIX_BYTES + len(metadata) + len(tiled)
    if decision.target_wire_bytes < content_bytes:
        raise ValueError(f"target wire budget {decision.target_wire_bytes} is below encoded content {content_bytes}")
    padding_len = decision.target_wire_bytes - content_bytes
    prefix = struct.pack(PREFIX, MAGIC, len(metadata), len(tiled))
    # Hash-stream padding is reproducible and ignored only after lengths parse.
    seed = hashlib.sha256(prefix + metadata + tiled).digest()
    padding = (seed * ((padding_len + len(seed) - 1) // len(seed)))[:padding_len]
    return WirePacket(prefix + metadata + tiled + padding, len(tiled), PREFIX_BYTES + len(metadata), padding_len)


def decode_packet(payload: bytes) -> tuple[Image.Image, dict]:
    if len(payload) < PREFIX_BYTES:
        raise ValueError("truncated CVC packet")
    magic, metadata_len, tiled_len = struct.unpack(PREFIX, payload[:PREFIX_BYTES])
    if magic != MAGIC:
        raise ValueError("invalid CVC packet magic")
    end_meta, end_tiled = PREFIX_BYTES + metadata_len, PREFIX_BYTES + metadata_len + tiled_len
    if end_tiled > len(payload):
        raise ValueError("truncated CVC packet content")
    metadata = json.loads(payload[PREFIX_BYTES:end_meta].decode("utf-8"))
    tiled = payload[end_meta:end_tiled]
    if hashlib.sha256(tiled).hexdigest() != metadata["tiled_sha256"]:
        raise ValueError("tiled payload integrity failure")
    parsed = deserialize_tiled_frame(tiled)
    return decode_tiles_to_rgb(parsed.tiles, parsed.grid), metadata


class HoldingReceiver:
    """Receiver boundary: packet bytes in, decoded/held images out."""

    def __init__(self) -> None:
        self._image: Image.Image | None = None
        self._source_timestamp_ms: int | None = None

    def step(self, now_ms: int, payload: bytes | None) -> ReceivedFrame:
        if payload is not None:
            image, metadata = decode_packet(payload)
            timestamp = int(metadata["timestamp_ms"])
            if timestamp > now_ms:
                raise ValueError("receiver cannot accept a future frame")
            self._image, self._source_timestamp_ms = image, timestamp
            held, wire_bytes = False, len(payload)
        else:
            if self._image is None or self._source_timestamp_ms is None:
                raise RuntimeError("no decoded frame is available to hold")
            held, wire_bytes = True, 0
        return ReceivedFrame(self._image.copy(), self._source_timestamp_ms, now_ms - self._source_timestamp_ms, wire_bytes, held)
