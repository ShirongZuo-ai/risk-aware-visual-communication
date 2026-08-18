# CVC-Q2 Development Protocol

Study identity: `cvc-q2-risk-arm-safety-value-spend-v1`. This is development-only and not Formal.

## Fixed task and cells

Q2 reuses the Q1 v2 planner, calibrated visual geometry, causal obstacle memory, controller information boundary, ten frozen physical-support cells, seeds, goals, duration, and physical labels without modification. The primary operating point is three exact 24,000-byte packets per 10 s episode because it is the smallest isolated startup/adaptive/reserve design inside Q1's preidentified 3-6 packet transition band.

## Policies

- U0 transmits uniformly at steps 0, 156, and 311.
- A0 uses current decoded sender-frame red-component apparent proximity R0 to ARM.
- A1 uses the existing causal constant-growth `predictive_risk` R1 to ARM.
- Both adaptive policies share threshold 0.14, event code, deadline, fallback, reserve, codec, perception, planner, and exact charged bytes. Risk crossing only changes `NORMAL -> ARMED`; it does not SEND.

Adaptive methods transmit startup at step 0, at most one adaptive packet, and a protected reserve at step 249. An ARM may wait 47 steps (one 1.5 s Q1 horizon rounded to 32 ms steps). It then uses a common deadline packet. If never armed, step 248 is the common unarmed fallback. No future debt exists.

## Safety Decision Value v1

HELD and hypothetical decoded CURRENT images pass through the same Q1 perception, odometry transform, causal-memory preview, and frozen planner. The hierarchy is:

1. safety-class deterioration or loss of all moving safe actions;
2. selected action changes because the HELD-selected action is removed from the CURRENT hard-safe set;
3. at least one-third of HELD hard-safe actions are removed and the same HELD-selected candidate loses at least 0.01 m conservative margin.

Ordinary goal-efficiency action changes do not trigger. Action equivalence tolerance is `1e-9`. The 0.01 m margin tolerance is a planner-stability quantity: it exceeds numerical noise and is one-fifth of the fixed 0.05 m hard-to-preferred band. Infinite obstacle-free margins are categorical bounded/unbounded transitions, never coerced into finite means.

## Information boundary

Sender/policy code may use raw/current decoded RGB, mirrored receiver HELD image, deterministic perception, command odometry/history, frozen planner, current budget/state, and causal R0/R1. It may not import or read Webots pose/object geometry, evaluator clearance/contact, future motion/outcomes, physical labels, or policy success. Shadow CURRENT packets are uncharged.

## Offline gate

The frozen Q1 U0-6 counterfactual planner traces qualify the event semantics without evaluator fields. Preserved P6 causal sender traces qualify common R0/R1 ARM timing without physical outcomes. All eight gates must pass: R1 earlier where expected; ARM alone does not spend; distractor rejection; narrow-passage detection; common event logic; intact reserve; exact cost; and schedule distinction from readiness lead.

## Outcomes and terminal classification

Primary physical outcomes remain separate: collision, near, safe, and minimum-clearance distribution. Task success, progress, completion time, and path efficiency remain separate. Mechanistic traces retain ARM, value event, SPEND cause, deadline/fallback, reserve, image age, HELD/CURRENT sets/classes/actions/margins, receiver action, wheels, clearance, and contact.

The literal mechanism, predictive-value, safety-path, and A/B/C/D rules are in `config/cvc_q2_development.json`. They were frozen before Q2 outcomes. Q2 runs exactly one 10-cell U0/A0/A1 matrix and then stops. It authorizes no threshold repair, scenario replacement, ML, broader validation, C4/C5 Formal, commit, or push.
