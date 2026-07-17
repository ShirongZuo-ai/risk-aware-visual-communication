# Trajectory Prediction Design

Last updated: 2026-07-17 (Asia/Shanghai)

## Scope

Milestone 2 defines short-horizon trajectory sources for the Phase 1 Webots/e-puck prototype. It does not implement obstacle risk, TTC, camera projection, ROI compression, object detection, closed-loop navigation, ROS 2, WSL, or machine learning.

## Trajectory Sources

### Planned command trajectory

A planned command trajectory is the future control plan that a controller or planner intends to execute. In this project it is represented as time-ordered command segments, each with start and end offsets and left/right wheel angular velocity commands.

Motors typically expose the command currently being executed, not the entire future plan. A controller, however, may know its own future schedule before commands are sent to the motors. That controller-side schedule can be passed explicitly into a predictor.

### State-only predicted trajectory

A state-only prediction uses only the current actual state:

- world position `x`, `y`
- heading `yaw_rad`
- actual ground-plane linear speed
- actual angular speed around the vertical axis

It extrapolates with a constant-twist model. It is a lowest-information baseline and must not read future commands or future ground truth.

### Command-conditioned nominal trajectory

A command-conditioned nominal trajectory starts from the current actual state and integrates a future command sequence. It can cross multiple future command segments, including stop commands. It is still nominal because simulated execution may differ from commanded wheel speeds because of dynamics, contact, numerical effects, or slip.

### Actual future trajectory

The actual future trajectory is what Webots produces after the current time. It is ground truth for offline evaluation only. It must not be used as an online prediction input; doing so would leak future information.

## Models

### State-only constant twist

For `abs(omega) < epsilon`, the model uses straight motion:

```text
x(t) = x0 + v*cos(yaw0)*t
y(t) = y0 + v*sin(yaw0)*t
yaw(t) = yaw0
```

Otherwise it uses circular-arc integration:

```text
x(t) = x0 + v/omega * (sin(yaw0 + omega*t) - sin(yaw0))
y(t) = y0 - v/omega * (cos(yaw0 + omega*t) - cos(yaw0))
yaw(t) = yaw0 + omega*t
```

All yaw outputs are normalized to `[-pi, pi]`.

### Command-conditioned differential drive

The predictor receives explicit future command segments. For each integration step, it selects the segment active at that time and converts wheel speeds to body twist:

```text
v = r/2 * (omega_right + omega_left)
angular_velocity = r/L * (omega_right - omega_left)
```

For Webots R2025a e-puck:

- wheel radius `r = 0.02 m`
- axle length `L = 0.052 m`

These values come from the official installed R2025a e-puck controller source, which defines `WHEEL_RADIUS 0.02` and `AXLE_LENGTH 0.052`.

## Coordinate Convention

The current Webots worlds use `x-y` as the ground plane and `z` as the vertical axis.

Yaw is the heading of the e-puck local `+x` forward axis around world `+z`, computed from the row-major Webots orientation matrix as:

```text
yaw = atan2(orientation[3], orientation[0])
```

Linear velocity is the actual ground-plane speed magnitude:

```text
sqrt(vx^2 + vy^2)
```

Angular velocity is the Webots world-frame angular velocity around `+z`, the sixth value returned by `Node.getVelocity()`.

## Uncertainty Corridor

The current model is not assumed to be exact. Prediction residuals against actual future trajectories are summarized into an empirical residual corridor:

```text
corridor_radius = robot_half_width + prediction_error_quantile + safety_margin
```

This is based on limited simulation data. It is not a rigorously calibrated confidence interval and does not specifically model sudden slip. Its purpose is to prevent downstream risk code from treating a nominal predicted trajectory as an exact line.

Future machine learning may be useful for residual correction or slip uncertainty estimation, but Milestone 2 intentionally uses interpretable physics-based models first.
