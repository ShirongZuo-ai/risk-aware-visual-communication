# M6-A v2 attempt-002 timeout diagnosis

Date: 2026-07-24 (Asia/Shanghai)

## Outcome

Attempt `m6a-prod-pilot-002` is permanently `failed_process` and remains
immutable. Its 75-second timeout was not evidence that the six simulated
seconds require a longer timeout. The launch package did not form a Webots
project in which `m6a_trusted_runtime` was discoverable.

The package launched:

```text
webots.exe --batch --mode=fast <prepared-workspace>/prepared.wbt
```

The world declared `controller "m6a_trusted_runtime"`, but the controller
existed only at the repository's `simulator/controllers/...` path. The prepared
workspace contained no `controllers/m6a_trusted_runtime/` directory. Webots'
retained template context for this exact launch recorded the project path as
`results/m6a_v2_control/prepared/`, not the repository root. It also recorded
the exact attempt-002 world. Thus the declared controller was outside the
project that Webots selected.

This diagnosis is consistent with all immutable process evidence: Webots was
spawned once, no runtime manifest or snapshot was produced, stdout and stderr
were empty, the host terminated the owned process after exactly 75 seconds,
and the terminal is `failed_process`. The old argv omitted Webots stdout/stderr
forwarding flags, which explains why the host logs could not diagnose Webots'
controller lookup.

## Adjacent lifecycle defects found before another launch

Repository tracing found three additional defects in the same required path.
They did not cause the first missing-controller condition, but would prevent a
future valid run from completing correctly after controller discovery:

- the controller never applied the frozen wheel-command schedule to the e-puck
  motors;
- the runtime summary writer rejected paths under the authoritative pilot root
  even when those exact paths were bound in the runtime config;
- the controller returned a Python status code but never called
  `Supervisor.simulationQuit(code)`, so a completed controller could leave the
  Webots process open until the host timeout.

The old launch spec also omitted output fields required by the existing
post-process completion handoff. The prepared runtime config already contained
the authoritative paths, so the fix propagates those paths rather than defining
a second path contract.

## Corrected lifecycle

For newly prepared packages only:

1. The producer creates one standard Webots project containing
   `worlds/prepared.wbt` and
   `controllers/m6a_trusted_runtime/m6a_trusted_runtime.py`.
2. The host validates the copied controller and source hashes, exact project
   layout, runtime path binding, shell-free argv, and environment.
3. The research runner exclusively owns the attempt, persists its research
   context and at-most-once launch claim, then spawns the declared process once.
4. Webots starts in batch fast mode with stdout/stderr forwarding and discovers
   the controller inside the prepared project.
5. The controller constructs a Supervisor, initializes the frozen scene before
   motion, applies the predefined wheel schedule before each 32 ms step,
   captures the four frozen snapshots, and continues to the frozen schedule end
   at 6.0 simulated seconds.
6. Runtime summary, status, diagnostic, and manifest artifacts are written only
   to their exact runtime-config-bound attempt paths.
7. The controller stops both motors and calls `simulationQuit(0)` after a valid
   runtime lifecycle, or `simulationQuit(1)` after a controlled failure.
8. The host records the actual process outcome. Only a normal zero exit advances
   to the existing 32-case aggregate, joint validation, final marker, and
   completed ownership terminal. No timeout or zero exit alone is scientific
   success, and no automatic retry is permitted.

## Timeout decision and remaining uncertainty

The timeout remains 75 seconds. The scientific schedule is 6.0 simulated
seconds, the last snapshot is at 5.408 seconds, and `--mode=fast` does not impose
real-time pacing. Repository evidence does not show that a valid run needs more
than 75 wall-clock seconds. A separately approved disposable Webots smoke is
still required to confirm R2025a controller discovery, camera/device names,
wall-clock performance, and normal main-process termination on this machine.
