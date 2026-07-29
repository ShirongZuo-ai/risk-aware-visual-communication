# M7 v1 Corpus Validator Correction

Status: pre-continuation engineering correction; scientific design unchanged

The first corpus-level reload exposed an identity-reconstruction defect in the read-only validator. Controller-produced runtime and joint evidence intentionally use the local identity values `launch_id=runtime-local` and `attempt_id=runtime-local`, while host process evidence is bound to the authoritative prepared-package launch and attempt identifiers. The validator incorrectly supplied the runtime-local identity to the host process-evidence loader.

The correction validates an explicit one-to-one bridge: the package launch/attempt identity must match the registered attempt, while both identities must independently match the same authoritative M7 v1 manifest record, `development` split, episode, scene, and seed. Runtime evidence must retain the two exact `runtime-local` fields; process evidence must retain the exact package fields. Canonical digest, path, artifact, manifest, aggregate, joint, final-marker, and ownership validation remain unchanged.

No manifest, lock, package, runtime evidence, codec evidence, scene, seed, method, budget, or scientific definition is rewritten by this correction.
