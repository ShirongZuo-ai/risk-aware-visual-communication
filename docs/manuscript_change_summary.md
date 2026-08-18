# Manuscript change summary

Date: 2026-08-16

## Preserved

- The original draft under `LaTex/` remains unchanged.
- Existing experiments, frozen manifests, result JSON files, protocol documents, Webots worlds/controllers, and access ledgers were not modified.
- Negative and mixed findings were retained rather than reframed as a successful final scheduler.

## Corrected

- Replaced the obsolete tile-allocation narrative with the actual causal chain: future danger, feasibility precursor, Safety Value, and matched-wire closed-loop utility.
- Corrected the predictor description from a learned model to deterministic differential-drive rollout.
- Corrected score semantics: R0 is current-clearance danger, R1 is state-only 2-s rollout danger and the primary signal, and R2 is command-scheduled rollout danger and secondary.
- Added the exact soft-feasibility mass, OLS slope, frozen precursor rule, and the decision-level Safety Value conditions.
- Separated Q5 precursor qualification from Q6 packet-utility evidence and explicitly bounded causal information access.
- Replaced unsupported success language with the exact Q6 mixed result against U0 and the stronger conclusion that relevance does not guarantee send utility.
- Removed unverified and overly broad novelty claims; retained seven references verified from primary or institutional sources.

## Added

- A new submission manuscript with exactly three contributions.
- Three reproducible vector figures and a one-table evidence boundary.
- Exact-byte budget definition and receiver hold semantics.
- Limitations covering simulator-only evidence, controlled perception, one robot, system-specific thresholds, no selected final scheduler, no Q7/Formal scheduler study, and no hardware validation.
- Machine-readable claim provenance and build/visual-QA records.

## Build outcome

- PDF: 5 pages, US Letter, 3 figures, 1 table, 7 references.
- Abstract: 185 words.
- Build: successful; no overfull boxes or unresolved references/citations.
- Visual QA: all pages inspected; all boxed figure text fits within its box.
