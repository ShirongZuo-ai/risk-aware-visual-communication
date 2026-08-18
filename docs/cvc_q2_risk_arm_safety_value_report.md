# CVC-Q2 Risk-ARM + Safety-Decision-Value-SPEND Report

Study: `cvc-q2-risk-arm-safety-value-spend-v1`. Status: development-only, terminal `CASE D`. Q2 stopped after one frozen comparison; no outcome-driven repair, broader validation, ML, or Formal study was opened.

## Required report-back

1. **Frozen protocol.** Q2 reused the Q1 v2 local planner, calibrated vision, causal obstacle memory, ten-cell support grid, seeds, goals, 10 s duration, and physical labels unchanged. U0/A0/A1 were run once on all ten paired cells.
2. **Protocol/config hashes.** The pre-outcome readiness manifest SHA-256 is `d5acb4b3b1a9857fe0c0154ee69e3f9a999917a417271e4a059bf6cecba67ca7`. Within it, protocol is `90bda0f146f3c4ce27c384533d920611ada4b835651f506ef6bf9ebdcc754e52` and config is `8d6366e7021731a7266eb09ca275780717f9dbf9264941849646fbef896a06ad`.
3. **Exact Safety Decision Value definition.** HELD and hypothetical decoded CURRENT frames traverse the same frozen perception, causal-memory preview, and planner. A trigger requires one of the three ordered events below; an efficiency-only action change is explicitly insufficient.
4. **Event hierarchy.** Priority 1: safety-class deterioration or loss of all moving safe actions. Priority 2: CURRENT removes the HELD-selected action from the hard-safe set and changes the selected action. Priority 3: CURRENT removes at least one-third of HELD hard-safe actions and reduces the same HELD-selected candidate's conservative margin by at least 0.01 m.
5. **Numerical tolerances.** Action/numeric equivalence uses `1e-9`; safe-set contraction uses `1/3`; matched margin deterioration uses `0.01 m`. Infinite margins are treated categorically, not averaged as finite values.
6. **ARM rule.** A0 crosses from previous R0 `<0.14` to current R0 `>=0.14`; A1 applies the identical crossing to causal R1. ARM only changes `NORMAL -> ARMED`; it never transmits by itself.
7. **Deadline.** An armed policy may wait 47 steps (1.504 s at 32 ms/step) for Safety Value, then spends the adaptive packet at the ARM deadline.
8. **Reserve.** Adaptive policies retain a protected third packet at step 249. Unarmed fallback is step 248. There is no future debt.
9. **Packet budget.** Three exact packets of 24,000 wire bytes each, or exactly 72,000 bytes/episode. U0 sends at steps `[0,156,311]`; A0/A1 send startup, one adaptive packet, and reserve.
10. **Offline qualification.** All eight outcome-blind gates passed using frozen Q1 U0-6 planner traces and preserved P6 causal sender-risk traces. No evaluator field or navigation outcome was used.
11. **Distractor qualification.** The frozen visual-distractor trace produced zero Safety Value events. In Webots, A0 and A1 remained unarmed, spent only at fallback step 248, retained identical 15-action HELD/CURRENT safe sets, and stayed physically safe (`0.711605 m` minimum clearance).
12. **Narrow-passage qualification.** Offline Q1 traces produced 57 value events beginning at step 255. In the primary run, A0 armed at 193 and deadline-spent at 240; its first actual value event was step 260, too late to cause transmission. A1 armed at 113 and deadline-spent at 160 but produced no value event on its changed trajectory.
13. **Episode counts.** Exactly 30 primary runs: 10 U0, 10 A0, and 10 A1; each policy used each frozen cell once.
14. **Exact charged bytes.** Every episode charged exactly 72,000 bytes and three packets. All 30 byte reconciliations and all sender-mirror/receiver checks passed. Across the ten episodes, content/metadata/padding bytes summed to U0 `54,677 / 5,509 / 659,814`, A0 `54,180 / 5,478 / 660,342`, and A1 `54,118 / 5,490 / 660,392`.
15. **ARM timing.** Paired R1 leads occurred in three cells: straight approach `42 -> 15` (27 steps), narrow passage `193 -> 113` (80), and subtle offset `6 -> 1` (5). Other cells were unarmed.
16. **Safety Decision Value timing.** There were 113 triggered timesteps: A0 straight approach 58, A0 narrow passage 52, and A1 straight approach 3. All began after that episode's adaptive packet was spent.
17. **SPEND timing.** A0 adaptive spends were steps 89, 240, and 53 for the three armed cells; A1 spends were 62, 160, and 48. All other adaptive spends occurred at fallback step 248. No adaptive spend was caused by Safety Value.
18. **Deadline/fallback use.** Per adaptive policy: 3/10 deadline and 7/10 unarmed fallback. Combined, deadline/fallback caused 20/20 adaptive packets (`100%`), violating the frozen maximum of 75%.
19. **Safe-set changes.** Across episode-step summaries, U0/A0/A1 recorded 224/561/387 HELD-vs-CURRENT safe-set-change steps. Within adaptive value evaluation, A0 had 100 large-contraction-plus-margin events and A1 had 3.
20. **Selected-action changes.** U0/A0/A1 recorded 379/848/664 action-change steps. Safety-value-qualified removal of the HELD action occurred on 100 A0 and 3 A1 steps, but never while an adaptive token was still spendable.
21. **Safety-class changes.** U0/A0/A1 recorded 35/109/3 safety-class-deterioration steps. They were diagnostics, not causes of any transmitted packet.
22. **Conservative-margin changes.** The priority-3 joint condition occurred on 100 A0 and 3 A1 steps. Its `0.01 m` threshold remained frozen and was not retuned.
23. **Collision results.** U0 `0/10`; A0 `2/10`; A1 `0/10`. A1 removed the two A0 contacts, but this cannot validate the intended value-triggered mechanism because neither A1 packet was value-triggered.
24. **Near-danger results.** U0 `3/10`; A0 `3/10`; A1 `5/10`, where near means no contact and episode minimum clearance `<=0.12 m`.
25. **Safe results.** U0 `7/10`; A0 `5/10`; A1 `5/10`. Total danger counts (collision + near) were U0/A0/A1 `3/5/5`.
26. **Minimum-clearance distributions.** U0 min/Q1/median/Q3/mean = `0.058189/0.110134/0.140006/0.319214/0.223226 m`; A0 = `-0.001639/0.092505/0.124700/0.319214/0.209560 m`; A1 = `0.014802/0.095578/0.124700/0.319214/0.221057 m`.
27. **Task completion.** U0/A0/A1 completed `9/7/9` tasks. The frozen task guardrail passed for A1.
28. **Task progress.** Mean progress was U0/A0/A1 `0.647805/0.645682/0.665350 m`; medians were `0.657074/0.653635/0.658970 m`. Mean path efficiency was `0.935875/0.940355/0.952910`.
29. **Representative true Safety Value trace.** A0 straight approach reached a priority-1, future-danger-associated event by step 243: HELD selected `v+0.045_w-1.600`, CURRENT selected stop-turn `v+0.000_w-1.600`, safe counts changed `11 -> 10`, and the following 2 s included contact. Its deadline packet had already been spent at step 89.
30. **Representative false-positive/distractor trace.** A0 and A1 distractor packets were unarmed fallback sends at step 248 with R0=R1=0, no value event, 7.936 s held-image age, and future clearance `0.713307 m`. This is a correctly rejected visual novelty but still a non-value communication spend.
31. **R1 -> ARM -> Safety Value -> SPEND -> control -> physical safety.** No complete example exists. R1 produced earlier ARM in three cells and A1 changed downstream trajectories, but SPEND always occurred at a deadline before value or at fallback. The causal chain therefore breaks at `Safety Value -> SPEND`.
32. **Failed/rejected pre-freeze variants.** Two engineering-only issues were fixed before freeze: the first offline qualification invocation lacked repository-root import setup; the next repeatedly reloaded traces and timed out. The smoke runner initially expected a nonexistent `.wire_bytes` packet attribute and was corrected to `len(payload)`. None exposed Q2 primary outcomes or changed scientific thresholds, cells, planner, or criteria.
33. **Is Safety Decision Value validated?** No. Its offline semantics discriminated the narrow passage from the distractor, but it did not causally actuate a single packet in the primary policy.
34. **Does predictive ARM add engineering safety value?** Not under the frozen criterion. It armed earlier in three cells and coincided with removal of A0 contacts, but created no useful value-triggered opportunity and produced five danger cells versus U0's three.
35. **Final classification.** `CASE D — Safety Decision Value trigger is inadequate`, because the frozen mechanism gate failed before safety outcomes could rescue the policy.
36. **Broader development validation justified?** No. The integration mechanism must first work on the frozen support cells.
37. **ML justified?** No. The observed failure is a transparent timing/token-lifetime mismatch, not evidence that the value boundary needs nonlinear learning.
38. **C4/C5 Formal justified?** No. Formal remains closed.
39. **Recommended next experiment.** A protocol-only temporal repair on the frozen traces: keep Q1 and all risk/value thresholds fixed, but evaluate a value-triggerable protected reserve or explicit post-ARM persistence window so a late Safety Value event can still cause a packet. Freeze that hypothesis before any new Webots outcomes.

## Evidence index

- Pre-outcome seal: `results/cvc_q2_readiness/manifest.json`
- Offline qualification: `results/cvc_q2_offline_qualification/qualification.json`
- Primary matrix and per-step traces: `results/cvc_q2_webots/`
- Strict terminal analysis and episode table: `results/cvc_q2_analysis/analysis.json`, `results/cvc_q2_analysis/episode_summary.csv`
- Figures: `results/cvc_q2_analysis/figures/q2_safety_outcomes.png`, `q2_narrow_passage_causal_timing.png`, `q2_adaptive_packet_causes.png`, and `q2_distractor_negative_control.png`

The frozen Q1, M9-A, M9-B, and P7 evidence hashes were rechecked by artifact tests. No historical evidence was changed, no commit was created, and nothing was pushed.
