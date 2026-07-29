# M7 v2 Constrained Visual-VoI Offline Evaluation

## Decision

**NO-GO for creating a new M7 formal corpus.** M7 v2 fixes the confirmed M7 v1 byte-fairness and reconstruction-quality failures, but none of the three preregistered candidates passes the continuous-task, critical-boundary-fidelity, or scene-balance gates. No candidate is selected.

This is development-only evidence from the completed 16-episode M7 v1 corpus. M7 v1 remains an immutable `NO-GO`; no Webots process or 720xxx formal identity was created.

## Mechanism revision

M7 v1 began every tile at JPEG quality 1 and used most available bytes for broad task-weighted upgrades. That increased nominal high-quality coverage while reducing critical and full-frame PSNR. M7 v2 makes the smallest shared correction:

1. reproduce both frozen baseline transmissions for the same snapshot and budget;
2. set a per-case cap to the lower integer midpoint of their exact charged bytes;
3. choose the highest uniform quality floor that fits that cap;
4. prohibit any tile from falling below the floor;
5. use only the residual bytes for deterministic one-step upgrades;
6. rebuild the complete tile container for every considered transition;
7. stop below the matched cap with no padding, fallback, replacement, or uncharged overhead.

The three preregistered marginal-benefit mechanisms are `v2_global_only`, `v2_visible_edges`, and `v2_corridor_edges`. The last uses sender-visible Canny edges inside the one-pixel-dilated union predicted corridor. Evaluator geometry, TCOBR labels, actual future information, and method-specific evaluation masks remain forbidden.

## Candidate gates

| Gate | Global only | Visible edges | Corridor edges |
| --- | --- | --- | --- |
| G1 Exact byte fairness | PASS | PASS | PASS |
| G2 Integrity and leakage | PASS | PASS | PASS |
| G3 Allocation actuation | PASS | PASS | PASS |
| G4 Continuous task utility | **FAIL** | **FAIL** | **FAIL** |
| G5 Critical quality | PASS | PASS | PASS |
| G6 TCOBR non-degradation | PASS | PASS | PASS |
| G7 Critical-boundary fidelity | **FAIL** | **FAIL** | **FAIL** |
| G8 Scene balance | **FAIL** | **FAIL** | **FAIL** |
| G9 Deterministic reproduction | PASS | PASS | PASS |

Each candidate passes six of nine gates. The gates are conjunctive, so no candidate is eligible for formal-corpus preparation.

## Byte fairness and allocation actuation

All 768 candidate cases remain under the common budget and within 0.5 percentage points of both baseline transmissions. The largest per-case utilization gaps are:

| Candidate | Maximum gap |
| --- | ---: |
| Global only | 0.2982 percentage points |
| Visible edges | 0.2982 percentage points |
| Corridor edges | 0.3011 percentage points |

At Severe and Low, 100% of snapshots differ from each frozen baseline in at least one tile-quality assignment. Every allocation records exact container recomputation, zero prohibited reads, zero fallback, and zero replacement.

## Continuous task utility

The primary effect is the equal Severe/Low episode effect against the better frozen baseline, resampled within each eligible scene with equal scene weights, 10,000 replicates, seed `20260724`.

| Candidate | Mean effect | 95% CI | Severe | Low |
| --- | ---: | ---: | ---: | ---: |
| Global only | -0.00305 | [-0.00610, 0.00000] | -0.00678 | 0.00000 |
| Visible edges | +0.00176 | [-0.00610, +0.00962] | +0.00391 | 0.00000 |
| Corridor edges | -0.00305 | [-0.00610, 0.00000] | -0.00678 | 0.00000 |

The visible-edge ablation is directionally positive, but its interval crosses zero and Low remains saturated. The full corridor-edge candidate is negative at Severe. No task-utility or fidelity gate passes.

## Reconstruction-quality safeguard

The uniform floor corrects the v1 quality failure. All effects below are against the better frozen baseline and exceed the preregistered `-0.25 dB` critical-region limit.

| Candidate | Severe critical PSNR | Low critical PSNR | Severe full PSNR | Low full PSNR |
| --- | ---: | ---: | ---: | ---: |
| Global only | +0.656 dB | +0.286 dB | +0.483 dB | +0.306 dB |
| Visible edges | +0.587 dB | +0.287 dB | +0.368 dB | +0.204 dB |
| Corridor edges | +0.576 dB | +0.279 dB | +0.424 dB | +0.268 dB |

Absolute episode-mean critical PSNR for the corridor-edge candidate is 28.699 dB at Severe and 38.136 dB at Low, compared with 28.123 dB and 37.857 dB for both frozen baselines.

## TCOBR and scene dependence

TCOBR remains saturated: every defined candidate/budget value is 1.0 and every paired effect is zero. No episode degrades, so G6 passes, but TCOBR cannot demonstrate improvement.

Only M7C2 has a nonzero primary continuous effect. Visible edges gains `+0.00879` there and is zero in M7C1/M7C3/M7C4/M7C5; the other two candidates lose `-0.01524` in M7C2 and are zero elsewhere. Therefore one scene accounts for all nonzero signal, leave-one-scene-out validation reaches zero or negative values, and G8 fails for every candidate.

## Interpretation

The matched-floor mechanism solves the engineering failures it targeted: byte fairness, global quality, critical quality, actuation, leakage, and reproducibility all pass. The remaining limitation is measurement and task localization rather than codec budget control. Current-frame edge prioritization produces only one-scene Severe improvement and no Low improvement; corridor intersection does not identify the evaluator's useful boundary pixels reliably enough.

The next step is not to tune these candidates on M7 v1. A separately reviewed measurement study must establish a sender-available, scene-stable continuous utility proxy and an eligibility-rich sampling authority before any formal corpus is prepared.

## Reproduction and artifacts

Run from the repository root without Webots:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_visual_voi_v2 evaluate
```

Machine-readable outputs:

- `docs/results/m7_v2_summary.json`
- `docs/results/m7_v2_candidate_comparison.csv`
- `docs/results/m7_v2_gates.csv`
- `docs/results/m7_v2_episodes.csv`
- `docs/results/m7_v2_cases.csv`
- `docs/results/m7_v2_provenance.json`

The summary canonical digest is `78241ce72226ef5272d752dc238e847eed23399f7634a01033a326f46a5d4903`.
