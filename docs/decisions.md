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
