# Related work

This document is a versioned project-positioning note. It is not yet a systematic literature review and does not add paper-specific claims, performance numbers, or novelty claims that are not already supported by project evidence. Detailed paper monitoring and innovation-threat notes should be folded in here only after source-backed review. The current repository contains no source-backed per-paper extraction; the corresponding no-inference baseline matrix and implementation actions are recorded in [M6 Follow-up Baseline and Ablation Protocol v1](m6_followup_evaluation_protocol.md).

## Current Research Positioning

The current project studies trajectory-conditioned, geometry-grounded visual communication for robot navigation. Its implemented chain projects world-coordinate collision-risk proxies into image space and uses those masks for actual-byte-constrained spatial visual allocation.

The most defensible short positioning statement is:

> Trajectory-conditioned collision-risk projection into image space and actual-byte-constrained visual resource allocation for robot navigation.

Current evidence is limited to a native-Windows Webots/Python prototype with static AABB obstacles, heuristic risk scores, deterministic tiled-JPEG allocation, and offline image-quality metrics. It has not yet shown multi-scene Risk ROI superiority, perception benefit, collision-rate reduction, or closed-loop navigation improvement.

## Crowded Broad Areas

The broad research space is already crowded. Treat these as neighboring or competitive fields, not as open novelty territory:

- safety-aware semantic communication;
- goal-oriented robotic communication;
- task-aware ROI coding;
- risk-aware navigation;
- closed-loop networked control.

Avoid claiming to originate any of these areas.

## Current Defensible Differences

The current project can more safely emphasize the specific combination it implements and validates:

- planned/state dual trajectories rather than a single nominal path;
- explicit trajectory disagreement as a scenario and diagnostic condition;
- TTCf/clearance-based heuristic risk over static AABB obstacle footprints;
- calibrated world-to-camera-to-image projection and image-space risk masks;
- fair comparison under equal complete actual container bytes, not nominal quality labels or payload-only bytes;
- a planned future closed-loop safety evaluation, if M5E formal offline evidence justifies continuing.

These are implementation and protocol differences. They are not yet proof of better safety or navigation performance.

## Main Competition and Borrowed Context

The following directions must be treated as primary competition, useful baselines, or design context when the literature review is expanded:

- CV-Cast;
- GOSC / ISAC robotic obstacle avoidance;
- safety-guaranteed goal-oriented communication;
- semantic/object ROI video coding;
- URVC;
- TouchSafeBench;
- Shared 3D Semantics;
- teleoperation latency and QoC;
- event-based navigation.

Do not add detailed claims about these works until their source-backed notes are imported and checked.

## Innovation-Threat Rules

Do not write:

- first safety-aware robot communication;
- first task-oriented robot communication;
- first dynamic ROI coding;
- first risk-aware navigation.

Prefer narrower phrasing tied to the implemented protocol:

- trajectory-conditioned collision-risk projection into image space;
- actual-byte-constrained visual resource allocation;
- planned/state trajectory disagreement as an auditable risk-allocation input;
- calibration-only common-byte budgets before formal evaluation.
