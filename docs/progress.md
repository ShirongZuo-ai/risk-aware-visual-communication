# Progress

Last updated: 2026-07-18 (Asia/Shanghai)

## Completed

- Confirmed that the formal project root is `C:\Users\ROG\Documents\risk-aware-visual-communication` on the native Windows host.
- Verified that `git rev-parse --show-toplevel` resolves to the formal Documents path. In the current PowerShell session, `git` is not on PATH, so verification used `C:\Program Files\Git\cmd\git.exe`.
- Confirmed the local no-commit branch is `main`. The requested `master` to `main` rename had already been applied before this verification pass; no remote is configured and nothing was pushed.
- Verified the copied project `.venv`: `.\.venv\Scripts\python.exe` runs Python 3.11.14, 64-bit, with the environment prefix under the formal Documents path.
- Installed the official Cyberbotics Webots R2025a stable Windows release and verified its command-line runtime and graphics-system detection.
- Completed Milestone 1A: created and GUI-verified a minimal repeatable Webots e-puck camera world.
- Completed Milestone 1B: created and Webots-verified a minimal fixed-sequence Python motion controller for straight, left-turn, right-turn, and stop.
- Completed Milestone 1C: captured and validated at least 100 PNG frames from the existing e-puck forward RGB camera during Webots runtime.
- Completed Milestone 1D: wrote one strictly aligned CSV state row for each saved image frame using Webots Supervisor ground truth.
- Completed Milestone 2: implemented State-only and Command-conditioned trajectory predictors, evaluated them on a dedicated Webots validation episode, and estimated first empirical uncertainty corridors.
- Completed Milestone 2R: preserved the original in-place rotation validation, added a forward-arc validation episode, improved stable/transition window labeling, and regenerated arc-only evaluation figures.
- Accepted Milestone 2R and the cleanup fix after GUI review; prepared `feature/m3-world-risk` for the next milestone without adding Milestone 3 code.
- Completed Milestone 3A: froze the world-coordinate trajectory-to-obstacle risk formulation, data structures, module boundaries, validation scenario roles, and acceptance criteria without implementing risk algorithms.
- Completed Milestone 3B: implemented and unit-tested the Webots-decoupled world-coordinate risk geometry core.
- Completed Milestone 3C: connected the risk core to a Webots multi-obstacle validation scene and generated an automatically validated 6-row world-risk CSV.
- Completed Milestone 3D automated diagnostics and Milestone 3D-R figure-readability corrections: generated world-coordinate figures, summary tables, parameter sensitivity checks, and the Milestone 3 validation report from accepted episode_0002.
- Accepted Milestone 3 after user GUI and figure review. `episode_0002` remains the official evidence data; `episode_0005` is GUI reproduction evidence only.
- Completed Milestone 4A: froze world-risk-to-camera-image projection design, interfaces, terminology, validation roles, and acceptance criteria without creating projection code or M4 data.
- Completed Milestone 4B: implemented and unit-tested the Webots-decoupled pure-Python camera projection core.
- Completed and accepted Milestone 4C: created a dedicated Webots camera-projection validation scene, connected the projection core through a Webots adapter, saved one RGB snapshot plus a 9-row projection CSV and metadata JSON, generated an overlay, passed automatic image-alignment validation, and passed GUI human review.

## Native Windows environment results

- OS: Microsoft Windows 11 Home China, version 25H2, build 26200.8875, 64-bit.
- PowerShell: Windows PowerShell 5.1.26100.8875.
- Working directory and Git top level: `C:\Users\ROG\Documents\risk-aware-visual-communication`.
- Project Python: `.\.venv\Scripts\python.exe`, Python 3.11.14, 64-bit. The copied environment executed successfully after the project move.
- PATH-default Python: 64-bit Anaconda Python 3.12.7 at `D:\Anaconda\python.exe`.
- Python Launcher: `C:\Windows\py.exe`, launcher file version 3.9.10150.1013; it does not discover the installed Conda interpreters.
- Git: 2.55.0.windows.3 at `C:\Program Files\Git\cmd\git.exe`. The repository is on the no-commit `main` branch; all project files are untracked and no remote is configured. The bare `git` command is not available on the current PowerShell PATH.
- winget: 1.29.280. No exact `Cyberbotics.Webots` package was present in the configured winget source.
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU, driver 561.00, 8188 MiB VRAM.
- WSL: installed but remains out of scope as the development environment.

## Webots installation and verification

- Release: Cyberbotics Webots R2025a, the latest official stable release reported by the Cyberbotics GitHub API on 2026-07-17 (`prerelease=false`, `draft=false`; originally published 2025-02-04).
- Source: `https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a_setup.exe`.
- Installer size: 262,879,830 bytes, matching the official release API metadata.
- Installer SHA-256: `9E326A54C104FC5FC88121E26014A409D1E35F0BBF30E23F3A712E7F842B08E7`.
- Installer metadata: Cyberbotics, Ltd.; product Webots; product version R2025a. The installer is not Authenticode-signed, consistent with the official installation documentation's Windows SmartScreen warning guidance.
- Installation registry entry: Webots R2025a, publisher Cyberbotics, Ltd., installed at `C:\Program Files\Webots`.
- Executable: `C:\Program Files\Webots\msys64\mingw64\bin\webots.exe`.
- `webots.exe --version`: returned `Webots version: R2025a`, exit code 0.
- `webots.exe --help`: returned command usage, exit code 0.
- `webots.exe --sysinfo`: exit code 0; detected Windows 11 25H2, Intel Core Ultra 9 185H, NVIDIA GeForce RTX 4060 Laptop GPU, OpenGL 4.6.0, and NVIDIA driver 561.00.
- No custom world was opened or created during verification.

## Milestone 1A: minimal repeatable Webots scene

- Stage: Milestone 1A, minimal e-puck camera scene only.
- Project root: `C:\Users\ROG\Documents\risk-aware-visual-communication`.
- Git top level: `C:/Users/ROG/Documents/risk-aware-visual-communication`, verified with `C:\Program Files\Git\cmd\git.exe`.
- Git branch and commit state: `main`, no commits yet. No remote is configured.
- Git identity: `user.name` and `user.email` were both unset, so the requested initial commit was not created and no Git configuration was changed.
- Created world: `simulator/worlds/minimal_epuck_camera.wbt`.
- Robot model: official Cyberbotics/GCtronic `E-puck.proto`, `version "2"`, no custom controller.
- Controller setting at Milestone 1A validation time: `controller "<none>"`; no Python, C, C++, ROS, motion, logging, risk, compression, perception, or navigation controller existed yet.
- Camera device: `camera`, confirmed from the official R2025a e-puck controller source using `wb_robot_get_device("camera")`.
- Camera node and resolution: official R2025a `E-puck.proto` defines `DEF EPUCK_CAMERA Camera`; this scene sets `camera_width 160` and `camera_height 120`, matching the official R2025a `e-puck2.wbt` example.
- Wheel motor device names: `left wheel motor` and `right wheel motor`, confirmed from the official R2025a `E-puck.proto` and e-puck controller source.
- Ground: official `RectangleArena.proto`, `floorSize 1.5 1.5`, `wallHeight 0.04`.
- Obstacle: official `WoodenBox.proto`, `name "front obstacle"`, `size 0.08 0.08 0.1`, `translation 0.35 0 0.05`, `locked TRUE`.
- Robot placement: `translation 0 0 0`, `rotation 0 0 1 0`. The obstacle is fixed 0.35 m in front of the robot and does not overlap the robot initial pose by construction.
- Webots launch command:

```powershell
& "$env:ProgramFiles\Webots\msys64\mingw64\bin\webots.exe" ".\simulator\worlds\minimal_epuck_camera.wbt"
```

### Milestone 1A verification actually run

- Read official installed R2025a example worlds under `C:\Program Files\Webots\projects\robots\gctronic\e-puck\worlds`.
- Read official R2025a PROTO definitions from the same version-locked Cyberbotics URLs used by the installed R2025a example worlds.
- Verified `RectangleArena.proto`, `TexturedBackground.proto`, `TexturedBackgroundLight.proto`, `WoodenBox.proto`, and `E-puck.proto` field names from official R2025a sources.
- Verified the installed Webots executable path: `C:\Program Files\Webots\msys64\mingw64\bin\webots.exe`.
- Ran command-line world load with `--batch --mode=pause --minimize --stdout --stderr .\simulator\worlds\minimal_epuck_camera.wbt`.
- Webots stayed running after the load command and produced empty stdout/stderr logs at `results/webots_m1a_stdout.log` and `results/webots_m1a_stderr.log`; no immediate `unknown node`, `unknown field`, or PROTO load error was printed.
- Webots created/updated user cache assets during the load attempt, consistent with resolving EXTERNPROTO resources.
- Stopped the Webots process after the short command-line load check.

### Milestone 1A passed automatically

- World file exists in the project under `simulator/worlds/minimal_epuck_camera.wbt`.
- World file has no personal absolute paths and no Downloads path references.
- World file uses R2025a official EXTERNPROTO declarations only.
- e-puck camera and wheel device names were confirmed from official R2025a sources.
- Command-line loading produced no stdout/stderr error text during the short load window.

### Milestone 1A GUI confirmation completed by user

- Ground, e-puck, and obstacle displayed normally.
- The robot was on the ground and had no initial collision.
- Simulation ran normally.
- With no controller, the robot remained still and did not move.
- Pause worked normally.
- Reset worked normally.
- Webots Console had no red errors.

### Milestone 1A warnings and issues

- `git` is installed but still unavailable as a bare command in the current PowerShell PATH; full path invocation was used.
- Git identity is not configured, so no initial commit was made.
- `webots.exe --log-performance=<file>,10` did not exit within the 60 second tool timeout and did not create the requested performance log; that command was not used as a pass/fail criterion for world validity.
- Scene Tree camera visibility was not separately restated in the user's GUI confirmation, but the Webots project file recorded the rendering device as `e-puck:camera`, and the camera device name/resolution were confirmed from official R2025a sources.

## Milestone 1B: minimal fixed-time motion controller

- Stage: Milestone 1B, minimal fixed-sequence motion only.
- Controller created: `simulator/controllers/minimal_epuck_motion/minimal_epuck_motion.py`.
- World updated: `simulator/worlds/minimal_epuck_camera.wbt` now uses `controller "minimal_epuck_motion"`.
- Robot model: official R2025a `E-puck.proto`, `version "2"`.
- Motor device names: `left wheel motor` and `right wheel motor`.
- Control mode: wheel motors are set to infinite position and commanded by velocity.
- No camera image saving, CSV logging, obstacle avoidance, trajectory prediction, TTC, risk map, ROI compression, ROS 2, WSL, or requirements installation was added.

### Milestone 1B action timing

- `0.0 <= t < 1.2 s`: straight, left wheel `2.00 rad/s`, right wheel `2.00 rad/s`.
- `1.2 <= t < 2.2 s`: left turn, left wheel `-1.50 rad/s`, right wheel `1.50 rad/s`.
- `2.2 <= t < 3.2 s`: right turn, left wheel `1.50 rad/s`, right wheel `-1.50 rad/s`.
- `t >= 3.2 s`: stop, both wheels `0.00 rad/s`; the controller exits after `3.7 s` after commanding stop.

### Milestone 1B verification actually run

- Ran Python bytecode compilation with `.\.venv\Scripts\python.exe -m py_compile .\simulator\controllers\minimal_epuck_motion\minimal_epuck_motion.py`; exit code 0.
- Ran Webots R2025a with the world and controller in batch/fast mode on port 1237.
- Because Webots stays open after loading the world, the command timed out at the tool level and the new validation Webots process was stopped after checking results.
- For validation only, set `M1B_VALIDATION_TRACE` so the controller wrote a plain text trace to `results/webots_m1b_controller_trace.log`; normal controller runs do not write this file.
- The trace recorded:

```text
minimal_epuck_motion: start
sequence: 0.0-1.2s straight, 1.2-2.2s left_turn, 2.2-3.2s right_turn, 3.2s+ stop
phase=straight t=0.032s left=2.00 right=2.00
phase=left_turn t=1.216s left=-1.50 right=1.50
phase=right_turn t=2.208s left=1.50 right=-1.50
phase=stop t=3.200s left=0.00 right=0.00
minimal_epuck_motion: complete
```

### Milestone 1B passed automatically

- Controller file exists under the Webots project controller layout.
- Controller compiles under Python 3.11 syntax checks.
- Webots started the world with `controller "minimal_epuck_motion"`.
- The controller executed all four expected phases in Webots and reached `complete`.
- The validation Webots process was stopped afterward; the user's pre-existing GUI Webots process was left running.

### Milestone 1B warnings and issues

- Webots controller stdout/stderr did not appear in shell output or redirected stdout/stderr logs in this environment, so an environment-variable-gated text trace was used for verification.
- A Python `__pycache__` directory was created by local bytecode compilation and is ignored by `.gitignore`; attempts to remove it were blocked by the shell execution policy.
- Git identity is still not configured, so no initial commit was made.

## Milestone 1C: camera frame capture

- Stage: Milestone 1C, e-puck forward camera image capture only.
- Modified controller: `simulator/controllers/minimal_epuck_motion/minimal_epuck_motion.py`.
- Motion sequence retained from Milestone 1B: straight `0.0-1.2 s`, left turn `1.2-2.2 s`, right turn `2.2-3.2 s`, stop after `3.2 s`.
- Completion rule: the controller exits only after the motion sequence has reached stop and at least 100 frames have been saved.
- Camera device: `camera`.
- Camera API confirmed from official Webots R2025a Python sample/API: `getDevice('camera')`, `camera.enable(timeStep)`, `camera.getWidth()`, `camera.getHeight()`, and `camera.saveImage(filename, 100)`.
- Camera actual resolution during Webots run: width `160`, height `120`.
- Camera sampling period: `32 ms`, from `robot.getBasicTimeStep()` and the world `WorldInfo.basicTimeStep`.
- Output directory: `data/frames/m1c`.
- Per-run cleanup: before capture, only old files matching `data/frames/m1c/frame_*.png` are removed. Other data directories are not deleted.
- File naming rule: `frame_<six-digit-index>_t<seven-digit-sim-ms>.png`, for example `frame_000000_t0000032.png`.
- Git/data rule: `data/frames/m1c/*.png` is ignored by `.gitignore` through `data/frames/*`; no frame images were added to Git.
- No CSV, JSON, database, robot pose/state log, trajectory prediction, TTC, risk map, ROI compression, obstacle avoidance, ROS 2, WSL, AI model, or requirements installation was added.

### Milestone 1C Webots run and verification commands

```powershell
.\.venv\Scripts\python.exe -m py_compile .\simulator\controllers\minimal_epuck_motion\minimal_epuck_motion.py
$env:M1C_VALIDATION_TRACE = (Resolve-Path .\results).Path + '\webots_m1c_controller_trace.log'
& "$env:ProgramFiles\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1238 ".\simulator\worlds\minimal_epuck_camera.wbt"
```

The Webots command timed out at the shell tool level because Webots remains open after controller completion; the validation process was stopped after the trace and frame outputs were checked.

### Milestone 1C verification actually run

- Python bytecode compilation passed with exit code 0.
- Webots R2025a actually ran the world and controller.
- Controller trace at `results/webots_m1c_controller_trace.log` recorded the expected sequence:

```text
minimal_epuck_motion: start
sequence: 0.0-1.2s straight, 1.2-2.2s left_turn, 2.2-3.2s right_turn, 3.2s+ stop
camera=camera width=160 height=120 sampling_period_ms=32 output=C:\Users\ROG\Documents\risk-aware-visual-communication\data\frames\m1c
phase=straight t=0.032s left=2.00 right=2.00
phase=left_turn t=1.216s left=-1.50 right=1.50
phase=right_turn t=2.208s left=1.50 right=-1.50
phase=stop t=3.200s left=0.00 right=0.00
frames_saved=116
minimal_epuck_motion: complete
```

- Actual saved frame count: `116`.
- Nonzero file check: `zero_byte_count=0`.
- PNG header/IHDR check using Python standard library:
  - First frame: `frame_000000_t0000032.png`, `160x120`, bit depth 8, PNG color type 6, SHA-256 `f5d3eecf5aeefa70a11f8616655d7ebf469c62c081b1d5e6c7666e59a1a4cb2c`.
  - Middle frame: `frame_000058_t0001888.png`, `160x120`, bit depth 8, PNG color type 6, SHA-256 `a061bbd424d280c09dfbeda4606e74c4c8e1d0a13056110d629ebfe24eeae5b3`.
  - Last frame: `frame_000115_t0003712.png`, `160x120`, bit depth 8, PNG color type 6, SHA-256 `1c1a77dfd40af6559dd1dae2a501bace5e2e1a230ce749069bfc41ec4de09188`.
- All 116 PNG files reported `160x120`.
- Unique file hashes: `116`, confirming the saved images are not repeated identical buffers.
- Output paths checked: no frame path contains `Downloads`.

### Milestone 1C warnings and issues

- Webots `camera.saveImage()` produced PNG files with PNG color type 6 (RGBA). The source device is the official e-puck RGB camera, but the saved PNG container includes an alpha channel.
- Webots controller stdout/stderr still did not reliably propagate to shell output; the environment-variable-gated plain-text trace was used for controller verification.
- Webots GUI Console red-error status could not be visually inspected from the automated run. No Python exception, `camera.saveImage` failure, or command-line controller error was observed in the trace/run output.
- Git identity is still not configured, so no initial commit was made.

## Milestone 1D: per-frame aligned CSV state logging

- Stage: Milestone 1D, synchronized image and ground-truth state CSV only.
- Modified controller: `simulator/controllers/minimal_epuck_motion/minimal_epuck_motion.py`.
- Modified world: `simulator/worlds/minimal_epuck_camera.wbt`; the e-puck now has `supervisor TRUE`.
- Created validator: `scripts/validate_m1d_dataset.py`.
- Ground-truth state source: Webots R2025a Supervisor API in the e-puck controller. The controller uses `Supervisor.getSelf()` and the returned node's `getPosition()`, `getOrientation()`, and `getVelocity()`.
- Episode ID: `episode_0001`.
- Image output directory: `data/frames/m1d/episode_0001`.
- CSV path: `data/logs/m1d/episode_0001.csv`.
- Saved image count: `116`.
- CSV data rows: `116` plus one header row.
- Camera device: `camera`; camera size in CSV: `160x120`; sampling period: `32 ms`.
- CSV fields: `episode_id`, `frame_index`, `sim_time_s`, `sim_time_ms`, `image_path`, `motion_phase`, `robot_x`, `robot_y`, `robot_z`, `yaw_rad`, `linear_velocity_m_s`, `angular_velocity_rad_s`, `left_wheel_command_rad_s`, `right_wheel_command_rad_s`, `camera_width`, `camera_height`.
- Image path format: project-relative paths such as `data/frames/m1d/episode_0001/frame_000000_t0000032.png`; no absolute `C:\Users\ROG\...` paths are written to CSV.
- File naming rule: `frame_<six-digit-index>_t<seven-digit-sim-ms>.png`.
- Strict alignment rule implemented: each controller loop computes the command and state for the current Webots simulation time, calls `camera.saveImage()`, and writes exactly one CSV row only after that image save succeeds.
- No CSV row is written if `camera.saveImage()` fails.
- No trajectory prediction, TTC, risk scoring, risk map, ROI compression, object detection, obstacle avoidance, navigation, ROS 2, WSL, new Python dependency, or requirements installation was added.

### Milestone 1D coordinate and velocity definitions

- Ground plane: Webots world `x-y`.
- Vertical axis: Webots world `z`.
- `robot_x`, `robot_y`, `robot_z`: Webots world coordinates from `Node.getPosition()`.
- `yaw_rad`: heading of the e-puck local `+x` forward axis around world `+z`, computed from the row-major orientation matrix as `atan2(orientation[3], orientation[0])`, normalized to `[-pi, pi]`.
- `linear_velocity_m_s`: actual ground-plane speed magnitude `sqrt(vx^2 + vy^2)` from the first two components of `Node.getVelocity()`.
- `angular_velocity_rad_s`: actual angular velocity around world vertical `+z`, the sixth component of `Node.getVelocity()`.

### Milestone 1D Webots run and validation commands

```powershell
.\.venv\Scripts\python.exe -m py_compile .\simulator\controllers\minimal_epuck_motion\minimal_epuck_motion.py .\scripts\validate_m1d_dataset.py
$env:M1D_VALIDATION_TRACE = (Resolve-Path .\results).Path + '\webots_m1d_controller_trace.log'
& "$env:ProgramFiles\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1239 ".\simulator\worlds\minimal_epuck_camera.wbt"
.\.venv\Scripts\python.exe .\scripts\validate_m1d_dataset.py .\data\logs\m1d\episode_0001.csv
```

The Webots command timed out at the shell tool level because Webots remains open after controller completion; the validation process was stopped after the trace and dataset outputs were checked.

### Milestone 1D verification actually run

- Python bytecode compilation passed for the controller and validation script.
- Webots R2025a actually ran the world and controller.
- Controller trace at `results/webots_m1d_controller_trace.log` recorded:

```text
minimal_epuck_motion: start
sequence: 0.0-1.2s straight, 1.2-2.2s left_turn, 2.2-3.2s right_turn, 3.2s+ stop
camera=camera width=160 height=120 sampling_period_ms=32 output=C:\Users\ROG\Documents\risk-aware-visual-communication\data\frames\m1d\episode_0001
episode_id=episode_0001 csv=C:\Users\ROG\Documents\risk-aware-visual-communication\data\logs\m1d\episode_0001.csv ground_plane=x_y vertical_axis=z yaw=atan2(orientation[3],orientation[0])
phase=straight t=0.032s left=2.00 right=2.00
phase=left_turn t=1.216s left=-1.50 right=1.50
phase=right_turn t=2.208s left=1.50 right=-1.50
phase=stop t=3.200s left=0.00 right=0.00
frames_saved=116
csv_rows=116
minimal_epuck_motion: complete
```

- Validation script result:

```text
OK: CSV rows: 116
OK: episode_id: episode_0001
OK: frame_index continuous from 0
OK: sim_time_s strictly increasing
OK: image count matches CSV row count: 116
OK: all motion phases present
OK: straight phase displacement: 0.046080 m
OK: left_turn yaw delta: 1.015107 rad
OK: right_turn yaw delta: -1.014645 rad
OK: turn angular velocity signs oppose: left=1.023395, right=-0.988913
OK: stop tail near zero: linear<=0.000170, angular<=0.002190
OK: validation passed
```

- Additional checks:
  - CSV rows: `116`; frame files: `116`.
  - CSV lines: `117`, including header.
  - Absolute image paths in CSV: `0`.
  - `Downloads` references in image paths: `0`.
  - Missing images: `0`.
  - Zero-byte images: `0`.
  - Phase row counts: straight `37`, left_turn `31`, right_turn `31`, stop `17`.
  - `data/frames/m1d/...`, `data/logs/m1d/...`, and `results/webots_m1d_controller_trace.log` are ignored by `.gitignore`.

### Milestone 1D warnings and issues

- Webots controller stdout/stderr still did not reliably propagate to shell output; the environment-variable-gated plain-text trace was used for controller completion evidence.
- Webots GUI Console red-error status could not be visually inspected from the automated run. No Python exception, image save failure, CSV write failure, or validation failure occurred.
- Git identity is still not configured, so no local commit was made.
- Generated data under `data/frames/m1d/` and `data/logs/m1d/` is intentionally ignored by Git.

## Milestone 2: trajectory prediction and empirical corridor

- Stage: Milestone 2 complete on local branch `feature/m2-trajectory-models`.
- Baseline before branch: `ddf5b92 feat: establish aligned Webots data pipeline`.
- New core modules:
  - `navigation/trajectory_prediction.py`
  - `navigation/trajectory_uncertainty.py`
- New Webots validation assets:
  - `simulator/worlds/m2_trajectory_validation.wbt`
  - `simulator/controllers/m2_trajectory_validation/m2_trajectory_validation.py`
- New scripts:
  - `scripts/evaluate_m2_trajectory.py`
- New tests:
  - `tests/test_trajectory_prediction.py`
  - `tests/test_trajectory_uncertainty.py`
- New docs:
  - `docs/trajectory_prediction_design.md`
  - `docs/system_overview.md`

### Milestone 2 definitions

- Planned command trajectory: the controller/planner's future command schedule.
- State-only predicted trajectory: constant-twist extrapolation from current actual state only.
- Command-conditioned nominal trajectory: differential-drive integration from current actual state plus explicit future command segments.
- Actual future trajectory: Webots ground truth used only for offline evaluation, never as online prediction input.

### Official e-puck geometry used

- Source: installed Webots R2025a official e-puck controller, `C:\Program Files\Webots\projects\robots\gctronic\e-puck\controllers\e-puck\e-puck.c`.
- Wheel radius: `0.02 m` from `#define WHEEL_RADIUS 0.02`.
- Axle length: `0.052 m` from `#define AXLE_LENGTH 0.052`.
- Conversion:
  - `v = r/2 * (omega_right + omega_left)`
  - `angular_velocity = r/L * (omega_right - omega_left)`

### Milestone 2 validation episode

- Episode CSV: `data/logs/m2/trajectory_validation_episode_0001.csv`.
- Episode role: in-place rotation validation.
- Row count: `500` data rows plus header.
- World: 4 m x 4 m `RectangleArena` with e-puck only; no obstacles.
- Controller sequence:
  - `0-4 s`: straight, left/right `2.00 rad/s`
  - `4-8 s`: left turn, left `-1.50 rad/s`, right `1.50 rad/s`
  - `8-12 s`: right turn, left `1.50 rad/s`, right `-1.50 rad/s`
  - `12-16 s`: stop, both `0.00 rad/s`
- Webots trace: `results/webots_m2_validation_trace.log`, ignored by Git.

### Milestone 2 actual commands run

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_trajectory_prediction tests.test_trajectory_uncertainty
$env:M2_VALIDATION_TRACE = (Resolve-Path .\results).Path + '\webots_m2_validation_trace.log'
& "$env:ProgramFiles\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1240 ".\simulator\worlds\m2_trajectory_validation.wbt"
.\.venv\Scripts\python.exe .\scripts\evaluate_m2_trajectory.py .\data\logs\m2\trajectory_validation_episode_0001.csv
```

The Webots command timed out at the shell tool level because Webots remains open after controller completion. The validation process was stopped after the trace and CSV were checked.

### Milestone 2 test and evaluation results

- Unit tests: `25` tests passed.
- Python compile checks passed for trajectory modules, tests, M2 controller, and evaluation script.
- Matplotlib was missing and installed only into the project `.venv` with:

```powershell
.\.venv\Scripts\python.exe -m pip install "matplotlib>=3.8,<4"
```

- Installed matplotlib version: `3.11.0`. Pip also installed matplotlib runtime dependencies in `.venv`, including `numpy 2.4.6` and `pillow 12.3.0`.

### Milestone 2 summary metrics

Stable and transition windows were reported separately.

| Method | Horizon | Category | Windows | ADE mean (m) | FDE mean (m) | yaw MAE mean (rad) |
|---|---:|---|---:|---:|---:|---:|
| State-only | 0.5 | all_stable | 439 | 0.000120561 | 0.000221264 | 0.002978459 |
| State-only | 0.5 | all_transition | 45 | 0.001220771 | 0.003285312 | 0.126981111 |
| State-only | 1.0 | all_stable | 375 | 0.000266159 | 0.000499997 | 0.006807695 |
| State-only | 1.0 | all_transition | 93 | 0.002367312 | 0.006551143 | 0.247685009 |
| State-only | 2.0 | all_stable | 251 | 0.000715992 | 0.001359725 | 0.017649484 |
| State-only | 2.0 | all_transition | 186 | 0.004612635 | 0.013322370 | 0.472876701 |
| Command-conditioned | 0.5 | all_stable | 439 | 0.000006398 | 0.000009305 | 0.013294641 |
| Command-conditioned | 0.5 | all_transition | 45 | 0.000008479 | 0.000015076 | 0.014727521 |
| Command-conditioned | 1.0 | all_stable | 375 | 0.000009568 | 0.000015435 | 0.025871473 |
| Command-conditioned | 1.0 | all_transition | 93 | 0.000012501 | 0.000019017 | 0.028601180 |
| Command-conditioned | 2.0 | all_stable | 251 | 0.000013655 | 0.000023841 | 0.050328531 |
| Command-conditioned | 2.0 | all_transition | 186 | 0.000021410 | 0.000034267 | 0.055576200 |

Observed result: Command-conditioned prediction was much better on ADE/FDE for both stable and transition windows. State-only was reasonable in stable windows but degraded strongly near command transitions, especially at 1 s and 2 s horizons. For yaw MAE in stable windows, State-only was lower than Command-conditioned in this validation run, but Command-conditioned remained far better in transition yaw error.

### Milestone 2 empirical corridor

The first corridor uses `robot_half_width + 90% position-error quantile + 0.01 m safety_margin`. Robot half-width is `0.026 m`.

| Method | Horizon | Samples | p50 (m) | p90 (m) | p95 (m) | corridor radius (m) |
|---|---:|---:|---:|---:|---:|---:|
| State-only | 0.5 | 7744 | 0.000019340 | 0.000080234 | 0.000288875 | 0.036080234 |
| State-only | 1.0 | 14976 | 0.000038498 | 0.000168068 | 0.001897709 | 0.036168068 |
| State-only | 2.0 | 27531 | 0.000083230 | 0.001592257 | 0.016633342 | 0.037592257 |
| Command-conditioned | 0.5 | 7744 | 0.000001409 | 0.000020462 | 0.000028943 | 0.036020462 |
| Command-conditioned | 1.0 | 14976 | 0.000003261 | 0.000032317 | 0.000043861 | 0.036032317 |
| Command-conditioned | 2.0 | 27531 | 0.000009357 | 0.000048970 | 0.000055403 | 0.036048970 |

This is an empirical residual corridor from limited simulation data, not a calibrated confidence interval. It does not model sudden slip.

### Milestone 2 generated figures

- `results/m2_trajectory/state_only_straight_1s.png`
- `results/m2_trajectory/command_conditioned_transition_2s.png`
- `results/m2_trajectory/method_comparison_ade.png`
- `results/m2_trajectory/uncertainty_corridor_example.png`

### Milestone 2 warnings and issues

- Webots GUI Console red-error status was not visually inspected in the automated run. No Python exception or CSV write failure appeared in the trace/output.
- Generated CSV/results/figures are ignored by Git.
- This validation episode has no obstacles and no slip-specific perturbation, so uncertainty estimates are narrow and scenario-limited.
- Git identity is still not configured, so no local commit was made despite validation passing.

## Milestone 2R: forward arc validation and transition guard

- Stage: Milestone 2R complete on local branch `feature/m2-trajectory-models`.
- Starting commit: `9663cc3 feat: add trajectory models and uncertainty corridor`.
- Original Milestone 2 assets were preserved:
  - `data/logs/m2/trajectory_validation_episode_0001.csv` remains the in-place rotation validation episode.
  - Existing figures under `results/m2_trajectory/` were not regenerated during 2R.
- New Webots validation assets:
  - `simulator/worlds/m2_arc_trajectory_validation.wbt`
  - `simulator/controllers/m2_arc_trajectory_validation/m2_arc_trajectory_validation.py`
- New generated episode:
  - `data/logs/m2/trajectory_validation_episode_0002.csv`
  - Episode role: forward arc validation.
  - Row count: `500` data rows plus header.
  - World: 4 m x 4 m `RectangleArena` with e-puck only; no obstacles.
- Episode sequence:
  - `0-4 s`: straight, left/right `2.00 rad/s`
  - `4-8 s`: forward-left arc, left `1.00 rad/s`, right `2.00 rad/s`
  - `8-12 s`: forward-right arc, left `2.00 rad/s`, right `1.00 rad/s`
  - `12-16 s`: stop, both `0.00 rad/s`
- Transition guard:
  - Central constants in `scripts/evaluate_m2_trajectory.py`: `TRANSITION_GUARD_START_S = 0.10`, `TRANSITION_GUARD_END_S = 0.20`.
  - Every prediction window intersecting `[command_switch + 0.10 s, command_switch + 0.20 s]` is labeled transition.
  - Stable windows start only after `command_switch + 0.20 s`, excluding actuator switching transients.
- Actual Webots arc validation:
  - Straight: mean actual linear velocity `0.039683774 m/s`, mean omega `-0.000000048 rad/s`, `dx=0.157439958 m`, `dy=0.000000013 m`.
  - Forward-left arc: mean actual linear velocity `0.030087395 m/s`, mean omega `0.348303969 rad/s`, `dx=0.084162558 m`, `dy=0.070315344 m`.
  - Forward-right arc: mean actual linear velocity `0.030009900 m/s`, mean omega `-0.345576797 rad/s`, `dx=0.083280314 m`, `dy=0.071326220 m`.
  - Stop: mean actual linear velocity `0.000585555 m/s`, mean omega `-0.002700135 rad/s`.
  - Full run bounds: `x=0.000000..0.327288 m`, `y=-0.000001..0.142593 m`, safely within the 4 m x 4 m arena.
- Arc evaluation output directory: `results/m2_trajectory_arc/`.
- New generated arc figures:
  - `results/m2_trajectory_arc/forward_left_arc_1s.png`
  - `results/m2_trajectory_arc/forward_right_arc_1s.png`
  - `results/m2_trajectory_arc/arc_transition_2s.png`
  - `results/m2_trajectory_arc/arc_uncertainty_corridor.png`
  - `results/m2_trajectory_arc/method_comparison_log_scale.png`

### Milestone 2R aggregate metrics

| Method | Horizon | Category | Windows | ADE mean (m) | FDE mean (m) | yaw MAE mean (rad) |
|---|---:|---|---:|---:|---:|---:|
| State-only | 0.5 | all_stable | 412 | 0.000034571 | 0.000063502 | 0.000009111 |
| State-only | 0.5 | all_transition | 57 | 0.001357671 | 0.003357978 | 0.039602718 |
| State-only | 1.0 | all_stable | 348 | 0.000071489 | 0.000135392 | 0.000027119 |
| State-only | 1.0 | all_transition | 105 | 0.002768084 | 0.007596697 | 0.079800137 |
| State-only | 2.0 | all_stable | 224 | 0.000166138 | 0.000324253 | 0.000092061 |
| State-only | 2.0 | all_transition | 198 | 0.006054908 | 0.018486356 | 0.157453182 |
| Command-conditioned | 0.5 | all_stable | 412 | 0.000026305 | 0.000066676 | 0.004550552 |
| Command-conditioned | 0.5 | all_transition | 57 | 0.000033524 | 0.000071485 | 0.005181834 |
| Command-conditioned | 1.0 | all_stable | 348 | 0.000096211 | 0.000259123 | 0.008848160 |
| Command-conditioned | 1.0 | all_transition | 105 | 0.000099031 | 0.000235729 | 0.009951645 |
| Command-conditioned | 2.0 | all_stable | 224 | 0.000354789 | 0.001009160 | 0.017183483 |
| Command-conditioned | 2.0 | all_transition | 198 | 0.000350929 | 0.000888623 | 0.019225080 |

### Milestone 2R verification actually run

```powershell
.\.venv\Scripts\python.exe -m py_compile .\navigation\trajectory_prediction.py .\navigation\trajectory_uncertainty.py .\scripts\evaluate_m2_trajectory.py .\simulator\controllers\m2_arc_trajectory_validation\m2_arc_trajectory_validation.py .\simulator\controllers\m2_trajectory_validation\m2_trajectory_validation.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
$env:M2_ARC_VALIDATION_TRACE = (Resolve-Path .\results).Path + '\webots_m2r_arc_trace_<timestamp>.log'
& "$env:ProgramFiles\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1242 ".\simulator\worlds\m2_arc_trajectory_validation.wbt"
.\.venv\Scripts\python.exe .\scripts\evaluate_m2_trajectory.py .\data\logs\m2\trajectory_validation_episode_0002.csv --profile arc
```

- `py_compile`: passed.
- Unit tests: `30` tests passed.
- Webots R2025a ran the arc world and controller; trace recorded `m2_arc_trajectory_validation: complete` and `csv_rows=500`.
- The Webots command timed out at the shell tool level because Webots remains open after controller completion. The new validation Webots process was stopped after trace/CSV checks; the user's pre-existing GUI Webots process was left running.
- Data validation confirmed episode ID `episode_0002`, 500 rows, no `Downloads` path, positive arc linear velocities, opposite arc angular-velocity signs, changing `robot_x` and `robot_y`, and arena bounds safely within 4 m x 4 m.
- New arc uncertainty corridor figure uses a union of disks along the predicted command-conditioned trajectory, not one circle around the start.

### Milestone 2R warnings and issues

- Webots GUI Console red-error status was not visually inspected for the automated arc run. No Python exception, CSV write failure, or evaluation failure appeared in the trace/output.
- Generated CSV/results/figures remain ignored by Git.
- The arc validation still has no obstacles, TTC, risk map, compression, perception, closed-loop navigation, ROS 2, WSL, or machine learning.

### Milestone 2R cleanup fix

- Date: 2026-07-18 (Asia/Shanghai).
- User GUI review found a real controller exit error in `simulator/controllers/m2_arc_trajectory_validation/m2_arc_trajectory_validation.py`: `AttributeError: 'Supervisor' object has no attribute 'cleanup'`.
- The failing run had already written `csv_rows=500` and `m2_arc_trajectory_validation: complete`, but Webots reported `controller exited with status: 1`.
- `data/logs/m2/trajectory_validation_episode_0003.csv` is retained as an ignored debugging artifact and is not used as final success evidence.
- Checked local Webots R2025a Python API files under `C:\Program Files\Webots\lib\controller\python\controller`:
  - `supervisor.py` defines `class Supervisor(Robot)` and no public `cleanup()` method.
  - `robot.py` calls `wb_robot_cleanup()` internally from `Robot.__del__`; it does not expose a `robot.cleanup()` instance method.
- Fix applied:
  - Removed the invalid `robot.cleanup()` call from the arc validation controller.
  - Converted the optional trace file and CSV episode log to context managers so files are flushed and closed through `with Trace() as trace, EpisodeLog(...) as log`.
  - Normal completion now returns from `main()` after the loop, and `robot.step()` returning `-1` exits the loop while the context managers still close files.
- Verification after fix:
  - `py_compile` passed for the arc controller and related evaluation modules.
  - Unit tests: `30` tests passed.
  - Webots R2025a ran `simulator/worlds/m2_arc_trajectory_validation.wbt` and generated `data/logs/m2/trajectory_validation_episode_0004.csv`.
  - `episode_0004` row count: `500`.
  - Trace `results/webots_m2r_cleanup_fix_trace_20260718_001807.log` contains the full phase sequence, `csv_rows=500`, and `m2_arc_trajectory_validation: complete`.
  - Redirected Webots stdout/stderr for the fix run contained no `Traceback`, `AttributeError`, or `status: 1` text.
  - `episode_0004` passed the existing arc evaluation script with unchanged metrics from episode_0002.
- Note: the automated Webots process remains open after controller completion and was stopped after trace/CSV checks. The redirected command-line logs did not expose a literal GUI Console line saying `controller exited with status: 0`; the controller returned normally without Python exception after the invalid cleanup call was removed.

### Milestone 2R formal acceptance and branch handoff

- Date: 2026-07-18 (Asia/Shanghai).
- Milestone 2R and the cleanup fix are formally accepted based on:
  - no `Traceback`, `AttributeError`, or `status: 1` after removing the invalid cleanup call;
  - complete trace with all four arc phases and `m2_arc_trajectory_validation: complete`;
  - successful 500-row CSV generation for the post-fix validation episode;
  - successful arc evaluation script output with unchanged metrics;
  - 30 unit tests passing.
- A literal GUI Console line saying `controller exited with status: 0` is not required as an acceptance item for this milestone because the concrete failure mode was the Python `AttributeError` and status 1, and the post-fix evidence shows normal controller return without traceback/status 1.
- Repository cleanup before merge:
  - `simulator/worlds/minimal_epuck_camera.wbt` had only Webots GUI/default-field changes: Viewpoint changed, `basicTimeStep 32`, robot `translation 0 0 0`, `rotation 0 0 1 0`, and `name "e-puck"` were omitted as defaults.
  - The minimal world robot model, obstacle, controller, camera settings, and experiment scene were not meaningfully changed.
  - `simulator/worlds/.minimal_epuck_camera.jpg` was a Webots-generated tracked thumbnail updated by opening/saving the world.
  - Both unrelated files were restored to HEAD; no extra commit was created for them.
- Merge result:
  - `main` was fast-forward merged from `feature/m2-trajectory-models`.
  - `main` now contains `5536897 fix: remove invalid Webots supervisor cleanup`, `a282935 fix: validate forward arc trajectories`, `9663cc3 feat: add trajectory models and uncertainty corridor`, and `ddf5b92 feat: establish aligned Webots data pipeline`.
  - `feature/m2-trajectory-models` was retained.
  - New branch `feature/m3-world-risk` was created from the updated `main`.
- No Milestone 3 risk model, obstacle risk, TTC, image risk map, compression, or navigation code was added during this handoff.

## Milestone 3A: world-risk formulation and interface freeze

- Stage: Milestone 3A complete on local branch `feature/m3-world-risk`.
- Starting commit: `d4d9b24 docs: close trajectory validation milestone`.
- New design document:
  - `docs/risk_formulation_design.md`
- Updated documents:
  - `docs/progress.md`
  - `docs/roadmap.md`
  - `docs/decisions.md`
  - `docs/research_protocol.md`
  - `docs/system_overview.md`
- Scope completed:
  - Defined planned trajectory as the Command-conditioned trajectory.
  - Defined state trajectory as the State-only trajectory.
  - Reaffirmed that actual future trajectory is offline evaluation ground truth only.
  - Defined the Trajectory Occupancy Corridor as robot half width plus empirical prediction residual plus safety margin.
  - Defined static AABB `ObstacleFootprint` fields and validation rules.
  - Defined `minimum_centerline_distance_m`, `minimum_clearance_m`, `closest_time_s`, `first_corridor_entry_time_s`, and `corridor_overlap_duration_s`.
  - Replaced broad TTC wording with `Time-to-Conflict (TTCf)` for first corridor entry time.
  - Froze first-version interpretable risk scores:
    - `spatial_score = exp(-max(clearance_m, 0) / sigma_distance_m)`
    - `temporal_score = exp(-relevant_time_s / tau_time_s)`
    - `risk_score = spatial_score * temporal_score`
  - Froze planned/state independent outputs and first combined rule `combined_risk = max(planned_risk, state_risk)`.
  - Defined future module responsibilities for `risk_map/models.py`, `risk_map/geometry.py`, `risk_map/trajectory_obstacle_risk.py`, and `risk_map/risk_formulation.py`.
  - Defined M3 validation scenario roles: `EARLY_CONFLICT`, `LATE_CONFLICT`, `ON_PLANNED_PATH`, `ON_STATE_PATH`, `NEAR_BOUNDARY`, and `OUTSIDE_BOTH`.
  - Wrote acceptance criteria and a 20-item unit test plan for Milestone 3B.
- Explicitly not created in Milestone 3A:
  - no `risk_map` Python package or algorithm files;
  - no M3 Webots world or controller;
  - no CSV data;
  - no figures;
  - no actual risk result computation;
  - no camera projection;
  - no ROI compression;
  - no machine learning.
- Current limitations frozen for the first world-risk version:
  - static obstacles only;
  - axis-aligned rectangular obstacle footprints only;
  - world-coordinate ground truth only;
  - no dynamic target prediction;
  - no camera projection;
  - no real collision dynamics;
  - no slip-specific model;
  - risk is not a probability;
  - no machine learning.

## Milestone 3B: world-risk geometry core implementation

- Stage: Milestone 3B complete on local branch `feature/m3-world-risk`.
- Starting design commit: `676f7ba docs: freeze world risk formulation`.
- Implemented ordinary-Python package:
  - `risk_map/models.py`
  - `risk_map/geometry.py`
  - `risk_map/risk_formulation.py`
  - `risk_map/trajectory_obstacle_risk.py`
  - `risk_map/__init__.py`
- Added focused unit tests:
  - `tests/test_risk_models.py`
  - `tests/test_risk_geometry.py`
  - `tests/test_risk_formulation.py`
  - `tests/test_trajectory_obstacle_risk.py`
- Implemented interfaces:
  - `TrajectorySource` constrained to `planned` and `state`;
  - `ObstacleFootprint` with derived `min_x`, `max_x`, `min_y`, and `max_y`;
  - `RiskParameters`;
  - `TrajectoryConflictResult`;
  - `DualTrajectoryRiskResult`.
- Implemented geometry:
  - point-to-segment distance with zero-length segment handling;
  - point-to-AABB distance;
  - segment-to-AABB distance using obstacle boundaries, not obstacle centers;
  - segment/AABB corridor interval calculation with inflated AABB;
  - polyline closest distance and interpolated closest time;
  - first corridor entry time and total overlap duration over merged time intervals;
  - tangent and near-boundary handling through `geometry_tolerance_m`.
- Implemented risk formulation:
  - `spatial_score = exp(-max(clearance_m, 0) / sigma_distance_m)`;
  - `temporal_score = exp(-relevant_time_s / tau_time_s)`;
  - `risk_score = spatial_score * temporal_score`;
  - `combined_risk = max(planned_risk, state_risk)`.
- Implemented trajectory-obstacle APIs:
  - `analyze_trajectory_obstacle(...)`;
  - `analyze_dual_trajectory_obstacle(...)`;
  - `compute_trajectory_disagreement(...)` with time interpolation instead of index-only matching.
- Validation performed:
  - `.\.venv\Scripts\python.exe -m py_compile risk_map\__init__.py risk_map\models.py risk_map\geometry.py risk_map\trajectory_obstacle_risk.py risk_map\risk_formulation.py`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `Select-String -Path risk_map\*.py -Pattern "webots|controller|numpy|scipy|shapely|cv2|sklearn|torch|tensorflow|PIL" -CaseSensitive:$false`
- Test result: 62 tests passed, including the previous 30 baseline tests and 32 new Milestone 3B tests.
- Dependency audit result: no prohibited Webots, camera, NumPy, SciPy, Shapely, OpenCV, ROS, or ML imports were found in `risk_map`.
- Explicitly not created in Milestone 3B:
  - no M3 Webots world;
  - no M3 Webots controller;
  - no CSV data;
  - no result figures;
  - no image-space risk map;
  - no ROI compression;
  - no navigation or obstacle-avoidance code.
- Current limitations remain:
  - static AABB obstacles only;
  - world-coordinate geometry only;
  - risk score is an interpretable heuristic proxy, not a probability;
  - no camera projection or pixel-space risk allocation.

## Milestone 3C: Webots world-risk validation

- Stage: Milestone 3C complete on local branch `feature/m3-world-risk`.
- Starting core implementation commit: `ced0dc7 feat: implement world risk geometry core`.
- Created Webots validation world:
  - `simulator/worlds/m3_world_risk_validation.wbt`
- Created controller:
  - `simulator/controllers/m3_world_risk_validation/m3_world_risk_validation.py`
- Created Webots obstacle adapter:
  - `simulator/adapters/webots_obstacle_adapter.py`
  - `simulator/adapters/__init__.py`
- Created shared M3C config:
  - `simulator/m3c_config.py`
- Created validation/calibration scripts:
  - `scripts/validate_m3c_risk_dataset.py`
  - `scripts/calibrate_m3c_obstacle_layout.py`
- Created tests:
  - `tests/test_webots_obstacle_adapter_helpers.py`
- Risk core consistency fix:
  - `risk_map/trajectory_obstacle_risk.py` now derives `enters_corridor` from `minimum_clearance_m <= geometry_tolerance_m`.
  - This fixes a real inconsistency where square inflated-AABB interval estimation could mark entry while Euclidean clearance was positive. Risk formulas were not changed.
- Analysis snapshot:
  - `analysis_time_s = 7.968`, exactly aligned to the 32 ms Webots basic time step.
  - The snapshot is one step before the 8.000 s command switch, so State-only continues the measured forward-left arc while Command-conditioned knows the upcoming right-arc command.
  - Prediction horizon: `2.0 s`.
  - Prediction step: `0.032 s`.
- Webots episode used as final evidence:
  - `data/logs/m3/risk_validation_episode_0002.csv`
  - `data/logs/m3/risk_validation_episode_0002_trace.txt`
  - CSV data rows: `6`.
  - Episode `0001` is retained as an ignored calibration/debug artifact and is not used as final success evidence because the first nominal obstacle layout did not satisfy all role relationships under the actual Webots analysis state.
- Actual analysis state from Webots episode `0002`:
  - `current_robot_x = 0.242882516`
  - `current_robot_y = 0.070315357`
  - `current_robot_yaw_rad = 1.393201041`
  - `current_linear_velocity_m_s = 0.029944488`
  - `current_angular_velocity_rad_s = 0.350989561`
  - `trajectory_disagreement_m = 0.040803441`
- Risk parameters:
  - `corridor_radius_m = 0.037592257`
  - `sigma_distance_m = 0.05`
  - `tau_time_s = 1.0`
  - `maximum_horizon_s = 2.0`
  - `geometry_tolerance_m = 0.000001`
- Fixed Webots Box obstacles, all size `0.025 m x 0.025 m x 0.05 m`, no planar rotation:

| obstacle_id | DEF | center_x | center_y |
|---|---|---:|---:|
| EARLY_CONFLICT | M3_EARLY_CONFLICT | 0.297106 | 0.065676 |
| LATE_CONFLICT | M3_LATE_CONFLICT | 0.241455 | 0.162030 |
| ON_PLANNED_PATH | M3_ON_PLANNED_PATH | 0.298331 | 0.106364 |
| ON_STATE_PATH | M3_ON_STATE_PATH | 0.203578 | 0.123618 |
| NEAR_BOUNDARY | M3_NEAR_BOUNDARY | 0.187397 | 0.095750 |
| OUTSIDE_BOTH | M3_OUTSIDE_BOTH | 0.330000 | 0.185000 |

- Episode `0002` obstacle risk summary:

| obstacle_id | planned clearance | planned TTCf | planned risk | state clearance | state TTCf | state risk | combined risk |
|---|---:|---:|---:|---:|---:|---:|---:|
| EARLY_CONFLICT | -0.000109235 | 0.540991177 | 0.582170932 | 0.002997031 | none | 0.666415720 | 0.666415720 |
| LATE_CONFLICT | -0.003019928 | 1.567852200 | 0.208492502 | -0.016164765 | 1.407580468 | 0.244734711 | 0.244734711 |
| ON_PLANNED_PATH | -0.024513607 | 0.650445002 | 0.521813517 | 0.004297946 | none | 0.455725349 | 0.521813517 |
| ON_STATE_PATH | 0.000910321 | none | 0.430045704 | -0.020909343 | 0.108539760 | 0.897143223 | 0.897143223 |
| NEAR_BOUNDARY | 0.007032912 | none | 0.764404461 | 0.000788975 | none | 0.138486732 | 0.764404461 |
| OUTSIDE_BOTH | 0.030868868 | none | 0.072994049 | 0.058035029 | none | 0.045094095 | 0.072994049 |

- Automatic role checks passed:
  - EARLY_CONFLICT and LATE_CONFLICT enter planned corridor.
  - EARLY_CONFLICT planned TTCf is earlier than LATE_CONFLICT.
  - EARLY_CONFLICT planned risk is greater than LATE_CONFLICT.
  - ON_PLANNED_PATH has planned risk greater than state risk and smaller planned clearance.
  - ON_STATE_PATH has state risk greater than planned risk and smaller state clearance.
  - OUTSIDE_BOTH enters neither corridor and has clearly positive planned/state clearance.
  - NEAR_BOUNDARY has a small positive state clearance within `0 < clearance <= 0.01 m`.
  - All rows share the same positive trajectory disagreement.
- Webots-to-`ObstacleFootprint` mapping:
  - `Supervisor.getFromDef(def_name)`;
  - `Solid.translation` maps to `center_x`, `center_y`;
  - `Shape.geometry Box.size` maps to `size_x`, `size_y`;
  - `Solid.rotation` must have no planar rotation;
  - appearance/color is ignored.
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m py_compile ...`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - Webots R2025a batch/fast run of `simulator/worlds/m3_world_risk_validation.wbt`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv`
  - `Select-String -Path risk_map\*.py -Pattern "webots|controller|numpy|scipy|shapely|cv2|sklearn|torch|tensorflow|PIL" -CaseSensitive:$false`
- Validation results:
  - `py_compile`: passed.
  - Unit tests: `65` tests passed.
  - Webots trace: `csv_rows=6` and `m3_world_risk_validation: complete`.
  - M3C CSV validator: exit code 0.
  - Redirected Webots stdout/stderr for the final run contained no text.
  - `risk_map` dependency audit still found no prohibited imports.
  - Generated `data/logs/m3` and `results/webots_m3c_*` files are ignored by Git.
- Data-leakage audit:
  - State-only prediction uses only current Webots state at analysis time.
  - Command-conditioned prediction uses the same current state plus explicit future command schedule.
  - Future actual position, yaw, velocity, or future CSV rows are not read by the controller.
- GUI/manual validation:
  - passed by user review during final Milestone 3 acceptance.
  - Scene Tree contained all six expected DEF nodes: `M3_EARLY_CONFLICT`, `M3_LATE_CONFLICT`, `M3_ON_PLANNED_PATH`, `M3_ON_STATE_PATH`, `M3_NEAR_BOUNDARY`, and `M3_OUTSIDE_BOTH`.
  - Six obstacles were visible, with no observed obstacle-to-obstacle overlap.
  - The robot did not visibly overlap obstacles, flip, or get stuck.
  - GUI run reported `analysis_time_s=7.968`, `planned_points=63`, `state_points=63`, `trajectory_disagreement=0.040803441`, `csv_rows=6`, `m3_world_risk_validation: complete`, and successful controller exit.
  - Console showed no `Traceback`, `AttributeError`, or `status:1`.
  - Non-blocking environment warning: ports `1234` and `1235` were already in use, and Webots automatically used `1236`; this did not affect controller completion and is not treated as an experiment failure.
  - GUI reproduction run generated `episode_0005`; it is retained only as GUI reproduction evidence. Formal M3D report values, figures, and automatic validation remain based on `episode_0002`.
- Explicitly not implemented in Milestone 3C:
  - no camera projection;
  - no image-space risk map or heatmap;
  - no ROI compression;
  - no JPEG/H.264/H.265 encoding;
  - no target detection;
  - no closed-loop obstacle avoidance;
  - no dynamic obstacles;
  - no ROS 2;
  - no machine learning;
  - no formal Milestone 3D figures.

## Milestone 3D: world-risk diagnostics and validation report

- Stage: Milestone 3D automated diagnostics complete on local branch `feature/m3-world-risk`.
- Input episode:
  - `data/logs/m3/risk_validation_episode_0002.csv`
  - `data/logs/m3/risk_validation_episode_0002_trace.txt`
- Explicitly not used:
  - `data/logs/m3/risk_validation_episode_0001.csv`, retained only as ignored calibration/debug output.
- Created scripts:
  - `scripts/m3d_world_risk_common.py`
  - `scripts/evaluate_m3d_world_risk.py`
  - `scripts/plot_m3d_world_risk.py`
  - `scripts/validate_m3d_report.py`
- Created tests:
  - `tests/test_m3d_evaluation_helpers.py`
- Created report:
  - `docs/m3_world_risk_validation_report.md`
- Generated ignored data/results:
  - `data/logs/m3/risk_validation_episode_0002_trajectories.csv`
  - `results/m3_world_risk/m3d_risk_summary.csv`
  - `results/m3_world_risk/m3d_risk_summary.json`
  - `results/m3_world_risk/parameter_sensitivity.csv`
  - `results/m3_world_risk/world_risk_overview.png`
  - `results/m3_world_risk/planned_vs_state_risk.png`
  - `results/m3_world_risk/risk_decomposition_planned.png`
  - `results/m3_world_risk/risk_decomposition_state.png`
  - `results/m3_world_risk/early_vs_late_ttcf.png`
  - `results/m3_world_risk/early_vs_late_risk_decomposition.png`
  - `results/m3_world_risk/clearance_risk_curve.png`
  - `results/m3_world_risk/trajectory_disagreement_over_time.png`
  - `results/m3_world_risk/parameter_sensitivity.png`
  - `results/m3_world_risk/parameter_sensitivity_margins.png`
- Rebuilt trajectories:
  - planned points: `63`
  - state points: `63`
  - maximum planned/state disagreement: `0.040803441 m`
- Formula checks:
  - spatial, temporal, risk, combined max, clearance, entry-time None semantics, and shared disagreement all recalculated successfully from episode_0002.
- Role acceptance:
  - `M3_ROLE_ACCEPTANCE=PASS`
  - EARLY planned risk is greater than LATE planned risk.
  - ON_PLANNED_PATH is planned-dominant.
  - ON_STATE_PATH is state-dominant.
  - NEAR_BOUNDARY remains outside with small positive clearance.
  - OUTSIDE_BOTH remains outside both corridors.
- Parameter sensitivity:
  - Tested `sigma_distance_m` in `{0.025, 0.05, 0.10}` and `tau_time_s` in `{0.5, 1.0, 2.0}`.
  - All 9 combinations preserve the key ordering checks.
  - This is a limited local sensitivity check over only the tested 9 parameter combinations, not a complete robustness proof.
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m py_compile scripts\m3d_world_risk_common.py scripts\evaluate_m3d_world_risk.py scripts\plot_m3d_world_risk.py scripts\validate_m3d_report.py tests\test_m3d_evaluation_helpers.py`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv`
  - `.\.venv\Scripts\python.exe .\scripts\evaluate_m3d_world_risk.py`
  - `.\.venv\Scripts\python.exe .\scripts\plot_m3d_world_risk.py`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3d_report.py`
- Validation results:
  - `py_compile`: passed.
  - Unit tests: `74` tests passed.
  - M3C validator on episode_0002: exit code 0.
  - M3D evaluation: exit code 0.
  - M3D plot generation: exit code 0.
  - M3D report validator: exit code 0.
- Data-leakage audit:
  - M3D rebuilds trajectories only from current episode_0002 snapshot state and known command schedule.
  - No future actual pose, yaw, velocity, or later Webots state is read.
- GUI validation:
  - passed by user review.
- Explicitly not implemented in Milestone 3D:
  - no camera projection;
  - no image-space risk map or heatmap;
  - no ROI compression;
  - no image/video codec;
  - no target detection;
  - no closed-loop navigation;
  - no dynamic obstacles;
  - no ROS 2;
  - no machine learning.

## Milestone 3D-R: diagnostic figure expression and readability

- Stage: Milestone 3D-R completed on local branch `feature/m3-world-risk`.
- Scope:
  - corrected scientific expression and readability of existing world-coordinate risk diagnostics only;
  - did not change risk algorithms, obstacle coordinates, formal parameters, or accepted CSV data;
  - did not add camera projection, image risk maps, ROI compression, or Milestone 4 code.
- Figure changes:
  - stopped generating the mixed-unit `results/m3_world_risk/early_vs_late_conflict.png` figure;
  - added `results/m3_world_risk/early_vs_late_ttcf.png` for TTCf values on a seconds axis;
  - added `results/m3_world_risk/early_vs_late_risk_decomposition.png` for spatial, temporal, and risk scores on a `[0, 1]` score axis;
  - improved `results/m3_world_risk/world_risk_overview.png` with lighter corridor fills, clearer planned/state centerlines, obstacle AABB legend, first-entry marker legend, P/S/C score explanation, and safer OUTSIDE_BOTH label placement;
  - improved `results/m3_world_risk/clearance_risk_curve.png` with planned/state marker legends, representative NEAR_BOUNDARY and OUTSIDE_BOTH annotations, sigma note, and heuristic-score wording;
  - kept `results/m3_world_risk/parameter_sensitivity.png` as the PASS summary;
  - added `results/m3_world_risk/parameter_sensitivity_margins.png` for the three positive ordering margins across all 9 sigma/tau parameter pairs.
- Updated files:
  - `scripts/plot_m3d_world_risk.py`
  - `scripts/validate_m3d_report.py`
  - `tests/test_m3d_evaluation_helpers.py`
  - `docs/m3_world_risk_validation_report.md`
  - `docs/progress.md`
  - `README.md`
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m py_compile scripts\plot_m3d_world_risk.py scripts\validate_m3d_report.py tests\test_m3d_evaluation_helpers.py`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv`
  - `.\.venv\Scripts\python.exe .\scripts\evaluate_m3d_world_risk.py`
  - `.\.venv\Scripts\python.exe .\scripts\plot_m3d_world_risk.py`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3d_report.py`
- Validation results:
  - `py_compile`: passed.
  - Unit tests: `75` tests passed.
  - M3C validator on episode_0002: exit code 0.
  - M3D evaluation: exit code 0.
  - M3D plot generation: exit code 0.
  - M3D report validator: exit code 0.
  - New figure files generated successfully.
  - `docs/m3_world_risk_validation_report.md` no longer references the mixed-unit `early_vs_late_conflict.png`.
  - Minimum positive parameter margin: `0.036022059` for `ON_PLANNED_PATH planned risk - state risk` at `sigma_distance_m=0.100`, `tau_time_s=0.500`.
- GUI validation:
  - regenerated M3D-R figures passed user visual review: `world_risk_overview`, `clearance_risk_curve`, `early_vs_late_ttcf`, `early_vs_late_risk_decomposition`, `planned_vs_state_risk`, planned/state decomposition, trajectory disagreement, parameter sensitivity, and parameter sensitivity margins.

## Milestone 3 acceptance closure

- Stage: Milestone 3 formally accepted on local branch `feature/m3-world-risk`.
- Official evidence data:
  - `data/logs/m3/risk_validation_episode_0002.csv`
  - `data/logs/m3/risk_validation_episode_0002_trace.txt`
- GUI reproduction evidence:
  - `episode_0005`, generated during the final GUI review.
  - This episode is not used for official M3D report values, figures, sensitivity checks, or automatic validation.
- Human acceptance:
  - Scene Tree contained all six M3 DEF obstacle nodes.
  - Six obstacles were visible and did not appear mutually overlapped.
  - The robot did not visibly overlap obstacles, flip, or get stuck.
  - GUI controller run completed with `analysis_time_s=7.968`, `planned_points=63`, `state_points=63`, `trajectory_disagreement=0.040803441`, `csv_rows=6`, `m3_world_risk_validation: complete`, and successful controller exit.
  - Console had no `Traceback`, `AttributeError`, or `status:1`.
  - Non-blocking environment warning: ports `1234` and `1235` were already in use, so Webots automatically used port `1236`. This is recorded as an environment warning and not an experiment failure.
  - Latest M3D-R figures passed visual review.
- Scope guard:
  - No risk algorithm, formula, parameter, obstacle coordinate, obstacle size, Webots world, controller, CSV, plotting code, generated data, or generated result file was changed during acceptance closure.
  - Risk scores remain heuristic proxy scores, not probabilities of collision.
  - Parameter-stability conclusions are limited to the tested 9 sigma/tau combinations.
- Updated files:
  - `docs/progress.md`
  - `docs/roadmap.md`
  - `docs/m3_world_risk_validation_report.md`
  - `scripts/validate_m3d_report.py`
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m py_compile scripts\m3d_world_risk_common.py scripts\evaluate_m3d_world_risk.py scripts\plot_m3d_world_risk.py scripts\validate_m3d_report.py scripts\validate_m3c_risk_dataset.py tests\test_m3d_evaluation_helpers.py`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv`
  - `.\.venv\Scripts\python.exe .\scripts\evaluate_m3d_world_risk.py`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m3d_report.py`
- Validation results:
  - `py_compile`: passed.
  - Unit tests: `75` tests passed.
  - M3C validator on episode_0002: exit code 0.
  - M3D evaluation: exit code 0.
  - M3D report validator: exit code 0.

## Milestone 4A: image-risk projection design freeze

- Stage: Milestone 4A complete on local branch `feature/m4-image-risk-projection`.
- Starting commit: `85fa41c docs: accept world risk milestone`.
- Project root and Git:
  - `C:\Users\ROG\Documents\risk-aware-visual-communication`
  - Git top-level resolved to `C:/Users/ROG/Documents/risk-aware-visual-communication`.
  - Current branch verified as `feature/m4-image-risk-projection`.
  - Working tree was clean before Milestone 4A edits.
  - Branch contains the accepted Milestone 3 commit `85fa41c`.
- Created design document:
  - `docs/image_risk_projection_design.md`
- Updated documentation:
  - `docs/progress.md`
  - `docs/roadmap.md`
  - `docs/decisions.md`
  - `docs/system_overview.md`
  - `README.md`
- Official M3 evidence retained:
  - `data/logs/m3/risk_validation_episode_0002.csv`
  - `data/logs/m3/risk_validation_episode_0002_trace.txt`
  - `episode_0005` remains GUI reproduction evidence only.
- Coordinate definitions frozen:
  - Webots world ground plane: `x-y`.
  - Webots vertical axis: `z`.
  - Robot body forward axis: e-puck local `+x`.
  - Robot body left axis: e-puck local `+y`; right is `-y`; up is `+z`.
  - Yaw: heading of robot local `+x` around world `+z`.
  - Webots Camera device convention for the first implementation: `+x_device` image/right, `+y_device` image/up, `-z_device` optical forward.
  - Project optical frame: `+z_optical` forward, `+x_optical` right, `+y_optical` down.
  - Frozen device-to-optical transform: `diag(1, -1, -1)`.
  - Image pixel frame: `u` right, `v` down, pixel-center convention, top-left pixel center `(0, 0)`.
- Camera parameters frozen from R2025a official e-puck PROTO and current worlds:
  - Camera device name: `camera`.
  - Camera mount in e-puck PROTO: `translation 0.03 0 0.028`.
  - Current camera rotation: `0 0 1 0`.
  - Width: `160 px`.
  - Height: `120 px`.
  - Horizontal FOV: `0.84 rad`.
  - Near clip: `0.0055 m`.
  - Intrinsics rule: `fx = W / (2 * tan(horizontal_fov / 2))`, `fy = fx`, `cx = (W - 1) / 2`, `cy = (H - 1) / 2`.
  - Current derived values: `fx=179.142225973 px`, `fy=179.142225973 px`, `cx=79.5 px`, `cy=59.5 px`, `vertical_fov=0.646372669 rad`.
- Interface and method boundaries frozen:
  - `CameraIntrinsics`
  - `CameraExtrinsics`
  - `ObstacleBox3D`
  - `ProjectedPoint`
  - `ProjectedObstacle`
  - Visibility statuses: `fully_visible`, `partially_visible`, `outside_frustum`, `behind_camera`, `intersects_near_plane`, `degenerate_projection`.
  - 3D Box projection must use corners, edges, near-plane clipping, image-boundary clipping, and a projected polygon; center-only and raw min/max-only projection are rejected.
  - Risk masks remain independent planned/state/combined channels and use max-union on overlaps.
  - Image-risk masks represent risky obstacle visual regions, not empty trajectory-corridor pixels.
  - First version does not claim true inter-object occlusion handling.
- Dependency decision:
  - Projection geometry core should start with Python standard library only.
  - Pillow may be used later for image IO/masks if needed.
  - OpenCV is deferred until automatic image validation requires it.
  - Shapely and ML frameworks are not introduced.
- Explicitly not created or modified in Milestone 4A:
  - no camera projection algorithm;
  - no Python projection module;
  - no M4 Webots world/controller;
  - no Camera frame, mask, plot, or generated data;
  - no JPEG, ROI compression, network simulation, or machine learning;
  - no M3 algorithm, scene, parameter, CSV, or official evidence modification.
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `Select-String` documentation consistency checks across `docs/image_risk_projection_design.md`, `docs/roadmap.md`, `docs/decisions.md`, `docs/system_overview.md`, `README.md`, and `docs/progress.md`
  - `C:\Program Files\Git\cmd\git.exe status --short --ignored`
  - `C:\Program Files\Git\cmd\git.exe diff --stat`
- Validation results:
  - Existing unit-test baseline: `75` tests passed.
  - Documentation records `episode_0002` as official M3 evidence and `episode_0005` as GUI reproduction evidence only.
  - README and roadmap both state that M4A is design-only and that projection code, masks, scenes, and compression are not implemented.
  - Git diff contains only documentation changes; ignored `data/`, `results/`, cache, and Webots GUI files remain untracked/ignored.

## Milestone 4B: pure-Python camera projection core

- Stage: Milestone 4B complete on local branch `feature/m4-image-risk-projection`.
- Starting design commit: `f7a752b docs: freeze image risk projection design`.
- Created modules:
  - `perception/camera_models.py`
  - `perception/camera_projection.py`
- Created tests:
  - `tests/test_camera_models.py`
  - `tests/test_camera_projection.py`
- Public data structures:
  - `VisibilityStatus`
  - `CameraIntrinsics`
  - `CameraExtrinsics`
  - `ObstacleBox3D`
  - `ProjectedPoint`
  - `ProjectedObstacle`
- Core projection capabilities implemented:
  - finite vector/matrix validation;
  - 3x3 matrix-vector and matrix-matrix multiplication;
  - vector add/subtract and dot product;
  - 3x3 determinant and transpose;
  - identity and pose-derived camera extrinsics;
  - world -> camera device -> project optical transforms;
  - camera device -> world round-trip helper;
  - pinhole optical point projection;
  - 3D near-plane edge clipping for Box corners and edges;
  - deterministic 2D monotonic-chain convex hull;
  - Sutherland-Hodgman image-rectangle clipping;
  - polygon area and bounding box;
  - `project_obstacle_box(...)` as the main 3D Box projection interface.
- Visibility priority implemented:
  1. `behind_camera`
  2. `outside_frustum`
  3. `degenerate_projection`
  4. `intersects_near_plane`
  5. `partially_visible`
  6. `fully_visible`
- Tests cover:
  - current e-puck 160x120 intrinsics derived from horizontal FOV `0.84 rad` and near `0.0055 m`;
  - invalid intrinsics, extrinsics, and 3D Box inputs;
  - identity, translation, yaw, pitch, roll, device-to-optical transform, and round-trip behavior;
  - principal point, right/down image directions, depth scaling, FOV boundaries, near plane, behind point, and non-finite point rejection;
  - convex hull duplicates/collinearity, rectangle clipping, full outside, boundary touch, large polygon, area, and bbox;
  - pure-math projection roles: `CENTER_VISIBLE`, `LEFT_VISIBLE`, `RIGHT_VISIBLE`, `PARTIAL_IMAGE_EDGE`, `OUTSIDE_FRUSTUM`, `BEHIND_CAMERA`, `NEAR_PLANE_INTERSECTION`, and two `DEPTH_OVERLAP` Boxes.
- Explicitly not implemented in Milestone 4B:
  - no Webots adapter or Webots runtime integration;
  - no M4 world/controller;
  - no RGB frame, CSV, mask, figure, or generated data;
  - no `risk_map/image_risk_map.py`;
  - no image-risk mask generation;
  - no true occlusion handling;
  - no JPEG, ROI compression, network simulation, closed-loop navigation, or machine learning;
  - no M1-M3 algorithm, scene, risk parameter, CSV, plot, or accepted evidence changes.
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m py_compile perception\camera_models.py perception\camera_projection.py tests\test_camera_models.py tests\test_camera_projection.py`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `Select-String -Path perception\camera_models.py,perception\camera_projection.py -Pattern '^\s*(import|from)\s+(numpy|NumPy|cv2|PIL|webots|controller|shapely|scipy|torch|tensorflow)\b' -CaseSensitive:$false`
  - checks for absent `risk_map/image_risk_map.py`, `simulator/adapters/webots_camera_adapter.py`, M4 worlds, and M4 controllers
  - `C:\Program Files\Git\cmd\git.exe status --short --ignored`
  - `C:\Program Files\Git\cmd\git.exe diff --stat`
- Validation results:
  - `py_compile`: passed.
  - Unit tests: `101` tests passed, including the previous 75-test baseline and 26 new M4B tests.
  - Prohibited dependency import scan: no forbidden imports in `perception/camera_models.py` or `perception/camera_projection.py`.
  - Confirmed absent: `risk_map/image_risk_map.py`, `simulator/adapters/webots_camera_adapter.py`, M4 worlds, and M4 controllers.
  - Git diff scope contains only M4B projection core modules, M4B tests, and roadmap/progress documentation.
  - Ignored `data/`, `results/`, caches, and Webots GUI files remain untracked/ignored.

## Milestone 4C: Webots camera projection validation

- Stage: Milestone 4C formally accepted on local branch `feature/m4-image-risk-projection`.
- Starting commit: `af956e5 feat: implement camera projection core`.
- Created implementation files:
  - `simulator/m4c_config.py`
  - `simulator/adapters/webots_camera_adapter.py`
  - `simulator/worlds/m4_camera_projection_validation.wbt`
  - `simulator/controllers/m4_camera_projection_validation/m4_camera_projection_validation.py`
  - `scripts/validate_m4c_projection_dataset.py`
  - `scripts/plot_m4c_projection_overlay.py`
  - `tests/test_webots_camera_adapter_helpers.py`
  - `docs/m4_camera_projection_validation_report.md`
- Updated documentation:
  - `docs/progress.md`
  - `docs/roadmap.md`
  - `docs/decisions.md`
  - `docs/image_risk_projection_design.md`
  - `docs/system_overview.md`
  - `README.md`
  - `scripts/validate_m3d_report.py`
- Dedicated world: `simulator/worlds/m4_camera_projection_validation.wbt`.
- Controller: `simulator/controllers/m4_camera_projection_validation/m4_camera_projection_validation.py`.
- Webots adapter API facts checked from local R2025a Python controller files:
  - `Supervisor.getFromDevice(tag)` exists.
  - `Node.getPose()`, `Node.getPosition()`, and `Node.getOrientation()` exist.
  - `Camera.getWidth()`, `Camera.getHeight()`, `Camera.getFov()`, `Camera.getNear()`, and `Camera.saveImage()` exist.
- Camera Node acquisition method: the controller gets the `camera` device, reads its private Webots device tag, and calls `Supervisor.getFromDevice(tag)` to get the Camera node.
- Camera actual runtime parameters:
  - width `160 px`;
  - height `120 px`;
  - horizontal FOV `0.840000000 rad`;
  - vertical FOV `0.646372669 rad`;
  - near clip `0.005500000 m`;
  - `fx=fy=179.142225973 px`;
  - `cx=79.5 px`, `cy=59.5 px`;
  - camera world position at the accepted snapshot: `(0.030000000, -0.000000308, 0.027948551) m`.
- Camera pose conversion:
  - Webots Camera pose is parsed as a camera-to-world 4x4 matrix and cross-checked against `Node.getPosition()`.
  - Adapter computes `R_world_to_camera = R_camera_to_world^T`.
  - Adapter computes `t_world_to_camera = -R_world_to_camera * C_world`.
- Webots e-puck Camera axis calibration:
  - `episode_0001` showed that the initial Milestone 4A assumption `diag(1,-1,-1)` made front-visible Boxes project outside the image while the RGB frame showed them in view.
  - The Webots R2025a e-puck Camera adapter now uses `x_optical=-y_device`, `y_optical=-z_device`, `z_optical=x_device`, i.e. `[[0,-1,0],[0,0,-1],[1,0,0]]`.
  - This is recorded as a Webots adapter calibration decision; the pure projection core remains generic and Webots-decoupled.
- Official automated evidence episode: `projection_validation_episode_0003`.
- GUI reproduction and human acceptance episode: `projection_validation_episode_0004`.
- Output files:
  - `data/frames/m4/projection_validation_episode_0003.png`
  - `data/logs/m4/projection_validation_episode_0003.csv`
  - `data/metadata/m4/projection_validation_episode_0003.json`
  - `results/m4_projection/projection_overlay.png`
- Debug artifacts:
  - `episode_0001` is a failed axis-calibration run and is not success evidence.
  - `episode_0002` is a calibration run before depth-overlap color-mask policy was corrected and is not the accepted automatic evidence.
- Evidence usage:
  - `episode_0003` remains the official automatic image-alignment, IoU metric, and validator evidence.
  - `episode_0004` is GUI reproduction and human acceptance evidence only; it does not replace `episode_0003` formal outputs.
- Projection CSV:
  - 9 rows, one per validation Box.
  - Projection-only fields; no planned, state, or combined image-risk fields are present.
  - Frame path is project-relative and contains no `Downloads`.
- Validation roles and visibility in accepted `episode_0003`:
  - `CENTER_VISIBLE`: `fully_visible`, bbox `(62.599, 31.073, 96.400, 64.873)`;
  - `LEFT_VISIBLE`: `fully_visible`, bbox `(2.331, 36.321, 36.506, 63.882)`;
  - `RIGHT_VISIBLE`: `fully_visible`, bbox `(122.494, 36.320, 156.669, 63.881)`;
  - `PARTIAL_IMAGE_EDGE`: `partially_visible`, bbox `(155.801, 19.361, 159.000, 70.545)`, truncation `0.959700735`;
  - `OUTSIDE_FRUSTUM`: `outside_frustum`;
  - `BEHIND_CAMERA`: `behind_camera`;
  - `NEAR_PLANE_INTERSECTION`: `intersects_near_plane`, finite clipped projection over the image bounds;
  - `DEPTH_OVERLAP_FRONT`: `fully_visible`;
  - `DEPTH_OVERLAP_BACK`: `fully_visible`.
- Enforced automatic color-alignment metrics:
  - `CENTER_VISIBLE`: bbox IoU `0.926`, polygon IoU `0.943`, center error `0.027 px`, width error `0.023`, height error `0.052`;
  - `LEFT_VISIBLE`: bbox IoU `0.914`, polygon IoU `0.889`, center error `0.131 px`, width error `0.033`, height error `0.055`;
  - `RIGHT_VISIBLE`: bbox IoU `0.887`, polygon IoU `0.862`, center error `0.590 px`, width error `0.062`, height error `0.055`;
  - `PARTIAL_IMAGE_EDGE`: bbox IoU `0.767`, polygon IoU `0.859`, center error `2.549 px`, width error `0.047`, height error `0.195`.
- Other automatic checks passed:
  - 9 unique roles;
  - camera parameters match expected values;
  - LEFT center is left of principal point and RIGHT center is right of principal point;
  - CENTER is near the principal point;
  - OUTSIDE and BEHIND have no valid clipped polygon and target colors are absent;
  - NEAR_PLANE has finite valid projection;
  - DEPTH_OVERLAP projected bboxes overlap.
- M3 report-validator maintenance:
  - `scripts/validate_m3d_report.py` now checks forbidden camera/ROI/ML coupling inside M3D scripts instead of scanning the whole repository for post-M3 artifact names.
  - This keeps M3D validation meaningful after Milestone 4 legitimately creates camera-projection files.
- Validation actually run:
  - `.\.venv\Scripts\python.exe -m py_compile simulator\m4c_config.py simulator\adapters\webots_camera_adapter.py simulator\controllers\m4_camera_projection_validation\m4_camera_projection_validation.py scripts\validate_m4c_projection_dataset.py scripts\plot_m4c_projection_overlay.py tests\test_webots_camera_adapter_helpers.py`
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests`
  - `& "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --minimize --stdout --stderr --port=1242 ".\simulator\worlds\m4_camera_projection_validation.wbt"`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py .\data\logs\m4\projection_validation_episode_0003.csv`
  - `.\.venv\Scripts\python.exe .\scripts\plot_m4c_projection_overlay.py .\data\logs\m4\projection_validation_episode_0003.csv`
  - `.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py .\data\logs\m4\projection_validation_episode_0003.csv`
- Validation results:
  - `py_compile`: passed.
  - Unit tests: `110` tests passed.
  - Webots generated the RGB frame, 9-row projection CSV, and metadata JSON.
  - M4C validator: exit code 0.
  - Overlay plot: exit code 0.
  - Re-run M4C validator after overlay generation: exit code 0.
- Webots command-line behavior:
  - As in earlier milestones, Webots remained open after the controller returned, so the shell tool timed out. The validation process was stopped after output files and validator results were confirmed.
- GUI validation:
  - passed by user review.
  - Scene Tree contained all 9 validation Boxes: `M4_CENTER_VISIBLE`, `M4_LEFT_VISIBLE`, `M4_RIGHT_VISIBLE`, `M4_PARTIAL_IMAGE_EDGE`, `M4_OUTSIDE_FRUSTUM`, `M4_BEHIND_CAMERA`, `M4_NEAR_PLANE_INTERSECTION`, `M4_DEPTH_OVERLAP_FRONT`, and `M4_DEPTH_OVERLAP_BACK`.
  - LEFT/RIGHT appeared on the correct image sides with no mirroring, overlay was not vertically inverted, CENTER and principal point were near image center, CENTER/LEFT/RIGHT outlines covered their Boxes, PARTIAL clipped only at the expected right boundary, OUTSIDE and BEHIND had no valid image region, and DEPTH_OVERLAP regions overlapped.
  - `NEAR_PLANE_INTERSECTION` was `intersects_near_plane`, finite, without NaN/Inf, and safely clipped to the image boundary. Its broad outline is expected near-plane diagnostic geometry, not an image risk mask or normal ROI experiment.
  - GUI episode `episode_0004` reported `camera width=160`, `camera height=120`, `fov=0.84`, `near=0.0055`, `snapshot_time_s=0.320`, `obstacle_rows=9`, saved frame/CSV outputs, `m4_camera_projection_validation: complete`, and successful controller exit.
  - Console had no `Traceback`, `AttributeError`, or `status: 1`.
- Explicitly not implemented in Milestone 4C:
  - no image-risk masks;
  - no planned/state/combined risk mask fields;
  - no `risk_map/image_risk_map.py`;
  - no true rendered occlusion model;
  - no camera projection changes to accepted M3 evidence;
  - no JPEG, ROI compression, network simulation, closed-loop navigation, ROS 2, WSL, or machine learning.

## Milestone 4D-1 - Pure-Python image-risk mask core

- Status: completed as a Webots-decoupled core implementation only.
- Branch and baseline:
  - working branch: `feature/m4-image-risk-projection`;
  - starting commit: `8034a9d docs: accept Webots camera projection alignment`;
  - project root: `C:\Users\ROG\Documents\risk-aware-visual-communication`.
- New core file:
  - `risk_map/image_risk_map.py`.
- New tests:
  - `tests/test_image_risk_map.py`.
- Implemented data structures and interface:
  - immutable `Mask2D` with row-major values, integer pixel-center indexing, rows/statistics helpers, dimension checks, finite value checks, and `[0, 1]` validation;
  - `ProjectedObstacleRisk` binding planned/state/combined heuristic risk scores to a `ProjectedObstacle`;
  - `ObstacleMaskContribution` diagnostics for eligibility, skip reason, candidate pixels, and per-channel written pixels;
  - `ImageRiskMasks` containing planned, state, and combined masks with a pixelwise combined-mask invariant;
  - `build_image_risk_masks(width_px, height_px, obstacles)`;
  - `bind_projection_to_risk(projection, planned_risk, state_risk, combined_risk)`.
- Core semantics:
  - only `ProjectedObstacle.clipped_polygon` is rasterized;
  - pixel centers are integer coordinates `(u, v)`, not `(u + 0.5, v + 0.5)`;
  - eligible visibility statuses are `fully_visible`, `partially_visible`, and `intersects_near_plane`;
  - `outside_frustum`, `behind_camera`, and `degenerate_projection` do not write pixels, even with high risk;
  - overlaps use pixelwise maximum independently for planned, state, and combined channels;
  - `combined_risk` must equal `max(planned_risk, state_risk)` within tolerance, and the combined mask must equal the pixelwise max of planned and state masks;
  - duplicate obstacle IDs are rejected;
  - contributions preserve input order, while final masks are order-invariant under overlap max-union.
- Dependency and scope checks:
  - no Webots controller, world, adapter, camera-parameter, projection-core, M3 risk, compression, network, ROI, machine-learning, or navigation code was modified;
  - no PNG mask, frame, CSV, metadata, figure, Webots episode, or M4D-2 diagnostic output was generated;
  - dependency scan of `risk_map/image_risk_map.py` found no forbidden package imports such as NumPy, OpenCV, Pillow, Shapely, SciPy, torch, TensorFlow, or Webots/controller APIs. The module imports the project `perception.camera_models` dataclasses to consume accepted 4B projection outputs.
- Validation actually run:
  - `python -m py_compile risk_map\image_risk_map.py tests\test_image_risk_map.py`: passed.
  - `python -m unittest tests.test_image_risk_map`: 29 tests passed.
  - `python -m unittest discover -s tests`: 139 tests passed.
  - `git diff -- perception/camera_models.py perception/camera_projection.py simulator/adapters/webots_camera_adapter.py`: no changes.
- Explicitly not implemented in Milestone 4D-1:
  - no Webots risk-mask integration;
  - no mask PNG or overlay generation;
  - no mask CSV/metadata;
  - no planned/state/combined image risk mask generated from `episode_0003`;
  - no true occlusion handling;
  - no ROI compression, codec, network, machine learning, or navigation.

## Milestone 4D-2 - Same-snapshot image-risk mask validation

- Status: automatic end-to-end validation completed; GUI manual acceptance remains pending.
- Branch and baseline:
  - working branch: `feature/m4-image-risk-projection`;
  - baseline commits present: `8034a9d docs: accept Webots camera projection alignment` and `e88d37f feat: implement image risk mask core`;
  - project root: `C:\Users\ROG\Documents\risk-aware-visual-communication`.
- Created implementation files:
  - `simulator/m4d_config.py`;
  - `simulator/worlds/m4d_image_risk_validation.wbt`;
  - `simulator/controllers/m4d_image_risk_validation/m4d_image_risk_validation.py`;
  - `scripts/m4d_image_risk_common.py`;
  - `scripts/validate_m4d_image_risk_dataset.py`;
  - `scripts/plot_m4d_image_risk.py`;
  - `tests/test_m4d_evaluation_helpers.py`;
  - `docs/m4_image_risk_validation_report.md`;
  - `data/masks/.gitkeep`.
- Updated:
  - `.gitignore` now ignores generated `data/masks/*` while preserving `data/masks/.gitkeep`;
  - `README.md`;
  - `docs/roadmap.md`;
  - `docs/system_overview.md`;
  - `docs/progress.md`.
- Dedicated world and controller:
  - world: `simulator/worlds/m4d_image_risk_validation.wbt`;
  - controller: `simulator/controllers/m4d_image_risk_validation/m4d_image_risk_validation.py`;
  - no M3 or M4C accepted world/controller was modified.
- Same-snapshot evidence:
  - successful M4D automatic episode: `image_risk_validation_episode_0001`;
  - snapshot time: `7.968 s`;
  - planned trajectory source: command-conditioned rollout from the pre-existing future wheel-command schedule;
  - state trajectory source: state-only constant-twist rollout from current Webots snapshot state;
  - actual future trajectory: explicitly not used.
- Runtime robot state:
  - `x=0.242882516`;
  - `y=0.070315357`;
  - `yaw=1.393201041`;
  - `linear_velocity=0.029944488 m/s`;
  - `angular_velocity=0.350989561 rad/s`.
- Runtime Camera parameters:
  - width `160 px`;
  - height `120 px`;
  - horizontal FOV `0.84 rad`;
  - near clip `0.0055 m`;
  - `fx=fy=179.142225973 px`;
  - `cx=79.5 px`, `cy=59.5 px`;
  - camera world position `(0.248188668, 0.099863469, 0.027919930) m`;
  - axis mapping remains `x_optical=-y_device`, `y_optical=-z_device`, `z_optical=x_device`.
- Trajectory summary:
  - planned points: `63`;
  - state points: `63`;
  - trajectory disagreement: `0.040803441 m`.
- Role risk and visibility:
  - `PLANNED_DOMINANT_VISIBLE`: planned `0.469831075`, state `0.189292428`, combined `0.469831075`, `partially_visible`;
  - `STATE_DOMINANT_VISIBLE`: planned `0.136077497`, state `0.226684741`, combined `0.226684741`, `partially_visible`;
  - `SHARED_RISK_VISIBLE`: planned `0.074374604`, state `0.083360084`, combined `0.083360084`, `fully_visible`;
  - `LOW_RISK_VISIBLE`: planned `0.005629554`, state `0.006903238`, combined `0.006903238`, `fully_visible`;
  - `PARTIAL_VISIBLE`: planned `0.005545375`, state `0.003763963`, combined `0.005545375`, `partially_visible`;
  - `OUTSIDE_VIEW`: planned `0.002909857`, state `0.001360382`, combined `0.002909857`, `outside_frustum`, no mask pixels;
  - `BEHIND_CAMERA`: planned `0.360274930`, state `0.360288054`, combined `0.360288054`, `behind_camera`, no mask pixels;
  - `OVERLAP_BACK`: planned `0.050168861`, state `0.055912865`, combined `0.055912865`, `fully_visible`;
  - `OVERLAP_FRONT`: planned `0.069507491`, state `0.078850731`, combined `0.078850731`, `fully_visible`.
- Contribution pixel counts:
  - `PLANNED_DOMINANT_VISIBLE`: candidate/written `480 / 480,480,480`;
  - `STATE_DOMINANT_VISIBLE`: candidate/written `3813 / 3813,3813,3813`;
  - `SHARED_RISK_VISIBLE`: candidate/written `6118 / 6118,6118,6118`;
  - `LOW_RISK_VISIBLE`: candidate/written `597 / 259,259,259`;
  - `PARTIAL_VISIBLE`: candidate/written `150 / 48,48,48`;
  - `OUTSIDE_VIEW`: candidate/written `0 / 0,0,0`;
  - `BEHIND_CAMERA`: candidate/written `0 / 0,0,0`;
  - `OVERLAP_BACK`: candidate/written `4218 / 0,0,0`;
  - `OVERLAP_FRONT`: candidate/written `4532 / 347,347,347`.
- Mask results:
  - planned nonzero pixels: `11065`;
  - state nonzero pixels: `11065`;
  - combined nonzero pixels: `11065`;
  - combined mask was validated pixelwise as `max(planned, state)`;
  - overlap pixels validated as max-union over all covering obstacles;
  - exclusive-pixel risk binding validated for planned-dominant, state-dominant, shared, low-risk, and partial roles.
- Output files:
  - `data/frames/m4/image_risk_validation_episode_0001.png`;
  - `data/logs/m4/image_risk_validation_episode_0001.csv`;
  - `data/metadata/m4/image_risk_validation_episode_0001.json`;
  - `data/masks/m4/image_risk_validation_episode_0001_masks.json`;
  - `results/m4_image_risk/planned_mask.png`;
  - `results/m4_image_risk/state_mask.png`;
  - `results/m4_image_risk/combined_mask.png`;
  - `results/m4_image_risk/planned_overlay.png`;
  - `results/m4_image_risk/state_overlay.png`;
  - `results/m4_image_risk/combined_overlay.png`;
  - `results/m4_image_risk/world_to_image_risk_summary.png`.
- RGB alignment auxiliary metrics:
  - `PLANNED_DOMINANT_VISIBLE`: bbox IoU `0.885`, polygon IoU `0.889`, center error `0.261 px`;
  - `STATE_DOMINANT_VISIBLE`: bbox IoU `0.980`, polygon IoU `0.967`, center error `0.322 px`;
  - `SHARED_RISK_VISIBLE`: bbox IoU `0.960`, polygon IoU `0.967`, center error `0.216 px`;
  - `LOW_RISK_VISIBLE`: bbox IoU `0.399`, polygon IoU `0.414`, center error `6.621 px`;
  - `PARTIAL_VISIBLE`: bbox IoU `0.287`, polygon IoU `0.316`, center error `2.225 px`.
- M4D-specific RGB threshold note:
  - LOW_RISK and PARTIAL are small or edge-clipped diagnostic objects with few color pixels; their RGB checks use documented M4D-specific relaxed auxiliary thresholds after diagnosis.
  - Numeric projection, risk, and mask validation are still based on core recomputation, not RGB color.
- Validation actually run:
  - `python -m py_compile simulator\m4d_config.py scripts\m4d_image_risk_common.py simulator\controllers\m4d_image_risk_validation\m4d_image_risk_validation.py scripts\validate_m4d_image_risk_dataset.py scripts\plot_m4d_image_risk.py tests\test_m4d_evaluation_helpers.py`: passed;
  - `python -m unittest discover -s tests`: `148` tests passed;
  - Webots R2025a command-line run of `simulator/worlds/m4d_image_risk_validation.wbt`: generated the M4D episode outputs;
  - `python scripts\validate_m4d_image_risk_dataset.py data\logs\m4\image_risk_validation_episode_0001.csv`: passed;
  - `python scripts\plot_m4d_image_risk.py data\logs\m4\image_risk_validation_episode_0001.csv`: passed;
  - M4D validator re-run after plots: passed;
  - `python scripts\validate_m4c_projection_dataset.py data\logs\m4\projection_validation_episode_0003.csv`: passed;
  - `python scripts\validate_m3c_risk_dataset.py data\logs\m3\risk_validation_episode_0002.csv`: passed;
  - `python scripts\evaluate_m3d_world_risk.py`: passed;
  - `python scripts\validate_m3d_report.py`: passed.
- Webots command-line behavior:
  - Webots again remained open at the shell level after the controller completed. The process was stopped after output files were confirmed.
- Explicitly not implemented in Milestone 4D-2:
  - no JPEG/H.264/H.265/URVC;
  - no ROI resource allocation or bytes/frame matching;
  - no network simulation;
  - no object detector or remote perception;
  - no closed-loop navigation;
  - no machine learning;
  - no dynamic obstacles;
  - no true rendered occlusion model.
- Next priority:
  - GUI manual acceptance for Milestone 4D outputs, then Milestone 4D closeout. Do not enter Milestone 5 before GUI acceptance and closeout.

## Commands actually run in the formal project

```text
Get-Content -Raw -Encoding UTF8 AGENTS.md
Get-Content -Raw -Encoding UTF8 docs/progress.md
Get-Content -Raw -Encoding UTF8 docs/roadmap.md
Get-Content -Raw -Encoding UTF8 docs/decisions.md
Get-Content -Raw -Encoding UTF8 docs/research_protocol.md
git rev-parse --show-toplevel  # attempted in the current PowerShell session; failed because git is not on PATH
git status --short --branch  # attempted in the current PowerShell session; failed because git is not on PATH
git branch --show-current  # attempted in the current PowerShell session; failed because git is not on PATH
"C:\Program Files\Git\cmd\git.exe" rev-parse --show-toplevel
"C:\Program Files\Git\cmd\git.exe" status --short --branch
"C:\Program Files\Git\cmd\git.exe" branch --show-current
"C:\Program Files\Git\cmd\git.exe" remote -v
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import platform,sys; ..."
Select-String -Path docs\*.md,AGENTS.md,README.md -Pattern <old Downloads project-root patterns> -SimpleMatch
winget search --id Cyberbotics.Webots --exact --source winget
winget show --id Cyberbotics.Webots --exact --source winget
Invoke-RestMethod https://api.github.com/repos/cyberbotics/webots/releases/latest
Invoke-WebRequest <official R2025a release URL> -OutFile <temporary installer>
Get-FileHash <temporary installer> -Algorithm SHA256
Get-AuthenticodeSignature <temporary installer>
webots-R2025a_setup.exe /SUPPRESSMSGBOXES /VERYSILENT /NOCANCEL /NORESTART /ALLUSERS
Get-ItemProperty <Windows uninstall registry paths>
webots.exe --version
webots.exe --help
webots.exe --sysinfo
```

The first `curl.exe` download attempt was reset before transferring data. A subsequent `Invoke-WebRequest` download completed from the same official HTTPS release URL and was validated before installation.

## Validation

- Formal project path and Git top level: verified.
- Project `.venv` Python 3.11.14/64-bit: verified after copying.
- Local branch state: `main` verified; no `master` branch rename was needed during this verification pass because the branch was already `main`.
- Documents path references: old Downloads root is not present as a current project root in `docs/*.md`, `AGENTS.md`, or `README.md`. The only remaining `Downloads` mention records that the old root was removed.
- Webots R2025a installation: verified through file, registry, version, help, and system-information checks.
- Camera frame capture: implemented and verified in Milestone 1C. Robot-state CSV logging, risk maps, ROI compression, object detection, and closed-loop navigation: not implemented and not tested.

## Current issues

1. Project dependencies in `requirements.txt` are not fully installed as a controlled dependency pass; matplotlib and its runtime dependencies were installed into `.venv` for Milestone 2 plotting.
2. The repository now has local commits on `feature/m2-trajectory-models`; generated data/results remain untracked and ignored.
3. The copied `.venv` remains based on a Python executable inside an application-specific Conda installation; it currently works and excludes that environment's site packages, but a dedicated base interpreter would reduce coupling if instability appears.
4. `git` is installed but not available as a bare command on the current PowerShell PATH; use `C:\Program Files\Git\cmd\git.exe` or fix PATH before relying on `git`.
5. Git `user.name` and `user.email` are now configured locally/globally for this environment as `ShirongZuo-ai <3095325284@qq.com>`.
6. Webots controller stdout/stderr did not propagate to shell logs; Milestone 1B, 1C, and 1D verification used optional controller trace files.
7. Milestone 2 and 2R Webots GUI Console red-error status still needs user visual confirmation if a GUI-level console check is required.

## Next priority

Milestone 4D is the next priority: generate planned, state, and combined image-risk masks from the accepted Milestone 4C projection outputs. Do not implement compression, networking, or navigation as part of Milestone 4D unless explicitly requested.
