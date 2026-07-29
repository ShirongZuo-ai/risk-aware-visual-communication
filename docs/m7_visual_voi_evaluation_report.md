# M7 Visual-VoI Development-Corpus Evaluation

## Decision

**NO-GO for a new M7 Webots study.** The frozen budget-conditioned Visual-VoI allocator passes five of nine preregistered gates. It produces large, deterministic allocation changes and improves critical-boundary high-quality coverage, but it does not improve TCOBR, lowers continuous boundary utility, violates the byte-utilization fairness tolerance, and degrades critical-region reconstruction quality.

This is an offline result on the completed 16-episode M7 v1 development corpus. It is not a formal 720xxx result and does not authorize Webots.

## Frozen inputs and information boundary

The evaluation uses all 16 finalized development episodes, 64 trusted snapshots, the four frozen byte budgets, and the frozen `state_only_risk_roi` and `command_conditioned_risk_roi` codec cases. M5/M6 evidence is not modified or used for parameter tuning.

The allocator reads only sender-time current RGB, current state, predefined command schedule, shared projection configuration, and state/command predicted corridors. Its strict input API rejects actual future motion, future frames, evaluator-only obstacle geometry, TCOBR labels, evaluation masks, and unknown fields. Evaluator-only geometry is loaded after allocation and is used only for method-independent TCOBR, continuous boundary utility, critical-boundary coverage, and critical-region PSNR.

The implementation follows the frozen 8x6 tile grid, JPEG ladder `(1, 15, 35, 55, 75, 95)`, equal 0.25 component weights, 50/30/20 distortion weights, exact complete-container byte accounting, positive one-step upgrades, and deterministic tile-ID/target-quality tie-breaking. Zero or negative exact byte increments fail closed at the candidate boundary and cannot become free upgrades.

## Nine-gate result

| Gate | Decision | Frozen criterion | Observed result |
| --- | --- | --- | --- |
| 1. Integrity and leakage | PASS | Complete finite cases; zero fallback, replacement, or prohibited reads | 768 method-budget cases, 256 Visual-VoI provenance records, zero prohibited usage and zero non-finite values |
| 2. Eligibility richness | **FAIL** | TCOBR in >=6/8 scenes, >=75% episodes, >=3 eligible episodes in every included scene | 5/8 scenes, 9/16 episodes, minimum 1 eligible episode per included scene |
| 3. Allocation actuation | PASS | At Severe/Low, >=75% of snapshots differ from each baseline in >=10% of tile qualities | 100% against both baselines at both primary budgets |
| 4. Byte fairness | **FAIL** | All under budget, zero fallback, mean utilization difference <=0.5 percentage points | All cases under budget; maximum difference 3.323 percentage points |
| 5. Critical coverage | PASS | >=+0.10 at Severe and Low; primary CI lower bound >0 | Severe +0.337, Low +0.874; Severe/Low mean +0.606, 95% CI [0.519, 0.692] |
| 6. Offline task utility | **FAIL** | Positive lower CI bounds for TCOBR and continuous utility | TCOBR effect 0.000, 95% CI [0.000, 0.000]; continuous effect -0.0163, 95% CI [-0.0317, -0.0009] |
| 7. Quality safeguard | **FAIL** | Critical PSNR >=-0.25 dB and full-frame PSNR >=-1.0 dB at Severe/Low | Severe -2.053/-1.316 dB; Low -8.571/-0.947 dB (critical/full-frame) |
| 8. Heterogeneity | PASS | No scene >50% positive gain; no eligible scene TCOBR loss below -0.05 | Every eligible-scene TCOBR effect is 0; no concentrated positive gain or scene loss |
| 9. Reproducibility | PASS | Byte-identical sources, provenance, bootstrap inputs, and figures | Per-case double-run allocation digests match across all 256 Visual-VoI allocations; complete regeneration is byte-identical |

All gates are conjunctive. Gates 2, 4, 6, and 7 therefore make the decision `NO-GO`.

## Budget-level baseline comparison

Values are episode means across all 16 episodes except TCOBR and critical-region metrics, which retain only mathematically defined episodes. Bytes are mean charged complete-container bytes per snapshot.

| Budget | Method | TCOBR | Continuous boundary utility | Critical HQ coverage | Critical PSNR (dB) | Full PSNR (dB) | SSIM | Bytes | HQ area ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Severe | State-only | 1.000 | 0.957 | 0.000 | 28.123 | 24.918 | 0.7715 | 31,393.1 | 0.0005 |
| Severe | Command-conditioned | 1.000 | 0.957 | 0.000 | 28.123 | 24.684 | 0.7704 | 31,399.0 | 0.0005 |
| Severe | Visual-VoI | 1.000 | 0.932 | 0.337 | 26.070 | 23.603 | 0.7483 | 31,457.0 | 0.3005 |
| Low | State-only | 1.000 | 0.989 | 0.000 | 37.857 | 32.186 | 0.8904 | 32,127.0 | 0.0005 |
| Low | Command-conditioned | 1.000 | 0.989 | 0.000 | 37.857 | 32.188 | 0.8906 | 32,139.7 | 0.0005 |
| Low | Visual-VoI | 1.000 | 0.978 | 0.874 | 29.286 | 31.241 | 0.8771 | 32,336.2 | 0.7305 |
| Medium | State-only | 1.000 | 1.000 | 0.000 | 41.320 | 35.576 | 0.9347 | 32,883.0 | 0.0005 |
| Medium | Command-conditioned | 1.000 | 1.000 | 0.000 | 41.320 | 35.577 | 0.9347 | 32,896.7 | 0.0005 |
| Medium | Visual-VoI | 1.000 | 1.000 | 0.892 | 29.683 | 32.985 | 0.9126 | 33,435.6 | 0.8167 |
| High | State-only | 1.000 | 0.989 | 0.000 | 41.846 | 36.908 | 0.9487 | 33,533.9 | 0.0005 |
| High | Command-conditioned | 1.000 | 0.989 | 0.000 | 41.846 | 36.913 | 0.9489 | 33,560.5 | 0.0005 |
| High | Visual-VoI | 1.000 | 1.000 | 0.892 | 29.752 | 33.830 | 0.9275 | 34,692.8 | 0.8490 |

Visual-VoI changes the allocation, but the changed area is not translated into better task recall. The frozen baseline TCOBR is already 1.0 wherever the primary outcome is defined. At the primary budgets, Visual-VoI instead reduces continuous boundary utility and concentrates quality in a way that substantially lowers critical-region PSNR.

## Scene dependence and eligibility

TCOBR is defined for both episodes in M7C1-M7C4, one episode in M7C5, and no episodes in M7C6, M7G1, or M7G2. Thus only 9/16 episodes across 5/8 scenes enter TCOBR inference. Every eligible scene has a zero mean Visual-VoI TCOBR effect. Undefined scenes and episodes are not imputed.

Gate 2 also exposes a design-level limitation: the development corpus contains only two episodes per scene, while the frozen gate requires at least three eligible episodes in every included scene. The gate is evaluated unchanged and fails; this report does not reinterpret or relax it after observing outcomes.

## Interpretation and next decision

The allocator is causally clean, deterministic, and capable of materially changing tile allocations. However, the current score does not value boundary preservation accurately enough per exact byte: it expands nominal high-quality coverage while losing continuous boundary support and critical-region PSNR. A new Webots or 720xxx study is not justified.

The next priority is an offline-only redesign review. It must address the mismatch between binary high-quality coverage and reconstruction benefit, exact-byte utilization, saturated TCOBR, and eligibility-rich sampling. Any revised weights, marginal-benefit definition, or gate must be preregistered on a new disjoint development/evaluation authority; the frozen M7 v1 result remains unchanged.

## Reproduction and artifacts

Run from the repository root without Webots:

```powershell
.\.venv\Scripts\python.exe -m scripts.m7_visual_voi evaluate
```

Machine-readable artifacts:

- `docs/results/m7_visual_voi_summary.json`
- `docs/results/m7_visual_voi_gates.csv`
- `docs/results/m7_visual_voi_episodes.csv`
- `docs/results/m7_visual_voi_cases.csv`
- `docs/results/m7_visual_voi_provenance.json`

Publication source tables and figures are under `docs/figures/data/` and `docs/figures/`. The summary canonical digest is `7faa6183961b087ae996cceff27eae2f8430d1e566476261161558cf3bb60077`.
