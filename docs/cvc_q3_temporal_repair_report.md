# CVC-Q3 Temporal Repair Report

Study: `cvc-q3-temporal-repair-v1`. Development-only terminal result: **CASE D — temporal repair fails the meaningful-frequency gate**. Q3 stopped after one frozen comparison; no outcome-driven repair, broader validation, ML, or C4/C5 Formal study was opened.

## Consolidated report-back

1. **Exact Q2 temporal failure.** Across 20 adaptive Q2 traces, only three episodes contained Safety Value. Their first events arrived 20, 146, and 216 steps after the adaptive packet (`0.640`, `4.672`, and `6.912 s`). One event arrived while the protected reserve physically remained but was scheduler-locked; two arrived after reserve exhaustion.
2. **ARM-to-value distribution.** The three supported delays were 67, 193, and 263 steps (`2.144`, `6.176`, `8.416 s`), with median 193 steps (`6.176 s`), range 67-263, and interquartile range 130-228 steps.
3. **Adaptive-spend-to-value distribution.** Delays were 20, 146, and 216 steps; median 146 (`4.672 s`), range 20-216, and interquartile range 83-181. Four consecutive event runs lasted 3, 10, 48, and 52 steps, so the failure was not one-step transience.
4. **Runtime latency profile.** The pre-outcome offline audit classified the problem as logical scheduling: conservative summed Q2 p95 `11.558 ms` versus the `32 ms` control period, with no component miss. In 9,360 prospective Webots cycles, mean/p95/max were: sender detector `1.804/7.824/27.686 ms`; HELD planner `0.973/1.556/16.595`; CURRENT planner `0.774/1.298/7.478`; Safety Value `0.070/0.123/1.447`; scheduler `0.016/0.023/1.082`. Each component had zero misses. The summed instrumented path was `7.169/20.390/52.586 ms` with 99/9,360 (`1.06%`) occasional overruns. This is an operational caveat, not Case E: value runs persist for at least three cycles and the Q2 failure spans tens to hundreds of cycles.
5. **Temporal-repair families tested.** Outcome-blind trace replay compared Q2's 47-step deadline, a 63-step latch under old eligibility, a one-step late eligible token, a 63-step bounded latch plus late token, and an episode-persistent latch plus late token.
6. **Failed/rejected variants.** Q2 baseline captured `0/3` supported opportunities; latch-only under the old reserve captured `1/3`. One-step late eligibility captured all three but lacked transient robustness. Episode-persistent latching captured all three but could retain stale value indefinitely. A routine initial qualification import-path error was fixed before any outcome. The first primary wrapper invocation used an erroneously short shell timeout; two completed U0 episodes were retained exactly and the unchanged runner resumed without replacement. No scientific parameter changed.
7. **Offline qualification.** Late-token variants captured 3/3 supported opportunities, yielded three Safety-Value packets, lost zero supported episodes, represented both A0/A1, tied value and fallback at 3/6 risk-armed episodes, retained step-311 reserve, and reconciled exactly three packets. The replay was explicitly trace-conditional because changed sends can change later HELD/CURRENT events and trajectories.
8. **Chosen scheduler.** `bounded_latch_late_token`: a 63-step bounded Safety Value latch, one protected adaptive token, step-295 late fallback, and step-311 final reserve.
9. **Outcome-independent selection.** The choice used only Q2 ARM/value/packet timing, event-run duration, known horizon coverage, causal eligibility, budget feasibility, interpretability, and runtime. Collision, clearance, danger labels, completion, progress, future trajectory, and A1-vs-A0 navigation outcomes were unread during selection.
10. **Frozen parameters.** Risk threshold `0.14`; latch validity `63` steps (`2.016 s`); fallback step `295` (`9.440 s`); reserve step `311` (`9.952 s`); startup step `0`; U0 schedule `[0,156,311]`; JPEG quality `45`.
11. **Latch semantics.** Any unchanged Q2 Safety Value event activates pending state before or after ARM. The latest event refreshes expiration; a stronger lower-numbered priority updates the stored reason. Validity is inclusive through 63 steps after the latest event. ARM plus pending value sends immediately and consumes/reset the one-shot latch. Expiration clears without sending. Events after consumption are diagnostic only. In the two immediate send traces, the raw snapshot records `consumed_this_step`; activation is causally established by the simultaneous value event and `safety_value_latch:*` send reason.
12. **Fallback rule.** If the adaptive token remains, step 295 sends `armed_late_fallback` or `unarmed_late_fallback`. Fallback is never removed and cannot occur earlier.
13. **Reserve rule.** A separate final packet is locked until step 311 and cannot be consumed by ARM, value, latch, or fallback. Every adaptive episode exhausted exactly at step 311.
14. **Protocol/config hashes.** Config SHA-256 `55d6b3352e64df3f4363acd7d2ab8b9940c72f4abb380239638a11ce1e28ac93`; protocol `a218dbee97e6c37787711b4912de1afd9a87e61cf5cd073fab0c32c4b3aca9a1`; pre-outcome readiness manifest `d05c0ca5332c4e676dbcf0058d789fb03da3837206988badd394e833520a1673`.
15. **Exact packet budget.** Every episode transmitted exactly three complete 24,000-byte packets, or 72,000 wire bytes. Across ten episodes/policy, content/metadata/padding were U0 `54,677/5,509/659,814`, A0 `53,841/5,458/660,701`, and A1 identical. Every decomposition and sender-mirror check passed.
16. **Episode count.** Exactly 30 runs: ten frozen Q1 support cells each under U0, A0, and A1. There were no replacements or scenario changes.
17. **Safety-Value-triggered packets.** Two: A0 and A1 straight approach, both at step 235. Each was priority-1 safety-class deterioration and transmitted on the event step.
18. **Fallback/deadline packets.** No deadline packets. There were four armed late fallbacks and fourteen unarmed late fallbacks; each A0/A1 policy had one value, two armed fallback, and seven unarmed fallback packets.
19. **Fraction genuinely value-controlled.** `2/20 = 10%` of adaptive packets and `2/6 = 33.3%` of risk-armed episodes. Both are below the frozen `3/20` minimum, and fallback dominates risk-armed episodes `4/6 = 66.7%`; the prospective mechanism gate fails.
20. **ARM-to-Safety-Value delay.** A0 straight approach armed at step 42 and valued at 235: 193 steps (`6.176 s`). A1 armed at 15 and valued at 235: 220 steps (`7.040 s`). Median `206.5` steps (`6.608 s`).
21. **Safety-Value-to-SPEND delay.** Both delays were exactly zero steps. Every observed Q3 eligible value episode was captured immediately (`2/2`).
22. **Image age.** Both value sends refreshed a `7,520 ms`-old HELD image to age zero. Late fallback ages were `9,440 ms`. U0's middle packet age was `4,992 ms`. A0/A1 adaptive age mean/median/range was `9,248/9,440/7,520-9,440 ms`.
23. **Safe-set/action changes after value send.** In both value sends, hard-safe candidates contracted `13 -> 9`; HELD selected `v+0.045_w+1.600`, CURRENT and the actual receiver selected `v+0.000_w+1.600`. Wheel commands changed from `[0.17,4.33]` to `[-2.08,2.08] rad/s`, proving decoded-image update, safe-plan change, and control actuation. Clearance was `0.147698 m` at send and the next-2 s minimum was `0.147449 m`, without contact.
24. **Collisions.** U0/A0/A1 each had `0/10`.
25. **Near-danger.** U0/A0/A1 each had `3/10`, using the unchanged no-contact clearance `<=0.12 m` definition.
26. **Safe episodes.** U0/A0/A1 each had `7/10`; danger counts were tied at three.
27. **Minimum-clearance distributions.** U0 min/Q1/median/Q3/mean = `0.058189/0.110134/0.140006/0.319214/0.223226 m`; A0 and A1 each = `0.102716/0.122029/0.142174/0.319214/0.244539 m`. The physical distributions are descriptively tied under the frozen rule; this cannot rescue a failed mechanism gate.
28. **Task completion/progress.** Successes were U0/A0/A1 `9/8/8`. Mean progress was `0.647805/0.591111/0.591111 m`; medians `0.657074/0.578738/0.578738 m`. Mean completion times among completed episodes were `7.484/7.676/7.676 s`; mean path efficiencies `0.935875/0.910267/0.910267`.
29. **Representative causal traces.** The A1 straight trace shows ARM at step 15, no immediate send, continued waiting, priority-1 value at 235, same-step adaptive packet, receiver refresh, safe-set contraction, movement-to-stop-turn action change, wheel-command change, and physical clearance. The A0 chain is identical except ARM occurs at step 42. A1 narrow passage shows ARM at 113 but no value and armed fallback at 295; the distractor shows no ARM/value and mandatory fallback at 295. No Q3 value occurred after fallback; the historical Q2 late examples remain preserved in the diagnosis.
30. **Is `SafetyValue -> SEND` established?** Locally, yes: two exact same-step causal sends occurred. At the frozen meaningful-frequency gate, no: only 10% of adaptive packets were controlled by value and fallback remained dominant among armed episodes.
31. **Does predictive R1 ARM add engineering safety value?** No. R1 armed earlier in three paired cells, but A0 and A1 had identical send schedules in all ten cells and identical safety/task outcomes. Earlier readiness did not create a distinct useful spend.
32. **Final classification.** **CASE D — temporal repair fails.** The repair proves local actuation but not the preregistered meaningful frequency; trace-conditional Q2 support did not prospectively persist, notably in the narrow passage.
33. **Broader validation justified?** No. The mechanism fails on the original support set.
34. **ML justified?** No. The remaining problem is sparse, schedule-dependent decision-divergence support, not evidence for a learned scheduler.
35. **C4/C5 Formal justified?** No. Formal remains closed.
36. **Recommended next experiment.** A separately frozen, mechanism-only schedule-robust Safety Value support study: retain the Q1 planner, R0/R1, value definition, codec, and temporal scheduler; qualify new outcome-independent cells for HELD/CURRENT decision divergence that persists under late-token schedules before any navigation comparison. Do not tune Q3 timing and do not train ML.

## Evidence and figure map

- Exact diagnosis: `results/cvc_q3_temporal_diagnosis/diagnosis.json`
- Offline family comparison: `results/cvc_q3_offline_qualification/qualification.json`
- Runtime audit: `results/cvc_q3_runtime_profile/profile.json`
- Pre-outcome seal: `results/cvc_q3_readiness/manifest.json`
- Primary matrix/traces: `results/cvc_q3_webots/`
- Strict terminal analysis/table: `results/cvc_q3_analysis/analysis.json`, `episode_summary.csv`
- Timing-support dot plot: `q3_q2_timing_diagnosis.png`
- Candidate and packet-cause bars: `q3_offline_candidate_comparison.png`, `q3_primary_packet_causes.png`
- Aligned mechanism/failure traces: `q3_full_causal_trace_a1_straight.png`, `q3_fallback_examples.png`
- Physical and runtime checks: `q3_safety_outcomes.png`, `q3_runtime_profile.png`

All figures use static reproducible Matplotlib output, a two-root-plus-neutral palette, and line/hatch distinctions; all seven exported files were inspected at their final size. Frozen Q1/Q2 and protected M9/P7 hashes remain unchanged. No commit or push occurred.
