# Risk-Aware Visual Communication

Research prototype for **Trajectory-Conditioned Collision-Risk-Aware Visual Communication for Remote Robot Navigation**.

Current status: the native-Windows environment baseline has been checked, the official Webots R2025a stable release is installed and verified, Milestone 1A/1B/1C/1D have created the synchronized Webots data pipeline, Milestone 2/2R have created trajectory prediction, in-place rotation validation, forward-arc validation, and empirical uncertainty corridor evaluation, and Milestone 3A/3B/3C/3D have frozen, implemented, Webots-validated, and diagnosed the world-coordinate risk core. Image risk maps, compression, perception, and navigation are not implemented.

## Scope

The first milestone only creates a repeatable Webots world, moves one differential-drive robot, and saves time-aligned RGB frames and robot state. See `docs/research_protocol.md` and `docs/roadmap.md` before implementation.

## Native Windows environment check

From PowerShell in the intended repository folder, run:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
py -0p
python --version
git --version
& "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe" --version
nvidia-smi
wsl --status
Get-Command webots -ErrorAction SilentlyContinue
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue | Where-Object DisplayName -Like "*Webots*" | Select-Object DisplayName, DisplayVersion, InstallLocation
Get-Location
git status --short --branch
```

Do not reinstall a tool merely because it is absent from `PATH`; inspect the reported installation location first. If `git status` says the directory is not a repository, initialize it only after confirming this is the intended project folder:

```powershell
git init
```

## Python environment

The project-local `.venv` uses 64-bit Python 3.11.14. The Windows Python Launcher does not discover the installed Conda interpreters, so project commands should invoke the local environment directly:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dependencies have not been installed yet. Do not install project packages into the existing application-specific Conda environments.

The verified Webots executable is installed under the standard Program Files location. From PowerShell, check it without opening a world:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots --version
& $webots --sysinfo
```

Open the minimal e-puck camera world with the Milestone 1B fixed-sequence motion controller:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots ".\simulator\worlds\minimal_epuck_camera.wbt"
```

Milestone 1C frame capture writes PNG files to:

```text
data/frames/m1c/
```

Each run removes old `frame_*.png` files in that folder before saving new frames. Frame images are ignored by Git.

Milestone 1D writes each new run to a paired episode:

```text
data/frames/m1d/episode_0001/
data/logs/m1d/episode_0001.csv
```

Validate the latest or specified Milestone 1D episode:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_m1d_dataset.py
.\.venv\Scripts\python.exe .\scripts\validate_m1d_dataset.py .\data\logs\m1d\episode_0001.csv
```

## Milestone 2 trajectory evaluation

Run the dedicated Webots validation episode:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots ".\simulator\worlds\m2_trajectory_validation.wbt"
```

Run the Milestone 2R forward-arc validation episode:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots ".\simulator\worlds\m2_arc_trajectory_validation.wbt"
```

Run the unit tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Evaluate the latest or specified Milestone 2 trajectory CSV:

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_m2_trajectory.py
.\.venv\Scripts\python.exe .\scripts\evaluate_m2_trajectory.py .\data\logs\m2\trajectory_validation_episode_0001.csv
.\.venv\Scripts\python.exe .\scripts\evaluate_m2_trajectory.py .\data\logs\m2\trajectory_validation_episode_0002.csv --profile arc
```

Milestone 2 outputs:

```text
data/logs/m2/trajectory_validation_episode_0001.csv
data/logs/m2/trajectory_validation_episode_0002.csv
results/m2_trajectory/
results/m2_trajectory_arc/
```

## Milestone 3 world-risk core

Run the ordinary-Python risk core tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The risk core lives in:

```text
risk_map/
```

It is intentionally decoupled from Webots and only consumes world-coordinate trajectory points plus static AABB obstacle footprints. See `docs/risk_formulation_design.md` for the frozen formulas and API responsibilities.

Run the Milestone 3C Webots world-risk validation scene:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots ".\simulator\worlds\m3_world_risk_validation.wbt"
```

Validate the latest or specified M3C risk CSV:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py
.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv
```

Milestone 3C outputs:

```text
data/logs/m3/risk_validation_episode_0002.csv
data/logs/m3/risk_validation_episode_0002_trace.txt
```

Generated M3C data remains ignored by Git.

Run the Milestone 3D world-risk diagnostics:

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_m3d_world_risk.py
.\.venv\Scripts\python.exe .\scripts\plot_m3d_world_risk.py
.\.venv\Scripts\python.exe .\scripts\validate_m3d_report.py
```

The diagnostics include split EARLY/LATE figures so TTCf seconds are not plotted on the same axis as unitless risk scores:

```text
results/m3_world_risk/early_vs_late_ttcf.png
results/m3_world_risk/early_vs_late_risk_decomposition.png
results/m3_world_risk/parameter_sensitivity_margins.png
```

Milestone 3D generated outputs:

```text
data/logs/m3/risk_validation_episode_0002_trajectories.csv
results/m3_world_risk/
```

Milestone 3 report:

```text
docs/m3_world_risk_validation_report.md
```

## Documentation

- `AGENTS.md`: Codex entry point and working rules
- `docs/research_protocol.md`: question, scope, methods, and metrics
- `docs/roadmap.md`: milestone order and acceptance criteria
- `docs/decisions.md`: durable technical/research choices
- `docs/progress.md`: verified current state and next priority
- `docs/trajectory_prediction_design.md`: Milestone 2 trajectory source definitions and uncertainty design
- `docs/risk_formulation_design.md`: Milestone 3 world-coordinate risk definitions and implemented core API notes
- `docs/m3_world_risk_validation_report.md`: Milestone 3D validation report and generated figure paths
- `docs/system_overview.md`: current end-to-end pipeline summary
