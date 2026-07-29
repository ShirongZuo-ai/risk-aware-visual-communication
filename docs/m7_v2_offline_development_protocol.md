# M7 v2 Offline Allocator Development Protocol

## Status and immutable inputs

Status: preregistered before any M7 v2 outcome calculation on 2026-07-30.

M7 v1 remains an immutable `NO-GO` result. Its implementation, protocol, nine gates, CSV/JSON evidence, figures, and reported values are not inputs to parameter tuning and must not be rewritten. M7 v2 reads the completed 16-episode M7 v1 development corpus only. It does not launch Webots, create 720xxx identities, or amend M5/M6/M7 v1 evidence.

The frozen baselines remain `state_only_risk_roi` and `command_conditioned_risk_roi`. The four common byte targets, 8x6 tile grid, JPEG implementation, method-independent TCOBR evaluator, Canny thresholds, episode unit, 10,000-replicate scene-stratified bootstrap, seed `20260724`, and 95% percentile interval remain unchanged.

## Information boundary

Allowed allocator inputs are current RGB, current state, the predefined command schedule already available at the snapshot timestamp, shared projection parameters, the two predicted trajectory-corridor masks, and the exact sender-side byte counts of the two frozen baseline encodings for that same snapshot and budget.

The allocator must reject actual future trajectory, future frames, ground-truth obstacle geometry, TCOBR labels, eligibility labels, evaluator masks, reconstructed-task outcomes, and unknown fields. Baseline byte counts are used only to construct a matched communication envelope; baseline quality, PSNR, TCOBR, and evaluator outcomes cannot select a tile.

Evaluator-only obstacle geometry is loaded only after every candidate allocation for all four budgets of an episode is finalized and provenance-validated.

## Shared constrained allocation

The allowed quality ladder is `(1, 5, 15, 25, 35, 45, 55, 65, 75, 95)`, which is exactly the union of qualities already exercised by the frozen baseline codec search and M7 v1.

For each snapshot and budget:

1. Reproduce both frozen baseline complete transmissions and validate their recorded case digests.
2. Define the candidate byte cap as the integer floor of the midpoint of their actual charged bytes.
3. Define the fairness tolerance as `0.005 * common_budget_bytes` for each baseline.
4. Encode every tile at every allowed quality.
5. Select the highest uniform quality whose exact complete tile-container bytes plus v2 metadata do not exceed the midpoint cap. This is the minimum-quality safeguard; no later operation may lower any tile below it.
6. Repeatedly consider every one-step tile-quality upgrade. For each candidate, rebuild the complete tile container and calculate its exact positive incremental transmitted bytes and marginal diagnostic distortion reduction.
7. Select the feasible positive-benefit upgrade with greatest benefit per exact incremental byte. Resolve ties by lower row-major tile ID and then lower target quality.
8. Stop when no positive-benefit transition fits the midpoint cap. Zero/nonpositive byte increments, nonpositive benefits, fallback, replacement, or over-budget output fail closed.

The final candidate must remain under the common byte target and within 0.5 percentage points of both frozen baselines. No uncharged padding, hidden signaling, or evaluator-derived mask is allowed.

## Predeclared candidate and ablation set

All candidates share the byte envelope, quality floor, exact recomputation, deterministic tie break, and information boundary. Only the marginal reconstruction-benefit mask differs:

| Candidate | Marginal diagnostic distortion | Purpose |
| --- | --- | --- |
| `v2_global_only` | 100% whole-tile RGB MSE | Quality-floor and byte-matching control |
| `v2_visible_edges` | 50% current-frame Canny-edge MSE, 30% predicted-corridor MSE, 20% whole-tile MSE | Tests whether visible edges without task localization suffice |
| `v2_corridor_edges` | 50% current-frame Canny edges inside the dilated union predicted corridor, 30% predicted-corridor MSE, 20% whole-tile MSE | Full v2 mechanism; optimizes a sender-visible proxy for continuous critical-boundary fidelity |

Empty component masks redistribute their weight proportionally across defined components. No candidate weight or threshold may change after outcome inspection.

## Episode effects and scene-aware selection

For each candidate and episode, compare against the better frozen baseline separately for every metric and budget. The primary continuous-task contrast is the equal mean of Severe and Low episode effects. Resample episodes within each eligible scene, weight scenes equally, use 10,000 replicates with seed `20260724`, and report the 95% percentile interval. Undefined TCOBR remains undefined and is never imputed.

A candidate is eligible for future formal-corpus preparation only when all nine gates pass:

1. **Exact byte fairness:** every case is under the common target and no candidate differs from either baseline by more than 0.5 percentage points of the common target.
2. **Integrity and leakage:** complete finite coverage and zero actual-future, evaluator-input, fallback, or replacement usage.
3. **Allocation actuation:** at least 75% of Severe and Low snapshots differ from each baseline in at least one tile quality.
4. **Continuous task utility:** the Severe/Low primary continuous-boundary effect has a scene-stratified 95% CI lower bound above zero.
5. **Critical quality:** mean critical-region PSNR effect is no worse than `-0.25 dB` at both Severe and Low; full-frame PSNR is also reported.
6. **TCOBR non-degradation:** no defined Severe/Low episode has a negative TCOBR effect and both budget means are nonnegative.
7. **Critical-boundary fidelity:** mean continuous-boundary effect is positive at both Severe and Low.
8. **Scene balance:** every leave-one-scene-out primary continuous effect is positive and no scene contributes more than 50% of total positive scene gain.
9. **Deterministic reproduction:** all 256 candidate allocations, source tables, provenance, bootstrap inputs, and figures regenerate byte-for-byte.

If multiple candidates pass, choose the candidate with the largest minimum leave-one-scene-out primary continuous effect, then the larger worst-budget critical-PSNR effect, then lexicographically smaller candidate ID. If none pass, the decision is `NO-GO`. A `GO` would authorize only preparation of a separately reviewed disjoint formal corpus, not a Webots launch.
