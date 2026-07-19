# Milestone 5E-E Episode-Level Statistical Analysis Report

Last updated: 2026-07-19 (Asia/Shanghai)

## Status and Scope

M5E-E is complete on `feature/m5-risk-roi-compression`. It analyzes the frozen M5E-D formal metric table without changing scenarios, seeds, snapshots, methods, metrics, thresholds, allocation rules, codec settings, or the M5E-C budgets.

The statistical unit is the episode. Four same-episode snapshots are aggregated before inference. No frame is treated as an independent observation. This report is offline image-quality evidence over the frozen heuristic combined-risk mask; it is not perception, collision, navigation, network, or robot-safety evidence.

## Engineering Validity

- Source formal metric SHA-256: `6d9089c98937ee061dd91fc1e67cbb09e8fc3f88b4627df91bb05b295298700d`.
- Formal input: 64 episodes, 256 frames, and 4,096 method-budget metric rows.
- Episode structure: eight scenarios, eight episodes per scenario, and four snapshots per episode.
- Primary pairs: 384 valid episode pairs (`64 episodes x 3 baselines x 2 primary budgets`).
- Formal replacements: zero.
- Missing or duplicate primary pairs: zero.
- Bootstrap: paired, scenario-stratified, 10,000 replicates, seed `20260718`.
- Overall estimator: equal-weight mean of the eight scenario means.
- Confidence interval: percentile 95% interval.
- Primary metric: continuous combined-risk-weighted PSNR.
- Primary comparisons: Risk ROI minus Uniform, Center ROI, and Object ROI.
- Primary budgets: severe `31466` and low `32374` bytes.
- All primary byte-fairness checks passed the frozen `0.5%` target-byte tolerance.
- Empty high-risk regions remain `undefined`; no NaN, empty region, or invalid value is replaced with a favorable number.

Secondary high-risk episode diagnostics average only structurally defined frame values and record the valid and undefined frame counts. An episode with no defined high-risk frame remains undefined. This rule does not affect the fully defined primary metric.

## Primary Scientific Outcomes

Positive values favor Risk ROI. Values are episode-level equal-scenario mean RW-PSNR differences in dB.

| Budget | Comparison | Mean difference | 95% bootstrap CI | Median | Win/Tie/Loss |
| --- | --- | ---: | ---: | ---: | ---: |
| Severe | Risk - Uniform | -1.122 | [-1.326, -0.919] | -1.055 | 14/0/50 |
| Severe | Risk - Center ROI | 0.520 | [0.219, 0.820] | 0.351 | 41/0/23 |
| Severe | Risk - Object ROI | -0.883 | [-1.108, -0.660] | -0.850 | 17/0/47 |
| Low | Risk - Uniform | 1.798 | [1.422, 2.194] | 0.553 | 44/0/20 |
| Low | Risk - Center ROI | 2.964 | [2.511, 3.400] | 2.397 | 57/0/7 |
| Low | Risk - Object ROI | 0.191 | [-0.219, 0.606] | 0.052 | 32/1/31 |

Mean actual-byte differences were `24.418` bytes for severe Risk-minus-Uniform and `17.789` bytes for low Risk-minus-Uniform, below the frozen fairness limits of `157.33` and `161.87` bytes. The other four primary mean byte differences were zero.

### H1

The pre-registered H1 is not fully supported. Risk ROI is better than Center ROI at both primary budgets and better than Uniform at low budget, with intervals wholly above zero. It is worse than Uniform and Object ROI at severe budget. The low-budget Risk-minus-Object mean is small and positive, but its interval crosses zero.

### H2

The pre-registered H2 direction is supported at both primary budgets. The frozen `(S2,S6) - (S1,S8)` Risk-minus-Object contrasts are:

| Budget | Contrast | 95% bootstrap CI |
| --- | ---: | ---: |
| Severe | 1.031 | [0.001, 1.927] |
| Low | 1.956 | [1.023, 2.883] |

This is a scenario-contrast result, not evidence that Risk ROI is generally better than Object ROI. The severe overall Risk-minus-Object effect is negative, and the low overall interval crosses zero.

### H3

All six frozen Risk-minus-Center contrasts `(S2,S3,S4) - S1` have the predicted positive direction. Severe-budget contrasts for S2/S3/S4 are `1.590`, `3.535`, and `2.647` dB. Low-budget contrasts are `1.164`, `2.945`, and `2.179` dB. The low-budget S2 contrast interval crosses zero; the other five contrast intervals are wholly positive.

### Basic Initial Support Gate

The protocol's complete basic initial support gate is not met at either primary budget.

- Severe Risk-minus-Object has a negative mean and an interval wholly below zero.
- Low Risk-minus-Object has a positive mean, an interval that is not wholly below zero, sufficient relevant-scenario win rates, and byte fairness, but fails the no-single-scenario-dominance requirement.
- Engineering validity is independent of this scientific nonsupport.

## Secondary Outcomes

Risk ROI's primary gains are accompanied by broad whole-image and background-quality costs. Overall mean Risk-minus-baseline differences were:

| Metric / budget | Uniform | Center ROI | Object ROI |
| --- | ---: | ---: | ---: |
| Full PSNR / severe | -2.972 | -0.250 | -0.910 |
| Full PSNR / low | -2.820 | -0.612 | -0.689 |
| Background PSNR / severe | -3.140 | -0.279 | -0.812 |
| Background PSNR / low | -3.105 | -0.749 | -0.657 |
| Object PSNR / severe | -1.381 | 0.268 | -1.272 |
| Object PSNR / low | 0.851 | 2.055 | -0.797 |

These diagnostics show that improved risk-weighted quality does not imply improved full-frame, background, or object-region quality. High-risk-region metrics are descriptive only because many frozen high-risk regions are structurally empty.

## Scenario Heterogeneity

The table reports primary-budget episode-level mean RW-PSNR differences. Each cell is Risk-minus-Uniform / Risk-minus-Center / Risk-minus-Object in dB.

| Scenario | Severe | Low |
| --- | ---: | ---: |
| S1 | -1.766 / -1.538 / -1.557 | -0.004 / 1.022 / -1.253 |
| S2 | -1.570 / 0.052 / -0.191 | -0.086 / 2.185 / 1.105 |
| S3 | -1.476 / 1.997 / -0.951 | 1.166 / 3.967 / -0.032 |
| S4 | -2.831 / 1.109 / -2.859 | 1.813 / 3.200 / 0.262 |
| S5 | -0.239 / 1.539 / -0.764 | -0.023 / 2.521 / -0.617 |
| S6 | 0.256 / 0.631 / 0.679 | 3.634 / 3.326 / 1.949 |
| S7 | -1.682 / -0.399 / -1.405 | -0.615 / 0.331 / -0.277 |
| S8 | 0.332 / 0.773 / -0.017 | 8.498 / 7.161 / 0.395 |

S6 is the most consistent favorable scenario across the primary comparisons. S5 supports Risk over Center but not over Uniform or Object. S7 is mostly unfavorable. S2 shows the expected low-budget separation from Object and Center, but not a severe-budget overall gain.

S8 does not behave as a null low-risk control against Uniform or Center at low budget. Its gains are large enough to dominate the positive low-budget Risk-minus-Uniform result and contribute to the low-budget Risk-minus-Object dominance failure. This unexpected outcome is retained. One plausible diagnostic interpretation is that continuous RW-PSNR normalizes distortion by the very small positive risk mass, so a low-risk scene is not automatically a null test for this metric. That interpretation is exploratory and does not change the frozen metric.

## Negative and Null Findings

- H1 is not fully supported.
- Severe Risk-minus-Uniform and Risk-minus-Object are negative with intervals wholly below zero.
- Low Risk-minus-Object is near null: 32 wins, one tie, 31 losses, and a 95% interval crossing zero.
- S5 and S7 do not show the anticipated broad Risk ROI advantage.
- S8 contradicts the expectation of no obvious low-risk-control gain against Uniform and Center.
- Full-frame and background PSNR are lower for Risk ROI in all six primary baseline-budget summaries.
- Exploratory correlations between episode risk/disagreement covariates and Risk ROI gain are mixed and cannot be interpreted as collision-risk prediction.

## Machine-Readable Outputs

Generated outputs are ignored by Git under `data/m5e_formal/statistical_analysis/`:

- `episode_level_metrics.csv`
- `paired_effects.csv`
- `bootstrap_results.csv`
- `scenario_diagnostics.csv`
- `win_tie_loss.csv`
- `figure_inputs.csv`
- `statistical_summary.json`
- `analysis_manifest.json`
- `failure_log.json`
- `figure_manifest.json`
- `m5e_e_validation_summary.json`

Nine deterministic figures are under `results/m5_compression/m5e_statistics/`:

- `primary_paired_effect_forest.png`
- `primary_bootstrap_ci.png`
- `scenario_budget_effect_heatmap.png`
- `episode_paired_scatter.png`
- `primary_win_tie_loss.png`
- `rw_vs_full_psnr_tradeoff.png`
- `background_quality_tradeoff.png`
- `s2_s5_s6_diagnostics.png`
- `s8_low_risk_control.png`

## Determinism

A second complete M5E-E run was written to `data/m5e_formal/statistical_analysis_repeat/`. Six CSV files, four JSON files after allowed timestamp normalization, all bootstrap sample hashes, all confidence intervals, all figure-input rows, and all nine PNG files matched exactly.

## Validation Actually Run

- Project `.venv` `pip check`: passed.
- Repository `compileall`: passed.
- Full unit suite: 285 tests passed.
- M3C, M3D evaluation/report, M4C, M4D, M5B, M5C, and M5D validators: passed.
- M5E-B final acceptance smoke validator: passed for 8 episodes / 32 snapshots.
- M5E-C dataset and independent calibration validators: passed for 16 episodes / 64 frames / 1,024 allocations.
- M5E-D dataset and formal evaluation validators: passed for 64 episodes / 256 frames / 4,096 recomputed metric rows.
- M5E-E validator: passed for 64 episodes, 384 primary pairs, 10,000 bootstrap iterations, and nine figures.
- M5E-E deterministic comparison: passed.

The historical smoke data directly under `data/` predate accepted S3/S5/S7 corrections and are rejected by the current config-hash validator. The canonical M5E-B regression evidence is `data/m5e_final_acceptance_smoke/`, which passed. No stale smoke frame enters calibration, formal M5E-D, or M5E-E statistics.

## Limitations

- Only eight static-AABB scenario families and 64 formal episodes are evaluated.
- The risk value is a heuristic proxy, not collision probability.
- Continuous RW-PSNR measures image distortion under the frozen risk mask; it does not measure detector recall, navigation success, or collisions.
- The tiled-JPEG implementation is a spatial allocation prototype, not a standards-compatible JPEG or video ROI codec.
- Scenario, budget, regional, and correlation diagnostics outside the six pre-registered comparisons are secondary or exploratory.
- No p-values are reported. The six primary comparisons are reported together, and no post-hoc multiple-comparison method is selected.

## What Remains Unproven

M5E-E does not prove lower collision rate, higher navigation success, guaranteed safety, real-network performance, real-robot performance, or superiority over semantic communication methods. Machine learning and closed-loop navigation remain unstarted. M5E-F independent full-evidence acceptance also remains unstarted.

The only next mainline milestone is M5E-F formal validation and acceptance. It must preserve the M5E-E outputs and separate engineering acceptance from scientific support or nonsupport.
