# M6-A Independent Byte-Fair Evaluation Preflight

Status: preparation complete; Webots pilot and formal run have **not** started.

M6-A compares `state_only_risk_roi` with `command_conditioned_risk_roi` using the same decision-time state, 2.0 s horizon, 0.032 s step, robot footprint, corridor/risk parameters, projection, codec, allocation search, and complete-container accounting. The command-conditioned method's sole additional input is its decision-time future command schedule. Actual future trajectory is forbidden as a method input and reserved for later prediction-error ground truth.

The immutable [manifest](results/m6a_manifest.json) fixes 16 calibration, 32 formal, and 8 pilot episode identities across S1–S8 in separate M6-A seed namespaces. Four snapshot targets yield 128 formal frames; two methods and four existing complete-container budgets yield 1,024 future formal cases. Each selected container must be at or below its target; paired mean byte differences retain the existing 0.5% tolerance.

Preflight passed for the manifest: calibration/formal overlap is zero, actual-future use is false, and the versioned formal output directory is clean. A deterministic two-frame / sixteen-case **codec-only** smoke passed with zero over-budget cases. It is not a Webots pilot, ROI-quality result, ADE/FDE result, or formal outcome.

Before formal execution, implement and run a small Webots pilot using the eight reserved pilot identities, then validate decoded artifacts, missing/duplicate keys, finite values, leakage flags, ROI areas, byte tolerance, runtime, and disk use. Formal execution remains blocked pending that pilot and explicit user approval.
