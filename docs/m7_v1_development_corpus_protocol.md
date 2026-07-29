# M7 v1 Development Corpus Protocol

Status: frozen before data generation
Role: allocator development and offline gate preparation; not formal inference

## Purpose and non-adaptive selection

M7 v1 supplies the first identity-disjoint evidence for developing the deterministic budget-conditioned Visual-VoI allocator. The complete matrix is fixed before Webots execution and before any RGB, codec, TCOBR, or reconstruction outcome is observed. Every registered episode is retained. There is no replacement pool, outcome-based exclusion, retry, or post-hoc scene selection.

The corpus contains exactly 16 episodes, four snapshots per episode, the two frozen M6 methods, and four frozen byte budgets. Expected scale is 64 trusted RGB snapshots and 512 exact-container codec cases. The allocator itself is not implemented or evaluated during corpus generation.

## Frozen matrix

| Scene | Seeds | Role | Predeclared geometry |
|---|---|---|---|
| M7C1 | 710100–710101 | straight critical | visible AABB intersects the frozen planned/state corridor union |
| M7C2 | 710200–710201 | left-turn critical | visible AABB intersects the frozen corridor union |
| M7C3 | 710300–710301 | right-turn critical | mirrored visible critical event |
| M7C4 | 710400–710401 | trajectory-disagreement critical | inner-turn visible critical event |
| M7C5 | 710500–710501 | late-turn critical | visible event before the late turn |
| M7C6 | 710600–710601 | S-curve critical | visible event under changing curvature |
| M7G1 | 710700–710701 | low-risk generalization | visible obstacle remains outside both corridors |
| M7G2 | 710800–710801 | low-risk turn generalization | visible obstacle remains outside both corridors |

Scene geometry is generated only from the scene ID and seed. Critical scenes pass a pre-run analytic check at the declared snapshot: the obstacle AABB intersects at least one frozen 2.0 s trajectory corridor and its clipped 160x120 projection contains at least 64 pixels. Generalization scenes pass only when no obstacle intersects either corridor at any registered snapshot. These checks use geometry, schedules, camera calibration, and frozen risk parameters—not rendered images or task/codec outcomes. They do not guarantee the later Canny-edge eligibility condition.

## Information boundary

Allocator-visible sender-time evidence is limited to:

- the trusted current RGB frame;
- current robot pose and wheel-derived twist at the snapshot;
- the predefined command schedule available at time zero;
- the fixed 2.0 s/0.032 s prediction and uncertainty configuration;
- the sender camera/projection context;
- predicted trajectory/corridor artifacts derived from those inputs.

The following remain evaluator-only and are forbidden from runtime configuration, method masks, allocation, and codec decisions:

- obstacle AABBs and critical-event declarations;
- actual future robot motion or trace;
- TCOBR eligibility, boundary labels, recall, or task outcomes;
- any reconstruction or codec result used to select an episode.

Evaluator-only geometry is stored in each immutable manifest record. After runtime and before host-side validation, it is copied to a separate canonical `evaluator_only_geometry.json` artifact and bound to the final marker. It is never added to snapshot metadata or the sender runtime configuration.

## Runtime and evidence contract

The existing v4 prepared-package, local research runner, ownership, at-most-once claim, process evidence, runtime manifest, 32-case byte-fair codec aggregate, joint validation, final marker, and completed ownership terminal remain authoritative. Each successful episode must contain:

- four distinct `raw/*.rgb` frames and canonical metadata;
- sender-time state, schedule, projection context, and serialized state-only/command-conditioned trajectories and corridors;
- `evaluator_only_geometry.json` in its isolated evaluator domain;
- 32 cases charging exact payload, mask, metadata, and complete-container bytes;
- zero prohibited future use, combined mask use, fallback, replacement, or retry;
- validated runtime, aggregate, joint, final, and ownership evidence.

The retained method set is exactly `state_only_risk_roi` and `command_conditioned_risk_roi`. The retained complete-container targets are severe 31,466, low 32,374, medium 33,509, and high 34,871 bytes. M7 corpus generation does not add the Visual-VoI method.

## Authority, immutability, and disjointness

The authoritative files are:

- `docs/results/m7_v1_episode_source_manifest.json`
- `docs/results/m7_v1_episode_source_manifest.lock.json`
- `docs/results/m7_v1_development_preregistration.json`

The lock binds canonical manifest bytes, source adapter, scene generator, base world, and frozen M6 v2/v3 parent hashes. Validation reconstructs all records and rejects canonical, digest, scene, seed, split, geometry, or parent-authority tampering. The 710xxx identities are checked against all M5 primary/replacement seed authority, both M6 manifests, historical prepared packages, and persisted runtime summaries.

## Execution and stop rules

All code, tests, protocol, manifest, lock, and the complete matrix must be committed before package creation. Every package must bind that exact clean HEAD and select one exact `development` record. All 16 prospective roots must be absent before the first launch.

The approved batch order is manifest order: M7C1 through M7C6, then M7G1 and M7G2, with ascending seed inside each scene. Each identity launches once. There are no retries. Any shared infrastructure, schema, information-boundary, byte-accounting, runtime, aggregate, or joint-validation defect stops all remaining launches. Episode-specific failure is retained truthfully and also stops this first corpus build for review.

Passing corpus validation establishes a development dataset only. It does not pass M7 offline go/no-go gates, authorize a new formal 720xxx split, or support a scientific effect claim.
