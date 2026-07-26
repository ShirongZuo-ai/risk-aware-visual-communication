# Risk-Aware Visual Communication for Mobile Robots

An interpretable Webots research pipeline for asking a narrow question: **when visual communication is byte-constrained, does knowledge of a robot's predefined future command improve which image regions should receive quality?**

The project converts predicted motion and geometric collision risk into image-space regions of interest (ROIs), applies deterministic byte-fair tiled JPEG allocation, and evaluates reconstructions at the episode level. The final M6 result is a useful negative baseline: command conditioning did **not** improve the preregistered downstream recall measure in the eligible subset.

> **M6 result.** The original eight-scene support gate is **NOT EVALUATED** because three scene strata contain no eligible trajectory-critical obstacles. Under the committed eligibility-conditional amendment, the gate is **FAIL**: command-conditioned minus state-only TCOBR is **0.000**, with a 95% CI of **[0.000, 0.000]** (`n=17` eligible episodes). At Low budget, command conditioning also reduces full-frame PSNR by **0.169 dB** and SSIM by **0.00318** on average (`n=32`).

All claims are limited to controlled Cyberbotics Webots R2025a simulation with a simulated e-puck. They are not real-robot, physical-network, collision-reduction, or navigation-safety claims.

## Research question

The M6 study isolates one causal comparison under shared geometry, codec, budgets, and evidence:

- **State-only risk ROI:** predicts a 2 s constant-twist trajectory from the current robot state.
- **Command-conditioned risk ROI:** uses the same current state plus the predefined wheel-command schedule already available at the decision time.

Both methods share the frozen e-puck footprint, uncertainty corridor, camera projection, rasterization, tiled-JPEG codec, and four actual-byte budgets. Actual future trajectories, combined masks, oracle masks, fallback, and replacement are prohibited from both allocation paths.

## End-to-end architecture

![M6 Webots-to-analysis pipeline](docs/figures/m6_pipeline.png)

*Figure 1. Trusted evidence path from the Webots scene to episode-level inference. Allocation uses predicted trajectories only; actual-future motion never enters either method. The corresponding vector figure and source table are in [`docs/figures/`](docs/figures/).*

The implementation provides:

1. deterministic scene initialization and synchronized RGB/state capture;
2. method-specific predictor-to-mask provenance with leakage checks;
3. complete-container byte accounting and matched frozen budgets;
4. canonical runtime, aggregate, joint-validation, and completion evidence;
5. strict identity binding across manifest, package, scene, seed, episode, and split;
6. episode-level paired inference with preregistered bootstrap settings.

## Formal M6 study

| Item | Frozen definition |
| --- | --- |
| Dataset | 32 independent formal episodes, 8 scenes, 4 episodes per scene |
| Seeds | 630100–630803 in the immutable v3 extension |
| Snapshots | 4 per episode; 128 total |
| Codec cases | 2 methods × 4 budgets × 4 snapshots = 32 per episode; 1,024 total |
| Budgets | Severe, Low, Medium, High; actual complete-container bytes |
| Statistical unit | Episode; snapshots are pooled before TCOBR inference |
| Primary measure | Trajectory-Critical Obstacle Boundary Recall (TCOBR) |
| Primary contrast | Command-conditioned minus state-only, Severe and Low equally weighted |
| Inference | Within-scene episode bootstrap, 10,000 replicates, seed `20260724` |
| Support rule | PASS only when the 95% percentile-CI lower bound is above zero |

TCOBR uses the method-independent union of the frozen planned and state trajectory corridors to identify critical obstacles. Eligibility requires a sufficiently large clipped projection and enough original-image Canny boundary edges. An episode with no eligible obstacle instance remains undefined; it is never imputed as zero or one.

The complete scientific definition is in the [M6 follow-up protocol](docs/m6_followup_evaluation_protocol.md), and the exact matrix is in the [v3 preregistration](docs/results/m6_multiscene_v3_preregistration.json).

## Results

### Eligibility and support gates

![M6 episode eligibility](docs/figures/m6_episode_eligibility.png)

*Figure 2. Eligibility for all 32 registered episodes. S1, S7, and S8 contain no eligible episodes; S4 contributes two and S5 contributes three. The original eight-scene gate therefore remains NOT EVALUATED. The amended analysis includes all 17 eligible episodes from S2–S6 and weights those five scenes equally.*

![M6 TCOBR forest plot](docs/figures/m6_tcobr_budget_forest.png)

*Figure 3. Eligibility-conditional TCOBR paired effects. Every budget and the Severe/Low primary contrast are exactly zero, with 95% CIs [0, 0]. The amended gate fails because its lower confidence bound is not above zero.*

| TCOBR contrast | Episodes | Effect | 95% CI | Decision |
| --- | ---: | ---: | ---: | --- |
| Original S1–S8 gate | — | — | — | **NOT EVALUATED** |
| Conditional Severe + Low | 17 | 0.000 | [0.000, 0.000] | **FAIL** |
| Severe | 17 | 0.000 | [0.000, 0.000] | Secondary |
| Low | 17 | 0.000 | [0.000, 0.000] | Secondary |
| Medium | 17 | 0.000 | [0.000, 0.000] | Secondary |
| High | 17 | 0.000 | [0.000, 0.000] | Secondary |

### Secondary image, byte, and ROI effects

![M6 secondary paired effects](docs/figures/m6_secondary_budget_effects.png)

*Figure 4. Mean episode-level differences across all 32 validated episodes; positive values favor command conditioning. Severe and Low budgets retain the observed full-frame quality degradation. Actual bytes and ROI area are reported rather than treated as benefits.*

| Budget | PSNR (dB) | SSIM | Charged bytes/frame | ROI area (percentage points) |
| --- | ---: | ---: | ---: | ---: |
| Severe | -0.2949 | -0.00537 | +0.3 | +0.003825 |
| Low | -0.1692 | -0.00318 | -12.5 | +0.003825 |
| Medium | +0.0053 | +0.00007 | +14.5 | +0.003825 |
| High | +0.0081 | +0.00010 | +20.4 | +0.003825 |

### Deterministic qualitative comparison

![M6 qualitative comparison](docs/figures/m6_qualitative_comparison.png)

*Figure 5. Original, state-only, and command-conditioned Low-budget reconstructions for the lexicographically first eligible episode (S2, seed 630200), then snapshot 0. This rule was fixed without inspecting effect magnitude. The two reconstructions are pixel-identical for this sample, although container metadata produces a 9-byte charged-size difference.*

## What this project contributes

- An interpretable framework that converts predicted robot-motion risk into visual communication priority.
- A strict dual-ROI boundary that proves which decision-time inputs each predictor may consume.
- Canonical, tamper-checked provenance from synchronized Webots capture through reconstruction and analysis.
- A byte-fair, episode-paired evaluation that preserves null, negative, and undefined outcomes.
- A reproducible negative baseline showing that adding a known command schedule is not sufficient, by itself, to improve TCOBR in this study.

These are engineering and experimental contributions. The repository does **not** establish a novel learned allocator, calibrated collision probability, state-of-the-art performance, or improved robot safety.

## Limitations

- Only 17 of 32 formal episodes are TCOBR-eligible, and three complete scene strata are empty.
- TCOBR is an edge-based reconstruction measure, not detector accuracy, navigation success, collision rate, or human teleoperation quality.
- The 160×120 camera, static AABB scenes, deterministic command schedules, and tiled JPEG prototype limit external validity.
- Both methods are heuristic geometric baselines; neither learns budget-dependent task utility.
- The zero TCOBR difference may reflect identical decisions at the frozen operating points, metric saturation, insufficiently discriminative scenes, or genuinely absent command value. The current evidence does not distinguish these mechanisms.
- Simulation evidence has not been validated on physical networks or real robots.

## Reproducibility

Use Python 3.11 from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m scripts.plot_m6_publication_figures
```

The plotting command reads only the checked JSON/CSV publication sources in [`docs/figures/data/`](docs/figures/data/) and regenerates all five SVG/PNG pairs. Maintainers with the immutable local formal evidence can additionally audit those source tables using:

```powershell
.\.venv\Scripts\python.exe -m scripts.plot_m6_publication_figures --refresh-source-data
```

That audit operation reconstructs the deterministic qualitative sample and requires its image SHA-256 values to match the frozen codec evidence. It does not launch Webots or write experimental data.

Large runtime evidence remains intentionally ignored under `data/m6a/`, and the frozen analysis remains under `results/m6_multiscene_formal_v3/`. The compact publication source tables and figures are tracked so the landing page is reproducible without redistributing the complete runtime corpus.

## Key artifacts

- [Final M6 report](docs/m6_final_report.md)
- [M6 scientific protocol](docs/m6_followup_evaluation_protocol.md)
- [Frozen v3 preregistration](docs/results/m6_multiscene_v3_preregistration.json)
- [Eligibility-conditional amendment](docs/results/m6_v3_eligibility_conditional_analysis_amendment.json)
- [Pre-analysis identity correction](docs/results/m6_v3_preanalysis_identity_correction.md)
- [Publication source data](docs/figures/data/)
- Local frozen analysis: `results/m6_multiscene_formal_v3/analysis_summary.json`
- Local eligible effects: `results/m6_multiscene_formal_v3/episode_effects.csv`
- Local all-episode secondary effects: `results/m6_multiscene_formal_v3/secondary_episode_effects.csv`

### Prior milestone evidence

M6 builds on the accepted M2–M5 geometry, projection, and matched-byte pipeline. The retained public figures are the [trajectory ADE comparison](docs/assets/m2_method_comparison_ade.png), [world-risk geometry](docs/assets/m3_world_risk_overview.png), [M5 primary paired effects](docs/assets/m5e_primary_paired_effects.png), and [M5 scene/budget heterogeneity](docs/assets/m5e_scene_budget_effects.png). Scientific definitions and acceptance evidence remain in the [M5 multi-scene protocol](docs/m5e_multiscene_offline_evaluation_protocol.md), [M5 statistical report](docs/m5e_statistical_analysis_report.md), and [independent M5 acceptance report](docs/m5e_f_independent_acceptance_report.md).

## Repository structure

| Path | Purpose |
| --- | --- |
| `simulator/` | Webots worlds, trusted controller, and runtime adapters |
| `navigation/`, `risk_map/`, `perception/` | Trajectory prediction, risk geometry, and camera projection |
| `compression/`, `evaluation/` | Byte-fair tiled JPEG and image-quality metrics |
| `scripts/` | Evidence production, validation, analysis, and plotting entry points |
| `tests/` | Unit, integration, tamper, lifecycle, and statistical regressions |
| `docs/` | Protocols, decisions, reports, roadmap, and publication figures |
| `data/`, `results/` | Ignored local runtime evidence and frozen generated analyses |

## Next milestone

The next research milestone is **budget-conditioned visual value of information**: jointly model risk, visible coverage, and downstream task utility per additional actual encoded byte. The next study should first create more discriminative, eligibility-rich scenes and an offline counterfactual tile-quality dataset; it should then compare a deterministic greedy value-per-byte allocator with the current state-only and command-conditioned heuristics. No claim of improved safety should be made until a separate closed-loop task protocol measures it.

See the [Risk-VoI experiment plan](docs/m6_risk_voi_experiment_plan.md) for the existing design boundary.
