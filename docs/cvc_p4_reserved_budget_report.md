# CVC-P4 reserved-budget predictive actuation

Status: development only. CVC-P2 and CVC-P3 remain unchanged. No C4/C5 Formal study was opened.

## Outcome-blind reserve qualification

Eight frozen reserve candidates were evaluated on the 18 distinct causal R0/R1 development streams using only risk, time, token state, implied image age, and exact bytes:

- fixed late reserve at 0.50, 0.667, and 0.75 of the horizon;
- release-time reserve at 0.50/0.75 and 0.667/0.875 release/fallback fractions;
- minimum separation of 128 and 192 steps;
- fixed final refresh.

The gate required 100% positive-lead conversion, 100% schedule differences, exact 72,000-byte equality, and no complete budget exhaustion before half the horizon. Selection first preferred a shared risk-independent reserve so A0/A1 differed only in the middle packet, then minimized worst implied image age.

The selected `fixed_late_050` rule sends startup at step 0, exactly one threshold-0.14 adaptive packet, and a protected reserve at step 218. If R0/R1 never crosses, the middle packet falls back at step 217. U0 uses fixed steps 0/109/218. Offline schedules differ on 18/18 streams; median prediction and communication lead are 26 steps and conversion is 1.0. All policies exhaust at step 218. Worst implied image age is 218 steps/6,976 ms, the lowest passing value.

The 128/192-step separation variants fail the exhaustion-time gate. Later fixed/release/final variants pass some or all gates but have worse implied maximum age or allow R0/R1 reserve times to differ.

## Exact Webots execution

The unchanged six P3 scenarios were run independently under U0/A0/A1: 18 episodes. Every episode sends three complete quality-45 JPEG packets of exactly 24,000 bytes, for exactly 72,000 wire bytes including JPEG content, metadata, and padding. Every trace retains one reserve token after the middle packet and sends/exhausts at step 218.

Exact schedules:

| Scenario | U0 | A0 | A1 | A1 lead |
|---|---|---|---|---:|
| angled_toward | 0/109/218 | 0/28/218 | 0/2/218 | 26 |
| center_large | 0/109/218 | 0/50/218 | 0/6/218 | 44 |
| late_appearance | 0/109/218 | 0/9/218 | 0/1/218 | 8 |
| left_offset | 0/109/218 | 0/35/218 | 0/11/218 | 24 |
| right_offset | 0/109/218 | 0/217/218 | 0/16/218 | 201* |
| two_component | 0/109/218 | 0/58/218 | 0/7/218 | 51 |

`right_offset` uses A0's deadline fallback because actual closed-loop R0 never crosses; its prediction-lead ratio is undefined. For the other five pairs, median finite lead is 26 steps and conversion is 1.0. Including the fallback pair, median communication lead is 35 steps.

## Image age and mechanism

P3 premature complete exhaustion is fixed in 6/6 pairs. Nevertheless, earlier A1 middle packets create a longer interval until the common step-218 refresh. A1 has lower pre-danger age in only one pair, ties once, and is older in four.

| Policy | Overall mean age | Pre-danger mean age | Maximum pre-danger age |
|---|---:|---:|---:|
| U0 | 2,610.0 ms | 2,393.2 ms | 6,976 ms |
| A0 | 3,095.5 ms | 3,104.0 ms | 6,976 ms |
| A1 | 3,371.3 ms | 3,692.9 ms | 6,976 ms |

The post-hoc pre-danger window is the 63 steps (~2 s) ending at first clearance below 0.12 m; when no such event occurs, it ends at minimum clearance. Only A1 `two_component` reaches the danger threshold, with image age 1.6 s at onset.

The initial avoidance-command diagnostic is non-discriminating because every decoded startup command already differs from cruise. It is retained, not hidden. A secondary first material command-change diagnostic is recorded in the machine report.

A0/A1 decoded perception differs over a mean 0.8166 of steps, mean wheel-command divergence is 1.3922 rad/s, and mean maximum trajectory divergence is 0.9528 m. Earlier transmission therefore remains causally effective at the receiver/controller boundary.

## Physical results

| Policy | Collisions | Task successes | Worst clearance | Mean episode minimum | Mean clearance |
|---|---:|---:|---:|---:|---:|
| U0 | 0/6 | 1/6 | 0.252038 m | 0.409184 m | 0.580075 m |
| A0 | 0/6 | 1/6 | 0.189703 m | 0.394201 m | 0.570481 m |
| A1 | 0/6 | 4/6 | 0.092103 m | 0.248836 m | 0.408473 m |

A1 gains task completion but loses minimum clearance in 4/6 pairs, lowers mean clearance substantially, and produces the only danger-threshold episode. This is a mixed completion/safety trade-off, not a stable safety advantage.

## Decision

P4 is **Case C: predictive communication timing may be poorly aligned with task value**. The budget-starvation confound is removed, but earlier R1 communication still does not improve safety and usually worsens the relevant image-age window. C4/C5 confirmation is not justified.

The next experiment should not be another threshold/reserve sweep. A development-only mechanism study should test whether an early risk-triggered frame contains new receiver-relevant visual/control information compared with the held frame. Freeze causal visual novelty and command-sensitivity diagnostics first; only consider another policy when prediction lead coincides with useful observation change.

## Reproduction

- `python scripts/qualify_cvc_p4_reserve.py`
- `python scripts/run_cvc_p4_webots.py`
- `python scripts/analyze_cvc_p4_development.py`
- Machine evidence: `results/cvc_p4_offline_qualification/` and `results/cvc_p4_webots/`
