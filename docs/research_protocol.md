# Research protocol

## Title

**Trajectory-Conditioned Collision-Risk-Aware Visual Communication for Remote Robot Navigation**

中文：面向远程机器人导航的轨迹条件化碰撞风险感知视觉通信

## Research question

Under the same or closely matched communication budget, can trajectory- and collision-risk-driven visual resource allocation reduce safety-critical obstacle misses and collisions, and improve navigation success, compared with uniform compression, a fixed center ROI, and an object-only ROI?

## Phase 1 scope

Phase 1 is a research prototype using native Windows, Webots, Python, one differential-drive robot, a forward RGB camera, mostly static obstacles, simulator ground truth, a 1–2 second trajectory horizon, an explicit risk map, block-wise spatial compression, offline perception evaluation, and later a simple closed-loop navigation evaluation.

Out of scope: ROS 2, WSL as the development environment, human teleoperation, multiple robots, real radio/network implementation, reinforcement learning, VLA models, future-frame generation, event cameras, soft robots, real robot hardware, training a neural codec, and full H.265/VVC or physical-layer implementation.

Learning-based visual allocation will not start until interpretable geometry/rule methods show an initial positive result.

## Hypothesis

At the same image size or approximately matched bitrate, preserving high-risk regions near the robot's predicted future trajectory will retain safety-relevant obstacle information better than uniform compression, a fixed center ROI, or a high-quality ROI over every obstacle.

## System chain

Camera → Robot state and future trajectory → Collision risk map → Spatial visual resource allocation → Compressed observation → Remote perception → Navigation decision

## Inputs and outputs

Inputs: RGB frame, world pose and heading, linear and angular velocity, current command, predicted 1–2 second trajectory, obstacle ground-truth positions, and per-frame budget.

Outputs: predicted trajectory, robot-width-inflated trajectory corridor, obstacle risk scores, pixel/block risk map, images from each compression policy, byte count and encoding time, perception outputs, and navigation/safety logs.

## Initial risk formulation

Milestone 3A freezes the first world-coordinate risk formulation in `docs/risk_formulation_design.md`.

The first version uses static axis-aligned rectangular obstacle footprints, Trajectory Occupancy Corridors, obstacle-boundary-to-trajectory clearance, and Time-to-Conflict (`TTCf`) rather than broad Time-to-Collision wording. `TTCf` is the first future time when an obstacle footprint enters a Trajectory Occupancy Corridor; it is a geometric conflict proxy, not a true rigid-body collision time.

The first interpretable risk proxy is:

```text
spatial_score = exp(-max(clearance_m, 0) / sigma_distance_m)
temporal_score = exp(-relevant_time_s / tau_time_s)
risk_score = spatial_score * temporal_score
combined_risk = max(planned_risk, state_risk)
```

Risk scores are heuristic values in `[0, 1]`, not probabilities. Camera projection, image risk maps, compression allocation, dynamic obstacles, and learned risk models remain out of scope until the world-coordinate risk core is implemented and validated.

## Comparators

- Baseline A — Uniform compression: one quality level for the whole image.
- Baseline B — Fixed center ROI: higher quality in a fixed central/forward region.
- Baseline C — Object ROI: higher quality for all obstacle regions without trajectory relevance.
- Proposed — Trajectory and collision-risk ROI: dynamic quality based on trajectory, distance, speed, and TTC.

Possible later additions: semantic ROI, learned spatial mask, no-TTC ablation, and no-trajectory ablation.

## Fair comparison

Milestone 5A freezes the detailed compression and fair-bitrate protocol in `docs/m5_compression_and_bitrate_protocol.md`.

The first compression experiment is a tiled-JPEG spatial allocation prototype, not a standards-compatible ROI video encoder. Numeric budgets are not hard-coded at protocol time; Milestone 5B must run a Uniform JPEG pilot and then select at least four feasible target budgets. Every comparison must match actual transmitted bytes, including container overhead, and the proposed Risk ROI method must not receive a systematically larger budget.

Milestone 5E-A freezes the multi-scene protocol in `docs/m5e_multiscene_offline_evaluation_protocol.md`. The M4D/M5D frame is development-only and excluded from M5E calibration and formal statistics. M5E common budgets are selected from calibration data only, then frozen before formal evaluation. The four methods, scoring rules, allocation search, risk threshold, JPEG/container settings, snapshot rules, and scenario weights cannot be changed from formal outcomes.

M5E-C froze the common complete-container-byte interval `[31240, 35779]` and the formal targets severe `31466`, low `32374`, medium `33509`, and high `34871` bytes. M5E-D generated the formal 256-frame split and 4096 matched-budget reconstructions with those targets unchanged. M5E-E completed the pre-registered episode-level statistics without changing the protocol: H1 is not fully supported, while H2/H3 receive direction-specific support under their frozen scenario contrasts. These remain offline image-quality findings only.

## Metrics

- Communication: bytes/frame, estimated bitrate, compression ratio, encoding time.
- Conventional image quality: PSNR and SSIM.
- Task/safety: trajectory-critical obstacle recall, trajectory-corridor obstacle miss rate, risk-region IoU, navigation success rate, collision rate, near misses, completion time, path length, and emergency stops.

Conclusions must not rely on PSNR or SSIM alone.

For M5E, the primary offline metric is continuous combined-risk-weighted PSNR at severe and low matched actual-byte budgets. The primary paired comparisons are Risk ROI against Uniform, Center ROI, and Object ROI. The episode, not the frame, is the primary resampling unit: four fixed snapshots are aggregated within each episode, and 10,000 fixed-seed bootstrap replicates preserve the eight scenario strata. This remains image-quality evidence over a heuristic risk proxy, not perception, collision, or navigation evidence.

## Milestone 5E scenario set

The first formal multi-scene experiment is limited to static AABB obstacles and freezes eight families: straight collision-relevant obstacle, off-trajectory visual distractor, left turn, right turn, planned/state disagreement, large low-risk versus small high-risk, partial visibility, and low-risk control. Development, calibration, and formal seeds/episodes are disjoint. Calibration contains 64 frames; formal evaluation contains 256 frames and 4096 method-budget reconstructions. M5E-D completed that formal metric table, M5E-E completed the frozen episode-level analysis, and M5E-F independently reproduced and formally accepted the evidence. These remain offline image-quality findings only.

## Initial scenarios

1. Straight motion with a small obstacle ahead.
2. Multiple obstacles, only one intersecting the future trajectory.
3. Left- and right-turn scenes.
4. Narrow doorway.
5. Constant-speed dynamic obstacle crossing the trajectory.

Phase 1 begins with scenarios 1–3.
# M6 formal multi-scene amendment (2026-07-25)

The M6 primary downstream measure is TCOBR as operationally frozen in `docs/m6_followup_evaluation_protocol.md`. The complete 32-episode S1-S8 matrix, paired contrast, exclusions, bootstrap seed/replicates, and support gate are committed in `docs/results/m6_multiscene_preregistration.json`. Pilot and disposable-smoke identities are never analysis eligible.

# M7 diagnostic and offline allocation gate (2026-07-28)

M7 begins with a descriptive, read-only diagnosis of the frozen M6 v3 evidence. ROI/pixel/tile overlap, final JPEG-quality divergence, critical-region tile payload, critical-boundary high-quality coverage, critical-region PSNR, absolute episode TCOBR, and eligibility reasons use the definitions in `docs/m7_m6_zero_effect_diagnostic.md`. These derived diagnostics do not amend M6 outcomes.

The first M7 allocator is a deterministic marginal visual-value-per-exact-byte baseline, not a learned policy. Its allowed causal inputs, equal-weight risk/coverage/visibility/uncertainty term, counterfactual marginal reconstruction benefit, exact byte cost, tie breaks, provenance, and offline gates are frozen in `docs/m7_budget_conditioned_voi_design.md`. M5/M6 evidence cannot be used for weight or threshold tuning. A new Webots proposal requires new disjoint, eligibility-rich data and all offline gates; passing the gates is not launch approval.

The first independent development authority is the M7 v1 corpus in `docs/m7_v1_development_corpus_protocol.md`: 16 fixed episodes across M7C1-M7C6 and M7G1-M7G2 at seeds 710100-710801. Geometry and identities are frozen before rendering. Sender-visible state/schedule/projection inputs are separated from evaluator-only obstacle geometry; no allocator or task-effect calculation occurs during generation. Each identity may launch once with no retry, and a shared defect stops the batch.

The frozen allocator implementation interpretation is recorded in `docs/m7_visual_voi_implementation_protocol.md`. It preserves the 8x6 grid, `(1, 15, 35, 55, 75, 95)` JPEG ladder, equal 0.25 component weights, 50/30/20 diagnostic-distortion weights, exact container-byte accounting, and the nine conjunctive gates. Evaluator-only geometry is loaded only after allocation. The completed M7 v1 evaluation is a `NO-GO`: gates 2, 4, 6, and 7 fail, so the corpus cannot authorize Webots or a 720xxx formal split.

M7 v2 is a separate development-only revision defined in `docs/m7_v2_offline_development_protocol.md`. It preserves M7 v1 unchanged and adds a two-baseline matched-byte midpoint, highest feasible uniform quality floor, and three preregistered residual-upgrade ablations. All transition costs use complete-container recomputation and evaluator-only evidence remains unavailable until allocation ends. The v2 result is also `NO-GO`: exact bytes and quality pass, but continuous-task, fidelity, and scene-balance gates fail for all candidates.

## M8-A sender-available proxy qualification protocol (2026-07-30)

M7 v1 and v2 are frozen development-only `NO-GO` baselines. M8 retains their validated matched-container-byte accounting, 0.5-percentage-point utilization tolerance, highest-feasible uniform quality floor, exact candidate-container recomputation, deterministic residual upgrades and tie-breaking, and zero leakage/fallback/replacement requirements. TCOBR is retained only as a non-degradation safety metric.

Before any new allocator is implemented, M8-A qualifies two operational measurement families on a new independent calibration split: fixed RGB obstacle-perception utility (FROPU) and sender-time risk-weighted continuous fidelity (STRCF). Exact candidate computations, allowed inputs, failure modes, and the evaluator-only CCORF calibration reference are defined in `docs/m8_a_proxy_comparison.md`.

Proxy qualification is independent of allocation outcomes. Deterministic codec perturbations are generated for every calibration snapshot; proxy artifacts are produced from a sender-only view; evaluator geometry, CCORF, TCOBR, perturbation class, and future information are joined only after proxy provenance validates. Episode is the statistical unit. Episodes are resampled within critical scene, scenes receive equal weight, and percentile 95% intervals use 10,000 replicates with seed `20260724`.

All nine gates in `docs/results/m8_a_proxy_validation_rules.json` are conjunctive: integrity/boundary, dynamic range, monotonicity, CCORF association, pairwise ranking, critical specificity, scene stability, incremental validity beyond full-frame PSNR, and byte-identical reproduction. FROPU must also pass the separately defined detector prerequisite. If both candidates pass, FROPU becomes primary and STRCF a safeguard; if one passes, only that candidate may proceed; if neither passes, allocator development is `NO-GO`. M7 outcomes and future allocator effects may not select a proxy.

The proposed versioned corpus design has disjoint calibration/development/formal seed families `810xxx`, `820xxx`, and `830xxx`. It covers eight critical scenes spanning straight/turning, near/far, left/right, and full/partial visibility, plus two low-risk generalization scenes. The proposed matrix contains 28 calibration, 40 development, and 40 formal episodes. It is a design artifact, not a launch manifest. Every future split requires a separately approved immutable manifest/lock and geometry checks before launch; no post-outcome replacement is permitted.

M8-A does not validate either proxy, implement an allocator, create a corpus, or support perception, navigation, collision, or safety claims.

## M9-A-P predictive future-danger validation protocol (2026-08-13)

M9-B is a separate confirmatory replication defined in `docs/m9b_confirmatory_preregistration.md`. It retains only R1-R0 as primary, uses distinct `94/95/96xxxx` namespaces and 240 distinct Formal geometry/schedule cells, and cannot access Formal without a new sealed contract and authorization. M9-A remains immutable.

M8 is paused while M9-A tests the missing causal bridge between predicted future motion and independently observed future danger. Existing M5E/M6/M7 data are ineligible because they contain only four actual-state snapshots per episode at gaps greater than 1.18 s and no validated dense contact stream.

The protocol-only M9-A-P stage is frozen in `docs/m9a_p_future_danger_protocol.md`. It defines disjoint pilot/calibration/formal partitions, eight danger-rich static-AABB scenario families, dense 0.032 s actual-state/contact logging, physical-contact collision truth, calibration-only near-danger and warning thresholds, exact nominal 0.5/1.0/2.0 s horizons, separate actual-future labels, frozen R0/R1/R2 conditions, episode-level inference, minimum-support rules, exclusions, and formal-access protection. It authorizes no Webots launch, dataset, result, or C2/C3 conclusion.

M9-A-R independently reviewed this protocol and returned `PASS WITH REQUIRED AMENDMENTS`. The amended primary tests are 2.0 s danger AUPRC using negative predicted physical clearance for paired R1-R0 (C2) and R2-R1 (C3), each requiring an absolute improvement of at least 0.05 and a paired episode-stratified 95% interval lower bound above zero. Secondary metrics cannot rescue a failed claim. Literal finite scenario grids, seed mapping, implementation review, and explicit launch approval remain required before pilot execution.

## CVC-P5 held-versus-current timing diagnostic (2026-08-14)

CVC-P5 is a development-only mechanism diagnostic over the unchanged six P4 scenarios and A0/A1 policies. At every 32 ms step it compares the receiver's pre-decision decoded HELD frame with a shadow CURRENT frame processed through the same frozen quality-45 exact-24,000-byte JPEG packet, decode, detector, and controller path. Shadow packets are never charged and evaluator geometry is unavailable to either branch.

Visual novelty retains decoded pixel MAE/RMSE, `1-SSIM`, and a threshold-10 changed-pixel fraction. Perception novelty retains existence, selected-component bearing/proximity/confidence, centroid, bounding-box, and component-count differences plus an equal-scale L2 diagnostic. Control sensitivity is the Euclidean left/right-wheel command difference, with signed wheel, speed, and steering changes retained separately. These layers may not be combined into an allocator score during P5.

Outcome-independent timing uses each signal's cumulative 25/50/75% mass, peaks, concentration, and continuous cross-correlation. A trigger before q25 is classified `before`, q25 through q75 as `during`, and after q75 as `after`. Navigation outcomes enter only the later trade-off diagnosis. P5 authorizes no new allocator, no parameter sweep, and no C4/C5 Formal execution.

## CVC-P6 risk-arm/task-novelty-spend development protocol (2026-08-15)

CVC-P6 v1 separates predictive risk relevance from current observation value. R0/A0 and R1/A1 share one state machine: risk crossing 0.14 changes `NORMAL -> ARMED` without itself requiring transmission; an outcome-blind decoded HELD-versus-CURRENT perception event changes `ARMED -> SPENT`; one fixed reserve at step 218 changes the state to `RESERVE`. U0 remains fixed at steps 0/109/218. All methods send three exact 24,000-byte packets.

The frozen event is bearing change above 0.15, proximity change above 0.075, relative selected-component area change above 0.50, or component appearance/disappearance. The ARM deadline is 96 steps and an unarmed adaptive fallback occurs at step 217. These values were selected from a finite signal-only calibration before P6 Webots outcomes. Control sensitivity remains evaluation-only; evaluator geometry, future frames, clearance, collision, progress, and success are forbidden sender/controller inputs.

P6 is development-only. Its first six-scenario comparison is terminal for the frozen configuration: no result-driven parameter repair is permitted, and no C4/C5 Formal protocol or authority follows automatically from any P6 outcome.

## CVC-P7 safety-value discrimination development protocol (2026-08-15)

CVC-P7 preserves P6 v1 exactly and separates sender-visible candidate cues from evaluator-only physical relevance. Sender diagnostics use only decoded held/current perception and the frozen visual controller: bearing convergence, proximity/area/bbox growth, component events, central-corridor overlap, image age, and differential-drive `delta_v`/`delta_abs_turn`/turn direction. Clearance, contact, future physical windows, category, trajectory, progress, and outcomes are evaluation-only and cannot affect ARM, SPEND, receive, perception, or control.

The outcome-independent physical reference is contact or clearance <=0.12 m in the next 63 steps (2.016 s), restricted to steps no later than minimum clearance. The frozen suite contains three deterministic cells in each novelty x intended-safety category A/B/C/D and must not be repaired, replaced, or reclassified after U0/A0/A1 outcomes. All policies retain three exact 24,000-byte packets, the frozen P6 novelty thresholds, deadline, reserve, JPEG quality, detector, and controller.

P7 is diagnostic only: feature rankings require positive physical-window support; no weighted SafetyVoI, learned allocator, P8 implementation, or C4/C5 Formal authorization follows from P7. When support is absent, candidate discrimination and safety lead are reported not estimable rather than recovered by changing the physical threshold or scenarios.

## CVC-Q1 safety-aware local-planning development protocol (2026-08-15)

CVC-Q1 replaces component-centering with a deterministic safety-first local planner. Fifteen commands cross speeds `{0,0.045,0.08}` m/s and turns `{-1.6,-0.8,0,0.8,1.6}` rad/s. M2-compatible 1.5 s rollouts use 0.1 s steps. Conservative visual clearance below 0.025 m is hard-unsafe; at least 0.075 m is preferred-safe; progress is considered only after feasibility. Near-obstacle speed is capped at 0.045 m/s and no hard-safe candidate yields stop.

Runtime inputs are decoded imagery, deterministic detections, outcome-blind range calibration, known dimensions, causal command odometry/history, causal static-obstacle memory, and goal bearing. Webots geometry, pose, contact, clearance, labels, and future outcomes are evaluator-only after action selection.

The 10-cell support grid was frozen after fresh-vision feasibility and before U0 outcomes. Collision is bilateral contact; near is no contact with clearance <=0.12 m; safe is no contact above 0.12 m. The neutral sweep uses exact 24,000-byte packets at `{1,2,3,6,12,24,48}` uniform transmissions. HELD/CURRENT shadow replay is diagnostic only and does not drive Q1 control.

Q1 terminates at development classification. It authorizes no A0/A1 run, predictive allocator, C4/C5 Formal, ML, or post-outcome scenario replacement.

## CVC-Q2 Risk-ARM + Safety-Decision-Value-SPEND development protocol (2026-08-15)

CVC-Q2 is the single frozen development comparison defined by `docs/cvc_q2_development_protocol.md` and `config/cvc_q2_development.json`. It preserves the Q1 planner, perception, memory, ten cells, physical labels, and exact 24,000-byte packet. U0 sends uniformly; A0 and A1 use the same threshold, value event, 47-step deadline, fallback, and reserve, differing only in causal R0 versus R1 ARM. HELD and hypothetical CURRENT planning are sender-side counterfactuals; evaluator pose, geometry, clearance, contact, labels, and outcomes remain unavailable until after actuation.

The pre-outcome manifest fixes a three-packet budget and the transparent three-priority Safety Decision Value hierarchy. The terminal run produced zero value-triggered packets: all 20 adaptive packets used the ARM deadline or unarmed fallback, even though 113 value-event timesteps appeared later. This is `CASE D`; no outcome-driven timing repair, ML model, expanded suite, C4/C5 Formal study, or claim of predictive communication safety is authorized.

## CVC-Q3 temporal-repair development protocol (2026-08-16)

CVC-Q3 preserves every Q1/Q2 scientific component and repairs only temporal eligibility. A bounded 63-step Safety Value latch can wait before/after ARM; one adaptive token remains eligible until value or step-295 fallback; a separate final reserve is fixed at step 311. Every policy retains exactly three 24,000-byte packets. The full pre-outcome definition and hashes are in `docs/cvc_q3_development_protocol.md` and `results/cvc_q3_readiness/manifest.json`.

The terminal run produced two same-step value-triggered sends, proving the local `SafetyValue -> SEND -> safe-plan/control change` link. It failed the frozen meaningful-frequency gate: 2/20 adaptive packets rather than at least 3, and fallback caused 4/6 risk-armed packets. A0/A1 schedules and outcomes were identical. Q3 is `CASE D`; no further timing adjustment, broader navigation validation, ML, or Formal study is authorized by this result.

## CVC-Q4 safety-decision precursor diagnostic (2026-08-16)

CVC-Q4 is offline, development-only, and does not implement a communication allocator. Q1 stable/no-change windows define one-sided 1% normal-variation tails. Q2/Q3 future Safety Decision Value onsets are evaluation-only and never enter causal signal calculation. The tested decision-space signals are the CURRENT margin of the HELD-selected action, the best-current safety-margin gap, safe fraction, positive safety slack, soft feasibility mass, and lower-quartile candidate margin. Causal OLS, Theil–Sen, and median-adjacent trends use only past-through-current 8/12/16/20-sample windows.

The terminal Q4 result is `CASE C`. A stable-Q1 q01 soft-feasibility level plus abnormal negative OLS-8 slope covers 8/8 observed onsets, but positive support is limited to two scenario families and 10/53 event-free episodes activate. This diagnostic does not authorize scheduler integration, ML, broader navigation evaluation, or Formal. The only recommended next step is a separate event-rich, no-scheduler support qualification of the frozen rule.

## CVC-Q5 event-rich precursor qualification (2026-08-16)

CVC-Q5 separates precursor-blinded physical support development from frozen-rule evaluation. Stage A may use only causal camera/Q1 held-current planner states, physical behavior, and frozen Safety Decision Value; it must preserve every attempted cell and freeze the complete corpus before accessing Q4 outputs. The exact rule is soft-feasibility mass <=0.6543448254639964 and causal OLS-8 slope <-0.11876628431105299/s. Generalization gates are 75% pooled coverage, 50% coverage in at least three positive families, 0.25 s median lead, 2% active time, 25% event-free episode activation, and usable multi-sample opportunity for at least half of covered onsets. Q5 remains development-only and cannot itself test communication or navigation benefit.

## CVC-Q6 terminal development protocol and boundary (2026-08-16)

Q6 preserves the exact Q5 rule, the causal Q1 perception/planner stack, evaluator separation, JPEG/container path, 10 s/312-step horizon, and three 24,000-byte packets. U0 sends at steps 0/109/218. A0 retains current-clearance semantics. A1 variants may change only causal scheduler eligibility; the step-218 token remains protected and step-217 is the late fallback. The physical danger boundary remains clearance <=0.12 m or bilateral contact.

Development selection requires the full `SEND -> decoded image -> planner/control -> physical safety` chain and non-adverse safety relative to both A0 and the strongest U0 baseline, including no serious adverse family. Frames are mechanistic observations; the physical scenario cell is the comparison unit. Progress/completion cannot rescue adverse safety.

The terminal generation uses two consecutive exact-precursor samples to spend. It is not frozen for downstream use: it improved safety versus A0 but was mixed versus U0 and adverse in staggered slalom. The grouped learned diagnostic also failed its false-warning burden. Q6 is therefore `Q6-C`. Q7 may not be created or consumed until a new method is developed on genuinely new development evidence, frozen under a new identity, and satisfies this selection boundary. Formal and real-robot execution remain unauthorized.
