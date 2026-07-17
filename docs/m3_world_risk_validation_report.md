# Milestone 3 World-Risk Validation Report

Last updated: 2026-07-18 (Asia/Shanghai)

## 1. Research Purpose

Milestone 3 validates the first world-coordinate, trajectory-conditioned obstacle risk layer before any camera projection or image-space allocation work. The goal is to verify that static AABB obstacle footprints, planned/state trajectories, trajectory occupancy corridors, and interpretable risk scores behave consistently on a real Webots episode.

## 2. Successful Episode

The accepted evidence is:

```text
data/logs/m3/risk_validation_episode_0002.csv
data/logs/m3/risk_validation_episode_0002_trace.txt
```

The episode contains one analysis snapshot and six obstacle rows. `scripts/validate_m3c_risk_dataset.py` exits 0 for this CSV.

## 3. Rejected Calibration Episode

`risk_validation_episode_0001.csv` was a calibration/debug run. Its first nominal obstacle layout did not satisfy all role relationships under the actual Webots analysis state, so it is not used for figures, summaries, sensitivity checks, or final Milestone 3 evidence.

## 4. Analysis Snapshot

The analysis time is `7.968 s`, one 32 ms Webots step before the scheduled command switch at `8.000 s`.

Current robot state from the accepted CSV:

| field | value |
|---|---:|
| x | 0.242882516 |
| y | 0.070315357 |
| yaw_rad | 1.393201041 |
| linear_velocity_m_s | 0.029944488 |
| angular_velocity_rad_s | 0.350989561 |

## 5. Trajectory Generation

Planned trajectory is regenerated from the current Webots state and the known future command schedule in `simulator/m3c_config.py`.

State trajectory is regenerated from the same current state using constant-twist extrapolation with current linear and angular velocity.

Both trajectories use:

```text
horizon = 2.0 s
step = 0.032 s
```

The regenerated trajectory file is:

```text
data/logs/m3/risk_validation_episode_0002_trajectories.csv
```

This file is generated data and is ignored by Git.

## 6. Data-Leakage Protection

The M3D evaluation uses only:

- current state stored in episode_0002;
- predefined future command schedule;
- static obstacle footprints from episode_0002;
- frozen risk parameters.

It does not read future actual pose, future actual yaw, future actual velocity, or later Webots state rows.

## 7. Trajectory Disagreement

The recomputed maximum planned/state Euclidean disagreement is:

```text
0.040803441 m
```

This matches the CSV value within the validation tolerance. The disagreement curve is written to:

```text
results/m3_world_risk/trajectory_disagreement_over_time.png
```

## 8. Corridor Radius

The M3 validation corridor radius is:

```text
corridor_radius_m = 0.037592257
```

This value follows the Milestone 2 convention:

```text
robot half width + empirical prediction residual + safety margin
```

The corridor radius already includes robot half width and is not inflated again in Milestone 3.

## 9. Obstacles

All six Webots obstacles are static, unrotated AABB Box objects with size `0.025 m x 0.025 m x 0.05 m`.

| obstacle_id | DEF | center_x | center_y |
|---|---|---:|---:|
| EARLY_CONFLICT | M3_EARLY_CONFLICT | 0.297106 | 0.065676 |
| LATE_CONFLICT | M3_LATE_CONFLICT | 0.241455 | 0.162030 |
| ON_PLANNED_PATH | M3_ON_PLANNED_PATH | 0.298331 | 0.106364 |
| ON_STATE_PATH | M3_ON_STATE_PATH | 0.203578 | 0.123618 |
| NEAR_BOUNDARY | M3_NEAR_BOUNDARY | 0.187397 | 0.095750 |
| OUTSIDE_BOTH | M3_OUTSIDE_BOTH | 0.330000 | 0.185000 |

## 10. Obstacle Risk Results

| obstacle_id | planned clearance | planned TTCf | planned risk | state clearance | state TTCf | state risk | combined risk |
|---|---:|---:|---:|---:|---:|---:|---:|
| EARLY_CONFLICT | -0.000109235 | 0.540991177 | 0.582170932 | 0.002997031 | none | 0.666415720 | 0.666415720 |
| LATE_CONFLICT | -0.003019928 | 1.567852200 | 0.208492502 | -0.016164765 | 1.407580468 | 0.244734711 | 0.244734711 |
| ON_PLANNED_PATH | -0.024513607 | 0.650445002 | 0.521813517 | 0.004297946 | none | 0.455725349 | 0.521813517 |
| ON_STATE_PATH | 0.000910321 | none | 0.430045704 | -0.020909343 | 0.108539760 | 0.897143223 | 0.897143223 |
| NEAR_BOUNDARY | 0.007032912 | none | 0.764404461 | 0.000788975 | none | 0.138486732 | 0.764404461 |
| OUTSIDE_BOTH | 0.030868868 | none | 0.072994049 | 0.058035029 | none | 0.045094095 | 0.072994049 |

Generated summary files:

```text
results/m3_world_risk/m3d_risk_summary.csv
results/m3_world_risk/m3d_risk_summary.json
```

## 11. EARLY vs LATE

Both EARLY and LATE enter the planned trajectory corridor, so their planned spatial scores are both `1.0`.

The risk ordering is driven by the time term:

```text
EARLY TTCf = 0.540991177 s
LATE TTCf = 1.567852200 s
EARLY temporal score = 0.582170932
LATE temporal score = 0.208492502
EARLY planned risk > LATE planned risk
```

Diagnostic figures:

```text
results/m3_world_risk/early_vs_late_ttcf.png
results/m3_world_risk/early_vs_late_risk_decomposition.png
```

The TTCf comparison is kept on a seconds axis. The spatial, temporal, and risk scores are shown separately on a `[0, 1]` score axis so the figure does not mix physical time with unitless scores.

## 12. Planned and State Dominance

ON_PLANNED_PATH has smaller planned clearance and higher planned risk than state risk. It is planned-dominant.

ON_STATE_PATH has smaller state clearance and higher state risk than planned risk. It is state-dominant.

Diagnostic figure:

```text
results/m3_world_risk/planned_vs_state_risk.png
```

## 13. NEAR_BOUNDARY

NEAR_BOUNDARY does not enter either corridor. Its smallest positive clearance is the state clearance:

```text
0.000788975 m
```

That value is positive, above the `0.000001 m` geometry tolerance, and within the target near-boundary band.

## 14. OUTSIDE_BOTH

OUTSIDE_BOTH enters neither corridor. Its clearances are:

```text
planned clearance = 0.030868868 m
state clearance = 0.058035029 m
```

Its scores remain low relative to corridor conflicts, but they are not forced to zero.

## 15. Formula Recalculation

`scripts/evaluate_m3d_world_risk.py` recalculates each row using:

```text
spatial_score = exp(-max(clearance_m, 0) / sigma_distance_m)
temporal_score = exp(-relevant_time_s / tau_time_s)
risk_score = spatial_score * temporal_score
combined_risk = max(planned_risk, state_risk)
```

The recalculated scores match episode_0002 CSV values within tolerance.

## 16. Parameter Sensitivity

The finite sensitivity check uses all 9 combinations:

```text
sigma_distance_m in {0.025, 0.05, 0.10}
tau_time_s in {0.5, 1.0, 2.0}
```

For all 9 combinations:

- EARLY planned risk remains greater than LATE planned risk;
- ON_PLANNED_PATH remains planned-dominant;
- ON_STATE_PATH remains state-dominant;
- OUTSIDE_BOTH remains outside both corridors;
- all scores remain in `[0, 1]`.

Sensitivity outputs:

```text
results/m3_world_risk/parameter_sensitivity.csv
results/m3_world_risk/parameter_sensitivity.png
results/m3_world_risk/parameter_sensitivity_margins.png
```

The margin figure shows three positive ordering margins for each parameter pair: `EARLY planned risk - LATE planned risk`, `ON_PLANNED_PATH planned risk - state risk`, and `ON_STATE_PATH state risk - planned risk`. Positive margin means the required ordering passes.

This is a limited local sensitivity check, not a complete robustness proof.

## 17. Milestone 3 Acceptance

| criterion | status |
|---|---|
| M3A formulation frozen | PASS |
| M3B ordinary-Python risk core implemented | PASS |
| risk_map remains Webots-decoupled | PASS |
| M3C Webots static AABB validation completed | PASS |
| episode_0002 CSV validated | PASS |
| M3D formulas recalculated | PASS |
| M3D role acceptance | PASS |
| M3D figures generated | PASS |
| parameter sensitivity completed | PASS |
| GUI human acceptance | PENDING USER CONFIRMATION |

## 18. GUI Human Acceptance

GUI validation: pending user confirmation.

Manual checklist:

1. six obstacles are visible;
2. obstacles do not overlap;
3. robot start does not overlap obstacles;
4. no actual collision before `7.968 s`;
5. EARLY is near the earlier future path;
6. LATE is near the later future path;
7. ON_PLANNED and ON_STATE lie in their intended dominant regions;
8. NEAR is close to a corridor boundary;
9. OUTSIDE is outside both corridors;
10. Console has no red Traceback.

## 19. Known Limitations

- Static AABB obstacles only.
- World-coordinate risk only.
- No dynamic obstacle prediction.
- No camera projection.
- No image-space risk map.
- No ROI compression.
- No closed-loop navigation.
- No machine learning.
- One validation scene and one analysis snapshot.

## 20. Why Camera Projection Comes Next

Milestone 3 validates the world-coordinate risk layer first. Camera projection should only start after the world-coordinate geometry, timing, scoring, and role acceptance are documented and reproducible. This prevents image-space work from masking errors in the underlying risk computation.

## Generated Figure Paths

```text
results/m3_world_risk/world_risk_overview.png
results/m3_world_risk/planned_vs_state_risk.png
results/m3_world_risk/risk_decomposition_planned.png
results/m3_world_risk/risk_decomposition_state.png
results/m3_world_risk/early_vs_late_ttcf.png
results/m3_world_risk/early_vs_late_risk_decomposition.png
results/m3_world_risk/clearance_risk_curve.png
results/m3_world_risk/trajectory_disagreement_over_time.png
results/m3_world_risk/parameter_sensitivity.png
results/m3_world_risk/parameter_sensitivity_margins.png
```

These files are generated artifacts under `results/` and are not committed.

## Reproduction Commands

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_m3c_risk_dataset.py .\data\logs\m3\risk_validation_episode_0002.csv
.\.venv\Scripts\python.exe .\scripts\evaluate_m3d_world_risk.py
.\.venv\Scripts\python.exe .\scripts\plot_m3d_world_risk.py
.\.venv\Scripts\python.exe .\scripts\validate_m3d_report.py
```
