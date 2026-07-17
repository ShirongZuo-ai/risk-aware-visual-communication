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

## Trajectory Types

- Planned command trajectory: the future wheel-command schedule the controller intends to execute.
- State-only predicted trajectory: a constant-twist extrapolation from current actual state only.
- Command-conditioned trajectory: a nominal differential-drive rollout from current state plus explicit future command segments.
- Actual trajectory: Webots ground truth observed later, used only for offline evaluation.

## Current Data Sources

- Milestone 1D CSV: `data/logs/m1d/episode_0001.csv`
- Milestone 2 in-place validation CSV: `data/logs/m2/trajectory_validation_episode_0001.csv`
- Milestone 2R forward-arc validation CSV: `data/logs/m2/trajectory_validation_episode_0002.csv`
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

Milestone 3B keeps this in world coordinates. Camera projection, image-space risk maps, and compression allocation remain downstream work.

## Explicitly Not Implemented

The project still does not implement Webots M3 risk worlds, camera projection, image risk maps, ROI compression, object detection, closed-loop navigation, ROS 2, WSL, or machine learning.
