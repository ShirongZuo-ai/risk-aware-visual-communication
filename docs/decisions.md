# Decision log

## 2026-07-21 - M6-A v2 preflight and attempt separation

- **Decision:** Keep prepared files in a preflight workspace and record the pilot location solely as a prospective attempt root.
- **Reason:** A preflight workspace may exist before authorization; an attempt root and ownership record must not. The explicit B2-to-materialization boundary preserves that distinction and reuses the existing ownership primitive.
- **Impact:** B1.1 wrapper execution must accept only an owned context produced after B2 validation; it must not treat a preflight marker or generic dictionary as execution authority.

## 2026-07-21 - M6-A v2 aggregate and joint completion evidence

- **Decision:** Make canonical B5 case entries the aggregate's authority and persist separate reloadable aggregate-validation and joint-validation reports.
- **Reason:** A declared case count cannot prove the frozen 4 × 2 × 4 matrix. Reconstructing identities and totals from case entries, then binding their validation to the runtime manifest, prevents completion from treating unverified in-memory dictionaries as evidence.
- **Impact:** Completion returns success only after aggregate and joint reports are persisted and reloaded. The final marker and any authorization/ownership workflow remain deliberately outside this change.

## 2026-07-21 - M6-A v2 runtime artifact integrity contract

- **Decision:** Extend the existing runtime-evidence manifest with canonical per-file serialization-tree evidence, rather than inventing a second snapshot serialization manifest.
- **Reason:** The existing trusted snapshot loader is the authoritative definition of allowed root and method files. Reusing it while recording sorted relative file entries, sizes, and SHA-256 values provides reloadable integrity evidence without duplicate schema logic.
- **Impact:** A successful runtime lifecycle persists its manifest only after summary, status, and diagnostic evidence, then immediately reloads every artifact. This is temporary-fixture coverage only and does not authorize a Webots execution.

## 2026-07-20 - M6-A independent byte-fair preparation

- **Decision:** Freeze M6-A v1 with new deterministic episode-disjoint calibration/formal/pilot identities, State-only versus Command-conditioned Risk ROI, the existing four complete-container targets, and a 2.0 s primary horizon.
- **Reason:** This is the smallest reproducible direct test of decision-time command information without retuning M5 or using actual-future leakage.
- **Gate:** A Webots pilot must pass before any formal execution; the current codec-only smoke is not scientific evidence.

## 2026-07-17 — Phase 1 scope and implementation strategy

- **Decision:** Start with a native-Windows Webots/Python research prototype using simulator ground truth and interpretable geometric risk.
- **Reason:** It isolates the research hypothesis with low infrastructure cost and makes the risk mechanism auditable.
- **Rejected for now:** ROS 2, WSL, real networking/hardware, reinforcement learning, VLA models, learned codecs, and full video-codec integration.
- **Impact:** Milestone 1 is limited to synchronized camera/state capture; no risk or compression code is permitted yet.

## 2026-07-17 — Communication comparison policy

- **Decision:** Initial rough candidate budgets were 5, 10, 20, and 40 KB/frame. This early choice is superseded by the Milestone 5A budget-selection protocol.
- **Reason:** Resource allocation cannot be credited for gains obtained by sending more data, and the actual feasible budget range must be measured from the tiled-JPEG container and source frames.
- **Rejected:** Comparing methods only at nominal quality settings or unequal byte counts.
- **Impact:** Every later evaluation must log actual bytes and budget mismatch. Milestone 5B must run a Uniform JPEG pilot before selecting final budgets.

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

## 2026-07-17 — Milestone 2 trajectory sources

- **Decision:** Implement State-only as the lowest-information baseline and Command-conditioned as the first main trajectory source.
- **Reason:** State-only tests how far current state extrapolation can go, while Command-conditioned uses the controller's explicit future command plan without reading future ground truth.
- **Actual future trajectory policy:** Actual Webots future trajectory is used only for offline evaluation of prediction error and never as online predictor input.
- **e-puck geometry:** Use official Webots R2025a e-puck values from `projects/robots/gctronic/e-puck/controllers/e-puck/e-puck.c`: wheel radius `0.02 m`, axle length `0.052 m`. The official controller computes orientation change as `(dr - dl) / AXLE_LENGTH`, matching `angular_velocity = r / L * (omega_right - omega_left)`.
- **Uncertainty corridor:** Use empirical residual quantiles from finite simulation data for the first corridor. The default corridor radius is `robot_half_width + 90% position-error quantile + 0.01 m safety margin`.
- **Rejected for now:** Machine learning trajectory prediction, LSTM/Transformer models, slip-specific modeling, and treating planned commands as guaranteed actual motion.
- **Future direction:** Machine learning may later be used for physics residual correction and slip uncertainty estimation, not as a replacement before interpretable baselines are measured.

## 2026-07-17 - Milestone 2R transition guard and arc validation

- **Decision:** Preserve `trajectory_validation_episode_0001` as the in-place rotation validation episode and add a separate forward-arc validation episode, `trajectory_validation_episode_0002`.
- **Reason:** The original episode is useful for command-transition yaw stress testing, but it does not validate forward curved motion because its turn phases rotate in place with near-zero linear velocity.
- **Decision:** Mark prediction windows intersecting `[command_switch + 0.10 s, command_switch + 0.20 s]` as transition, and allow stable labels only after `command_switch + 0.20 s`.
- **Reason:** This prevents frames immediately after a command switch, before actuator/state response has settled, from being counted as stable.
- **Decision:** Render the empirical uncertainty corridor as a union of disks along the predicted trajectory.
- **Reason:** Downstream risk modules need a band around the path, not a single uncertainty circle at the starting pose.
- **Rejected for now:** Merging the in-place and arc episodes into one CSV, overwriting original Milestone 2 figures, adding obstacle risk/TTC/risk maps, or introducing learned trajectory models.
- **Impact:** Milestone 2 evaluation now supports named profiles (`in_place` and `arc`), with arc-only outputs under `results/m2_trajectory_arc/`.

## 2026-07-18 - Milestone 3A world-risk formulation

- **Decision:** Use Time-to-Conflict (`TTCf`) for the first obstacle-risk timing term instead of broad Time-to-Collision wording.
- **Reason:** The current model detects geometric entry into a safety-inflated trajectory corridor, not a true rigid-body collision event.
- **Decision:** Measure obstacle risk from the obstacle footprint boundary/interior to the trajectory centerline, not from obstacle center alone.
- **Reason:** Large obstacles can intersect a trajectory corridor even when their center remains outside.
- **Decision:** Compute planned and state trajectory risks independently, then combine the first version with `max(planned_risk, state_risk)`.
- **Reason:** Planned and state trajectories represent different evidence sources; max-union preserves conflicts that appear in either source without hiding them by averaging.
- **Decision:** Treat risk as an interpretable heuristic proxy in `[0, 1]`, not as a probability.
- **Reason:** The first version is not calibrated against collision statistics and uses transparent distance/time decay terms.
- **Decision:** Limit the first world-risk version to static, axis-aligned rectangular obstacle footprints in world coordinates.
- **Reason:** This keeps Milestone 3B geometry testable without Webots, camera projection, dynamic obstacle prediction, or learned models.
- **Rejected for now:** Dynamic obstacle prediction, camera projection, image risk maps, TTC as rigid-body collision time, non-AABB obstacles, machine learning, and unvalidated weighted risk terms.
- **Impact:** Milestone 3B must implement the frozen interfaces and acceptance criteria from `docs/risk_formulation_design.md` before Webots validation or visualization work.

## 2026-07-18 - Milestone 3C Webots validation snapshot

- **Decision:** Use a single Webots analysis snapshot at `analysis_time_s = 7.968 s`, one 32 ms step before the 8.000 s command switch from forward-left arc to forward-right arc.
- **Reason:** At that instant, State-only continues the measured forward-left arc, while Command-conditioned uses the known future command schedule and turns right within the 2 s horizon. This produces a clear planned/state trajectory disagreement without reading future actual motion.
- **Decision:** Use fixed unrotated Webots `Solid` + `Shape` + `Box` obstacles and convert them to `ObstacleFootprint` through a simulator adapter outside `risk_map`.
- **Reason:** This validates the frozen world-coordinate risk interface against simulator ground truth while keeping `risk_map` independent of Webots.
- **Decision:** Use one shared validation parameter set for all six obstacles and both trajectories: `corridor_radius_m = 0.037592257`, `sigma_distance_m = 0.05`, `tau_time_s = 1.0`, `maximum_horizon_s = 2.0`, and `geometry_tolerance_m = 0.000001`.
- **Rejected for now:** Dynamic obstacles, camera projection, image risk heatmaps, ROI compression, formal Milestone 3D plots, and per-obstacle risk-parameter tuning.
- **Impact:** Milestone 3C produces a 6-row world-coordinate CSV and automatic validator only. Later Milestone 3D should use this accepted CSV for diagnostics before any image-space risk work.

## 2026-07-18 - Milestone 4A image-risk projection design

- **Decision:** Project full static 3D obstacle Boxes into image polygons, not only obstacle centers and not only raw min/max corner bounding boxes.
- **Reason:** Center projection loses object extent, and raw corner min/max fails around near-plane intersections and can over-cover pixels that are not part of the projected support.
- **Decision:** Keep planned, state, and combined image-risk masks as separate channels.
- **Reason:** Planned and state risk remain distinct evidence sources from Milestone 3. Channel separation preserves interpretability and later ablations.
- **Decision:** Use `max` for overlapping obstacle mask values, not `sum`.
- **Reason:** Milestone 3 combined risk uses max-union semantics, and max keeps image-risk values in `[0, 1]` without double-counting overlap.
- **Decision:** First-version visibility is geometric frustum and image-boundary visibility only; it does not claim true inter-object occlusion handling.
- **Reason:** The current accepted M3 evidence has no depth, segmentation, recognition mask, or z-buffer validation for real rendered visibility.
- **Decision:** The first Risk ROI is based on projected risky obstacle visual regions, not a filled projection of the empty trajectory corridor.
- **Reason:** The communication target should preserve pixels containing safety-relevant obstacles, not mark empty ground as high risk merely because a future corridor crosses it.
- **Decision:** The world-to-camera-to-project-optical coordinate transform must be explicit, including a fixed Webots device-frame to project-optical-frame axis transform.
- **Reason:** Webots Camera coordinates and image pixel coordinates are not identical to the project optical frame; implicit conventions would risk left/right or up/down mirroring errors.
- **Decision:** Do not guess the e-puck Camera convention from generic camera habits. Use the R2025a official e-puck PROTO, Webots Camera API, current project worlds, and later overlay validation.
- **Reason:** The current e-puck Camera has version-locked fields and a specific mount position. M4B/M4C must validate the frozen convention against actual Webots output.
- **Decision:** Keep the projection core standard-library first; allow Pillow later for image IO/masks if needed, defer OpenCV until automatic validation requires it, and do not add Shapely or ML frameworks.
- **Reason:** This preserves M3's auditable ordinary-Python style while avoiding unreliable custom image encoders when image files become necessary.
- **Rejected for now:** Camera projection implementation in 4A, M4 Webots scenes/controllers, mask artifacts, JPEG/H.264/ROI compression, network simulation, true occlusion claims, Shapely, and machine learning.
- **Impact:** Milestone 4B should implement the pure projection core from `docs/image_risk_projection_design.md`; Webots API access belongs only in a later adapter layer.

## 2026-07-18 - Milestone 4C Webots e-puck Camera axis calibration

- **Decision:** For the Webots R2025a e-puck Camera adapter, map Camera node/device coordinates to the project optical frame with `x_optical=-y_device`, `y_optical=-z_device`, and `z_optical=x_device`.
- **Reason:** Actual M4C Webots RGB validation showed that Boxes in front of the e-puck camera are seen when they lie along local `+x_device`, LEFT/RIGHT are correctly separated by the sign of local `y_device`, and vertical image direction matches local `z_device`. The earlier Milestone 4A initial assumption `diag(1,-1,-1)` made all front Boxes project outside the frustum in `episode_0001`.
- **Rejected:** Keeping the initial `diag(1,-1,-1)` e-puck adapter mapping despite failed Webots evidence, or changing the generic pure-Python projection core to hard-code Webots-specific axes.
- **Impact:** `perception` remains Webots-decoupled and accepts explicit extrinsics. The Webots adapter supplies the calibrated `R_device_to_optical` matrix for the R2025a e-puck Camera. M4C accepted automatic evidence starts from `projection_validation_episode_0003`; earlier M4C episodes are calibration/debug artifacts.

## 2026-07-18 - Milestone 5A compression and fair-bitrate protocol

- **Decision:** Use a tiled-JPEG spatial allocation prototype for the first compression experiment.
- **Reason:** It is simple, auditable, deterministic, and sufficient to test whether spatial resource allocation favors risk-relevant image regions under equal transmitted bytes.
- **Rejected for now:** Standards-compatible JPEG ROI coding, H.264/H.265/VVC/AV1 QP maps, neural codecs, temporal video coding, network simulation, remote perception, and closed-loop navigation.
- **Decision:** Use a `160x120` frame split into `20x20` tiles, giving 8 columns, 6 rows, and 48 row-major tiles.
- **Reason:** This exactly covers the accepted e-puck Camera frame without overlap or gaps and keeps per-tile accounting inspectable.
- **Decision:** Compare Uniform, Center ROI, Object ROI, and Risk ROI using the same encoder, deterministic container, decoder, tile grid, JPEG settings, and budget matcher.
- **Reason:** Fair comparison requires that Risk ROI can only differ in tile scoring, not in byte accounting or codec machinery.
- **Decision:** Match methods by actual total transmitted bytes, including container overhead and all transmitted metadata, and never select over-budget candidates.
- **Reason:** Nominal quality settings are not a fair communication budget because JPEG payloads vary by image content and ROI selection.
- **Decision:** Select numeric budgets only after a Milestone 5B Uniform JPEG pilot; the old 5/10/20/40 KB values are not frozen defaults.
- **Reason:** The feasible range depends on tiled payload sizes, container overhead, and actual source-frame complexity.
- **Decision:** Risk ROI tile scores use `max` combined image risk inside each tile for the first version.
- **Reason:** A maximum preserves small high-risk objects that would be diluted by mean risk over a `20x20` tile.
- **Decision:** Treat risk-weighted quality as an image-quality diagnostic over the accepted heuristic combined mask, not as collision probability, perception accuracy, or navigation safety.
- **Impact:** Milestone 5B may implement the shared codec backend and pilot, but no compression implementation belongs in Milestone 5A. Later claims remain limited until separately validated.

## 2026-07-18 - Milestone 5B tiled-JPEG backend

- **Decision:** Add `Pillow==12.3.0` as the explicit JPEG backend dependency for the first tiled-JPEG prototype.
- **Reason:** The current project environment already validates Pillow `12.3.0`, and using the installed version makes M5B payload and budget evidence reproducible on this machine.
- **Decision:** Use Pillow JPEG settings `format="JPEG"`, `quality=1..95`, `progressive=False`, `optimize=False`, and `subsampling=0`.
- **Reason:** Explicit settings avoid hidden Pillow defaults. `subsampling=0` preserves color edges in `20x20` tiles and is shared by every later baseline using this backend.
- **Decision:** Do not transmit tile quality values in the M5B container.
- **Reason:** JPEG payloads contain the tables required for decode, and quality values are experiment diagnostics rather than receiver-required payload.
- **Decision:** Use a strict big-endian binary container with magic `RAVCJT1`, version `1`, a 23-byte header, 48 six-byte tile index entries, and concatenated row-major JPEG payloads.
- **Reason:** This makes actual-byte accounting deterministic and includes only decode-required information.
- **Decision:** M5B Uniform budget matching exhaustively enumerates qualities 1 through 95 and chooses the largest legal actual container payload under the target, using higher quality as the tie-break.
- **Reason:** JPEG payload bytes are content-dependent and need not be strictly monotonic; exhaustive search avoids invalid binary-search assumptions.
- **Decision:** Development budgets for the accepted M4D frame are selected from actual Uniform container bytes at qualities 5, 25, 50, and 80.
- **Reason:** These produce four distinct under-budget matched qualities on the accepted development frame while remaining tied to measured payloads rather than intuition.
- **Impact:** Center/Object/Risk ROI allocation in Milestone 5C must reuse the same tile grid, JPEG settings, container, and budget matcher. Bit-exact payload stability is only claimed within the same Pillow/libjpeg environment; other environments must rerun the pilot and matcher.

## 2026-07-18 - Milestone 5C shared spatial allocation completion

- **Decision:** Resolve the M5A numeric allocation ambiguity with one shared exhaustive candidate space: background quality `1..94`, enhancement quality `2..95` constrained by `enhancement_quality > background_quality`, and top-k enhanced tiles `1..48`. If every score is equal, use a Uniform-quality candidate path rather than assigning an arbitrary ROI.
- **Reason:** M5A froze the allocation family and fairness rule but intentionally left numeric ranges to the implementation phase. The chosen range covers the full M5B JPEG quality domain while retaining a genuine high-versus-background split. The equal-score behavior preserves stable semantics.
- **Decision:** Center ROI uses tile-center Gaussian scores around the accepted M4D principal point (`79.5`, `59.5`) with normalized `sigma=0.5`; normalized offsets divide by the frame half-width and half-height.
- **Reason:** This supplies the protocol's unspecified Center parameter without following obstacles, risk, RGB content, robot turn direction, or later evaluation results, and preserves left/right and top/bottom symmetry on the frozen grid.
- **Decision:** Object ROI uses the maximum exact clipped-polygon coverage fraction per tile over `fully_visible`, `partially_visible`, and `intersects_near_plane` projections. Risk ROI uses the maximum accepted combined floating-point mask value in each tile.
- **Reason:** These are the M5A baseline definitions and maintain method isolation: Object does not read risk values; Risk does not read RGB, labels, or future actual trajectory.
- **Impact:** All non-Uniform methods share cache, JPEG settings, binary container, actual-byte objective, and tie-break: maximum legal actual bytes, then higher enhancement quality, higher background quality, smaller top-k, and lexicographic configuration. M5C proves allocation/fairness mechanics only, not image-quality, perception, navigation, or communication benefit.

## 2026-07-18 - Milestone 5D single-frame quality evaluation

- **Decision:** Define the M5D high-risk image region as the accepted continuous combined float mask satisfying `combined_risk >= 0.20`; retain the continuous, unthresholded combined mask for the primary risk-weighted MSE and PSNR.
- **Reason:** The M4D risk scale is a bounded heuristic proxy, and `0.20` yields a fixed, explicit diagnostic subset without discarding the continuous weighting used by the primary risk-weighted metric. The threshold is specified before reading M5D quality results and applies identically to all four fixed M5C allocations.
- **Decision:** Use `scikit-image==0.26.0` only in the M5D evaluator for the frozen RGB SSIM call (`data_range=255`, `channel_axis=-1`, Gaussian weights, `sigma=1.5`, population covariance, `win_size=11`), alongside `numpy==2.4.6` for numeric evaluation.
- **Reason:** These dependencies provide the protocol-defined, deterministic full-image quality metric without changing the codec, allocation matcher, container, risk model, Webots adapter, or M4 evidence. `imageio` is an indirect wheel dependency of scikit-image in this environment; it is neither imported by project code nor listed as a direct project requirement.
- **Impact:** M5D reports descriptive quality values for one accepted 160x120 M4D frame and its pre-existing 16 M5C fixed allocations. It does not retune allocation from quality metrics and must not be interpreted as a claim of collision probability, general method superiority, perception benefit, navigation benefit, or statistical significance.

## 2026-07-18 - Milestone 5E-A multi-scene protocol freeze

- **Decision:** Exclude `image_risk_validation_episode_0001` from M5E and separate development, calibration, and formal evidence by split, seed, episode, frame, and path. Use 64 calibration frames and 256 formal frames across eight equally weighted static-AABB scenario families.
- **Reason:** The accepted frame has already informed M4D-M5D development and cannot provide independent evidence. Balanced, disjoint scenario episodes reduce selection bias while remaining practical on the current machine.
- **Decision:** Select four M5E budgets only from the calibration-wide common feasible complete-container-byte interval, using fixed 5%, 25%, 50%, and 80% interval positions plus pre-registered adequacy checks. Formal evaluation may not recalibrate budgets.
- **Reason:** Single-frame M5B targets do not guarantee feasibility across different image content. A common interval and method-identical targets preserve actual-byte fairness without using formal outcomes.
- **Decision:** Select four snapshots at fixed reference-motion progress `0.20`, `0.45`, `0.70`, and `0.90`; invalidate and replace an entire episode when a required snapshot or scenario condition fails.
- **Reason:** Deterministic, method-independent triggers prevent post-hoc selection. Whole-episode replacement preserves paired comparisons and within-episode correlation.
- **Decision:** Use episode-level paired differences and a 10,000-replicate, seed-`20260718`, scenario-stratified bootstrap. Equal-weight the eight scenario means in overall estimates.
- **Reason:** Four snapshots in one episode are correlated and must not be treated as independent samples. Stratification prevents a single scenario from dominating the overall estimate.
- **Impact:** Center/Object/Risk scoring, M5C allocation, `HIGH_RISK_THRESHOLD=0.20`, M5D metrics, JPEG/container settings, and risk/projection definitions are frozen. Engineering acceptance is independent of Risk ROI performance. The next task is M5E-B generator implementation; no M5E data exist yet.

## 2026-07-18 - Milestone 5E-B deterministic dataset generator

- **Decision:** Use one parameterized Webots world/controller that imports static, unrotated AABB Box nodes from an immutable per-episode `ScenarioConfig`.
- **Reason:** A shared generator reduces scene drift while retaining exact scenario IDs, roles, seeds, geometry, command schedules, and hashes in saved evidence.
- **Decision:** Capture the first Webots step at or after reference-motion progress `0.20`, `0.45`, `0.70`, and `0.90`, and validate against tolerance `0.006`.
- **Reason:** This implements the frozen M5E-A result-independent snapshot rule without selecting frames from risk or image-quality outcomes.
- **Decision:** Calibrate S5 with a bounded deterministic geometry sweep using only snapshot-time planned/state trajectories and Camera geometry, then write the selected schedule and AABBs back into the static scenario definition.
- **Reason:** The original S5 geometry and turn timing did not create stable opposite risk rankings at the frozen third snapshot. The selected configuration gives visible, mask-contributing branch objects with positive planned/state margins without reading compression or quality results.
- **Decision:** Use a fixed departure arc after the validation approach in S1, S2, S6, and S7.
- **Reason:** It preserves the required high-risk approach at `p=0.70` while avoiding physical collision before all four deterministic snapshots are captured.
- **Impact:** M5E-B can generate and independently validate a deterministic 32-frame smoke dataset. Risk formulas/parameters, Camera projection, trajectory definitions, snapshot targets, tile/compression policies, and M5E-A acceptance thresholds remain unchanged. Calibration generation and common-budget selection remain Milestone 5E-C work.

## 2026-07-18 - S3 Webots contact clearance

- **Decision:** Move only the nominal S3 `TURN_RISK` Box center from `(0.155, 0.080) m` to `(0.210, 0.110) m`, retaining its size and the complete S3 left-turn command schedule.
- **Reason:** Per-step Webots evidence with the canonical single-instance world found the original e-puck body-cylinder/Box contact beginning at step `140` (`4.480 s`) during the left arc. Two corrected batch runs and one corrected GUI run retained the frozen S3 risk/yaw/centroid criteria while maintaining at least `0.003971330 m` estimated body clearance and zero obstacle contacts.
- **Rejected:** Hiding the Console warning, changing the global `basicTimeStep`, weakening S3 validator thresholds, changing risk/trajectory/Camera/mask logic, changing wheel speed or turn semantics, or altering S1/S2/S4-S8.
- **Impact:** S3 remains a forward-left-arc, high-risk visual scenario under the frozen M5E-A protocol, but its validation target is no longer a physical collider on the executed path. Generated data remain deterministic, and no compression or quality metric informed the correction.

## 2026-07-19 - S5/S7 Webots contact clearance and diagnostic identity

- **Decision:** Move both S5 branch Boxes `0.030 m` in `+y`, retaining their dimensions and command schedule; retain all S7 geometry and switch only to a stop phase at `5.5 s`, after its final frozen snapshot.
- **Reason:** GUI and step diagnostics found post-snapshot e-puck body contact with `M5E_S5_PLANNED_BRANCH` and `M5E_S7_RISK`. The corrected configurations retain every frozen S5/S7 validator condition while producing positive full-episode clearance.
- **Decision:** Optional M5E contact diagnostics may record only the top-level e-puck body node ID. Do not call `getId()` on internal e-puck PROTO nodes.
- **Reason:** Internal wheel DEF nodes produced Webots Console errors and their IDs were diagnostic-only. Obstacle identity is already stable through top-level DEF nodes and immutable `ScenarioConfig.obstacle_id` strings.
- **Impact:** No risk, trajectory, Camera, projection, mask, snapshot, codec, or evaluation definition changed. M5E-B can be closed as data-generation/risk-scenario validation evidence only; it does not support a multi-scene Risk ROI superiority claim.

## 2026-07-19 - M5E-C common actual-byte budget freeze

- **Decision:** Freeze M5E formal target budgets from the calibration-only common complete-container-byte interval, not from development evidence, JPEG quality labels, payload-only sizes, or method outcomes.
- **Reason:** Across the 64 calibration frames and all four frozen methods, exhaustive legal candidate measurement yields a nonempty common interval `[31240, 35779]` bytes. The predeclared floor rule produces strictly increasing common targets: severe `31466`, low `32374`, medium `33509`, and high `34871` bytes.
- **Decision:** Retain the existing deterministic M5C matching/tie-break and require actual complete container bytes at or below each target for every frame-method combination.
- **Reason:** This preserves method-identical byte fairness and includes header, tile index, and JPEG payload in every budget. The 1,024 calibration allocation matrix passed without an over-budget result.
- **Rejected:** Selecting different budgets per method, using M5B/M5D development targets, tuning a target from PSNR/SSIM/RW-PSNR, or choosing budgets to favor Risk ROI.
- **Impact:** M5E-D/E, if explicitly started, must use these values unchanged. Calibration establishes only byte feasibility; it does not establish Risk ROI, perception, collision, or navigation benefit.

## 2026-07-19 - M5E-D formal metric table

- **Decision:** Generate the full formal split and metric table with the M5E-C frozen budgets unchanged: severe `31466`, low `32374`, medium `33509`, and high `34871` bytes.
- **Reason:** The protocol requires formal evidence to be independent of budget selection. M5E-D therefore may encode, reconstruct, and compute frozen metrics, but may not tune budgets or interpret method performance.
- **Decision:** Treat M5E-D as a deterministic engineering evidence milestone: 256 formal frames, 4,096 complete-container reconstructions, and frozen M5D metrics with independent recomputation.
- **Reason:** This creates the fixed formal evidence table needed by M5E-E while preserving paired frame-method-budget identity, actual-byte fairness, and no-future-actual provenance.
- **Rejected:** Running episode-level statistics, bootstrapping, method ranking, formal superiority claims, perception evaluation, learned training, or closed-loop navigation inside M5E-D.
- **Impact:** M5E-E must use the M5E-D metric table as frozen input for pre-registered episode statistics and diagnostics. Engineering completeness remains separate from scientific support or nonsupport.

## 2026-07-19 - M5E-E structural empty-region aggregation

- **Decision:** Keep the primary continuous risk-weighted PSNR fully paired over all four snapshots. For secondary high-risk-region diagnostics only, retain each structurally empty frame as `undefined`, average the defined frames within an episode, record valid and undefined frame counts, and leave an episode undefined when all four frames are empty.
- **Reason:** The M5D/M5E protocol forbids inventing a metric for an empty region. Explicit counts preserve that rule while allowing clearly labeled descriptive regional diagnostics where the frozen region exists.
- **Rejected:** Replacing empty regions with zero, infinity, a favorable sentinel, the full-frame metric, or dropping an episode from primary analysis.
- **Impact:** No primary pair is missing. High-risk-region results remain secondary diagnostics and cannot replace continuous RW-PSNR conclusions.

## 2026-07-20 - Public repository preparation

- **Decision:** Keep raw generated Webots data, large local result sets, logs, caches, virtual environments, and Webots GUI files ignored for public release; expose only small curated figures and a compact M2 summary CSV under `docs/`.
- **Reason:** A public research repository should let external readers understand the evidence without committing bulky raw frames, local caches, or machine-specific artifacts.
- **Rejected:** Publishing the full generated `data/` and `results/` trees, changing experimental values for presentation, adding a license without an explicit authorization choice, or claiming real-robot performance.
- **Impact:** README now points to curated public artifacts, while detailed milestone evidence remains documented in `docs/`. The public-release preparation does not alter validated experiment outputs.

## 2026-07-20 - M2 public ADE visualization and Risk-VoI sequencing

- **Decision:** Regenerate the curated M2 ADE figure from its compact public CSV with a log-scale y-axis and publish an explicit ADE improvement-factor companion figure. Draw only category/horizon combinations actually present in the CSV.
- **Reason:** The previous linear-scale chart made command-conditioned ADE nearly invisible and visually implied stable/transition and horizon coverage that the published compact CSV does not contain.
- **Decision:** Treat the existing M5E Risk ROI as the Heuristic Risk ROI baseline. Plan, but do not start, a counterfactual tile-level Visual VoI study until M5E-F independent acceptance.
- **Reason:** M5E-E shows heterogeneous offline image-quality effects and does not support a general superiority or navigation claim. Current M5E outputs do not contain enough controlled tile-quality counterfactuals to train a VoI allocator.
- **Impact:** The new plan prioritizes trajectory-critical obstacle recall, episode/scene-isolated splits, actual complete-container byte increments, an offline oracle, and a deterministic greedy allocator before any learned policy, closed-loop navigation, or network simulation.

## 2026-07-20 - Milestone 5 public presentation boundary

- **Decision:** Curate the public README around four figures and regenerate M5E figures from a checked snapshot of the frozen M5E-E outputs, rather than editing prior raster figures or exposing every diagnostic on the landing page.
- **Reason:** A compact presentation makes the formal scope, heterogeneous primary results, and limitations reviewable without concealing adverse results or turning the README into a paper-length report.
- **Impact:** The README retains S7/S8, negative/null effects, matched-byte context, and simulation-only limits; detailed diagnostics remain linked from the statistical and acceptance reports. Public plotting is presentation-only and does not write M5E-D/E formal data or manifests.

## 2026-07-21 - M6-A v2 scene-initialization authority

- **Decision:** Use controller-side Option A for M6-A v2 scene initialization. The temporary world changes only the controller wiring to `m6a_trusted_runtime` and preserves `supervisor TRUE`; the controller must apply the frozen v2 scene/seed, initial pose, and obstacle geometry before any motion, camera enablement, or snapshot lifecycle.
- **Reason:** The immutable M5E base world intentionally contains an empty obstacle group, while its historical controller imports deterministic obstacles at episode start. Keeping this single runtime authority avoids geometry drift, preserves the base-world hash, and is verifiable with Supervisor read-back digests.
- **Rejected:** Static host-side geometry materialization (Option B), modifying the M5E base world, using M5 historical results or actual traces, and maintaining dual controller/world scene authorities.
- **Impact:** A later launcher may use only the preflight-generated temporary world and must call the pre-motion initialization gate before it enables runtime devices. This decision does not authorize Webots launch, pilot generation, or scientific evaluation.
# M6-A v2 external authorization signature trust

- Execution authorization signatures use Ed25519 from the mature `cryptography` implementation; no repository code implements curve mathematics.
- The signed message is `b"RAVC-M6A-V2-EXECUTION-AUTHORIZATION\\x00"` followed by canonical JSON bytes for every authorization field except the authenticator envelope and the two derived artifact digests. The fixed prefix provides protocol-version domain separation.
- Trust is configured only by an explicitly supplied Ed25519 public key plus pinned `SHA-256(raw 32-byte Ed25519 public key)` fingerprint, key ID, issuer claim, policy version, verifier identity, and trust domain. Artifact-declared fingerprints are consistency claims, never trust roots.
- The production private key must remain offline and outside the repository. Missing, placeholder, malformed, or mismatched trust configuration fails closed. Test keys are ephemeral and may not be used as a production fallback.
- The production public trust configuration is pinned to the repository-relative `config/m6a_v2/trust/m6a_authority_public.pem` and raw-key SHA-256 `327b50d78e9f965ce7e8a10ed12bb14483ca7120325add9dbfd6d86c22f50ef4`. Signing-request export is unsigned control evidence only and cannot authorize or materialize execution.
