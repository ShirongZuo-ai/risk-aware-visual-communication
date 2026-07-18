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
6. GUI human review passed.

Milestone 4D-1 and 4D-2 implement and validate image-space risk masks:

1. A Webots-decoupled pure-Python mask core fills planned, state, and combined channels over projected clipped obstacle polygons.
2. A dedicated M4D Webots scene samples one 7.968 s snapshot and computes world risk, Camera projection, and image masks from that same snapshot.
3. Numeric masks are saved as row-major floating-point arrays; PNG masks are visualization-only quantized copies.
4. Automatic validation recomputes trajectories, world risks, projections, and masks from metadata and checks exact ID binding, max-union overlap, invisible-obstacle skipping, exclusive-pixel risk binding, and RGB geometry alignment.
5. GUI human acceptance for M4D passed, and Milestone 4 is formally accepted.

Milestone 5A freezes the compression and fair-bitrate protocol without implementation:

1. The first prototype is a tiled-JPEG spatial allocation experiment, not a standards-compatible ROI video codec.
2. All methods share the same `160x120` frame, `20x20` tile grid, deterministic container, encoder, decoder, and budget matcher.
3. Uniform, Center ROI, Object ROI, and Risk ROI are the frozen first baselines.
4. Risk ROI uses the accepted combined image-risk mask and must not use future actual trajectories or downstream evaluation results.
5. Budgets are selected after a Uniform JPEG pilot in Milestone 5B, not hard-coded during 5A.

Milestone 5B implements the shared Uniform tiled-JPEG codec foundation:

1. A deterministic Pillow-based tile encoder/decoder for the frozen `160x120`, `20x20`, 48-tile grid.
2. A strict binary container with a 23-byte header, 48 six-byte index entries, and row-major JPEG payloads.
3. Actual-byte accounting where `total_bytes = container_overhead_bytes + sum(tile_jpeg_payload_bytes)`.
4. Exhaustive Uniform quality matching over JPEG qualities 1 through 95, with no over-budget candidate selection.
5. A Uniform pilot on `image_risk_validation_episode_0001.png` that records development budgets only.

Milestone 5C implements spatial scoring and allocation while keeping the M5B transport backend unchanged:

1. Center ROI scores normalized Gaussian distance from the fixed camera principal point.
2. Object ROI scores maximum clipped-polygon coverage for eligible visible M4D obstacles.
3. Risk ROI scores the maximum value of the accepted combined floating-point image-risk mask per tile.
4. All non-Uniform methods share one pre-encoded tile cache and exhaustive actual-byte candidate search; Uniform continues to use its accepted M5B matcher.
5. The resulting 16 method-budget allocation rows validate byte accounting and no-future-actual inputs only, not image quality or task benefit.

Milestone 5D evaluates those already fixed 16 allocations without invoking a matcher or changing the selected quality maps:

1. Each saved M5C quality tuple is deterministically re-encoded, serialized, decoded, and checked against its original actual container bytes.
2. The evaluator measures full RGB MSE/PSNR/SSIM, continuous combined-mask risk-weighted MSE/PSNR, and pixel-center eligible-object, high-risk (`combined >= 0.20`), and background regional MSE/PSNR.
3. Generated CSV, metadata, decoded PNGs, and diagnostics are ignored development evidence for one `160x120` M4D snapshot.
4. This is not a perception, communication, collision-probability, navigation, or multi-frame generalization result; M5E is the next priority for broader offline evidence.

Milestone 5E-A freezes the broader offline experiment without generating data:

1. Development, 64-frame calibration, and 256-frame formal splits are disjoint.
2. Eight static-AABB scenario families cover straight risk, visual distractors, left/right turns, planned/state disagreement, area-risk disagreement, partial visibility, and low-risk controls.
3. Four method-independent snapshots per episode use fixed reference-motion progress.
4. Calibration alone establishes four common feasible actual-byte budgets; formal data cannot alter them.
5. Formal inference aggregates snapshots within episodes and uses paired, scenario-stratified bootstrap resampling.
6. Engineering validity is separated from scientific support, and failed or unfavorable episodes cannot be silently removed.

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
- Milestone 4D image-risk CSV: `data/logs/m4/image_risk_validation_episode_0001.csv`
- Milestone 4D float masks: `data/masks/m4/image_risk_validation_episode_0001_masks.json`
- Milestone 4D RGB frame: `data/frames/m4/image_risk_validation_episode_0001.png`
- Milestone 4D diagnostics: `results/m4_image_risk/`
- Milestone 5A compression protocol: `docs/m5_compression_and_bitrate_protocol.md`
- Milestone 5B validation report: `docs/m5b_tiled_jpeg_validation_report.md`
- Milestone 5B generated Uniform pilot CSV: `data/logs/m5/m5b_uniform_quality_sweep.csv`
- Milestone 5B generated Uniform pilot metadata: `data/metadata/m5/m5b_uniform_pilot.json`
- Milestone 5B generated payload curve: `results/m5_compression/m5b_uniform_payload_curve.png`
- Milestone 5C allocation CSV: `data/logs/m5/m5c_allocation_validation.csv`
- Milestone 5C allocation metadata: `data/metadata/m5/m5c_allocation_validation.json`
- Milestone 5C allocation diagnostics: `results/m5_compression/`
- Milestone 5D quality CSV: `data/logs/m5/m5d_single_frame_quality.csv`
- Milestone 5D quality metadata and decoded frames: `data/metadata/m5/m5d_single_frame_evaluation.json`, `data/decoded/m5/m5d/`
- Milestone 5D diagnostics and report: `results/m5_compression/m5d_*.png`, `docs/m5d_single_frame_evaluation_report.md`
- Milestone 5E-A protocol: `docs/m5e_multiscene_offline_evaluation_protocol.md`
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

Milestone 4C validates static obstacle 3D Box projection into image polygons against a real Webots RGB frame. Milestone 4D fills planned/state/combined image-risk masks over validated clipped obstacle regions. It does not project empty trajectory corridors as the main Risk ROI.

Milestone 5A defines how later compression experiments consume accepted image-risk masks. Milestone 5B adds the shared Uniform tiled-JPEG backend and budget pilot. Milestone 5C adds Center/Object/Risk scoring and shared actual-byte allocation on the M4D development snapshot. Milestone 5D measures fixed-allocation single-frame quality only. Milestone 5E-A freezes the future multi-scene protocol but creates no data or implementation. It does not select a generally best method, add a network model, remote perception, or navigation code.

## Explicitly Not Implemented

The project still does not implement M5E multi-scene data generation or formal statistics, object detection, closed-loop navigation, ROS 2, WSL, or machine learning.
