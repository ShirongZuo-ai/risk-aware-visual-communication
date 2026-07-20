"""Fair actual-byte budget matching for Milestone 5B Uniform JPEG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from PIL import Image

from compression.tiled_jpeg import DEFAULT_M5_GRID, EncodedTiledFrame, TileGrid, encode_uniform_tiled_jpeg, validate_quality


@dataclass(frozen=True)
class BudgetCandidate:
    quality: int
    actual_total_bytes: int
    tile_payload_bytes_sum: int
    container_overhead_bytes: int


@dataclass(frozen=True)
class UniformBudgetMatch:
    target_bytes: int
    actual_total_bytes: int
    unused_bytes: int
    utilization: float
    quality: int
    tile_payload_bytes: tuple[int, ...]
    container_overhead_bytes: int
    encoded_frame: EncodedTiledFrame
    candidates: tuple[BudgetCandidate, ...]


class InfeasibleBudgetError(ValueError):
    """Raised when no uniform JPEG quality fits the target budget."""


def enumerate_uniform_quality_candidates(
    image: Image.Image,
    grid: TileGrid = DEFAULT_M5_GRID,
    quality_min: int = 1,
    quality_max: int = 95,
) -> tuple[tuple[BudgetCandidate, EncodedTiledFrame], ...]:
    validate_quality(quality_min)
    validate_quality(quality_max)
    if quality_min > quality_max:
        raise ValueError("quality_min must be <= quality_max")
    candidates = []
    for quality in range(quality_min, quality_max + 1):
        encoded = encode_uniform_tiled_jpeg(image, quality, grid)
        candidates.append(
            (
                BudgetCandidate(
                    quality=quality,
                    actual_total_bytes=encoded.total_bytes,
                    tile_payload_bytes_sum=sum(encoded.tile_payload_bytes),
                    container_overhead_bytes=encoded.container_overhead_bytes,
                ),
                encoded,
            )
        )
    return tuple(candidates)


def choose_best_under_budget(
    candidates: Sequence[tuple[BudgetCandidate, EncodedTiledFrame]],
    target_bytes: int,
) -> tuple[BudgetCandidate, EncodedTiledFrame]:
    if not isinstance(target_bytes, int) or target_bytes <= 0:
        raise ValueError("target_bytes must be a positive integer")
    legal = [(candidate, encoded) for candidate, encoded in candidates if candidate.actual_total_bytes <= target_bytes]
    if not legal:
        raise InfeasibleBudgetError(f"no uniform JPEG quality fits target_bytes={target_bytes}")
    return max(legal, key=lambda item: (item[0].actual_total_bytes, item[0].quality))


def match_uniform_quality_to_budget(
    image: Image.Image,
    target_bytes: int,
    grid: TileGrid = DEFAULT_M5_GRID,
    quality_min: int = 1,
    quality_max: int = 95,
) -> UniformBudgetMatch:
    candidates_with_frames = enumerate_uniform_quality_candidates(image, grid, quality_min, quality_max)
    best, encoded = choose_best_under_budget(candidates_with_frames, target_bytes)
    return UniformBudgetMatch(
        target_bytes=target_bytes,
        actual_total_bytes=best.actual_total_bytes,
        unused_bytes=target_bytes - best.actual_total_bytes,
        utilization=best.actual_total_bytes / target_bytes,
        quality=best.quality,
        tile_payload_bytes=encoded.tile_payload_bytes,
        container_overhead_bytes=encoded.container_overhead_bytes,
        encoded_frame=encoded,
        candidates=tuple(candidate for candidate, _ in candidates_with_frames),
    )
