# Publication Figures

All figures are presentation-only derivatives of frozen repository evidence. Each is exported as SVG and 360-dpi PNG with DejaVu Sans, fixed dimensions, a colorblind-safe palette, fixed budget ordering, and a deterministic SVG hash salt.

Regenerate every figure from the checked publication source tables:

```powershell
.\.venv\Scripts\python.exe -m scripts.plot_m6_publication_figures
```

Release maintainers with the immutable local evidence can re-extract, validate, and render in one command:

```powershell
.\.venv\Scripts\python.exe -m scripts.plot_m6_publication_figures --refresh-source-data
```

The refresh path never runs Webots or modifies experimental evidence. It fails closed if frozen coverage, lifecycle completion, budgets, gates, effects, sample hashes, or codec reconstruction hashes differ.

M7 diagnostic figures regenerate from checked derived sources with:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_m6_diagnostics
```

Maintainers with the immutable local M6 corpus may add `--refresh-source-data` to reproduce all 1,024 frozen codec/evaluation cases before rendering. The extractor writes only `docs/` derivatives and fails closed on any evidence mismatch.

| Figure | Checked source data | Frozen upstream source | Scope |
| --- | --- | --- | --- |
| `m6_capability_evolution.{svg,png}` | `data/m6_capability_evolution.csv` | milestone reports listed per row | Verified M1-M6 capability progression; not a method-effect claim |
| `m6_study_scale_validation.{svg,png}` | `data/m6_study_scale_validation.csv` | v3 preregistration plus runtime, aggregate, process, final-marker, and ownership evidence | 8 scenes, 32 episodes, 128 snapshots, 1,024 cases, 32 finalized, 0 retries |
| `m6_pipeline.{svg,png}` | `data/m6_pipeline_nodes.csv` | `docs/m6_final_report.md` and production call chain | Frozen end-to-end architecture |
| `m6_absolute_budget_quality.{svg,png}` | `data/m6_absolute_budget_quality.csv` | `results/m6_multiscene_formal_v3/analysis_summary.json`; budget targets from `docs/results/m6a_v3_episode_source_manifest.json` | Absolute PSNR, SSIM, actual bytes, and targets, `n=32` |
| `m6_qualitative_comparison.{svg,png}` | `data/m6_qualitative_source.json` | hash-bound raw frame and codec aggregate named in the JSON | Original and Severe/High reconstructions for one deterministic sample |
| `m5_primary_baseline_effects.{svg,png}` | `data/m5_primary_baseline_effects.csv` | `docs/results/m5e_publication_figure_snapshot.json` | Risk ROI versus all three M5 baselines at Severe and Low, `n=64` |
| `m6_episode_eligibility.{svg,png}` | `data/m6_episode_eligibility.csv` | v3 preregistration and frozen analysis summary | 32 episodes; 17 eligible and 15 undefined |
| `m6_tcobr_budget_forest.{svg,png}` | `data/m6_tcobr_budget_effects.csv` | frozen eligibility-conditional analysis summary | TCOBR effects and 95% CIs, `n=17` |
| `m6_secondary_budget_effects.{svg,png}` | `data/m6_secondary_effects.csv` | frozen analysis summary | Paired PSNR, SSIM, bytes, and ROI-area effects, `n=32` |
| `m7_allocation_divergence.{svg,png}` | `data/m7_allocation_overlap.csv` | frozen v3 mask and codec evidence | Pixel/tile/final-quality divergence and identical reconstructions, 128 snapshots |
| `m7_absolute_tcobr.{svg,png}` | `data/m7_episode_absolute_tcobr.csv` | frozen v3 TCOBR evidence | Absolute episode TCOBR by method and budget, 17 defined episodes |
| `m7_critical_region_diagnostics.{svg,png}` | `data/m7_case_diagnostics.csv` | hash-reproduced frozen reconstructions and method-independent TCOBR geometry | Critical tile bytes, boundary high-quality coverage, and masked PSNR |
| `m7_empty_scene_diagnosis.{svg,png}` | `data/m7_empty_scene_reasons.csv` | frozen TCOBR instance eligibility | Method-independent reason counts for S1-S8 |
| `m7_scene_budget_failure_patterns.{svg,png}` | `data/m7_scene_budget_patterns.csv` | derived from frozen overlap/case/episode tables | Quality-map divergence and reconstruction identity by scene/budget |
| `m7_visual_voi_gates.{svg,png}` | `data/m7_visual_voi_gates.csv` | completed M7 v1 development corpus and frozen nine-gate definitions | All nine conjunctive offline gate decisions |
| `m7_visual_voi_allocation_divergence.{svg,png}` | `data/m7_visual_voi_cases.csv` | M7 v1 trusted snapshots plus frozen baseline and Visual-VoI quality maps | Fraction of changed tile qualities by budget and baseline |
| `m7_visual_voi_task_effects.{svg,png}` | `data/m7_visual_voi_episodes.csv` | method-independent M7 v1 evaluator output | Critical-boundary HQ coverage and episode TCOBR effects by budget |

Regenerate the M7 Visual-VoI evaluation, checked source tables, and figures with:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_visual_voi evaluate
```

This command is offline-only. It reads the immutable M7 v1 corpus, rejects evaluator-only inputs at the allocator boundary, and does not start Webots.

M7 v2 constrained-development figures regenerate from the same immutable corpus with:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_visual_voi_v2 evaluate
```

| Figure | Checked source data | Scope |
| --- | --- | --- |
| `m7_v2_candidate_gates.{svg,png}` | `data/m7_v2_gates.csv` | Nine preregistered gate decisions for all three candidates |
| `m7_v2_task_quality.{svg,png}` | `data/m7_v2_candidate_comparison.csv` | Scene-stratified continuous effect and Severe/Low critical-PSNR safeguard |
| `m7_v2_byte_scene.{svg,png}` | candidate comparison plus `m7_v2_summary.json` scene effects | Exact-byte gap and eligible-scene dependence |

All M7 v2 figures use the frozen candidate set and preserve null, adverse, and single-scene results. They are SVG plus 360-dpi PNG and do not imply formal-study eligibility.

## Deterministic qualitative rule

Select the lexicographically first TCOBR-eligible episode, then snapshot `0`, the fixed `state_only_risk_roi` method, and the frozen Severe/High budget endpoints. This yields S2 seed 630200. The rule does not inspect visual quality or effect size. The JSON stores original and reconstructed RGB bytes as base64, SHA-256 values, recorded metrics, and exact source-evidence paths. High-budget PSNR and SSIM must both exceed the Severe values before rendering.

## Interpretation boundary

The landing-page order separates four levels of evidence:

1. project capability evolution;
2. system and formal-study validation;
3. absolute budget-quality behavior;
4. method-level scientific findings.

The TCOBR forest remains unchanged and is intentionally presented with limitations. The M5 figure is narrowly scoped: it includes Uniform, Center ROI, and Object ROI, preserves adverse Severe effects, and does not imply universal Risk ROI superiority.
