# Milestone 5E Multi-Scene Offline Evaluation Protocol

Last updated: 2026-07-18 (Asia/Shanghai)

## 1. Status and Scope

This document freezes Milestone 5E before any M5E dataset is generated. M5E evaluates the existing Uniform, Center ROI, Object ROI, and Risk ROI methods across multiple static-obstacle scenes, episodes, and snapshots under matched actual transmitted byte budgets.

M5E-A is design-only. It does not create or modify a Webots world, controller, configuration, frame, CSV, JSON, decoded image, or figure. It does not rerun a JPEG pilot. M5E-B through M5E-F must implement this protocol without changing the already accepted risk, projection, mask, compression, allocation, or metric definitions.

The first M5E version remains inside the validated model boundary:

- native Windows and Webots R2025a;
- one e-puck with a `160x120` forward RGB Camera;
- static, unrotated AABB Box obstacles;
- current planned command-conditioned and State-only trajectories;
- the existing maximum-combined heuristic risk mask;
- deterministic `20x20` tiled JPEG with the `RAVCJT1` container;
- offline image-quality evaluation only.

Dynamic obstacles, semantic classes, true inter-object occlusion, new uncertainty algorithms, network simulation, remote perception, navigation, collision-rate evaluation, learned allocation, and publication-level innovations are out of scope.

## 2. Scientific Question and Pre-Registered Hypotheses

Core question:

> Under the same complete actual transmitted byte budget, does trajectory-conditioned Risk ROI preserve collision-relevant visual-region quality more consistently across motion states, obstacle layouts, and risk distributions?

Frozen methods:

1. Uniform
2. Center ROI
3. Object ROI
4. Risk ROI

No additional proposed method or ablation is added in M5E.

Pre-registered hypotheses, not conclusions:

- **H1:** At severe and low budgets, Risk ROI has higher continuous risk-weighted PSNR than Uniform, Center ROI, and Object ROI.
- **H2:** Risk ROI's advantage over Object ROI is larger when visible object area and future-trajectory collision relevance disagree. Operationally, the mean Risk-minus-Object difference in S2 and S6 is compared with the corresponding mean in S1 and S8 at severe and low budgets.
- **H3:** Center ROI can be a strong baseline for straight motion with risk near the principal point, but its advantage should weaken for off-trajectory distractors and left/right turns. Operationally, Risk-minus-Center differences in S2, S3, and S4 are compared with S1 at severe and low budgets.

No M5D method ordering may change these hypotheses, scenario rules, methods, thresholds, metrics, or budgets.

## 3. Frozen Components

The following are fixed for all calibration and formal M5E data:

- Center ROI normalized Gaussian `sigma=0.5` and principal-point input;
- Object ROI maximum eligible clipped-polygon coverage per tile;
- Risk ROI maximum combined float risk per tile;
- spatial allocation candidate space and deterministic M5C tie-break;
- `HIGH_RISK_THRESHOLD=0.20`;
- `160x120` RGB frame, `20x20` tiles, 8 columns, 6 rows, and 48 row-major tiles;
- Pillow `12.3.0` JPEG parameters: qualities `1..95`, `progressive=False`, `optimize=False`, and `subsampling=0`;
- `RAVCJT1` version 1 container and 311-byte overhead;
- M5D MSE, PSNR, SSIM, continuous risk-weighted, and region-mask definitions;
- current risk parameters, Camera model, projection, pixel-center rasterization, max-union mask semantics, and no-future-actual rule.

M5E must not use image quality or formal outcomes to retune any frozen component.

## 4. Dataset Splits and Leakage Barrier

### 4.1 Existing development evidence

`image_risk_validation_episode_0001` is development evidence used by M4D, M5B, M5C, and M5D. It is excluded from calibration and formal M5E manifests, budget selection, statistics, and claims.

### 4.2 Calibration dataset

Calibration is used only to validate the generator and snapshot triggers, verify scene coverage, estimate runtime, establish the common feasible byte interval, and freeze four common target budgets. It must not be used to tune Center/Object/Risk scoring, allocation search, risk or metric thresholds, select a preferred method, or support scientific claims.

Calibration contains 8 scenario families x 2 primary seeds x 4 snapshots = **64 frames**.

### 4.3 Formal evaluation dataset

Formal data are disjoint from development and calibration by split label, seed, episode ID, frame ID, and file path. Formal evaluation contains 8 scenario families x 8 valid seeds x 4 snapshots = **256 frames**, producing 256 x 4 methods x 4 budgets = **4096 reconstructed results**.

Once formal generation starts, no score, allocation, metric, threshold, budget, snapshot trigger, scenario validation rule, or scenario weight may change. A genuine implementation bug requires a documented fix followed by a complete regeneration and re-evaluation of all formal data. Partial reuse before and after the fix is forbidden.

### 4.4 Seed namespaces

For scenario index `i` in `1..8`:

- calibration primary seeds: `100000 + 100*i + j`, where `j=0,1`;
- calibration replacement seeds: the same expression with `j=50..59`, used in ascending order;
- formal primary seeds: `200000 + 100*i + j`, where `j=0..7`;
- formal replacement seeds: the same expression with `j=50..79`, used in ascending order.

The generator version and all sampled parameters must be recorded. A seed maps deterministically to one scene configuration. Replacement seeds never cross scenario families or splits.

## 5. Scale and Runtime Estimate

The requested scale is retained. Existing one-frame runs took approximately 5.7 seconds for 16 M5C allocations and 3.4 seconds for 16 M5D reconstructions/metrics on this machine. Linear extrapolation gives approximately 10 minutes for 64 calibration frames and 39 minutes for 256 formal frames for codec/allocation/evaluation work, before Webots generation, file IO, plotting, and independent validation. The expected end-to-end workload remains practical within roughly two hours on the current host, so no sample-size reduction is justified before data generation.

The formal dataset may not be reduced after method results are observed. Any future pre-data scale amendment must retain equal seeds per scenario, balanced S3/S4 counts, at least 5 formal seeds per scenario, and at least 160 formal frames.

## 6. Scenario Families and Machine Validation

Every episode has exactly one `primary_scenario` in `S1..S8`. It may also carry an ordered list of `secondary_scenario_labels` when other conditions happen to hold. Formal per-scenario statistics use only the primary label, preventing double counting.

Common definitions:

- unless a condition explicitly says otherwise, scenario-family conditions are evaluated at snapshot 2 (`p=0.70`); conditions about progression, turn onset, or all-snapshot bounds use the snapshots named in that rule;
- eligible visibility is `fully_visible`, `partially_visible`, or `intersects_near_plane`;
- `combined_max` is the maximum visible eligible-obstacle combined risk;
- `planned_yaw_change` is final minus initial unwrapped yaw of the 2.0-second planned trajectory;
- principal-point horizontal offset uses the risk-weighted centroid of the combined float mask;
- polygon area uses the pixel-center rasterized eligible clipped polygon;
- ties for maximum area or risk use ascending obstacle ID;
- high risk means `combined_risk >= 0.20`;
- low risk means `0 < combined_risk < 0.10`;
- every valid episode has at least one eligible obstacle and positive combined risk sum at all four snapshots.

### S1 Straight collision-relevant obstacle

- `abs(planned_yaw_change) <= 0.10 rad`;
- at least one eligible obstacle enters the planned corridor within the 2.0-second horizon;
- the highest combined-risk eligible obstacle has `combined_risk >= 0.20`;
- combined-mask risk centroid satisfies `abs(u_risk - cx) <= 12 px`;
- trajectory disagreement is `< 0.03 m`.

Purpose: compare Center and Risk in a typical forward, near-principal-point conflict.

### S2 Off-trajectory visual distractor

- the largest eligible polygon and highest combined-risk obstacle have different IDs;
- largest polygon area is at least `2.0x` the highest-risk obstacle polygon area;
- the largest-area obstacle does not enter either planned or state corridor;
- the highest-risk obstacle enters the planned corridor and has `combined_risk >= 0.20`.

Purpose: create a verified disagreement between object visibility and collision relevance.

### S3 Left-turn trajectory

- `planned_yaw_change >= +0.30 rad`;
- highest-risk eligible obstacle has `combined_risk >= 0.20`;
- combined-mask risk centroid satisfies `u_risk <= cx - 12 px`.

### S4 Right-turn trajectory

- `planned_yaw_change <= -0.30 rad`;
- highest-risk eligible obstacle has `combined_risk >= 0.20`;
- combined-mask risk centroid satisfies `u_risk >= cx + 12 px`.

S3 and S4 use mirrored parameter ranges and matched seed suffixes. Their counts, obstacle-size distributions, and absolute wheel-speed distributions must be identical by construction.

### S5 Planned/State disagreement

- trajectory disagreement is in `[0.03, 0.12] m`;
- the obstacle with maximum planned risk differs from the obstacle with maximum state risk;
- both maxima are eligible and each corresponding channel risk is at least `0.10`;
- both obstacle regions contribute nonzero pixels to the combined mask.

Purpose: test the existing max-combined mask only; no new uncertainty method is introduced.

### S6 Large low-risk versus small high-risk

- a large eligible obstacle has combined risk in `(0, 0.10)`;
- a different smaller eligible obstacle has combined risk `>= 0.20`;
- large polygon area is at least `3.0x` the small polygon area;
- at least one tile receives pixels from both polygons, exercising maximum-risk tile aggregation.

### S7 Partial visibility

- at least one eligible collision-relevant obstacle has `partially_visible` status;
- that obstacle has positive combined risk, nonzero clipped area, and nonzero mask-written pixels;
- its unclipped projected polygon extends beyond at least one image boundary.

### S8 Low-risk control

- at least one eligible obstacle is visible;
- combined risk sum is positive;
- every eligible obstacle has `combined_risk < 0.10` and `combined_max < 0.10`;
- no obstacle reaches the frozen `0.20` high-risk threshold.

S8 intentionally has an empty high-risk region. Its high-risk-region PSNR is recorded as `undefined_empty_region`; the episode remains valid because the primary continuous risk-weighted metric is defined. Undefined secondary metrics are never replaced with zero or infinity.

For S8, the `<0.10` bound and positive risk-sum requirement apply to all four snapshots. For every other family, the common positive-risk and eligible-obstacle requirements apply to all four snapshots while the family-specific role conditions apply at snapshot 2 unless stated otherwise.

## 7. Snapshot Selection

Each scenario configuration freezes a motion window `[t_start, t_end]` before an episode runs. Reference progress is `p=(t-t_start)/(t_end-t_start)`, clipped to `[0,1]`. Each snapshot is the first Webots control step at or after its fixed progress target:

| Snapshot | Phase | Progress |
| --- | --- | ---: |
| 0 | early approach | `0.20` |
| 1 | mid approach | `0.45` |
| 2 | designed closest pre-contact / highest planned-risk phase | `0.70` |
| 3 | post-turn or risk-transition phase | `0.90` |

The same four source snapshots are used by every method and budget. Snapshot times cannot depend on RGB quality, PSNR, SSIM, allocation, method output, collision outcome, or human visual selection. M5E-B scenario configuration must place the intended maneuver/conflict phases at these progress points; the validator checks the scenario role after capture but never searches neighboring frames.

For S1, S2, S5, S6, and S7, snapshot 2 must have planned maximum risk no lower than snapshots 0 and 1. For S3/S4, snapshot 1 is at or immediately after turn onset and snapshot 3 is after the main turn command transition. S8 is exempt from a high-risk peak but must remain below its low-risk bound at all snapshots.

If any prescribed snapshot is missing or a scenario condition fails, the entire episode is invalid. Its remaining frames stay in the manifest as excluded evidence, and the next pre-registered replacement seed is used. Frames are never manually added, moved, or selected after the run.

## 8. Required Snapshot Record

Each snapshot record must include at least:

- dataset split, scenario family, secondary labels, seed, generator version, episode ID, snapshot index, progress target, simulation time, frame path, and frame SHA-256;
- robot `x`, `y`, `z`, yaw, linear velocity, and angular velocity;
- complete planned and state trajectory point arrays and their trajectory disagreement;
- eligible obstacle count and each obstacle's ID, AABB, planned/state/combined risk, visibility, projected and clipped polygons, and mask eligibility;
- combined risk sum and maximum, risk-support pixel count, high-risk pixel count, object-union pixel count, and combined-mask hash;
- scenario validation fields, validity status, warning codes, and missing/invalid reason;
- `actual_future_trajectory_used=false`.

Future actual position, velocity, yaw, trajectory, image, or collision outcome may not enter snapshot selection, risk, scoring, allocation, matching, or quality computation.

## 9. Calibration-Only Common Budget Freeze

The M5B/M5D byte targets `31348`, `32105`, `32729`, and `33959` are development-only and are not M5E defaults.

For every calibration frame `f` and method `m`, M5E-C enumerates the frozen legal candidate space and records minimum and maximum complete container bytes `L_fm` and `U_fm`. The common feasible interval is:

```text
L_common = max_f,m L_fm
U_common = min_f,m U_fm
```

Calibration fails if `L_common >= U_common`. Otherwise let `span = U_common - L_common`. The four target bytes are frozen deterministically as:

```text
severe = L_common + floor(0.05 * span)
low    = L_common + floor(0.25 * span)
medium = L_common + floor(0.50 * span)
high   = L_common + floor(0.80 * span)
```

The four targets must be strictly increasing and feasible for every calibration frame and method. Every method uses identical target bytes. Actual bytes include all container overhead, may not exceed target, and use the existing maximum-legal-byte matcher and tie-break. Utilization is `actual_total_bytes / target_bytes`; `[0.98,1.00]` is the accepted matched range. Legal results below 0.98 remain in the data with `low_utilization` and are reported rather than deleted.

Budget adequacy checks use only calibration data and cannot compare methods for superiority:

- Uniform median full-frame PSNR at severe must be at least `3.0 dB` below high;
- Uniform median full-frame PSNR at low must be at least `1.5 dB` below high;
- high must remain below `U_common`, and no Uniform high result may select quality 95;
- at least 90% of frame-method pairs must select different quality maps at each adjacent budget pair;
- target feasibility, utilization distributions, and allocation-collapse counts are reported for every method.

If these pre-registered checks fail, M5E-C stops before formal generation. It may not hand-tune a budget or inspect formal outcomes. Any protocol amendment requires explicit approval, a documented reason, and a fresh calibration run; development evidence cannot be substituted.

The budget report includes target bytes, bits/frame, and illustrative bitrate at a frozen conversion rate of `10 frames/s`: `bitrate_bps = target_bytes * 8 * 10`. This conversion is not a network model or a claim about runtime frame rate.

Formal M5E uses the M5E-C budgets unchanged and never recalibrates them.

## 10. Metrics

Primary metric:

- continuous combined-risk-weighted PSNR, with the exact M5D formula and continuous float mask.

Primary comparisons:

- Risk ROI minus Uniform;
- Risk ROI minus Center ROI;
- Risk ROI minus Object ROI.

Primary budget focus:

- severe;
- low.

Secondary metrics:

- high-risk-region PSNR with `combined >= 0.20`;
- risk-support PSNR with `combined > 0`;
- eligible-object-region PSNR;
- full-frame PSNR;
- full-frame SSIM with the frozen M5D parameters;
- background PSNR;
- risk-weighted mean assigned quality;
- actual bytes, unused bytes, budget utilization, tile payload bytes, and container overhead.

M5E does not evaluate object detection, semantic segmentation, human visual quality, LPIPS, navigation success, collision rate, or safety probability. Risk-weighted PSNR remains an image-distortion proxy over a heuristic risk mask.

## 11. Statistical Unit and Analysis

The episode is the primary resampling unit because its four snapshots are correlated. For method `m`, baseline `b`, budget `q`, and episode `e`:

```text
frame_delta = RW_PSNR(m) - RW_PSNR(b) on the same source frame and budget
episode_delta = arithmetic mean of the four frame_delta values in episode e
```

The primary analysis uses `m=Risk ROI`, each of the three baselines, and severe/low budgets. It is paired because methods share the same source frame and target budget.

Frozen bootstrap procedure:

1. compute one episode-level paired difference per valid episode;
2. preserve the eight primary scenario strata;
3. for each of 10,000 replicates, independently resample eight episodes with replacement inside every scenario;
4. compute each scenario mean, then the equal-weight mean of the eight scenario means;
5. use random seed `20260718`;
6. report the observed equal-scenario mean difference and percentile 95% interval at the 2.5th and 97.5th percentiles;
7. also report episode-level median, IQR (`Q1`, `Q3`), strict win rate `P(delta>0)`, tie rate, and sample count;
8. repeat descriptively per scenario with episode as the resampling unit.

Frames are never treated as independent bootstrap observations. Missing/invalid episodes are reported and replaced before the frozen formal matrix is analyzed; no available-case frame-level inference is allowed.

P-values are optional and never the sole evidence. If used, they must come from a stated paired episode-level test, report all six primary comparisons, and apply Holm correction across `3 baselines x 2 primary budgets`.

## 12. Engineering Acceptance and Scientific Interpretation

Engineering acceptance is independent of method performance. M5E engineering work passes when the dataset and provenance are complete, all eight scene validators pass, byte fairness and metrics independently recompute, statistics use episodes correctly, outputs are deterministic, and no future-actual leakage occurs. Risk ROI may lose every comparison without causing engineering failure.

Basic initial support for the Risk ROI hypothesis requires all of the following:

1. at severe or low budget, the overall episode-level paired mean Risk-minus-Object RW-PSNR is positive;
2. its 95% bootstrap interval is not wholly below zero;
3. in a majority of S2, S3, S4, and S6, the relevant Risk-minus-Object or Risk-minus-Center episode win rate exceeds 50%;
4. the difference is not explained by Risk receiving higher target or actual bytes;
5. validators pass without a large failure rate and no single scenario dominates the equal-weight overall result.

For criterion 3, a majority means at least three of the four named primary scenarios. For criterion 4, target bytes must be identical and the absolute overall mean Risk-minus-baseline actual-byte difference must be at most `0.5%` of target bytes; otherwise that comparison cannot support a method claim. A large failure rate means invalid attempts exceed `20%` overall or `25%` within any primary scenario. Single-scenario domination means either removing one scenario reverses the sign of an otherwise positive overall mean, or one scenario contributes more than `50%` of the sum of absolute scenario mean differences. These checks are reported for every primary comparison.

Stronger support requires the severe and low intervals to be wholly above zero for both Risk-minus-Center and Risk-minus-Object. H1 is fully supported only if the pre-registered comparisons against all three baselines are positive at severe and low with intervals wholly above zero. H2 and H3 are reported using their frozen scenario contrasts whether or not they favor the hypothesis.

If evidence does not support the hypotheses, formal data and failed scenes remain unchanged. The next activity is failure analysis and an explicit Innovation Design Freeze, not post-hoc parameter tuning or scene removal.

## 13. Failure, Warning, and Replacement Policy

Every attempted episode appears in the manifest with one terminal status:

- `valid`;
- `invalid_webots_failure`;
- `invalid_missing_snapshot`;
- `invalid_camera_output`;
- `invalid_no_eligible_obstacle`;
- `invalid_zero_risk_sum`;
- `invalid_budget_infeasible`;
- `invalid_container_decode`;
- `invalid_primary_metric`;
- `invalid_nondeterministic_repeat`;
- `invalid_scenario_validation`.

Non-terminal warnings include `low_utilization` and `undefined_empty_high_risk_region`. A legal low-utilization match is retained. An empty high-risk region is valid only when allowed by the scenario, especially S8; the secondary metric is undefined and is not imputed.

For an invalid episode:

1. preserve its manifest row, logs, generated paths, reason, failing check, and seed;
2. exclude all four snapshots from formal metric statistics;
3. consume the next ascending replacement seed for the same split and primary scenario;
4. never reuse a seed or replace only an unfavorable frame;
5. stop the split as incomplete if its reserved replacement pool is exhausted.

Raw attempts, valid episodes, invalid episodes, warning counts, replacements, and final effective episodes are reported per split and scenario. No failure may be silently deleted. A method-specific budget or decode failure invalidates the whole episode so paired fairness is preserved.

## 14. Planned Outputs

Later M5E implementation may create only ignored generated evidence under:

```text
data/frames/m5e/<split>/<scenario>/<episode>/...
data/logs/m5/m5e_dataset_manifest.csv
data/logs/m5/m5e_quality_results.csv
data/metadata/m5/m5e_dataset.json
data/metadata/m5/m5e_evaluation.json
data/decoded/m5/m5e/<split>/<scenario>/<episode>/...
results/m5_compression/m5e/...
```

The manifest contains split, primary/secondary scenario labels, seed, generator version, episode and snapshot identity, progress target, simulation time, frame path/hash, robot state, trajectory and risk statistics, obstacle visibility/projection records, scenario validation, warning codes, validity status, replacement linkage, and no-future-actual provenance.

Quality results contain frame identity, scenario, episode, snapshot, method, budget, target/actual/unused bytes, allocation and tile payloads, all metrics and region counts, dependency/container identity, and `actual_future_trajectory_used=false`.

Generated data and results remain ignored by Git. M5E-A creates none of these outputs.

## 15. Independent Validation Requirements

The future M5E validator must independently reload source frames, metadata, trajectories, obstacles, polygons, and float masks; recompute scenario conditions, masks, scores, allocations, complete container bytes, decodes, metrics, and episode-level statistics; verify split/seed disjointness and all hashes; and reject any future-actual field usage. It may not merely trust runner summary fields.

Repeated execution in the frozen software environment must reproduce scene parameters from seeds, snapshot identities, source hashes, allocation choices, container bytes, decoded pixels, metrics, manifest ordering, and statistical outputs. Webots rendering determinism is checked by repeated calibration episodes before formal data generation.

## 16. Milestone Decomposition

- **M5E-A:** freeze this multi-scene protocol.
- **M5E-B:** implement the parameterized static-AABB scenario and dataset generator plus scenario validators; do not encode formal results.
- **M5E-C:** generate calibration data, run the calibration-only pilot, validate the common feasible interval, and freeze common budgets.
- **M5E-D:** generate the full formal dataset and run matched-budget encoding and metrics.
- **M5E-E:** compute episode-level statistics and diagnostic figures.
- **M5E-F:** independently validate all evidence and formally accept or reject the M5E engineering milestone and scientific hypotheses.

The only next priority after M5E-A is M5E-B.
