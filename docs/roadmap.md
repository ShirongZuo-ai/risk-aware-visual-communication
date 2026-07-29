# Roadmap

## M6 v3 formal multi-scene study

- [x] Define an additive immutable 32-episode S1-S8 manifest extension using seeds 630100-630803.
- [x] Preserve and bind the v2 manifest/lock without modification.
- [x] Freeze the unchanged TCOBR paired analysis in a versioned pre-registration.
- [x] Pass all pre-launch validation, commit, prepare/audit all packages, then execute each registered identity at most once with no retries.
- [x] Persist and validate episode-level TCOBR inference, budget/scene heterogeneity, and secondary quality/byte/ROI results.
- [x] Preserve the original eight-scene gate as `NOT EVALUATED` and freeze the preregistered eligibility-conditional result as `FAIL` with effect `0.000000`, 95% CI `[0.000000, 0.000000]`.
- [x] Publish deterministic source tables, figures, and a final report without changing formal evidence.
- [x] Reorder the publication landing page to separate project capability, lifecycle validation, absolute budget-quality behavior, and method-level scientific findings while retaining all null and adverse results.

Acceptance: only committed v3 identities may launch; a shared defect stops the batch; null and negative results remain; v2 and all historical evidence remain immutable.

M6 is complete and frozen as a negative-result baseline.

## Milestone 7 - Budget-conditioned visual value of information

- [x] Diagnose the frozen M6 zero effect using ROI/pixel/tile divergence, critical-region allocation, absolute TCOBR, reconstruction quality, and empty-scene mechanisms.
- [x] Freeze an offline design target and go/no-go gates for a deterministic byte-cost-aware allocator combining risk, trajectory coverage, visibility gain, uncertainty, and marginal reconstruction benefit.
- [ ] Implement the deterministic allocator and provenance contract on new disjoint offline data; keep both M6 methods unchanged as baselines.
- [x] Freeze the M7 v1 development authority: 16 disjoint M7C1-M7C6/M7G1-M7G2 episodes, outcome-blind geometric prechecks, isolated evaluator geometry, and an at-most-once generation contract.
- [ ] Finalize the registered M7 v1 corpus and independently reload all runtime, 512 codec-case, joint, final, and ownership evidence.
- [ ] Generate an independent counterfactual tile-quality dataset with actual complete-container byte increments from the finalized M7 v1 corpus.
- [ ] Implement an offline oracle and deterministic greedy marginal-utility-per-byte baseline before any learned allocator.
- [ ] Pre-register episode/scene splits, byte fairness, failure handling, task metrics, and support gates.

Acceptance: the new study uses identities and evidence disjoint from M5/M6, passes every offline go/no-go gate in `docs/m7_budget_conditioned_voi_design.md`, reports all null and adverse outcomes, and makes no navigation-safety claim without a separately frozen closed-loop task protocol.

## Milestone 0 — Repository and environment baseline

- [x] Create repository structure and durable project documents.
- [x] Verify native Windows version, Python 3.10/3.11, Git, winget, NVIDIA GPU/driver, and Webots installation on the user's machine.
- [x] Initialize Git on the user's intended Windows project folder if this workspace is not that folder.

Acceptance: all checks are recorded truthfully in `docs/progress.md`; missing software is identified before installation.

## Milestone 1 — Synchronized frame and robot-state capture

- [x] Create one repeatable Webots world with a differential-drive robot and forward RGB camera.
- [x] Implement minimal straight, left-turn, and right-turn motion.
- [x] Save at least 100 camera frames.
- [x] Save aligned CSV rows containing timestamp, pose, heading, linear velocity, angular velocity, and image path.
- [x] Verify image paths exist and timestamps align with the CSV.
- [x] Document exact launch and validation commands in `README.md`.

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

[x] Implement deterministic static-AABB scenario generation and split-safe seeds.
[x] Implement the parameterized Webots world/controller and four fixed-progress snapshot triggers.
[x] Save RGB frames, floating-point masks, metadata, episode summaries, and stable manifests.
[x] Independently validate all S1-S8 scenario roles, hashes, max-union, and no-future-actual provenance.
[x] Generate and exactly repeat the 32-frame smoke dataset and diagnostics.
[x] Complete targeted GUI manual acceptance for S2, S3, S5, and S7, including collision/Console checks and S7 partial visibility.

Acceptance: M5E-B is accepted for deterministic multi-scene dataset generation and risk-scenario validation. All eight smoke scenarios passed with four snapshots each, no replacements, deterministic repeat evidence, and no future-actual leakage. Targeted GUI manual evidence passed for S2/S3/S5/S7; it complements rather than replaces automatic validation. No calibration/formal data, common budget, or compression evaluation was generated.

### Milestone 5E-C - Calibration pilot and common budget freeze

- [x] Generate the independent 64-frame calibration split (S1-S8, two fixed seeds each, four fixed-progress snapshots).
- [x] Exhaustively measure actual complete-container byte ranges for Uniform, Center ROI, Object ROI, and Risk ROI.
- [x] Freeze method-identical severe/low/medium/high targets from the nonempty common interval.
- [x] Validate 1,024 deterministic under-budget allocations and repeat the complete calibration run.

Acceptance: passed. The calibration-only common interval is `[31240, 35779]` bytes and the frozen targets are `31466`, `32374`, `33509`, and `34871` bytes. No formal image-quality or method-performance result is included.

### Milestone 5E-D - Formal encoding and metric evaluation

- [x] Generate the 8-scenario, 8-formal-episode, 4-snapshot split without changing M5E-C budgets.
- [x] Produce all 4096 method-budget reconstructions using the frozen allocation, codec, and metric definitions.

Completed: generated 256 formal frames and 4096 matched-budget reconstructions, then computed frozen M5D metrics without changing protocol parameters.

Acceptance: passed. The formal matrix is complete, paired, byte-fair, deterministic, and independently recomputable. No M5E-E statistics or method-performance conclusion is included.

### Milestone 5E-E - Episode statistics and diagnostics

- [x] Aggregate the formal metrics by episode.
- [x] Run the fixed-seed scenario-stratified paired bootstrap and generate diagnostics.

Completed: aggregated four snapshots within each of 64 episodes, generated 384 primary paired effects, ran the 10,000-replicate seed-`20260718` scenario-stratified bootstrap, and produced overall/per-scenario diagnostics plus deterministic figures.

Acceptance: passed. Statistical outputs use episodes as the resampling unit and report all pre-registered comparisons, failures, utilization, uncertainty, negative findings, and limitations. H1 is not fully supported; H2/H3 retain their pre-registered direction-specific interpretation.

### Milestone 5E-F - Formal validation and acceptance

- [x] Independently validate formal manifests, metrics, statistics, determinism, split isolation, and no-future-actual provenance.
- [x] State engineering acceptance separately from scientific support or nonsupport.

Completed: independently recomputed the M5E-D matrix and reproduced M5E-E in an isolated acceptance directory. Six statistical CSVs and nine figures matched byte-for-byte; four JSON outputs matched after normalizing run-specific timestamp and commit provenance. See `docs/m5e_f_independent_acceptance_report.md`.

Acceptance: passed. Engineering acceptance is separate from scientific support: H1 remains not fully supported, H2/H3 retain direction-specific support only, and unsupported outcomes are retained.

### Milestone 5F - Compression validation report and next-step decision

Planned: write the Milestone 5 report and decide whether remote perception or closed-loop navigation evaluation is justified.

Acceptance: the report states what compression and image-risk-region claims are supported, what remains unproven, and the single next priority.

## Milestone 6 — Simple closed-loop navigation

M5 is formally frozen after M5E-F acceptance. M6 remains planned and does not authorize immediate Risk-VoI training or closed-loop navigation: it first requires independent counterfactual data generation, frozen task utility/splits, and oracle/greedy baseline validation.

The M5E-D closeout audit and [M6 follow-up baseline/ablation protocol](m6_followup_evaluation_protocol.md) are complete design artifacts. The first M6 execution candidate is independent-data byte-fairness validation plus the command-conditioned versus state-only trajectory ablation; no M5 formal evidence may be retuned or reused for training.

The post-M5E-E [Risk-conditioned Visual VoI plan](m6_risk_voi_experiment_plan.md) is a future experiment-design artifact, not authorization to train a model or start M6 before M5E-F acceptance.
# M6 formal multi-scene execution gate (2026-07-25)

Implement and validate TCOBR and exact formal identity selection; commit the 32-episode pre-registration; require full tests, clean tracked state, and unchanged frozen manifest/lock; then prepare and launch only the registered identities once each with no retry. Analyze only completed, strictly validated formal episodes with the pre-registered episode-level procedure.
