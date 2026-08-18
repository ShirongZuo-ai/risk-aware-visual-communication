# CVC-P5 visual novelty and control-sensitivity timing diagnostic

Status: complete as a development-only mechanism study. CVC-P4 remains the stable Case-C result. No allocator was added, no threshold/reserve/packet/scenario sweep was performed, and C4/C5 Formal remains unopened.

## Diagnostic execution and integrity

P4 did not retain the current camera image at every step, so a purely offline reconstruction was impossible. CVC-P5 therefore performed 12 deterministic diagnostic replays of the unchanged six P4 scenarios under the unchanged A0 and A1 policies. At every 32 ms controller step it encoded the current Webots camera frame through the frozen quality-45, exact-24,000-byte JPEG packet path and decoded it as an uncharged shadow observation. The charged policy, detector, controller, geometry, dynamics, and actual received-frame schedule were unchanged.

All 12 replays exactly reproduce the P4 send steps, collisions, forward progress, and clearance fields. Every actual episode still charges three packets and exactly 72,000 wire bytes; 5,244 shadow packets were evaluated and zero shadow bytes were charged. The evaluator's physical clearance/contact fields are logged only after the controller decision and never enter perception or control.

## Frozen held-versus-current definitions

At step `t`:

- **HELD** is the pre-decision decoded image already held by the receiver. It is the image that would drive the controller if no packet were sent.
- **CURRENT** is the sender's current camera image after the same complete JPEG encode, serialization, integrity check, decode, and frozen detector used by P4.
- The counterfactual varies only the received visual observation. The frozen cruise state and control mapping are identical in both branches.

Visual novelty remains a vector of continuous diagnostics rather than a binary event:

- per-channel pixel MAE and RMSE between decoded HELD and decoded CURRENT;
- structural difference `1 - SSIM` using the repository's frozen SSIM implementation;
- changed-pixel fraction, where a pixel changes if its maximum absolute RGB-channel difference is at least 10 intensity levels.

Perception novelty runs the frozen detector independently on HELD and CURRENT and retains component existence, selected-component bearing, apparent proximity, confidence, normalized centroid displacement, `1 - bounding-box IoU`, and normalized connected-component-count change. The descriptive combined signal is the equal-scale Euclidean norm of those seven terms; its weights were not fitted to navigation outcomes.

Control sensitivity computes the frozen wheel command from each perception result and retains signed left/right-wheel deltas, signed forward-speed and steering deltas, and primary magnitude

`delta_control = sqrt(delta_left^2 + delta_right^2)`.

Visual, perception, and control signals remain separate. They are not combined into an allocator score.

## Outcome-independent timing rule

The primary onset proxy is the step at which a signal accumulates 25% of its episode-total nonnegative mass (`q25`). Its 50% and 75% cumulative steps, peak timing, peak magnitude, top-10%-of-steps signal share, and continuous risk/signal cross-correlations are also retained. An R0/R1 trigger is categorized as:

- **before** when it precedes q25;
- **during** when it lies from q25 through q75;
- **after** when it follows q75.

This rule and the three representative scenarios (`center_large`, `left_offset`, and `two_component`) were frozen before navigation outcomes were joined. Clearance, collision, and task success were used only in the later trade-off diagnosis.

## R0/R1 alignment and timing gaps

The table uses each A1 replay's own causal trajectory. Its R0 time is therefore the counterfactual current-state threshold crossing on that same trajectory, not the possibly different A0 closed-loop episode's send time. The A1 adaptive transmission occurs at its R1 trigger.

| Scenario | R1 trigger | R0 trigger | R1 lead | Visual q25 | Perception q25 | Control q25 | Control peak | Control at R1 / peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| angled_toward | 2 | 28 | 26 | 137 | 186 | 187 | 265 | 0.0065 |
| center_large | 6 | 49 | 43 | 76 | 107 | 136 | 155 | 0.0227 |
| late_appearance | 1 | 3 | 2 | 85 | 82 | 71 | 63 | 0.0168 |
| left_offset | 11 | 54 | 43 | 158 | 198 | 196 | 265 | 0.1299 |
| right_offset | 16 | 49 | 33 | 88 | 86 | 82 | 83 | 0.3557 |
| two_component | 7 | 66 | 59 | 109 | 85 | 112 | 142 | 0.0487 |

R1 occurs **before** visual q25 in 6/6 episodes, perception q25 in 6/6, and control q25 in 6/6. Median R1-to-q25 gaps are 93 steps/2.976 s for visual novelty, 91 steps/2.912 s for perception novelty, and 117.5 steps/3.760 s for control sensitivity. The corresponding R0 gaps remain positive but are shorter: 62.5 steps/2.000 s, 68.5 steps/2.192 s, and 77.5 steps/2.480 s. Median R1-before-R0 prediction lead is 38 steps/1.216 s, much smaller than R1's median lead to useful-information onset.

All six control-sensitivity peaks occur after the A1 adaptive packet. Their median delay from R1 is 142 steps/4.544 s (range 62-263 steps). At the R1 trigger, the median control magnitude is only 0.1601 rad/s, or 3.57% of that episode's later peak. At the same-trajectory R0 trigger, the median is 0.5934 rad/s and 10.47% of peak.

## Values at trigger times

Across the six A1 traces:

| Diagnostic | Median at R1 | Median at same-trajectory R0 |
|---|---:|---:|
| decoded pixel MAE | 9.7169 | 18.0851 |
| decoded pixel RMSE | 21.5371 | 31.5152 |
| structural difference | 0.3309 | 0.3302 |
| changed-pixel fraction | 0.2846 | 0.3928 |
| combined perception change | 0.5162 | 0.5688 |
| bearing change | 0.0417 | 0.0768 |
| proximity change | 0.00760 | 0.03208 |
| confidence change | 0.0000 | 0.0000 |
| control sensitivity | 0.1601 rad/s | 0.5934 rad/s |
| signed forward-speed change if sent | -0.08935 rad/s | -0.37698 rad/s |

R1 frames are therefore not universally identical to HELD: `right_offset` already has substantial bearing and control change at its R1 trigger. The systematic result is relative, not absolute—A1 sends before the main episode mass and well before the later control peaks. Confidence contributes no timing information because the controlled-scene detector is saturated at confidence 1.0 whenever it detects the red component.

The continuous cross-correlations are retained but are not used as a hard onset estimator. Four of six R1-control maxima hit the positive +100-step search boundary, one hits -100, and one peaks at +19. Transmission resets, post-pass viewpoint changes, and nonstationary risk make a single lag ambiguous; the cumulative timing and direct counterfactual magnitudes are more interpretable here.

## Is useful information temporally concentrated?

It is moderately concentrated, not an instantaneous spike. Across A1 episodes, the median share of total signal carried by the top 10% of steps is 16.5% for visual MAE, 25.5% for perception novelty, and 28.8% for control sensitivity. The control q25-to-q75 window has median width 92 steps/2.944 s. This supports an upcoming communication-critical **window**, but not a single universally optimal send step.

## Why task completion improved while clearance worsened

P4's physical result is reproduced: A1 has 4/6 task successes versus A0's 1/6, mean forward progress 0.6413 m versus 0.2495 m, and no collisions in either arm. Separately, A1 has lower minimum clearance in 4/6 pairs, a median A1-minus-A0 minimum-clearance change of -0.13865 m, and mean episode minimum clearance 0.24884 m versus 0.39420 m.

The counterfactual traces identify a controller-level mechanism:

- At A1's early adaptive send, CURRENT would reduce forward speed relative to HELD in all six episodes, but only by a median 0.08935 rad/s; median control magnitude is 0.1601 rad/s.
- At A0's actual later adaptive send, the corresponding median forward-speed reduction is 0.38555 rad/s and median control magnitude is 1.2432 rad/s.
- A1 then holds the earlier, smaller/farther-looking obstacle until the common step-218 reserve. As the real obstacle grows or changes bearing, a fresh frame would command substantially more braking or steering, but the adaptive token is already gone.

Thus A1's additional completions are consistent with **less conservative stale-view control and greater commitment/progress**, not a safety benefit. The same mechanism reduces stopping/steering authority during approach and explains the clearance loss. Recovery behavior after step 218 varies by scene; it does not reverse the aggregate safety trade-off.

## Representative causal traces

The plots align R0/R1, the 0.14 P4 trigger, actual startup/adaptive/reserve transmissions, peak-normalized visual/perception/control diagnostics, and physical clearance. Exact unnormalized values, received perceptions, wheel commands, image ages, and contact/clearance fields remain in the JSONL traces.

- `center_large`: A1 sends at step 6; visual/perception/control q25 occur at 76/107/136, and control peaks at 155. The held early view continues near cruise while a current view would increasingly brake, reaching a 5.326 rad/s control difference.
- `left_offset`: A1 sends at step 11; q25 occurs at 158/198/196 and control peaks at 265. Later novelty includes steering and post-reserve/post-pass changes, demonstrating that visual change is not automatically safety value.
- `two_component`: A1 sends at step 7; q25 occurs at 109/85/112 and control peaks at 142. This episode achieves task success but has the study's lowest A1 clearance, 0.09210 m.

Figure paths are `results/cvc_p5_diagnostic/figures/a1_timing__*.png`. Continuous traces are `results/cvc_p5_diagnostic/traces/diagnostic__<scenario>__<policy>.jsonl`.

## Alternative hypotheses

**A. R1 already coincides with useful image change:** not generally supported. `right_offset` is a meaningful partial exception with 35.6% of peak control sensitivity at R1, but all six R1 triggers precede all three q25 onsets.

**B. Useful information has no concentrated window:** partly plausible but not the best description. Visual novelty is diffuse, while perception and control are more concentrated. The evidence supports a broad multi-second window rather than a sharp instant.

**C. Controller response is unrelated to safety:** not ruled out. Much of the rising pre-reserve control sensitivity accompanies falling physical clearance, but later post-pass visual/component changes can also create large control differences. A future spend rule must distinguish safety-relevant approach novelty from arbitrary viewpoint novelty.

**D. The detector/controller abstraction is limiting:** clearly applicable. The color-component detector has saturated confidence and the deterministic memoryless controller maps nearly every perception change to a wheel change, yielding a median perception-to-control zero-response fraction of 0.0. P5 validates timing in this controlled Webots abstraction, not with a general visual navigation stack.

## Mechanistic decision and next experiment

H_P5 is **supported as a development mechanism**, with the stated system-specific limitation. R1 predicts the R0 crossing a median 1.216 s earlier, but A1 immediately spends at R1 roughly 3.760 s before control q25 and 4.544 s before the later control peak. It is therefore accurate to say that P4's predictive frame was generally too early relative to when a new observation became control-relevant.

A **risk-arm plus novelty/control-spend** architecture is justified as the next concept, not as an established winning policy. R1 should open a causal communication-critical window; a sender-available visual/perception-change condition should spend within that window, with a deadline/fallback and the existing protected reserve. Pure novelty is insufficient because post-pass changes may be large but safety-irrelevant.

The next priority is a separately frozen, development-only **CVC-P6 arm/spend qualification**. Before any Webots outcome comparison, it should use the unchanged P4 traces to define one signal-only spend rule and verify: positive R1 arm lead, spending during the frozen q25-q75 control window, exact three-packet/72,000-byte accounting, no future debt, and a risk-window guard against post-pass novelty. Only one frozen candidate should then be run against unchanged U0/A0/A1 on the same six development scenarios. This is a recommendation only; no P6 allocator or experiment was implemented in P5.

## Reproduction and evidence

- `python scripts/run_cvc_p5_diagnostics.py --timeout 180`
- `python scripts/analyze_cvc_p5_timing.py`
- `python scripts/plot_cvc_p5_timing.py`
- Frozen definitions: `config/cvc_p5_diagnostic.json`
- Machine analysis: `results/cvc_p5_diagnostic/timing_analysis.json`
- Episode table: `results/cvc_p5_diagnostic/episode_timing.csv`
- Replay integrity: `results/cvc_p5_diagnostic/replay_summary.json`

