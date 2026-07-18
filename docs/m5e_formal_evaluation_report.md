# Milestone 5E-D Formal Offline Quality Evaluation Report

Last updated: 2026-07-19 (Asia/Shanghai)

## Status

M5E-D is complete on `feature/m5-risk-roi-compression`. The formal split was generated, encoded, reconstructed, evaluated with the frozen M5D image-quality metrics, and independently validated by recomputation.

This report covers formal encoding and metric generation only. It does not perform M5E-E episode statistics, bootstrap inference, method ranking, perception evaluation, networking, machine learning, or closed-loop navigation.

## Formal Dataset

- Output root: `data/m5e_formal/` (Git ignored).
- Split: `formal`.
- Scenarios: S1-S8.
- Episodes: 64 accepted primary episodes (`8 scenarios x 8 formal seeds`).
- Frames: 256 (`64 episodes x 4 fixed-progress snapshots`).
- Seeds: formal primary seeds follow `200000 + 100 * scenario_index + seed_index`, with `seed_index=0..7`.
- Replacements: none; every accepted episode used replacement index `0`.
- Scenario balance: every scenario contributes 32 frames.
- Dataset validation: `scripts/validate_m5e_dataset.py --output-root data/m5e_formal --split formal` passed for 64 episodes and 256 snapshots.
- Provenance: all formal rows record `actual_future_trajectory_used=false`.

The formal split is disjoint from development and calibration evidence. The M4D/M5D single development frame remains excluded from M5E formal metrics.

## Frozen Budgets Used

M5E-D used the M5E-C calibration-only common complete-container-byte budgets unchanged:

| Budget | Target bytes |
| --- | ---: |
| severe | 31,466 |
| low | 32,374 |
| medium | 33,509 |
| high | 34,871 |

The common feasible interval remains `[31,240, 35,779]` bytes. No formal result was used to change these budgets.

## Reconstruction Matrix

- Methods: Uniform, Center ROI, Object ROI, Risk ROI.
- Budgets: severe, low, medium, high.
- Reconstructions: 4,096 (`256 frames x 4 methods x 4 budgets`).
- Allocation records: 4,096.
- Metric records: 4,096.
- Over-budget records: 0.
- Actual-byte utilization range: `[0.991568925468154, 1.0]`.
- Container format: `RAVCJT1`, version `1`.
- JPEG settings: frozen M5B tiled-JPEG settings through Pillow `12.3.0`.
- Metrics: frozen M5D full-image MSE/PSNR/SSIM, continuous risk-weighted MSE/PSNR, eligible-object, risk-support, high-risk, and background regional MSE/PSNR.

Some formal frames, especially low-risk-control cases, have an empty high-risk region under the frozen threshold `combined_risk >= 0.20`; those regional high-risk metrics are recorded as `undefined` rather than treated as validation failures.

## Artifacts

- Allocation table: `data/m5e_formal/formal_evaluation/m5e_d_formal_allocations.csv`
- Metric table: `data/m5e_formal/formal_evaluation/m5e_d_formal_quality_metrics.csv`
- Run metadata: `data/m5e_formal/formal_evaluation/m5e_d_formal_evaluation_metadata.json`
- Validation summary: `data/m5e_formal/formal_evaluation/m5e_d_formal_validation_summary.json`
- Containers: `data/m5e_formal/formal_evaluation/containers/`
- Decoded images: `data/m5e_formal/formal_evaluation/decoded/`
- Descriptive diagnostics:
  - `results/m5_compression/m5e_formal/m5e_d_byte_utilization_heatmap.png`
  - `results/m5_compression/m5e_formal/m5e_d_full_psnr_boxplot.png`
  - `results/m5_compression/m5e_formal/m5e_d_risk_weighted_psnr_boxplot.png`
  - `results/m5_compression/m5e_formal/m5e_d_scenario_method_summary.png`
  - `results/m5_compression/m5e_formal/m5e_d_representative_reconstructions.png`

Generated data and results remain ignored by Git.

## Determinism

A formal repeat subset was generated under `data/m5e_formal_repeat_subset/` using seed index `0` for all eight scenarios:

- Repeat subset episodes: 8.
- Repeat subset frames: 32.
- Repeat subset reconstructions: 512.
- Repeat subset over-budget records: 0.
- Repeat subset validation: passed with recomputation.
- Determinism comparison: 512 shared frame-method-budget rows matched exactly for source/mask/config hashes, normalized metadata hash, allocation identity, actual bytes, container hash, reconstruction hash, tile qualities, tile payload bytes, and frozen metrics.

## Verification Actually Run

- `.\.venv\Scripts\python.exe -m pip check`: no broken requirements found.
- `.\.venv\Scripts\python.exe -m compileall -q compression evaluation navigation perception risk_map scripts simulator tests`: passed.
- `.\.venv\Scripts\python.exe -m unittest tests.test_m5e_formal_helpers`: 5 tests passed.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`: 268 tests passed.
- `.\.venv\Scripts\python.exe scripts\run_m5e_formal_dataset.py --output-root data/m5e_formal --overwrite`: passed, 64 episodes / 256 frames.
- `.\.venv\Scripts\python.exe scripts\validate_m5e_dataset.py --output-root data/m5e_formal --split formal`: passed.
- `.\.venv\Scripts\python.exe scripts\run_m5e_formal_evaluation.py --output-root data/m5e_formal --calibration-root data/m5e_calibration --overwrite`: passed, 4,096 reconstructions, 0 over budget.
- `.\.venv\Scripts\python.exe scripts\validate_m5e_formal_evaluation.py --output-root data/m5e_formal --calibration-root data/m5e_calibration`: passed, recomputed 4,096 metric rows.
- `.\.venv\Scripts\python.exe scripts\run_m5e_formal_dataset.py --output-root data/m5e_formal_repeat_subset --seed-index 0 --overwrite`: passed, 8 episodes / 32 frames.
- `.\.venv\Scripts\python.exe scripts\run_m5e_formal_evaluation.py --output-root data/m5e_formal_repeat_subset --calibration-root data/m5e_calibration --allow-subset --overwrite`: passed, 512 reconstructions, 0 over budget.
- `.\.venv\Scripts\python.exe scripts\validate_m5e_formal_evaluation.py --output-root data/m5e_formal_repeat_subset --calibration-root data/m5e_calibration --allow-subset`: passed, recomputed 512 metric rows.
- `.\.venv\Scripts\python.exe scripts\compare_m5e_formal_determinism.py --reference-root data/m5e_formal --repeat-root data/m5e_formal_repeat_subset`: passed, 512 shared rows.
- `.\.venv\Scripts\python.exe scripts\plot_m5e_formal_diagnostics.py --output-root data/m5e_formal --results-root results/m5_compression/m5e_formal`: passed.

## Interpretation Boundary

M5E-D establishes a complete, deterministic, byte-fair formal metric table. It does not establish that Risk ROI is superior to Uniform, Center ROI, or Object ROI. Episode aggregation, paired bootstrap statistics, scenario-stratified diagnostics, and scientific support or nonsupport remain M5E-E work.

Risk remains a heuristic proxy, not a collision probability. The tiled-JPEG backend remains a spatial allocation prototype, not a standards-compatible JPEG ROI codec. Formal data are evaluation evidence and must not be used for machine-learning training.

The next mainline milestone is M5E-E episode statistics and diagnostics using these frozen M5E-D outputs.
