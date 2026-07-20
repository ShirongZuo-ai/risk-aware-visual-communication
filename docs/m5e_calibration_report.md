# Milestone 5E-C Calibration Report

Last updated: 2026-07-19 (Asia/Shanghai)

## Status

M5E-C calibration and common-budget freeze completed on `feature/m5-risk-roi-compression`. This report covers byte feasibility only. At M5E-C closeout, formal evaluation had not started, no formal frames had been generated, and no comparison of method quality or Risk ROI superiority had been performed. Current status after M5E-E: formal metrics and episode statistics exist, H1 is not fully supported, and the calibration budgets remain unchanged.

## Calibration Dataset

- Output root: `data/m5e_calibration/` (Git ignored).
- Secondary deterministic repeat: `data/m5e_calibration_repeat/` (Git ignored).
- Seeds: S1 `100100, 100101`; S2 `100200, 100201`; S3 `100300, 100301`; S4 `100400, 100401`; S5 `100500, 100501`; S6 `100600, 100601`; S7 `100700, 100701`; S8 `100800, 100801`.
- Episodes: 16 accepted primary episodes.
- Frames: 64 (`8 scenarios x 2 episodes x 4 first-crossing snapshots`).
- Snapshot progress targets: `0.20`, `0.45`, `0.70`, `0.90`.
- Replacements: none; every accepted episode used replacement index `0`.
- Dataset validation: all scenario conditions, RGB/mask hashes, Camera/risk/projection values, `combined=max(planned,state)`, and `actual_future_trajectory_used=false` passed.

## Actual-Byte Ranges

The complete legal actual-container-byte range was measured from real tiled-JPEG encodes for every frame-method pair. All methods have the same global extrema because their frozen legal spaces include the all-tile quality endpoints; each individual pair remains separately recorded in `calibration/feasible_ranges.json`.

| Method | Global minimum bytes | Global maximum bytes |
| --- | ---: | ---: |
| Uniform | 31,169 | 40,675 |
| Center ROI | 31,169 | 40,675 |
| Object ROI | 31,169 | 40,675 |
| Risk ROI | 31,169 | 40,675 |

The calibration-wide common feasible interval is `[31,240, 35,779]` bytes, width `4,539` bytes.

- `L_common=31,240` witness: `m5e_calibration_s7_seed100700_actual100700_snapshot01`, `uniform`.
- `U_common=35,779` witness: `m5e_calibration_s3_seed100300_actual100300_snapshot02`, `center_roi`.
- Every one of the 256 frame-method ranges covers this interval.

## Frozen Common Budgets

The fixed rule is `L_common + floor(fraction * 4,539)` using fractions 5%, 25%, 50%, and 80%. The resulting strictly increasing, calibration-only targets are:

| Budget | Target bytes | Bits/frame | Illustrative 10 fps bitrate |
| --- | ---: | ---: | ---: |
| severe | 31,466 | 251,728 | 2,517,280 bps |
| low | 32,374 | 258,992 | 2,589,920 bps |
| medium | 33,509 | 268,072 | 2,680,720 bps |
| high | 34,871 | 278,968 | 2,789,680 bps |

The bitrate column is a protocol conversion only, not a network model or observed runtime rate.

## Matching and Determinism

- Matched allocation records: 1,024 (`64 frames x 4 methods x 4 budgets`).
- All allocations exist and have `actual_total_bytes <= target_bytes`.
- Overall utilization: `[0.992859, 1.000000]`.
- Uniform utilization: `[0.992859, 1.000000]`; Center ROI, Object ROI, and Risk ROI: exactly `1.000000` in this calibration matrix.
- The independent validator recomputed all 256 feasible ranges, both common-interval witnesses, all four budgets, and all 1,024 allocations successfully.
- A second isolated 64-frame Webots calibration run was byte-identical for source RGB hashes, float-mask hashes, ScenarioConfig, normalized metadata, feasible ranges, frozen budgets, allocations, and actual bytes.

## Verification Actually Run

- `pip check`: passed.
- `compileall` across compression, evaluation, navigation, perception, risk-map, scripts, simulator, and tests: passed.
- Full unit suite: 263 tests passed.
- M3C official `episode_0002` validator, M3D evaluation, and M3D report validator: passed.
- M4C official `episode_0003` validator and M4D official `episode_0001` validator: passed.
- M5B Uniform-pilot, M5C allocation, M5D single-frame evaluation, and M5E-B final 32-frame smoke validators: passed.
- M5E-C validator: passed for 16 episodes, 64 frames, 256 feasible ranges, and 1,024 allocations.

## Boundaries

No PSNR, SSIM, risk-weighted quality, regional quality, method ranking, statistical test, bootstrap, perception, communication simulation, or navigation result was calculated or used to choose a budget. Risk remains a heuristic proxy, not collision probability. M5E-C freezes a fair common-byte input for later work; it does not support a multi-scene Risk ROI performance claim.

The next formal work after M5E-C had to use these four targets unchanged. M5E-D later did so for formal encoding and metric generation. M5E-E statistics must also retain these targets unchanged.
