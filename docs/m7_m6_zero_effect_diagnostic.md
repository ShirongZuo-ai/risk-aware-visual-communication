# M7 Frozen-M6 Zero-Effect Diagnostic

## Scope and evidence boundary

This study diagnoses the frozen M6 v3 result without changing or regenerating any experiment. It strictly reloads all 32 finalized formal episodes, 128 snapshots, and 1,024 codec cases, regenerates both trusted masks, reproduces every codec/evaluation digest, and writes only derived tables and figures under `docs/`. Pilot, smoke, M5, and failed-attempt evidence is not analyzed.

The command-conditioned-minus-state-only TCOBR result remains the preregistered null result. This report explains the observed mechanism; it is not a post-hoc positive hypothesis test and does not evaluate the proposed M7 allocator.

## Diagnostic definitions

- **ROI overlap:** Jaccard and XOR over the two frozen binary 160x120 masks.
- **Tile-selection overlap:** Jaccard and XOR over the frozen 8x6 grid; a tile is selected when any ROI pixel lies inside it.
- **Actual allocation change:** fraction of tiles whose final JPEG quality differs after the complete-container budget search.
- **Critical-region bytes:** sum of JPEG payload bytes for tiles intersecting the method-independent union of projected trajectory-critical obstacle polygons. Signaling and container overhead remain included in the separately validated charged-byte total and are not attributed to individual regions.
- **Boundary coverage:** fraction of original-image Canny boundary pixels belonging to critical obstacles that lies within tiles whose selected JPEG quality is above the frame's background quality.
- **Critical-region quality:** masked RGB PSNR over the projected critical-obstacle union. Eligible-boundary PSNR is also retained in the checked case table.
- **Absolute TCOBR:** eligible/recalled instances are pooled across the four snapshots before the episode ratio is calculated, exactly as in M6.

## Confirmed cause

The zero effect is explained by a three-stage allocation collapse.

1. The bridge rasterized predicted trajectory sample points rather than a dense projected corridor. Across 128 snapshots the state-only mask averages **8.844 pixels** and the command-conditioned mask **9.578 pixels** out of 19,200.
2. Although pixel-mask Jaccard is 0.754, only **0.0197% of pixels** differ. The 8x6 tile policy collapses this further: tile-selection Jaccard is 0.969 and only **0.1302% of tiles** differ.
3. After the byte-fair quality search, the reconstruction is identical for **85.16% / 90.63% / 93.75% / 93.75%** of Severe/Low/Medium/High snapshot pairs. Quality-map differences average 8.72%, 3.26%, 0.13%, and 0.13%, respectively; the larger Severe/Low percentages are concentrated in a few snapshots where a small signaling change moves the whole frame to an adjacent candidate quality, not in sustained critical-region targeting.

TCOBR then has little remaining sensitivity. Both methods have the same 17 defined episodes at every budget. Absolute episode TCOBR is **0.9412** at Severe, **1.0000** at Low, **0.9412** at Medium, and **1.0000** at High for both methods. Sixteen or seventeen of 17 episodes are exactly at 1.0, so the endpoint is near ceiling as well as allocation-invariant.

## Critical-region allocation and quality

Command conditioning increases mean high-quality critical-boundary coverage by only **0.595 percentage points** (11.91% to 12.50%). Mean critical-region tile-payload differences are +1.0, -2.0, +7.6, and +7.6 bytes at Severe, Low, Medium, and High. Mean command-minus-state critical-region PSNR is -0.045, -0.119, +0.016, and +0.016 dB. These magnitudes are descriptive and do not support a task advantage.

The scene/budget table exposes concentration rather than a hidden broad effect. S1 and S8 have identical reconstructions at all budgets. Medium/High are identical in S2 and S5-S8; S3/S4 differ in only 0.52% of tile qualities while retaining identical TCOBR. S2 is the only scene with a non-ceiling mean at Severe/Medium (0.75), but both methods share it.

## Why S1, S7, and S8 are empty

Counts below are method-independent obstacle-snapshot instances over four episodes per scene.

- **S1:** eight critical instances project adequately but each contains fewer than 16 original-image Canny boundary pixels; eight other instances are not trajectory-critical.
- **S7:** eight critical instances fail the same 16-edge eligibility threshold; 24 are not trajectory-critical.
- **S8:** all 16 instances are outside both frozen trajectory corridors. No obstacle reaches the criticality gate.

No undefined episode is imputed. The diagnosis confirms a scene/measurement-coverage limitation rather than evidence corruption.

## Reproduction

Render from checked source tables:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_m6_diagnostics
```

Maintainers who possess the immutable local M6 evidence can re-extract, strictly validate, and render:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_m6_diagnostics --refresh-source-data
```

The refresh takes several minutes because it reproduces all 1,024 codec/evaluation records. It fails closed on package, runtime, raw-frame, mask, aggregate, geometry, case, evaluation, or reconstruction mismatch.

## Artifacts

- Summary: `docs/results/m7_m6_diagnostic_summary.json`
- Checked tables: `docs/figures/data/m7_*.csv`
- Figures: `docs/figures/m7_*.{svg,png}`
- M7 design: `docs/m7_budget_conditioned_voi_design.md`

The next priority is an offline-only, disjoint-data implementation of the deterministic allocator in the design memo. No Webots study is authorized by this diagnostic.
