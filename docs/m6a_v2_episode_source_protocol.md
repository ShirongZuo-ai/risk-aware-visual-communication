# M6-A v2 episode-source protocol

`m6a-byte-fair-v2` supersedes v1 for execution only; v1 remains immutable historical evidence. v2 uses the immutable M5E base world plus the causal pre-run scene primitives in `simulator/m5e_scenarios.py`, without using M5 outputs or actual traces. Duration is 6.0 s and basic timestep is 32 ms. Progress `(0.20, 0.45, 0.70, 0.90)` is aligned by `floor(raw/0.032 + 0.5)`, producing `(1.216, 2.688, 4.192, 5.408)` s. The M2 16 s schedule remains validation-only.

This phase defines in-memory source records only. It creates no v2 lockfile, Webots run, pilot data, or scientific result.

## B1 immutable lock

The canonical 56-record manifest and independent lockfile freeze the source records. Their hash rule excludes self-reference: the lock hashes the canonical manifest bytes. v1 remains unchanged. Runtime configuration, temporary-world wiring, launching, summary validation, Webots, and pilot data remain out of scope.
# M6-A v2 offline codec-audit boundary

The first-pilot source record permits exactly `state_only_risk_roi` and `command_conditioned_risk_roi`, at severe/low/medium/high charged-byte budgets `31466`, `32374`, `33509`, and `34871`. The offline-only B4 codec wrapper uses the frozen M5 tiled-JPEG container and M5 image-quality implementation. For each method, it charges container payload bytes, deterministic sparse mask-index signaling bytes, and fixed codec metadata bytes; neither mask nor method signaling is free. Both methods use the same descending quality-candidate family and select the first feasible under-budget allocation, otherwise fail closed.

Codec inputs contain only the frozen identity/snapshot time, current RGB frame/current state, and predeclared command schedule. Actual future, future frames/poses, combined/raw/oracle masks, arbitrary methods/budgets, fallback, replacement, and evaluation-guided re-encoding are prohibited. The required matrix is in canonical snapshot → method → budget order and contains exactly 4 × 2 × 4 = 32 audited cases. Synthetic fixtures may test this contract in system temporary directories, but are not pilot data or scientific results; Webots execution remains unauthorized.
