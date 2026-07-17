# Research protocol

## Title

**Trajectory-Conditioned Collision-Risk-Aware Visual Communication for Remote Robot Navigation**

中文：面向远程机器人导航的轨迹条件化碰撞风险感知视觉通信

## Research question

Under the same or closely matched communication budget, can trajectory- and collision-risk-driven visual resource allocation reduce safety-critical obstacle misses and collisions, and improve navigation success, compared with uniform compression, a fixed center ROI, and an object-only ROI?

## Phase 1 scope

Phase 1 is a research prototype using native Windows, Webots, Python, one differential-drive robot, a forward RGB camera, mostly static obstacles, simulator ground truth, a 1–2 second trajectory horizon, an explicit risk map, block-wise spatial compression, offline perception evaluation, and later a simple closed-loop navigation evaluation.

Out of scope: ROS 2, WSL as the development environment, human teleoperation, multiple robots, real radio/network implementation, reinforcement learning, VLA models, future-frame generation, event cameras, soft robots, real robot hardware, training a neural codec, and full H.265/VVC or physical-layer implementation.

Learning-based visual allocation will not start until interpretable geometry/rule methods show an initial positive result.

## Hypothesis

At the same image size or approximately matched bitrate, preserving high-risk regions near the robot's predicted future trajectory will retain safety-relevant obstacle information better than uniform compression, a fixed center ROI, or a high-quality ROI over every obstacle.

## System chain

Camera → Robot state and future trajectory → Collision risk map → Spatial visual resource allocation → Compressed observation → Remote perception → Navigation decision

## Inputs and outputs

Inputs: RGB frame, world pose and heading, linear and angular velocity, current command, predicted 1–2 second trajectory, obstacle ground-truth positions, and per-frame budget.

Outputs: predicted trajectory, robot-width-inflated trajectory corridor, obstacle risk scores, pixel/block risk map, images from each compression policy, byte count and encoding time, perception outputs, and navigation/safety logs.

## Initial risk formulation

Risk must consider distance to the predicted trajectory, distance to the robot, linear speed, turning direction, time-to-collision (TTC), and trajectory-corridor intersection.

Initial interpretable form:

`risk_i = trajectory_relevance_i × inverse_ttc_i × collision_cost_i`

The precise normalization, clipping, zero-velocity behavior, and risk aggregation remain to be specified before risk-map implementation.

## Comparators

- Baseline A — Uniform compression: one quality level for the whole image.
- Baseline B — Fixed center ROI: higher quality in a fixed central/forward region.
- Baseline C — Object ROI: higher quality for all obstacle regions without trajectory relevance.
- Proposed — Trajectory and collision-risk ROI: dynamic quality based on trajectory, distance, speed, and TTC.

Possible later additions: semantic ROI, learned spatial mask, no-TTC ablation, and no-trajectory ablation.

## Fair comparison

Target budgets: 5, 10, 20, and 40 KB/frame. Record actual bytes and budget mismatch. The proposed method must not receive a systematically larger budget. Phase 1 must be described as a **block-wise spatial compression prototype**, not a standards-compatible ROI video encoder.

## Metrics

- Communication: bytes/frame, estimated bitrate, compression ratio, encoding time.
- Conventional image quality: PSNR and SSIM.
- Task/safety: trajectory-critical obstacle recall, trajectory-corridor obstacle miss rate, risk-region IoU, navigation success rate, collision rate, near misses, completion time, path length, and emergency stops.

Conclusions must not rely on PSNR or SSIM alone.

## Initial scenarios

1. Straight motion with a small obstacle ahead.
2. Multiple obstacles, only one intersecting the future trajectory.
3. Left- and right-turn scenes.
4. Narrow doorway.
5. Constant-speed dynamic obstacle crossing the trajectory.

Phase 1 begins with scenarios 1–3.

