# Milestone 5E-C Calibration and Common-Budget Freeze

Last updated: 2026-07-19 (Asia/Shanghai)

## Scope

M5E-C uses the already frozen M5E-A scenario, snapshot, Camera, risk-mask, tiled-JPEG, scoring, allocation-search, and container definitions. It creates a calibration-only dataset and freezes four method-identical complete-container-byte targets before any formal M5E evaluation.

It does not modify scenario geometry, risk, trajectories, Camera projection, masks, codec settings, score definitions, tie-breaking, or formal seeds. It does not calculate PSNR, SSIM, regional quality, method ranks, significance, bootstrap statistics, perception results, or navigation results.

## Calibration Split

- Eight primary scenario families: `S1` through `S8`.
- Two calibration primary seeds per scenario: `100000 + 100*i + j`, for scenario `i` in `1..8` and `j` in `{0,1}`.
- The exact seed set is `100100/100101` through `100800/100801`.
- The calibration replacement pool is same-scenario only: suffixes `j=50..59`, consumed in ascending order and recorded in the episode manifest.
- Formal seeds begin at `200000 + 100*i`; they are disjoint from calibration seeds.
- Each accepted episode captures the first Webots control step at progress `0.20`, `0.45`, `0.70`, and `0.90`.
- Required accepted scale: `8 x 2 x 4 = 64` frames.

The dataset runner is `scripts/run_m5e_calibration_dataset.py`. It writes only under a caller-selected project-relative output root, by default `data/m5e_calibration/`; that root is ignored by Git.

## Byte Feasibility

For every calibration frame and each frozen method (`uniform`, `center_roi`, `object_roi`, and `risk_roi`), the calibration code exhaustively measures actual `RAVCJT1` container bytes over the legal candidate space. Container header, tile index, and all JPEG payload bytes are included. JPEG quality labels or payload-only bytes are never used as budgets.

For each frame-method pair it records `L(frame, method)`, `U(frame, method)`, their allocation witnesses, candidate count, source-frame hash, mask hash, config hash, codec version, and container version. The common interval is:

```text
L_common = max L(frame, method)
U_common = min U(frame, method)
```

An empty interval stops calibration. No score, scenario, codec, or candidate-space retuning is allowed.

## Frozen Budgets

Before calculation, the fixed integer rule is:

```text
span = U_common - L_common
severe = L_common + floor(0.05 * span)
low    = L_common + floor(0.25 * span)
medium = L_common + floor(0.50 * span)
high   = L_common + floor(0.80 * span)
```

The targets must be strictly increasing and lie inside the common interval. Every frame-method-budget allocation uses the existing deterministic maximum-legal-actual-byte matcher and frozen M5C tie-break. There are `64 x 4 x 4 = 1024` required allocation records. An allocation must exist and satisfy `actual_total_bytes <= target_bytes`; it may not be selected using image-quality outcomes.

`scripts/freeze_m5e_calibration_budgets.py` writes the range table, frozen-budget manifest, and allocation matrix. `scripts/validate_m5e_calibration.py` independently recomputes the source dataset, range table, witnesses, budgets, and all allocations. `scripts/compare_m5e_calibration_runs.py` compares two isolated complete runs after excluding output-root paths, wall-clock time, and Git lifecycle metadata.

## Interpretation Boundary

Calibration is used only for common-byte feasibility and budget freezing. It is not formal evidence and cannot establish that Risk ROI is better or worse than another method. Formal M5E-D/E must use these exact frozen targets without post-hoc adjustment.
