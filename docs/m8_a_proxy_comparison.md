# M8-A Operational Proxy Comparison

## Selection principle

No proxy is selected from M7 allocator outcomes. Both candidates must first be frozen and evaluated on an independent M8 calibration split using method-independent perturbations and evaluator-only reference targets. The calibration result selects a measurement; allocator development begins only afterward.

If both candidates pass all gates, the fixed RGB obstacle-perception proxy is primary because it has the more direct semantic link to obstacle localization; sender-time risk-weighted fidelity is retained as a safeguard and diagnostic. If only one passes, that proxy may proceed. If neither passes, M8 remains `NO-GO` and no allocator is developed.

## Candidate A: fixed RGB obstacle-perception utility

Working name: **FROPU** (Fixed RGB Obstacle-Perception Utility).

### Sender-available inputs

- current trusted RGB frame;
- candidate reconstruction produced locally by the encoder;
- current robot state and the predefined command schedule available at the snapshot timestamp;
- frozen camera projection and predicted state/command corridor plus uncertainty fields;
- fixed detector configuration and version.

Actual future motion, future frames, obstacle ground truth, TCOBR labels, eligibility labels, evaluator masks, and navigation outcomes are forbidden.

### Operational computation

The candidate is a deterministic, non-learned OpenCV pipeline applied identically to the original and reconstruction:

1. convert RGB to grayscale, apply a `3 x 3` Gaussian blur with sigma `0`, and run Canny with thresholds `50/150`;
2. perform one `3 x 3` morphological close and extract external contours;
3. discard contours with width or height below 3 pixels, contour area below 16 pixels, or fewer than 8 boundary pixels;
4. sort proposals by `(top, left, height, width)` and compute confidence `c_i = min(1, edge_pixels/32) * min(1, contour_area/128)`;
5. compute sender-time relevance `r_i = 0.10 + 0.90 * corridor_overlap_fraction`, using the union of the two predicted corridors only;
6. match each original proposal to the reconstructed proposal with maximum IoU, resolving ties by the proposal sort order;
7. compute continuous proposal fidelity

```text
f_i = 0.40 * IoU
    + 0.30 * exp(-centroid_distance_pixels / 20)
    + 0.30 * one_pixel_boundary_recall
```

8. report `sum(c_i * r_i * f_i) / sum(c_i * r_i)`. With no original proposals the proxy is undefined, not zero or one.

All intermediate proposal, match, and component values are persisted. The constants above are candidates frozen for calibration, not validated scientific parameters.

### Expected behavior and risks

FROPU is continuous in localization, overlap, and boundary preservation, so it should be less saturated than binary TCOBR. It has a plausible link to obstacle detection and localization, but not directly to collision avoidance or navigation success.

Its principal risks are false contours, texture sensitivity, proposal instability under compression, and circularity from defining original-image proposals with the same detector being scored. A method might preserve detector-specific edges without preserving real obstacles. Therefore the detector must first pass evaluator-geometry recall, false-positive, and localization gates; proxy qualification is invalid if that prerequisite fails.

## Candidate B: sender-time risk-weighted continuous fidelity

Working name: **STRCF** (Sender-Time Risk-weighted Continuous Fidelity).

### Sender-available inputs

- current trusted RGB frame and candidate reconstruction;
- sender-time union risk field from the state-only and command-conditioned predicted corridors;
- sender-time union uncertainty field;
- fixed color, grayscale, and gradient transforms.

It does not read obstacle geometry, TCOBR, eligibility, actual future motion, future frames, or reconstructed evaluator outcomes.

### Operational computation

For each pixel `p`, normalize union risk and uncertainty independently to `[0,1]` and define:

```text
w_p = 0.05 + 0.475 * risk_p + 0.475 * uncertainty_p
color_p = 1 - clip(||RGB_original - RGB_reconstruction||_2 /
                   (sqrt(3) * 255), 0, 1)
gradient_p = 1 - clip(|G_original - G_reconstruction| /
                      (G_original + G_reconstruction + 10), 0, 1)
STRCF = weighted_mean(0.5 * color_p + 0.5 * gradient_p, w_p)
```

`G` is the Sobel gradient magnitude of the grayscale image. The score, color component, gradient component, weight map, normalization maxima, and digests are persisted. Constant fields remain valid because the `0.05` floor prevents an empty weighted domain.

### Expected behavior and risks

STRCF is dense and continuous and therefore should have broad dynamic range even when obstacle eligibility is sparse. It directly measures reconstruction fidelity where sender-time motion risk and uncertainty are high, but its relationship to object perception and navigation is indirect.

Its main risk is circularity: a future allocator may use the same projected risk field to choose bytes and to receive credit. It can also reward visually faithful background pixels inside a corridor even when they carry no obstacle information. Qualification therefore requires association with an evaluator-only continuous critical-obstacle target, superiority to full-frame PSNR as a ranking signal, and a critical-versus-noncritical perturbation test.

## Evaluator-only calibration reference

Calibration uses **Continuous Critical-Obstacle Representation Fidelity** (CCORF) only as a reference label. CCORF uses frozen evaluator obstacle geometry and projected critical boundaries and is never available to an allocator:

```text
CCORF = 0.50 * soft boundary fidelity
      + 0.30 * clipped-obstacle SSIM mapped to [0,1]
      + 0.20 * inverse normalized RGB error inside the clipped obstacle
```

Soft boundary fidelity averages `exp(-d/1.5)` for each original critical-boundary pixel, where `d` is distance in pixels to the nearest reconstructed Canny edge, clipped at 5 pixels. Eligible geometry retains the frozen minimum 64 projected pixels and 16 original boundary-edge pixels. CCORF is a calibration reference, not the M8 allocator objective and not a replacement for TCOBR.

## Comparison

| Dimension | FROPU | STRCF |
| --- | --- | --- |
| Semantic relation | fixed obstacle proposal preservation | reconstruction fidelity in predicted risk/uncertainty support |
| Sender availability | yes | yes |
| Continuous/non-saturating mechanism | IoU, localization, and boundary terms | dense color and gradient fidelity |
| Empty-domain behavior | undefined if no proposals | always defined |
| Dependence on predicted corridor | relevance weighting only | direct pixel weighting |
| Leakage risk | low with strict schema; evaluator geometry forbidden | low with strict schema; evaluator geometry forbidden |
| Circularity risk | detector-specific edge preservation | high because allocation and score may share risk support |
| Scene sensitivity | detector may fail on texture/occlusion | risk projection may reward irrelevant background |
| Downstream link | obstacle detection/localization, still not navigation | indirect visual-fidelity surrogate |
| Required prerequisite | detector ground-truth validity gates | none beyond field validity |
| Rejection trigger | detector prerequisite or any proxy gate fails | any proxy gate fails |
| Role if both pass | primary | safeguard/secondary diagnostic |

## Why this strategy addresses M7 failures

M7 v1 optimized nominal HQ coverage and lost reconstruction quality; M7 v2 protected quality and bytes but optimized an unvalidated edge score whose signal came from one scene. The M8 strategy separates measurement qualification from allocator comparison. Controlled degradation supplies sensitivity and monotonicity evidence, evaluator-only geometry tests task relevance, scene-stratified gates reject single-scene effects, and a fixed selection rule prevents choosing whichever proxy later favors a method.
