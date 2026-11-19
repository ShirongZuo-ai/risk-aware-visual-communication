# Research results and continuation

Evidence through September 2, 2026. The studies use Webots simulation. M9-B evaluates future-danger prediction. CVC and Q6AD evaluate visual communication under a fixed episode budget.

## Main findings

| Study | Evidence and disposition |
| --- | --- |
| M6 allocation | The original eight-scene gate was unevaluable because three strata had no eligible episodes. Among 17 eligible episodes, command-conditioned minus state-only obstacle-boundary recall was 0.000 (95% CI [0.000, 0.000]). The amended gate failed. |
| M9-B prediction | Across 240 valid cells (70 collision, 70 buffered-near, 100 safe), 2 s macro-AUPRC was 0.906311 for current-clearance R0, 0.993730 for state-rollout R1, and 0.999778 for R2. The preregistered R1−R0 contrast was +0.087419 (paired 95% CI [0.077181, 0.098534]) and passed. The macro-average covers F1–F7. The R2 contrast is descriptive. |
| CVC-P2 / Q6 / Q6.5 development | P2 verified 72,000 charged bytes per episode (two 36,000-byte packets, 42 episodes). R0 and R1 tied in all 18 matched mechanism/scenario pairs. Q6 showed that send timing can change wheel commands, with heterogeneous physical effects. Q6.5 found measurable adjacent-opportunity labels, and both generations failed their policy or predictor gates. |
| Q6AD engineering | E6 completed 511 of 512 registered Train surfaces, with one fixed quarantine. Seven timing branches per eligible surface yielded 3,577 primary evaluator records. The episode budget was three 24,000-byte packets. The outcome-blind learner-object and Train evaluator finalization gates passed within their engineering scopes. |
| Q6AD Train-only pilots 01 and 02-R1I | Pilot 01 stopped at scalar reward audit. The registered R1I rerun supersedes Candidate4, which is classified as orphaned evidence. Across 511 Train surfaces the two fitted arms chose identical actions, with 54 collisions each versus 0 at forced step 217. Mean danger steps were 87.85 versus 115.81. The R1I acceptance verdict establishes the registered lineage for this adverse collision result. |
| Safe Improvement Pilot 01 | The corrected, process-separated run met its frozen Train-only hierarchy. Statistics audit passed. Red-team and reproducibility audits were qualified. This supports review of a Selection gate. |
| Selection engineering | The September 2 diagnostic at step 125 ran successfully in Webots on its third attempt. The subsequent verifier failed, and the sequence stopped before step 217 and before outcome opening. This leaves Selection efficacy unevaluated. |

Supporting records: [M6 protocol](../m6_followup_evaluation_protocol.md), [M9-B registration](../m9b_confirmatory_preregistration.md), [CVC-P2 report](../cvc_p2_development_report.md), [Q6 terminal record](../../results/cvc_q6_final_status.json), [Q6.5 terminal record](../../results/cvc_q65_final_status.json), [aggregate metrics and source identities](research-aggregates.json).

## Safe Improvement Pilot 01

The unit is one registered Q6AD Train surface. Each scored arm used 72,000 bytes per surface with zero budget violations. A is the fixed step-217 comparator. B is the ungated learned comparator. C applies the learned safety gate with fallback to step 217. SIP01 B reproduces the registered R1I B action distribution. SIP01 C is the distinct conservative policy. F is an evaluator-only oracle.

| Arm | Collisions / 511 | Mean danger steps | Mean minimum clearance (m) | Mean progress (m) |
| --- | ---: | ---: | ---: | ---: |
| A — forced 217 | 0 | 115.8141 | 0.01118 | 0.63117 |
| B — ungated | 54 | 87.8513 | 0.02170 | 0.65223 |
| C — safety-gated | 0 | 80.1292 | 0.03017 | 0.64951 |
| F — evaluator-only oracle | 0 | 75.7280 | 0.02988 | 0.65848 |

C captured 341 of 402 safe opportunities and fell back on 164 of 511 surfaces. The exact one-sided 95% collision-rate upper bound for C was 0.5845%. C−A mean danger steps were −35.6849 (95% CI [−36.8630, −34.5283]), clearance +0.01898 m [0.01823, 0.01974], and progress +0.01833 m [0.01709, 0.01955]. Intervals use 10,000 paired surface bootstrap replicates across the 16 frozen strata.

The corrected provider → learner → evaluator lineage was 171200 → 171400 → 171500, with scorer code 14b805624dba19a96a807a3a984c32bf60df2932. Earlier run 170200 is invalid because the learner could access the full physical table via its CLI. The corrected verifier checks recorded access and provenance. Operating-system isolation, environment locking, and process resource capture remain reproducibility gaps.

## Resume the study

1. Identify the corrected pilot by the artifact hashes in the aggregate file. The later Train-only promotion froze SAFE-RAW55-V1 with C=1.0, tau=0.05 and margin=0.0. The earlier Selection design used an incompatible observation shape and timing schedule, so the prospective design is Selection V2.
2. Reconcile the failed post-verifier receipts against the frozen progression contract. The engineering closeout calls for an independently verified double-clean-clone run before a new scoped technical smoke.
3. Keep Train, Selection, holdout and stress separate. A confirmatory safety claim requires independent evaluation against a frozen strongest comparator. Real-robot applicability remains open.

The aggregate file records original evidence identities for researchers with access to those artifacts. The execution commits and original per-surface records for the later runs are held in local research worktrees. Cloning this repository provides the published analyses, protocols, and summaries.
