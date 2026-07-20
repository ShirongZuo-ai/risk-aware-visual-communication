# M5E-F Independent Formal Acceptance Report

Last updated: 2026-07-20 (Asia/Shanghai)

## 1. Scope

This acceptance independently checked the frozen M5E-D inputs and the completed M5E-E analysis. It did not change scenarios, seeds, budgets, algorithms, metrics, statistical definitions, formal data, or M5E-E outputs. No exploratory analysis was added.

## 2. Frozen Inputs

- Formal metric table: `data/m5e_formal/formal_evaluation/m5e_d_formal_quality_metrics.csv`.
- Formal evidence: 64 episodes, 256 frames, and 4,096 method-budget reconstructions.
- Coverage: S1-S8, four frozen budgets (`31466`, `32374`, `33509`, `34871` bytes), and Uniform, Center ROI, Object ROI, and Risk ROI.
- Formal replacements: zero. There were no non-finite formal metric cells, no duplicate full `(scene, seed, snapshot, method, budget)` keys, and no missing primary pairs.

## 3. Reproduction Commands

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_m5e_formal_evaluation.py
.\.venv\Scripts\python.exe .\scripts\run_m5e_statistical_analysis.py `
  --formal-root data\m5e_formal `
  --analysis-root results\m5e_f_acceptance_reproduction\analysis `
  --figure-root results\m5e_f_acceptance_reproduction\figures
```

The isolated reproduction completed with 64 episodes, 384 primary pairs, the frozen seed `20260718`, 10,000 bootstrap replicates, and nine figures. It did not overwrite `data/m5e_formal/statistical_analysis/` or `results/m5_compression/m5e_statistics/`.

## 4. Data Integrity

The independent M5E-D validator recomputed and passed the complete formal matrix: 64 episodes, 256 frames, and 4,096 metrics. The primary paired matrix contains 384 valid rows (`64 episodes x 3 baselines x 2 primary budgets`) with zero missing and zero duplicate pair keys. Primary byte fairness used complete containers and passed the frozen 0.5% target-byte tolerance: the only nonzero equal-scenario mean Risk-minus-baseline differences were 24.418 bytes at severe and 17.789 bytes at low versus Uniform, respectively 0.078% and 0.055% of target.

## 5. Statistical Unit

The independent check confirmed that each episode aggregates its four snapshots before inference. Every primary pair preserves scene, original seed, episode, and budget identity. The bootstrap resamples episodes within scenario and then equal-weights the eight scenario means; it does not treat 256 frames as independent observations. Confirmatory primary comparisons are separated from secondary and exploratory diagnostics.

## 6. Key Number Verification

Independent arithmetic directly from the frozen formal metric CSV first averaged the four snapshots per method/episode, formed paired Risk-minus-baseline differences, and equal-weighted eight scenario means. It reproduced the primary RW-PSNR effects (dB):

| Budget | Comparison | Recomputed mean | Reproduced 95% CI |
| --- | --- | ---: | ---: |
| Severe | Risk - Uniform | -1.122019 | [-1.325551, -0.919124] |
| Severe | Risk - Center ROI | +0.520335 | [+0.219145, +0.819932] |
| Severe | Risk - Object ROI | -0.883174 | [-1.108029, -0.660112] |
| Low | Risk - Uniform | +1.797863 | [+1.422217, +2.194322] |
| Low | Risk - Center ROI | +2.964203 | [+2.511463, +3.399561] |
| Low | Risk - Object ROI | +0.191282 | [-0.218742, +0.605708] |

All six rows use `n=64` episodes, `Risk ROI minus baseline` as the positive direction, and the frozen scenario-stratified 10,000-replicate bootstrap. The low Risk-minus-Object interval crosses zero.

## 7. Determinism

The isolated M5E-F reproduction matched the accepted M5E-E outputs byte-for-byte for all six CSV files and all nine PNG figures. The four JSON documents matched after excluding unavoidable provenance metadata (`generated_timestamp_utc` and `git_commit`); their data, bootstrap samples, figure hashes, and analysis definitions matched. The differing provenance correctly records the independent acceptance run rather than a change in analysis content.

## 8. S7/S8 Audit

S7's unfavorable outcomes are present in valid paired episode data, not missingness or filtering. For example, its severe Risk-minus-Uniform mean is -1.682 dB (1 win, 7 losses) and severe Risk-minus-Object is -1.405 dB (0 wins, 8 losses); all constituent primary pairs have four valid snapshots.

S8 has eight retained episodes and no replacements. Its large low-budget effects are present in paired data (Risk-minus-Uniform +8.498 dB and Risk-minus-Center +7.161 dB; both 8 wins), with valid scene labels, matched complete-container byte accounting, and no duplicate/missing pair key. It was neither removed nor down-weighted. The M5E-E report correctly retains S8 as heterogeneity and an exploratory diagnostic, not a general conclusion.

## 9. Documentation Consistency

The protocol, report, progress, roadmap, README, and M6 plan consistently state that H1 is not fully supported; H2/H3 have direction-specific support only; severe-budget negative results are retained; Object ROI is a strong baseline; and Risk ROI has full-frame/background quality costs. The current policy is described as a Heuristic Risk ROI baseline, not a learned final method. No occurrences were found in the M5E-E report for `consistently outperforms`, `always better`, `universally superior`, `proves safety`, `guarantees safety`, `state of the art`, or `first risk-aware communication`.

## 10. Test Results

- M5E-D independent formal validator: passed (`64 / 256 / 4096`, recomputed).
- Isolated M5E-E reproduction: passed (`64` episodes, `384` primary pairs, `10,000` bootstrap replicates, `9` figures).
- Existing M5E-E independent validator: passed.
- Existing M5E-E determinism comparison: passed (`6` CSV, `4` JSON, `9` figures).
- Full unit suite: 287 tests passed.
- M2 plotting smoke test: passed.
- `git diff --check`: passed.

## 11. Deviations

The full M5E-D validator required approximately seven minutes because it independently recomputes the complete formal matrix; no shortened summary was substituted. The M5E-F reproduction output is intentionally stored in the ignored `results/m5e_f_acceptance_reproduction/` directory. JSON provenance differs only by the acceptance-run timestamp and current commit; all analytical content matches.

## 12. Acceptance Decision

**PASS: M5E-E is independently reproduced and formally accepted.**

This is an engineering and reproducibility acceptance. It does not change the scientific interpretation: H1 remains not fully supported, and M5E does not establish collision, navigation, network, real-robot, or universal Risk ROI superiority claims.

## 13. Conditions Before Push

Before any push, retain the two safety stashes, preserve the frozen M5E-D/E evidence and acceptance report, keep the working tree clean, and review the local acceptance commit. This acceptance run itself performs no push, merge, rebase, reset, force push, or amend.

## 14. M6 Entry Decision

M5 is formally frozen and M5E-F permits preparation of the separately defined M6 dataset/protocol. It does **not** authorize immediate Risk-VoI training: M6 must first generate independent counterfactual tile-quality data, freeze its task utility and split rules, and validate an oracle/greedy baseline. The next priority is that independent M6 data-generation protocol and dataset work, not learned allocation.
