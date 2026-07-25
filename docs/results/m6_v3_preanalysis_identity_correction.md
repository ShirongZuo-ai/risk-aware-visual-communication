# M6 v3 pre-analysis identity correction

Date: 2026-07-25 (Asia/Shanghai)

## Scope

This correction is frozen before calculating the M6 v3 study result. It changes only how the study loader obtains the identity argument required by the existing strict aggregate validator. It does not change TCOBR, the registered matrix, evidence, methods, budgets, byte accounting, exclusions, secondary metrics, bootstrap seed or replicates, confidence interval, or support gate.

## Observed defect

The completed runtime pipeline canonically persisted the runtime-manifest identity with `launch_id=runtime-local` and `attempt_id=runtime-local`. Aggregate validation and joint validation were created and reloaded with that same identity. The study loader instead reconstructed a new identity using the prepared package launch and attempt identifiers. The strict aggregate validator correctly rejected that unequal identity before analysis.

## Correction

The study loader now reads the identity from the canonical persisted runtime manifest, requires the exact runtime-local producer identity, and passes it unchanged to the existing runtime, aggregate, and joint validators. Before accepting it, the loader binds episode, scene, seed, formal split, manifest authority, manifest/lock digests, registered attempt, package identity, and prospective attempt root to the committed v3 registration. Aggregate and joint paths remain fixed within that attempt root.

Runtime evidence is never rewritten. Recomputed-digest identity tampering and any package/runtime/registration mismatch continue to fail closed.
