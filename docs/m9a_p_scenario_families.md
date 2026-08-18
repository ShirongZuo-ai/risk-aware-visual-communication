# M9-A-P Scenario-Family Specification

Status: proposed parameter ranges; no episodes generated. SI units are meters, seconds, radians, and radians/second. Obstacles remain static, upright AABBs for compatibility with frozen M3 geometry.

## Common constraints

- e-puck start center: `x in [-0.10, 0.10]`, `y in [-0.12, 0.12]`, yaw in `[-0.35, 0.35]` relative to the family reference direction.
- Wheel commands: each wheel in `[0.5, 5.0] rad/s` while moving; zero is allowed for braking/stop segments. Reverse motion is excluded from M9-A v1.
- Command segments: duration `[0.32, 3.0] s`; transitions align to simulator steps; total episode approach duration `[3.0, 8.0] s` plus required post-event recording.
- Primary obstacle footprint: width/depth `[0.025, 0.080] m`; height `[0.04, 0.10] m`; center placed `[0.10, 0.40] m` from the initial robot center.
- Distractors: one to three AABBs, at least one physical robot radius outside the intended actual swept footprint; placement is outcome-blind and logged.
- Every family has matched configurations sharing start pose, speed class, obstacle dimensions, and schedule skeleton; only the preregistered role parameter changes.
- The finite parameter grids and seed-to-parameter mapping are frozen before pilot generation. Formal literal parameters are derived and locked then; pilot may invalidate the protocol but cannot regenerate/filter formal combinations.
- No R0/R1/R2 output is computed during scenario materialization or used to accept, reject, or reposition an obstacle.

## Families

| ID | Family | Required roles and controlled variation |
|---|---|---|
| F1 | Straight approach | Collision: obstacle center intersects straight swept footprint. Near: lateral offset selected by calibration role range. Safe: larger preregistered offset. Constant command. |
| F2 | Curved approach | Left/right constant unequal-wheel arcs; collision/near/safe change radial obstacle offset while preserving arc and speed. Both turn directions balanced. |
| F3 | Turn toward danger | Initially safe current trend, then scheduled turn toward obstacle within 0.25-1.50 s of an eligible decision interval. Collision/near/safe vary turn magnitude from a locked grid. |
| F4 | Turn away from danger | Initially threatening current trend, then scheduled turn away. Includes collision when too late, near-miss, and safe avoidance. This is essential for false-warning and R2-versus-R1 behavior. |
| F5 | Brake/speed change | Straight or shallow arc followed by slowdown/stop at a locked transition time. Roles vary braking onset, not post-outcome obstacle placement. Includes insufficient, marginal, and early braking. |
| F6 | Opposite-turn transition | Forward-left to forward-right and mirrored schedules near an obstacle; balances direction and transition timing. Designed for legitimate R1/R2 disagreement, not an R2 win. |
| F7 | Primary plus distractors | F1/F2 primary event with off-path large/small distractors. Roles remain collision/near/safe for the primary; distractor layouts are balanced and cannot become unlogged events. |
| F8 | Low-risk matched control | Same start/speed/command complexity as F3-F6 but all obstacles remain outside the calibrated near zone. The three manifest roles are safe-near-boundary, safe-mid, and safe-far; this family contributes safe controls rather than forced collisions. |

F8 is the only exception to the universal 4/4/4 and 6/6/6 role allocation: its nominal collision and near-miss slots are replaced by matched safe-near-boundary and safe-mid controls. Consequently the matrix-wide minimum collision/near counts, rather than nominal totals, governs support.

## Outcome-independent role construction

Pilot may repeat engineering attempts but cannot change a frozen grid in place. If feasibility fails, a reviewed protocol-version amendment replaces all ungenerated split authorities. Calibration may select `d_near` but may not reposition completed episodes. Formal manifests contain literal parameter values, not a generator instruction conditioned on predicted risk or observed clearance. Random jitter is derived solely from the episode seed and a documented deterministic generator.

## Episode termination

- Collision: terminate after first qualifying contact plus five successfully logged steps.
- Near-miss: terminate after the unique minimum-clearance region has been passed and clearance has increased for at least ten steps, with no contact.
- Safe: terminate after passing the primary obstacle or completing the planned maneuver plus ten steps.
- Timeout at 10 s is a technical failure unless the manifest explicitly declares a shorter family limit.

Multiple disjoint danger episodes are prohibited. If an unexpected second event occurs, retain and flag the episode; do not count it as two independent primary events or replace it. The formal analysis must report such protocol deviations.
