# CVC-P3 risk-to-allocation actuation qualification

Status: development only. CVC-P2 remains an immutable negative result. No C4/C5 Formal study was opened.

## P2 collapse diagnosis

All 42 P2 traces were reprojected to time, sender R0/R1, and communication fields only. Every trace contains different R0/R1 values that were quantized to the same temporal and quality actions; none was functionally identical at the allocator input.

P2 had two 36,000-byte packets. The mandatory startup frame left one packet token. Adaptive T/TS used a 218-step uniform gap and a 72-step urgency eligibility delay. Earlier R1 crossings therefore waited until the same eligibility step as R0, or both signals reached forced end reconciliation. S timing ignored risk. At shared send steps, the binary 0.16 quality threshold matched and the causal image-component ROI could not move as a function of risk. There was no separate debounce.

Across the 28 P2 traces where both signals crossed 0.16, R1 lead was 10--40 steps, median 23. The exact trace-level explanation is in `results/cvc_p3_offline_qualification/p2_trace_diagnosis.json`.

## Outcome-blind qualification gate

The gate and candidate grid were frozen in `config/cvc_p3_development.json` before P3 downstream fields were read. Selection used only causal risk, time/history, and fixed bytes. It did not reference evaluator clearance/geometry, collision, success, perception, control, or which policy later performed better.

A candidate had to support finite positive prediction lead on at least half of the 18 distinct causal streams; convert every supported positive trigger lead while tokens were available; have positive median communication lead and median conversion efficiency at least 0.8; reconcile exactly to 72,000 bytes; and pass at two or more packet granularities. This is a mechanistic identifiability gate, not a safety-performance gate.

## Prediction lead and packet granularity

The 42 P2 files reduce to 18 distinct exact R0/R1 streams.

| Threshold | Both cross | Positive | Median steps | Range steps |
|---:|---:|---:|---:|---:|
| 0.12 | 18 | 12 | 25.0 | 0--33 |
| 0.14 | 18 | 18 | 26.0 | 2--51 |
| 0.16 | 14 | 14 | 23.5 | 10--40 |
| 0.18 | 14 | 14 | 23.5 | 6--37 |
| 0.20 | 12 | 12 | 24.5 | 13--42 |

The 72,000-byte episode budget was divided as 3 x 24,000, 4 x 18,000, and 6 x 12,000. Threshold 0.14 passed at all three granularities: schedules differed on 18/18 streams, median first adaptive lead was 26 steps, range 2--51, and conversion efficiency was exactly 1.0 on all 18.

P2's 48-tile codec cannot represent these smaller opportunities: on a representative accepted 160x120 frame its quality-1 content was 31,181 bytes before outer metadata. P3 therefore uses one complete 160x120 JPEG inside a deterministic authenticated envelope, identically for U0/A0/A1. It is not a nominal-token surrogate.

## Allocator variants

- Threshold: all five frozen thresholds passed at all three granularities; 0.14 maximized coverage and was selected by the frozen simplicity/coverage rule.
- Derivative/rise: 0/9 packetization/spec candidates passed.
- Integral: 9/9 passed, but had lower median communication leads (1--3 steps) and was not selected.
- Hazard bucket: 6/6 passed, but was more complex than the equally covering threshold rule.

The selected mechanism is threshold 0.14 with three 24,000-byte packets. A startup packet is mandatory; remaining tokens are available without future debt; unused tokens reconcile at the end. The same code and threshold are used for A0 and A1. Only the scalar risk input changes.

## Temporal and spatial actionability

Temporal actionability is qualified. At threshold 0.14, R1 caused earlier real frame transmission on every outcome-blind source stream.

Spatial actionability is not qualified. Under shared uniform times, the two-level risk quality state differed on 0/18 streams at three packets, 0/18 at four packets, and 2/18 at six packets (three individual decisions). The image-derived ROI itself is the same at a shared time. P3 therefore tested temporal allocation with fixed JPEG quality 45 and made no spatial-benefit claim.

## Webots development result

The qualified mechanism was run on the six preserved P2 scenarios as independent U0/A0/A1 executions: 18 episodes total. Every episode transmitted three actual 24,000-byte packets and exactly 72,000 wire bytes. Across 54 packets, JPEG content was 1,157--2,085 bytes, metadata plus prefix was 179--197 bytes, and deterministic padding was 21,734--22,661 bytes. Every component sum equals the logged wire bytes.

| Policy | Collisions | Task successes | Worst clearance (m) | Mean minimum clearance (m) | Mean image age (ms) |
|---|---:|---:|---:|---:|---:|
| U0 | 0/6 | 3/6 | 0.095586 | 0.362944 | 3464.1 |
| A0 | 2/6 | 1/6 | -0.002043 | 0.290956 | 5984.9 |
| A1 | 3/6 | 2/6 | -0.002244 | 0.082025 | 6446.9 |

A0/A1 schedules differ in 6/6 scenarios. In the five pairs with finite triggers for both policies, first adaptive communication lead is 8--51 steps (0.256--1.632 s), median 26 steps (0.832 s), and conversion efficiency is 1.0. In `right_offset`, A0 never risk-triggers and reconciles at steps 435/436, while A1 triggers at 16/42; the finite lead ratio is undefined.

Earlier A1 packets immediately cause decoded-perception, wheel-command, and trajectory divergence in all six scenarios, in that causal order. Mean pairwise perception-difference fraction is 0.9836, mean wheel-command divergence is 0.3668 rad/s, and mean maximum trajectory divergence is 0.5203 m.

The mechanism is nevertheless adverse overall. Repeated threshold crossings often spend A1's two post-startup tokens by step 5--20. A1 then has older held imagery later in five of six scenarios. A1 loses minimum clearance in five pairs and wins one; it has one more collision than A0. The one positive pair is `late_appearance`, where A1 changes A0's collision/failure into a collision-free task success, but this isolated result does not offset the suite-level adverse pattern.

## Conclusion and stop decision

Predictive risk is **actionable but has not demonstrated task value**. P3 proves that P2's prediction-to-action loss was allocator-induced rather than intrinsic. It also shows that naively converting every early warning can exhaust a fixed episode budget too soon and make later observation staleness worse.

C4/C5 confirmation is not justified. No confirmatory artifact was created. The next experiment, if separately authorized, should remain development-only and test a single-spend or reserved-token threshold rule that preserves one late packet, with its budget-retention rule frozen from risk/time alone. It must not alter scenarios based on A1 outcomes.

## Reproduction

- Offline qualification: `python scripts/qualify_cvc_p3_allocators.py`
- Webots matrix: `python scripts/run_cvc_p3_webots.py`
- Post-gate analysis: `python scripts/analyze_cvc_p3_development.py`
- Machine evidence: `results/cvc_p3_offline_qualification/` and `results/cvc_p3_webots/`
