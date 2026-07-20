# Milestone 5E-B Dataset Generator Validation Report

Last updated: 2026-07-19 (Asia/Shanghai)

## Scope

Milestone 5E-B implements one parameterized Webots world/controller for the eight frozen static-AABB scenario families. It generates deterministic RGB frames, floating-point planned/state/combined masks, snapshot metadata, episode summaries, and manifests. It does not select communication budgets, encode images, evaluate PSNR/SSIM, generate calibration/formal datasets, or perform statistics.

## Generator and evidence

- World: `simulator/worlds/m5e_dataset_generator.wbt`
- Controller: `simulator/controllers/m5e_dataset_generator/m5e_dataset_generator.py`
- Scenario/config modules: `simulator/m5e_scenarios.py`, `simulator/m5e_config.py`
- Snapshot targets: reference-motion progress `0.20`, `0.45`, `0.70`, `0.90`
- Snapshot tolerance: `0.006`; observed maximum error: `0.0040000000000000036`
- Camera: `160x120`, horizontal FOV `0.84 rad`, near plane `0.0055 m`
- Smoke seeds: S1-S8 use `9001` through `9008`; all primary episodes passed without replacement
- Accepted smoke evidence: 8 episodes, 32 snapshots, 32 unique frame identities, 32 frame hashes, and 32 floating-point mask hashes
- Dataset manifest: `data/logs/m5/m5e_dataset_manifest.csv`
- Episode manifest: `data/metadata/m5e/m5e_episode_manifest.json`
- Diagnostics: `results/m5_compression/m5e_smoke/m5e_scenario_diagnostics.png` and `m5e_snapshot_progress.png`

Generated data and results are ignored by Git. At M5E-B closeout, no calibration or formal manifest had been created. M5E-C later generated the separate calibration split and froze common budgets. M5E-D later generated the formal split and metric table. Calibration seed indices 0/1 and formal boundary indices 0/7 were checked only at configuration level for all scenarios during M5E-B.

## S5 diagnosis and correction

The initial S5 failure was not a risk-model defect. The original command timing and obstacle geometry did not create enough planned/state trajectory separation by the frozen validation snapshot, and candidate obstacle visibility/depth allowed one obstacle to dominate both channels. The first validator also selected metadata index 1 rather than the frozen third snapshot (`p=0.70`); this indexing error was corrected before scenario acceptance.

A bounded deterministic offline geometry sweep used only snapshot-time planned/state trajectories and Camera geometry. It did not read compression allocations or image-quality metrics. The frozen selection rule required both branch obstacles to be visible and mask-contributing, opposite planned/state argmax identities, positive margins, different masks, and then maximized the smaller margin with deterministic tie-breaks.

The final static S5 configuration uses:

- `0.0-4.25 s`: left `1.0 rad/s`, right `2.0 rad/s`
- `4.25-6.0 s`: left `2.0 rad/s`, right `1.0 rad/s`
- planned branch nominal center `(0.120, 0.180) m`, size `(0.015, 0.015, 0.050) m`
- state branch nominal center `(0.060, 0.185) m`, size `(0.020, 0.020, 0.050) m`
- deterministic per-seed position jitter bounded by `+/-0.002 m`

At the accepted `p=0.704` snapshot, trajectory disagreement is `0.03721414398972764 m`. Planned risk ranks `M5E_S5_PLANNED_BRANCH` first with margin `0.029617547559283128`; state risk ranks `M5E_S5_STATE_BRANCH` first with margin `0.03668397334636701`. Both are partially visible, eligible, and contribute nonzero mask pixels. No risk parameter, risk formula, trajectory model, Camera parameter, snapshot target, or validator threshold was changed.

## Scenario checks

- S1: collision-relevant straight approach is present at the frozen validation snapshot; a fixed late departure arc avoids physical collision during the complete episode.
- S2: a small high-risk obstacle and large off-trajectory visual distractor remain distinct.
- S3/S4: mirrored forward left/right arc scenarios pass their risk-weighted lateral checks.
- S5: planned/state branch argmax objects differ with positive margins, nonempty projections, mask contributions, and different channel masks.
- S6 at `p=0.704`: small-high candidate area `938 px`, combined risk `0.3593353909604333`; large-low candidate area `3652 px`, combined risk `0.0011643852196083705`; area ratio `3.893390191897655`. Both contribute mask pixels and share at least one frozen tile.
- S7 at `p=0.704`: the partial obstacle is `partially_visible`, combined risk `0.03360701169399`, candidate/written area `1154 px`, truncation ratio `0.5862820200055942`, and its unclipped horizontal bounds cross the left image boundary (`u=-24.501109` to `18.104531`).
- S8: all four snapshots contain one eligible visible obstacle and positive mask mass. Combined maxima are `1.3235533551247435e-05`, `4.4110649896514015e-05`, `0.00014998117730962427`, and `0.0004900511667976293`; the high-risk region is correctly treated as empty rather than as a failed episode.

The validator independently recomputes trajectories, obstacle risks, projections, masks, pixelwise combined max, scenario roles, hashes, paths, progress, Camera constants, and `actual_future_trajectory_used=false`. Controller-written status alone is not accepted as proof.

## Reproducibility and validation

The full smoke run was repeated under `data/m5e_repeat`. Comparison of all 32 frame bytes/hashes, floating-point masks, configs, and normalized metadata was exact. A final independent smoke run under `data/m5e_final_acceptance_smoke` passed all 8 episodes / 32 snapshots with no replacements. Webots subprocess output did not propagate into the redirected shell log files on this machine; GUI Console status is therefore recorded only from explicit manual observations.

Automated acceptance passed for the 32-frame smoke dataset and deterministic repeat. The final validation set included `pip check`, compileall, 257 unit tests, the independent M5E validator, and M3, M4C, M4D, M5B, M5C, and M5D validators. Results are recorded in `docs/progress.md`.

## S3 physics-warning diagnosis and correction

The original S3 `TURN_RISK` Box was physically too close to the executed e-puck left arc. With the canonical world restored and only one Webots instance running, per-step diagnostics first found body-cylinder/Box contact at step `140`, `4.480 s`, during `left_arc`. This was after the third frozen snapshot at `4.224 s`, not during initialization, turn onset, snapshot capture, or GUI pause. The original run had 49 contact/penetration rows, minimum estimated surface clearance `-0.000662464 m`, and a later speed drop to approximately `0.0112 m/s`. This localizes the user-observed physics-warning interval to the post-snapshot left-arc approach/contact phase.

The nominal S3 target center was moved from `(0.155, 0.080) m` to `(0.210, 0.110) m`. The smoke-seed instance is `(0.211093647280262, 0.11133095177193035) m` after the pre-existing deterministic jitter. Its size remains `(0.030, 0.030, 0.060) m`; the S3 wheel schedule, left-turn semantics, start pose, snapshot targets, risk parameters, trajectory models, Camera, projection, masks, and frozen validator thresholds are unchanged. S1, S2, and S4-S8 are unchanged.

Two independent fixed S3 batch runs and one isolated GUI run each produced four snapshots, 188 diagnostic rows, zero obstacle-contact rows, and minimum estimated surface clearance `0.003971330 m`. The repeated batch outputs matched exactly for RGB frame bytes, float masks, ScenarioConfig/manifest values, and normalized metadata. S3 retained a left-turn yaw change of `0.670769 rad`, combined risk `0.256176`, the frozen lateral-centroid condition, `actual_future_trajectory_used=false`, and pixelwise `combined=max(planned,state)`.

The optional project-relative `M5E_PHYSICS_DIAGNOSTICS_PATH` output records each Webots step, simulation time, command segment, wheel command, robot pose/roll/pitch/yaw/height, measured velocity, snapshot crossing, contact points, obstacle-node IDs, and robot/obstacle geometry. It is disabled by default and does not enter frame, mask, metadata, risk, compression, or quality calculations. The controller also refuses to import parameterized obstacles into a nonempty runtime group, preventing duplicate colliders if a generated GUI world is accidentally reused.

The isolated GUI lifecycle generated and validated four snapshots, paused, remained open for inspection, and returned normally after manual close. Automated diagnostics establish zero obstacle contact. The user then explicitly confirmed zero Webots physics warnings and no visible contact, jitter, or tilt.

## S5/S7 post-snapshot contact corrections

The prior S5 GUI run contacted `M5E_S5_PLANNED_BRANCH` at step `170` / `5.440 s`, after the final snapshot at `5.408 s`. Its minimum estimated body clearance was `-0.000590270 m`. Both S5 branch targets were moved only `0.030 m` in `+y`; their sizes and motion schedule are unchanged. The correction retains opposite planned/state maxima, positive margins, distinct masks, and all validator conditions. Corrected diagnostics found zero body overlap and minimum clearance `0.010794580 m`, and the user manually confirmed no collision while the planned/state disagreement remained visible.

The prior S7 GUI run contacted `M5E_S7_RISK` at step `185` / `5.920 s`, also after the final snapshot. Its minimum estimated body clearance was `-0.000386838 m`. S7 geometry, including the partial target, is unchanged. Its command schedule now switches to stop at `5.5 s`, after the final `5.408 s` snapshot, preventing only the post-capture collision. Corrected diagnostics found zero body overlap and minimum clearance `0.010996237 m`; the partial target remains `partially_visible`, has `1154` written pixels, positive risk, and crosses the expected image boundary.

During the first corrected S7 GUI run, two Console errors reported `wb_supervisor_node_get_id() called for an internal PROTO node`. The controller had attempted to obtain IDs for e-puck wheel DEFs inside the official PROTO solely to annotate optional diagnostic contact records. This data was not used for metadata, obstacle identity, Camera location, physics configuration, risk, masks, or validation. The controller now records only the top-level e-puck body ID; static obstacles retain top-level DEF IDs and immutable `ScenarioConfig.obstacle_id` strings. A unit test forbids `getFromProtoDef()` in this controller. The final S7 GUI run had no internal-PROTO error, no physics warning, no collision, and normal partial visibility according to user manual review.

## GUI acceptance evidence

The following are explicit user GUI observations, not automatic claims:

1. S2: normal GUI lifecycle, four snapshots, and no robot collision.
2. S3: prior real contact corrected; no physics warning, collision, jitter, or visible tilt.
3. S5: corrected GUI run completed with four snapshots, no collision, and preserved planned/state disagreement.
4. S7: four snapshots, independent validator pass, zero body overlap, minimum clearance `10.996 mm`, no internal-PROTO error or physics warning, no collision, and normal partial visibility.

The complete automatic S1-S8 smoke validator remains the evidence for all eight frozen scenario conditions. GUI observations are physical and Console acceptance evidence for the reviewed scenarios.

## Interpretation boundary

Risk values remain heuristic proxies, not collision probabilities. M5E-B establishes deterministic multi-scene input generation only. It provides no compression, communication, perception, or navigation benefit claim.

Historical M5E-B closeout next priority was Milestone 5E-C calibration pilot and common-budget freeze. Current status after M5E-F: calibration data, common budgets, formal data, the formal metric table, episode statistics, and independent acceptance are complete. M5E-E does not establish general ROI superiority.
