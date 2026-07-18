# Milestone 4C Camera Projection Validation Report

Last updated: 2026-07-18 (Asia/Shanghai)

## Status

Milestone 4C Webots camera-projection validation is formally accepted on `feature/m4-image-risk-projection`.

GUI human review passed by user review after the automated validation.

## Scope

This milestone validates geometric projection alignment between the Webots R2025a e-puck forward RGB Camera and the pure-Python projection core. It does not generate image-risk masks, planned/state/combined risk masks, ROI compression, JPEG/video outputs, network simulation, closed-loop navigation, machine learning, or real occlusion models.

## Evidence Dataset

Official automated validation episode:

```text
data/frames/m4/projection_validation_episode_0003.png
data/logs/m4/projection_validation_episode_0003.csv
data/metadata/m4/projection_validation_episode_0003.json
results/m4_projection/projection_overlay.png
```

GUI reproduction and human acceptance episode:

```text
projection_validation_episode_0004
```

Debug calibration episodes:

- `episode_0001`: showed that the Milestone 4A initial `diag(1,-1,-1)` Webots-device mapping was inconsistent with actual e-puck camera rendering.
- `episode_0002`: validated the corrected axis mapping, but still treated the depth-overlap front Box as a full color-mask target.

The accepted automatic image-alignment, IoU, and validator evidence is `episode_0003`. `episode_0004` is GUI reproduction and human acceptance evidence only; it does not replace the official automatic metrics or generated report artifacts.

## Camera Parameters

The controller read the following values from the live Webots Camera API and Camera node:

- Camera device: `camera`
- Width: `160 px`
- Height: `120 px`
- Horizontal FOV: `0.840000000 rad`
- Vertical FOV: `0.646372669 rad`
- Near clip: `0.005500000 m`
- `fx = fy = 179.142225973 px`
- Principal point: `cx=79.5 px`, `cy=59.5 px`
- Snapshot time: `0.320 s`
- Camera world position: `(0.030000000, -0.000000308, 0.027948551) m`

## Webots Camera Axis Calibration

The R2025a e-puck Camera node pose was read through `Supervisor.getFromDevice(camera_tag)` and `Node.getPose()`.

Automatic validation against the saved RGB frame showed that the e-puck Camera node frame used for this project must be mapped to the project optical frame as:

```text
x_optical = -y_device
y_optical = -z_device
z_optical =  x_device
```

Matrix form:

```text
R_device_to_optical =
[ 0 -1  0
  0  0 -1
  1  0  0 ]
```

This supersedes the initial Milestone 4A assumption `diag(1,-1,-1)` for the Webots e-puck adapter only. The pure projection core remains generic and Webots-decoupled.

## Validation Scene Roles

| Role | Center `(x,y,z)` m | Actual visibility |
| --- | ---: | --- |
| `CENTER_VISIBLE` | `(0.320, 0.000, 0.045)` | `fully_visible` |
| `LEFT_VISIBLE` | `(0.380, 0.115, 0.045)` | `fully_visible` |
| `RIGHT_VISIBLE` | `(0.380, -0.115, 0.045)` | `fully_visible` |
| `PARTIAL_IMAGE_EDGE` | `(0.270, -0.145, 0.045)` | `partially_visible` |
| `OUTSIDE_FRUSTUM` | `(0.350, 0.420, 0.045)` | `outside_frustum` |
| `BEHIND_CAMERA` | `(-0.160, 0.000, 0.045)` | `behind_camera` |
| `NEAR_PLANE_INTERSECTION` | `(0.037, 0.000, 0.028)` | `intersects_near_plane` |
| `DEPTH_OVERLAP_FRONT` | `(0.340, 0.010, 0.045)` | `fully_visible` |
| `DEPTH_OVERLAP_BACK` | `(0.480, 0.020, 0.045)` | `fully_visible` |

## Automatic Image Metrics

Color-mask IoU is enforced for `CENTER_VISIBLE`, `LEFT_VISIBLE`, `RIGHT_VISIBLE`, and `PARTIAL_IMAGE_EDGE`. Depth-overlap objects are evaluated geometrically because real RGB occlusion is explicitly outside the first projection-core model.

| Role | BBox IoU | Polygon IoU | Center error px | Width rel. error | Height rel. error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `CENTER_VISIBLE` | `0.926` | `0.943` | `0.027` | `0.023` | `0.052` |
| `LEFT_VISIBLE` | `0.914` | `0.889` | `0.131` | `0.033` | `0.055` |
| `RIGHT_VISIBLE` | `0.887` | `0.862` | `0.590` | `0.062` | `0.055` |
| `PARTIAL_IMAGE_EDGE` | `0.767` | `0.859` | `2.549` | `0.047` | `0.195` |

Other automatic checks passed:

- CSV contains 9 rows with unique roles.
- Camera parameters match the frozen e-puck values.
- LEFT projects left of the principal point and RIGHT projects right of it.
- CENTER is near the principal point.
- OUTSIDE and BEHIND have no valid clipped polygon and their target colors are absent from the frame.
- NEAR_PLANE projection is finite and valid.
- DEPTH_OVERLAP_FRONT and DEPTH_OVERLAP_BACK projected bounding boxes overlap.
- Output paths do not contain `Downloads`.

## Commands Run

```powershell
.\.venv\Scripts\python.exe -m py_compile simulator\m4c_config.py simulator\adapters\webots_camera_adapter.py simulator\controllers\m4_camera_projection_validation\m4_camera_projection_validation.py scripts\validate_m4c_projection_dataset.py scripts\plot_m4c_projection_overlay.py tests\test_webots_camera_adapter_helpers.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
& "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1242 ".\simulator\worlds\m4_camera_projection_validation.wbt"
.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py .\data\logs\m4\projection_validation_episode_0003.csv
.\.venv\Scripts\python.exe .\scripts\plot_m4c_projection_overlay.py .\data\logs\m4\projection_validation_episode_0003.csv
.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py .\data\logs\m4\projection_validation_episode_0003.csv
```

## Validation Results

- `py_compile`: passed.
- Unit tests: `110` tests passed.
- Webots controller wrote 9 projection rows, frame PNG, and metadata JSON.
- M4C validator: exit code 0.
- Overlay plot: exit code 0.
- Re-run M4C validator after overlay generation: exit code 0.
- GUI manual acceptance: passed by user review.

The Webots command-line process remained open after the controller returned, matching previous project behavior. The process was stopped after outputs were verified.

## GUI Human Acceptance

User-confirmed GUI evidence:

1. Scene Tree contained all 9 validation Box DEF nodes.
2. `LEFT_VISIBLE` appeared on the image left and `RIGHT_VISIBLE` appeared on the image right.
3. LEFT/RIGHT were not mirrored.
4. Overlay was not vertically inverted.
5. CENTER was near the image center and the principal point was near image center.
6. CENTER, LEFT, and RIGHT projected outlines covered the corresponding Boxes.
7. `PARTIAL_IMAGE_EDGE` was clipped only at the expected right image boundary.
8. `OUTSIDE_FRUSTUM` and `BEHIND_CAMERA` had no valid image region.
9. `DEPTH_OVERLAP_FRONT` and `DEPTH_OVERLAP_BACK` projected regions overlapped.
10. Real visual occlusion of the back Box is not treated as a Milestone 4C geometric-projection failure.
11. `NEAR_PLANE_INTERSECTION` had `intersects_near_plane`, finite projection, no NaN or Inf, and safe clipping to image bounds. Its broad orange outline is expected diagnostic geometry, not an image risk mask or normal ROI experiment.
12. GUI episode `episode_0004` reported camera `160x120`, FOV `0.84`, near `0.0055`, snapshot time `0.320`, `obstacle_rows=9`, saved frame/CSV outputs, `m4_camera_projection_validation: complete`, and successful controller exit.
13. Console had no `Traceback`, `AttributeError`, or `status: 1`.

## Limitations

- The dataset is projection-only. It contains no planned, state, or combined risk fields; Milestone 4D will add image-risk mask fields.
- RGB color masks validate alignment for selected roles only.
- True rendered inter-object occlusion is not modeled by the projection core.
- No planned/state/combined image risk masks have been generated yet.
