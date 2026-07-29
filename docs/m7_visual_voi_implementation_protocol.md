# M7 Visual-VoI Offline Implementation Protocol

Status: frozen implementation interpretation before development-corpus outcome calculation

The scientific weights, thresholds, nine gates, tile grid, codec, budgets, and causal boundary are unchanged from `m7_budget_conditioned_voi_design.md`. The implementation uses the existing shared JPEG ladder `(1, 15, 35, 55, 75, 95)` and the established scene-stratified bootstrap with 10,000 replicates, seed 20260724, equal scene weights, and a 95% percentile interval.

Sender-only component maps are operationalized without evaluator annotations: risk is normalized mean state/command predicted-corridor occupancy; trajectory coverage is each tile's share of union-corridor support; visibility gain is normalized current-RGB Canny edge support at the frozen 50/150 thresholds; uncertainty is normalized state/command disagreement plus projected-corridor boundary support. Marginal distortion uses the frozen 50/30/20 component weights with proportional redistribution for empty masks. The exact tiled container plus fixed method metadata is charged; no evaluator mask is signaled.

Evaluator-only obstacle geometry is loaded only after all four budget allocations for an episode have returned and passed provenance validation. It is used solely to calculate frozen TCOBR eligibility, continuous boundary recall, critical-boundary coverage, and critical-region quality. The allocator API rejects evaluator geometry, TCOBR labels, evaluation masks, actual future data, and unknown fields.

JPEG quality transitions whose exact encoded payload increment is zero or negative are rejected at the candidate boundary, recorded with `nonpositive_delta_bytes`, and never divided, selected, treated as a free upgrade, or skipped across. The affected tile remains at its current quality. This is the fail-closed interpretation of the frozen nonmonotone/zero-byte rule and does not invoke fallback or alter the candidate ladder.

For comparisons to the "better frozen baseline," each episode/budget uses the larger of the state-only and command-conditioned values for benefits and quality. This conservative rule is fixed before outcome inspection. Gate 6 requires positive lower confidence bounds for both binary episode TCOBR and continuous boundary utility. Undefined episodes remain excluded only from metrics that are mathematically undefined and are never imputed.
