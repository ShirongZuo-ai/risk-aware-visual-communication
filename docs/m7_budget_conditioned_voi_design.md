# M7 Budget-Conditioned Visual Value-of-Information Design

## Status

This memo freezes a deterministic offline design target. It does not implement, tune, or validate a new allocator and does not authorize Webots. The M6 `state_only_risk_roi` and `command_conditioned_risk_roi` methods remain immutable baselines.

## Allocation unit and causal inputs

M7 starts with the existing 8x6, 20x20-pixel tile grid and frozen JPEG/container accounting so differences are attributable to allocation rather than codec changes. At each decision time it may read the current RGB frame, current robot state, the already-available command schedule, camera/projection configuration, and method-independent current-frame obstacle/visibility estimates. Actual future trajectory, future frames, outcome labels, ground-truth future motion, M6 formal effects, and method-specific evaluation masks are forbidden.

For each tile `t`, compute four `[0,1]` fields using one shared projection:

- `R_t`: normalized collision-risk mass from the union of state-only and command-conditioned risk corridors;
- `C_t`: fraction of projected trajectory-corridor support covered by the tile;
- `V_t`: visible obstacle-boundary support that would newly receive the candidate quality level;
- `U_t`: normalized projected uncertainty mass, including corridor width and visibility uncertainty.

The initial deterministic task weight is the untuned equal-weight mean:

```text
W_t = 0.25 R_t + 0.25 C_t + 0.25 V_t + 0.25 U_t
```

For each allowed one-step JPEG-quality upgrade `k -> k+1`, encode the current source tile at both qualities. Let `delta_D_t,k` be the reduction in a method-independent diagnostic distortion consisting of 50% visible-boundary MSE, 30% projected-corridor MSE, and 20% whole-tile MSE. Empty component masks transfer their weight proportionally to the remaining defined components. Let `delta_B_t,k` be the exact positive change in transmitted complete-container bytes, including any changed header or signaling bytes.

```text
VoI_t,k = (0.01 + W_t) * delta_D_t,k / delta_B_t,k
```

The `0.01` term keeps a positive reconstruction-benefit path for tiles with zero current task support; it is not a learned parameter. Starting from the lowest shared quality, repeatedly apply the feasible positive-benefit transition with maximum `VoI_t,k`. Recompute exact complete-container bytes after each transition. Ties are resolved by lower row-major tile ID and then lower target quality. Stop when no positive-benefit transition fits. Over-budget output, fallback, replacement, nonmonotone/zero byte increments, or missing component provenance fails closed.

The output records every component map, candidate distortion/byte increment, chosen transition, tie break, final tile qualities, charged bytes, and canonical digest. An offline oracle may solve the same finite candidate set for comparison, but is explicitly non-deployable.

## Offline development separation

M5/M6 data may be used only to reproduce the diagnosis and verify compatibility. Allocator component weights, thresholds, or candidate rules cannot be tuned against M6 outcomes. Development, threshold selection, and final offline evaluation require new disjoint identity sets, with the final evaluation frozen before outcomes are inspected.

## Go/no-go gates before any Webots experiment

All gates are conjunctive and evaluated on the frozen held-out offline split.

1. **Integrity and leakage:** 100% identity coverage; zero missing/duplicate cases, non-finite values, fallback/replacement, actual-future reads, or method-specific evaluation inputs; deterministic rerun hashes match.
2. **Eligibility richness:** TCOBR is defined in at least 6/8 scenes and 75% of episodes, with at least three eligible episodes in every included scene. Undefined scenes are never imputed.
3. **Allocation actuation:** at Severe and Low, at least 75% of snapshots differ from each frozen baseline in at least 10% of tile-quality assignments. This prevents another nominal-method/identical-allocation study.
4. **Byte fairness:** every case remains at or below the common target; zero fallback; mean utilization differs from each baseline by at most 0.5 percentage points; all overhead is charged.
5. **Critical coverage:** relative to the better frozen baseline, mean critical-boundary high-quality coverage improves by at least 10 percentage points at both Severe and Low, and the episode-level scene-stratified 95% CI for the Severe/Low average has lower bound above zero.
6. **Offline task utility:** the preregistered episode-level command-independent TCOBR/continuous-boundary-utility contrast against the better frozen baseline has a positive 95% scene-stratified CI lower bound. Null and adverse scenes remain included.
7. **Quality safeguard:** critical-region PSNR is non-inferior within 0.25 dB at both primary budgets, and full-frame PSNR degradation is no worse than 1.0 dB relative to the better baseline.
8. **Heterogeneity:** no single scene contributes more than 50% of the aggregate paired gain, and no eligible scene has a mean TCOBR loss worse than 0.05.
9. **Reproducibility:** source tables, allocator provenance, bootstrap inputs, and figures regenerate byte-for-byte using one documented command.

A failed gate is a **NO-GO** for Webots and triggers offline redesign or a separately reviewed measurement-coverage study. Passing these gates supports only a new pre-registration proposal; it is not itself launch approval.
