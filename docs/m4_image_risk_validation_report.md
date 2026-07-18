# Milestone 4D Image-Risk Validation Report

Last updated: 2026-07-18 (Asia/Shanghai)

## Status

Milestone 4D-2 automatic end-to-end validation is complete and GUI human acceptance has passed on `feature/m4-image-risk-projection`.

Milestone 4D and the full Milestone 4 image-space risk projection milestone are formally accepted. This report does not claim compression benefit, communication gain, improved perception, or navigation safety.

## Scope

This milestone validates one same-snapshot connection:

```text
Webots snapshot -> planned/state world risk -> Camera projection -> planned/state/combined image-risk masks
```

Risk scores remain heuristic proxy scores, not collision probabilities. The first version does not model true rendered occlusion.

## Evidence Episode

Successful automatic and GUI-accepted episode:

```text
data/frames/m4/image_risk_validation_episode_0001.png
data/logs/m4/image_risk_validation_episode_0001.csv
data/metadata/m4/image_risk_validation_episode_0001.json
data/masks/m4/image_risk_validation_episode_0001_masks.json
```

Diagnostic visualizations:

```text
results/m4_image_risk/planned_mask.png
results/m4_image_risk/state_mask.png
results/m4_image_risk/combined_mask.png
results/m4_image_risk/planned_overlay.png
results/m4_image_risk/state_overlay.png
results/m4_image_risk/combined_overlay.png
results/m4_image_risk/world_to_image_risk_summary.png
```

The PNG masks are 8-bit visualizations using `round(255 * risk_value)`. The authoritative numeric masks are the row-major floating-point arrays in `data/masks/m4/image_risk_validation_episode_0001_masks.json`.

## Same-Snapshot Inputs

Snapshot time:

```text
7.968 s
```

Robot snapshot state:

```text
x=0.242882516
y=0.070315357
yaw=1.393201041
linear_velocity=0.029944488 m/s
angular_velocity=0.350989561 rad/s
```

Trajectory sources:

- Planned trajectory: command-conditioned rollout from the pre-existing future wheel-command schedule.
- State trajectory: state-only constant-twist rollout from the current Webots snapshot state.
- Actual future trajectory: not used.

Both planned and state trajectories contain 63 points over a 2.0 s horizon. The planned/state trajectory disagreement is:

```text
0.040803441 m
```

## Camera Parameters

Runtime Camera parameters:

```text
width=160 px
height=120 px
horizontal_fov=0.84 rad
near_clip=0.0055 m
fx=fy=179.142225973 px
cx=79.5 px
cy=59.5 px
camera_world_position=(0.248188668, 0.099863469, 0.027919930) m
```

Axis mapping:

```text
x_optical = -y_device
y_optical = -z_device
z_optical =  x_device
```

## Role Results

| role | visibility | planned | state | combined | candidate px | planned/state/combined written px |
|---|---|---:|---:|---:|---:|---:|
| PLANNED_DOMINANT_VISIBLE | partially_visible | 0.469831075 | 0.189292428 | 0.469831075 | 480 | 480/480/480 |
| STATE_DOMINANT_VISIBLE | partially_visible | 0.136077497 | 0.226684741 | 0.226684741 | 3813 | 3813/3813/3813 |
| SHARED_RISK_VISIBLE | fully_visible | 0.074374604 | 0.083360084 | 0.083360084 | 6118 | 6118/6118/6118 |
| LOW_RISK_VISIBLE | fully_visible | 0.005629554 | 0.006903238 | 0.006903238 | 597 | 259/259/259 |
| PARTIAL_VISIBLE | partially_visible | 0.005545375 | 0.003763963 | 0.005545375 | 150 | 48/48/48 |
| OUTSIDE_VIEW | outside_frustum | 0.002909857 | 0.001360382 | 0.002909857 | 0 | 0/0/0 |
| BEHIND_CAMERA | behind_camera | 0.360274930 | 0.360288054 | 0.360288054 | 0 | 0/0/0 |
| OVERLAP_BACK | fully_visible | 0.050168861 | 0.055912865 | 0.055912865 | 4218 | 0/0/0 |
| OVERLAP_FRONT | fully_visible | 0.069507491 | 0.078850731 | 0.078850731 | 4532 | 347/347/347 |

`OVERLAP_BACK` contributes candidate pixels but writes zero pixels because earlier overlapping higher-risk regions already occupy those pixels under max-union. This validates that a later or lower-risk obstacle cannot reduce existing mask values.

## Mask Results

Nonzero pixels:

```text
planned=11065
state=11065
combined=11065
```

Automatic validator checks:

- exact obstacle ID binding between risk, 3D Box, projection, and mask contribution;
- planned/state/combined channels remain independent;
- combined risk and combined mask equal max-union;
- invisible obstacles write zero pixels;
- overlap pixels use max across all covering obstacles;
- exclusive pixels bind back to each visible role's world-risk values;
- float masks match core recomputation;
- generated mask PNG values match the documented 8-bit quantization rule.

## RGB Alignment Metrics

| role | bbox IoU | polygon IoU | center error px | visible color px |
|---|---:|---:|---:|---:|
| PLANNED_DOMINANT_VISIBLE | 0.885 | 0.889 | 0.261 | 480 |
| STATE_DOMINANT_VISIBLE | 0.980 | 0.967 | 0.322 | 3834 |
| SHARED_RISK_VISIBLE | 0.960 | 0.967 | 0.216 | 6117 |
| LOW_RISK_VISIBLE | 0.399 | 0.414 | 6.621 | 259 |
| PARTIAL_VISIBLE | 0.287 | 0.316 | 2.225 | 48 |

The LOW_RISK and PARTIAL roles are small or image-edge diagnostic objects with few color pixels. Their RGB checks use documented M4D-specific relaxed auxiliary thresholds after diagnosis. Numeric projection, risk, and mask validation still use the pure geometry and mask cores.

## Validation Commands

```powershell
python -m py_compile simulator\m4d_config.py scripts\m4d_image_risk_common.py simulator\controllers\m4d_image_risk_validation\m4d_image_risk_validation.py scripts\validate_m4d_image_risk_dataset.py scripts\plot_m4d_image_risk.py tests\test_m4d_evaluation_helpers.py
python -m unittest discover -s tests
& "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1245 ".\simulator\worlds\m4d_image_risk_validation.wbt"
python scripts\validate_m4d_image_risk_dataset.py data\logs\m4\image_risk_validation_episode_0001.csv
python scripts\plot_m4d_image_risk.py data\logs\m4\image_risk_validation_episode_0001.csv
python scripts\validate_m4d_image_risk_dataset.py data\logs\m4\image_risk_validation_episode_0001.csv
python scripts\validate_m4c_projection_dataset.py data\logs\m4\projection_validation_episode_0003.csv
python scripts\validate_m3c_risk_dataset.py data\logs\m3\risk_validation_episode_0002.csv
python scripts\evaluate_m3d_world_risk.py
python scripts\validate_m3d_report.py
```

## Validation Results

- `py_compile`: passed.
- Unit tests: 148 passed.
- Webots generated the M4D frame, CSV, metadata JSON, and float mask JSON.
- M4D validator: exit 0.
- M4D plot: exit 0.
- M4D validator after plots: exit 0.
- M4C validator on `projection_validation_episode_0003.csv`: exit 0.
- M3C validator on `risk_validation_episode_0002.csv`: exit 0.
- M3D evaluate: exit 0.
- M3D report validator: exit 0.
- GUI manual acceptance: passed by user review.

As in earlier Webots command-line runs, the Webots shell process did not exit by itself after the controller completed; it was stopped after output files were confirmed.

## GUI Human Acceptance

GUI manual acceptance passed by user review for `image_risk_validation_episode_0001`.

Accepted observations:

1. `PLANNED_DOMINANT_VISIBLE` has planned risk `0.469831075`, state risk `0.189292428`, and combined risk `0.469831075`. It is stronger in the planned mask than the state mask, and combined selects the planned value.
2. `STATE_DOMINANT_VISIBLE` has planned risk `0.136077497`, state risk `0.226684741`, and combined risk `0.226684741`. It is stronger in the state mask than the planned mask, and combined selects the state value.
3. `SHARED_RISK_VISIBLE` has nonzero planned risk `0.074374604` and nonzero state risk `0.083360084`; combined risk is `0.083360084`.
4. `LOW_RISK_VISIBLE` is visible but weak, with combined risk `0.006903238`, clearly below dominant and shared targets.
5. `OUTSIDE_VIEW` is `outside_frustum`, `eligible_for_mask=false`, and writes zero pixels. `BEHIND_CAMERA` is `behind_camera`, has combined world risk `0.360288054`, `eligible_for_mask=false`, and writes zero pixels. This confirms that world risk exists independently of current Camera visibility.
6. `PARTIAL_VISIBLE` is `partially_visible` and writes mask pixels only inside the image boundary; the outside-image region has no mask pixels.
7. `OVERLAP_BACK` has 4218 candidate pixels and writes zero pixels; `OVERLAP_FRONT` has 4532 candidate pixels and writes 347 planned/state/combined pixels. The summary and images match pixelwise max semantics, risk is not summed above 1, and lower-risk overlapping objects do not reduce existing mask values.
8. The combined mask equals `max(planned mask, state mask)` pixelwise. Planned, state, and combined masks all have 11065 nonzero support pixels; their support regions match, while risk intensities differ.
9. The overlay has no left/right mirroring or vertical inversion, the principal point is near the image center, polygon outlines cover the corresponding Boxes, risk fill lies inside the corresponding clipped polygons, PARTIAL clips as expected, and OUTSIDE/BEHIND do not write image-mask pixels.
10. Metadata records `actual_future_trajectory_used=false`; risk and masks come from snapshot state plus the future command schedule available at that snapshot, without reading future actual trajectory.

## Visualization Note

The planned/state/combined overlay differences are visually subtle because the three masks have identical nonzero support, many risk values are low, and the overlays use transparency. The numeric masks, summary, and validator prove that the three channels differ. The current overlays are accepted diagnostic evidence, not final publication-quality figures. Later paper figures can use fixed color scales, color bars, and a planned-state difference map without changing the accepted M4D evidence.

## Limitations

- Static AABB Box obstacles only.
- One Webots snapshot and one validation scene.
- Risk is heuristic, not probability.
- No true inter-object occlusion model.
- Milestone 4 proves world-risk to image-risk mapping only.
- No image-risk compression, bytes/frame matching, network simulation, remote perception, closed-loop navigation, ROS 2, or machine learning.
