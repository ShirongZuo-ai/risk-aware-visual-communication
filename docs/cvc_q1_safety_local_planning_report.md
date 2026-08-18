# CVC-Q1 Safety-Aware Local Planning and Physical-Support Qualification

Status: complete, development-only, `CASE A` (2026-08-15). This milestone did not run A0/A1, implement a predictive communication allocator, open C4/C5 Formal, or modify M9/P6/P7 evidence.

## Consolidated 29-item report

1. **Old centering root cause.** The P2-P7 controller converted red-component bearing directly into steering toward the component. Fresher obstacle views could improve progress while reducing clearance because there were no path alternatives, hard clearance rejection, or semantic avoidance rule.

2. **Planner architecture.** Decoded RGB is detected, calibrated into robot-local obstacles, transformed through causal command odometry/history, retained in causal static-obstacle memory, and supplied with local goal bearing to a receding-horizon command rollout. Hidden Webots geometry enters only the evaluator after actuation.

3. **Candidate action grid.** Fifteen commands: linear `{0, 0.045, 0.08}` m/s crossed with angular `{-1.6, -0.8, 0, 0.8, 1.6}` rad/s.

4. **Horizon.** Each command uses the M2-compatible predictor for 1.5 s at 0.1 s increments. Only its first control action is executed.

5. **Visual obstacle representation.** Red-component bearing and bbox height become local circular obstacles with known radius 0.04 m and calibrated uncertainty. A 125-step causal memory prevents forgetting static obstacles when avoidance turns them out of view. Runtime inputs exclude simulator truth.

6. **Range calibration.** The outcome-blind model is `range_m = 14.9909244777 / bbox_height_px + 0.0490508719`. Ten placements span 0.18-0.84 m. Bias is approximately `0`, MAE `0.01203 m`, RMSE `0.01669 m`, and worst error `0.04541 m` at 0.18 m. All per-distance errors are preserved. The bound is `0.05541 m` (worst error plus 0.01 m); navigation outcomes were not used.

7. **Safety feasibility.** Clearance subtracts robot radius 0.037 m, obstacle radius, and range uncertainty. Below 0.025 m is hard-unsafe; at least 0.075 m is preferred-safe. Within estimated range 0.35 m, linear speed is capped at 0.045 m/s.

8. **Goal-efficiency rule.** Among moving preferred-safe candidates, select maximum goal progress with deterministic tie-breaks. If none exist, select the hard-safe candidate with maximum conservative margin before progress. Progress cannot compensate for hard-unsafe clearance.

9. **Fallback.** If no candidate is hard-safe, issue deterministic stop (`v=0,w=0`).

10. **Fresh/full-vision fixtures.** Preserved v1 failed center-near collision, clearance, and slowdown gates. V2 passed all seven gates over eight fixtures: 8/8 contact-free, correct directions, near slowdown, obstacle-free progress, adequate clearance, determinism, and boundary isolation. Obstacle fixture clearances were `0.0945-0.2331 m`; five of eight met the separate 0.5 m success rule. Each used 312 exact 24,000-byte packets.

11. **Avoidance rather than centering.** A left obstacle first produced `w=-0.8 rad/s` (right avoidance) at step 127; a right obstacle produced `w=+0.8 rad/s` at step 126. Turn-away did not turn back. Center-near obeyed the 0.045 m/s cap and remained contact-free.

12. **Physical-support grid.** Ten deterministic cells cover straight approach, shallow conflict, strong conflict, late reveal, obstacle after turn, narrow passage, subtle approach, safe turn-away, red nonphysical distractor plus blue physical anchor, and command transition. Seeds are 982001-982010.

13. **Frozen manifest.** All 10 cells passed pre-freeze HIGH feasibility: no contact, clearance >=0.025 m, progress >=0.35 m. The 0.5 m success rule was not a freeze requirement. Pre-U0 manifest SHA-256: `7685b3059509b391a9ae9e11ebcd840458f1c8a22e0dbe2e7f00de79349ed5f9`.

14. **HIGH results.** HIGH produced 0 collision, 3 near, 7 safe; suite minimum `0.09300 m`, median episode minimum `0.14603 m`, mean episode minimum `0.22983 m`, 9/10 successes, and mean progress `0.65916 m`.

15. **U0 exact-wire sweep.** Seventy neutral episodes used 10 cells x `{1,2,3,6,12,24,48}` packets. Each packet is exactly 24,000 bytes. All content + metadata + padding reconciles; no A0/A1 ran.

| condition | bytes | collision | near | safe | min clearance (m) | success | mean progress (m) |
|---|---:|---:|---:|---:|---:|---:|---:|
| HIGH | 7,488,000 | 0 | 3 | 7 | 0.09300 | 9/10 | 0.65916 |
| U0-1 | 24,000 | 0 | 4 | 6 | 0.09556 | 8/10 | 0.58712 |
| U0-2 | 48,000 | 0 | 4 | 6 | 0.09523 | 8/10 | 0.58764 |
| U0-3 | 72,000 | 0 | 3 | 7 | 0.05819 | 9/10 | 0.64780 |
| U0-6 | 144,000 | 0 | 5 | 5 | 0.00123 | 10/10 | 0.66899 |
| U0-12 | 288,000 | 0 | 1 | 9 | 0.11416 | 8/10 | 0.63672 |
| U0-24 | 576,000 | 0 | 0 | 10 | 0.12309 | 8/10 | 0.63178 |
| U0-48 | 1,152,000 | 0 | 2 | 8 | 0.10070 | 9/10 | 0.63217 |

16. **Transition regime.** The descriptive band is 3-6 packets: both contain near support; U0-6 has the greatest near count and global 1.23 mm minimum. It is non-monotone and is not a fitted threshold or formal effect.

17. **Collision/near/safe support.** Across U0: 0 collision, 19 near, 51 safe. Frozen labels are bilateral contact; no-contact clearance <=0.12 m; and no-contact clearance >0.12 m. The 1.23 mm case is near, not collision.

18. **Minimum clearance.** Narrow passage has U0 span `0.13069 m`, minimum `0.00123 m`; strong-right has span `0.08651 m`, minimum `0.05819 m`. Three insensitive cells remain retained.

19. **Task success/progress.** U0 success is 8/10 to 10/10; mean progress is `0.58712-0.66899 m`. Neither is monotone and neither substitutes for physical safety.

20. **Safe-set changes.** HELD/CURRENT safe sets differ on 28.85%, 28.85%, 7.18%, 4.13%, 2.37%, 2.37%, and 1.28% of decisions for 1, 2, 3, 6, 12, 24, and 48 packets.

21. **Action changes.** Selected-action rates are 38.65%, 38.65%, 12.15%, 6.67%, 4.23%, 4.13%, and 2.95%. Safety-class changes peak at 1.76% for U0-6.

22. **Margin changes.** U0-6 has 1,502 finite and 1,618 bounded/unbounded comparisons; finite mean absolute selected-margin change is `0.00786 m`. Unbounded obstacle-free margins are categorical and excluded from finite means.

23. **High safety-information-value example.** Narrow-passage U0-6 steps 275-277: HELD is obstacle-free and selects `v=0.08,w=-0.8`; CURRENT reveals a close obstacle, removes all ten moving actions, selects stop/turn `v=0,w=+1.6`, and changes preferred-safe to hard-safe. Evaluator-only next-2 s clearance reaches `0.00123 m`.

24. **Novel but safety-irrelevant example.** In the distractor cell, held/current obstacle representations change while straight action, safe set, and safety class do not; retained examples keep future 2 s clearance >=`0.895 m`.

25. **Measurability.** Safety Information Value is measurable as separate action, safe-set, safety-class, bounded-margin, and goal-efficient-safe-path changes. Q1 does not collapse them into an allocator score.

26. **Failures retained.** Preserved black-camera P1 evidence, centering negative evidence, Q1 v1 failure, codec metadata startup rejection, path failure, and timeout/orphan attempts. Q1 v2 repaired only identified pre-freeze planner/memory defects. Insensitive cells and the fresh strong-right task-success miss remain.

27. **Classification.** `CASE A - AVOIDANCE + PHYSICAL SUPPORT QUALIFIED`, bounded to this deterministic development suite. There is no collision evidence, monotone dose-response, causal allocator comparison, or Formal claim.

28. **Readiness.** Ready to *design* Risk-ARM + Safety-Decision-Value-SPEND. Q1 does not authorize implementation or evaluation.

29. **Next experiment.** Freeze a separate development protocol holding Q1 task identities fixed. Use R1 only to ARM and spend a reserved exact-byte packet only on causal safe-decision change. Compare exact-byte neutral and nonpredictive controls in the 3-6-packet band, retain the non-monotone grid, and preregister support/stop rules.

## Evidence and verification

- Machine analysis: `results/cvc_q1_analysis/analysis.json`; exact budget table: `budget_summary.csv`.
- Three figures under `results/cvc_q1_analysis/figures/` were visually inspected.
- 23 focused Q1 tests and 115 broad CVC + M9 tests passed.
- Protected M9-A/M9-B, P6, and P7 hashes remain exact.
- No commit or push was performed.
