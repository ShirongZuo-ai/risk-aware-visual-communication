# Decision log

## 2026-07-17 — Phase 1 scope and implementation strategy

- **Decision:** Start with a native-Windows Webots/Python research prototype using simulator ground truth and interpretable geometric risk.
- **Reason:** It isolates the research hypothesis with low infrastructure cost and makes the risk mechanism auditable.
- **Rejected for now:** ROS 2, WSL, real networking/hardware, reinforcement learning, VLA models, learned codecs, and full video-codec integration.
- **Impact:** Milestone 1 is limited to synchronized camera/state capture; no risk or compression code is permitted yet.

## 2026-07-17 — Communication comparison policy

- **Decision:** Compare policies at matched or closely matched actual byte budgets of 5, 10, 20, and 40 KB/frame.
- **Reason:** Resource allocation cannot be credited for gains obtained by sending more data.
- **Rejected:** Comparing methods only at nominal quality settings or unequal byte counts.
- **Impact:** Every later evaluation must log actual bytes and budget mismatch.

## 2026-07-17 — Terminology

- **Decision:** Call the Phase 1 codec component a “block-wise spatial compression prototype.”
- **Reason:** The prototype is not a standards-compatible ROI video encoder.
- **Rejected:** Claims of implementing H.265/VVC ROI coding without such an implementation.
- **Impact:** Papers, README, figures, and reports must use constrained terminology.

## 2026-07-17 — Project Python environment

- **Decision:** Use a project-local `.venv` with 64-bit Python 3.11.14, bootstrapped from an existing Conda Python 3.11 interpreter without inheriting its site packages.
- **Reason:** Python 3.11 matches the selected project range, while the PATH default is Python 3.12.7 and the Windows Python Launcher does not discover the installed Conda interpreters.
- **Rejected:** Installing project dependencies into the existing Open WebUI or RAG Conda environments, or using the PATH-default Python 3.12 before compatibility is established.
- **Impact:** Run project Python commands through `.\.venv\Scripts\python.exe`; dependencies remain uninstalled until the next environment step.

## 2026-07-17 — Webots stable release

- **Decision:** Use the official Cyberbotics Webots R2025a Windows release downloaded from the project's official GitHub release.
- **Reason:** R2025a is the latest non-draft, non-prerelease release reported by the official GitHub API, and its command-line runtime passes version and system-information checks on this machine.
- **Rejected:** Nightly builds, third-party mirrors, package identifiers absent from the local winget catalog, and adding ROS 2 or other simulator integrations during environment setup.
- **Impact:** The verified executable is under `$env:ProgramFiles\Webots\msys64\mingw64\bin`; Milestone 1 may use this installation, but no custom world or controller was created during installation verification.

## 2026-07-17 — Milestone 1A robot model

- **Decision:** Use the official GCtronic e-puck model for the first Webots scene and initial synchronized capture work.
- **Reason:** The R2025a official e-puck model is mature, differential-drive, compact, and includes a forward RGB camera. It is enough to verify repeatable robot placement, camera availability, and later frame/state logging without ROS 2 or real hardware.
- **Rejected for now:** TurtleBot, larger mobile robots, and a custom robot model.
- **Impact:** Milestone 1A uses `E-puck.proto` with no custom controller. Later Milestone 1 work should use the official device names confirmed from R2025a: camera device `camera`, left motor `left wheel motor`, and right motor `right wheel motor`.

## 2026-07-17 — Milestone 1D ground-truth state logging

- **Decision:** Use Webots Supervisor ground truth from the same e-puck controller for Milestone 1D state logging.
- **Reason:** The R2025a Python Supervisor API provides the robot's own node through `Supervisor.getSelf()`, with world position from `Node.getPosition()`, orientation matrix from `Node.getOrientation()`, and 6D velocity from `Node.getVelocity()`. This avoids adding GPS, Compass, InertialUnit, ROS 2, or custom sensors.
- **Rejected for now:** GPS/Compass/InertialUnit devices, separate supervisor robot, wall-clock timestamps, and independent state-sampling threads.
- **Coordinate convention:** The verified world uses the Webots `x-y` plane as the ground plane and `z` as the vertical axis. Position fields `robot_x`, `robot_y`, and `robot_z` are Webots world coordinates.
- **Yaw definition:** The e-puck forward direction is local `+x`; yaw is computed from the row-major orientation matrix as `atan2(orientation[3], orientation[0])` and normalized to `[-pi, pi]`.
- **Velocity definition:** `linear_velocity_m_s` is the magnitude of the actual world-frame ground-plane velocity, `sqrt(vx^2 + vy^2)`, using the first two components of `Node.getVelocity()`. `angular_velocity_rad_s` is the actual world-frame angular velocity around vertical `+z`, using the sixth component of `Node.getVelocity()`.
- **Synchronization policy:** One CSV row is written immediately after each successful `camera.saveImage()` call in the same controller loop and at the same Webots simulation time. If image saving fails, no CSV row is written for that frame.

## 2026-07-17 — Milestone 2 trajectory sources

- **Decision:** Implement State-only as the lowest-information baseline and Command-conditioned as the first main trajectory source.
- **Reason:** State-only tests how far current state extrapolation can go, while Command-conditioned uses the controller's explicit future command plan without reading future ground truth.
- **Actual future trajectory policy:** Actual Webots future trajectory is used only for offline evaluation of prediction error and never as online predictor input.
- **e-puck geometry:** Use official Webots R2025a e-puck values from `projects/robots/gctronic/e-puck/controllers/e-puck/e-puck.c`: wheel radius `0.02 m`, axle length `0.052 m`. The official controller computes orientation change as `(dr - dl) / AXLE_LENGTH`, matching `angular_velocity = r / L * (omega_right - omega_left)`.
- **Uncertainty corridor:** Use empirical residual quantiles from finite simulation data for the first corridor. The default corridor radius is `robot_half_width + 90% position-error quantile + 0.01 m safety margin`.
- **Rejected for now:** Machine learning trajectory prediction, LSTM/Transformer models, slip-specific modeling, and treating planned commands as guaranteed actual motion.
- **Future direction:** Machine learning may later be used for physics residual correction and slip uncertainty estimation, not as a replacement before interpretable baselines are measured.

## 2026-07-17 - Milestone 2R transition guard and arc validation

- **Decision:** Preserve `trajectory_validation_episode_0001` as the in-place rotation validation episode and add a separate forward-arc validation episode, `trajectory_validation_episode_0002`.
- **Reason:** The original episode is useful for command-transition yaw stress testing, but it does not validate forward curved motion because its turn phases rotate in place with near-zero linear velocity.
- **Decision:** Mark prediction windows intersecting `[command_switch + 0.10 s, command_switch + 0.20 s]` as transition, and allow stable labels only after `command_switch + 0.20 s`.
- **Reason:** This prevents frames immediately after a command switch, before actuator/state response has settled, from being counted as stable.
- **Decision:** Render the empirical uncertainty corridor as a union of disks along the predicted trajectory.
- **Reason:** Downstream risk modules need a band around the path, not a single uncertainty circle at the starting pose.
- **Rejected for now:** Merging the in-place and arc episodes into one CSV, overwriting original Milestone 2 figures, adding obstacle risk/TTC/risk maps, or introducing learned trajectory models.
- **Impact:** Milestone 2 evaluation now supports named profiles (`in_place` and `arc`), with arc-only outputs under `results/m2_trajectory_arc/`.
