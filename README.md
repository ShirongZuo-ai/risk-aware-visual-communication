# Risk-Aware Visual Communication

Research prototype for **Trajectory-Conditioned Collision-Risk-Aware Visual Communication for Remote Robot Navigation**.

Current status: the native-Windows environment baseline has been checked, the local Git repository uses the `main` branch, the official Webots R2025a stable release is installed and verified, and Milestone 1A/1B/1C/1D have created a minimal e-puck camera world, a fixed-sequence motion controller, camera frame capture, and aligned per-frame CSV state logging. Risk maps, compression, perception, and navigation are not implemented.

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

## Documentation

- `AGENTS.md`: Codex entry point and working rules
- `docs/research_protocol.md`: question, scope, methods, and metrics
- `docs/roadmap.md`: milestone order and acceptance criteria
- `docs/decisions.md`: durable technical/research choices
- `docs/progress.md`: verified current state and next priority
