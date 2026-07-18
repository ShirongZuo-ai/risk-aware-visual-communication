# Roadmap

## Milestone 0 — Repository and environment baseline

- [x] Create repository structure and durable project documents.
- [x] Verify native Windows version, Python 3.10/3.11, Git, winget, NVIDIA GPU/driver, and Webots installation on the user's machine.
- [x] Initialize Git on the user's intended Windows project folder if this workspace is not that folder.

Acceptance: all checks are recorded truthfully in `docs/progress.md`; missing software is identified before installation.

## Milestone 1 — Synchronized frame and robot-state capture

- [ ] Create one repeatable Webots world with a differential-drive robot and forward RGB camera.
- [ ] Implement minimal straight, left-turn, and right-turn motion.
- [ ] Save at least 100 camera frames.
- [ ] Save aligned CSV rows containing timestamp, pose, heading, linear velocity, angular velocity, and image path.
- [ ] Verify image paths exist and timestamps align with the CSV.
- [ ] Document exact launch and validation commands in `README.md`.

Acceptance: Webots runs; the world is repeatable; all three motions work; at least 100 aligned frame/state samples are validated; README and progress record the real results.

Do not implement risk maps, ROI compression, object detection, closed-loop navigation, ROS 2, or AI models in this milestone.

## Milestone 2 — Geometry and trajectory ground truth

- [x] Define planned command, State-only prediction, Command-conditioned prediction, and actual future trajectory.
- [x] Implement State-only constant-twist prediction.
- [x] Implement Command-conditioned differential-drive prediction from explicit future command segments.
- [x] Generate a dedicated Webots validation episode with stable and transition windows.
- [x] Evaluate ADE, FDE, yaw MAE, valid windows, and compute time for 0.5, 1.0, and 2.0 second horizons.
- [x] Estimate first empirical residual uncertainty corridors.

Acceptance: trajectory definitions are documented; predictors are unit-tested; a dedicated validation episode is actually run; stable and transition windows are reported separately; figures and progress record real results.

## Milestone 3 - Interpretable collision-risk map

### Milestone 3A - Risk formulation and interface freeze

- [x] Freeze world-coordinate trajectory-to-obstacle risk terminology.
- [x] Define Trajectory Occupancy Corridor semantics.
- [x] Define static AABB obstacle footprint data structures.
- [x] Define clearance, Time-to-Conflict, risk score, and dual-trajectory combination rules.
- [x] Freeze planned module boundaries and acceptance criteria.

Acceptance: `docs/risk_formulation_design.md` documents the risk model, data structures, module boundaries, validation scenario roles, and test plan. No risk algorithm code, Webots world, controller, CSV, figure, camera projection, ROI compression, or machine-learning component is created.

### Milestone 3B - Geometry and risk core implementation

- [x] Implement frozen ordinary-Python risk data models.
- [x] Implement boundary-based AABB geometry and trajectory corridor intervals.
- [x] Implement trajectory-obstacle conflict analysis.
- [x] Implement interpretable spatial, temporal, and combined planned/state risk scores.
- [x] Add unit tests for geometry, data validation, risk formulation, and dual-trajectory analysis.

Acceptance: `risk_map` contains ordinary-Python modules only, core modules do not depend on Webots or camera APIs, geometry uses obstacle boundaries, risk formulas match `docs/risk_formulation_design.md`, and the full test suite passes.

### Milestone 3C - Webots world-risk validation

- [x] Create a Webots validation world with six fixed static AABB Box obstacles.
- [x] Convert simulator ground-truth obstacles into the frozen `ObstacleFootprint` interface.
- [x] Generate planned and State-only trajectories at a command-switch analysis snapshot.
- [x] Write a 6-row world-risk CSV.
- [x] Validate CSV structure, geometry consistency, role relationships, data leakage constraints, and ignored output paths.

Acceptance: Webots runs the M3C world, the controller writes one risk row per obstacle, the validator exits 0, `risk_map` remains Webots-decoupled, and no camera projection, image risk map, ROI compression, dynamic obstacles, or navigation code is added.

### Milestone 3D - Visualization and evaluation

- [x] Rebuild planned and State-only trajectories from the accepted M3C analysis snapshot.
- [x] Generate world-coordinate trajectory, corridor, obstacle, risk, decomposition, and disagreement diagnostics.
- [x] Recalculate risk formulas from CSV values.
- [x] Generate summary CSV/JSON and parameter sensitivity diagnostics.
- [x] Create Milestone 3 validation report.
- [x] Validate generated artifacts and report.
- [x] Complete GUI human acceptance.

Acceptance: M3D diagnostics are generated from `risk_validation_episode_0002.csv`, role acceptance and formulas pass automatically, parameter sensitivity over the tested 9 combinations is reported, the validation report is complete, generated data/results remain ignored, and GUI human acceptance has passed. `risk_validation_episode_0002` remains the official evidence data; `risk_validation_episode_0005` is GUI reproduction evidence only.

## Milestone 4 — Image-space risk projection

### Milestone 4A - Projection design and interface freeze

- [x] Freeze world-to-camera-to-image coordinate terminology.
- [x] Freeze Camera intrinsics and extrinsics interface targets.
- [x] Freeze 3D Box projection, visibility, clipping, and image-risk mask semantics.
- [x] Define M4 validation scene roles, automatic verification plan, error metrics, module boundaries, and dependency policy.

Acceptance: `docs/image_risk_projection_design.md` documents the projection model, interfaces, validation roles, and boundaries. No camera projection code, M4 Webots world/controller, camera frame, mask, figure, compression, networking, or machine-learning component is created.

### Milestone 4B - Pure-Python projection core

- [x] Implement frozen camera models and validation.
- [x] Implement world/device/optical/image transforms.
- [x] Implement pinhole projection, near-plane clipping, image-boundary clipping, and 3D Box projected polygons.
- [x] Unit-test projection roles, helper geometry, visibility classification, and invariants.

Acceptance: core projection logic is unit-tested and remains decoupled from Webots, OpenCV, ROS, and machine learning unless a later dependency decision changes this. Image-risk mask generation remains out of scope until Milestone 4D.

### Milestone 4C - Webots calibration and projection validation

- [x] Create a separate M4 validation world without modifying accepted M3 worlds.
- [x] Read camera intrinsics/extrinsics and 3D Box geometry through a Webots adapter.
- [x] Save RGB frame and snapshot metadata for repeatable projection validation.
- [x] Validate overlay direction, Box coverage, clipping, and numeric error metrics.

Acceptance: Webots validation runs on a dedicated M4 scene; automatic metrics are recorded; GUI review is recorded separately and does not replace numeric validation. Milestone 4C has passed both automatic validation and GUI human acceptance; `projection_validation_episode_0003` is the automatic evidence and `projection_validation_episode_0004` is GUI reproduction evidence.

### Milestone 4D - Image-space risk masks and diagnostics

- [x] Implement the Webots-decoupled pure-Python image-risk mask core.
- [x] Unit-test mask value range, channel separation, overlap max-union, invisible-obstacle handling, and rasterization invariants.
- [x] Generate planned, state, and combined image-risk masks from one same-snapshot Webots validation episode.
- [x] Generate diagnostic overlays and summaries.
- [x] Complete GUI human acceptance and Milestone 4D closeout.

Acceptance: image-space risk masks are generated from validated projections and documented. Milestone 4 is formally accepted: it proves the world-risk to image-risk mapping for the validation snapshot only. Compression policy, bitrate allocation, JPEG/H.264 integration, communication benefit, and task/navigation evaluation remain out of scope until Milestone 5.

## Milestone 5 — Offline task evaluation

Planned: evaluate communication, image-quality, and safety-critical perception metrics across scenarios and budgets. The first Milestone 5 substeps are split below.

### Milestone 5A - Compression and fair-bitrate protocol freeze

- [x] Freeze the first tiled-JPEG spatial allocation prototype terminology.
- [x] Freeze the `160x120` frame, `20x20` tile grid, 8 columns, 6 rows, and 48 row-major tiles.
- [x] Define deterministic container byte accounting and actual transmitted byte matching.
- [x] Define Uniform, Center ROI, Object ROI, and Risk ROI baselines.
- [x] Define shared score-to-quality allocation and under-budget selection rules.
- [x] Define the budget-selection pilot process instead of hard-coding budget values.
- [x] Define communication, whole-image, risk-weighted, and regional quality metrics.
- [x] Define fairness and leakage checks.

Acceptance: `docs/m5_compression_and_bitrate_protocol.md` freezes the protocol and scope. No compression algorithm, JPEG container, compressed image, experiment CSV, risk algorithm change, Camera projection change, image-risk-mask change, network, perception, navigation, or machine-learning code is created.

### Milestone 5B - Tiled-JPEG codec and budget pilot

- [x] Add explicit Pillow dependency for the JPEG backend.
- [x] Implement the deterministic tiled-JPEG encoder/decoder.
- [x] Implement the strict binary tiled-frame container and byte accounting.
- [x] Implement Uniform exhaustive quality-to-budget matching.
- [x] Run the Uniform JPEG quality sweep on the accepted M4D development frame.
- [x] Generate development budgets from actual Uniform container bytes.
- [x] Validate the pilot outputs and rerun determinism checks.

Acceptance: all methods can later share one encode/container/decode backend, target budgets are selected from measured Uniform pilot data, and generated compression data remains ignored by Git. Milestone 5B is complete; Center ROI, Object ROI, Risk ROI, method comparison, perception, networking, navigation, and machine learning remain out of scope until later milestones.

### Milestone 5C - Baseline allocation implementation

- [x] Implement immutable row-major tile score maps with deterministic ranking.
- [x] Implement the frozen Center Gaussian, visible-polygon Object, and combined-float-mask Risk scoring rules.
- [x] Implement one shared cached tiled-JPEG allocation search and fair actual-byte matcher for all non-Uniform methods.
- [x] Preserve the M5B Uniform matcher and its four official development-budget results.
- [x] Generate, independently recompute, and validate the 16-row single-frame allocation matrix and diagnostics.

Acceptance: all baselines use identical byte matching, tile grid, JPEG settings, and container accounting; Risk ROI receives no extra budget or future actual information. M5C is complete as an allocation/fairness implementation milestone only; it does not compare image quality, perception, or navigation outcomes.

### Milestone 5D - First single-frame compression validation

- [x] Reconstruct the existing 16 M5C selected tiled-JPEG containers without rerunning allocation or matching.
- [x] Measure full-image MSE, PSNR, and frozen-parameter SSIM on uint8 RGB reconstructions.
- [x] Measure continuous-mask risk-weighted and eligible-object, high-risk, and background regional quality.
- [x] Validate exact actual-byte matching, fixed M5C quality maps, decoding, no-future-actual provenance, and deterministic reruns.
- [x] Generate metric, quality-allocation, and per-budget reconstruction diagnostics.

Acceptance: communication metrics, whole-image quality, risk-weighted quality, regional quality, and fairness checks are reported for the accepted single-frame M4D evidence. M5D is complete as a single-frame descriptive evaluation only; M5E must establish whether any observation persists across multiple snapshots and layouts.

### Milestone 5E-A - Multi-scene protocol freeze

- [x] Separate development, calibration, and formal evidence.
- [x] Freeze eight static-AABB scenario families, deterministic four-snapshot rules, seed namespaces, validation thresholds, and replacement policy.
- [x] Freeze the calibration-only common-budget rule, metrics, episode-level paired statistics, engineering acceptance, and scientific support criteria.

Acceptance: `docs/m5e_multiscene_offline_evaluation_protocol.md` is internally consistent and no M5E world, controller, code, frame, CSV, JSON, decoded image, or figure is created.

### Milestone 5E-B - Parameterized scenario and dataset generator

Planned: implement deterministic static-AABB scenario generation, split-safe seed handling, four snapshot triggers, manifests, and machine validators. Do not run the common-budget pilot or formal encoding.

Acceptance: every scenario family can be generated and independently validated from configuration and seed, with complete failure records and no future-actual leakage.

### Milestone 5E-C - Calibration pilot and common budget freeze

Planned: generate the 64-frame calibration split, measure the shared feasible container-byte interval, apply the frozen budget formula and adequacy checks, and freeze severe/low/medium/high targets.

Acceptance: all four targets are common and feasible, method-identical, calibration-only, and documented before formal generation.

### Milestone 5E-D - Formal encoding and metric evaluation

Planned: generate 256 formal frames and 4096 matched-budget reconstructions, then compute frozen M5D metrics without changing protocol parameters.

Acceptance: the formal matrix is complete, paired, byte-fair, deterministic, and independently recomputable.

### Milestone 5E-E - Episode statistics and diagnostics

Planned: aggregate four snapshots per episode, run the fixed-seed stratified paired bootstrap, and generate overall/per-scenario diagnostics.

Acceptance: statistical outputs use episodes as the resampling unit and report all pre-registered comparisons, failures, utilization, uncertainty, and limitations.

### Milestone 5E-F - Formal validation and acceptance

Planned: independently validate all manifests, inputs, allocations, containers, metrics, statistics, split isolation, and no-future-actual provenance.

Acceptance: engineering acceptance is stated independently of whether the hypotheses receive scientific support; unsupported outcomes are retained and reported.

### Milestone 5F - Compression validation report and next-step decision

Planned: write the Milestone 5 report and decide whether remote perception or closed-loop navigation evaluation is justified.

Acceptance: the report states what compression and image-risk-region claims are supported, what remains unproven, and the single next priority.

## Milestone 6 — Simple closed-loop navigation

Planned only after offline evidence supports continuing.
