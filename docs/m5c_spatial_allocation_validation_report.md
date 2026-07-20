# Milestone 5C Spatial Allocation Validation Report

Last updated: 2026-07-18 (Asia/Shanghai)

## Status

Milestone 5C is complete on `feature/m5-risk-roi-compression`. It implements and validates four tile-allocation paths on the accepted M4D development snapshot. This is an allocation and fair-byte-accounting milestone only. It does not compare PSNR, SSIM, risk-weighted image quality, perception, navigation, or a "best method".

## Inputs and Shared Backend

- Frame: `data/frames/m4/image_risk_validation_episode_0001.png`
- Frame SHA-256: `2b9e6b0b992d022a0e52fe6861b177c98841a1210a45688907d99c016f8bfa91`
- M4D projection metadata and CSV: accepted `image_risk_validation_episode_0001`
- Risk input: formal `combined` float mask in `data/masks/m4/image_risk_validation_episode_0001_masks.json`
- No-future-actual declaration: `actual_future_trajectory_used=false`
- Grid: 160x120 RGB, 20x20 tiles, 8x6 grid, 48 row-major tile IDs.
- JPEG backend: `Pillow==12.3.0`, `quality=1..95`, `progressive=False`, `optimize=False`, `subsampling=0`.
- Container: `RAVCJT1` version 1, big endian, 311 bytes of header/index overhead.

The per-tile cache is keyed only by source tile, quality, and the frozen JPEG settings. It is shared by Center, Object, and Risk allocation. Every selected result is serialized through the normal container before its byte count is reported.

## Scoring

- Uniform: continues to call the accepted M5B Uniform matcher and consumes no spatial score.
- Center ROI: `exp(-(dx_norm^2 + dy_norm^2) / (2 * 0.5^2))`, at tile centers, with principal point `(79.5, 59.5)` and half-frame coordinate normalization.
- Object ROI: maximum area fraction of an eligible M4D `clipped_polygon` inside each tile. Eligible statuses are `fully_visible`, `partially_visible`, and `intersects_near_plane`.
- Risk ROI: maximum combined float-mask value among the 400 pixels of each tile. It does not read a mask PNG, RGB pixels, object labels, or future actual trajectory.

## Shared Allocation and Fairness

Center, Object, and Risk each exhaustively search the same configurations: background quality `1..94`, enhancement quality `2..95` with enhancement strictly greater than background, and `top_k=1..48`. For every score map, tiles are ranked by descending score then ascending tile ID.

Candidates are legal only when actual serialized-container bytes are at most target bytes. Selection maximizes actual bytes, then applies this fixed order: higher enhancement quality, higher background quality, smaller top-k, lexicographic configuration. Equal score maps reduce to a Uniform-quality search.

Development budgets, retained from M5B, are `31348`, `32105`, `32729`, and `33959` bytes per frame. They are not a multi-frame or deployment bitrate claim.

## Actual Results

All 16 method-budget combinations used exact target bytes and therefore utilization `1.000` on this one source frame.

| Method | Severe q range / enhanced | Low q range / enhanced | Medium q range / enhanced | High q range / enhanced |
|---|---|---|---|---|
| Uniform | 5-5 / 0 | 25-25 / 0 | 50-50 / 0 | 80-80 / 0 |
| Center ROI | 2-66 / 5 | 12-93 / 11 | 23-91 / 15 | 4-95 / 23 |
| Object ROI | 3-69 / 9 | 21-91 / 10 | 49-95 / 5 | 60-91 / 25 |
| Risk ROI | 3-90 / 2 | 22-95 / 2 | 24-94 / 5 | 62-95 / 8 |

The M5B Uniform regression remains exact: `31348 -> q5`, `32105 -> q25`, `32729 -> q50`, and `33959 -> q80`.

## Generated Evidence

- CSV: `data/logs/m5/m5c_allocation_validation.csv`
- Metadata: `data/metadata/m5/m5c_allocation_validation.json`
- Selected containers and decoded RGB images: `data/compression/m5/m5c_selected_containers/`
- Score diagnostics: `results/m5_compression/m5c_score_maps.png`
- Quality-map diagnostics: `results/m5_compression/m5c_quality_maps.png`
- Utilization diagnostic: `results/m5_compression/m5c_budget_utilization.png`

These generated artifacts are ignored by Git. The plots show scores, selected qualities, and byte utilization only; they do not make a quality or method-superiority claim.

## Validation

`scripts/validate_m5c_allocation_validation.py` independently reloads the formal M4D frame, metadata, polygons, and combined float mask; recomputes all three score maps, every allocation candidate, selected qualities, JPEG payloads, and serialized container bytes; and compares them to the saved 16 rows. It also verifies the Uniform regression, byte accounting, decoded `160x120 RGB` dimensions, monotonic score-to-quality behavior, no-future-actual declaration, and saved selected containers.

The implementation is deterministic for repeated runs in the same Pillow/libjpeg environment. Cross-environment runs must repeat the M5B pilot and M5C matching.

## Limitations and Next Priority

Only one accepted simulator snapshot is used. The first image-risk map remains a geometric heuristic proxy, not collision probability, and does not model true rendered inter-object occlusion. No image-quality, perception, network, or navigation outcome is yet evaluated.

Next priority: Milestone 5D, the first matched-budget single-frame quality and fairness evaluation using these frozen allocation results.
