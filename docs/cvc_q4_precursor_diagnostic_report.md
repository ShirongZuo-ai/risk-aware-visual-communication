# CVC-Q4 Safety-Decision Precursor / Gradient Diagnostic

Date: 2026-08-16  
Status: development/diagnostic complete  
Classification: **CASE C — weak / scenario-limited precursor**

## Scope and result

Q4 reused fixed Q1/Q2/Q3 traces and did not run Webots, modify an allocator, compare new A0/A1 policies, inspect navigation outcomes for feature selection, train a model, or open C4/C5 Formal. It found a useful but not yet robust continuous decision-space signature.

The best retained rule is:

```text
soft feasibility mass <= 0.6543448255
AND
OLS_8 slope(soft feasibility mass) < -0.1187662843 /s
```

It covered all 8 observed Safety Decision Value onsets within 2.0 s. Lead was median `0.480 s`, mean `0.828 s`, range `0.160–1.952 s`; 6/8 exceeded 0.25 s, 4/8 exceeded 0.5 s, and 3/8 exceeded 1.0 s. It was active for 0.983% of all evaluation steps and falsely active outside a 2 s event window for 0.593% of all steps. However, it fired at least once in 10/53 event-free episodes (18.9%), and all positive labels came from only 2/10 scenario families. That concentration prevents a stable cross-family precursor claim and does not justify scheduler integration.

## 1. Recovered trace set

- Calibration: 10 Q1 U0 support traces, 3,120 steps, from `results/cvc_q1_support_qualification/traces/`.
- Evaluation: 30 Q2 traces plus 30 Q3 traces, 18,720 steps, from `results/cvc_q2_webots/traces/` and `results/cvc_q3_webots/traces/`.
- Target support: Q2 has 148 event-positive steps forming 5 onsets; Q3 has 37 event-positive steps forming 3 onsets.
- The 8 onsets occur in seven executions and only in straight-approach and narrow-passage scenarios.
- Q1 supplies normal-variation calibration only. Future event labels are used only for offline evaluation.

## 2–4. Signal definitions

`M_stale(t)` is the frozen Q1 conservative margin, under the CURRENT causal planner observation, of the exact action selected from the receiver-HELD image. The matched action identity must occur in both 15-action candidate tables.

`M_best_current(t)` is the maximum CURRENT conservative margin among hard-feasible Q1 candidates. `G(t) = M_best_current(t) - M_stale(t)`. This deliberately measures safety-margin opportunity, not the goal-efficient selected-current margin.

Safe-set representations were:

- `N_safe` and `F_safe = N_safe / 15`;
- mean positive hard-boundary slack, `mean(max(margin - 0.025 m, 0))`;
- soft feasibility mass, `mean(sigmoid((margin - 0.025 m) / 0.050 m))`, where 0.050 m is the frozen hard-to-preferred band width;
- lower quartile of the 15 CURRENT candidate margins.

No signal API accepts evaluator clearance, contact, physical geometry, or navigation outcome fields.

## 5–7. Trend estimators, windows, and baseline

Q4 retained three causal estimators: ordinary local linear regression (OLS), all-pairs Theil–Sen, and median adjacent slope. It tested 8/12/16/20 samples, corresponding to past-through-current spans of `0.224/0.352/0.480/0.608 s` at the 32 ms step.

The normal baseline contains Q1 windows in which held and current selected action IDs match, safe-action tuples match, and both selected safety classes are `preferred_safe`. No future event, evaluator outcome, collision, near-danger, clearance, or A1 result enters calibration. Each abnormal slope threshold is the one-sided 1st/99th percentile of this normal distribution. The chosen OLS-8 baseline contains 1,570 finite `M_stale`/`G` windows and 2,899 finite soft-mass windows.

OLS-8 was retained because it matched the robust estimators' 8/8 chosen-rule coverage and median lead, is the simplest estimator, has the shortest tested latency, and did not require an R² gate. Longer OLS windows retained coverage but increased false-step activation from 0.593% to 1.004%. Theil–Sen behaved similarly. Median-adjacent lost one event at 16 and 20 samples.

## 8–11. Frozen diagnostic thresholds and reliability

- `tau_M = 0.2024315376 m/s` (abnormally negative).
- `tau_G = 0.0395115952 m/s` (abnormally positive).
- safe-fraction contraction threshold: `0.2976190476 /s` negative.
- positive-slack contraction threshold: `0.2024839557 m/s` negative.
- soft-mass contraction threshold: `0.1187662843 /s` negative.
- lower-quartile-margin contraction threshold: `0.2029581974 m/s` negative.
- `M_stale` attention level: the frozen preferred-clearance boundary, `0.075 m`.
- `G` attention level: stable-Q1 q95, `0.1199999996 m`.
- soft-mass attention levels: stable-Q1 q01 `0.6543448255` and q05 `0.6890516548`.

Trend reliability records OLS R², robust residual scale, and pairwise sign consistency. It is reported but not used as an automatic gate. For baseline soft mass, median R² is `0.99919`, median residual scale is approximately zero, and median sign consistency is 1.0; the lower tail shows that reliability is heterogeneous, so a hard R² threshold was rejected.

## 12–16. Pre-event behavior

Within the strictly pre-onset 2 s windows:

- `M_stale` median level is `0.07651 m`; median slope is `-0.03574 m/s`. The q01 slope is `-0.20957 m/s`, barely beyond `-tau_M`, so only a small tail is abnormal.
- `G` median level is `0.05034 m`; median slope is `-0.00357 m/s`, opposite the proposed positive-gap trend. Its q99 is `0.03862 m/s`, below `tau_G`.
- safe fraction median is `0.9333`; its median slope is zero because it is discrete.
- soft feasibility mass median level is `0.77788`; median slope is `-0.11820 /s`, nearly the calibrated abnormal boundary, with q25 `-0.15439 /s`.
- positive slack and lower-quartile margin decline, but their abnormal tail rules each cover only 1/8 events.

This shows that the available continuous signature is broad candidate-space contraction, not a reliable early `M_stale` collapse or positive `G` gradient.

## 17–22. Coverage, lead, false activation, and combinations

At OLS-8:

| Rule | Event coverage | Median lead | False steps outside 2 s | Event-free episodes firing |
|---|---:|---:|---:|---:|
| `M_stale` slope | 2/8 | 0.128 s | 0.657% | 37.7% |
| `M_stale` level + slope | 2/8 | 0.128 s | 0.016% | 0% |
| `G` slope | 1/8 | 1.408 s | 0.278% | 11.3% |
| `G` level + slope | 0/8 | — | 0.037% | 0% |
| `M_stale` + `G` slopes | 0/8 | — | 0.016% | 0% |
| safe fraction contraction | 8/8 | 1.376 s | 1.351% | 41.5% |
| soft-mass contraction | 8/8 | 1.984 s | 4.220% | 41.5% |
| soft q01 level + contraction | **8/8** | **0.480 s** | **0.593%** | **18.9%** |
| soft q05 level + contraction | 8/8 | 0.672 s | 0.956% | 26.4% |
| `M_stale` level+slope+soft contraction | 2/8 | 0.128 s | 0% | 0% |

The selected rule forms 25 active runs. Duration median is `0.224 s`, range `0.032–0.736 s`. Its stable-safe false activation is only `0.0143%` of stable/no-upcoming-event steps, but the episode-level false rate remains material because short warnings occur across ten negative executions.

No weighted score or large combinatorial search was used. The q01 and q05 soft levels are outcome-independent stable-support anchors. Gradient-only, level-plus-gradient, reliability-gated, and the three priority combinations are all retained in the machine artifact.

## 23–24. Scenario robustness and future-window prediction

The selected rule covers all five Q2 onsets and all three Q3 onsets. It does not establish family robustness: straight approach supplies five onsets and narrow passage supplies three; the other eight scenario families supply none. Some false steps occur in strong-right as well as the two positive families.

Step-level prediction results, with current-event samples excluded from labels:

| Future horizon | Precision | Recall | False-positive rate |
|---|---:|---:|---:|
| 0.25 s | 0.185 | 0.531 | 0.804% |
| 0.5 s | 0.261 | 0.375 | 0.731% |
| 1.0 s | 0.288 | 0.209 | 0.709% |
| 2.0 s | 0.397 | 0.155 | 0.608% |

These step metrics are lower than event-level coverage because the rule is intentionally intermittent rather than continuously active throughout every future-event window.

## 25. Runtime profile

In-process timing on the available machine:

| Component | Mean | p95 | Max | >32 ms |
|---|---:|---:|---:|---:|
| decision-space signals | 0.201 ms | 0.462 ms | 1.847 ms | 0/3,000 |
| OLS 8-sample trend | 0.133 ms | 0.339 ms | 2.192 ms | 0/3,000 |
| six-signal diagnostic path | 1.206 ms | 2.157 ms | 3.346 ms | 0/1,000 |

This excludes camera, detector, planner, file I/O, and scheduler time. Q4 itself is not CASE E; the diagnostic primitive fits within 32 ms in isolation.

## 26–30. Figures, rejected candidates, and best candidate

Five static figures were generated and visually inspected: two aligned event traces, a candidate coverage-specificity plot, an estimator/window trade-off, and slope distributions. Plot contracts, palette, denominators, and paths are embedded in `analysis.json`.

Rejected/failed findings are preserved: stale-margin gradients are late and sparse; gap gradients are directionally inconsistent; level gating can remove true warnings; discrete safe fraction is less smooth; unconstrained soft contraction is too permissive; long windows can erase short stale-margin warnings. A non-zero abnormal-gradient threshold is meaningful, but a reliable cross-family precursor is not established.

The best current candidate is the outcome-independent q01 soft-feasibility level plus abnormal OLS contraction rule. It is a decision-space precursor, not a communication policy.

## 31–34. Decision and next experiment

- Final classification: **CASE C — weak / scenario-limited precursor**.
- A scheduler experiment is **not yet justified**.
- ML is **not justified**; the limitation is positive support and cross-family stability, not representational complexity.
- Recommended next experiment: a development-only, event-rich support qualification of this frozen rule across at least three additional Safety-Value-positive scenario families. It should measure precursor coverage and event-free activation only, without implementing or comparing communication schedulers.

## Verification and artifacts

- Machine analysis: `results/cvc_q4_analysis/analysis.json`.
- Candidate table: `results/cvc_q4_analysis/candidate_summary.csv`.
- Figures: `figures/cvc_q4/`.
- Q3's manifest and all 22 protected inputs match. The frozen Q3 readiness, matrix, analysis, M9-A manifest/result/ledger, and M9-B result/ledger hashes also match.
- The analysis is strict JSON with non-finite values converted to `null`; its SHA-256 sidecar is emitted beside it.
- No commit or push was performed.
