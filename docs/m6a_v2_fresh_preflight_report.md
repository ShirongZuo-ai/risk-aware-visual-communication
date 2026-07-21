# M6-A v2 fresh execution preflight

Status: **FAIL — authorization not generated; this is not an experiment result.**

The fresh preflight uses the immutable v2 manifest/lock and static Webots installation evidence only. It never starts Webots, creates a pilot attempt directory, writes an ownership marker, consumes authorization, or processes runtime artifacts.

Passes: the immutable manifest/lock reload, S1/seed 600100 one-episode identity, four snapshots, two methods, four frozen budgets (31,466 / 32,374 / 33,509 / 34,871 bytes), 32 future cases, static R2025a executable evidence, and repeated disposable-temporary launch-spec construction.

Failures that prohibit authorization:

- The production spec still binds `owned_root` to a disposable preflight directory instead of a unique, non-existing M6-A pilot attempt root.
- The wrapper expects an existing ownership marker; it does not atomically create one after authorization and before spawn.
- The authorization schema lacks consumed/launch-performed state and complete binding fields, so it is not a safe single-use authorization.
- No sole final-marker path is implemented after runtime reload, B5 processing, aggregate reload, and joint validation.

The corresponding machine-readable control report is written only under ignored `results/m6a_v2_control/`; it is not a runtime or scientific artifact. The next priority is to implement the missing production ownership/attempt-root/authorization/final-marker boundary, then repeat this fresh preflight.
