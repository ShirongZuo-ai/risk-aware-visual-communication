# M5E-D Formal Offline Evaluation Closeout

Last updated: 2026-07-20 (Asia/Shanghai)

## Scope and frozen inputs

This retrospective closeout audits the frozen M5E-D formal image-quality matrix only. It does not regenerate inputs, allocations, reconstructions, metrics, scenarios, seeds, budgets, or protocol definitions. M5E-D is an engineering-quality table; M5E-E/F are the later statistical analysis and independent acceptance of that frozen evidence.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\audit_m5e_d_closeout.py
```

The command is read-only with respect to `data/m5e_formal/`; it writes the reproducible descriptive summary to `docs/results/m5e_d_closeout_summary.json`.

## Integrity and coverage

The 2026-07-20 audit passed:

- 64 accepted primary episodes, 256 formal snapshots, and 4,096 reconstructions;
- S1–S8, Uniform, Center ROI, Object ROI, Risk ROI, and all four frozen byte budgets;
- zero replacement records, duplicate frame-method-budget keys, missing matrix keys, non-finite numeric cells, missing artifacts, unreadable decoded PNGs, and over-budget rows;
- zero rows using an actual future trajectory; and
- CSV allocation/metric keys agree with the formal manifest and recorded run metadata.

The frozen complete-container-byte targets remain severe 31,466, low 32,374, medium 33,509, and high 34,871 bytes. The check tests `actual_total_bytes <= target_bytes`; later primary paired comparisons additionally passed the frozen 0.5% mean byte-fairness tolerance in M5E-F.

## Descriptive result inventory

The summary records, by method/budget and scene/method/budget, complete transmitted bytes, utilization, full-frame PSNR/SSIM, continuous risk-weighted PSNR, eligible-object PSNR, risk-support PSNR, background PSNR, and risk-weighted mean tile quality. It also retains the ten lowest risk-weighted-PSNR rows as diagnostic cases. This uses existing metric definitions only; it does not invent a bitrate or compression-ratio definition absent from the frozen protocol.

High-risk regional PSNR is `undefined` for 2,688 rows because the frozen threshold has an empty region in low-risk controls. This is an expected metric-domain condition, not a NaN/inf or missing-data failure.

## What the evidence supports

### Directly supported

- The implementation produces deterministic, readable, complete, complete-container-byte-constrained reconstructions under the frozen static-scene protocol.
- M5E-E/F establish heterogeneous paired offline image-quality results: Risk ROI is worse than Uniform and Object ROI at severe budget, better than Uniform and Center ROI at low budget, and the low-budget Risk-minus-Object interval crosses zero.
- Risk allocation creates a quality trade-off: it can reduce full-frame/background quality while prioritizing risk-related regions. Object ROI is a strong baseline.

### Preliminary indications

- The future-command-conditioned, geometry-grounded risk signal can change allocation in ways relevant to trajectory-critical visual regions.
- The S2/S6 and S3/S4 planned contrasts give direction-specific, not universal, support to H2/H3.

### Not supported by the current experiment

- General Risk ROI superiority at matched bytes, including over Object ROI.
- Superiority of command-conditioned ROI over a state-only trajectory ROI: the latter is a planned ablation, not a frozen M5E-D method.
- Reduced network cost beyond the imposed byte budget, since all methods were deliberately byte matched.
- Improved robot safety, collision reduction, navigation success, perception accuracy, or closed-loop control. There is no closed-loop task outcome in M5E-D.

## Anomalies and boundary

Worst risk-weighted-PSNR diagnostics are retained rather than removed; they are concentrated in severe-budget S6 rows and are descriptive rather than exclusions. S7's adverse paired effects and S8's large paired effects were retained and independently audited in [the M5E-F acceptance report](m5e_f_independent_acceptance_report.md): neither comes from replacements, missing pairs, duplicate rows, scene-label errors, or byte mismatch. S8 remains an exploratory heterogeneity diagnostic, not a universal conclusion.

The technical contribution is an interpretable framework that explicitly converts projected future-motion risk into visual communication priority. It is a heuristic tiled-JPEG baseline, not a learned allocator, a calibrated collision model, a standards codec, or a demonstrated safety system.
