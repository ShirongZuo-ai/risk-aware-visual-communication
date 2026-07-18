# System Overview

Last updated: 2026-07-18 (Asia/Shanghai)

## Completed Pipeline

Milestone 1 established a native Windows Webots R2025a/e-puck data pipeline:

1. A repeatable Webots world with an e-puck and forward RGB camera.
2. A fixed motion controller with straight, left-turn, right-turn, and stop phases.
3. Camera frame capture.
4. Per-frame aligned CSV state logging from Webots Supervisor ground truth.

Milestone 2 adds trajectory prediction and empirical uncertainty estimation:

1. State-only constant-twist prediction.
2. Command-conditioned prediction from explicit future wheel-command segments.
3. Offline comparison against actual future Webots trajectories.
4. First empirical residual corridor parameters.

Milestone 2R adds forward-arc validation without replacing the original in-place rotation validation:

1. `trajectory_validation_episode_0001` remains the in-place rotation validation episode.
2. `trajectory_validation_episode_0002` validates straight, forward-left arc, forward-right arc, and stop.
3. Stable metrics exclude command-switch transients using a documented 0.10-0.20 s transition guard.
4. Arc uncertainty is visualized as a band along the predicted path using a union of disks.

Milestone 3A freezes the world-risk design:

1. Static axis-aligned rectangular obstacle footprints in world coordinates.
2. Trajectory Occupancy Corridors around planned and state trajectories.
3. Obstacle boundary-to-trajectory geometry and clearance definitions.
4. Time-to-Conflict (`TTCf`) and interpretable spatial/temporal risk scores.
5. Independent planned/state risk outputs combined by max-union.

Milestone 3B implements the Webots-decoupled world-risk core:

1. Ordinary-Python data models for obstacles, risk parameters, and conflict results.
2. Boundary-based AABB geometry for trajectory polylines and safety-inflated corridors.
3. First corridor entry time and overlap duration from inflated segment/AABB intervals.
4. Interpretable spatial, temporal, and combined planned/state risk scores.
5. Unit-tested APIs with no Webots, camera, ROS, NumPy, Shapely, OpenCV, or ML dependency.

Milestone 3C connects the world-risk core to Webots for static AABB validation:

1. A Webots world with e-puck and six fixed, unrotated Box obstacles.
2. A controller that runs to a 7.968 s analysis snapshot and then stops.
3. A Webots adapter that converts DEF Box nodes to `ObstacleFootprint`.
4. Planned and State-only 2 s trajectories generated from current state and known command schedule.
5. A 6-row CSV validated by an ordinary-Python acceptance script.

Milestone 3D adds world-coordinate diagnostics and reporting:

1. Planned/state trajectories are rebuilt from the accepted M3C snapshot.
2. World-coordinate corridors, AABB obstacles, entry points, and risk scores are visualized.
3. Risk formulas are recalculated from CSV values.
4. Parameter sensitivity is checked for 9 sigma/tau combinations.
5. `docs/m3_world_risk_validation_report.md` records Milestone 3 validation and passed GUI acceptance status.

Milestone 4A freezes image-risk projection design without implementation:

1. World, robot body, Webots Camera device, project optical, and image pixel frames are separated.
2. Camera intrinsics are derived from actual e-puck Camera fields: `160x120`, horizontal FOV `0.84 rad`, and near clip `0.0055 m`.
3. The planned interface uses `CameraIntrinsics`, `CameraExtrinsics`, `ObstacleBox3D`, `ProjectedPoint`, and `ProjectedObstacle`.
4. 3D Boxes project to clipped image polygons and metadata, not center points alone.
5. Planned, state, and combined image-risk masks remain separate and use max-union on overlaps.
6. True rendered occlusion is explicitly out of scope until depth, segmentation, recognition, or equivalent validation evidence is selected.

Milestone 4B implements the Webots-decoupled camera projection core:

1. Camera intrinsics and extrinsics data structures.
2. World/device/optical/image transforms.
3. Pinhole projection, near-plane clipping, image-boundary clipping, and Box projection.
4. Unit-tested projection helpers with no Webots dependency.

Milestone 4C connects projection to Webots for calibration and validation:

1. A dedicated e-puck camera-projection validation world.
2. A Webots adapter that reads live Camera intrinsics, Camera node pose, and static 3D Box geometry.
3. A projection-only RGB frame, 9-row CSV, metadata JSON, and overlay.
4. Automatic RGB color-mask validation for center/left/right/partial roles.
5. Webots e-puck Camera axis calibration: `x_optical=-y_device`, `y_optical=-z_device`, `z_optical=x_device`.
6. GUI human review remains pending.

## Trajectory Types

- Planned command trajectory: the future wheel-command schedule the controller intends to execute.
- State-only predicted trajectory: a constant-twist extrapolation from current actual state only.
- Command-conditioned trajectory: a nominal differential-drive rollout from current state plus explicit future command segments.
- Actual trajectory: Webots ground truth observed later, used only for offline evaluation.

## Current Data Sources

- Milestone 1D CSV: `data/logs/m1d/episode_0001.csv`
- Milestone 2 in-place validation CSV: `data/logs/m2/trajectory_validation_episode_0001.csv`
- Milestone 2R forward-arc validation CSV: `data/logs/m2/trajectory_validation_episode_0002.csv`
- Milestone 3C accepted risk validation CSV: `data/logs/m3/risk_validation_episode_0002.csv`
- Milestone 3D generated trajectories: `data/logs/m3/risk_validation_episode_0002_trajectories.csv`
- Milestone 3D diagnostics: `results/m3_world_risk/`
- Milestone 4A projection design: `docs/image_risk_projection_design.md`
- Milestone 4C projection CSV: `data/logs/m4/projection_validation_episode_0003.csv`
- Milestone 4C RGB frame: `data/frames/m4/projection_validation_episode_0003.png`
- Milestone 4C overlay: `results/m4_projection/projection_overlay.png`
- Milestone 2 results: `results/m2_trajectory/`
- Milestone 2R arc results: `results/m2_trajectory_arc/`

Generated data and results are ignored by Git.

## Coordinate and State Definitions

- Ground plane: Webots world `x-y`
- Vertical axis: `z`
- Yaw: heading of the e-puck local `+x` axis around world `+z`
- Linear velocity: ground-plane speed magnitude
- Angular velocity: world-frame angular velocity around `+z`

## Milestone 2 Inputs and Outputs

Inputs:

- Current actual state from CSV
- Future explicit command segments
- Actual future CSV rows for offline evaluation only

Outputs:

- Predicted state-only trajectories
- Predicted command-conditioned trajectories
- ADE, FDE, yaw MAE, valid window counts, and compute time
- Empirical residual corridor radii
- Diagnostic trajectory figures
- Stable and transition windows separated by profile-specific phase labels

## Milestone 3 Inputs and Outputs

Inputs:

- Planned command-conditioned trajectory in world coordinates
- State-only trajectory in world coordinates
- Trajectory Occupancy Corridor radius
- Static AABB obstacle footprints in world coordinates
- Risk parameters: `sigma_distance_m`, `tau_time_s`, and `maximum_horizon_s`

Outputs:

- Per-obstacle planned trajectory conflict result
- Per-obstacle state trajectory conflict result
- Clearance, closest time, Time-to-Conflict, overlap duration, spatial score, temporal score, and risk score
- Trajectory disagreement between planned and state trajectories
- Combined risk score defined as `max(planned_risk, state_risk)`
- Ordinary-Python API calls in `risk_map/` for the world-coordinate risk core

## Downstream Use

The later risk module should consume a trajectory corridor rather than a single exact line. The corridor combines robot half-width, measured prediction error quantile, and a safety margin, and should be interpreted as a band along the predicted path.

Milestone 3B keeps this in world coordinates. Milestone 3D still keeps risk in world coordinates. The Webots adapter provides obstacle ground truth only; it does not project into camera pixels.

Milestone 4C validates static obstacle 3D Box projection into image polygons against a real Webots RGB frame. Future M4D code should fill planned/state/combined image-risk masks over validated clipped obstacle regions. It should not project empty trajectory corridors as the main Risk ROI.

## Explicitly Not Implemented

The project still does not implement image risk masks, ROI compression, object detection, closed-loop navigation, ROS 2, WSL, or machine learning.
