# CVC-Q6.5 — Communication Opportunity Value

Status: development protocol frozen before any Q6.5 paired branch outcome was generated.

## Question

At a causally detected communication opportunity, what is the marginal physical safety value of consuming the single adaptive 24,000-byte packet now instead of preserving it for the next causally detected opportunity?

Q6.5 is a new development study. Q1–Q6 and M9 evidence is historical and read-only. Q6.5 uses new scenario identities, seeds, jobs, traces, summaries, and analysis artifacts.

## Intervention

Every 10 s episode has 312 control steps at 32 ms and exactly three complete 24,000-byte packets: startup at step 0, one adaptive packet, and a protected reserve at step 218. Total cost is exactly 72,000 serialized wire bytes.

A discovery replay uses the same startup/hold prefix and sends its adaptive packet only at the frozen fallback (step 217). Candidate opportunities are the first two causal onsets, after step 24 and before step 181, of either (a) the frozen Q5 precursor with two-step persistence or (b) frozen Q1/Q2 Safety Value. Onsets must be at least 16 steps apart. If fewer than two onsets exist, fixed causal clock opportunities at steps 80 and 144 fill the missing ranks; they are marked `clock_fallback`, not presented as detected events.

For each frozen candidate step `t`, deterministic replay creates:

- `S`: transmit the adaptive packet at `t`;
- `H`: hold at `t`, preserve the packet, and transmit at the first later causal onset at least 16 steps after `t`, or at step 217 if no such onset occurs.

Both branches use the same seed, geometry, controller, planner, codec, packet size, reserve, and continuation rule. Rows strictly before `t` must match on sender state, receiver state, planner state, wheel commands, odometry, and evaluator state. A pair is invalid if prefix identity, exact byte accounting, or receiver mirroring fails. No oracle later-send time is available to `H`.

## Offline utility target

Let deltas be `S - H`. The frozen 0.12 m near-danger boundary remains unchanged.

1. If collision differs, the non-colliding branch is safer.
2. Otherwise, at least 3 control steps (96 ms) less near-danger exposure is safer.
3. Otherwise, at least 0.001 m greater minimum clearance is safer.
4. Otherwise the opportunity is safety-neutral.

The label is `helpful`, `harmful`, or `neutral` for SEND NOW. Goal progress and task success are reported as non-compensatory guardrails. A safety-helpful send with more than 0.05 m progress loss is flagged `task_adverse`; its safety label is not rewritten.

The 3-step and 1 mm indifference bands are physical/practical tolerances fixed before Q6.5 outcomes, not fitted thresholds.

## Causal feature boundary

Predictor inputs may be computed only from the branch-common prefix through the decision instant before the communication action. Allowed inputs include R0/R1 and their causal histories, Q5 precursor state/history, Safety Value state/history, held/current planner margins and safe-set sizes, selected-action stability, image age, time since send, remaining packet count, and recent wheel commands. Family name, cell ID, seed, evaluator clearance/contact, branch outcomes, and future values are forbidden.

## Support gate

Predictor fitting is allowed only if the new paired corpus contains at least 6 helpful, 6 harmful, and 6 neutral opportunities, with helpful and harmful support each spanning at least 3 physical families. Multiple probes from one cell remain grouped together for all splitting and inference.

## Development model and scheduler gate

The initial model hierarchy is: preregistered simple rules, regularized logistic/multinomial regression, and a shallow tree. Family-held-out results, calibration, false-send/false-hold rates, realized utility, runtime, and per-family failure are required. A temporal neural model is not authorized unless static models fail for a documented history-dependent mechanism.

A scheduler may be integrated only after the opportunity label is predictably separated on new development evidence. A method may be frozen only if matched-byte closed-loop development improves danger burden and minimum clearance versus U0, does not increase collision, and has no severe family with both worse mean danger and worse mean clearance. Independent Q7 remains unopened until that freeze.

