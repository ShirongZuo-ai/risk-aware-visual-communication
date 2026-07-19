# Risk-Aware Visual Communication

Research prototype for **Trajectory-Conditioned Collision-Risk-Aware Visual Communication for Remote Robot Navigation**.

Current status: the native-Windows environment baseline has been checked, the official Webots R2025a stable release is installed and verified, Milestone 1A/1B/1C/1D have created the synchronized Webots data pipeline, Milestone 2/2R have created trajectory prediction and uncertainty-corridor validation, Milestone 3 has accepted the world-coordinate risk core, Milestone 4 has accepted the image-space risk chain, and Milestone 5A-5D have frozen and implemented the tiled-JPEG baselines plus one-frame development quality evaluation. M5E-A froze the multi-scene protocol, M5E-B accepted the parameterized static-AABB Webots generator, M5E-C froze calibration-only common complete-container-byte budgets, M5E-D generated the 256-frame / 4096-reconstruction formal metric table, and M5E-E completed pre-registered episode-level statistics and diagnostics. H1 is not fully supported; H2/H3 receive direction-specific support under their frozen scenario contrasts. M5E-F independent full-evidence acceptance, perception evaluation, networking, machine learning, and closed-loop navigation remain unstarted.

## M5E Calibration Budget Freeze

M5E-C generated ignored deterministic calibration data under `data/m5e_calibration/` and froze shared complete-container-byte targets for all four existing methods: severe `31466`, low `32374`, medium `33509`, and high `34871` bytes. M5E-D and M5E-E used those targets unchanged. M5E-E does not establish general Risk ROI superiority: primary effects vary by budget, baseline, and scenario.

```powershell
.\.venv\Scripts\python.exe scripts\run_m5e_calibration_dataset.py --output-root data\m5e_calibration
.\.venv\Scripts\python.exe scripts\freeze_m5e_calibration_budgets.py --output-root data\m5e_calibration
.\.venv\Scripts\python.exe scripts\validate_m5e_calibration.py --output-root data\m5e_calibration
.\.venv\Scripts\python.exe scripts\run_m5e_statistical_analysis.py --overwrite
.\.venv\Scripts\python.exe scripts\validate_m5e_statistical_analysis.py
```

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

The verified project environment has run the current `requirements.txt` stack for the accepted M5E-C baseline, including NumPy, pandas, matplotlib, Pillow, scikit-image, and OpenCV. Continue to use the project-local `.venv`; do not install project packages into unrelated application-specific Conda environments, and do not assume cross-platform support beyond the documented native-Windows/Webots setup.

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

## Milestone 4 image-risk projection design

Milestone 4A is design-only. It freezes the world-to-camera-to-image coordinate chain, camera intrinsics/extrinsics, 3D Box projection semantics, visibility statuses, planned/state/combined image-risk mask rules, validation scene roles, error metrics, module boundaries, and dependency policy:

```text
docs/image_risk_projection_design.md
```

Milestone 4B implements the Webots-decoupled projection core:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Run the Milestone 4C Webots camera-projection validation scene:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots ".\simulator\worlds\m4_camera_projection_validation.wbt"
```

Validate the latest or specified M4C projection CSV and regenerate the overlay:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py
.\.venv\Scripts\python.exe .\scripts\validate_m4c_projection_dataset.py .\data\logs\m4\projection_validation_episode_0003.csv
.\.venv\Scripts\python.exe .\scripts\plot_m4c_projection_overlay.py .\data\logs\m4\projection_validation_episode_0003.csv
```

M4C automated evidence:

```text
data/frames/m4/projection_validation_episode_0003.png
data/logs/m4/projection_validation_episode_0003.csv
data/metadata/m4/projection_validation_episode_0003.json
results/m4_projection/projection_overlay.png
docs/m4_camera_projection_validation_report.md
```

Milestone 4C is projection-only. It does not create image risk masks, ROI compression, JPEG/video outputs, or navigation code.

Run the Milestone 4D image-risk validation scene:

```powershell
$webots = Join-Path $env:ProgramFiles "Webots\msys64\mingw64\bin\webots.exe"
& $webots ".\simulator\worlds\m4d_image_risk_validation.wbt"
```

Validate and plot the accepted M4D automatic episode:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_m4d_image_risk_dataset.py .\data\logs\m4\image_risk_validation_episode_0001.csv
.\.venv\Scripts\python.exe .\scripts\plot_m4d_image_risk.py .\data\logs\m4\image_risk_validation_episode_0001.csv
```

M4D automated evidence:

```text
data/frames/m4/image_risk_validation_episode_0001.png
data/logs/m4/image_risk_validation_episode_0001.csv
data/metadata/m4/image_risk_validation_episode_0001.json
data/masks/m4/image_risk_validation_episode_0001_masks.json
results/m4_image_risk/
docs/m4_image_risk_validation_report.md
```

M4D generates image-risk masks only. It does not implement ROI compression, JPEG/video integration, networking, perception, or navigation.

## Milestone 5 compression protocol

Milestone 5A is design-only. The frozen compression and fair-bitrate protocol is:

```text
docs/m5_compression_and_bitrate_protocol.md
```

It defines the tiled-JPEG spatial allocation prototype, actual-byte matching, Uniform/Center ROI/Object ROI/Risk ROI baselines, budget-pilot process, and image-quality metrics.

Milestone 5B implements the shared Uniform tiled-JPEG codec/container and budget pilot. Milestone 5C adds deterministic Center/Object/Risk tile scoring and shared actual-byte allocation. Milestone 5D evaluates those fixed 16 allocations on the one accepted M4D frame without rerunning allocation:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_m5b_uniform_pilot.py
.\.venv\Scripts\python.exe .\scripts\validate_m5b_uniform_pilot.py
.\.venv\Scripts\python.exe .\scripts\run_m5c_allocation_validation.py
.\.venv\Scripts\python.exe .\scripts\validate_m5c_allocation_validation.py
.\.venv\Scripts\python.exe .\scripts\plot_m5c_allocation_maps.py
.\.venv\Scripts\python.exe .\scripts\run_m5d_single_frame_evaluation.py
.\.venv\Scripts\python.exe .\scripts\validate_m5d_single_frame_evaluation.py
.\.venv\Scripts\python.exe .\scripts\plot_m5d_single_frame_results.py
```

M5B generated outputs:

```text
data/logs/m5/m5b_uniform_quality_sweep.csv
data/metadata/m5/m5b_uniform_pilot.json
results/m5_compression/m5b_uniform_payload_curve.png
data/logs/m5/m5c_allocation_validation.csv
data/metadata/m5/m5c_allocation_validation.json
results/m5_compression/m5c_score_maps.png
results/m5_compression/m5c_quality_maps.png
results/m5_compression/m5c_budget_utilization.png
data/logs/m5/m5d_single_frame_quality.csv
data/metadata/m5/m5d_single_frame_evaluation.json
data/decoded/m5/m5d/
results/m5_compression/m5d_*.png
```

These are development outputs from `data/frames/m4/image_risk_validation_episode_0001.png` and are ignored by Git. M5D adds only a single-frame descriptive quality evaluation; it does not establish general method superiority, perception benefit, communication benefit, or navigation benefit. See `docs/m5d_single_frame_evaluation_report.md`.

Milestone 5E-A freezes the later multi-scene experiment before data generation:

```text
docs/m5e_multiscene_offline_evaluation_protocol.md
```

The accepted M4D/M5D frame remains development-only and cannot enter M5E calibration or formal statistics. M5E-A created no frames or results. M5E-B runs the frozen scenario/snapshot protocol without compression evaluation:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_m5e_dataset_smoke.py --output-root data --timeout-s 90
.\.venv\Scripts\python.exe .\scripts\validate_m5e_dataset.py --output-root data --split smoke
.\.venv\Scripts\python.exe .\scripts\plot_m5e_dataset_diagnostics.py --output-root data
```

The smoke output contains 8 scenarios x 4 snapshots under `data/frames/m5e/`, `data/masks/m5e/`, and `data/metadata/m5e/`; its manifest is `data/logs/m5/m5e_dataset_manifest.csv`. These generated artifacts are ignored by Git. M5E-B is accepted for deterministic dataset generation and frozen risk-scenario validation; targeted GUI manual checks covered S2, S3, S5, and S7. M5E-B did not generate calibration/formal data, select common budgets, or establish that Risk ROI is superior across multiple scenes. M5E-C later froze common budgets, M5E-D generated the formal metric table, and M5E-E completed episode statistics. M5E-F remains unstarted.

## Documentation

- `AGENTS.md`: Codex entry point and working rules
- `docs/research_protocol.md`: question, scope, methods, and metrics
- `docs/roadmap.md`: milestone order and acceptance criteria
- `docs/decisions.md`: durable technical/research choices
- `docs/progress.md`: verified current state and next priority
- `docs/trajectory_prediction_design.md`: Milestone 2 trajectory source definitions and uncertainty design
- `docs/risk_formulation_design.md`: Milestone 3 world-coordinate risk definitions and implemented core API notes
- `docs/m3_world_risk_validation_report.md`: Milestone 3D validation report and generated figure paths
- `docs/image_risk_projection_design.md`: Milestone 4A image-risk projection design and acceptance criteria
- `docs/m4_camera_projection_validation_report.md`: Milestone 4C automated camera-projection validation report and GUI checklist
- `docs/m4_image_risk_validation_report.md`: Milestone 4D image-risk mask validation report and GUI checklist
- `docs/m5_compression_and_bitrate_protocol.md`: Milestone 5A tiled-JPEG spatial allocation, fair byte matching, baseline, and metric protocol
- `docs/m5b_tiled_jpeg_validation_report.md`: Milestone 5B codec/container, Uniform pilot, and matcher validation report
- `docs/m5c_spatial_allocation_validation_report.md`: Milestone 5C score/allocation validation report
- `docs/m5d_single_frame_evaluation_report.md`: Milestone 5D matched-budget single-frame quality report
- `docs/m5e_multiscene_offline_evaluation_protocol.md`: Milestone 5E split, scenario, snapshot, budget, metric, statistics, and failure protocol
- `docs/m5e_dataset_generator_validation_report.md`: Milestone 5E-B smoke generator, scenario validation, reproducibility, and GUI checklist
- `docs/m5e_calibration_protocol.md`: Milestone 5E-C calibration-only byte-feasibility and common-budget freeze protocol
- `docs/m5e_calibration_report.md`: Milestone 5E-C calibration results, frozen common budgets, and validation baseline
- `docs/m5e_formal_evaluation_report.md`: Milestone 5E-D formal split, 4096 reconstructions, frozen metrics, and validation baseline
- `docs/m5e_statistical_analysis_report.md`: Milestone 5E-E episode statistics, hypothesis outcomes, scenario diagnostics, trade-offs, and limitations
- `docs/system_overview.md`: current end-to-end pipeline summary
