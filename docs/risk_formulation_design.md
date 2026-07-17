# World-Risk Formulation Design

Last updated: 2026-07-18 (Asia/Shanghai)

## Scope

Milestone 3A freezes the design, data structures, module boundaries, and acceptance criteria for world-coordinate trajectory-to-obstacle risk. Milestone 3B implements the ordinary-Python risk core from this design. Milestone 3C connects that core to a Webots validation world through an adapter layer and writes a world-coordinate risk CSV. These milestones do not create camera projection, image risk maps, ROI compression, navigation, or machine learning.

The design is intentionally limited to static, axis-aligned rectangular obstacle footprints in Webots world coordinates. All distances are meters, times are seconds, and angles are radians.

## Trajectory Sources

### Planned Trajectory

The planned trajectory is the Command-conditioned trajectory from Milestone 2. It represents the future motion the robot plans to execute from the current state using the known future wheel-command schedule.

### State Trajectory

The state trajectory is the State-only trajectory from Milestone 2. It represents the execution trend extrapolated from the current actual motion state only: current world position, yaw, actual ground-plane linear speed, and actual angular velocity.

### Actual Trajectory

The actual trajectory is the future Webots ground-truth trajectory. It is available only for offline evaluation. It must never be used as an online risk input, because that would leak future information.

### Why Planned and State Risk Stay Separate

Milestone 3 computes planned and state risk separately because they answer different questions:

- Planned risk asks what conflicts arise if the controller follows its known future command plan.
- State risk asks what conflicts arise if the robot continues its current actual motion trend.

The first version must not immediately average these trajectories. Averaging can hide a conflict that exists in only one source, especially during command transitions, slip, or actuation lag. Separate outputs also make later ablations possible: planned-only, state-only, max-union, and oracle actual-trajectory evaluation.

## Trajectory Occupancy Corridor

The corridor used by Milestone 3 is a safety-inflated occupancy corridor around a trajectory centerline. It includes:

- robot half width;
- empirical prediction residual;
- safety margin.

Use one of these terms:

- Trajectory Occupancy Corridor
- Safety-Inflated Trajectory Corridor

Do not call the whole corridor only "prediction uncertainty". Prediction uncertainty is one component of the corridor radius, not the full occupancy corridor.

The corridor radius is already inflated by robot half width. Milestone 3 must not add robot half width a second time.

## Obstacle Representation

The first implementation version supports only static, axis-aligned rectangular obstacles in world coordinates. Webots code may read simulator ground truth and convert it into this representation, but core geometry and risk code must not depend on Webots APIs.

### ObstacleFootprint

Proposed fields:

```text
obstacle_id: str
center_x: float
center_y: float
size_x: float
size_y: float
min_x: float
max_x: float
min_y: float
max_y: float
```

Rules:

- `size_x > 0`
- `size_y > 0`
- `min_x = center_x - size_x / 2`
- `max_x = center_x + size_x / 2`
- `min_y = center_y - size_y / 2`
- `max_y = center_y + size_y / 2`
- all length fields are meters;
- all values must be finite;
- obstacle IDs must be stable within one scene or evaluation episode.

## Geometry Definitions

### minimum_centerline_distance_m

`minimum_centerline_distance_m` is the shortest Euclidean distance from the obstacle rectangle boundary or interior to the trajectory centerline polyline.

This is not the obstacle-center-to-trajectory distance. Large obstacles whose edge enters the corridor must be detected even when their center remains outside.

If the trajectory centerline intersects the obstacle rectangle, the minimum centerline distance is `0`.

### minimum_clearance_m

```text
minimum_clearance_m = minimum_centerline_distance_m - corridor_radius_m
```

Interpretation:

- `minimum_clearance_m < 0`: the obstacle intersects the Trajectory Occupancy Corridor.
- `minimum_clearance_m = 0`: the obstacle is tangent to the corridor boundary, within numerical tolerance.
- `minimum_clearance_m > 0`: the obstacle remains outside the corridor.

`enters_corridor` must be consistent with this sign using a documented tolerance.

### closest_time_s

`closest_time_s` is the future time offset on the trajectory where the obstacle rectangle is closest to the trajectory centerline.

It must lie in `[0, horizon]`. For sampled trajectories, the implementation may estimate it from discrete trajectory points or segment interpolation, but it must document which approximation is used.

### first_corridor_entry_time_s

`first_corridor_entry_time_s` is the earliest future time offset at which the Trajectory Occupancy Corridor intersects the obstacle footprint.

If the obstacle never enters the corridor, this field is `None`.

### corridor_overlap_duration_s

`corridor_overlap_duration_s` is the estimated duration for which the Trajectory Occupancy Corridor intersects the obstacle footprint over the prediction horizon.

For the first implementation, this may be estimated from discrete prediction points or time segments. It must be non-negative. If the obstacle never enters the corridor, it is `0`.

## Time-to-Conflict Terminology

Do not call every time quantity Time-to-Collision.

The first version uses:

```text
Time-to-Conflict = TTCf
```

Definition:

`TTCf` is the first future time at which the obstacle enters the Trajectory Occupancy Corridor.

Mapping:

- If `enters_corridor` is true, `TTCf = first_corridor_entry_time_s`.
- If the obstacle never enters the corridor, `TTCf = None`.
- `closest_time_s` may still be reported for non-entering obstacles.
- Do not invent a collision time for non-entering obstacles.

`TTCf` is a geometric conflict proxy. It is not a true rigid-body collision time.

## Interpretable Risk Scores

The first risk formulation is an interpretable heuristic proxy, not a collision probability.

### Parameters

```text
corridor_radius_m: meters
sigma_distance_m: meters
tau_time_s: seconds
maximum_horizon_s: seconds
```

Parameter rules:

- `corridor_radius_m > 0`
- `sigma_distance_m > 0`
- `tau_time_s > 0`
- `maximum_horizon_s > 0`
- all values must be finite.

### spatial_score

```text
spatial_score = exp(-max(minimum_clearance_m, 0) / sigma_distance_m)
```

If `minimum_clearance_m <= 0`, `spatial_score = 1`. Larger positive clearance must not increase spatial score.

### temporal_score

```text
temporal_score = exp(-relevant_time_s / tau_time_s)
```

`relevant_time_s` is:

- `first_corridor_entry_time_s` if the obstacle enters the corridor;
- otherwise `closest_time_s`.

Earlier conflicts or closest approaches produce higher temporal score.

### risk_score

```text
risk_score = spatial_score * temporal_score
```

Rules:

- `risk_score` is in `[0, 1]`.
- It is an interpretable heuristic risk proxy.
- It is not a probability.
- Do not add unsupported complex weights in the first version.

## Dual-Trajectory Risk

Planned and state trajectories produce independent obstacle-level results.

Required output fields:

```text
planned_clearance
planned_ttc_f
planned_risk
state_clearance
state_ttc_f
state_risk
```

The first combined-risk definition is:

```text
combined_risk = max(planned_risk, state_risk)
```

This max-union rule is transparent and preserves conflicts that appear in only one trajectory source.

### trajectory_disagreement_m

`trajectory_disagreement_m` is the maximum Euclidean distance between planned and state trajectory points at matching time offsets.

If sampling times are not identical, the implementation must match or interpolate by time offset. It must not blindly compare list indices.

## Proposed Data Structures

These data structures are frozen as interface targets. Milestone 3A does not implement them.

### TrajectoryPoint

Existing source: `navigation.trajectory_prediction.TrajectoryPoint`.

```text
time_offset_s: float
x: float
y: float
yaw_rad: float
```

No fields may be `None`.

### ObstacleFootprint

```text
obstacle_id: str
center_x: float
center_y: float
size_x: float
size_y: float
min_x: float
max_x: float
min_y: float
max_y: float
```

No fields may be `None`. Invalid sizes, NaN, or infinity must raise an error.

### RiskParameters

```text
corridor_radius_m: float
sigma_distance_m: float
tau_time_s: float
maximum_horizon_s: float
```

No fields may be `None`. Invalid non-positive, NaN, or infinity values must raise an error.

### TrajectoryConflictResult

```text
obstacle_id: str
trajectory_source: str
minimum_centerline_distance_m: float
minimum_clearance_m: float
closest_time_s: float
enters_corridor: bool
first_corridor_entry_time_s: float | None
corridor_overlap_duration_s: float
spatial_score: float
temporal_score: float
risk_score: float
```

`first_corridor_entry_time_s` is `None` only when `enters_corridor` is false. All other fields must be present. `trajectory_source` must be a constrained value such as `planned` or `state`.

### DualTrajectoryRiskResult

```text
obstacle_id: str
planned_result: TrajectoryConflictResult
state_result: TrajectoryConflictResult
trajectory_disagreement_m: float
combined_risk_score: float
```

No fields may be `None`.

## Frozen Module Boundaries

The following files are the implemented Milestone 3B module boundaries.

### risk_map/models.py

Responsibilities:

- dataclasses;
- enums;
- parameter validation;
- shared data models.

It must not contain Webots reads, plotting, camera projection, or experiment orchestration.

### risk_map/geometry.py

Responsibilities:

- point-to-segment distance;
- segment-to-AABB distance;
- polyline-to-AABB distance;
- corridor intersection;
- closest point and closest time;
- first entry time;
- overlap duration support.

It must contain geometry only, with no business weights or Webots dependencies.

### risk_map/trajectory_obstacle_risk.py

Responsibilities:

- analyze one trajectory against one obstacle footprint;
- produce `TrajectoryConflictResult`;
- call geometry and risk formulation helpers.

It must not read from Webots and must not perform camera projection.

### risk_map/risk_formulation.py

Responsibilities:

- spatial score;
- temporal score;
- planned/state combined risk;
- parameter validation.

It must not implement geometric distance details.

## Milestone 3B Implementation Notes

The implementation is Webots-decoupled and uses only the Python standard library plus the existing `navigation.trajectory_prediction.TrajectoryPoint` dataclass.

Implemented public APIs:

```text
risk_map.models.TrajectorySource
risk_map.models.ObstacleFootprint
risk_map.models.RiskParameters
risk_map.models.TrajectoryConflictResult
risk_map.models.DualTrajectoryRiskResult
risk_map.geometry.point_to_segment_distance(...)
risk_map.geometry.point_to_aabb_distance(...)
risk_map.geometry.segment_to_aabb_distance(...)
risk_map.geometry.polyline_to_aabb_closest(...)
risk_map.geometry.corridor_intervals_for_trajectory(...)
risk_map.geometry.summarize_corridor_intervals(...)
risk_map.risk_formulation.spatial_score(...)
risk_map.risk_formulation.temporal_score(...)
risk_map.risk_formulation.compute_risk_score(...)
risk_map.risk_formulation.combine_risk_scores(...)
risk_map.trajectory_obstacle_risk.analyze_trajectory_obstacle(...)
risk_map.trajectory_obstacle_risk.analyze_dual_trajectory_obstacle(...)
risk_map.trajectory_obstacle_risk.compute_trajectory_disagreement(...)
```

Geometry approximation choices:

- sampled trajectories are treated as polylines;
- closest time is linearly interpolated within the closest segment;
- corridor entry is computed by intersecting each segment against the obstacle AABB inflated by `corridor_radius_m`;
- multiple corridor intervals are merged before overlap duration is summed;
- tangent and near-boundary cases use `RiskParameters.geometry_tolerance_m`;
- zero-length trajectory segments are valid and are handled as point-to-AABB checks;
- trajectory disagreement is computed at the union of available planned/state sample times within the common time range, using linear interpolation.

Dependency rule:

- `risk_map` must not import Webots, controller APIs, camera APIs, NumPy, SciPy, Shapely, OpenCV, ROS, or machine-learning libraries.

Milestone 3C consistency note:

- `enters_corridor` is defined by the Euclidean clearance sign: `minimum_clearance_m <= geometry_tolerance_m`.
- Segment/AABB interval estimation is used to estimate `first_corridor_entry_time_s` and `corridor_overlap_duration_s` after the clearance test establishes corridor entry.
- This avoids treating the square inflated-AABB approximation as a substitute for the frozen Euclidean clearance definition.

## Milestone 3C Webots Adapter

The Webots adapter lives outside `risk_map` in `simulator/adapters/webots_obstacle_adapter.py`.

Mapping:

- `Supervisor.getFromDef(def_name)` locates each fixed obstacle.
- `Solid.translation[0]` and `[1]` map to `ObstacleFootprint.center_x` and `center_y`.
- `Shape.geometry Box.size[0]` and `[1]` map to `size_x` and `size_y`.
- `Solid.rotation` must have zero planar rotation.
- Appearance, color, and label text are ignored.

The first adapter is deliberately limited to the fixed M3C world structure: one `Shape` child with `Box` geometry under each static `Solid`.

Milestone 3C validation parameters:

```text
analysis_time_s = 7.968
prediction_horizon_s = 2.0
prediction_step_s = 0.032
corridor_radius_m = 0.037592257
sigma_distance_m = 0.05
tau_time_s = 1.0
geometry_tolerance_m = 0.000001
```

## Milestone 3D Diagnostics

Milestone 3D uses the accepted `risk_validation_episode_0002.csv` only. It rebuilds planned and State-only trajectories from the analysis snapshot and known command schedule, then regenerates:

- world-coordinate overview with full trajectory occupancy corridors;
- planned/state/combined risk comparison;
- planned and state risk decomposition;
- EARLY vs LATE timing comparison;
- clearance-to-spatial-score curve;
- planned/state disagreement over time;
- 9-combination sensitivity check over `sigma_distance_m` and `tau_time_s`.

The diagnostics do not change formal risk parameters, obstacle positions, or risk formulas. They do not perform camera projection, image-space risk mapping, ROI compression, or navigation.

## Milestone 3 Validation Scenario Roles

These roles define future validation requirements. Milestone 3A does not assign fixed world coordinates. Coordinates must be chosen later after visualizing the actual M3 trajectories.

### EARLY_CONFLICT

- Geometry: obstacle enters a Trajectory Occupancy Corridor early in the horizon.
- Expected risk: high spatial score and higher temporal score than a late conflict with similar clearance.
- Validates: first entry time and temporal monotonicity.
- Ordering: `EARLY_CONFLICT risk > LATE_CONFLICT risk` when spatial conditions are comparable.

### LATE_CONFLICT

- Geometry: obstacle enters a Trajectory Occupancy Corridor later in the horizon.
- Expected risk: conflict risk is present but lower than early conflict under similar clearance.
- Validates: temporal decay.
- Ordering: lower than `EARLY_CONFLICT` with comparable clearance.

### ON_PLANNED_PATH

- Geometry: obstacle intersects or nearly intersects the planned trajectory corridor and not the state corridor.
- Expected risk: planned risk is high; state risk may be lower.
- Validates: planned/state separation.
- Ordering: `ON_PLANNED_PATH planned risk > OUTSIDE_BOTH planned risk`.

### ON_STATE_PATH

- Geometry: obstacle intersects or nearly intersects the state trajectory corridor and not the planned corridor.
- Expected risk: state risk is high; planned risk may be lower.
- Validates: planned/state separation during disagreement.
- Ordering: `ON_STATE_PATH state risk > OUTSIDE_BOTH state risk`.

### NEAR_BOUNDARY

- Geometry: obstacle is tangent to, or within tolerance of, a corridor boundary.
- Expected risk: clearance is near zero and `enters_corridor` follows the documented tolerance.
- Validates: tangent handling and clearance sign consistency.
- Ordering: should sit near the threshold between entering and non-entering cases.

### OUTSIDE_BOTH

- Geometry: obstacle remains outside both planned and state corridors for the full horizon.
- Expected risk: no corridor entry, `TTCf = None`, closest time still reported.
- Validates: non-entry handling and no fabricated collision time.
- Ordering: lower risk than planned/state path conflicts.

## Acceptance Criteria

### Geometry Correctness

- Use obstacle boundaries, not only obstacle centers.
- Large obstacles whose edge enters the corridor must be identified.
- `minimum_clearance_m` sign and `enters_corridor` must be consistent within tolerance.
- Tangent cases must use a documented numerical tolerance.
- Zero-length trajectory segments must be handled.
- Invalid obstacle sizes must raise clear errors.

### Time Correctness

- `closest_time_s` lies in `[0, horizon]`.
- First entry time is not earlier than `0`.
- First entry time is not later than the horizon.
- Non-entering obstacles use `first_corridor_entry_time_s = None`.
- Multiple entries return the first entry.
- `corridor_overlap_duration_s` is non-negative.

### Risk Monotonicity

- Larger positive clearance must not increase `spatial_score`.
- Earlier relevant time must produce higher `temporal_score`.
- Under equal spatial conditions, earlier conflict must produce higher `risk_score`.
- All risk scores must be in `[0, 1]`.
- Risk must not be described as a probability.

### Dual-Trajectory Correctness

- Planned and state results are computed separately.
- Combined risk follows the frozen `max(planned_risk, state_risk)` definition.
- `trajectory_disagreement_m` is computed by matching or interpolating time offsets.
- Future actual trajectory is not read as an online input.

### Engineering Correctness

- Core modules run in ordinary Python.
- Core modules do not depend on Webots.
- Core modules do not depend on camera APIs.
- Core modules do not depend on ROS 2.
- Core modules do not use machine learning.
- Units are meters, seconds, and radians.

## Unit Test Plan

Milestone 3B should implement tests covering at least:

1. point on segment;
2. point outside segment endpoint;
3. horizontal segment;
4. vertical segment;
5. zero-length segment;
6. trajectory passing through rectangle;
7. trajectory passing beside rectangle;
8. tangent rectangle/corridor case;
9. rectangle center outside corridor while edge enters corridor;
10. first entry time;
11. closest approach time;
12. multiple entries returning the first;
13. never entering the corridor;
14. clearance monotonicity;
15. temporal monotonicity;
16. risk score range;
17. planned/state result separation;
18. combined max definition;
19. trajectory disagreement by time matching or interpolation;
20. invalid `sigma_distance_m`, `tau_time_s`, obstacle size, and NaN inputs.

## Current Limitations

- Static obstacles only.
- Axis-aligned rectangular obstacle footprints only.
- World-coordinate simulator ground truth only.
- No dynamic target prediction.
- No camera projection.
- No real collision dynamics.
- No slip-specific model.
- Risk is not a probability.
- No machine learning.
