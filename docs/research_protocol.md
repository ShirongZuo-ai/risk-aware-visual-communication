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
