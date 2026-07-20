# Milestone 5D Single-Frame Matched-Budget Quality Report

## Scope and Evidence

Milestone 5D evaluates exactly the 16 pre-existing M5C allocations: Uniform, Center ROI, Object ROI, and Risk ROI at the four actual-byte targets severe `31348`, low `32105`, medium `32729`, and high `33959` bytes/frame. It uses only the accepted M4D source frame `data/frames/m4/image_risk_validation_episode_0001.png` (SHA-256 `2b9e6b0b992d022a0e52fe6861b177c98841a1210a45688907d99c016f8bfa91`).

The evaluator reads the selected M5C quality tuples and tile payload sizes, deterministically re-encodes and serializes them, verifies their saved container bytes, decodes the result, and then measures quality. It does not call a quality-to-budget matcher, tile scorer, or spatial allocator. Therefore the quality metrics cannot change M5C selection. Every result is `160x120` uint8 RGB, uses the same 48 `20x20` tiles, Pillow `12.3.0`, fixed JPEG parameters, and the `311` byte `RAVCJT1` container overhead.

Generated evidence is ignored by Git:

```text
data/logs/m5/m5d_single_frame_quality.csv
data/metadata/m5/m5d_single_frame_evaluation.json
data/decoded/m5/m5d/<budget>/<method>.png
results/m5_compression/m5d_*.png
```

## Metrics and Regions

- Full-image MSE is the mean squared error over height, width, and RGB channels after conversion from uint8 to float. PSNR is `10 * log10(255^2 / MSE)` and is infinite only for zero MSE.
- SSIM uses `skimage.metrics.structural_similarity` with `data_range=255`, `channel_axis=-1`, `gaussian_weights=True`, `sigma=1.5`, `use_sample_covariance=False`, and `win_size=11`.
- Risk-weighted MSE uses the continuous accepted combined float mask and the per-pixel mean RGB squared error: `sum(risk * error) / sum(risk)`. Its PSNR uses the same formula as full-image PSNR. It is a risk-region image-distortion proxy, not a collision probability.
- Eligible-object union is the pixel-center union of M4D clipped polygons with statuses `fully_visible`, `partially_visible`, or `intersects_near_plane`. It contains 11065 pixels (`0.576302`). Risk support (`combined > 0`) also contains 11065 pixels, its risk sum is `1629.2801493906895`, high risk (`combined >= 0.20`) contains 4293 pixels (`0.223594`), and the background complement contains 8135 pixels (`0.423698`). No region metric is silently defined for an empty region.

## Fixed-Budget Results

All four methods exactly match the specified actual bytes at each budget, with zero unused bytes and utilization `1.000`. Values below are dB except SSIM and risk-weighted mean assigned quality (`RW Q`).

| Budget | Method | Bytes | Full PSNR | SSIM | Risk PSNR | Object PSNR | High-risk PSNR | Background PSNR | RW Q |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| severe | Uniform | 31348 | 24.980 | 0.830401 | 26.838 | 26.062 | 27.574 | 23.840 | 5.000 |
| severe | Center ROI | 31348 | 22.801 | 0.792624 | 25.613 | 24.708 | 26.248 | 21.088 | 8.308 |
| severe | Object ROI | 31348 | 23.014 | 0.794939 | 26.305 | 25.162 | 27.949 | 21.165 | 25.344 |
| severe | Risk ROI | 31348 | 22.921 | 0.795130 | 25.713 | 24.528 | 26.637 | 21.397 | 7.014 |
| low | Uniform | 32105 | 31.239 | 0.912879 | 33.169 | 31.665 | 33.861 | 30.719 | 25.000 |
| low | Center ROI | 32105 | 28.927 | 0.883114 | 30.007 | 29.564 | 29.455 | 28.188 | 27.149 |
| low | Object ROI | 32105 | 30.733 | 0.905072 | 32.919 | 31.325 | 34.146 | 30.039 | 46.131 |
| low | Risk ROI | 32105 | 30.708 | 0.908186 | 32.572 | 31.147 | 33.112 | 30.175 | 25.368 |
| medium | Uniform | 32729 | 33.618 | 0.944189 | 36.132 | 34.406 | 37.097 | 32.734 | 50.000 |
| medium | Center ROI | 32729 | 32.030 | 0.924602 | 34.357 | 33.192 | 34.185 | 30.826 | 38.822 |
| medium | Object ROI | 32729 | 33.598 | 0.943291 | 36.082 | 34.328 | 37.024 | 32.768 | 58.563 |
| medium | Risk ROI | 32729 | 31.489 | 0.919657 | 32.925 | 31.471 | 33.797 | 31.514 | 32.086 |
| high | Uniform | 33959 | 38.436 | 0.972965 | 42.193 | 40.064 | 44.061 | 36.897 | 80.000 |
| high | Center ROI | 33959 | 25.697 | 0.868299 | 26.016 | 26.452 | 25.312 | 24.844 | 40.071 |
| high | Object ROI | 33959 | 36.935 | 0.965096 | 41.239 | 39.765 | 42.269 | 34.756 | 82.744 |
| high | Risk ROI | 33959 | 35.898 | 0.959210 | 38.108 | 36.430 | 39.860 | 35.266 | 69.388 |

The companion CSV contains unrounded MSE, PSNR, SSIM, regional fractions, tile payload statistics, fixed quality maps, and all provenance fields. The risk-weighted allocation figure also records high-risk and zero-risk tile counts, mean/min/max quality, and their payload totals. High-risk tiles are classified by tile maximum `>= 0.20`; zero-risk tiles have tile maximum exactly zero.

## Single-Frame Observations

At the fixed severe and low targets, Uniform has the highest full and risk-weighted PSNR in this particular frame, while Object ROI has the highest reported high-risk PSNR. At medium, Uniform and Object ROI are close in full and risk-weighted PSNR. At high, Uniform has the highest listed full, risk-weighted, object, high-risk, and background PSNR for this one fixed allocation matrix. Center ROI's high-budget allocation visibly demonstrates that equal actual bytes do not guarantee comparable spatial quality distributions: its fixed M5C configuration uses a low background quality and a small enhanced region.

The allocation diagnostic demonstrates a concrete resource trade-off rather than a general ranking. For example, at the high fixed budget Object ROI assigns a risk-weighted mean quality of `82.744` compared with Uniform's `80.000`, but its observed background PSNR is `34.756` compared with Uniform's `36.897`. Such observations are descriptive properties of this source frame, frozen tile scores, discrete JPEG payloads, and M5C tie-break outcomes. They do not establish that any method is generally better or worse.

## Diagnostics

The following figures are generated from the fixed CSV and decoded images:

```text
results/m5_compression/m5d_full_psnr_vs_bytes.png
results/m5_compression/m5d_full_ssim_vs_bytes.png
results/m5_compression/m5d_risk_weighted_psnr_vs_bytes.png
results/m5_compression/m5d_object_region_psnr_vs_bytes.png
results/m5_compression/m5d_high_risk_region_psnr_vs_bytes.png
results/m5_compression/m5d_background_psnr_vs_bytes.png
results/m5_compression/m5d_risk_weighted_quality_allocation.png
results/m5_compression/m5d_severe_reconstructions.png
results/m5_compression/m5d_low_reconstructions.png
results/m5_compression/m5d_medium_reconstructions.png
results/m5_compression/m5d_high_reconstructions.png
```

The reconstruction figures show the source and all four decoded results at each fixed budget. The cyan contour identifies the fixed high-risk diagnostic region; it is not transmitted and is not used for decoding.

## Validation and Reproducibility

The M5D validator independently reloads the accepted source frame, M4D float mask and eligible polygons, and the M5C 16-row evidence. It recomputes each deterministic container, decode, full/risk/region metric, and tile diagnostic; checks exact target bytes, `311` byte overhead, saved M5C quality and payload tuples, decoded PNG contents and dimensions, non-source reconstructions, dependency versions, no-future-actual provenance, and metadata hashes. A second evaluation run must reproduce the same CSV, metadata, container bytes, decoded PNGs, and plot inputs in the same Pillow/libjpeg environment.

This milestone does not claim statistical significance, general superiority, collision probability, real occlusion handling, perception benefit, network benefit, or navigation benefit. It does not change M1-M4 evidence, world risk, image risk, camera projection, codec, spatial allocation, or byte budgets. The next priority is Milestone 5E: a multi-frame and multi-scene offline evaluation under the same frozen fairness and leakage rules.
