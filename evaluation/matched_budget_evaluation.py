"""Evaluate fixed M5C containers without invoking allocation or matching."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

import numpy as np

from compression.tile_container import deserialize_tiled_frame
from compression.tiled_jpeg import DEFAULT_M5_GRID, decode_tiles_to_rgb, encode_rgb_frame_to_tiles
from evaluation.image_quality import ErrorMetrics, compute_error_metrics, compute_masked_error_metrics, compute_risk_weighted_metrics
from evaluation.region_masks import EvaluationRegions


@dataclass(frozen=True)
class TileAllocationDiagnostics:
    risk_weighted_mean_quality: float
    high_risk_tile_count: int
    high_risk_tile_mean_quality: float | None
    high_risk_tile_minimum_quality: int | None
    high_risk_tile_maximum_quality: int | None
    high_risk_tile_payload_bytes: int
    zero_risk_tile_count: int
    zero_risk_tile_mean_quality: float | None
    zero_risk_tile_payload_bytes: int


@dataclass(frozen=True)
class FixedEvaluation:
    decoded_rgb: np.ndarray
    full: ErrorMetrics
    full_ssim: float
    risk_weighted: ErrorMetrics
    risk_sum: float
    regions: dict[str, ErrorMetrics]
    diagnostics: TileAllocationDiagnostics
    container_bytes: bytes


def evaluate_fixed_m5c_row(
    source_rgb: np.ndarray,
    m5c_row: dict[str, str],
    combined_risk_values: tuple[float, ...],
    regions: EvaluationRegions,
    compute_ssim,
) -> FixedEvaluation:
    """Rebuild and decode exactly the M5C-selected quality tuple, not a candidate search."""

    qualities = tuple(int(value) for value in json.loads(m5c_row["tile_qualities_json"]))
    saved_tile_bytes = tuple(int(value) for value in json.loads(m5c_row["tile_jpeg_bytes_json"]))
    if len(qualities) != DEFAULT_M5_GRID.tile_count or len(saved_tile_bytes) != DEFAULT_M5_GRID.tile_count:
        raise ValueError("M5C row must contain 48 fixed qualities and payload sizes")
    encoded_tiles = encode_rgb_frame_to_tiles(_array_to_image(source_rgb), DEFAULT_M5_GRID, qualities)
    if tuple(len(tile.jpeg_payload) for tile in encoded_tiles) != saved_tile_bytes:
        raise ValueError("fixed M5C qualities no longer reproduce saved tile JPEG bytes")
    from compression.tile_container import serialize_tiled_frame

    reconstructed_container = serialize_tiled_frame(DEFAULT_M5_GRID, encoded_tiles)
    if len(reconstructed_container) != int(m5c_row["actual_total_bytes"]):
        raise ValueError("fixed M5C quality tuple no longer reproduces actual container bytes")
    parsed = deserialize_tiled_frame(reconstructed_container)
    decoded_image = decode_tiles_to_rgb(parsed.tiles, parsed.grid)
    decoded_rgb = np.asarray(decoded_image, dtype=np.uint8)
    if decoded_rgb.shape != source_rgb.shape:
        raise ValueError("decoded image shape differs from source")
    full = compute_error_metrics(source_rgb, decoded_rgb)
    risk_weighted, risk_sum = compute_risk_weighted_metrics(source_rgb, decoded_rgb, combined_risk_values)
    region_metrics = {
        "object": compute_masked_error_metrics(source_rgb, decoded_rgb, regions.eligible_object_union.values),
        "risk_support": compute_masked_error_metrics(source_rgb, decoded_rgb, regions.risk_support.values),
        "high_risk": compute_masked_error_metrics(source_rgb, decoded_rgb, regions.high_risk.values),
        "background": compute_masked_error_metrics(source_rgb, decoded_rgb, regions.background.values),
    }
    return FixedEvaluation(
        decoded_rgb=decoded_rgb,
        full=full,
        full_ssim=compute_ssim(source_rgb, decoded_rgb),
        risk_weighted=risk_weighted,
        risk_sum=risk_sum,
        regions=region_metrics,
        diagnostics=tile_allocation_diagnostics(qualities, saved_tile_bytes, combined_risk_values),
        container_bytes=reconstructed_container,
    )


def tile_allocation_diagnostics(
    qualities: tuple[int, ...], tile_payload_bytes: tuple[int, ...], combined_risk_values: tuple[float, ...]
) -> TileAllocationDiagnostics:
    if len(qualities) != 48 or len(tile_payload_bytes) != 48 or len(combined_risk_values) != 160 * 120:
        raise ValueError("M5D diagnostics require the frozen 48 tiles and 160x120 mask")
    risk_masses = []
    risk_maxima = []
    for tile_id, _, _, (left, top, right, bottom) in DEFAULT_M5_GRID.iter_tiles():
        values = [combined_risk_values[v * 160 + u] for v in range(top, bottom) for u in range(left, right)]
        risk_masses.append(sum(values))
        risk_maxima.append(max(values))
    risk_sum = sum(risk_masses)
    if risk_sum <= 0.0:
        raise ValueError("risk-weighted tile quality is undefined for an empty risk mask")
    high_ids = [tile_id for tile_id, value in enumerate(risk_maxima) if value >= 0.20]
    zero_ids = [tile_id for tile_id, value in enumerate(risk_maxima) if value == 0.0]
    return TileAllocationDiagnostics(
        risk_weighted_mean_quality=sum(risk_masses[index] * qualities[index] for index in range(48)) / risk_sum,
        high_risk_tile_count=len(high_ids),
        high_risk_tile_mean_quality=_mean_or_none(qualities, high_ids),
        high_risk_tile_minimum_quality=min((qualities[index] for index in high_ids), default=None),
        high_risk_tile_maximum_quality=max((qualities[index] for index in high_ids), default=None),
        high_risk_tile_payload_bytes=sum(tile_payload_bytes[index] for index in high_ids),
        zero_risk_tile_count=len(zero_ids),
        zero_risk_tile_mean_quality=_mean_or_none(qualities, zero_ids),
        zero_risk_tile_payload_bytes=sum(tile_payload_bytes[index] for index in zero_ids),
    )


def _mean_or_none(values: tuple[int, ...], ids: list[int]) -> float | None:
    return None if not ids else sum(values[index] for index in ids) / len(ids)


def _array_to_image(image: np.ndarray):
    from PIL import Image

    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.shape != (120, 160, 3):
        raise ValueError("source image must be a 160x120 RGB uint8 array")
    return Image.fromarray(image, mode="RGB")
