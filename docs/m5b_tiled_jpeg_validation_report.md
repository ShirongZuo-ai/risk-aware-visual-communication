# Milestone 5B Tiled-JPEG Validation Report

Last updated: 2026-07-18 (Asia/Shanghai)

## Status

Milestone 5B is complete on `feature/m5-risk-roi-compression`.

This milestone implements the deterministic tiled-JPEG codec/container, Uniform JPEG quality sweep pilot, and fair actual-byte matcher. It does not implement Center ROI, Object ROI, Risk ROI, method comparison, risk-weighted PSNR, SSIM, perception, networking, navigation, or machine learning.

## Dependency

The JPEG backend is Pillow:

```text
Pillow==12.3.0
```

Runtime validation used Pillow `12.3.0` from the project `.venv`.

Bit-exact JPEG payload stability is guaranteed only within the same Pillow/libjpeg environment. Cross-environment runs must rerun the Uniform pilot and budget matching.

## Tile Grid

The implemented grid matches the Milestone 5A protocol:

```text
frame_width_px=160
frame_height_px=120
tile_width_px=20
tile_height_px=20
columns=8
rows=6
tile_count=48
tile_id = tile_row * columns + tile_column
```

Pillow crop bounds use left-closed, right-open rectangles:

```text
left = tile_column * tile_width
top = tile_row * tile_height
right = left + tile_width
bottom = top + tile_height
```

The codec rejects non-matching input dimensions and converts inputs to explicit RGB before encoding.

## JPEG Parameters

All Uniform tiles use the same Pillow save settings except for quality:

```text
format="JPEG"
quality=1..95
progressive=False
optimize=False
subsampling=0
```

`subsampling=0` is used to preserve color edges in `20x20` tiles and avoid implicit Pillow defaults. Later baselines must use the same fixed settings.

## Container Format

The deterministic container uses Python `bytes` and `struct`, not pickle.

Header:

```text
endianness: big
magic: b"RAVCJT1"
version: uint16 = 1
frame_width: uint16
frame_height: uint16
tile_width: uint16
tile_height: uint16
columns: uint16
rows: uint16
tile_count: uint16
```

Tile index entry, repeated 48 times in row-major order:

```text
tile_id: uint16
payload_length: uint32
```

Payload section:

```text
JPEG payload bytes concatenated by tile_id order
```

Byte accounting:

```text
header_bytes = 23
index_entry_bytes = 6
index_bytes = 48 * 6 = 288
container_overhead_bytes = 311
total_bytes = 311 + sum(tile_jpeg_payload_bytes)
```

The container does not transmit risk masks, risk scores, method names, experiment labels, PSNR, target budget, original image pixels, trajectories, debug metadata, or tile quality values.

## Public Interfaces

Implemented modules:

```text
compression/tiled_jpeg.py
compression/tile_container.py
compression/budget_matcher.py
```

Important public functions and data structures:

```text
TileGrid
EncodedTile
EncodedTiledFrame
encode_rgb_frame_to_tiles(...)
decode_tiles_to_rgb(...)
encode_uniform_tiled_jpeg(...)
serialize_tiled_frame(...)
deserialize_tiled_frame(...)
container_overhead_bytes(...)
match_uniform_quality_to_budget(...)
```

The compression modules do not import `risk_map`, `perception`, Webots/controller APIs, OpenCV, NumPy, imageio, Shapely, torch, TensorFlow, or ffmpeg bindings.

## Uniform Pilot Evidence

Input development frame:

```text
data/frames/m4/image_risk_validation_episode_0001.png
```

Frame SHA-256:

```text
2b9e6b0b992d022a0e52fe6861b177c98841a1210a45688907d99c016f8bfa91
```

Pilot outputs:

```text
data/logs/m5/m5b_uniform_quality_sweep.csv
data/metadata/m5/m5b_uniform_pilot.json
results/m5_compression/m5b_uniform_payload_curve.png
```

These outputs are generated evidence and remain ignored by Git.

Quality sweep:

```text
qualities: 1..95 inclusive
rows: 95
min_total_bytes: 31258
max_total_bytes: 37125
container_overhead_bytes: 311
```

Key Uniform results:

| quality | total bytes | tile JPEG bytes | min tile bytes | mean tile bytes | max tile bytes |
|---:|---:|---:|---:|---:|---:|
| 1 | 31258 | 30947 | 642 | 644.729 | 655 |
| 5 | 31348 | 31037 | 642 | 646.604 | 661 |
| 25 | 32105 | 31794 | 643 | 662.375 | 712 |
| 50 | 32729 | 32418 | 644 | 675.375 | 756 |
| 80 | 33959 | 33648 | 644 | 701.000 | 828 |
| 95 | 37125 | 36814 | 645 | 766.958 | 1005 |

## Development Budgets

The pilot selected development budgets from actual Uniform container bytes at representative qualities `5`, `25`, `50`, and `80`.

These are development budgets for the accepted single M4D frame only. They are not final multi-frame budgets and must be rechecked before Milestone 5E.

| budget id | target bytes | bits/frame | source quality | matched quality | matched bytes | utilization |
|---|---:|---:|---:|---:|---:|---:|
| severe | 31348 | 250784 | 5 | 5 | 31348 | 1.000 |
| low | 32105 | 256840 | 25 | 25 | 32105 | 1.000 |
| medium | 32729 | 261832 | 50 | 50 | 32729 | 1.000 |
| high | 33959 | 271672 | 80 | 80 | 33959 | 1.000 |

The matcher exhaustively enumerates all qualities from 1 to 95. It never uses binary search and never chooses based on PSNR or any evaluation metric.

Selection rule:

1. legal candidates must satisfy `actual_total_bytes <= target_bytes`;
2. choose the legal candidate with maximum actual total bytes;
3. if bytes tie, choose the higher quality.

## Determinism

For every quality in the pilot:

- repeated encode in the same process produced identical container bytes;
- container deserialize/serialize round-trip preserved tile JPEG bytes exactly;
- decoded frame size was `160x120`;
- decoded mode was `RGB`.

The second pilot run reproduced the same payload range, budgets, metadata hash, and plot hash. The CSV hash changed because the CSV records measured encode/decode timing fields. This timing variation does not affect JPEG payload bytes, container bytes, or matched budgets.

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pip show Pillow
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q compression navigation perception risk_map scripts simulator tests
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe .\scripts\run_m5b_uniform_pilot.py
.\.venv\Scripts\python.exe .\scripts\validate_m5b_uniform_pilot.py
.\.venv\Scripts\python.exe .\scripts\run_m5b_uniform_pilot.py
.\.venv\Scripts\python.exe .\scripts\validate_m5b_uniform_pilot.py
.\.venv\Scripts\python.exe .\scripts\validate_m4d_image_risk_dataset.py .\data\logs\m4\image_risk_validation_episode_0001.csv
.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py .\data\logs\m4\projection_validation_episode_0003.csv
.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv
.\.venv\Scripts\python.exe .\scripts\evaluate_m3d_world_risk.py
.\.venv\Scripts\python.exe .\scripts\validate_m3d_report.py
```

## Validation Results

- Pillow runtime version: `12.3.0`.
- `pip check`: no broken requirements.
- `compileall`: passed.
- Unit tests: 173 passed, including 25 new M5B tests.
- Uniform pilot: exit 0, 95 quality rows.
- Pilot validator: exit 0.
- Re-run pilot: exit 0.
- Re-run pilot validator: exit 0.
- M4D validator on `image_risk_validation_episode_0001`: exit 0.
- M4C validator on `projection_validation_episode_0003`: exit 0.
- M3C validator on `risk_validation_episode_0002`: exit 0.
- M3D evaluation: exit 0.
- M3D report validator: exit 0.
- Dependency scan found no forbidden codec dependencies in the M5B compression chain.

## Limitations

- Only Uniform tiled-JPEG encoding and budget matching are implemented.
- Center ROI, Object ROI, and Risk ROI allocation are not implemented yet.
- No method comparison result exists yet.
- No risk-weighted PSNR, SSIM, object-region quality, perception accuracy, navigation safety, network simulation, or machine-learning component is implemented.
- Development budgets are based on one accepted M4D frame and must not be treated as globally valid.

## Next Priority

Milestone 5C: implement Uniform, Center ROI, Object ROI, and Risk ROI tile scoring/allocation using the shared M5B codec backend and fair actual-byte matcher.
