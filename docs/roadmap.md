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
- [x] Implement the deterministic allocator and provenance contract on new disjoint offline data; keep both M6 methods unchanged as baselines.
- [x] Freeze the M7 v1 development authority: 16 disjoint M7C1-M7C6/M7G1-M7G2 episodes, outcome-blind geometric prechecks, isolated evaluator geometry, and an at-most-once generation contract.
- [x] Finalize the registered M7 v1 corpus and independently reload all runtime, 512 codec-case, joint, final, and ownership evidence.
- [x] Generate an independent counterfactual tile-quality dataset with actual complete-container byte increments from the finalized M7 v1 corpus.
- [ ] Implement an offline oracle and deterministic greedy marginal-utility-per-byte baseline before any learned allocator.
- [x] Pre-register episode/scene splits, byte fairness, failure handling, task metrics, and support gates.

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

## M7 Visual-VoI offline gate (2026-07-29)

- [x] Complete and validate the 16-episode disjoint M7 v1 development corpus.
- [x] Implement the frozen equal-weight budget-conditioned Visual-VoI allocator with exact byte recomputation and strict sender-time inputs.
- [x] Compare with both frozen M6 baselines at Severe, Low, Medium, and High budgets.
- [x] Evaluate all nine preregistered gates without post-result tuning.
- [x] Persist canonical case, episode, provenance, bootstrap, gate, and figure artifacts.
- [ ] Redesign the offline allocation objective under a separately reviewed protocol.
- [ ] Create any 720xxx formal authority or request any Webots launch.

Acceptance: **NO-GO**. The development allocator demonstrates deterministic allocation actuation and critical-boundary coverage, but fails eligibility richness, byte fairness, offline task utility, and quality safeguards. No further Webots study is permitted by this gate. The next milestone is an offline measurement-and-objective redesign, not parameter tuning on M7 v1.

## M7 v2 constrained offline revision (2026-07-30)

- [x] Freeze a limited three-candidate ablation set before evaluation.
- [x] Enforce a matched two-baseline byte envelope and uniform minimum-quality floor.
- [x] Recompute complete-container bytes for every candidate upgrade.
- [x] Preserve zero-leakage sender-time inputs and method-independent evaluation.
- [x] Evaluate exact-byte, actuation, continuous-utility, quality, TCOBR, scene-balance, and reproduction gates.
- [x] Retain null, adverse, and scene-concentrated outcomes.
- [ ] Prepare a new formal corpus or launch Webots.

Acceptance: **NO-GO**. The matched-floor design fixes byte fairness and reconstruction quality, but no preregistered candidate has a positive continuous-utility CI lower bound, positive fidelity at both primary budgets, or scene-balanced gains. The next priority is a new offline measurement review; post-result candidate tuning is prohibited.

## Milestone 8 - Measurement-qualified budget-conditioned visual communication

### M8-A - Scientific design and M7 closeout (complete)

- Freeze M7 v1/v2 as immutable `NO-GO` development baselines.
- Preserve matched actual container bytes, utilization tolerance, uniform quality floor, deterministic task upgrades, exact recomputation, and strict information boundaries.
- Define FROPU and STRCF operationally without implementing or evaluating them.
- Define evaluator-only CCORF calibration reference, detector prerequisite, nine proxy gates, and fixed selection rule.
- Propose a disjoint 28-episode calibration, 40-episode development, and 40-episode formal matrix covering eight critical and two generalization scenes.
- Validate the design matrix and rules read-only. No Webots, allocator, corpus, or experimental outcome belongs to M8-A.

### M8-B0 - Proxy implementation (complete offline)

- [x] Implement FROPU, STRCF, and isolated CCORF with canonical provenance and tamper rejection.
- [x] Add synthetic/offline tests for sender/evaluator separation, detector determinism, score computation, empty domains, perturbations, and canonical reproduction.
- [x] Persist a deterministic unit-validation report that explicitly withholds scientific qualification and proxy selection.
- [x] Do not generate Webots data or select a proxy.

### M8-B1 - Independent calibration corpus and proxy qualification (planned)

- Under separate review and launch approval, freeze an immutable calibration manifest/lock from the proposed `810xxx` identities.
- Execute only the registered calibration identities once, with no replacements.
- Apply the frozen perturbation panel and all proxy gates. Select a proxy only by the preregistered rule.
- Stop with `NO-GO` if eligibility or any applicable proxy gate fails.

### M8-C - Allocator development (blocked on M8-B1)

- Freeze the qualified proxy before using the disjoint `820xxx` development split.
- Retain all M7 v2 byte, quality, determinism, and leakage mechanisms.
- Preregister a limited allocator candidate set; do not tune on calibration or formal evidence.

### M8-D - Formal evaluation (blocked)

- Freeze one allocator and a separate `830xxx` formal manifest before data generation.
- Use episode-level, scene-stratified inference and retain null, adverse, and undefined outcomes.
- No formal corpus is authorized by this roadmap entry.

## Milestone 9 - Predictive future-danger validation

### M9-B - Independent confirmatory replication (protocol hard stop)

- [x] Freeze independent identity, primary R1-R0 claim, support margins, physical construction bands, inference, and seed namespaces.
- [ ] Implement and validate distinct-cell Pilot and Calibration grids without predictor-guided construction.
- [ ] Freeze the literal 240-cell Formal manifest and complete readiness contract.
- [x] Obtain and consume separate one-shot Formal authorization.

Formal completion update: 240/240 episodes completed with full support and zero exclusions. C2 replication PASS; R2 remains secondary.

### Closed-loop predictive communication engineering

- [x] Define U0/A0/A1, exact matched-cost accounting, causal information boundaries, and a decoded-image control loop.
- [x] Preserve nominal 1-D scaffold failures as engineering-only evidence.
- [x] Demonstrate actual camera/JPEG/container/decoded-perception Webots control under exact paired bytes.
- [x] Pass HIGH/MEDIUM/LOW communication-relevance sanity.
- [x] Run matched-cost U0/A0/A1 development comparison and retain the null result.
- [x] Complete CVC-P2 non-ceiling development and preserve its R0/R1 allocation-collapse negative.
- [x] Complete CVC-P3 actuation qualification: prediction lead converts to timing, but repeated triggers exhaust budget and do not improve navigation.
- [x] Complete CVC-P4 protected-reserve development: starvation is fixed, but predictive timing remains clearance/pre-danger-age adverse.
- [x] Complete CVC-P5 held-versus-current timing diagnosis: all six R1 triggers precede visual/perception/control q25, and all six control peaks follow the A1 adaptive send.
- [x] Freeze and execute one CVC-P6 risk-arm/task-novelty-spend candidate outcome-blindly; retain its Case-A completion benefit and adverse clearance trade-off without retuning.
- [x] Complete CVC-P7 safety-value discrimination with P6 v1 unchanged: explain the historical centering/progress versus clearance mechanism, freeze and execute a balanced 12-cell suite, and preserve the zero-danger-window support failure as bounded Case D.
- [ ] Before any P8 allocator, separately authorize physical-support qualification with an avoidance-capable controller and outcome-independent danger cells; do not tune communication from P7 outcomes.
- [ ] Freeze any C4/C5 confirmatory protocol before scientific execution.

### M9-A-FR - Formal readiness and evaluation (complete; insufficient support)

- [x] Freeze and hash 144 outcome-free Formal identities and the analysis contract.
- [x] Derive warning thresholds from Calibration only and perform one-shot authorization.
- [x] Generate all 144 episodes without replacement and run the locked analysis.
- [x] Preserve the F6 near-miss support failure and mark C2/C3 `insufficient_support`.

Acceptance: engineering execution is complete; scientific support is insufficient because F6 has 3 rather than 4 near-miss episodes. The next priority is independent evidence review, not augmentation.

### M9-A-P - Danger-rich dataset protocol (complete; protocol only)

- [x] Record why sparse M5E/M6/M7 snapshots cannot independently label future danger.
- [x] Define disjoint pilot, calibration, and sealed formal partitions.
- [x] Specify eight parameterized collision/near-miss/safe scenario families and support targets.
- [x] Freeze dense log and dataset-manifest schemas, exact nominal horizon semantics, contact truth, near-danger calibration, R0/R1/R2, warning/event rules, inference, exclusions, and pilot acceptance.
- [x] Record initial source-backed literature positioning without claiming novelty.
- [ ] Implement the M9-A runtime, labeler, validators, or manifests.
- [ ] Launch Webots or generate pilot, calibration, or formal data.

Acceptance: protocol artifacts are internally consistent and machine-readable schemas parse; M2-M8 evidence is unchanged; no simulator process or dataset is created. Next priority is independent protocol review followed, only if approved, by implementation and pilot engineering. Calibration and formal generation remain unauthorized.

### M9-A-R - Independent protocol review (complete with amendments)

- [x] Review all M9-A-P artifacts against frozen M2/M3 semantics.
- [x] Remove best-signal/horizon/metric outcome-selection freedom with two primary AUPRC contrasts.
- [x] Freeze `d_near`, contact, horizon, warning, event, support, exclusion, and sealing rules precisely.
- [x] Strengthen machine-readable schemas and record literature threat classes.
- [ ] Materialize literal finite scenario grids and deterministic seed mapping.
- [ ] Implement or launch the pilot.

Verdict: **PASS WITH REQUIRED AMENDMENTS**, with the amendments applied. Pilot implementation/execution remains unauthorized until literal scenario authorities and a separately reviewed implementation satisfy the checklist in `docs/m9a_r_independent_protocol_review.md`.

## CVC-Q1 - Safety-aware local planning and physical support

- [x] Audit M2 timing/dynamics and freeze the 15-command, 1.5 s safety-first planner.
- [x] Calibrate deterministic visual range without navigation outcomes.
- [x] Preserve failed v1 and pass the repaired v2 fresh/full-vision gate.
- [x] Qualify and freeze 10 physical cells before communication outcomes.
- [x] Run 70 exact-byte neutral U0 episodes and decision-level diagnostics.
- [x] Classify development `CASE A`: avoidance and physical support qualified.
- [x] Separately preregister Risk-ARM + Safety-Decision-Value-SPEND without modifying Q1.

## CVC-Q2 - Risk-ARM + Safety-Decision-Value-SPEND

- [x] Freeze the transparent event hierarchy, common R0/R1 ARM rule, deadline, reserve, three-packet exact-cost operating point, and terminal criteria before outcomes.
- [x] Pass the outcome-blind eight-gate offline qualification and preserve the distractor/narrow-passage counterexamples.
- [x] Execute exactly one paired ten-cell U0/A0/A1 Webots matrix with exact bytes and receiver-mirror checks.
- [x] Classify `CASE D`: 0/20 adaptive packets were value-triggered; all used deadline/fallback.
- [x] Preserve causal traces, strict analysis, figures, pre-outcome hashes, and protected historical evidence.
- [x] Authorize and freeze a protocol-only temporal repair using a value-triggerable protected token and bounded value window, with Q1 and all risk/value thresholds fixed.

## CVC-Q3 - Temporal repair for Safety-Value communication

- [x] Diagnose Q2 timing without evaluator outcomes and audit detector/planner/value/scheduler runtime.
- [x] Compare five causal repair families on frozen Q2 traces and select one bounded late-token scheduler outcome-blindly.
- [x] Freeze the 63-step latch, step-295 fallback, step-311 reserve, exact three-packet budget, ten-cell grid, and terminal criteria.
- [x] Execute 30/30 U0/A0/A1 Webots episodes with exact cost and sender-mirror integrity.
- [x] Preserve two real same-step Safety-Value sends but classify `CASE D` because only 2/20 packets were value-triggered and fallback dominated risk-armed episodes.
- [x] Preserve seven causal/runtime/safety figures and protected Q1/Q2/M9/P7 evidence.
- [ ] Next priority: separately authorize a mechanism-only schedule-robust Safety Value support study. Do not retune Q3 timing, train ML, or open Formal.

## CVC-Q4 - Safety-decision precursor / gradient diagnostic

- [x] Recover 10 Q1 calibration traces and 60 fixed Q2/Q3 evaluation traces without Webots replay.
- [x] Implement `M_stale`, best-current gap, four safe-set contraction representations, three causal estimators, and four history windows.
- [x] Derive strictly non-zero one-sided thresholds from stable/no-change Q1 variation only.
- [x] Evaluate event coverage, lead, false activation, future windows, scenario support, reliability, and runtime.
- [x] Preserve failed candidates and five visually inspected static figures.
- [x] Classify `CASE C`: the soft-feasibility q01 level-plus-slope rule covers 8/8 onsets but remains limited to two positive families and fires in 10/53 event-free episodes.
- [ ] Next priority: separately authorize event-rich, no-scheduler support qualification across at least three additional Safety-Value-positive families. Do not implement a scheduler, ML, or Formal.
## CVC-Q5 - Event-rich cross-scenario precursor qualification

- **Status:** Complete as development-only CASE A.
- **Result:** Blinded support produced 19 accepted onsets across four new positive families; the manifest was frozen before applying the unchanged Q4 rule. All six generalization gates passed.
- **Boundary:** No scheduler integration, A0/A1 comparison, ML, C4/C5 Formal, commit, or push.
- **Next:** A separately authorized protocol-only precursor-actuated scheduler study with exact matched bytes and frozen Q4 semantics.

## CVC-Q6 - Precursor-actuated closed-loop scheduler

- [x] Freeze and execute the hard-ARM/value-confirmed generation at exactly 72 kB/episode.
- [x] Diagnose live ARM bootstrap starvation and preserve the complete negative matrix.
- [x] Freeze and execute opportunity-plus-SafetyValue generation 2 without changing precursor thresholds, planner, codec, budget, or cells.
- [x] Freeze and execute final two-sample persistent generation 3 against sealed controls.
- [x] Audit send, decoded-image, planner/control, physical safety, family heterogeneity, progress, fallback, and runtime links.
- [x] Run grouped compact logistic/tree ML qualification after escalation criteria were met; reject integration for excessive false warnings.
- [x] Classify Q6-C, preserve the development ledger, master report, verified figure, hashes, and 193-test regression.
- [ ] Q7 remains blocked: no complete method satisfies non-adverse safety versus the strongest U0 baseline across families.
- [ ] Formal and real-robot execution remain blocked behind a future new-development method and independent Q7 pass.

## CVC-Q6.5 - Communication Opportunity Value

- [x] Freeze a direct paired SEND-now/HOLD intervention and safety-first utility target.
- [x] Generate positive, harmful, and neutral support across new physical families with exact 72-kB cost.
- [x] Preserve and repair the sender-risk/runtime-risk feature-interface mismatch before scheduler evidence.
- [x] Reject generation-1 scheduler against strongest U0 under the pre-outcome gate.
- [x] Freeze and execute the adjacent-opportunity target repair with four fixed schedules per cell.
- [x] Evaluate bounded binary and safety-asymmetric multiclass interpretable models by leave-family-out validation.
- [x] Close as Q6.5-C: corrected utility is not safely predictable across families; no method selected.
- [ ] Q7 remains unopened because no method was frozen.
- [ ] Budget robustness, ablation, scheduler Formal, and real-robot work remain blocked.
