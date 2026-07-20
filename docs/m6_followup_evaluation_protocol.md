# M6 Follow-up Baseline and Ablation Protocol v1

Last updated: 2026-07-20 (Asia/Shanghai). Design only; no new experiment is authorized by this document.

## Gate and research question

M5 is frozen after M5E-F acceptance. This protocol requires a new, independent M6 dataset; it must not modify or reuse M5E-D formal rows for tuning or training. The first question is: under equal **complete actual container bytes**, which predeclared visual allocation policy best preserves a predeclared trajectory-critical downstream signal on held-out episodes?

No policy may claim safety, collision reduction, or navigation success until a separately frozen closed-loop experiment measures those outcomes.

## Baseline matrix from currently recorded related-work notes

`related_work.md` deliberately contains direction names rather than verified paper-level technical notes. The unknown cells below are explicit evidence gaps, not inferred literature claims. No web search was performed.

| Paper/method note | Task / ROI / trajectory / risk | Codec / constraints / metrics | Code/data | Relation and reproducibility | Category and action |
| --- | --- | --- | --- | --- | --- |
| Uniform tiled JPEG | Navigation-image quality; no ROI, no trajectory/risk | Existing RAVCJT1, complete-byte matching; frozen M5 metrics | Local implementation | Directly reproducible | Must implement/retain: reference fairness baseline |
| Fixed Center ROI | Navigation-image quality; fixed image center, no trajectory/risk | Existing allocator and matched bytes | Local implementation | Directly reproducible | Must implement/retain: geometric prior baseline |
| Object ROI / semantic-object ROI coding | Existing eligible projected objects; no future trajectory in score | Existing allocator and matched bytes | Local implementation; external paper details unverified | Directly reproducible as Object ROI | Must implement/retain: strong task-region baseline |
| Heuristic Risk ROI | Planned/state trajectory and heuristic TTCf/clearance risk | Existing allocator and matched bytes | Local implementation | Directly reproducible | Treatment baseline, not a proven winner |
| CV-Cast; GOSC/ISAC; safety-guaranteed goal-oriented communication | Details not yet source-backed in this repository | Details not yet source-backed | Unknown | Cannot fairly reproduce yet | Related-work citation; import checked notes before baseline claims |
| URVC; TouchSafeBench; Shared 3D Semantics; teleoperation QoC; event-based navigation | Details not yet source-backed in this repository | Details not yet source-backed | Unknown | Not currently reproducible | Borrow experiment-design ideas only after source review |

## Predeclared methods and ablations

| Experiment | Research question | Variables / controls | Metrics and comparison | Success criterion | New data / cost / priority |
| --- | --- | --- | --- | --- | --- |
| B0: fairness rerun | Are baseline implementations deterministic and byte matched on new data? | Method varies: Uniform, Center, Object, Heuristic Risk; hold scenes, codec, image size, seeds, budgets, split fixed | Complete bytes, decode validity, target tolerance, task signal | All artifacts valid; no method exceeds byte rule | Yes / low / P0 |
| A1: command removal | Does future command add value beyond state-only motion? | Combined Risk vs State-only trajectory ROI; same mask/raster/allocator | Episode-level trajectory-critical recall; paired bytes and quality | Held-out, scenario-stratified benefit with CI excluding zero and no byte violation | Yes / medium / P0 |
| A2: corridor removal | Is uncertainty corridor useful? | Combined Risk vs no uncertainty corridor | Same as A1 plus failure cases | Benefit is not isolated to one scene family | Yes / medium / P0 |
| A3: footprint removal | Does robot footprint change useful allocation? | Combined Risk vs point-robot risk | Same as A1 | Predeclared paired benefit without degraded baseline task metric | Yes / medium / P1 |
| A4: static ROI | Does dynamic projection beat a fixed ROI? | Dynamic Risk vs fixed first-snapshot Risk | Same as A1, reported by snapshot | Benefit persists across held-out episodes | Yes / medium / P1 |
| A5: horizon | Which fixed prediction horizon is robust? | Predeclare 2–3 horizons before generation | Same metrics, multiplicity reported | Select only on validation, lock before test | Yes / medium / P1 |
| U0: oracle upper bound | What headroom remains? | Offline oracle with legal tile upgrades only | Task utility per actual incremental byte | Upper bound only; never deploy or call a baseline | Yes / high / P2 |

Visual-saliency/object baseline is retained only when it can use the same frozen image input, complete-byte accounting, and allocation backend. The oracle is nondeployable. No learned model is included in this protocol.

## Dataset, unit, metrics, and analysis

Generate new M6 episodes under a versioned manifest with episode-level train/validation/test separation; keep all snapshots from an episode together and reserve held-out scene families where feasible. Preserve scene, seed, budget, and snapshot alignment for every paired comparison. Aggregate snapshots within an episode before inference and use a scenario-stratified episode-level bootstrap. Never treat frames as independent episodes.

Primary metric: simulator-ground-truth **trajectory-critical obstacle recall** after reconstruction, with a predeclared detector/measurement procedure. Secondary metrics: risk-support/object quality, full-frame/background quality, actual complete bytes, decode validity, and allocation determinism. A navigation-success or collision metric becomes primary only in a new closed-loop protocol with controller, stopping rule, and safety accounting frozen before data generation.

## Entry decision

The first execution item is B0 plus A1 on independent data, because it directly tests the untested command-conditioned versus state-only causal claim while preserving the strong Uniform/Center/Object/Risk comparison and byte fairness. Do not start Risk-VoI training: it requires the separate counterfactual data and oracle/greedy validation already described in [the M6 VoI plan](m6_risk_voi_experiment_plan.md).

M6-A v1 now freezes the independent manifest and preflight for this first item; see [M6-A preflight](m6a_preflight_report.md). It does not authorize a Webots pilot or formal run by itself.
