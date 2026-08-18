# Decision log

## 2026-08-14 - CVC-P4 removes starvation but rejects confirmatory escalation

- **Decision:** Select the outcome-blind fixed-late reserve at step 218. U0 is 0/109/218; A0/A1 share startup and reserve, and only the threshold-0.14 middle packet timing differs.
- **Evidence:** All 18 Webots episodes reconcile to three 24,000-byte packets and 72,000 bytes; every policy exhausts at step 218. P3 premature exhaustion is structurally impossible.
- **Decision:** Classify P4 as Case C. A1 improves completion (4/6 versus 1/6) but loses clearance in 4/6, reduces mean clearance by 0.1620 m, creates the only danger-threshold episode, and worsens pre-danger image age in four pairs.
- **Rejected:** Calling completion gains a stable safety advantage, opening C4/C5, moving the reserve after outcomes, redesigning scenarios, or continuing threshold/reserve tuning until A1 wins.
- **Next priority:** Freeze a development-only receiver-relevant visual novelty/control-sensitivity timing diagnostic to determine whether early risk warnings coincide with useful new information.

## 2026-08-14 - CVC-P3 converts prediction lead but does not justify confirmation

- **Decision:** Qualify the frozen threshold-0.14, three-packet mechanism as a temporal actuator. On 18 distinct sender-only P2 risk streams it converts all finite positive leads, with median 26 steps and exact 72,000-byte equality; the same result holds at four and six packets.
- **Decision:** Use a compact complete-frame JPEG envelope for P3 because the prior 48-tile codec cannot physically fit the fixed-cost 12/18/24 kB opportunities. All policies share quality 45, metadata, padding, receiver hold, and total cost.
- **Evidence:** In 18 Webots development episodes A1's earlier packets change decoded perception, wheel commands, and trajectory in every A0/A1 pair, but A1 has 3/6 collisions, 2/6 successes, and 1/6 clearance wins versus A0's 2/6 collisions, 1/6 successes, and 5/6 clearance wins.
- **Decision:** Classify predictive risk as actionable without demonstrated task value. Preserve the adverse repeated-trigger/token-exhaustion mechanism; do not tune until A1 wins or alter scenarios.
- **Rejected:** Opening C4/C5 Formal, claiming spatial actionability, treating the isolated `late_appearance` improvement as general benefit, or overwriting CVC-P2.
- **Next priority:** If separately authorized, freeze a development-only single-spend or reserved-token allocator that guarantees one late packet using only risk/time/budget, then retest the same scenarios. No confirmatory study is currently justified.

## 2026-08-14 - M9-B confirms C2; CVC-P1 remains development-only

- Accept the preregistered M9-B C2 replication as PASS: effect `0.087419` and CI lower bound `0.077181` satisfy the frozen practical and uncertainty criteria with full support.
- Retain R2-R1 as secondary: delta `0.006048` remains far below the `0.05` practical threshold.
- Treat CVC-P1 as a functional visual closed-loop engineering baseline, not C4/C5 evidence. Communication relevance passes, but matched U0/A0/A1 safety results are null.

## 2026-08-13 - M9-A-FR primary claims remain unsupported

- Preserve the complete 144-episode corpus without augmentation, replacement, or Calibration pooling.
- Apply the support gate before primary interpretation: F6 has three near misses versus four required, so C2/C3 are `insufficient_support`.
- Retain the descriptive result: state-only prediction improves danger discrimination over current state, while command conditioning adds only `0.002950` AUPRC, below the frozen `0.05` practical floor.

## 2026-08-13 - M9-A physical footprint and calibration freeze

- **Decision:** M9 physical labels use the R2025a e-puck root collision-cylinder radius `0.037 m`, not axle half-length `0.026 m` and not predictor uncertainty radius `0.037592257 m`.
- **Reason:** The version-pinned PROTO specifies the cylinder; runtime validation removes the prior 9-11 mm systematic discrepancy.
- **Decision:** Accept scenario grid v7 after preserving failed Pilot grids v2-v6. Placement uses obstacle-free command traces and fixed physical-clearance targets only.
- **Decision:** Freeze `d_near=0.013 m`, the smallest preregistered candidate satisfying calibration support and safe-contamination constraints.
- **Impact:** Pilot and calibration are complete. Formal generation/evaluation remains prohibited pending explicit review.

## 2026-08-13 - M9-A-I2-V2 bilateral finding

- **Decision:** Accept dual-sided contact-point matching as operationally confirmed, but retain the overall validation verdict as FAIL.
- **Evidence:** Intended obstacle and wall contacts produced exact paired coordinates and one event in both repetitions. However, the designed safe close pass also produced 21 exact bilateral obstacle-contact frames in both runs despite `+0.011000014 m` simplified clearance.
- **Impact:** Do not weaken contact truth, tune `epsilon_contact`, or reinterpret the safe fixture. Pilot remains unauthorized pending a separately reviewed physical-footprint and fixture-geometry correction.

## 2026-08-13 - M9-A-I2R dual-sided pairing repair

- **Decision:** Reject `ContactPoint.node_id == counterpart root ID` as authoritative and use dual-sided world-coordinate point matching at `epsilon_contact=1e-6 m`.
- **Reason:** Failed I2 runtime evidence and installed R2025a bindings expose an associated node ID but do not support the assumed counterpart-root meaning. The tolerance is a pre-rerun engineering precision allowance, not outcome tuning.
- **Decision:** Eligible roots are frozen in scenario configuration; all simultaneous matches are retained, and multi-root scientific contacts receive `CONTACT_VALIDATION_FAILURE`.
- **Decision:** Fixture-validation artifacts use dedicated engineering schemas and are rejected by scientific evaluators.

## 2026-08-13 - M9-A-I2 fail-closed contact finding

- **Decision:** Do not infer intended obstacle/wall collision from positive raw contact counts or geometric proximity when Webots counterpart identity does not match the manifest-declared node.
- **Reason:** In all four authorized positive-fixture runs, contact records identified robot descendant/body nodes rather than the obstacle/wall root. Physical contact was evident, but the frozen identity filter could not validate its counterpart.
- **Impact:** Pilot remains unauthorized. A reviewed adapter must establish R2025a counterpart semantics (potentially by querying declared environment nodes or resolving both sides of descendant contacts), and fixture-only schema support must be added before any further Webots authorization.

## 2026-08-13 - M9-A-I1 finite identities

- **Decision:** Freeze six literal cells per F1-F8 and one/two/three replicates for pilot/calibration/formal (48/96/144 identities).
- **Decision:** Map seeds as split base plus `1000*family + 10*parameter + replicate`, with bases 910000/920000/930000.
- **Decision:** Keep raw contact observations, declared-counterpart filtering, and validated collision events as separate types; predictive quantities cannot enter physical labels.

## 2026-07-24 - M6-A v2 controller failure evidence

- **Decision:** Persist controller failures as canonical `m6a-v2-episode-runtime-failure-v2` records with a stable operation stage, last completed lifecycle state, original exception type, redacted actionable message, basename/function/line frames, runtime identity, transition history, producer identity, and digest. Reload verifies canonical bytes, schema, semantics, transitions, frames, and digest; the same structured payload is emitted to controller stderr.
- **Decision:** Read current e-puck position and orientation from the Supervisor Node APIs and derive z-up yaw from the orientation matrix, matching accepted M2-M5 controllers. Continue deriving causal linear/angular velocity from current wheel device values.
- **Reason:** Disposable smoke-001 proved controller discovery but its v1 status discarded the only information capable of separating scene, device, actuator, episode, and shutdown failures. Offline tracing also found that the prior strict axis-angle check could reject ordinary dynamic roll/pitch before snapshot persistence.
- **Rejected:** Retrying smoke-001, weakening runtime validators, treating return code zero as scientific success, persisting absolute host paths or environment values, overwriting immutable success/failure evidence, or changing scene/schedule/snapshot/scientific definitions.
- **Impact:** Existing v1 smoke evidence remains immutable. A separately approved smoke-002 can determine whether the state-reader defect was smoke-001's actual cause; if anything else fails, its exact stage and sanitized traceback will be retained without another protocol.

## 2026-07-24 - M6-A v2 Webots project and termination contract

- **Decision:** Newly prepared packages are complete Webots projects with the world under `worlds/` and the trusted wrapper under `controllers/m6a_trusted_runtime/`. The package binds the copied/source hashes, repository import root, forwarded controller output, and the existing attempt path plan.
- **Decision:** The runtime adapter applies the frozen predefined wheel schedule before every step, continues through its 6.0 s end, stops the motors, and the Supervisor requests `simulationQuit(0)` only after the runtime lifecycle returns success. Controlled failures request `simulationQuit(1)`.
- **Reason:** Attempt-002's retained Webots context proves its selected project excluded the named controller. Independent code tracing also showed missing actuation, rejected authoritative output paths, and no Webots exit request. These are lifecycle defects, not evidence that the frozen six-second episode requires more than 75 seconds.
- **Rejected:** Increasing the timeout, changing the scientific schedule, adding a second output-path protocol, accepting exit/timeout as scientific success, modifying attempt-002, or retrying it.
- **Impact:** The timeout stays at 75 seconds, historical v3 packages remain audit-readable but cannot launch through the v4 production runner, and a new package plus separately approved disposable Webots smoke is required before attempt-003.

## 2026-07-23 - M6-A v2 verified-authorization generation archival

- **Decision:** Treat the authoritative detached bundle, authorization artifact, and verified receipt as one immutable generation. Archive exact bytes under `authorization_generation_history/g.<request-digest-prefix>/` with a canonical manifest binding the full request digest, authorization ID, signed-message digest, production trust, per-file SHA-256, and canonical digests before releasing any authoritative source path.
- **Reason:** Independent file histories could admit partial or mixed generations, while deleting stale verification evidence would destroy auditability. A short generation directory avoids Windows path-length failures and reuses the retained request/preflight plus the pinned Ed25519 verifier instead of duplicating trust logic.
- **Impact:** `refresh-export` now fails closed before renewal on incomplete, conflicting, tampered, escaped, or unverified generation state. Copy interruption resumes while sources remain intact; source-release interruption resumes only from a complete identical manifest. A new request cannot inherit an old bundle, artifact, or receipt.

## 2026-07-22 - M6-A v2 materialization-only operator boundary

- **Decision:** Extend the fixed-path operator CLI with one `materialize-only` command that revalidates the full persisted authorization chain, repeats pinned-public-key verification, builds the existing external context type, calls the existing production materializer, and reloads the existing owned-context/ownership contract.
- **Reason:** A parallel ownership artifact or materializer would duplicate security semantics. Reusing the current context factory, atomic attempt-root creation, and ownership marker preserves a single authority chain and makes the stop-before-launch boundary explicit.
- **Impact:** Successful materialization creates one root and ownership marker only. Pre-existing execution evidence, second use, test or arbitrary contexts, stale/tampered evidence, or path drift fail closed; no runner, process evidence, consumption, completion, or final marker is invoked.

## 2026-07-22 - M6-A v2 request archival path and recovery

- **Decision:** Name archived unsigned requests `request.<canonical_request_digest>.json` inside the package workspace and implement explicit source/archive recovery states. Validate expired requests against their retained bound preflight at issue time before any move.
- **Reason:** The original timestamp-plus-digest filename produced a 276-character Windows destination and failed with `WinError 3` after creating the history directory. A short content-addressed name is deterministic, portable, and avoids platform-specific extended-path handling.
- **Impact:** First use, identical duplicate recovery, source-missing recovery, and the request-moved/preflight-refreshed crash boundaries are idempotent. Conflicting bytes, missing source plus missing expected archive, path escape, symlink, and invalid history types fail closed; current request freshness remains unchanged.

## 2026-07-22 - M6-A v2 authorization operator command boundary

- **Decision:** Provide fixed-path `refresh-export` and `verify-only` repository commands, plus an explicitly repository-external signing template. The repository commands expose no private-key or output-root parameter and never create execution context or runtime evidence.
- **Reason:** Multi-step `python -c` commands require manual path, digest, and timestamp handling inside a five-minute window. A narrow tested wrapper reuses existing authorities and reduces operator error without adding a signing service or authorization layer.
- **Impact:** Expired unsigned requests can be validated against their retained preflight evidence and moved unchanged into digest-named history before renewal. Actual private-key access remains an explicit operator action outside the repository.

## 2026-07-22 - M6-A v2 detached authorization verification boundary

- **Decision:** Accept repository-external signatures only through one canonical detached-bundle schema bound to the current unsigned-request digest, signed-message digest, authorization ID, and pinned key ID. Derive bundle, unverified-artifact, and receipt paths from the prepared workspace; reuse the existing authorization payload, Ed25519 verifier, and receipt type.
- **Reason:** This closes the offline-signature return path without duplicating canonical payload or cryptographic logic, accepting artifact-claimed trust, or creating an execution context.
- **Impact:** Successful verification proves signature and binding validity only. Materialization, ownership, process launch, consumption, and finalization remain separate and false; no repository component gains private-key access or signing capability.

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
- Renewable authorization control evidence keeps one canonical current preflight path plus immutable digest-named history inside the prepared workspace. Production signing requests use the fixed workspace-relative name `unsigned_authorization_signing_request.json`; valid repeats are idempotent and caller path redirection is rejected.

## 2026-07-23 - M6-A v2 durable owned context and one-shot launch

- **Decision:** Separate pre-materialization package validation from post-materialization validation. The former requires an absent prospective root; the latter requires the exact canonical ownership record and durable owned-context artifact. No `allow_existing_root` compatibility switch is provided.
- **Decision:** Persist `OwnedAttemptContext` inside the attempt root immediately after ownership acquisition. It binds the package path/digest/HEAD/branch, authorization and receipt, the externally validated context, attempt identity/root, ownership, execution mode, and materialization time. Production callers must reload the artifact; arbitrary dictionaries are rejected.
- **Decision:** Reuse `OwnedPopenBackend.start(...)` behind `ProductionOwnedProcessRunner.run(...)`, while keeping authorization consumption, process evidence, completion, and finalization in their existing single-authority modules. `run-pilot` launches at most once and treats a complete consumption/process pair as recovery evidence, a partial pair as terminal failure, and a completed terminal as idempotent success.
- **Decision:** Legacy owned roots that predate durable context may only be closed through immutable `retired_pre_spawn` evidence after proving no launch, consumption, runtime, completion, or final evidence exists. The original ownership file remains unchanged and retirement is not a scientific result.
- **Rejected:** Treating any existing root as owned, synthesizing context for a legacy attempt, retrying a process after partial evidence, duplicating subprocess/consumption/completion protocols, or launching a package whose HEAD differs from the executing repository.
- **Impact:** A newly authorized attempt can now move from durable ownership through one-shot process execution and existing completion/finalization. The superseded `m6a-prod-pilot-001` remains untouched until a separately approved retirement command is run.

## 2026-07-24 - M6-A v2 separate local research execution authority

- **Decision:** Add a separate research entry point that reuses the canonical prepared package, exclusive ownership, shell-free process runner, process evidence, scientific completion, joint validation, and final marker while omitting production signatures, receipts, execution contexts, and authorization consumption.
- **Decision:** Persist a research context followed by an immutable launch claim before process start. A claim without complete process evidence is indeterminate and terminal for automatic execution; a complete process record may be recovered without relaunching.
- **Decision:** Preserve attempt-002's immutable package rather than regenerate it after adding the runner. Package HEAD equality remains preferred; one direct descendant commit is accepted only when its complete changed-path set is contained in a fixed runner/tests/documentation allowlist. Both commit identities, changed paths, and the binding digest are persisted in the research context.
- **Reason:** Local simulation research needs a reviewable at-most-once boundary but does not require the operational complexity or private trust material of a production deployment. The narrow HEAD bridge keeps the scientific package immutable while binding the only implementation commit introduced after package preparation.
- **Rejected:** Weakening the production authorization workflow, silently accepting arbitrary descendant HEADs, rewriting the prepared package, retrying after ambiguous spawn, creating a second scientific validation stack, or treating exit code zero as a valid pilot result.
- **Impact:** A separately approved command can create and run the first local closed-loop attempt once. No Webots launch or real attempt was performed while implementing this capability; production execution semantics remain unchanged.
# 2026-07-25 - Freeze TCOBR as the M6 primary outcome

Use the method-independent union of the frozen planned and state corridors to define critical obstacles, frozen M4 projection and deterministic boundary-edge matching to measure recall, and episode-level scene-stratified inference. This resolves the earlier ambiguous trajectory-critical recall placeholder without changing scenes, identities, methods, budgets, byte accounting, manifest, or lock.
# M6 v3 additive authority (2026-07-25)

The exhausted v2 authority remains immutable. The final formal study uses a separate v3 manifest/lock with exactly 32 new S1-S8 records at seeds 630100-630803. Production routing selects either strict v2 or strict v3 validation from the declared manifest schema; it does not merge manifests or introduce a second runner. TCOBR, methods, budgets, byte accounting, exclusions, bootstrap and support gate are unchanged.

## 2026-07-26 - Freeze M6 as a negative baseline and enter budget-conditioned VoI

- **Decision:** Freeze the completed M6 v3 study as a negative-result baseline. The original S1-S8 support gate remains `NOT EVALUATED`; the committed eligibility-conditional S2-S6 gate remains `FAIL`, with command-conditioned minus state-only TCOBR `0.000000` and 95% CI `[0.000000, 0.000000]`.
- **Reason:** Fifteen episodes have undefined TCOBR and three scene strata are empty; among all 17 eligible episodes, both methods have identical TCOBR at every budget. Replacing scenes, imputing undefined episodes, or tuning against this evidence would invalidate the preregistered boundary.
- **Decision:** Define the next milestone as budget-conditioned visual value of information combining trajectory risk, visible coverage, downstream task utility, and actual incremental bytes. Require new disjoint, eligibility-rich data and deterministic oracle/greedy baselines before learned allocation.
- **Rejected:** Reinterpreting the zero interval as universal method equivalence, claiming command schedules have no value outside the frozen study, modifying TCOBR eligibility, or immediately training on M6 formal evidence.
- **Impact:** M6 artifacts, protocols, manifests, locks, and outcomes remain immutable. Publication figures are presentation-only derivatives with checked JSON/CSV source tables and may not alter scientific results.

## 2026-07-27 - Separate publication progress from scientific method effects

- **Decision:** Lead the repository landing page with verified M1-M6 capability evolution, formal lifecycle scale, and absolute budget-quality behavior; place the unchanged zero-effect TCOBR forest under scientific findings and limitations.
- **Reason:** Project-level engineering progress and budget-quality improvement are distinct from whether command conditioning improves the preregistered TCOBR endpoint. Presenting them in one visual hierarchy prevents the null method result from obscuring verified system capabilities without diminishing the negative finding.
- **Decision:** Retain one narrowly scoped M5 context figure only because frozen evidence supports it, showing all three baselines at both Severe and Low budgets, including adverse and null-compatible effects.
- **Impact:** Quantitative publication figures remain deterministic derivatives of documented frozen paths. No protocol, evidence, gate, or interpretation boundary changes.

## 2026-07-28 - Diagnose allocation collapse before implementing M7 VoI

- **Decision:** Treat the frozen M6 null effect as a measured allocation-actuation failure plus TCOBR saturation, not as evidence that future commands are intrinsically useless. Preserve both M6 methods unchanged.
- **Evidence:** Trusted masks average fewer than ten active pixels; only 0.0197% of pixels and 0.1302% of selected tiles differ. Depending on budget, 85.16%-93.75% of paired reconstructions are identical, critical-region byte/coverage/PSNR differences are negligible, and both methods share near-ceiling absolute TCOBR.
- **Decision:** Start M7 with an offline deterministic marginal-benefit-per-exact-byte allocator using equally weighted risk, trajectory coverage, visibility gain, and uncertainty, multiplied by measured marginal reconstruction benefit. Require explicit actuation, eligibility, byte-fairness, critical-coverage, task-utility, quality, heterogeneity, and reproducibility gates before proposing Webots.
- **Rejected:** Retuning the frozen masks, changing TCOBR eligibility, interpreting undefined scenes as zero/one, immediately learning from M6, merely increasing ROI size without byte-cost evidence, or launching another Webots experiment before offline actuation is demonstrated.
- **Impact:** The next implementation must use new disjoint offline development/evaluation identities. M6 remains the immutable negative baseline and no new experiment is authorized.

## 2026-07-29 - Freeze the M7 v1 development corpus before generation

- **Decision:** Register exactly 16 new development identities across M7C1-M7C6 and M7G1-M7G2 at seeds 710100-710801. Critical scenes use declared geometry-only visible corridor events; G scenes are low-risk controls. All records are fixed before RGB, codec, or task outcomes.
- **Decision:** Keep sender-time state, schedule, trajectory/uncertainty, and projection inputs separate from evaluator-only obstacle AABBs and critical labels. Persist evaluator geometry only after runtime in a separate canonical artifact bound to final evidence.
- **Decision:** Reuse the existing v4 prepared-package and research lifecycle with exactly one launch per registered identity, no retry, and batch stop on any shared or episode failure. Corpus generation retains only the two frozen M6 methods and does not implement Visual-VoI.
- **Rejected:** Reusing M5/M6 evidence, inventing post-outcome replacements, exposing obstacle labels to allocation, creating the 720xxx formal split, or treating development-corpus completion as an M7 go decision.
- **Impact:** The manifest, lock, schemas, validators, tests, protocol, and complete matrix must be committed before preparation. The corpus is development-only and cannot enter formal inference.

# M7 v1 corpus identity reconstruction correction (2026-07-29)

- Preserve the intentional runtime-local identity in controller-produced evidence and the package identity in host process evidence.
- Validate an explicit bridge through the exact registered M7 v1 authority, development split, episode, scene, and seed; never rewrite persisted evidence to make the identities equal.
- This is a read-only validation correction and does not alter the M7 v1 manifest, lock, packages, scientific design, or episode data.

## 2026-07-29 - Retain the M7 Visual-VoI offline NO-GO

- **Decision:** Evaluate the frozen Visual-VoI weights, thresholds, codec rules, and nine conjunctive gates without post-outcome adjustment. The resulting decision is `NO-GO` because gates 2, 4, 6, and 7 fail.
- **Evidence:** Allocation actuation and critical-boundary HQ coverage improve, but TCOBR remains saturated at 1.0 in eligible episodes, continuous boundary utility declines, the exact-byte utilization gap reaches 3.323 percentage points, and critical-region PSNR falls by 2.053 dB at Severe and 8.571 dB at Low.
- **Decision:** Keep undefined TCOBR observations undefined. M7C6, M7G1, M7G2 and the ineligible M7C5 episode are not imputed or replaced. The mismatch between two registered episodes per scene and the gate requirement of three eligible episodes is reported as a failed gate, not repaired retrospectively.
- **Rejected:** Relaxing byte fairness, redefining high-quality coverage, modifying benefit weights, treating binary coverage as task success, creating a 720xxx split, or launching Webots after a partial gate pass.
- **Impact:** M7 v1 remains a frozen development result. A future allocator requires a separately reviewed offline redesign and new disjoint authority before any experiment proposal.

## 2026-07-30 - Retain the M7 v2 matched-floor NO-GO

- **Decision:** Use the exact midpoint of the two frozen baseline transmissions as a per-case cap, establish the highest feasible uniform quality floor, and compare only three preregistered residual-upgrade objectives: global MSE, visible edges, and visible edges inside the predicted corridor.
- **Reason:** This is the smallest deterministic revision that directly addresses v1's excess utilization and quality loss while keeping the codec, baselines, task evaluator, and sender-time boundary intact.
- **Evidence:** All candidates pass byte fairness, integrity, actuation, critical quality, TCOBR non-degradation, and determinism. None passes continuous task utility, critical-boundary fidelity, or scene balance. The best mean effect is `+0.00176`, 95% CI `[-0.00610, +0.00962]`, entirely driven by M7C2 at Severe.
- **Rejected:** Padding bytes, weakening the 0.5-point byte tolerance, selecting the directionally positive candidate despite a nonpositive CI bound, retuning weights after seeing M7 v1/v2 results, replacing saturated TCOBR observations, or creating 720xxx/Webots evidence.
- **Impact:** No v2 candidate is selected. Future work requires a separately reviewed sender-available utility measurement and new eligibility-rich authority, not another adjustment on this corpus.

## 2026-07-30 - Freeze M7 v1/v2 and require independent proxy qualification for M8

- **Decision:** Freeze M7 v1 and M7 v2 as completed development-only `NO-GO` baselines. Preserve the M7 v2 matched-byte envelope, 0.5-percentage-point utilization tolerance, uniform quality floor, deterministic residual upgrades, exact container recomputation, and zero leakage/fallback/replacement.
- **Reason:** M7 v2 repaired the M7 v1 byte and quality defects, but all three candidates failed continuous task utility, critical-boundary fidelity, and scene balance. The best effect crossed zero and arose entirely from one scene; TCOBR remained saturated.
- **Decision:** Qualify FROPU and STRCF on a new calibration split before allocator development. Use fixed method-independent perturbations and isolated evaluator-only CCORF references, with nine conjunctive proxy-validity gates and a selection rule fixed before allocation outcomes.
- **Decision:** Treat TCOBR as a non-degradation safety metric. It cannot select or optimize an M8 allocator.
- **Decision:** Propose disjoint `810xxx` calibration, `820xxx` development, and `830xxx` formal identities across eight eligibility-rich critical scenes and two low-risk generalization scenes. The proposal is not a manifest or launch approval.
- **Rejected:** Further tuning on the M7 v1 corpus, selecting the least-negative M7 v2 candidate, choosing a proxy because it favors a baseline, weakening scene-balance or byte gates, imputing undefined TCOBR, implementing an allocator before proxy qualification, or generating a formal corpus now.
- **Impact:** M8 proceeds measurement-first. Failure of either a proxy's prerequisite or any common gate is retained as `NO-GO`; data generation and allocator development require later, separately reviewed stages.

## 2026-08-13 - Pause M8 and preregister M9-A future-danger validation

- **Decision:** Pause M8 after B0 and insert M9-A as a falsifiable validation of whether predicted future motion forecasts independently observed danger better than current-state clearance. Do not reinterpret M3 heuristic risk or M5-M7 offline outcomes as future-danger evidence.
- **Decision:** Use disjoint pilot/calibration/formal partitions; dense basic-timestep actual motion; Supervisor contact observations validated in pilot; physical 0.026 m robot radius for labels; and exact nominal 0.5/1.0/2.0 s horizons with boundary interpolation. Keep the uncertainty-inflated 0.037592257 m M3 corridor predictor-side only.
- **Decision:** Calibrate `d_near` and matched false-warning operating points without formal access. Compare raw R0/R1/R2 signals and resample episodes within family. Formal support failure is reported as insufficient data, not repaired with calibration observations.
- **Rejected:** Reusing sparse M5E/M6/M7 snapshots as ground truth, selecting thresholds from formal outcomes, forcing command-transition geometry to favor R2, using predicted TTCf as collision truth, or launching any split from this protocol-only stage.
- **Impact:** `docs/m9a_p_future_danger_protocol.md` and its schemas become the review basis for a later implementation/pilot. C2 and C3 remain pending; communication development remains paused.

## 2026-08-13 - Amend M9-A after independent readiness review

- **Decision:** Use exactly two primary claim tests: 2.0 s danger AUPRC from negative predicted physical clearance, R1-R0 for C2 and R2-R1 for C3. Require difference at least 0.05 and paired 95% interval lower bound above zero; secondary endpoints cannot rescue failure.
- **Decision:** Freeze finite physical `d_near` candidates, calibration selection, safe-exposure false-warning rules, event grouping, family-specific support, closed exclusion codes, and digest/ledger-based one-shot formal access as specified in the amended protocol.
- **Decision:** Freeze literal scenario grids and seed mapping before pilot generation; pilot failure may trigger reviewed version replacement but cannot filter formal identities.
- **Rejected:** Best-performing signal/horizon selection, pooled-frame inference, documentation-only formal sealing, role-based formal replacement, or treating protocol readiness as launch approval.
- **Impact:** M9-A-P passes protocol review with amendments. Pilot implementation and all Webots execution remain unauthorized pending the incomplete checklist in `docs/m9a_r_independent_protocol_review.md`.

## 2026-08-14 - Retain CVC-P2 as a negative development result and stop before Formal

- **Decision:** Select two exact 36,000-byte packets as the CVC-P2 candidate regime using U0 physical outcomes only: collision or clearance below 0.12 m, mixed across scenarios, and at least two temporal opportunities.
- **Evidence:** The U0 sweep moves from 0/6 physical failures at three packets to 1/6 at two packets and 1/6 with an actual collision at one packet. The 42-episode matched matrix reconciles to exactly 72,000 bytes per episode.
- **Decision:** Retain the corrected R0/R1 result as negative. R1 warning lead exists but produces identical T/S/TS decisions in all 18 pairs; T and TS are adverse, with 1/6 collisions and 0/6 task successes versus U0's 0/6 and 3/6.
- **Rejected:** Treating warning lead alone as communication benefit, tuning decision thresholds until R1 wins, hiding the startup-initialization failure, or opening C4/C5 Formal without an actuating candidate.
- **Impact:** Preserve all CVC-P2 failures and corrected traces. Any next stage must be a new development-only allocator qualification with a pre-Webots R0/R1 actuation gate; C4/C5 remain unopened.

## 2026-08-14 - Support the P4 temporal-misalignment mechanism after CVC-P5

- **Decision:** Retain CVC-P4 unchanged as Case C and accept H_P5 only as a development mechanism in the controlled red-component Webots stack. In all six A1 episodes, R1 precedes the cumulative 25% onset of visual, perception, and control novelty; all six control peaks occur after the adaptive token is spent.
- **Evidence:** Median R1-before-R0 lead is 38 steps, while median R1-to-control-q25 and R1-to-control-peak gaps are 117.5 and 142 steps. Median control sensitivity is 0.1601 rad/s at A1's send versus 1.2432 rad/s at A0's later actual send. Twelve diagnostic replays exactly reproduce P4 at 72,000 charged bytes with zero charged shadow bytes.
- **Decision:** Separate physical-danger prediction from communication spending. The next candidate may let R1 arm a causal window, but spending must wait for sender-available safety-relevant visual/perception/control novelty and retain a deadline plus protected reserve.
- **Rejected:** Treating all visual novelty as communication value, using clearance/outcomes to tune an onset threshold, implementing a new allocator inside P5, another risk/reserve/packet sweep, or opening C4/C5 Formal.
- **Impact:** CVC-P6, if authorized, must first freeze one signal-only arm/spend candidate and prove timing actuation, causal inputs, exact bytes, and post-pass guarding offline. P5 itself supports no superiority or safety claim.

## 2026-08-15 - Retain CVC-P6 as Case A with an explicit safety limitation

- **Decision:** Freeze and retain the single `coarse_12px` P6 configuration selected without navigation outcomes: R0/R1 ARM at 0.14; bearing/proximity/relative-area novelty thresholds 0.15/0.075/0.50 plus component events; 96-step deadline; step-218 reserve; exact 72,000 bytes.
- **Evidence:** Offline qualification passed all mechanistic gates. In the frozen Webots comparison, A1 delayed spending and moved closer to perception/control q25 in 4/6 cases; three A0/A1 schedules collapsed exactly. U0/A0/A1 task successes were 1/1/4 with zero collisions, but every schedule-different A1 pair lost clearance.
- **Decision:** Classify P6 as **CASE A - Mechanism + task benefit** for completion/progress only. Do not interpret it as safety benefit: A1 mean minimum clearance is 0.261445 m versus A0 0.413892 m.
- **Rejected:** Post-outcome threshold/deadline/reserve tuning, combining completion and clearance into one score, treating zero collisions as proof of safety, learned novelty/control triggering in P6, and opening C4/C5.
- **Impact:** Retain P6 v1 unchanged as a development baseline. A separate broader P7 study may examine safety-relevant novelty discrimination using new outcome-independent scenarios; confirmatory testing remains unjustified.

## 2026-08-15 - Retain CVC-P7 as support-bounded Case D and do not implement P8

- **Decision:** Preserve the frozen 12-cell, 3-per-category P7 suite and its evaluator-only 0.12 m/63-step safety-window rule. Do not move, replace, delete, or retrospectively reclassify cells after the unchanged P6 U0/A0/A1 comparison.
- **Evidence:** Historical P6 schedule-different traces show that every earlier A1 update turns toward the red component, reduces absolute turning versus the stale A0 command, improves progress, and loses clearance. P7 completed 36/36 exact-cost runs, but zero runs crossed 0.12 m; high-novelty harmless B cells nevertheless armed at step 1 and spent at step 3.
- **Decision:** Classify P7 as **CASE D - no usable communication safety window demonstrated**, explicitly because positive physical-window support is absent. Treat feature AUPRC and safety lead as not estimable, not zero.
- **Rejected:** Relaxing the frozen physical threshold, editing or adding outcome-selected cells, calling slowdown/centering safety-protective without physical support, training a diagnostic model on all-negative labels, implementing P8, or opening C4/C5 Formal.
- **Impact:** The next experimental priority is separately authorized physical-support qualification with an avoidance-capable controller. P7 justifies neither rule-based nor learned Safety-VoI selection.

## 2026-08-15 - CVC-Q1 safety-task decisions

- Replaced component-centering with a 15-action, 1.5 s command-conditioned planner using safety feasibility before progress.
- Selected outcome-blind inverse-height ranging with a 0.0554147 m uncertainty bound. Preserved failed v1; v2 adds a 0.045 m/s near cap and 125-step causal static-obstacle memory.
- Froze 10 cells after HIGH feasibility and before U0 outcomes, retaining bilateral contact and the 0.12 m near boundary.
- Classified Q1 as bounded development `CASE A`: frozen near support, within-cell clearance variation, and interpretable held/current safe-decision changes exist despite zero collisions and a non-monotone budget response.
- The result authorizes design only of a separate Risk-ARM + Safety-Decision-Value-SPEND study. It does not authorize A0/A1, C4/C5 Formal, ML, or outcome-driven grid repair.

## 2026-08-15 - Retain CVC-Q2 as terminal Case D

- **Decision:** Retain the pre-outcome three-packet Q2 protocol and its transparent Safety Decision Value hierarchy without post-outcome timing or threshold repair.
- **Evidence:** All 30 paired runs reconciled to 72,000 wire bytes and matched the sender mirror, but 0/20 adaptive packets were value-triggered. All used deadline or fallback; 113 value-event timesteps occurred only after the token was already spent. U0/A0/A1 danger counts were 3/5/5 and collisions 0/2/0.
- **Decision:** Classify Q2 as **CASE D - Safety Decision Value trigger is inadequate**. Earlier R1 ARM in three cells and elimination of A0's two contacts do not validate a causal risk-to-value-to-spend safety mechanism.
- **Rejected:** Retrospective deadline/reserve changes, scenario or threshold repair, safety claims from the A0/A1 collision difference, ML, broader development, or C4/C5 Formal.
- **Impact:** The only recommended next hypothesis is a separately frozen temporal repair in which protected capacity remains value-triggerable or value persists across an explicit window. Q1 and the existing risk/value thresholds remain fixed.

## 2026-08-16 - Retain CVC-Q3 as terminal Case D despite local Safety-Value actuation

- **Decision:** Retain the frozen 63-step bounded latch, step-295 late fallback, and step-311 protected reserve without outcome-driven repair.
- **Evidence:** Two straight-approach packets were genuinely caused by priority-1 Safety Value on the same step, changing the receiver from moving-turn to stop-turn. However, only 2/20 adaptive packets were value-triggered and fallback caused 4/6 risk-armed packets; the frozen meaningful-frequency gate fails. A0/A1 schedules and outcomes were identical.
- **Decision:** Classify Q3 as **CASE D - temporal repair fails the meaningful-frequency gate**. Treat the two sends as local causal actuation, not validation of predictive communication safety.
- **Latency decision:** Preserve the pre-outcome logical-timing classification. Every requested component had zero 32 ms misses; the prospective summed path had 99/9,360 occasional overruns, which are reported as an operational caveat rather than the hundred-step mechanism failure or Case E.
- **Rejected:** Retuning fallback/window duration, replacing cells, using tied safety outcomes to rescue the mechanism, training ML, broader navigation validation, or opening C4/C5 Formal.
- **Impact:** The next experiment, if authorized, is a schedule-robust Safety Value support study with fixed Q1/Q2/Q3 mechanisms and outcome-independent cells—not another temporal sweep.

## 2026-08-16 - Retain CVC-Q4 as Case C despite full observed-event coverage

- **Decision:** Define `M_stale` as the CURRENT conservative margin of the receiver-HELD selected action and `G` as the maximum CURRENT hard-feasible margin minus `M_stale`. Use the frozen 0.025/0.075 m safety band to define candidate-space slack and soft feasibility.
- **Decision:** Retain OLS over Theil–Sen and median-adjacent as the simplest causal estimator when its 8-sample result has equal chosen-rule coverage/lead. Use the 0.224 s past-through-current window and stable-Q1 one-sided 1% tails.
- **Evidence:** `M_stale` slope covers only 2/8 onsets and `G` slope only 1/8. Soft-feasibility contraction covers 8/8 but is too permissive. Adding the outcome-independent stable-Q1 q01 level retains 8/8, median 0.480 s lead, 0.593% false steps, and 18.9% event-free episode activation.
- **Decision:** Classify Q4 as **CASE C - weak / scenario-limited precursor**, because all positive onsets come from only straight-approach and narrow-passage families. Do not treat duplicated Q2/Q3 executions as cross-family validation.
- **Rejected:** scheduler integration, a new A0/A1 comparison, outcome-selected thresholds, weighted formula search, ML, navigation claims, C4/C5 Formal, or alteration of protected Q1/Q2/Q3/M9 evidence.
- **Impact:** A future scheduler experiment is not yet justified. The next priority is event-rich, no-scheduler support qualification of the frozen soft-feasibility q01 level-plus-slope rule across at least three additional positive families.

## 2026-08-16 - Qualify the frozen Q4 precursor across CVC-Q5 families

- **Decision:** Preserve all 70 blinded Stage-A cells and retain the exact Q4 soft-feasibility q01 plus OLS-8 rule without refitting. The support gate passed with 19 onsets across four positive families before unblinding.
- **Evidence:** The frozen rule covered 16/19 onsets, achieved 0.576 s median lead, used 1.465% active time, activated in 11/53 event-free episodes, and produced a usable multi-sample opportunity for all 16 covered onsets. Every positive family exceeded 50% coverage and all six frozen gates passed.
- **Decision:** Classify Q5 as **CASE A — cross-scenario precursor qualified**, bounded to mechanism qualification. Scheduler integration is now a justified next experiment, not a result already demonstrated.
- **Rejected:** Precursor-guided scenario selection, threshold/window/estimator changes, deleting four negative families, A0/A1 execution, navigation-benefit claims, ML fitting, or Formal access.
- **Impact:** A learned precursor is not the immediate priority. Any next work must separately freeze a matched-byte causal scheduler protocol using the unchanged precursor.

## 2026-08-16 - Close CVC-Q6 as Q6-C; do not consume Q7 or open Formal

- **Decision:** Reject generation 1 after hard R1 ARM produced zero armed A1 episodes and complete fallback equivalence with A0. Treat this as F7/F6 bootstrap starvation, not precursor invalidation.
- **Decision:** Reject generation 2 despite one complete beneficial causal chain because only 1/20 cells intervened and the method remained broadly adverse versus U0.
- **Decision:** Retain generation 3 as the strongest development candidate but do not select or freeze it. It improves safety versus A0, yet versus U0 has slightly lower mean minimum clearance and a serious staggered-slalom adverse family, while also reducing progress.
- **ML decision:** A compact grouped diagnostic was justified by family-dependent timing ambiguity. Do not integrate it: logistic/tree false-warning episode fractions (56.6%/83.0%) exceed the frozen rule (20.8%), and 19 onsets do not support larger temporal models.
- **Evidence:** All executed episodes reconcile to exactly 72,000 wire bytes, the full image-to-planner-to-physical chain is demonstrated on intervention cells, 193 regressions pass, and protected M9 hashes remain exact.
- **Rejected:** threshold tuning on consumed Q5/Q6 cells, a fourth rule generation, larger ML on 19 onsets, calling generation 3 independently validated, creating Q7 without a selected method, Formal execution, or real hardware.
- **Impact:** Terminal classification is **Q6-C**. Q7 and Formal remain unopened. The next legitimate priority requires genuinely new development evidence and a new method identity.

## 2026-08-18 - Close CVC-Q6.5 after bounded opportunity-value search

- **Decision:** Preserve generation 1 as a rejected target/scheduler pair. Its fallback-relative utility was predictable but did not optimize strongest U0.
- **Decision:** Treat adjacent opportunities (80, 109, 144, 217) as the correct finite-budget counterfactual for generation 2; preserve all helpful, harmful, and neutral cases.
- **Decision:** Reject binary and three-class interpretable predictors because none passed the frozen leave-family-out predictability gate. Do not add neural models or tune thresholds on the same 45 opportunities.
- **Decision:** Freeze no scheduler and do not consume Q7, robustness, ablation, Formal, or real-robot evidence.
- **Impact:** The paper may claim that communication action utility is measurable and distinct, but not that it is predictably solved or that risk-aware scheduling beats U0.

## 2026-08-18 - Adopt one final submission-figure visual contract

- **Decision:** Use one semantic palette across the final manuscript figures: gray for current/reference/baseline, blue for future prediction and R1, green for positive physical effects or supportive secondary results, red for adverse physical effects, and amber for Safety Value/precursor concepts. Pair color with signs, edges, markers, hatching, zero lines, and direction labels.
- **Decision:** Preserve the scientific structure of Figure 1, rebuild Figures 2 and 3 from authoritative machine artifacts, and integrate one compact Q6.5 adjacent-opportunity reversal panel into Figure 3 rather than add a fourth main figure.
- **Decision:** Treat vector PDF as the submission master, SVG as the editable master, and 600-dpi PNG as review-only. Enforce a 7-pt minimum displayed figure font and programmatic canvas/box-bound checks.
- **Evidence:** The final five-page candidate has no visual overlap or clipping, no LaTeX overfull boxes or unresolved references, embedded/subset fonts, no raster image objects in the final figure PDFs, and interpretable grayscale renders. Exact provenance is recorded in `paper/figures/figure_data_provenance_final.json` and the full audit in `docs/manuscript_figure_finalization_report.md`.
- **Impact:** `paper/main_submission_figures_final.tex` is the recommended author-review candidate; historical figures and manuscript candidates remain preserved. This plotting decision changes no experiment, result, claim boundary, or Q6/Q6.5 readiness status.

## 2026-08-18 - Preserve the external-review revision as a separate candidate

- **Decision:** Apply only critique items supported by the authoritative manuscript and research artifacts: concrete motivation, comparative literature positioning, threshold provenance, and bounded Q6.5 opportunity-cost interpretation.
- **Decision:** Keep `paper/main_submission_review_revision.*` separate from `main_submission_figures_final` and `paper/IROS_submission_final/` until author approval.
- **Rejected:** Unverified typo/CI corrections, inflated framing of the negative result, and a new plot derived from narrative-only examples.
- **Evidence:** The revised five-page PDF builds with 11 references, no overfull or unresolved-reference warnings, and no visible clipping or overlap. The prior source and bibliography hashes still match their copies in the standalone final package.
- **Impact:** This is a review candidate, not an automatic replacement of the preserved submission baseline; it changes no experiment or claim boundary.

## 2026-08-18 - Freeze the Git checkpoint storage boundary

- **Decision:** Version the accumulated research implementation, tests, protocols, lightweight grids/status evidence, publication figures, manuscript sources, and the self-contained author-review package as one coherent checkpoint.
- **Decision:** Keep large/reproducible run trees under the existing top-level `results/` policy, and exclude the 52 MiB M6A pilot RGB/step corpus, temporary QA renders/builds, LaTeX auxiliaries, Python caches, and ZIP archives.
- **Decision:** Preserve the two small terminal-status files `results/cvc_q6_final_status.json` and `results/cvc_q65_final_status.json` despite the general result-output ignore rule, because they record the bounded terminal scientific decisions rather than raw experiment output.
- **Evidence:** Frozen artifact hashes pass, the standalone delivery manifest passes, the full offline suite reports 761 passed, both manuscript sources build to five pages in isolated copies, and staged-file size/secret scans pass.
- **Impact:** A clean GitHub checkpoint can be reviewed without publishing bulky raw data or weakening the Q6/Q6.5 negative-result boundaries.
