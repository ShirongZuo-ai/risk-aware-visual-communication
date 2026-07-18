"""Shared score-to-quality allocation and actual-byte matching for M5C."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from PIL import Image

from compression.tile_container import container_overhead_bytes, serialize_tiled_frame
from compression.tile_scoring import TileScoreMap
from compression.tiled_jpeg import DEFAULT_M5_GRID, EncodedTile, EncodedTiledFrame, TileGrid, encode_rgb_frame_to_tiles, validate_quality


@dataclass(frozen=True)
class AllocationSearchSpace:
    """Frozen shared search space for every non-Uniform method."""

    background_quality_min: int = 1
    background_quality_max: int = 94
    enhancement_quality_min: int = 2
    enhancement_quality_max: int = 95
    top_k_min: int = 1
    top_k_max: int = 48

    def __post_init__(self) -> None:
        validate_quality(self.background_quality_min)
        validate_quality(self.background_quality_max)
        validate_quality(self.enhancement_quality_min)
        validate_quality(self.enhancement_quality_max)
        if self.background_quality_min > self.background_quality_max:
            raise ValueError("background quality bounds are invalid")
        if self.enhancement_quality_min > self.enhancement_quality_max:
            raise ValueError("enhancement quality bounds are invalid")
        if self.top_k_min < 1 or self.top_k_max > DEFAULT_M5_GRID.tile_count or self.top_k_min > self.top_k_max:
            raise ValueError("top-k bounds are invalid for the frozen grid")


DEFAULT_ALLOCATION_SEARCH_SPACE = AllocationSearchSpace()


@dataclass(frozen=True)
class SpatialAllocationConfig:
    background_quality: int
    enhancement_quality: int
    top_k: int


@dataclass(frozen=True)
class SpatialBudgetMatch:
    method: str
    target_bytes: int
    actual_total_bytes: int
    unused_bytes: int
    utilization: float
    qualities: tuple[int, ...]
    selected_config: SpatialAllocationConfig
    tile_payload_bytes: tuple[int, ...]
    container_overhead_bytes: int
    container_bytes: bytes
    deterministic_tie_break: str
    candidate_count: int
    feasible_candidate_count: int
    score_map: TileScoreMap

    @property
    def unique_quality_count(self) -> int:
        return len(set(self.qualities))


class InfeasibleSpatialBudgetError(ValueError):
    """Raised when no legal allocation fits an actual byte budget."""


class EncodedTileCache:
    """One source-frame/quality payload cache shared across allocation methods."""

    def __init__(self, grid: TileGrid, tiles_by_quality: dict[int, tuple[EncodedTile, ...]]) -> None:
        self.grid = grid
        self._tiles_by_quality = dict(tiles_by_quality)
        if not self._tiles_by_quality:
            raise ValueError("tile cache must contain at least one quality")
        for quality, tiles in self._tiles_by_quality.items():
            validate_quality(quality)
            if len(tiles) != grid.tile_count:
                raise ValueError("every cached quality must contain every tile")
            if tuple(tile.tile_id for tile in tiles) != tuple(range(grid.tile_count)):
                raise ValueError("cached tiles must be row-major")
            if any(tile.quality != quality for tile in tiles):
                raise ValueError("cached tile quality mismatch")

    @property
    def available_qualities(self) -> tuple[int, ...]:
        return tuple(sorted(self._tiles_by_quality))

    @classmethod
    def build(
        cls,
        image: Image.Image,
        grid: TileGrid = DEFAULT_M5_GRID,
        quality_min: int = 1,
        quality_max: int = 95,
    ) -> "EncodedTileCache":
        validate_quality(quality_min)
        validate_quality(quality_max)
        if quality_min > quality_max:
            raise ValueError("quality_min must be <= quality_max")
        return cls(
            grid,
            {
                quality: encode_rgb_frame_to_tiles(image, grid, (quality,) * grid.tile_count)
                for quality in range(quality_min, quality_max + 1)
            },
        )

    def tile_payload_length(self, tile_id: int, quality: int) -> int:
        return len(self._tiles_by_quality[quality][tile_id].jpeg_payload)

    def encode(self, qualities: Sequence[int]) -> EncodedTiledFrame:
        if len(qualities) != self.grid.tile_count:
            raise ValueError("qualities length must equal grid.tile_count")
        selected = tuple(self._tiles_by_quality[int(quality)][tile_id] for tile_id, quality in enumerate(qualities))
        container = serialize_tiled_frame(self.grid, selected)
        return EncodedTiledFrame(self.grid, selected, container)


def build_tile_cache(
    image: Image.Image,
    grid: TileGrid = DEFAULT_M5_GRID,
    quality_min: int = 1,
    quality_max: int = 95,
) -> EncodedTileCache:
    return EncodedTileCache.build(image, grid, quality_min, quality_max)


def qualities_for_config(score_map: TileScoreMap, config: SpatialAllocationConfig) -> tuple[int, ...]:
    if config.top_k < 0 or config.top_k > score_map.grid.tile_count:
        raise ValueError("top_k is outside the grid")
    validate_quality(config.background_quality)
    validate_quality(config.enhancement_quality)
    ranked = score_map.stable_ranked_tile_ids
    enhanced = set(ranked[: config.top_k])
    return tuple(config.enhancement_quality if tile_id in enhanced else config.background_quality for tile_id in range(score_map.grid.tile_count))


def match_spatial_allocation_to_budget(
    tile_score_map: TileScoreMap,
    encoded_tile_cache: EncodedTileCache,
    target_bytes: int,
    allocation_search_space: AllocationSearchSpace = DEFAULT_ALLOCATION_SEARCH_SPACE,
) -> SpatialBudgetMatch:
    return match_spatial_allocations_to_budgets(
        tile_score_map,
        encoded_tile_cache,
        (target_bytes,),
        allocation_search_space,
    )[0]


def match_spatial_allocations_to_budgets(
    tile_score_map: TileScoreMap,
    encoded_tile_cache: EncodedTileCache,
    target_bytes_values: Iterable[int],
    allocation_search_space: AllocationSearchSpace = DEFAULT_ALLOCATION_SEARCH_SPACE,
) -> tuple[SpatialBudgetMatch, ...]:
    """Exhaustively scan shared configurations once and match one or more budgets."""

    if tile_score_map.grid != encoded_tile_cache.grid:
        raise ValueError("tile score grid must match encoded tile cache grid")
    targets = tuple(target_bytes_values)
    if not targets or any(not isinstance(target, int) or target <= 0 for target in targets):
        raise ValueError("target bytes must be positive integers")
    qualities = encoded_tile_cache.available_qualities
    required = set(range(allocation_search_space.background_quality_min, allocation_search_space.enhancement_quality_max + 1))
    if not required.issubset(qualities):
        raise ValueError("tile cache does not cover the allocation search space")

    best: dict[int, tuple[int, SpatialAllocationConfig] | None] = {target: None for target in targets}
    feasible: dict[int, int] = {target: 0 for target in targets}
    candidate_count = 0
    overhead = container_overhead_bytes(encoded_tile_cache.grid)
    ranked = tile_score_map.stable_ranked_tile_ids
    all_equal = tile_score_map.minimum_score == tile_score_map.maximum_score

    if all_equal:
        candidates = (
            SpatialAllocationConfig(quality, quality, 0)
            for quality in range(allocation_search_space.background_quality_min, allocation_search_space.enhancement_quality_max + 1)
        )
        for config in candidates:
            total = overhead + sum(encoded_tile_cache.tile_payload_length(tile_id, config.background_quality) for tile_id in range(encoded_tile_cache.grid.tile_count))
            candidate_count += 1
            _consider_candidate(best, feasible, targets, total, config)
    else:
        for background_quality in range(allocation_search_space.background_quality_min, allocation_search_space.background_quality_max + 1):
            baseline = sum(encoded_tile_cache.tile_payload_length(tile_id, background_quality) for tile_id in range(encoded_tile_cache.grid.tile_count))
            for enhancement_quality in range(
                max(background_quality + 1, allocation_search_space.enhancement_quality_min),
                allocation_search_space.enhancement_quality_max + 1,
            ):
                payload = baseline
                for top_k, tile_id in enumerate(ranked, start=1):
                    if top_k > allocation_search_space.top_k_max:
                        break
                    payload += encoded_tile_cache.tile_payload_length(tile_id, enhancement_quality) - encoded_tile_cache.tile_payload_length(tile_id, background_quality)
                    if top_k < allocation_search_space.top_k_min:
                        continue
                    config = SpatialAllocationConfig(background_quality, enhancement_quality, top_k)
                    candidate_count += 1
                    _consider_candidate(best, feasible, targets, overhead + payload, config)

    matches = []
    for target in targets:
        selected = best[target]
        if selected is None:
            raise InfeasibleSpatialBudgetError(f"no spatial allocation fits target_bytes={target}")
        actual_total_bytes, config = selected
        selected_qualities = qualities_for_config(tile_score_map, config)
        encoded = encoded_tile_cache.encode(selected_qualities)
        if encoded.total_bytes != actual_total_bytes:
            raise AssertionError("cached payload accounting does not match serialized container bytes")
        matches.append(
            SpatialBudgetMatch(
                method=tile_score_map.method,
                target_bytes=target,
                actual_total_bytes=actual_total_bytes,
                unused_bytes=target - actual_total_bytes,
                utilization=actual_total_bytes / target,
                qualities=selected_qualities,
                selected_config=config,
                tile_payload_bytes=encoded.tile_payload_bytes,
                container_overhead_bytes=encoded.container_overhead_bytes,
                container_bytes=encoded.container_bytes,
                deterministic_tie_break="max_actual_bytes, higher_enhancement_quality, higher_background_quality, smaller_top_k, lexicographic_config",
                candidate_count=candidate_count,
                feasible_candidate_count=feasible[target],
                score_map=tile_score_map,
            )
        )
    return tuple(matches)


def _consider_candidate(best, feasible, targets, total: int, config: SpatialAllocationConfig) -> None:
    for target in targets:
        if total > target:
            continue
        feasible[target] += 1
        current = best[target]
        if current is None or _candidate_key(total, config) > _candidate_key(current[0], current[1]):
            best[target] = (total, config)


def _candidate_key(total: int, config: SpatialAllocationConfig) -> tuple[int, int, int, int, tuple[int, int, int]]:
    return (
        total,
        config.enhancement_quality,
        config.background_quality,
        -config.top_k,
        (config.background_quality, config.enhancement_quality, config.top_k),
    )
