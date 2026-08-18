# CVC-P6 risk-armed task-novelty communication

Status: completed as one development-only, outcome-blindly frozen comparison. No C4/C5 Formal protocol, manifest, seal, or execution was created. No post-outcome parameter change was made.

## 1. Implemented architecture

CVC-P6 separates future-danger relevance from current visual transmission value:

`R0 or R1 crosses 0.14 -> ARM`

`decoded CURRENT differs sufficiently from decoded receiver HELD state -> SPEND adaptive packet`

The complete chain remains Webots RGB -> exact JPEG packet -> independent sender-held mirror and receiver decode -> frozen red-component perception -> frozen wheel controller -> Webots trajectory -> evaluator-only clearance/contact.

## 2. Exact state machine

- `NORMAL`: startup packet was sent; no risk crossing yet.
- `ARMED`: selected R0/R1 crossed 0.14; no packet is sent solely because of the crossing.
- `SPENT`: one adaptive packet was sent because a task-novelty event occurred, the 96-step ARM deadline elapsed, or the unarmed step-217 fallback was required.
- `RESERVE`: the protected fixed packet is sent at step 218 and the exact three-packet budget is exhausted.

If novelty is already above a frozen boundary at ARM, same-step spending is legitimate and explicitly retained. If risk never arms, step 217 provides the exact-budget adaptive fallback without consuming the step-218 reserve.

## 3. Reused and new modules

Reused unchanged:

- P2 six scenarios, connected-component detector, and visual wheel controller;
- P3 quality-45 complete-JPEG codec, exact 24,000-byte envelope, integrity check, padding, and holding receiver;
- P4 startup / one adaptive / protected step-218 reserve structure and U0 schedule `0/109/218`;
- P5 decoded HELD/CURRENT visual, perception, and counterfactual-control diagnostics.

New:

- `communication/cvc_p6_allocator.py`: task-novelty representation, event rule, ARM/SPEND state machine, and independent mirrored holding channel;
- outcome-blind calibration and offline qualification scripts;
- P6 Webots controller/world/runner, analysis, causal plotting, and focused tests.

## 4. Outcome-blind novelty calibration

Calibration used no evaluator geometry, clearance, collision, progress, task success, or A0/A1 navigation outcome. A real illuminated Webots center-obstacle frame was repeatedly passed through the frozen codec. Sixteen repeated stable encodes and 16 deterministic one-LSB irrelevant-background changes produced zero bearing, proximity, and area variation. Controlled 4/8/12-pixel translations and 5/10/20% image-scale changes established interpretable detector-scale anchors.

A finite three-candidate panel was declared before P6 Webots outcomes:

| Candidate | Bearing | Proximity | Relative area | Non-immediate A1 | Median delay | Closer to perception q25 | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| resolution_4px | 0.05 | 0.025 | 0.25 | 3/6 | 1.5 steps | 3/6 | fail |
| task_8px | 0.10 | 0.050 | 0.40 | 4/6 | 7.5 steps | 4/6 | fail |
| coarse_12px | 0.15 | 0.075 | 0.50 | 4/6 | 16 steps | 4/6 | pass/select |

The first two are preserved as failed engineering variants. The first listed candidate passing every signal-only gate was selected; no candidate was compared on navigation performance.

## 5-7. Frozen thresholds, deadline, and reserve

The single P6 v1 event is:

- absolute bearing change `> 0.15`, or
- absolute proximity change `> 0.075`, or
- relative primary-component area change `> 0.50`, or
- deterministic component appearance/disappearance.

Confidence is logged but excluded because P5 showed it saturated at 1.0. Centroid, box, and component-count changes remain diagnostics rather than additional free trigger thresholds.

The deadline is 96 steps/3.072 s after ARM: the first 32-step multiple at or above P5's 91-step median R1-to-perception-q25 gap. The protected reserve remains fixed at step 218. Neither value used navigation outcomes.

## 8. Receiver-held mirror

The actual packet independently enters a receiver `P3HoldingReceiver` and a sender-side mirror `P3HoldingReceiver`. Every step checks source timestamp, image age, wire bytes, hold state, and decoded RGB SHA-256. Any divergence is a hard runtime error. All 18 Webots episodes matched at every step.

## 9-12. Offline ARM/SPEND qualification

On frozen P5 traces, A1 R1 ARM times were `2, 6, 1, 11, 16, 7` for angled, center, late, left, right, and two-component scenes. The corresponding selected SPEND times were `51, 82, 12, 11, 16, 28`; ARM-to-SPEND delays were `49, 76, 11, 0, 0, 21` steps, median 16.

The same-trace median R1-before-R0 ARM lead remained 38 steps. Four of six A1 sends became non-immediate and moved closer to P5 perception q25. No deadline or unarmed fallback dominated A1. Deterministic replay, shared A0/A1 implementation, protected reserve, exact cost, and forbidden-input checks all passed before Webots authorization.

## 13-14. Exact communication accounting and schedules

All 18 episodes transmitted exactly three complete packets. Each packet is exactly 24,000 wire bytes including JPEG, metadata, integrity fields, and deterministic padding; every episode totals exactly 72,000 bytes. All budgets exhaust at the common step-218 reserve.

| Scenario | U0 | A0 ARM -> SPEND | A1 ARM -> SPEND |
|---|---|---|---|
| angled_toward | 0/109/218 | 28 -> 35 | 2 -> 35 |
| center_large | 0/109/218 | 50 -> 84 | 6 -> 84 |
| late_appearance | 0/109/218 | 9 -> 11 | 1 -> 11 |
| left_offset | 0/109/218 | 35 -> 35 | 11 -> 11 |
| right_offset | 0/109/218 | unarmed -> 217 | 16 -> 16 |
| two_component | 0/109/218 | 58 -> 58 | 7 -> 16 |

A0 and A1 converge to identical schedules and exactly identical trajectories in angled, center, and late scenes. They differ only through R0 versus R1 ARM input; thresholds, deadline, reserve, codec, detector, controller, dynamics, and bytes are identical.

## 15. Visual, perception, and control alignment

In the actual P6 A1 runs, four of six adaptive sends were delayed versus P4 and moved closer to both perception q25 and control q25. Median actual ARM-to-SPEND delay was 9.5 steps because the closed-loop trajectories differed from offline P5 replay.

Counterfactual control sensitivity increased from ARM to SPEND in every delayed representative case:

- angled: `0.0385 -> 0.6026 rad/s`;
- center: `0.1212 -> 1.3709 rad/s`;
- late: `0.0542 -> 0.4477 rad/s`;
- two-component: `0.1991 -> 0.3608 rad/s`.

Left and right offset legitimately spent immediately because the frozen bearing event was already present at ARM. No P6 A1 send used the deadline.

P6 improves alignment but does not locate every later peak. In several scenes the task-novelty event still precedes cumulative perception/control q25 by many steps. This is a mechanistic improvement, not an optimal timing claim.

## 16. Image age

| Policy | Overall mean age | Pre-danger mean age | Maximum pre-danger age |
|---|---:|---:|---:|
| U0 | 2,610.0 ms | 2,396.2 ms | 6,976 ms |
| A0 | 3,042.6 ms | 2,621.2 ms | 6,976 ms |
| A1 | 3,130.0 ms | 3,070.0 ms | 6,976 ms |

Relative to P4, A1's mean pre-danger age falls from 3,692.9 to 3,070.0 ms and overall mean age falls from 3,371.3 to 3,130.0 ms. The worst case remains unchanged because all methods retain the common step-218 reserve and long post-reserve hold.

## 17-19. Navigation outcomes

| Policy | Collisions | Task successes | Mean episode minimum clearance | Mean clearance | Mean forward progress | Mean path length |
|---|---:|---:|---:|---:|---:|---:|
| U0 | 0/6 | 1/6 | 0.409184 m | 0.580075 m | 0.314323 m | 1.063223 m |
| A0 | 0/6 | 1/6 | 0.413892 m | 0.583240 m | 0.224461 m | 0.862315 m |
| A1 | 0/6 | 4/6 | 0.261445 m | 0.404843 m | 0.658107 m | 0.798210 m |

Successful completion times are U0 `10.080 s`, A0 `7.648 s`, and A1 mean `7.088 s` across four successes.

The three A0/A1 schedule-different scenes—left, right, and two-component—produce A1 task success versus A0 failure in all 3/3, with A1 progress advantages of `+0.577`, `+1.208`, and `+0.817 m`. They also produce A1 minimum-clearance losses of `-0.375`, `-0.235`, and `-0.304 m`. The other three paired trajectories tie exactly.

Completion/progress value and safety clearance therefore remain separate: P6 retains a repeatable completion benefit but does not establish a safety benefit.

## 20. Representative causal traces

Three inspected figures under `results/cvc_p6_webots/figures/` align R0/R1, ARM/SPEND/reserve, normalized novelty features, receiver image age, counterfactual control sensitivity, actual wheel commands, clearance, and contact:

- `center_large`: R1 arms at 6, waits until proximity novelty spends at 84, and A0 converges to the same spend/trajectory.
- `left_offset`: bearing novelty is already above threshold at R1 ARM step 11, so same-step spending is legitimate; A1 completes but loses clearance versus A0.
- `two_component`: R1 arms at 7 and bearing novelty spends at 16; A0 waits until ARM/spend at 58. A1 completes while losing clearance.

Exact step-level causal evidence is retained in `results/cvc_p6_webots/traces/`.

## 21. Failed and rejected variants

- `resolution_4px` failed because only 3/6 A1 cases delayed, median delay was 1.5 steps, and only 3/6 moved closer to perception q25.
- `task_8px` delayed 4/6 and improved 4/6, but failed the frozen 16-step median-separation requirement at 7.5 steps.
- No threshold, deadline, reserve, packet, scenario, detector, controller, or risk-model revision was attempted after Webots outcomes.
- A learned score, control-sensitivity trigger, optical flow, evaluator geometry, and outcome-based selection were rejected for P6 v1.

## 22-25. Decision

P6 **solves the P5 temporal-misalignment mechanism at the frozen development gate**, but only partially in magnitude: A1 delays 4/6 sends, improves q25 proximity in 4/6, and makes A0/A1 converge in three scenes. It does not place every send at the strongest later control moment.

Result classification: **CASE A - Mechanism + task benefit**.

Predictive risk now demonstrates engineering task value for completion and forward progress in this six-scenario development set: every schedule-different scene favors A1 completion, with no collisions. It still does **not** demonstrate safety-clearance value; every schedule-different scene has lower A1 clearance.

Broader development validation is justified specifically to test whether the completion advantage survives additional unchanged-method scenarios while the clearance penalty can be understood—not to retune P6 v1 on these outcomes.

C4/C5 confirmatory testing is **not justified yet**. Six controlled scenarios, three schedule-different pairs, a coarse detector, and an adverse clearance trade-off are insufficient for Formal authority.

## 26. Recommended next experiment

Freeze a separate **CVC-P7 safety-value discrimination study** without changing P6 v1. Reuse P6 as a baseline and add new development scenarios selected independently of P6 outcomes to distinguish approach-relevant novelty from lateral/post-pass novelty. The primary question should be whether sender-available novelty can retain P6's completion advantage while avoiding systematic clearance loss. Any candidate representation or guard must be calibrated without navigation outcomes and qualified before Webots. Do not open C4/C5 until broader development shows both mechanism stability and a non-adverse safety pattern.

## Reproduction

- `python scripts/calibrate_cvc_p6_novelty.py`
- `python scripts/qualify_cvc_p6_offline.py`
- `python scripts/run_cvc_p6_webots.py --timeout 180`
- `python scripts/analyze_cvc_p6_development.py`
- `python scripts/plot_cvc_p6_traces.py`

Machine evidence is under `results/cvc_p6_calibration/`, `results/cvc_p6_offline_qualification/`, and `results/cvc_p6_webots/`.
