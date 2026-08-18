# M9-B confirmatory replication preregistration

## Identity and independence

`m9b-confirmatory-v1` is a new study motivated by M9-A's F6 support failure. It does not repair, augment, or reinterpret M9-A. No M9-A Formal episode, label, seed, or log is eligible. M9-A hashes are checked before every M9-B stage.

## Hypotheses

The sole primary comparison is R1 versus R0 on 2.0 s `danger_within_H` AUPRC. PASS requires both `AUPRC(R1)-AUPRC(R0) >= 0.05` and a paired family-stratified episode bootstrap 95% percentile interval lower bound above zero. The threshold is retained from the earlier preregistration, not selected from M9-A's effect. R2-R1 is secondary/mechanistic and cannot rescue the primary claim.

Labels retain physical radius `0.037 m`, `d_near=0.013 m`, bilateral contact truth, dense 0.032 s trajectories, and exact nominal horizon interpolation. Warning thresholds are recalibrated on M9-B Calibration only.

## Independent design and support margin

The inferential unit is a distinct geometry/schedule cell. Identical deterministic reruns are reproducibility checks and never separate inferential episodes.

Formal contains 240 distinct cells: F1-F7 each contain 10 collision, 10 buffered-near, and 10 safe cells; F8 contains 30 distinct safe controls. Required observed support is at least 216 valid; at least 56 collision, 56 near, and 80 safe overall; F1-F7 each at least 8/8/8; F8 at least 24 safe. No replacement follows Formal outcome access.

Physical construction uses only contact and actual clearance: collision requires bilateral contact; buffered near requires no contact and minimum clearance in `[0.003, 0.010] m`; safe requires no contact and minimum clearance at least `0.020 m`. Predictor outputs are forbidden during construction.

Pilot must explore at least five distinct candidates per class per F1-F7 plus ten F8 controls. Calibration uses at least six newly distinct candidates per class per F1-F7 plus eighteen F8 controls and passes only with at least four observed collision, four buffered-near, and four safe cells per F1-F7 and fifteen F8 safe cells.

## Inference

Use 10,000 paired episode resamples within F1-F7, NumPy PCG64 seed `20261001`, percentile 95% intervals, and equal family macro-weight. F8 has no positive labels and is excluded from AUPRC aggregation but retained for safety/support and warning calibration. Undefined resamples are reported and cannot be imputed.

## Access hard stop

Formal remains prohibited until literal Pilot/Calibration/Formal grids, schemas, split-isolation validation, M9-B warning decisions, implementation identities, a complete analysis contract, a 240-record outcome-free manifest, hashes, and a separate sealed one-shot ledger exist. A new explicit Formal authorization ID is required.
