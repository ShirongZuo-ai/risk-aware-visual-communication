# Roadmap

## Milestone 0 — Repository and environment baseline

- [x] Create repository structure and durable project documents.
- [x] Verify native Windows version, Python 3.10/3.11, Git, winget, NVIDIA GPU/driver, and Webots installation on the user's machine.
- [x] Initialize Git on the user's intended Windows project folder if this workspace is not that folder.

Acceptance: all checks are recorded truthfully in `docs/progress.md`; missing software is identified before installation.

## Milestone 1 — Synchronized frame and robot-state capture

- [ ] Create one repeatable Webots world with a differential-drive robot and forward RGB camera.
- [ ] Implement minimal straight, left-turn, and right-turn motion.
- [ ] Save at least 100 camera frames.
- [ ] Save aligned CSV rows containing timestamp, pose, heading, linear velocity, angular velocity, and image path.
- [ ] Verify image paths exist and timestamps align with the CSV.
- [ ] Document exact launch and validation commands in `README.md`.

Acceptance: Webots runs; the world is repeatable; all three motions work; at least 100 aligned frame/state samples are validated; README and progress record the real results.

Do not implement risk maps, ROI compression, object detection, closed-loop navigation, ROS 2, or AI models in this milestone.

## Milestone 2 — Geometry and trajectory ground truth

- [x] Define planned command, State-only prediction, Command-conditioned prediction, and actual future trajectory.
- [x] Implement State-only constant-twist prediction.
- [x] Implement Command-conditioned differential-drive prediction from explicit future command segments.
- [x] Generate a dedicated Webots validation episode with stable and transition windows.
- [x] Evaluate ADE, FDE, yaw MAE, valid windows, and compute time for 0.5, 1.0, and 2.0 second horizons.
- [x] Estimate first empirical residual uncertainty corridors.

Acceptance: trajectory definitions are documented; predictors are unit-tested; a dedicated validation episode is actually run; stable and transition windows are reported separately; figures and progress record real results.

## Milestone 3 - Interpretable collision-risk map

### Milestone 3A - Risk formulation and interface freeze

- [x] Freeze world-coordinate trajectory-to-obstacle risk terminology.
- [x] Define Trajectory Occupancy Corridor semantics.
- [x] Define static AABB obstacle footprint data structures.
- [x] Define clearance, Time-to-Conflict, risk score, and dual-trajectory combination rules.
- [x] Freeze planned module boundaries and acceptance criteria.

Acceptance: `docs/risk_formulation_design.md` documents the risk model, data structures, module boundaries, validation scenario roles, and test plan. No risk algorithm code, Webots world, controller, CSV, figure, camera projection, ROI compression, or machine-learning component is created.

### Milestone 3B - Geometry and risk core implementation

Planned: implement the frozen ordinary-Python geometry, risk data models, trajectory-obstacle conflict analysis, and unit tests.

### Milestone 3C - Webots world-risk validation

Planned: create a Webots validation world and convert simulator ground-truth obstacles into the frozen `ObstacleFootprint` interface.

### Milestone 3D - Visualization and evaluation

Planned: generate world-coordinate risk diagnostics and report validation results before any camera projection or image risk map.

## Milestone 4 — Budget-matched compression comparison

Planned: implement Uniform, Fixed Center ROI, Object ROI, and Proposed block-wise prototypes; match target byte budgets and report mismatch.

## Milestone 5 — Offline task evaluation

Planned: evaluate communication, image-quality, and safety-critical perception metrics across scenarios and budgets.

## Milestone 6 — Simple closed-loop navigation

Planned only after offline evidence supports continuing.
