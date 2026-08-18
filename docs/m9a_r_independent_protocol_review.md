# M9-A-R Independent Protocol-Readiness Review

Date: 2026-08-13. Scope: protocol and schema review only. No Webots process, M9 dataset, or method outcome was accessed or generated.

## A. Verdict

**PASS WITH REQUIRED AMENDMENTS.** The original M9-A-P had a sound separation of future labels from predictor inputs, but it was not ready to authorize pilot implementation until the amendments recorded below. The amended protocol is ready for a separate implementation review; this review itself does not authorize launch.

## B. Critical validity issues found

1. The original claim rule allowed any favorable signal, horizon, or metric to support C2, creating hidden multiplicity and outcome selection. Amendment: one primary score/label/horizon and two paired contrasts are now frozen.
2. False-warning calibration lacked an exact safe-exposure denominator, debounce, refractory period, and aggregation formula. Amendment: completed safe calibration episodes, three-step activation/release, 0.5 s refractory interval, total events/total eligible minutes, and episode bootstrap are frozen.
3. The formal grid could still be changed after pilot feasibility observations. Amendment: grids and deterministic seed mapping must be frozen before pilot; failure requires a reviewed protocol version change, not filtering.
4. F8 has no collision/near roles but the original per-family support rule required all roles in all families. Amendment: F1-F7 and F8 have separate support gates.
5. Prose-only formal sealing was insufficient. Amendment: manifest/protocol/calibration digests, append-only access ledger, explicit unlock, atomic one-shot state transition, and terminal ambiguous access are specified.

## C. Major non-fatal issues found

- Physical radius and M3 corridor were numerically separated but output terminology was not enforceable. Durable M9 names now distinguish physical, nominal-predicted, and uncertainty-corridor clearance.
- Contact truth did not fully specify the queried node, counterpart fields, or mandatory fixtures. These are now frozen.
- `d_near` selection did not state collision participation, boundary handling, persisted decision identity, or the absence of a tie beyond “smallest.” These are now explicit.
- Near-miss grouping and overlapping positive-window mapping were incomplete. Maximal intervals, merge gaps, primary interval choice, and episode/event inference are now defined.
- Command-transition support was not independently gated. F3-F6 now require 16 danger events, including six toward and six away/braking events.
- Exclusions were prose strings. A closed reason-code vocabulary and method-blind pre-outcome decision boundary are now required.

## D. Minor reproducibility issues

- Horizon point counts needed an explicit zero-offset convention and interpolation fractions.
- The manifest schema lacked protocol digest, seed namespace, calibration digest, access-ledger path, and separate radii.
- Contact records lacked API/query identity and counterpart DEF.
- The literature table needed explicit threat classes.

## E. Required amendments applied

All critical and major amendments above were applied to the protocol, scenario specification, and schemas. Pilot implementation must not weaken them. The finite literal family grids remain to be enumerated in an outcome-free manifest before implementation can be judged launch-ready; current broad ranges alone are insufficient to launch.

## F. Claim-metric mapping

| Claim | Primary endpoint | Required contrast/rule | Secondary | Descriptive only |
|---|---|---|---|---|
| C2 | `danger_within_2.0s` AUPRC using negative predicted physical clearance | R1-R0; difference >=0.05 and paired 95% CI lower bound >0 | event detection and lead time at calibrated false-warning constraint; Spearman and clearance MAE | 0.5/1.0 s, collision-only/near-only, AUROC, RMSE/Pearson, TTCf, corridor entry, M3 component scores, timestep precision/recall/FPR |
| C3 | Same | R2-R1; same rule | Same | Same |

Secondary results cannot rescue a failed primary claim. Family effects diagnose heterogeneity; an adverse supported-family AUPRC effect below -0.05 prohibits an unqualified GO.

## G. Minimum support

- At least 120 valid formal episodes, 32 collisions, 32 near misses, and 40 safe episodes.
- F1-F7: at least four observed episodes of each collision/near/safe role per family.
- F8: at least 12 safe controls, at least three in each safe distance band.
- F3-F6: at least 16 danger events, including six turn-toward and six turn-away/braking events.
- Lead-time analysis: at least 24 eligible events separately for collision and near-miss strata.
- Failure produces `insufficient_support`; calibration is never pooled.

## H. Formal sealing

The formal outcome-free manifest and literal parameters are frozen before pilot. A lock binds protocol version/digest, schema versions, Git HEAD, Webots version, seed namespace, and manifest digest. Calibration produces one canonical artifact binding selected `d_near`, all warning thresholds, source/code digests, and its SHA-256. Formal evaluation requires exact locks plus explicit one-shot unlock. An append-only ledger records access before any log opens. Partial or ambiguous access cannot auto-retry. A separate validator proves no exploratory/calibration path references formal logs.

## I. Literature threats

| Work/direction | Threat class | Reason |
|---|---|---|
| Dynamic Allocation of Visual Attention for Vision-based Autonomous Navigation under Data Rate Constraints | **Close threat** | Already establishes receding-horizon navigation-dependent information-rate allocation. |
| Goal-Oriented Semantic Communication for ISAC-Enabled Robotic Obstacle Avoidance | **Direct overlap** | Connects prediction/VoI-driven transmission decisions with closed-loop obstacle-avoidance success, though not spatial camera fidelity. |
| Collision avoidance using predicted obstacle trajectories/probability | **Enabling/adjacent** | Establishes future-trajectory collision risk; no communication allocation. |
| Risk-aware navigation / CIAO* | **Enabling/adjacent** | Establishes predictive or physical risk in planning, not transmission. |
| WayFAST predictive traversability | **Close threat** | Projects future-path task utility into image space and evaluates navigation, but has no constrained visual communication allocation. |
| Risk-aware aerial visual assistant | **Close threat** | Couples visual utility and motion risk through viewpoint control, not transmitted bitrate. |
| Safe-VLN / RA-Nav | **Low threat** | Navigation safety and risk maps without communication-resource allocation. |

To remain meaningfully distinct, a future paper must demonstrate all three empirically: independently validated ego-future danger, danger-conditioned **spatial camera-bit/fidelity allocation** under matched actual communication cost, and improved preregistered constrained-navigation safety. M9 can establish only the first link.

## J. Pilot-authorization checklist

- [x] Exact horizon semantics and equivalence tests specified.
- [x] Physical and predictor-side geometry separated in terminology and schemas.
- [x] Contact API, queried body, counterpart classification, onset/persistence, and mandatory fixtures specified.
- [x] Finite `d_near` candidates and deterministic calibration rule frozen.
- [x] False-warning denominator, debounce, refractory interval, selection, and failure behavior frozen.
- [x] Collision/near-miss/overlapping-window event grouping frozen.
- [x] Formal manifest/digest/access-ledger enforcement design frozen.
- [ ] Literal finite scenario grids and deterministic seed mapping materialized and independently validated.
- [x] Minimum event-support gates frozen.
- [x] Closed exclusion codes and method-blind decision boundary frozen.
- [x] Log/manifest schemas parse and contain the amended enforcement fields.
- [ ] Pilot implementation and its unit/fake-Supervisor tests independently reviewed.

## K. Authorization

**Pilot implementation is not yet authorized by this review.** Protocol readiness passes with the applied amendments, but launch authorization requires literal scenario-grid/seed artifacts and a reviewed implementation satisfying every checklist item. Webots pilot execution remains separately gated.
