# Milestone 5E-B Dataset Generator Validation Report

Last updated: 2026-07-18 (Asia/Shanghai)

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

Generated data and results are ignored by Git. No calibration or formal manifest was created. Calibration seed indices 0/1 and formal boundary indices 0/7 were checked only at configuration level for all scenarios.

## S5 diagnosis and correction

The initial S5 failure was not a risk-model defect. The original command timing and obstacle geometry did not create enough planned/state trajectory separation by the frozen validation snapshot, and candidate obstacle visibility/depth allowed one obstacle to dominate both channels. The first validator also selected metadata index 1 rather than the frozen third snapshot (`p=0.70`); this indexing error was corrected before scenario acceptance.

A bounded deterministic offline geometry sweep used only snapshot-time planned/state trajectories and Camera geometry. It did not read compression allocations or image-quality metrics. The frozen selection rule required both branch obstacles to be visible and mask-contributing, opposite planned/state argmax identities, positive margins, different masks, and then maximized the smaller margin with deterministic tie-breaks.

The selected static S5 configuration uses:

- `0.0-4.25 s`: left `1.0 rad/s`, right `2.0 rad/s`
- `4.25-6.0 s`: left `2.0 rad/s`, right `1.0 rad/s`
- planned branch nominal center `(0.120, 0.150) m`, size `(0.015, 0.015, 0.050) m`
- state branch nominal center `(0.060, 0.155) m`, size `(0.020, 0.020, 0.050) m`
- deterministic per-seed position jitter bounded by `+/-0.002 m`

At the accepted `p=0.704` snapshot, trajectory disagreement is `0.03721414398972764 m`. Planned risk ranks `M5E_S5_PLANNED_BRANCH` first with margin `0.17591532330398388`; state risk ranks `M5E_S5_STATE_BRANCH` first with margin `0.1725670221363893`. Both are partially visible, eligible, and contribute nonzero mask pixels. No risk parameter, risk formula, trajectory model, Camera parameter, snapshot target, or validator threshold was changed.

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

The full smoke run was repeated under `data/m5e_repeat`. Comparison of all 32 frame bytes/hashes, floating-point masks, configs, and normalized metadata was exact. Webots subprocess output did not propagate into the redirected shell log files on this machine; success is established by complete artifacts and independent validation, while GUI Console status remains a separate manual check.

Automated acceptance passed for the 32-frame smoke dataset and deterministic repeat. Unit, compile, dependency, leakage, and M3-M5 regression results are recorded in `docs/progress.md`.

## GUI checklist

Manual GUI acceptance is pending. Check only:

1. Each S1-S8 generated world instance contains the configured static Box DEF nodes and no unintended overlap.
2. The e-puck remains upright and does not become stuck or collide during the complete episode.
3. Representative saved frames agree with the visible Camera view and expected partial clipping.
4. Webots Console has no red controller error, Traceback, or `status: 1`.

## Interpretation boundary

Risk values remain heuristic proxies, not collision probabilities. M5E-B establishes deterministic multi-scene input generation only. It provides no compression, communication, perception, or navigation benefit claim.

Next priority: Milestone 5E-C calibration data generation and common-budget freeze.
