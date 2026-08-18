# M9-A Implementation Inventory

This is a proposed change inventory, not authorization to implement or launch.

## Files to add

- `simulator/m9a_config.py`: frozen scenario parameters and split-independent constants.
- `simulator/m9a_scenarios.py`: deterministic parameter materialization.
- `simulator/controllers/m9a_future_danger/m9a_future_danger.py`: dense logger and contact observer.
- `simulator/worlds/m9a_future_danger.wbt`: dedicated base world.
- `evaluation/m9a_ground_truth.py`: actual-future slicing, clearance, collision and event labels; no predictor imports.
- `evaluation/m9a_predicted_risk.py`: R0/R1/R2 adapter over frozen M2/M3 modules; no future-log access.
- `scripts/validate_m9a_episode.py`: schema, time, geometry, contact, and provenance validation.
- `scripts/run_m9a_pilot.py`: pilot-only generation with explicit output root.
- `scripts/calibrate_m9a_thresholds.py`: calibration-only `d_near` and warning cutoffs.
- `scripts/evaluate_m9a_formal.py`: sealed formal evaluation requiring lock/calibration digests.
- `scripts/validate_m9a_split_isolation.py`: identity/path/seed and access-boundary checks.
- `tests/test_m9a_ground_truth.py`, `tests/test_m9a_schemas.py`, `tests/test_m9a_split_isolation.py`, and controller fake-Supervisor tests.
- `docs/results/m9a_*_manifest.json` and lock files only after separate split approval.
- Generated logs under `data/logs/m9a/<split>/` and results under `results/m9a_future_danger/` only after launch approval.

## Existing files expected to change

- `docs/research_protocol.md`, `docs/roadmap.md`, `docs/progress.md`, and `docs/decisions.md` for verified stage transitions.
- `README.md` only when runnable pilot commands exist.
- `.gitignore` only if new generated roots are not already covered.

## Files that must not change

Frozen M2-M8 data, results, manifests, locks, metrics, predictors, risk geometry, and historical reports. M9-A adapters reuse, not edit, `navigation/trajectory_prediction.py` and `risk_map/geometry.py`.
