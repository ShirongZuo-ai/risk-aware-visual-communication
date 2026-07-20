# Milestone 5A Compression and Bitrate Protocol

Last updated: 2026-07-18 (Asia/Shanghai)

## Status

Milestone 5A is a design freeze only. It defines the first spatial compression prototype, fair bitrate rules, baselines, metrics, output schema, and acceptance criteria for later Milestone 5 implementation.

This document does not implement compression code, generate compressed images, run bitrate pilots, create evaluation CSVs, or claim perception, navigation, communication, or safety benefits.

## Scientific Question

Under equal actual transmitted bytes, does allocating visual quality to trajectory-conditioned collision-risk regions preserve risk-relevant visual information better than these baselines?

- Uniform compression.
- Fixed Center ROI.
- Object ROI over all visible obstacles.
- Risk ROI from the accepted combined image-risk mask.

The first evaluation is limited to image quality and risk-region quality under matched frame payload budgets. It must not claim improved object detection, remote perception, navigation success, collision reduction, or communication benefit until those downstream experiments are separately implemented and validated.

## Prototype Terminology

The first version is a tiled-JPEG spatial allocation prototype.

It is not:

- standards-compatible JPEG ROI coding;
- H.264, H.265, VVC, or AV1 ROI/QP-map coding;
- a neural codec;
- a video codec with inter-frame prediction;
- a network protocol.

The purpose is to test spatial visual resource allocation under a shared byte accounting rule. All methods must use the same encoder, container, decoder, tile grid, input frame, and budget matcher.

## Source Data

The first implementation and single-frame validation may use the accepted Milestone 4D evidence:

```text
data/frames/m4/image_risk_validation_episode_0001.png
data/logs/m4/image_risk_validation_episode_0001.csv
data/metadata/m4/image_risk_validation_episode_0001.json
data/masks/m4/image_risk_validation_episode_0001_masks.json
```

This episode is development and validation evidence for the image-risk-to-compression chain. It is not a full paper dataset. Later evaluation needs multiple snapshots, motion states, obstacle layouts, seeds, risk distributions, and risk support sizes.

## Tile Grid

The first frame size is fixed by the accepted e-puck Camera evidence:

```text
width = 160 px
height = 120 px
```

The frozen first tile grid is:

```text
tile_width = 20 px
tile_height = 20 px
columns = 8
rows = 6
tile_count = 48
```

Tiles are non-overlapping and cover the full frame without gaps. Tile IDs are row-major:

```text
tile_id = row * 8 + column
```

Pixel boundaries:

```text
x0 = column * 20
x1_exclusive = x0 + 20
y0 = row * 20
y1_exclusive = y0 + 20
```

Each tile is independently JPEG-encoded and later decoded and stitched in row-major order back to a `160x120` RGB frame.

## JPEG Parameters

All methods must use identical JPEG settings except for the selected per-tile quality values:

- input colorspace: RGB;
- output format: JPEG tile payloads;
- `progressive=False`;
- `optimize=False`;
- fixed chroma subsampling across all methods;
- one shared integer JPEG quality candidate range;
- one fixed Pillow version range when implementation begins.

Current dependency check for 5A:

- `requirements.txt` does not list Pillow.
- The current `.venv` can import Pillow `12.3.0`.

Milestone 5A does not modify dependencies. Milestone 5B must decide whether to add an explicit Pillow dependency range to `requirements.txt` before implementing tiled JPEG encoding.

## Deterministic Container and Byte Accounting

Every method writes the same deterministic tiled container. Total transmitted bytes are:

```text
total_bytes = container_header_bytes + tile_index_bytes + sum(tile_jpeg_payload_bytes)
```

The container must include at least:

- magic bytes;
- format version;
- frame width and height;
- tile width and height;
- tile count;
- tile IDs;
- tile payload lengths;
- JPEG payload bytes;
- decode metadata needed by the receiver.

Risk masks, obstacle labels, or scoring arrays are not transmitted unless a later receiver truly needs them. If quality settings, selected tile IDs, ROI metadata, or score metadata are transmitted, their bytes must be counted in `total_bytes`.

No evaluation may compare raw JPEG payloads for one method against full container bytes for another.

## Baselines

### Uniform

Uniform uses the same JPEG quality for all 48 tiles. It must not use risk masks, object geometry, or center scores. Its quality is selected by budget search.

### Center ROI

Center ROI is fixed and scene-independent. It uses a continuous score from each tile center to the camera principal point:

```text
center_score = exp(-distance_squared / (2 * sigma_center_squared))
```

The center ROI cannot move with obstacles, trajectory, or risk.

### Object ROI

Object ROI uses visible projected obstacle support only. Eligible visibility statuses are:

- `fully_visible`;
- `partially_visible`;
- `intersects_near_plane`.

For each tile:

```text
object_score(tile) = max polygon coverage fraction among eligible visible obstacles
```

Object ROI does not use planned risk, state risk, combined risk, trajectory corridors, or TTCf. It represents the assumption that all visible obstacles are important.

### Risk ROI

Risk ROI is the main proposed method. It uses the accepted combined image-risk mask from Milestone 4D.

For each tile:

```text
tile_risk_score = max combined_image_risk inside tile
```

The max aggregation is frozen for the first version so small high-risk objects are not diluted by low-risk background pixels. Mean risk, total risk mass, binary risk, planned-only risk, state-only risk, bounding-box object ROI, and oracle actual-future ROI are planned ablations, not 5A core baselines.

Risk ROI must not use RGB content, detector outputs, manual labels, future actual trajectory, or evaluation results to choose tiles.

## Score-to-Quality Allocation

Uniform has one quality value. Center ROI, Object ROI, and Risk ROI must use the same score-to-quality allocation function and the same search space.

The first frozen allocation family:

1. Compute one scalar score per tile.
2. Stable-sort tiles by descending score, then by ascending tile ID.
3. Search a shared candidate space over:
   - background quality;
   - enhancement quality;
   - top-k enhanced tiles.
4. Assign enhancement quality to the top-k tiles and background quality to all other tiles.
5. Encode through the shared tiled container.
6. Select the best under-budget configuration by the fair bitrate rule.

The candidate ranges are chosen in Milestone 5B after the uniform pilot. They must be identical for Center ROI, Object ROI, and Risk ROI.

M5C resolved the previously unspecified numeric candidate ranges through the durable decision record: background quality `1..94`, enhancement quality `2..95` with `enhancement_quality > background_quality`, and `top_k=1..48`. Every Center, Object, and Risk run exhaustively searches this identical space. If all tile scores are equal, the spatial path reduces to a Uniform-quality search so equal scores do not create an arbitrary ROI.

## Fair Bitrate Rule

For each source frame, target budget, and method, independently match actual transmitted bytes.

Rules:

- `actual_total_bytes <= target_bytes` is mandatory.
- Never choose an over-budget result.
- Among legal candidates, choose the candidate with the largest `actual_total_bytes`.
- If two candidates have equal `actual_total_bytes`, use deterministic tie-breaks: higher ROI quality, then higher background quality, then smaller top-k, then lexicographic method config.
- Record unused budget and utilization:

```text
unused_budget_bytes = target_bytes - actual_total_bytes
utilization = actual_total_bytes / target_bytes
```

Target utilization is at least `0.98` when the discrete JPEG candidate set makes it feasible. If discrete JPEG payload sizes cannot reach `0.98` without exceeding the budget, record the closest under-budget candidate and the reason.

Every output row must record:

- `target_bytes`;
- `actual_total_bytes`;
- `unused_budget_bytes`;
- `utilization`;
- `container_overhead_bytes`;
- `tile_payload_bytes`;
- quality configuration;
- encode and decode status.

## Budget Selection Process

Milestone 5A freezes the process, not the numeric budgets.

Milestone 5B must first run a Uniform JPEG pilot over the accepted source frame set to measure:

- minimum feasible payload;
- high-quality payload range;
- distribution of bytes across quality settings;
- discrete step sizes caused by tile JPEG encoding and container overhead.

After that pilot, select at least four frame budgets that:

- are feasible for all methods;
- include severe, low, medium, and high quality regimes;
- make the low budget visibly degrade the frame;
- avoid choosing only saturated high-quality points;
- are recorded in bytes/frame and bits/frame.

Bitrate in bits/second may be reported only when an explicit frame rate is defined.

The earlier `5/10/20/40 KB/frame` values are no longer frozen defaults. They may be considered only as historical rough candidates if the pilot shows they are feasible and informative.

## Decode and Rebuild

The receiver uses the same container parser for all methods.

Decode rules:

- decode every tile JPEG payload;
- stitch decoded tiles in row-major order;
- output exactly `160x120` RGB;
- do not use seam smoothing;
- do not use the original tile as fallback;
- do not apply denoising, sharpening, super-resolution, or ML post-processing.

If any tile is missing or fails to decode, the reconstructed frame fails validation.

## Metrics

### Communication Metrics

- target bytes;
- actual total bytes;
- bits/frame;
- utilization;
- unused budget bytes;
- compression ratio against the original PNG/RGB reference size, with the denominator documented;
- container overhead bytes and fraction;
- per-tile payload bytes;
- encode time;
- decode time.

### Whole-Image Quality

- MSE;
- PSNR;
- SSIM, if the dependency path is explicitly accepted;
- PSNR and SSIM are auxiliary and cannot alone establish risk-aware communication benefit.

RGB squared error is computed per pixel as the mean over the three RGB channel squared errors.

### Risk-Weighted Quality

Use the accepted combined float risk mask as the official weight map. Do not use 8-bit diagnostic PNG masks as official weights.

For one reconstructed frame:

```text
squared_error_rgb_mean(u, v) = mean_c((original(u, v, c) - reconstructed(u, v, c))^2)
weighted_MSE = sum(mask(u, v) * squared_error_rgb_mean(u, v)) / sum(mask(u, v))
risk_weighted_PSNR = 10 * log10(MAX_I_squared / weighted_MSE)
```

Where:

```text
MAX_I = 255
MAX_I_squared = 255 * 255
```

If `sum(mask) == 0`, risk-weighted metrics are not applicable and must be recorded as `NA`, not zero.

If `weighted_MSE == 0` and `sum(mask) > 0`, `risk_weighted_PSNR` is infinite and must be recorded explicitly.

### Regional Quality

The first evaluation must report:

- visible-object-region PSNR;
- risk-region PSNR;
- background PSNR;
- high-risk tile quality;
- low-risk tile quality.

The risk-region threshold must be defined before evaluation. Future ablations may compare thresholds, but the first evaluation must not choose the threshold based on which method wins.

Optional later geometry metrics may include projected-obstacle boundary quality or visible-object mask edge quality, but they are not part of 5A core acceptance.

## Fairness and Leakage Checks

Every later compression run must verify:

- same source frame for all methods;
- same tile grid;
- same JPEG encoder settings except quality;
- same deterministic container;
- same target budget;
- no method exceeds `target_bytes`;
- actual total bytes are recorded and compared;
- all discrete under-budget limitations are recorded;
- decoded frame size is exactly `160x120` RGB;
- no method copies original pixels outside decoded JPEG tiles;
- Risk ROI uses only the snapshot combined mask available at that time;
- Risk ROI does not read future actual trajectories;
- Object ROI does not read risk values;
- Center ROI does not read objects or risk values;
- Uniform does not read ROI information;
- no ROI is selected from downstream evaluation results;
- input order does not affect final tile scores or outputs;
- runs are deterministic for the same inputs.

These checks are mandatory acceptance criteria for Milestone 5B and later evaluations.

## Planned Outputs for Later Milestones

Generated data should remain ignored by Git.

Planned output roots:

```text
data/compression/m5/
data/logs/m5/
results/m5_compression/
```

Planned CSV fields include:

- `episode_id`;
- `frame_id`;
- `source_frame_path`;
- `mask_path`;
- `method`;
- `budget_id`;
- `target_bytes`;
- `actual_total_bytes`;
- `unused_budget_bytes`;
- `utilization`;
- `container_overhead_bytes`;
- `tile_count`;
- `tile_width_px`;
- `tile_height_px`;
- `background_quality`;
- `enhancement_quality`;
- `enhanced_tile_count`;
- `quality_config_json`;
- `tile_bytes_json`;
- `whole_image_mse`;
- `whole_image_psnr`;
- `risk_weighted_mse`;
- `risk_weighted_psnr`;
- `visible_object_region_psnr`;
- `risk_region_psnr`;
- `background_psnr`;
- `high_risk_tile_quality`;
- `low_risk_tile_quality`;
- `encode_time_ms`;
- `decode_time_ms`;
- `decode_status`;
- `notes`.

## Milestone 5 Roadmap Split

- Milestone 5A: freeze compression and fair-bitrate protocol.
- Milestone 5B: implement deterministic tiled-JPEG container, budget pilot, and byte matcher.
- Milestone 5C: implement Uniform, Center ROI, Object ROI, and Risk ROI allocation using the shared codec backend.
- Milestone 5D: run first single-frame M4D evidence evaluation and validate fairness.
- Milestone 5E: expand to multi-frame and multi-scene offline evaluation.
- Milestone 5F: write compression validation report and decide whether perception or navigation evaluation is justified.

## Known Limitations

- Tiled JPEG creates seams and is not a standards-compatible ROI video codec.
- No inter-frame prediction, GOP structure, motion compensation, or temporal rate control.
- No network loss, latency, packetization, or retransmission model.
- No remote object detector or perception task yet.
- No closed-loop navigation evaluation yet.
- Risk is a heuristic proxy, not a collision probability.
- The first evidence uses simulator state and static obstacles.
- The first image-risk mask version does not handle true rendered inter-object occlusion.
- Milestone 5A freezes the protocol only; it does not prove compression, communication, perception, or navigation benefit.
