# M8-A Scientific Design: Proxy Qualification Before Allocation

## Status

M8-A is a design and preregistration milestone. It does not implement an allocator, generate a corpus, calculate experimental outcomes, authorize Webots, or create a formal split.

The recommended strategy is to qualify two sender-available proxy families on a new, disjoint calibration split before any allocation development. Calibration uses deterministic method-independent perturbations, isolated evaluator-only references, scene-stratified tests, and a fixed selection rule. This directly addresses M7 v1's quality/byte failures and M7 v2's unvalidated, single-scene task signal without selecting a proxy because it favors an existing method.

## Frozen inheritance

M7 v1/v2 remains a completed `NO-GO` baseline. M8 retains:

- matched actual complete-container bytes;
- utilization gap no greater than 0.5 percentage points from both frozen baselines;
- the highest feasible uniform minimum-quality floor;
- deterministic task-directed one-step upgrades;
- full container-byte recomputation for every candidate transition;
- deterministic tile-ID and target-quality tie-breaking;
- zero leakage, fallback, and replacement;
- TCOBR as a non-degradation safety metric rather than an optimization target.

The M7 corpus cannot be used to tune, qualify, or choose an M8 proxy.

## Measurement question

Can a deterministic score computed entirely from information available at the sender distinguish task-relevant reconstruction degradation continuously, across scenes and budgets, before that score is used to allocate a byte?

The two frozen-for-calibration candidates are defined in `docs/m8_a_proxy_comparison.md`:

1. FROPU: fixed RGB obstacle-proposal preservation;
2. STRCF: sender-time risk-weighted continuous RGB/gradient fidelity.

Neither is presently validated. CCORF is an evaluator-only calibration reference and cannot enter allocator inputs, provenance, or scoring.

## Information boundary

### Allowed at sender decision time

- current trusted RGB;
- candidate local reconstructions and exact charged bytes;
- current robot state;
- predefined command schedule whose availability time is no later than the snapshot timestamp;
- predicted state-only and command-conditioned trajectories, corridors, risk, and uncertainty;
- frozen camera/projection and proxy configuration;
- fixed FROPU outputs computed from the current original/reconstruction pair.

### Evaluator only

- obstacle AABBs and projected ground-truth masks/boundaries;
- critical-obstacle labels, eligibility, CCORF, and TCOBR;
- actual future trajectory, future frames, and downstream outcomes.

The calibration harness must create sender and evaluator views separately. A proxy artifact fails closed if its input schema or provenance contains an evaluator-only field, future datum, unknown field, fallback, or replacement.

## Independent calibration procedure

The complete calibration identities are frozen before any RGB outcome. For each trusted snapshot, produce a method-independent perturbation panel using the existing codec and exact container accounting:

- uniform JPEG quality levels `5, 15, 35, 55, 75, 95`;
- critical-local degradation and equal-area noncritical-local degradation, constructed by the evaluator only and never exposed to the proxy;
- matched-byte reconstruction pairs whose actual complete-container difference is at most 0.5 percentage points of the common budget;
- deterministic repeat encodes for every panel item.

Both proxies are computed from their sender view. CCORF, TCOBR, geometry, and perturbation class are joined only after all proxy artifacts validate. Full-frame PSNR is a preregistered negative-control predictor.

### FROPU detector prerequisite

Before FROPU proxy statistics are evaluated, its original-image proposals must achieve all of:

- visible critical-obstacle recall at least `0.85` overall;
- recall at least `0.70` in every critical scene;
- no more than `2.0` false-positive proposals per frame on average;
- median matched proposal IoU at least `0.50` and 10th-percentile IoU at least `0.30`;
- exact deterministic proposal output on repeat input.

Failure rejects FROPU without changing its thresholds.

### Common proxy qualification gates

Each candidate must pass all gates in `docs/results/m8_a_proxy_validation_rules.json`:

1. complete identity coverage, finite values, zero prohibited inputs, and exact tamper rejection;
2. at most 10% of defined observations at either exact endpoint and median within-episode range at least 0.15;
3. quality-ladder monotonicity: scene-stratified Spearman correlation at least 0.80 in at least 80% of critical episodes;
4. association with CCORF: equal-scene Spearman at least 0.60 with 95% bootstrap lower bound above 0.40;
5. pairwise CCORF ranking concordance at least 0.75 with 95% lower bound at least 0.65;
6. stronger response to critical-local than matched-byte noncritical-local degradation, with 95% CI lower bound above zero;
7. every critical scene has association at least 0.40 and no scene supplies more than 35% of positive covariance;
8. CCORF association exceeds full-frame PSNR by at least 0.05 with a positive 95% CI lower bound;
9. all source tables, proxy artifacts, statistics, and figures reproduce byte-for-byte.

Statistics use episode as the unit, resample episodes within scene, weight critical scenes equally, use 10,000 bootstrap replicates with seed `20260724`, and report percentile 95% intervals. Undefined domains remain undefined and are not imputed.

### Fixed selection rule

- If FROPU passes its detector prerequisite and all common gates, and STRCF passes all gates, select FROPU as primary and STRCF as safeguard.
- If exactly one candidate passes its applicable gates, select that candidate.
- If neither passes, record `NO-GO`; do not implement an allocator.
- Selection never uses allocator output, baseline improvement, or effect direction from M7.

Passing calibration authorizes only a separate proxy-freeze review. It does not authorize allocator development, corpus generation, or Webots.

## Proposed M8 corpus authority

The proposed matrix is machine-readable at `docs/results/m8_a_proposed_corpus_matrix.csv`. It contains ten scenes and three disjoint splits:

| Split | Critical scenes | Generalization scenes | Episodes | Purpose |
| --- | ---: | ---: | ---: | --- |
| calibration | 8 x 3 | 2 x 2 | 28 | qualify and select a proxy only |
| development | 8 x 4 | 2 x 4 | 40 | develop an allocator after proxy freeze |
| formal | 8 x 4 | 2 x 4 | 40 | final inference after allocator preregistration |

Planned seed families are `810xxx`, `820xxx`, and `830xxx`, respectively. They are proposals, not an authoritative launch manifest. A later approval must create versioned manifests and locks and rerun disjointness against all evidence then present.

### Critical-scene coverage

| Scene | Trajectory | Range | Side | Visibility |
| --- | --- | --- | --- | --- |
| M8C1 | straight | near | left | full |
| M8C2 | straight | near | right | full |
| M8C3 | straight | far | left | full |
| M8C4 | straight | far | right | full |
| M8C5 | left turn | near | left | full |
| M8C6 | right turn | near | right | full |
| M8C7 | left turn | far | left | partial occlusion |
| M8C8 | right turn | far | right | partial occlusion |

M8G1 is a straight low-risk off-corridor scene and M8G2 is a turning low-risk off-corridor scene. Generalization scenes remain in secondary robustness summaries and cannot replace a failed critical scene.

### Pre-launch geometry gates

All checks use scene configuration, frozen projection, and planned trajectories before image or codec outcomes:

- a critical obstacle AABB intersects the union of frozen state and planned corridors at a registered snapshot;
- near depth is `0.35-0.65 m`; far depth is `0.80-1.20 m`;
- full-visibility projected area is at least 128 pixels with clipped-visible fraction at least 0.80;
- partial-occlusion projected area is at least 64 pixels with clipped-visible fraction from 0.25 through 0.60;
- projected centroid is at or left of column 72 for left scenes and at or right of column 88 for right scenes in the 160-pixel image;
- straight scenes change yaw by at most 5 degrees over the critical interval; turning scenes change yaw by at least 30 degrees;
- generalization obstacles do not intersect either corridor and remain at least `0.15 m` from the union corridor boundary;
- every record has exactly four registered snapshot identities and no overlap with any prior seed or identity.

A split is generated exactly as registered. A failing record is retained truthfully; no replacement is selected after observing RGB, codec, proxy, or task outcomes.

### Realized eligibility gates

Before calibration inference, at least 2/3 episodes in each M8C scene must contain a defined CCORF/TCOBR-eligible event. Before allocator development or formal inference, at least 3/4 episodes in each M8C scene must be eligible. If a critical scene misses its threshold, the phase is `NO-GO`; episodes are not imputed or replaced.

## Phase order

1. **M8-A:** accept this design only; no data and no allocator.
2. **M8-B0:** implement and test both proxy candidates and isolated evaluator reference.
3. **M8-B1:** freeze a calibration manifest/lock, generate it under separate launch approval, and qualify proxies.
4. **M8-B2:** freeze the selected proxy only if all gates pass.
5. **M8-C:** implement allocator candidates on the disjoint development split, retaining the M7 v2 byte and quality mechanisms.
6. **M8-D:** preregister one allocator and the formal matrix before any formal outcome.

No step may be skipped, and later phases cannot amend earlier evidence after outcomes are visible.

## Claims boundary

M8-A supports a measurement-validation plan, not a validated proxy, superior allocator, improved obstacle perception, safer navigation, or collision reduction. FROPU and STRCF are unimplemented candidates. The next priority is offline implementation and unit validation of the two proxy pipelines and CCORF isolation, before any Webots corpus is proposed.
