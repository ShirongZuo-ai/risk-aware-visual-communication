# Progress

Last updated: 2026-07-17 (Asia/Shanghai)

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

1. Project dependencies in `requirements.txt` are not installed in `.venv`.
2. The repository has no initial commit and its files remain untracked.
3. The copied `.venv` remains based on a Python executable inside an application-specific Conda installation; it currently works and excludes that environment's site packages, but a dedicated base interpreter would reduce coupling if instability appears.
4. `git` is installed but not available as a bare command on the current PowerShell PATH; use `C:\Program Files\Git\cmd\git.exe` or fix PATH before relying on `git`.
5. Git `user.name` and `user.email` are not configured, so the initial commit requested for Milestone 1A was skipped.
6. Webots controller stdout/stderr did not propagate to shell logs; Milestone 1B, 1C, and 1D verification used optional controller trace files.
7. Milestone 1D Webots GUI Console red-error status still needs user visual confirmation if a GUI-level console check is required.

## Next priority

Review the Milestone 1D dataset manually in Webots/CSV if desired, then proceed to the next Milestone 1 task only after confirming the captured images and aligned CSV are acceptable.
