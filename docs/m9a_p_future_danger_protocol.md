# M9-A-P Danger-Rich Future-Risk Validation Protocol

Status: protocol-only preregistration for review. No M9-A Webots episode has been generated and no C2/C3 outcome has been evaluated.

## Scientific gate

M9-A tests two falsifiable claims:

- C2: predicted future motion improves future-danger estimation over current-state-only risk.
- C3: command-conditioned future prediction improves future-danger estimation over state-only future prediction.

M2 predictors and M3 geometry are frozen dependencies. M5-M7 evidence, including negative results, is immutable. M8 is paused. A failure of both predictive conditions to improve meaningfully on R0 is a stop decision for risk-driven communication.

Claim status and evidence boundaries are maintained in [the claim-evidence matrix](claim_evidence_matrix.md).

## Partition and access policy

| Split | Purpose | Regeneration | Outcome access |
|---|---|---|---|
| Pilot | Logging/contact engineering, prevalence and scenario feasibility | Allowed with a recorded attempt index | Never enters scientific claims |
| Calibration | Select `d_near`, warning cutoffs, and only quantities named here | No replacement after the split manifest is locked | Available only to calibration code |
| Formal | One primary C2/C3 evaluation | No replacement; objective exclusions remain in denominator/accounting | Sealed until protocol, implementation, calibration outputs, exclusions, and analysis code are frozen |

Pilot, calibration, and formal episode IDs and seeds are disjoint. Proposed seed namespaces are `91xxxx`, `92xxxx`, and `93xxxx`, respectively. A formal manifest is created without outcome fields, hashed, and locked before pilot generation. Formal parameters are a deterministic function of the protocol version, literal family grid, and formal seed; pilot observations cannot regenerate or filter them. If pilot engineering shows that a declared range is invalid, the protocol version and all not-yet-generated split manifests must be amended under review rather than silently changing formal identities.

Formal paths are rejected by exploratory/calibration CLIs. A formal access ledger starts in `sealed`, is append-only, and records actor, UTC time, command, protocol digest, manifest digest, calibration digest, and prior/new state. The formal evaluator requires exact protocol/schema versions, the manifest lock digest, a frozen calibration-artifact digest, clean validation, an explicit `--formal-unlock` flag, and an unused one-shot evaluation authorization ID. It atomically records `authorized_once` before opening any formal log and `evaluated` after completion; a partial/ambiguous authorization is terminal for automatic rerun. Validators reject cross-split identities, paths, seeds, hashes, or prior formal reads. Merely listing the outcome-free formal manifest is permitted; reading logs, summaries, or outcome-derived metadata before unlock is not.

## Scenario matrix and support targets

Eight parameterized families are defined in [the scenario specification](m9a_p_scenario_families.md). Each family contains collision, near-miss, and matched-safe roles where physically meaningful, and command-transition families include both turn-toward and turn-away cases. Geometry is not chosen from predictor outcomes.

The target matrix is:

| Split | Episodes per family | Total | Role allocation per family |
|---|---:|---:|---|
| Pilot | at least 3, expandable | at least 24 | at least one collision, near-miss, safe |
| Calibration | 12 | 96 | 4 collision, 4 near-miss, 4 matched safe |
| Formal | 18 | 144 | 6 collision, 6 near-miss, 6 matched safe |

Formal minimum support is 120 valid episodes overall, at least 32 collision events, 32 near-miss events, and 40 safe episodes. F1-F7 each require at least four observed collision, four observed near-miss, and four observed safe episodes. F8 requires at least 12 observed safe controls spanning at least three each of safe-near-boundary, safe-mid, and safe-far. The command-transition set F3-F6 requires at least 16 danger events overall, including at least six turn-toward and six turn-away/braking danger events. Lead-time endpoints require at least 24 eligible true events in each collision and near-miss stratum; otherwise that stratum is `insufficient_support`. If any primary support rule fails, the affected formal endpoint is insufficient; calibration episodes are never pooled into formal analysis. These are precision-oriented support rules, not a prospective power guarantee: with 32 events, an observed 50% event-detection proportion has an approximate 95% binomial half-width of 0.17, still requiring intervals and cautious interpretation.

## Dense episode record

The complete episode is logged after every successful `Robot.step(basicTimeStep)` at the actual basic timestep (expected 0.032 s, verified from the world at runtime). The normative schemas are:

- [step-log schema](results/m9a_p_step_log_schema.json)
- [dataset-manifest schema](results/m9a_p_dataset_manifest_schema.json)

One JSON Lines record per step is recommended because obstacle and future-schedule arrays are structured. Each record binds episode/split/family/seed, step/time, actual pose and velocity, applied commands, controller-known future schedule, obstacle AABBs, footprint, contact observations, and provenance. Static geometry and schedule may be referenced by canonical digest after an explicit full record at step zero, but the episode package must be self-contained and independently reloadable. RGB is not required.

The robot footprint for labels is the frozen circular e-puck footprint with radius `0.026 m` (`EPUCK_ROBOT_HALF_WIDTH_M`), not the M3 uncertainty-inflated corridor. Durable names are `physical_clearance_m`, `predicted_nominal_clearance_m`, and `predicted_uncertainty_corridor_clearance_m`. The M3 corridor radius `0.037592257 m` remains a predictor-side risk parameter only. It cannot change collision, near-collision, or actual-clearance labels. Figures and tables must include `physical` or `uncertainty-corridor` in axis/column names. Historical M2/M3 field names are not renamed; M9 adapters expose the new names. Mixing radii or labeling M3 `minimum_clearance_m` as physical clearance is a validation error.

## Physical collision definition

At each completed simulator step the Supervisor queries `Supervisor.getSelf()` and every configuration-declared eligible obstacle/wall root with Python `Node.getContactPoints(includeDescendants=True)`. A collision requires a robot-side and eligible-environment-side runtime point whose world positions agree within the preregistered `epsilon_contact = 1e-6 m`; associated `node_id` values are diagnostic because R2025a did not document or exhibit counterpart-root semantics. Floor, robot descendants/self, decoration, and undeclared bodies are excluded. All simultaneously matched roots are retained; multiple roots in a planned scientific episode cause `CONTACT_VALIDATION_FAILURE`, never opportunistic root selection. Physical clearance remains diagnostic and cannot create collision truth. Full rationale is in [the I2R semantics repair](m9a_i2r_contact_semantics.md).

`collision_active` is true when at least one qualifying point exists. First physical contact is the first completed step whose preceding step had no qualifying contact and whose current step does. Its timestamp is the current post-step simulation timestamp; temporal resolution is one basic timestep. Persistence across subsequent steps belongs to the same event. Collision episodes stop after at least five post-contact steps (nominally 0.160 s) have been logged, unless simulator safety requires earlier termination; an early technical stop is ineligible for lead-time analysis.

Before calibration, pilot contact fixtures must include a definite obstacle collision, definite wall collision, safe close pass below the largest candidate `d_near` without contact, and stationary no-contact episode. Each fixture must reproduce in two runs, with zero qualifying contacts in both negative fixtures and at least one correctly identified contact onset in both positive fixtures. The pilot compares returned points/IDs, visible Webots contacts, and footprint/AABB relations. If counterpart identity or contact detection is unreliable, M9-A stops; predicted TTCf, corridor entry, or geometric overlap may not silently replace physical collision truth. Webots documents Supervisor contact points in world coordinates and descendant inclusion/tracking; this remains a protocol choice pending pilot validation.

## Actual clearance and danger labels

Ground-truth labeling is implemented separately from predictor scoring. At decision step `i`, only evaluator code may read actual states from `i` through the horizon endpoint and true obstacle geometry.

For each actual center trajectory segment, exact segment-to-AABB distance is computed with the existing M3 geometry and reduced by the physical radius `0.026 m`. Boundary interpolation supplies the actual center at an exact nominal horizon endpoint. The primary continuous label is the minimum signed physical clearance over all eligible obstacles and interpolated segments.

For horizon `H`:

- `collision_within_H`: qualifying first contact occurs in `(t, t+H]`.
- `near_collision_within_H`: no qualifying collision occurs in `(t, t+H]` and actual minimum physical clearance is strictly below calibrated `d_near`.
- `danger_within_H`: collision or near collision.
- `time_to_actual_first_danger`: first collision time, otherwise the time of the first threshold crossing into clearance `< d_near`; undefined if neither occurs.

Exact equality to `d_near` is non-dangerous. Windows lacking an observed/interpolable endpoint, complete contact coverage, or geometry are ineligible rather than truncated. Collision and near-miss labels are mutually exclusive for a window.

## Near-danger calibration

No single numerical `d_near` is selected here. Calibration uses exactly `{0.0065, 0.0130, 0.0195, 0.0260}` m, equal to `{0.25r, 0.50r, 0.75r, 1.00r}` for the physical radius `r=0.026 m`. Each is physically interpretable as a fraction of body radius and is larger than the `1e-6 m` M3 geometry tolerance; none derives from method performance. No continuous search or interpolated candidate is permitted.

Pilot checks resolvability only; pilot outcomes cannot select the value. Collision episodes do not participate in candidate selection because contact overrides near-miss classification, but their clearance distributions are reported diagnostically. Using calibration episodes only, label every completed noncollision episode under all four candidates. Select the smallest candidate satisfying: at least 24 near-miss episodes; at least three near-miss episodes in six of eight families; and at most 25% of manifest-intended matched-safe/F8 safe episodes labeled near-miss. Selection uses observed prevalence only through these fixed constraints, never R0/R1/R2 scores. Exact equality is safe; values within `1e-6 m` of a candidate are flagged and the unrounded float determines the label. Because the smallest qualifying candidate always wins, no further tie exists. Persist candidate counts, selected value, source-manifest digest, code digest, and calibration artifact SHA-256 before formal unlock. If none qualifies, calibration fails and the protocol must be amended before formal access. All four candidates form the separately frozen formal sensitivity set, but only the selected value defines primary danger.

## Horizon semantics

Option A, exact nominal time, is frozen. The existing M2 predictor emits points at 0.032 s intervals and a final point exactly at the requested horizon, integrating a shortened final interval when needed. Dense ground truth uses linear position interpolation and shortest-angle yaw interpolation only for the final nominal-time boundary; clearance over the partial final interval is evaluated geometrically.

| Nominal horizon | Full 0.032 s steps | Endpoint lies in transition | Final partial interval |
|---:|---:|---:|---:|
| 0.5 s | 15 full + endpoint in transition 16 | step 16, realized step time 0.512 s | 0.020 s after 0.480 s |
| 1.0 s | 31 full + endpoint in transition 32 | step 32, realized step time 1.024 s | 0.008 s after 0.992 s |
| 2.0 s | 62 full + endpoint in transition 63 | step 63, realized step time 2.016 s | 0.016 s after 1.984 s |

Prediction point counts are 16, 32, and 63 because frozen M2 `_time_offsets` emits positive offsets `0.032, 0.064, ...` strictly below `H` and replaces the first crossing offset with exactly `H`; the decision-time state at offset zero is not a prediction point. Ground-truth windows use `(t, t+H]` for events and `[t, t+H]` for continuous clearance, with the same exact endpoint. Tables and paper text report exact nominal horizons, the 0.032 s source cadence, and boundary interpolation. The final predictor point is already nominal-time and must not be relabeled 0.512/1.024/2.016 s.

Horizon-equivalence tests must cover all three horizons from grid-aligned and nonzero decision indices; assert point counts, exact final offsets, interpolation fractions `0.625`, `0.25`, and `0.5`, inclusion of an event exactly at `t+H`, exclusion at `t` and just after `t+H`, identical endpoint state for a constant-twist analytic trace, correct partial-segment clearance, and ineligibility when the bracketing post-boundary sample is absent.

## Frozen risk conditions

All conditions receive the same decision-time state and eligible static AABBs.

- R0, current clearance: negative of the current footprint-aware minimum signed clearance, with current-overlap indicator as a separate raw signal. It performs no rollout. Current speed is reported as a covariate, not multiplied into the primary score.
- R1, state-only prediction: frozen M2 constant-twist trajectory at the requested exact horizon, followed by frozen M3 geometry. Raw outputs are negative predicted minimum clearance, corridor-entry indicator, TTCf (with non-entry represented as beyond-horizon/undefined as appropriate), spatial score, and temporal score.
- R2, command-conditioned prediction: frozen M2 differential-drive rollout using only the schedule known at decision time, followed by exactly the same M3 geometry and raw outputs as R1.

No combined score is primary. Each raw signal is evaluated separately. R1 and R2 use identical footprint/corridor parameters, horizons, obstacles, aggregation, and missing-value rules. Actual future state is prohibited from all three inputs.

A secondary classical comparator is recommended: constant-velocity straight-line TTC to inflated AABBs. It is reviewer-facing and not part of C2/C3 because R1 already supplies a stronger constant-twist current-motion baseline. Its definition must be frozen before formal access.

## Threshold-free and clearance evaluation

The two primary tests use `danger_within_2.0s` and negative predicted physical clearance: C2 is R1 minus R0 AUPRC; C3 is R2 minus R1 AUPRC. Each claim requires an observed absolute AUPRC improvement of at least `0.05` and a paired episode-stratified 95% bootstrap interval whose lower bound is above zero. C2 and C3 are separate claims; neither substitutes for the other. This rule is frozen before pilot method outputs are inspected.

The `0.05` absolute AUPRC threshold is a preregistered practical-effect floor: a smaller gain is unlikely to justify the added prediction inputs, implementation complexity, and communication-policy coupling, even if a large corpus made that gain statistically distinguishable from zero. Requiring both this floor and a positive paired interval separates practical relevance from sampling uncertainty. This rationale predates all M9 outcomes and is not calibrated from them.

Secondary endpoints are 2.0 s event detection and median uncensored warning lead time at the calibrated false-warning constraint, plus Spearman correlation and MAE for physical-clearance prediction. The 0.5/1.0 s AUPRCs, collision-only and near-only AUPRCs, AUROC, RMSE, Pearson correlation, TTCf, corridor-entry, M3 spatial/temporal scores, precision, recall, and FPR are secondary or descriptive as labeled in result tables. No best-horizon, best-signal, or best-label selection can support C2/C3.

Predicted versus actual minimum physical clearance is evaluated using Spearman correlation as primary association, with Pearson correlation secondary, plus MAE and RMSE. Predictor clearance uses the physical radius for this comparison; uncertainty-inflated M3 clearance remains a separately named risk signal.

Percentile 95% intervals use 10,000 bootstrap replicates at seed `20260901`, resampling episodes within scenario family and giving families equal weight. Paired method differences use the same resampled episode indices. Frames are never independently resampled.

## Warning calibration and event grouping

The primary operating constraint is false-warning events per minute on completed calibration episodes whose observed ground truth contains no collision and never crosses the selected `d_near`. Danger episodes contribute no safe exposure to threshold calibration. A raw threshold crossing becomes an active warning after three consecutive above-threshold logged steps; it ends after three consecutive below-threshold steps. One active run is one warning event. After warning end, a 0.5 s refractory interval suppresses new false-warning counts. These same persistence/refractory rules apply to all methods and formal detection.

For each safe calibration episode compute warning count and eligible duration from the first step with a complete 2.0 s future window through the last such step. The aggregate rate is total warning events divided by total eligible minutes; episode-stratified bootstrap resamples whole episodes and recomputes that ratio. Calibration chooses, separately for each method/raw signal/horizon, the most sensitive observed-score threshold whose upper 95% bootstrap bound is at most `0.5` false warnings/minute. Threshold ties choose the higher/more conservative risk threshold. If no nontrivial threshold produces any true-event warning while meeting the constraint, the method has no qualifying operating point and detection rate is zero; the criterion is never relaxed.

One primary event is allowed per episode. Collision onset is first qualifying physical contact; sustained or intermittent qualifying contact separated by less than 0.5 s is one collision event. A near-miss event is the maximal contiguous interval with `physical_clearance_m < d_near`; gaps shorter than 0.5 s are merged. Its onset is the first interpolated threshold crossing and its anchor is the unique/global minimum-clearance time, with earliest time breaking a tie. Multiple separated intervals are a protocol deviation: retain the episode, use the interval containing the global minimum as primary, and report the others descriptively without extra inferential units.

Every decision window whose `(t,t+H]` contains the same primary onset maps to that one underlying episode event; overlapping positive windows are not independent events. Safe episodes contain none. Warning lead time is onset minus the first qualifying warning in the preceding 2.0 s surveillance interval. Warnings already active at interval start are left-censored and reported separately. Report event detection rate, missed events, median/distribution of uncensored lead time, false warnings/minute, and episode-level false-warning probability. Inference resamples episodes/events, never positive windows.

## Objective exclusions

Eligible machine-readable exclusion codes are `SIMULATOR_CRASH`, `PROCESS_FAILURE`, `INCOMPLETE_LOG`, `NONMONOTONIC_TIME`, `CORRUPT_ARTIFACT`, `HASH_MISMATCH`, `MISSING_CONTACT_STREAM`, `CONTACT_VALIDATION_FAILURE`, `INVALID_GEOMETRY`, `UNDECLARED_GEOMETRY_CHANGE`, `MISSING_PREDICTOR_INPUT`, `MISSING_COMMAND_SCHEDULE`, `COORDINATE_UNIT_MISMATCH`, `DUPLICATE_IDENTITY`, and `TECHNICAL_CONTEXT_SHORTFALL`. Free-text detail is required but cannot replace the code. Exclusion is decided by a method-blind validator before R0/R1/R2 outcomes load. Scenario-role nonrealization is retained as a completed pilot/calibration outcome; in formal it is analyzed by observed ground truth and does not justify replacement.

Never exclude difficult cases, prediction failures, false warnings, missed events, unexpected collisions, adverse outcomes, or episodes because C2/C3 weaken. Every exclusion is immutable, reason-coded, and summarized by split/family/role without method outcomes.

## Pilot acceptance checklist

Pilot acceptance is engineering-only and requires:

- complete step records from initialization through termination;
- contiguous monotonic indices and timestamps equal to runtime basic timestep within tolerance;
- world `x-y` ground plane and `+z` yaw agreement with M2/M3;
- exact 0.026 m label footprint and separately identified 0.037592257 m predictor corridor;
- obstacle AABBs matching Supervisor fields and configured dimensions;
- applied wheel commands and future schedule consistent at every transition;
- reliable qualifying contact identity, onset, persistence, and exclusions;
- exact 0.5/1.0/2.0 s horizon slicing and end-of-episode rejection;
- deterministic configuration/seed reproduction within declared numeric tolerances;
- at least one observed collision, near-miss, and safe completion per family after permitted pilot iteration;
- no R0/R1/R2 performance criterion.

Failure of contact reliability, coordinate agreement, or dense horizon coverage is a hard stop before calibration.

## Analysis decision

C2 and C3 use only the two primary AUPRC contrasts and rules frozen above. Secondary endpoints explain timing and geometry but cannot rescue a failed primary claim. A claim that passes overall but has an adverse paired AUPRC effect below `-0.05` in any family with its required support is reported heterogeneous and does not authorize an unqualified communication GO. Null and adverse results are retained.

## Reproduction boundary

This document authorizes no Webots launch. The next implementation review may add only the files listed in [the implementation inventory](m9a_p_implementation_inventory.md), tests, and immutable pilot/calibration/formal authorities approved separately. Formal generation remains prohibited until pilot acceptance, calibration freeze, and an explicit review.
