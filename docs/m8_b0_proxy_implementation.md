# M8-B0 Offline Proxy Primitive Implementation

## Status

FROPU, STRCF, and CCORF are operational as deterministic offline primitives. This is unit validation only. FROPU and STRCF remain unvalidated candidates, CCORF remains an evaluator-only calibration reference, no candidate is selected, and no allocator or corpus is authorized.

## Production boundaries

The implementation is divided into four explicit layers:

- `scripts/m8_proxy_common.py`: canonical identity, array validation, persistence, digest, and synthetic sequence diagnostics;
- `scripts/m8_sender_proxies.py`: sender-only FROPU and STRCF inputs, computations, evidence, and validators;
- `scripts/m8_evaluator_reference.py`: evaluator-only CCORF input, computation, evidence, and validator;
- `scripts/validate_m8b0_proxies.py`: synthetic qualification-harness rehearsal; this is the only production-side module that imports both boundaries.

The sender module does not import CCORF or evaluator geometry. Its factories reject actual future trajectory, future frames, ground-truth obstacle geometry, TCOBR, eligibility, CCORF, evaluator masks, navigation outcomes, and unknown fields. CCORF requires an explicit evaluator geometry digest and records `evaluator_input_usage=1`; FROPU and STRCF require `evaluator_input_usage=0`.

Every input is bound to `m8-proxy-identity-v1`, containing identity, split, scene, episode, seed, snapshot, and reconstruction IDs. Evidence reload may require an exact expected identity and optionally recompute the complete evidence from the original validated input. Missing fields, identity mismatch, wrong `120 x 160 x 3` RGB shape, wrong mask/field shape, non-`uint8` RGB, non-finite or out-of-range fields, noncanonical JSON, digest tampering, fallback, replacement, and future/evaluator leakage fail closed.

## Operational schemas

| Primitive | Input type | Evidence schema | Boundary | Status field |
| --- | --- | --- | --- | --- |
| FROPU | `FROPUInput` | `m8-fropu-evidence-v1` | sender-visible only | `unvalidated_candidate` |
| STRCF | `STRCFInput` | `m8-strcf-evidence-v1` | sender-visible only | `unvalidated_candidate` |
| CCORF | `CCORFInput` | `m8-ccorf-evidence-v1` | evaluator only | `evaluator_reference_only` |

Canonical JSON uses sorted keys, compact separators, UTF-8, no NaN/Infinity, and exactly one LF. SHA-256 covers the canonical object without its `canonical_digest` field. Array digests bind dtype, shape, and row-major payload SHA-256. Persistence refuses overwrite; reload rejects CRLF, noncanonical serialization, digest mismatch, identity mismatch, and internal score inconsistency.

## FROPU

FROPU implements the frozen M8-A fixed RGB pipeline exactly:

- grayscale, `3 x 3` Gaussian blur, Canny `50/150`, one `3 x 3` close, external contours;
- width/height at least 3 pixels, contour area at least 16 pixels, and at least 8 Canny-supported contour-boundary pixels;
- proposal order `(top, left, height, width)`;
- confidence `min(1, edge_count/32) * min(1, area/128)`;
- relevance `0.10 + 0.90 * corridor_overlap` over filled contour support;
- maximum bounding-box IoU matching with lower proposal ID tie-break;
- fidelity `0.40 IoU + 0.30 exp(-centroid_distance/20) + 0.30 one-pixel-boundary-recall`;
- confidence/relevance-weighted mean, or explicitly undefined when the original has no proposals.

Evidence persists both proposal sets, boundary/support digests, all matches and components, weights, input/config/identity digests, and the final score.

## STRCF

STRCF independently normalizes the sender-time union risk and uncertainty fields to `[0,1]`, uses spatial weight `0.05 + 0.475 risk + 0.475 uncertainty`, and computes the exact frozen color and Sobel-gradient fidelity terms. It persists the weighted color, gradient and combined scores, normalization maxima, weight sum, field digests, and canonical provenance. Constant risk/uncertainty fields remain defined through the 0.05 floor.

## CCORF

CCORF accepts only evaluator-isolated critical-obstacle and boundary masks plus their geometry digest. Eligibility requires at least 64 projected pixels and 16 original Canny boundary-edge pixels. Defined evidence combines:

- 50% soft reconstructed-edge distance fidelity, `exp(-min(distance, 5)/1.5)`;
- 30% frozen-parameter SSIM response averaged inside the critical obstacle and mapped from `[-1,1]` to `[0,1]`;
- 20% inverse normalized RGB error inside the critical obstacle.

Ineligible evidence remains undefined with an explicit exclusion reason. CCORF is not imported by the sender module and may not be passed to an allocator.

## Synthetic perturbation validation

The repository-owned fixture contains one corridor-intersecting obstacle, an off-corridor distractor, sender-time risk/uncertainty fields, and isolated evaluator masks. The deterministic panel covers perfect reconstruction, blur, JPEG quality 15, contrast loss, localization shift, internal occlusion, and irrelevant-background blur.

| Perturbation | FROPU | STRCF | CCORF |
| --- | ---: | ---: | ---: |
| Perfect | 1.0000 | 1.0000 | 1.0000 |
| Blur | 1.0000 | 0.8234 | 0.4999 |
| JPEG q15 | 0.9851 | 0.8560 | 0.7870 |
| Contrast loss | 0.9100 | 0.8034 | 0.4666 |
| Localization shift | 0.6523 | 0.8168 | 0.6174 |
| Internal occlusion | 1.0000 | 0.9056 | 0.8902 |
| Irrelevant-background blur | 0.9100 | 0.9378 | 1.0000 |

The irrelevant-background case leaves CCORF effectively unchanged while critical degradations lower it. FROPU responds strongly to localization shift but is blind to this fixture's blur and internal occlusion because the external proposal contour remains unchanged. That limitation is retained, not tuned away.

On the deterministic JPEG ladder `(5,15,35,55,75,95)`:

- FROPU: range `0.0843`, endpoint fraction `0.50`, Spearman `0.6983`, not monotone;
- STRCF: range `0.1248`, endpoint fraction `0.00`, Spearman `1.0000`, monotone;
- CCORF: range `0.1381`, endpoint fraction `0.00`, Spearman `0.8857`, not monotone.

These are single-fixture diagnostics, not G2/G3 decisions. The frozen gates require episode- and scene-level evidence from the future 810xxx calibration corpus. In particular, FROPU's synthetic saturation and all three sub-0.15 ranges remain unresolved calibration risks.

## Validation and reproduction

Run without Webots:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_m8_proxy_primitives
.\.venv\Scripts\python.exe -m scripts.validate_m8b0_proxies --check
```

Machine-readable evidence is `docs/results/m8_b0_unit_validation.json`, schema `m8-b0-unit-validation-v1`. It states `scientific_qualification=NOT_EVALUATED_REQUIRES_810XXX_CALIBRATION` and `candidate_selection=NOT_PERFORMED`.

## Remaining qualification work

M8-B0 establishes operational definitions, boundaries, tamper detection, and deterministic synthetic behavior. It does not establish detector recall, cross-scene dynamic range, CCORF association, ranking concordance, critical specificity, scene stability, incremental validity over full-frame PSNR, or any scientific benefit. Those questions require the separately frozen and approved 810xxx calibration corpus before allocator development can be considered.
