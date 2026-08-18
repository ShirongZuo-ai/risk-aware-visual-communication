# CVC simulation research program master report

Date: 2026-08-16  
Repository: `C:/Users/ROG/Documents/risk-aware-visual-communication`  
Scope: experiments only; no paper, commit, push, or real-robot action.

## Part I — Q6 development

1. **Initial scheduler.** `q6-v1-value-confirmed`: R0/R1 hard ARM, exact frozen Q5 PREPARE, discrete SafetyValue SPEND, step-217 fallback, and step-218 reserve.
2. **Major variants.** Generation 1 hard-arm/value confirmation; generation 2 precursor opportunity plus value confirmation; generation 3 two-sample persistent opportunity. The predeclared hard-arm persistence and safe-set variants were behaviorally dominated by generation 1 because no live episode armed.
3. **Causal hypotheses.** Generations sequentially tested hard-risk relevance, removal of ARM bootstrap starvation, removal of sparse live-value confirmation, and finally grouped learned opportunity discrimination.
4. **Matched bytes.** Every executed policy episode sent exactly three 24,000-byte real JPEG wire packets = 72,000 bytes; container components reconciled and all receiver mirrors matched.
5. **Actionability.** A1-v1 changed 0/20 schedules versus A0; generation 2 changed 1/20; generation 3 changed 9/20. Generation-3 opportunity sends occurred at steps 145–150.
6. **Receiver images.** Schedule-different generation-3 pairs changed decoded receiver image hashes in all 9 intervention cells. Against U0, image hashes differed in all 20 cells because the schedules differed.
7. **Planner/control.** All 9 generation-3 interventions changed the selected action and wheel command versus A0. Frame counts are mechanistic, not inferential units.
8. **Physical safety.** Generation 3 versus A0: mean danger-step delta -40.9, minimum-clearance delta +0.019750 m, 9 improved/11 tied/0 adverse cells, no collision delta. Versus U0: mean danger-step delta -10.3, minimum-clearance delta -0.001237 m, 8 improved/4 tied/8 adverse, no collision delta.
9. **False activation.** No matched control spent early in the 20-cell generation-3 screen. Q5's broader frozen corpus had 11/53 event-free episodes activate, so absence in this screen is not a general false-warning guarantee.
10. **Starvation/reserve.** Generation 1 never armed and all 20 A1 packets fell back. Generation 2 used 19/20 fallbacks. Generation 3 intervened in 9 cells and fell back in 11. Every run preserved the step-218 reserve; it prevented budget exhaustion but exposed fallback dominance.
11. **Rejected variants.** v1 rejected for F7/F6/F1; generation 2 rejected for F6/F9; generation 3 rejected for F6/F9/F10. No result was erased or relabeled.
12. **Selected method.** None. Generation 3 is the strongest development method but fails the predeclared non-adverse strongest-baseline/family requirement.
13. **ML escalation.** Yes, as a development-only qualification diagnostic; the model was not integrated into the scheduler.
14. **Why ML was justified.** The rule was actionable and changed image/planning/safety, but useful timing was family-dependent and the simple rule could not separate useful from adverse opportunities.

## Part II — Learned branch

15. **Data support.** Frozen Q5 causal data: 70 episodes, 21,840 rows, eight families, 19 accepted SafetyValue onsets, 304 positive future-window rows. This is adequate for compact baselines, not a GRU/TCN.
16. **Features.** Soft feasibility mass and OLS-8 slope, stale-action margin, safety gap, safe fraction, four candidate-margin summaries, obstacle bearing/proximity, image age, and held/current action change. No evaluator fields, R1 fabrication, or component-area fabrication.
17. **Grouped split.** Leave-one-physical-family-out; episodes never cross folds and timesteps are never randomly split.
18. **Models.** Regularized class-balanced logistic regression and a small class-balanced histogram gradient-boosting model (7 leaves, 100 iterations).
19. **AUPRC.** Positive-family macro AUPRC: logistic 0.266707; tree 0.444611. Overall out-of-fold AUPRC: 0.111714 and 0.289120.
20. **Event recall.** At development thresholds constrained to <=3% active time: logistic 18/19 = 94.74%; tree 16/19 = 84.21%.
21. **Lead.** Target horizon is strictly future 16 steps = 0.512 s. The Q5 rule's measured covered-onset lead remains median 0.576 s; the ML audit did not re-estimate a separate event lead distribution.
22. **False activation.** Event-free warning episodes: logistic 30/53 = 56.60%; tree 44/53 = 83.02%; both are worse than the frozen rule's 11/53 = 20.75%.
23. **Calibration.** Thresholds were selected only from out-of-fold development scores under the 3% activity cap. No independent calibration set exists, so probability calibration is not claimed.
24. **Runtime.** Offline training completed, but online runtime was not qualified because integration failed the discrimination gate.
25. **Selected model.** The tree ranked higher by macro AUPRC, but no model passed the integration gate; therefore no operational model was selected.
26. **Weights/hash.** Diagnostic model artifact SHA-256 `1d14de4b52255d34e8c891666a4a539926ad8c5a68edbe54e288f16f89040466`; it is explicitly non-operational and not a frozen communication method.

## Part III — Frozen method

27. **Final algorithm.** No algorithm is frozen for independent validation. Generation 3 is retained only as the strongest consumed development candidate.
28. **R1 semantics.** Two-second state-only constant-twist clearance from current causal visual obstacles and the held selected command; score is negative conservative clearance. It remained diagnostic after hard ARM proved incompatible.
29. **Precursor.** Exactly `soft_mass <= 0.6543448254639964` and causal OLS-8 slope `< -0.11876628431105299/s`; never refit.
30. **PREPARE.** Generation 3 requires two consecutive precursor-active samples; no future frame or evaluator truth is used.
31. **SPEND.** Generation 3 spends the single adaptive token on the second consecutive active sample.
32. **Reserve/fallback.** Adaptive fallback step 217 and protected reserve step 218; future byte debt forbidden.
33. **Packetization.** Three packets of exactly 24,000 bytes, JPEG quality 45, unchanged real encode/container/decode path.
34. **Exact bytes.** 72,000 wire bytes per episode including metadata and deterministic padding.
35. **Method manifest.** None, because no method passed development selection. Readiness manifests bind each attempted generation but do not confer Q7 eligibility.
36. **Hashes.** G1 `b14ab05e...afb4`; G2 `ed5d04fd...4714`; G3 `3b9ed080...2aab7`. Full hashes are in the machine manifests.

## Part IV — Q7 independent validation

37. **New families.** Not created: doing so after no selectable method would spend independent evidence without a valid frozen candidate.
38. **Manifest.** Not created.
39. **Manifest hash.** Not applicable.
40. **Safety support.** Not measured.
41. **Schedule differences.** Not measured independently.
42. **Image age.** Not measured independently.
43. **Planning effects.** Not measured independently.
44. **Physical effects.** Not measured independently.
45. **Family results.** Not measured independently.
46. **Budget robustness.** Not performed; the primary 72 kB development point failed selection.
47. **Delay robustness.** Not performed.
48. **Classification.** Q7 not authorized/not executed; no PASS/PARTIAL/FAIL claim.

## Part V — Formal

49. **Pilot design.** Not created because the Q7 prerequisite failed.
50. **Calibration design.** Not created.
51. **Formal protocol.** Not created or frozen.
52. **Primary endpoint.** Not preregistered.
53. **Practical threshold.** Not selected.
54. **Statistics.** Not selected.
55. **Support gates.** Not opened.
56. **Formal manifest.** Does not exist.
57. **Formal hash.** Not applicable.
58. **Execution count.** 0.
59. **Exclusions/replacements.** 0/0.
60. **Primary result.** Not available.
61. **Uncertainty interval.** Not available.
62. **Secondary results.** Not available.
63. **Family heterogeneity.** Development heterogeneity is strong and blocks Formal; no Formal heterogeneity estimate exists.
64. **Verdict.** Formal NOT JUSTIFIED / NOT EXECUTED, not Formal FAIL.
65. **Protected evidence.** M9-A manifest/result/ledger hashes remain `52b33b...02e8f`, `efaea5...1715`, `efd873...50ca`; M9-B result/ledger remain `59bfd8...f8b11`, `bd9b6f...73bc4`.

## Part VI — Final scientific status

66. **Proven.** In this controlled Webots stack, exact-cost packet timing can causally change decoded information, a safety-first planner, wheel commands, and physical clearance/danger exposure.
67. **Descriptive only.** The magnitude and family distribution of benefits, progression tradeoffs, and ML rankings are development-only.
68. **Did predictive/value-aware communication improve safety?** Versus reactive A0, yes for the final development rule. Versus the strongest U0 baseline, the result is mixed and fails the non-adverse requirement.
69. **Conditions.** Benefits appear in opposed-gate, three-stage-weave, and parts of reverse-chicane; interventions reduce progress because refreshed obstacle information induces conservative control.
70. **Failures.** Hard R1 ARM starved; live discrete SafetyValue was too sparse; persistent precursor was adverse in staggered slalom and mixed versus U0; learned predictors had excessive false warnings.
71. **Strongest claim.** A qualified decision-space precursor can make exact-cost visual communication task-effective in some closed-loop geometries, but the present scheduler does not generalize safely enough to beat a strong uniform baseline.
72. **Is ML necessary?** Not established. The tested compact ML models are worse than the interpretable rule on false-warning burden; more complex ML is under-supported.
73. **Frozen?** Historical attempts and evidence are hash-bound; no method is frozen for Q7 or hardware.

## Part VII — Real-robot readiness

74. **Software artifact.** No hardware-eligible artifact; generation 3 remains development-only.
75. **Runtime.** A future candidate must meet the existing 32 ms loop, qualify inference latency, and retain deterministic failure handling.
76. **Robot/camera.** Required: calibrated RGB camera compatible with 160x120 BGRA/RGB semantics, known pose/extrinsics, differential-drive wheel interface, and validated obstacle-range model.
77. **Network.** Required: exact end-to-end byte accounting including headers/metadata/padding, measured delay/loss, causal receive/hold semantics, and no hidden side channel.
78. **Safety supervisor.** Required independent speed/clearance/contact supervisor that cannot be overridden by the communication policy.
79. **Emergency stop.** Required tested human and automatic E-stop, command timeout, motor-disable path, and recovery checklist.
80. **Ground truth.** Required external pose/obstacle measurement, bilateral contact instrumentation, synchronized clocks, and blinded evaluator logging.
81. **Pilot.** Not authorized. A future pilot would need low-speed static fixtures, staged clearance, abort boundaries, and non-inferential feasibility trials before paired tests.
82. **Baselines.** Future paired baselines must include strong uniform timing U0 and a causal reactive baseline at identical wire cost.
83. **Sim-to-real risks.** Color/lighting detector brittleness, range bias, unmodeled dynamics/slip, camera latency, packet overhead, obstacle appearance, contact semantics, and human safety.
84. **Remaining actions.** Develop a new method on new development evidence, freeze it, pass a new independent Q7, justify/complete Formal, then obtain hardware, safety review, calibration, and explicit physical authorization. No hardware action was taken.

## Part VIII — Reproducibility

85. **Commands.** `python scripts/qualify_cvc_q6_offline.py`; `python scripts/run_cvc_q6_webots.py --variant q6-v1-value-confirmed`; `python scripts/run_cvc_q6_generation2.py`; `python scripts/run_cvc_q6_generation3.py`; `python scripts/analyze_cvc_q6.py ...`; `python scripts/train_cvc_q6_learned_precursor.py`; `python scripts/plot_cvc_q6.py`.
86. **Environment.** Windows 11, Python 3.12.7, Webots R2025a, repository branch `main`, inspected HEAD `816b4453184a1cc602f6558764e839478d142e96`.
87. **Packages.** NumPy 1.26.4, pandas 2.2.3, scikit-learn 1.7.2, Matplotlib 3.9.2, Pillow 11.3.0.
88. **Seeds.** Q5 literal scenario seeds 985xxx; learned models use 20260816; no timestep-random split.
89. **Tests.** 15 focused Q6 tests passed; final broad CVC/M9 regression: 193 passed in 9.38 s. A shell-glob invocation that collected zero tests was corrected and is not counted.
90. **Hashes.** Machine manifests, results, model, figure, and historical M9 evidence have SHA-256 sidecars or are listed in the master evidence inventory.
91. **Figures.** `figures/cvc_q6/q6_family_safety.png` and PDF; the PNG was visually inspected after one layout revision, SHA-256 `3b2782a6...4312f`.
92. **Machine summaries.** `results/cvc_q6_analysis/*.json`, `results/cvc_q6_learned_precursor/training_report.json`, and generation matrix results/traces/jobs/logs.
93. **Ledger.** `results/cvc_q6_development/development_ledger.json` preserves hypotheses, lineage, exact cost, results, failure classes, selection decisions, and the reason development stopped.

## Terminal decision

The program stops at **Q6-C**. Continuing to tune rule thresholds, train larger models on 19 onsets, or consume an independent Q7 set without a selectable method would be outcome-driven search. Q7, Formal, and real-robot execution remain unopened.
