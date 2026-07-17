# Roadmap

## Milestone 0 — Repository and environment baseline

- [x] Create repository structure and durable project documents.
- [x] Verify native Windows version, Python 3.10/3.11, Git, winget, NVIDIA GPU/driver, and Webots installation on the user's machine.
- [x] Initialize Git on the user's intended Windows project folder if this workspace is not that folder.

Acceptance: all checks are recorded truthfully in `docs/progress.md`; missing software is identified before installation.

## Milestone 1 — Synchronized frame and robot-state capture

- [ ] Create one repeatable Webots world with a differential-drive robot and forward RGB camera.
- [ ] Implement minimal straight, left-turn, and right-turn motion.
- [ ] Save at least 100 camera frames.
- [ ] Save aligned CSV rows containing timestamp, pose, heading, linear velocity, angular velocity, and image path.
- [ ] Verify image paths exist and timestamps align with the CSV.
- [ ] Document exact launch and validation commands in `README.md`.

Acceptance: Webots runs; the world is repeatable; all three motions work; at least 100 aligned frame/state samples are validated; README and progress record the real results.

Do not implement risk maps, ROI compression, object detection, closed-loop navigation, ROS 2, or AI models in this milestone.

## Milestone 2 — Geometry and trajectory ground truth

Planned: define coordinate frames, generate the 1–2 second predicted trajectory, inflate it by robot width, and validate projections/metadata on scenarios 1–3.

## Milestone 3 — Interpretable collision-risk map

Planned: specify TTC edge cases and risk normalization, implement obstacle-level and block-level risk, and add unit/visual tests.

## Milestone 4 — Budget-matched compression comparison

Planned: implement Uniform, Fixed Center ROI, Object ROI, and Proposed block-wise prototypes; match target byte budgets and report mismatch.

## Milestone 5 — Offline task evaluation

Planned: evaluate communication, image-quality, and safety-critical perception metrics across scenarios and budgets.

## Milestone 6 — Simple closed-loop navigation

Planned only after offline evidence supports continuing.
