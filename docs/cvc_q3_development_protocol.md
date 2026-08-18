# CVC-Q3 Temporal-Repair Development Protocol

Study identity: `cvc-q3-temporal-repair-v1`. This is development-only and not Formal.

## Fixed evidence and components

Q1 and Q2 remain immutable evidence. Q3 reuses the Q1 v2 planner, calibrated visual geometry, causal obstacle memory, detector, codec, ten-cell support grid, seeds, goals, 10 s duration, and physical labels. It reuses Q2's R0, R1, common 0.14 crossing, HELD/CURRENT counterfactual planning, and exact three-priority Safety Decision Value implementation without modification. Only temporal scheduling changes.

The scheduler and sender may use current/past risk, current/past Safety Value, latch state, budget, step, and the known fixed episode horizon. Webots pose, object geometry, contact, clearance, physical labels, future frames, future Safety Value, future trajectory, task outcomes, and policy success are forbidden. Evaluator truth is read only after actuation.

## Q2 temporal and runtime diagnosis

The frozen 20 adaptive Q2 traces contain three value-supported episodes. Their ARM-to-first-value delays are 67, 193, and 263 steps; their adaptive-spend-to-first-value delays are 20, 146, and 216 steps. Event runs last 3-52 steps. One first event precedes the old reserve while two follow it, so the failure combines a scheduler-locked reserve with actual capacity exhaustion. A deadline extension alone cannot repair the old step-249 reserve.

The outcome-blind runtime audit uses four saved actual Webots camera fixtures and 2,000 timed calls/component after warmup. The exact detector, both planners, Safety Value computation, and scheduler have a conservative summed Q2 p95 below the 32 ms control period and no component deadline miss. Q2 is therefore classified as a logical scheduler-timing failure, not Case E computation latency.

## Selected repair

The chosen `bounded_latch_late_token` policy combines a bounded value latch with a protected late adaptive token:

1. A Safety Value event activates `VALUE_PENDING` whether it occurs before or after ARM.
2. Pending value remains valid through 63 steps (2.016 s) after its latest event. A subsequent event refreshes the latest-event time; a stronger lower-numbered priority replaces the stored reason.
3. When both ARM and pending value hold and the adaptive token is available, the token sends immediately on that control step. Consumption clears the latch. Only one adaptive token exists.
4. An expired latch clears without sending. Events after adaptive consumption are diagnostic only and cannot reactivate spending.
5. If no value send occurs, step 295 guarantees one late adaptive fallback: `armed_late_fallback` or `unarmed_late_fallback`.
6. Step 311 is a separate protected final reserve and can never be spent by the adaptive transition.
7. U0 remains `[0,156,311]`. Every method sends exactly three complete 24,000-byte packets (72,000 bytes/episode), with actual payload, metadata, container/integrity, and padding reconciliation.

The 63-step window reuses the existing 2.016 s physical-danger horizon and prevents indefinite stale value. Step 295 is late enough to leave at least the existing 0.5 s near-term horizon after the latest Q2 first-value support, while still guaranteeing a refresh 0.512 s before the final reserve. These parameters were selected from timing support, causality, and horizon coverage only.

## Offline qualification and frozen prospective gate

Five trace-conditional families were compared without reading evaluator outcomes: Q2 short deadline, bounded latch under old eligibility, one-step late eligibility, bounded latch plus late token, and episode-persistent latch plus late token. The old policies captured zero or one supported opportunity. All late-token variants captured 3/3. The bounded latch was selected because it adds transient robustness without retaining stale value for the full episode.

The primary prospective mechanism passes only if: at least three of 20 adaptive packets are Safety-Value-triggered; A0 and A1 each have at least one; among risk-armed episodes value sends at least tie fallback sends; every episode with an observed eligible pre-spend value is captured on the same step; final reserve, three-packet exact cost, sender mirror, causality, and identical A0/A1 scheduler code all hold. The 3/20 threshold is the complete frozen Q2 support, not a post-outcome percentage. Unarmed mandatory refreshes are reported separately and cannot enter the ARM-to-value denominator.

Case E applies only if the frozen runtime audit is computational. Otherwise failure of the prospective mechanism is Case D. If it passes, the unchanged safety paths and tie rule in `config/cvc_q3_development.json` select Case A, B, or C. Task outcomes remain separate guardrails. One ten-cell U0/A0/A1 matrix is terminal; there is no retuning, replacement, ML, broader validation, C4/C5 Formal, commit, or push authority.
