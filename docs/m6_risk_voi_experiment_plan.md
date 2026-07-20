# Milestone 6 Risk-Conditioned Visual VoI Experiment Plan

## Status and gate

This is a planning document only. It does not train an allocator, alter the frozen M5E-D data, or change the M5E protocol. M5E-E provides heterogeneous offline image-quality evidence, not a general Risk ROI win: Risk ROI is worse than Uniform and Object ROI at severe budget, better than Uniform and Center ROI at low budget, and the low-budget Risk-versus-Object interval crosses zero. M5E-F independent evidence validation and acceptance remains the required mainline gate before any M6 experiment begins.

## Baseline and objective

The frozen `Risk ROI` policy becomes the **Heuristic Risk ROI baseline**. It is trajectory-conditioned, geometry-grounded, and uses the combined planned/state image-risk mask to allocate tiled-JPEG quality. It is not a learned policy and is not a calibrated collision predictor.

For tile `i` and candidate quality `q`, the next allocator will estimate:

`VoI(i, q) = Delta U(i, q) / Delta B(i, q)`

`Delta U` is a held-out task or safety-relevant gain from upgrading that tile; `Delta B` is the increment in the actual complete encoded container bytes, including tile payload, index, and header effects. A candidate is admissible only when the final complete container remains within the frozen target-byte accounting rule.

## First downstream task

The first task should be **trajectory-critical obstacle recall**, evaluated from simulator ground-truth projected obstacle regions. It directly tests whether extra visual quality preserves obstacles relevant to the predicted corridor, while avoiding an unsupported jump to closed-loop collision claims. Free-space segmentation and clearance estimation are later candidates; control-decision consistency requires a defined remote controller and comes after a task signal is validated.

## Tile features and targets

Each tile-level record must contain immutable episode, scene, snapshot, method, and budget identifiers plus:

- planned risk, state risk, combined risk, and planned/state disagreement;
- trajectory-corridor clearance, TTCf, projected obstacle coverage, and visibility status;
- tile texture/edge complexity, current linear and angular velocity, budget, current quality, and actual incremental bytes;
- candidate quality, decoder/container metadata, and task label needed to compute `Delta U`.

The primary utility target is the change in trajectory-critical obstacle recall after a tile-quality intervention. Secondary targets may include projected-obstacle quality and calibrated error measures, but PSNR/SSIM alone cannot become the utility target.

## Data and split design

The current M5E dataset is insufficient for training a VoI model: it has only four method-level allocations per frame, not controlled tile-by-quality counterfactual outcomes. Generate a new, clearly separated M6 dataset of counterfactual tile-quality samples after M5E-F. Split by episode first and keep every snapshot from an episode in the same split; reserve entire scenario families for the final generalization test where feasible. Do not mix scene variants, seed families, or repeated reconstruction variants across train/validation/test.

An offline oracle should enumerate a bounded set of legal tile upgrades, encode complete containers, and compute held-out utility and actual incremental bytes. The oracle is a label generator and upper bound, never an online method. A deterministic greedy allocator should be evaluated first against Uniform, Center ROI, Object ROI, and Heuristic Risk ROI. A learned allocator may be considered only if the oracle/greedy study demonstrates stable held-out benefit under matched bytes.

## Ablations and failure criteria

Required ablations are planned-risk only, state-risk only, combined risk, no-disagreement, no-TTCf, no-clearance, no visual-complexity, and no-actual-byte feature. Report every frozen scene and budget, not selected favorable subsets.

Do not advance an allocator when it:

- improves only a small, post-hoc selected subset;
- exceeds matched-byte tolerance or relies on nominal rather than actual bytes;
- loses trajectory-critical recall to a baseline on held-out scenes without an explained trade-off;
- has utility gains dominated by one scene or one episode family;
- materially degrades background quality without a predeclared task benefit; or
- fails deterministic reconstruction, split-isolation, or no-future-actual checks.

## Sequencing

1. Complete M5E-F independently, preserving the M5E-E outputs.
2. Freeze the M6 counterfactual generator, split, utility label, byte accounting, and analysis protocol.
3. Generate and validate counterfactual tile-quality samples.
4. Benchmark oracle and greedy allocation against all four existing methods.
5. Consider a learned allocator only after the held-out greedy/oracle evidence is positive and stable.
6. Add a remote downstream perception task before closed-loop navigation.
7. Enter closed-loop navigation only after the task improvement is independently validated under byte matching.
8. Add latency, jitter, and loss only after the closed-loop baseline is stable; then repeat codec-independent validation before considering network simulators or complex neural codecs.

Sionna, ns-3, URVC, and neural codecs remain out of scope now: none resolves the demonstrated allocation heterogeneity, and each would confound the first causal test of visual value per actual byte.
