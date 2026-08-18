# Closed-loop predictive visual communication engineering protocol

## Scientific boundary

The central future question is whether R1-driven allocation improves physical navigation safety under matched communication cost. Existing M5-M7 offline results are engineering lessons, not proof. The present analytic implementation is a unit scaffold only; it is not credible visual/Webots evidence and cannot support C4 or C5.

## Required causal loop

Each Webots decision must execute: capture 160x120 RGB; derive sender-available R0 or R1 without evaluator geometry; choose U0/A0/A1 allocation causally; encode and serialize an actual tiled-JPEG packet; account complete container and policy metadata bytes; decode or hold the received frame; detect the obstacle from decoded pixels; compute wheel commands only from that received percept; then log evaluator-only physical clearance/contact.

U0 uses fixed uniform communication. A0 uses current-state danger. A1 uses state-only predicted danger. R2/A2 is secondary. Initial ablations are temporal-only, spatial-only, combined, reactive versus predicted, and shuffled-risk negative control.

## Cost and execution rules

Operating points are low/medium/high episode-byte caps. A causal token bucket forbids debt. Payload, container overhead, policy metadata, and padding are separate logged fields. Deterministic terminal padding makes total transmitted bytes exactly equal across paired methods while fixed-horizon simulation prevents early collision from shortening cost exposure.

Scenario/seed pairs are common across methods but each method receives a separate simulator execution. Camera-to-actuation ordering and one-frame latency are frozen before scientific evaluation. Perception/controller code must never read Webots obstacle coordinates, contact, or future trajectory.

Engineering gates require actual camera/JPEG/container bytes, successful decoded-image control actuation, exact paired byte totals, bilateral contact truth, and trajectory divergence caused by received imagery. Only after these pass may a separately frozen confirmatory protocol define collision rate and task success as primary outcomes.

## Current negative scaffold evidence

The 1-D nominal-byte scaffold compared two policy revisions over six scenarios. `offline_quota_v1` was noncausal and adverse: U0 had 2/6 collisions while A0/A1 each had 6/6. `causal_token_v2` removed future ranking and matched all methods at 1,440,000 nominal bytes, but all methods tied at 2/6 collisions. This exposes policy timing and risk saturation problems; it is not visual communication or Webots safety evidence.

CVC-P1 subsequently ran 27 Webots development episodes with actual tiled-JPEG packets. Every U0/A0/A1 policy episode used exactly 1,872,000 wire bytes and 52 transmissions. However, diagnostic camera frames were black, the red detector found zero pixels, and HIGH/MEDIUM/LOW as well as U0/A0/A1 produced identical trajectories. This is a preserved communication-relevance failure, not C4/C5 evidence.

The later CVC-P1 lighting repair and decoded-loop rerun are also preserved: communication conditions changed image age and trajectory, but exact-cost U0/A0/A1 remained at a safety ceiling with 0/8 collisions and about 0.2084 m worst clearance.

## CVC-P2 development result

CVC-P2 uses deterministic decoded-image connected components and bearing/proximity control. U0-only physical selection identified two 36,000-byte packets per 14 s episode as a communication-limited mixed-clearance regime. T, S, and TS use causal exact-quota timing and/or a component-localized image ROI; every corrected matrix episode has exactly 72,000 wire bytes.

The corrected six-scenario matrix is a negative development result. R1 can warn before R0, but frozen allocation thresholds map both signals to identical transmission steps and quality ranges in every pair. Consequently R1 has no communication, perception/control, or physical-outcome lead. T/TS are adverse relative to U0/S. C4/C5 remain unopened; details and retained failures are in `docs/cvc_p2_development_report.md`.
