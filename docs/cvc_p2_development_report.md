# CVC-P2 non-ceiling closed-loop communication development report

Status: development only; stopped before C4/C5 Formal. M9-B and CVC-P1 are unchanged.

## 1. Detector changes and validation

`communication/cvc_p2_perception.py` uses deterministic 8-connected red components while the CVC-P1 module remains unchanged. Every component records area, centroid, bounding box, normalized horizontal bearing, apparent proximity, and confidence. The largest component passing the fixed 12-pixel filter is selected with deterministic lower-image/left-centroid tie breaks. No simulator geometry enters detection. Tests cover left, center, right, small/far, large/near, three red fragments, absence, and JPEG qualities 90, 45, and 15.

## 2. Controller changes and validation

The controller consumes only decoded bearing and apparent proximity. Bearing sets differential avoidance steering; proximity continuously reduces speed and invokes braking at 0.34. Raw fixtures and JPEG-decoded fixtures verify direction, scale ordering, steering sign, and braking. The relevant CVC test set passes 22/22.

## 3. Development scenario suite

The frozen core contains six deterministic Webots cases: `center_large` (straight), `left_offset`, `right_offset`, `angled_toward` (curved/turn-toward and stale-sensitive), `late_appearance`, and `two_component` (red distractor). These establish straight, offset/turn, curved, late-reveal, stale-frame, and distractor behavior plus different clearances. A narrow passage and a literal external command-transition scenario were not added after the negative core result; doing so would expand the scientific scope after observing adaptive outcomes. This limitation is retained rather than hidden.

## 4. U0 budget-performance curve

All points use real 36,000-byte packets and six U0 episodes. Physical failure is collision or clearance below 0.12 m.

| Packets | Bytes/episode | Collisions | Physical failures | Worst clearance (m) | Mean progress (m) |
|---:|---:|---:|---:|---:|---:|
| 88 | 3,168,000 | 0/6 | 0/6 | 0.3842 | 0.3427 |
| 44 | 1,584,000 | 0/6 | 0/6 | 0.3808 | 0.3456 |
| 22 | 792,000 | 0/6 | 0/6 | 0.3261 | 0.3733 |
| 11 | 396,000 | 0/6 | 0/6 | 0.2796 | 0.9706 |
| 6 | 216,000 | 0/6 | 0/6 | 0.3799 | 0.5980 |
| 3 | 108,000 | 0/6 | 0/6 | 0.2270 | 0.3075 |
| 2 | 72,000 | 0/6 | 1/6 | 0.0959 | 0.3575 |
| 1 | 36,000 | 1/6 | 1/6 | -0.0025 | 0.3239 |

The nonmonotonic task progress is a real closed-loop consequence of stale decoded commands, not a smoothed trend.

## 5. Transition communication regime

Two packets (72,000 bytes/episode) is the highest-budget mixed physical-failure point with at least two temporal opportunities. It was selected from U0 only. The initial collision-only rule selected one packet, but that cannot test timing; both decisions are preserved.

## 6. T/S/TS implementations

T uses a causal exact-quota scheduler with fixed spatial quality. S uses the uniform two-packet timing and a causal one-tile-expanded component ROI with high/low JPEG quality. TS combines both. The known horizon can force quota reconciliation, but no future risk, outcome, evaluator geometry, or communication debt is used.

## 7. Matched-cost matrix

The corrected matrix contains 42 independent episodes: U0 plus R0/R1 versions of T, S, and TS over six scenarios. Every episode sends exactly two 36,000-byte packets. Trace-level payload + metadata + padding sums reconcile to 72,000 bytes in all 42 episodes.

## 8. R0-versus-R1 by mechanism

R0 and R1 tie exactly for collision, clearance, progress, image age, decoded error, and control divergence for T, S, and TS. Across 18 scenario/mechanism pairs, R1 has 0 clearance wins, 0 losses, and 18 ties; net collision difference is zero. No inferential test was performed.

## 9. Collision, success, and clearance

| Method | Collision | Task success | Near miss | Worst clearance (m) | Mean minimum clearance (m) |
|---|---:|---:|---:|---:|---:|
| U0 | 0/6 | 3/6 | 1/6 | 0.0959 | 0.3621 |
| S-R0 / S-R1 | 0/6 | 3/6 | 1/6 | 0.0970 | 0.3632 |
| T-R0 / T-R1 | 1/6 | 0/6 | 1/6 | -0.0016 | 0.4125 |
| TS-R0 / TS-R1 | 1/6 | 0/6 | 1/6 | -0.0016 | 0.4143 |

Task success is collision-free forward progress of at least 0.5 m; near miss is clearance below 0.12 m. T/TS's high average clearance coexists with poor progress and one collision, so it is not treated as a benefit.

## 10. Detector and image-age results

U0/S mean image age is 3480.0 ms; T/TS is 5997.8 ms because their second packet is spent early in responsive cases or forced at episode end in nonresponsive cases. Mean absolute decoded proximity error is about 0.052 for U0/S and 0.166-0.167 for T/TS. Mean wheel-command divergence is about 0.655-0.665 rad/s for U0/S and 1.571-1.580 rad/s for T/TS. These establish that communication allocation changes observability and control.

## 11. Causal episode traces

Full aligned JSONL traces log time, R0, R1, allocation reason, content/metadata/padding/wire bytes, ROI and quality range, image age, decoded component output, wheel commands, clearance, and contact. In `center_large`, R1 crosses 0.16 40 steps before R0 under U0/T, but T-R0 and T-R1 both transmit at steps 0 and 72. The risk warning lead therefore produces zero communication lead, zero perception/control lead, and identical collision at step 388. U0 sends at steps 0 and 218 and avoids contact. `angled_toward` similarly has 37 steps of R1 warning lead but identical R0/R1 transmissions at 0 and 72.

## 12. Failed variants

The first six-budget U0 sweep remained ceilinged and is preserved as `u0_sweep_v1_ceiling_summary.json`. The collision-only selector chose one packet and is preserved as `u0_selection_v2_collision_only.json`. The first adaptive matrix had a false R1 startup spike because an absent previous observation was initialized to zero; the complete run is preserved under `results/cvc_p2_development_v1_startup_artifact`. The corrected runner sets first-sample R1 equal to R0 and reruns the unchanged design.

## 13. Engineering communication value of predictive risk

Not demonstrated. R1 supplies real warning lead, but the implemented causal allocators quantize R0 and R1 to identical decisions. The communication-limited regime and allocation-to-control effect exist, yet R1 creates no additional allocation actuation. This is a stable negative result for these mechanisms, not proof that predictive risk can never help.

## 14. Confirmatory C4/C5 justification

No. There is no promising R1 policy to freeze, T/TS are adverse on collision/task success, and the core scenario coverage is not broad enough for confirmation. No C4/C5 Formal artifact was created.

## 15. Recommended next experiment

Do not run Formal. If work continues, preregister a new development-only allocator qualification that requires distinct R0/R1 decisions on synthetic causal risk traces before Webots, uses at least three packets so timing can be redistributed without spending the only update too early, and adds narrow-passage and literal command-transition cases. Proceed to Webots only after an actuation gate demonstrates positive communication lead without extra bytes.

## Reproduction

- Scenario/config: `config/cvc_p2_development.json`
- Runner: `scripts/run_cvc_p2_webots.py`
- Analysis: `scripts/analyze_cvc_p2_development.py`
- Commands: `python scripts/run_cvc_p2_webots.py --mode sweep`, `python scripts/run_cvc_p2_webots.py --mode matrix`, `python scripts/analyze_cvc_p2_development.py`
- Results: `results/cvc_p2_development/`
