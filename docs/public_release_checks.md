# Public Release Checks

Last checked: 2026-07-20

This file records the public-release audit for the repository state prepared for GitHub publication. It is a publication-safety note only; it does not modify or reinterpret experimental outputs.

## Git And Branch Safety

- Active branch during preparation: `feature/m5-risk-roi-compression`.
- Local `main` exists and was verified as an ancestor of the active branch with `git merge-base --is-ancestor main HEAD`.
- Existing safety stashes were listed and left untouched.
- No rebase, reset, stash apply/drop, history rewrite, or force push was used during preparation.

## Public Risk Scan

- Tracked files were scanned for common API keys, GitHub tokens, private-key blocks, password/secret patterns, and credential terms.
- No `.env`, private key, virtual environment, Python cache, Webots project file, or log file is tracked.
- No tracked file exceeds 20 MB.
- Generated `data/`, `results/`, local Webots GUI files, virtual environments, caches, logs, and temporary files remain ignored unless a small curated artifact is copied into `docs/` for public explanation.
- Personal local paths and local Git identity details were removed from public-facing progress notes where they were not required for reproducibility.

## Metric Verification

The CV-style trajectory metrics are supported by the Milestone 2 in-place rotation validation summary:

- Prediction horizon: `2.0 s`.
- Evaluation category: `all_stable`, aggregating stable windows only.
- State-only stable-window ADE: `0.000715992 m`, reported as `7.16e-4 m` when rounded to three significant figures.
- Command-conditioned stable-window ADE: `0.000013655 m`, reported as `1.37e-5 m` when rounded to three significant figures.
- Public summary rows: `docs/results/m2_in_place_summary_metrics.csv`.
- Original local generated artifact: `results/m2_trajectory/summary_metrics.csv`.
- Evaluation implementation: `scripts/evaluate_m2_trajectory.py`.

These are controlled Webots simulation results. They are not real-world robot performance, deployed-system performance, or hardware experiments.

## License Status

No repository license file is present. A license should be selected before broader reuse is encouraged.
