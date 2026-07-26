# M6 Publication Figures

All M6 figures are presentation-only derivatives of frozen evidence. Each figure is provided as SVG and 360-dpi PNG. The renderer uses DejaVu Sans, fixed dimensions, a colorblind-safe palette, fixed budget ordering, and a fixed SVG hash salt.

Regenerate all figures from the checked publication source data:

```powershell
.\.venv\Scripts\python.exe -m scripts.plot_m6_publication_figures
```

Release maintainers with the immutable local formal corpus can re-extract and validate the source tables before rendering:

```powershell
.\.venv\Scripts\python.exe -m scripts.plot_m6_publication_figures --refresh-source-data
```

The refresh path does not run Webots or modify experiment artifacts. It fails if frozen coverage, gates, effects, sample hashes, or codec reconstruction hashes differ.

| Figure | Source data | Scope |
| --- | --- | --- |
| `m6_pipeline.{svg,png}` | `data/m6_pipeline_nodes.csv` | Frozen end-to-end architectural stages |
| `m6_episode_eligibility.{svg,png}` | `data/m6_episode_eligibility.csv` | 32 registered episodes; 17 eligible and 15 undefined |
| `m6_tcobr_budget_forest.{svg,png}` | `data/m6_tcobr_budget_effects.csv` | Conditional TCOBR effects and 95% CIs, `n=17` |
| `m6_secondary_budget_effects.{svg,png}` | `data/m6_secondary_effects.csv` | PSNR, SSIM, bytes, and ROI area, `n=32` |
| `m6_qualitative_comparison.{svg,png}` | `data/m6_qualitative_source.json` | Frozen original and hash-verified reconstructions |

The qualitative rule is fixed independently of results: select the lexicographically first eligible episode, then snapshot `0` and the Low budget. This yields S2 seed 630200. The JSON stores the original and reconstructed RGB bytes as base64 together with SHA-256, recorded metrics, source-evidence paths, and the rule itself. It does not select the largest, smallest, or most visually appealing effect.
