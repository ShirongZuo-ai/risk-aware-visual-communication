"""Compact complete-frame JPEG wire codec for CVC-P3 packet granularity.

P2's 48 independently encoded tiles have a measured content floor above the
12/18/24 kB P3 packet targets.  This development-only codec keeps the same
camera resolution and exact authenticated envelope semantics while using one
complete JPEG so smaller fixed-cost temporal opportunities are physically real.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import struct

from PIL import Image


MAGIC = b"CVCP3\x00\x01\x00"
PREFIX = ">8sII"
PREFIX_BYTES = struct.calcsize(PREFIX)


@dataclass(frozen=True)
class P3WirePacket:
    payload: bytes
    content_bytes: int
    metadata_bytes: int
    padding_bytes: int


@dataclass(frozen=True)
class P3ReceivedFrame:
    image: Image.Image
    source_timestamp_ms: int
    image_age_ms: int
    wire_bytes: int
    held: bool


def encode_p3_packet(image: Image.Image, timestamp_ms: int, risk: float, policy: str,
                     quality: int, target_wire_bytes: int) -> P3WirePacket:
    if timestamp_ms < 0 or not 0.0 <= risk <= 1.0 or policy not in ("U0", "A0", "A1"):
        raise ValueError("invalid causal packet input")
    if not 1 <= quality <= 95 or target_wire_bytes <= 0:
        raise ValueError("invalid codec configuration")
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality, progressive=False,
                              optimize=False, subsampling=0)
    jpeg = buffer.getvalue()
    metadata = json.dumps({
        "policy": policy, "risk": risk, "timestamp_ms": timestamp_ms, "quality": quality,
        "width": image.width, "height": image.height,
        "jpeg_sha256": hashlib.sha256(jpeg).hexdigest(),
    }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    prefix = struct.pack(PREFIX, MAGIC, len(metadata), len(jpeg))
    content = prefix + metadata + jpeg
    if len(content) > target_wire_bytes:
        raise ValueError(f"target wire budget {target_wire_bytes} is below encoded content {len(content)}")
    padding_length = target_wire_bytes - len(content)
    seed = hashlib.sha256(content).digest()
    padding = (seed * ((padding_length + len(seed) - 1) // len(seed)))[:padding_length]
    return P3WirePacket(content + padding, len(jpeg), PREFIX_BYTES + len(metadata), padding_length)


def decode_p3_packet(payload: bytes) -> tuple[Image.Image, dict]:
    if len(payload) < PREFIX_BYTES:
        raise ValueError("truncated CVC-P3 packet")
    magic, metadata_length, jpeg_length = struct.unpack(PREFIX, payload[:PREFIX_BYTES])
    if magic != MAGIC:
        raise ValueError("invalid CVC-P3 packet magic")
    metadata_end = PREFIX_BYTES + metadata_length
    jpeg_end = metadata_end + jpeg_length
    if jpeg_end > len(payload):
        raise ValueError("truncated CVC-P3 content")
    metadata = json.loads(payload[PREFIX_BYTES:metadata_end].decode("utf-8"))
    jpeg = payload[metadata_end:jpeg_end]
    if hashlib.sha256(jpeg).hexdigest() != metadata["jpeg_sha256"]:
        raise ValueError("CVC-P3 JPEG integrity failure")
    with Image.open(BytesIO(jpeg)) as source:
        image = source.convert("RGB")
        image.load()
    if image.size != (int(metadata["width"]), int(metadata["height"])):
        raise ValueError("decoded CVC-P3 frame dimensions differ from metadata")
    return image, metadata


class P3HoldingReceiver:
    def __init__(self) -> None:
        self._image: Image.Image | None = None
        self._timestamp_ms: int | None = None

    def step(self, now_ms: int, payload: bytes | None) -> P3ReceivedFrame:
        if payload is not None:
            image, metadata = decode_p3_packet(payload)
            timestamp = int(metadata["timestamp_ms"])
            if timestamp > now_ms:
                raise ValueError("receiver cannot accept a future frame")
            self._image, self._timestamp_ms = image, timestamp
            held, wire_bytes = False, len(payload)
        else:
            if self._image is None or self._timestamp_ms is None:
                raise RuntimeError("no decoded frame is available to hold")
            held, wire_bytes = True, 0
        return P3ReceivedFrame(self._image.copy(), self._timestamp_ms,
                               now_ms - self._timestamp_ms, wire_bytes, held)
