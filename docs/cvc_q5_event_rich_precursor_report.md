# CVC-Q5 — Event-Rich Cross-Scenario Precursor Qualification

Date: 2026-08-16  
Status: development/mechanism qualification complete — **CASE A**  
Scope: no scheduler integration, A0/A1 comparison, ML fitting, navigation-benefit claim, or Formal access.

## Blinded physical development and freeze

Stage A executed the unchanged Q1 Webots world/controller at fixed U0-3 cadence. Its runner and support module had no Q4 import; an AST/config guard rejected precursor-module imports and threshold keys. Scenario construction could inspect only physical behavior, causal camera/Q1 held-current planner states, and the frozen Q2/Q3 Safety Decision Value. An accepted onset required step >=8, no preceding/coincident bilateral contact, and at least two current safe actions. Every attempted cell, including negatives and controls, was retained.

Eight physical families and 70 cells were attempted:

| Family | Physical rationale | Cells | Positive episodes | Accepted onsets | Status |
|---|---|---:|---:|---:|---|
| progressive offset closure | A curved path progressively narrows one side while leaving an outer arc. | 8 | 0 | 0 | preserved negative |
| late turn reveal | Goal-directed turning makes a previously oblique obstacle relevant to the committed arc. | 8 | 0 | 0 | preserved negative |
| asymmetric route collapse | Staggered obstacles remove one initially viable route branch while retaining an alternative. | 8 | 0 | 0 | preserved negative |
| staggered slalom constraint | Alternating constraints remove left/right candidate groups during a diagonal traverse. | 8 | 3 | 4 | positive |
| off-axis size growth | Oblique apparent growth removes the toward-obstacle action family. | 8 | 0 | 0 | preserved negative |
| three-stage weave | Three alternating constraints create two successive route-choice contractions. | 10 | 5 | 5 | positive |
| opposed gate contraction | Offset gate posts reduce the admissible steering fan while alternatives remain. | 10 | 4 | 4 | positive |
| reverse diagonal chicane | A mirrored right-then-left constraint tests the opposite steering topology. | 10 | 5 | 6 | positive |

The initial 40-cell pass produced only one positive family/four onsets and was preserved. A blinded, independently motivated 30-cell repair added three topologically distinct families. Final support was four positive families and 19 onsets, exceeding the frozen 3-family/4-onset-per-family/12-total gate. There were 53 event-free episodes, including controls in every positive family.

The full 70-cell manifest freezes family definitions, roles, seeds, initial poses, goals, obstacles, U0-3 timing, unchanged Q1 world/controller hashes, SafetyValue support, trace/job hashes, historical protected hashes, and the six generalization gates. Manifest: `results/cvc_q5_readiness/manifest.json`; SHA-256 `5d1f4f6ff683937bdde6c2df1d61ec11a37b9f6bf199d3b3abc2999e3398616c`.

## Frozen rule and causal boundary

Only after the manifest was written did Q5 evaluate the exact Q4 rule:

```text
soft_feasibility_mass <= 0.6543448254639964
AND OLS-8 slope < -0.11876628431105299 /s
```

No threshold, signal, estimator, window, or SafetyValue definition changed. Implementation: `evaluation/cvc_q4_precursor.py`, SHA-256 `c58905f6de70757d540eaaa21cbcacf440bb72e3fc43ec2677bb7a4ee6ce668f`. OLS-8 uses only the current and preceding seven 32 ms samples. Evaluator geometry/contact/outcomes do not enter precursor computation or the exported feature set.

## Coverage and lead

The frozen precursor covered 16/19 onsets (84.21%). Covered-onset lead was mean 0.648 s, median 0.576 s, range 0.352–1.344 s, q25 0.432 s, and q75 0.776 s. Fractions over all 19 onsets were 84.21% at >=0.25 s, 47.37% at >=0.50 s, and 10.53% at >=1.00 s; uncovered onsets remain failures in these denominators.

| Positive family | Episodes | Onsets | Covered | Coverage | Covered lead mean / median / range (s) | >=.25 / >=.50 / >=1.00 of all onsets |
|---|---:|---:|---:|---:|---|---|
| staggered slalom | 8 | 4 | 3 | 75.0% | .843 / .608 / .576–1.344 | 75% / 75% / 25% |
| three-stage weave | 10 | 5 | 5 | 100% | .397 / .384 / .352–.448 | 100% / 0% / 0% |
| opposed gate | 10 | 4 | 3 | 75.0% | .683 / .800 / .384–.864 | 75% / 50% / 0% |
| reverse chicane | 10 | 6 | 5 | 83.3% | .762 / .672 / .448–1.344 | 83.3% / 66.7% / 16.7% |

The four other attempted families had no accepted target onset, so they contribute event-free/false-activation evidence rather than an undefined coverage estimate.

## Opportunity width, persistence, and timing jitter

For covered onsets, total active duration had mean/median 0.248/0.224 s and range 0.064–0.416 s. Longest contiguous runs had mean/median 0.204/0.192 s and range 0.064–0.320 s. The gap from last activation to onset had mean/median 0.352/0.352 s and range 0.128–0.640 s.

Of all 19 onsets, 15 had stable intervals, one was intermittent, three were missed, and none was an isolated one-step opportunity. Sixteen (84.21%) had >=2 consecutive active steps and 15 (78.95%) had >=3. Strict opportunity robustness—requiring a contiguous run of at least `2k+1` samples for ±k scheduler-phase shift—was 15/19 at ±1, 14/19 at ±2, and 7/19 at ±3. Per-family ±1/±2/±3 fractions were: slalom 50/50/0%, weave 100/80/60%, gate 75/75/75%, and reverse chicane 83.3/83.3/16.7%.

## Sparsity and event-free false activation

The precursor was active for 320/21,840 samples (1.465%). It activated in 11/53 event-free episodes (20.75%). Those episodes contained 15 runs, or 0.283 runs/event-free episode. False-run duration was mean/median 0.179/0.192 s, range 0.032–0.384 s; three runs were isolated and 12 persisted >=2 steps. Runs occurred in asymmetric route collapse (8), opposed gate (4), and progressive offset closure (3); all other families had none. This distinction shows that the episode-level false rate is driven mostly by short bounded intervals, although the 0.384 s maximum is non-trivial.

## Frozen gates and classification

| Gate | Requirement | Result | Pass |
|---|---|---:|:---:|
| support | >=3 positive families, >=4 onsets/family, >=12 total | 4 families; 4/5/4/6; 19 | yes |
| A | pooled coverage >=75% | 84.21% | yes |
| B | >=50% coverage in >=3 positive families | 4/4 families | yes |
| C | median lead >=0.25 s | 0.576 s | yes |
| D | total active time <=2% | 1.465% | yes |
| E | event-free episode activation <=25% | 20.75% | yes |
| F | >=50% covered onsets have usable non-isolated opportunity | 16/16 = 100% | yes |

Primary classification: **CASE A — CROSS-SCENARIO PRECURSOR QUALIFIED**. This is a development qualification, not evidence that precursor-assisted communication improves navigation safety.

## Runtime, artifacts, and verification

The online composite (one decision-space extraction plus OLS-8 trend) over 1,000 repetitions measured mean 0.126 ms, p95 0.220 ms, max 0.578 ms, with 0/1,000 32 ms misses. Full corpus analysis covered 21,840 samples.

Machine result: `results/cvc_q5_analysis/analysis.json`, SHA-256 `4d5e71872039635ff7ed93d4f72db77c62f6b1c6fda737f3441adae747808067`. The causal future-ML dataset contains 21,840 timestamped rows in CSV and JSONL with family/episode identity, soft mass, slope, M_stale, G, safe-set statistics, candidate-margin statistics, causal obstacle bearing/proximity, image age, action identities, and SafetyValue target. R1 risk and component area are explicitly null because the unchanged Q1 runtime did not log them. No model was fitted and no random timestep split was created.

Six figures were generated and visually inspected: covered onset, missed onset, event-free activation, per-family coverage/lead, persistence/jitter, and activation burden. Focused plus broad CVC/M9 verification passed 107 tests.

Protected Q1/Q2/Q3/Q4/M9 artifacts match the hashes frozen before unblinding. No historical artifact was rewritten; no scheduler, A0/A1 policy, ML, C4/C5 Formal, commit, or push occurred.

## Decision and next experiment

Scheduler integration is now scientifically justified only as a separately authorized development experiment using this exact frozen rule. A learned temporal precursor is not currently justified as the next action: the simple rule passed, and 19 onsets across four families are useful diagnostic support but still thin for reliable held-out-family learning.

Next priority: freeze a separate precursor-actuated scheduler protocol with exact matched bytes, causal sender-only inputs, explicit latch/PREPARE semantics, and no threshold changes; stop before implementation until that new scope is authorized.
