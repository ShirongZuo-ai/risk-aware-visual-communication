# CVC-P7 Safety-Value Discrimination Study

Date: 2026-08-15  
Status: development-only complete; no paper work, P8 allocator, C4/C5 Formal protocol, commit, or push

## Executive result

CVC-P7 explains the frozen P6 completion/clearance trade-off, but it does **not** identify a safety-value discriminator. The frozen red-component controller turns toward the selected component. In every historical schedule-different P6 pair, A1's earlier update slightly reduced forward velocity and reduced absolute turning demand relative to the stale A0 command, while still turning toward the component. That removed stale detours and improved forward completion, but kept the path closer to the component. This is task/centering value, not obstacle-avoidance value.

The new P7 suite was frozen before U0/A0/A1 outcomes, ran 36/36 episodes at exact cost, and successfully created high-novelty/low-physical-relevance distractor cases. However, none of its 36 runs crossed the frozen 0.12 m physical-danger boundary. Consequently, safety-window labels contain zero positives: feature AUPRC, cue-to-danger lead, and learned diagnostic models are not estimable. The closest authorized classification is **CASE D — no usable communication safety window demonstrated**, explicitly bounded as a physical-support failure of this frozen suite rather than a general proof that no window exists.

## 1. Frozen P6 trade-off reconstruction

P6 v1 was not changed. The three schedule-different A0/A1 pairs were reconstructed from their original causal traces.

| Scenario | A1 vs A0 progress (m) | A1 vs A0 min clearance (m) | A1 early-send delta v (m/s) | A1 vs A0 abs-turn at early send (rad/s) | Direction after send |
|---|---:|---:|---:|---:|---|
| left_offset | +0.576687 | -0.375409 | -0.001907 | -0.431071 | toward component |
| right_offset | +1.208152 | -0.235479 | -0.003161 | -0.289158 | toward component |
| two_component | +0.817040 | -0.303793 | -0.002007 | -0.092846 | toward component |

The frozen controller computes a positive image-right bearing into a rightward robot yaw. It therefore centers/pursues the red component; it is not an avoidance controller. The early A1 packet changes steering immediately at steps 11/16/16 and trajectory divergence begins at the same steps. Two pairs reverse steering sign. All three reduce absolute turn magnitude, preventing the larger stale detours later taken by A0. The velocity reductions are real but below the preregistered 0.005 m/s braking-event threshold. The dominant reproducible mechanism is earlier centering/forward commitment, not protective braking or turn-away control.

## 2. New outcome-independent suite

The suite contains 12 distinct deterministic cells, three per conceptual category:

| Category | Intended novelty | Intended safety relevance | Construction |
|---|---|---|---|
| A | low | low | stable clear paths with distant blue physical anchors |
| B | high | low | large lateral red nonphysical distractors plus distant blue anchors |
| C | low/subtle | high | narrow red physical obstacles on gradual approaches |
| D | high | high | angled/late red physical conflict reveals |

The identities, starts, objects, sizes, colors, physical flags, and seeds are in `config/cvc_p7_development.json`. `results/cvc_p7_readiness/scenario_manifest.json` was materialized before comparisons and records 3/3/3/3 category counts, no outcome construction fields, the scenario hash, and hashes of the frozen P6 config/allocator/perception-controller/adapter/world. No cell was deleted, replaced, moved, or reclassified after outcome inspection.

## 3. Physical safety reference and software boundary

The evaluator-only label is true at step t when contact or clearance <= 0.12 m occurs in the next 63 control steps (2.016 s), restricted to steps no later than the episode minimum-clearance step. The 0.12 m threshold is approximately 1.17 s of nominal 5 rad/s cruise travel using the 0.0205 m wheel radius. It was fixed before feature comparisons and was not optimized for discrimination.

Sender-visible code receives decoded held/current RGB-derived perception only. It logs bearing convergence, proximity/area/bbox growth, component events, corridor overlap, image age, and counterfactual control. Evaluator clearance/contact/category/trajectory are computed only after sender decision, receive, perception, and control; they never enter R0/R1, ARM, novelty, receiver perception, or wheel control.

## 4. Directional control and visual cue diagnostics

Differential-drive diagnostics use:

- v = wheel_radius * (left + right) / 2;
- omega = wheel_radius * (right - left) / axle_length;
- delta_v = v_send - v_hold;
- delta_abs_turn = abs(omega_send) - abs(omega_hold);
- slowdown event at delta_v <= -0.005 m/s;
- increased-turn event at delta_abs_turn >= 0.10 rad/s;
- turn-toward/turn-away from the currently decoded component using camera-bearing/yaw sign.

Visual diagnostics include absolute bearing, bearing convergence rate, proximity/approach rate, selected-component pixel and bbox-height growth, relative area growth, appearance/disappearance, component-count change, and overlap with the central 30% image corridor. They are diagnostic only and do not change transmission.

## 5. Feature structure by intended category

At A1's frozen adaptive spend:

- A produced no visual cue and used the step-217 unarmed fallback in all three cells.
- B armed at step 1 and spent at step 3 in all three harmless-distractor cells. Bearing convergence was 2.018-2.162 normalized units/s and proximity growth 0.291-0.425/s despite zero physical-danger windows. This is a strong generic-novelty false positive.
- C was deliberately subtle: one cell armed/spent at step 117; two never armed and fell back at step 217. Those fallback frames made the component disappear and increased forward velocity, yielding the only two `mainly_progress_enabling` A1 spend labels.
- D armed at steps 69-71 and spent at steps 69-71. Sends reduced velocity by 0.0132-0.0156 m/s and increased absolute turn demand, but every nonzero-bearing command turned toward rather than away from the component.

Across 12 A1 spends, post-hoc classification was 2 mainly-progress-enabling and 10 negligible/ambiguous; zero were safety-protective or mixed because no spend occurred inside a realized physical safety window.

## 6. Timing

R1 ARM and P6 novelty/spend timings were observable, but safety timing was not:

- A: no ARM or novelty; fallback spend step 217.
- B: ARM step 1, first P6 novelty and spend step 3. Bearing convergence/proximity growth existed at ARM; corridor overlap followed 5-7 steps later.
- C: first P6 novelty steps 17/17/33. Only C01 armed at step 117 and spent immediately; its post-ARM proximity growth occurred at ARM, bearing convergence one step later, and corridor overlap five steps later. C02/C03 never armed.
- D: first novelty steps 16/16/35, ARM/spend steps 70/69/71. Post-ARM proximity growth occurred at ARM, bearing convergence one step later, and corridor overlap within 0-4 steps.

Candidate slowdown/turn-away-shaped control changes occurred, but without a physical-danger onset they cannot be labeled safety-protective. Therefore R1-to-safety-cue lead, P6-novelty timing error relative to safety value, safety-cue-to-protective-control time, protective-control-to-danger lead, and available communication/control lead are all **not estimable** under the frozen definition.

## 7. Unchanged P6 policy outcomes on P7

| Policy | Completion | Collision | Mean minimum clearance (m) | Mean clearance (m) | Mean progress (m) |
|---|---:|---:|---:|---:|---:|
| U0 | 7/12 | 0/12 | 0.565443 | 0.805473 | 0.713779 |
| A0 | 5/12 | 0/12 | 0.564667 | 0.798987 | 0.512745 |
| A1 | 5/12 | 0/12 | 0.565497 | 0.790770 | 0.572636 |

The original P6 `completion gain + clearance loss` pattern did not generalize: A1 tied A0 on completion, improved mean progress by 0.059891 m, improved mean minimum clearance by only 0.000830 m, and reduced mean clearance by 0.008217 m. U0 had the highest completion and progress. These are development outcomes, not superiority claims.

## 8. Exact communication cost

All 36 episodes sent exactly three packets and exactly 72,000 charged bytes; total charged bytes were 2,592,000. Across the matrix the reconciliation was:

- JPEG/content: 189,194 bytes;
- metadata/container/integrity: 20,096 bytes;
- padding: 2,382,710 bytes;
- total: 2,592,000 bytes.

Per episode, content ranged 4,497-5,594 bytes, metadata 541-577 bytes, and padding 65,838-66,957 bytes. Every receiver-held mirror matched and every reserve/budget exhaustion occurred at step 218.

## 9. Failed candidates and model decision

All proposed sender-visible features—bearing convergence, proximity/approach growth, area growth, bbox growth, corridor overlap, directional speed/turn changes, and component events—remain unvalidated as safety-value discriminators because the label has no positive support. High values in B demonstrate that these signals can be task/visual novelty without physical safety relevance. No one-feature AUPRC is reported, no threshold was selected, and no decision tree or logistic model was trained. Machine learning is not justified by this dataset.

The connected-component representation is too ambiguous for safety-value claims in its current stack: the same component dynamics can be a harmless distractor or a physical obstacle, and the controller actively turns toward the selected component. However, P7 cannot isolate perception as the sole bottleneck because the physical-support failure and controller semantics are both limiting.

## 10. Classification and next direction

Final classification: **CASE D — No usable communication safety window demonstrated**, with a mandatory support qualifier. Zero frozen cells realized the evaluator safety window, so this is not evidence that a broader safety window is absent. It is evidence that P7 cannot support Case A/B/C and that outcome-selected geometry repair would be scientifically invalid.

Recommended next direction, without implementing P8: retain P7 as negative evidence; before any Safety-Value-SPEND design, create a separately authorized, outcome-independent physical-support qualification using an avoidance-capable controller and danger cells that are validated without communication-policy comparisons. Only after positive/negative safety-window support exists should a rule-based versus lightweight learned P8 choice be considered.

C4/C5 Formal remains unjustified.

## 11. Artifacts

- Frozen protocol/config: `config/cvc_p7_development.json`
- Frozen manifest: `results/cvc_p7_readiness/scenario_manifest.json`
- Webots matrix: `results/cvc_p7_webots/matrix_summary.json`
- Causal traces: `results/cvc_p7_webots/traces/`
- Mechanistic analysis: `results/cvc_p7_analysis/mechanistic_analysis.json`
- Aligned A1 series: `results/cvc_p7_analysis/aligned_a1_timeseries.csv`
- Episode and feature tables: `results/cvc_p7_analysis/episode_summary.csv`, `feature_distribution.csv`
- Inspected figures: `results/cvc_p7_analysis/figures/`

