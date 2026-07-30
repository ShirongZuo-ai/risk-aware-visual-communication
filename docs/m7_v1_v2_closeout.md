# M7 v1/v2 Closeout

## Decision

M7 v1 and M7 v2 are frozen as completed development-only `NO-GO` baselines. Neither result authorizes a formal corpus or a Webots experiment, and neither may be tuned further on the 16 M7 v1 development episodes.

M7 v1 proved that the deterministic allocator can change tile assignments, but its allocation did not preserve exact byte parity or critical reconstruction quality. M7 v2 repaired those engineering failures with matched actual container bytes, a highest-feasible uniform quality floor, deterministic residual upgrades, and complete-container byte recomputation. It still failed to produce a scene-stable continuous task-utility gain.

## Frozen evidence

| Version | Decision | Passed gates | Failed gates | Main evidence |
| --- | --- | --- | --- | --- |
| M7 v1 | `NO-GO` | integrity, actuation, critical HQ coverage, heterogeneity, reproduction | eligibility, byte fairness, task utility, quality | TCOBR effect `0.000`, 95% CI `[0.000, 0.000]`; continuous boundary effect `-0.0163`, 95% CI `[-0.0317, -0.0009]` |
| M7 v2 | `NO-GO` | byte fairness, integrity, actuation, critical quality, TCOBR non-degradation, reproduction | continuous task utility, critical-boundary fidelity, scene balance | best candidate effect `+0.00176`, 95% CI `[-0.00610, +0.00962]`; signal confined to M7C2 Severe |

The authoritative reports are `docs/m7_visual_voi_evaluation_report.md` and `docs/m7_v2_offline_evaluation_report.md`. Their machine-readable summaries are `docs/results/m7_visual_voi_summary.json` and `docs/results/m7_v2_summary.json`.

## Mechanisms retained for M8

The following mechanisms are validated engineering controls and remain mandatory:

- exact actual complete-container bytes, including metadata and signaling;
- at most 0.5 percentage points utilization difference from each frozen baseline;
- a highest-feasible uniform minimum-quality floor before task-directed upgrades;
- deterministic one-step task-directed upgrades;
- complete-container recomputation for every candidate transition;
- deterministic tile-ID then target-quality tie-breaking;
- zero actual-future, evaluator-geometry, label, fallback, and replacement usage;
- strict provenance, canonical persistence, tamper rejection, and deterministic reproduction.

These controls solve resource-accounting and implementation-validity problems. They do not establish that the optimized utility is related to perception or navigation.

## Scientific interpretation

TCOBR is saturated at 1.0 wherever it is defined in the M7 development corpus and is undefined in 7/16 episodes. It remains useful as a non-degradation safety check, but it is not sufficiently sensitive to optimize or select an allocator.

The v2 continuous boundary proxy is also not qualified as an optimization target. Its best directional result crosses zero, has no Low-budget gain, and is entirely explained by one scene. Selecting it because it is the least negative candidate would be post-outcome tuning.

The confirmed next problem is measurement validation: establish that a sender-available continuous score responds to task-relevant visual degradation across scenes before using it to direct bytes. This requires new calibration evidence with evaluator-only references kept outside the allocation boundary.

## Freeze boundary

The M7 v1 corpus, allocators, candidate definitions, nine-gate decisions, statistics, figures, and reports are immutable historical evidence. M8 may reuse the validated engineering mechanisms listed above, but it may not:

- change an M7 score, threshold, gate, exclusion, or reported number;
- select or reject M7 episodes after inspecting outcomes;
- reinterpret undefined TCOBR as zero or one;
- present an M8 proxy as validated before the independent calibration gates pass;
- launch Webots or prepare a formal corpus under this closeout.

## Closeout status

M7 v1/v2 is complete as a negative baseline. The next priority is M8-A proxy qualification design, followed by a separately approved calibration corpus. Allocator development remains blocked until one sender-available proxy passes every preregistered calibration gate.
