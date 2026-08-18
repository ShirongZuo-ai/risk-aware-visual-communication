# Evidence-backed manuscript review revision

Date: 2026-08-18

## Scope

This pass responds selectively to the external manuscript critique. It is a manuscript-only revision: no simulator run, experiment, statistic, figure datum, or scientific claim boundary was changed.

The revision is deliberately preserved as a separate author-review candidate:

- source: `paper/main_submission_review_revision.tex`
- bibliography: `paper/references_review_revision.bib`
- compiled review PDF: `paper/main_submission_review_revision.pdf`

The preceding `main_submission_figures_final` candidate and the standalone `paper/IROS_submission_final/` package remain unchanged.

## Changes accepted

1. **Concrete introductory motivation.** The Introduction now uses a two-constriction, one-packet example to distinguish future danger from the marginal value and opportunity cost of a transmission decision.
2. **More comparative Related Work.** The revision adds Directed-CP, R-ACP, the communication-aware robotics review, and predictive-latent communication/safety control. The comparison is bounded to the missing question addressed here: the causal marginal Safety Value of one visual packet under identical wire cost.
3. **Threshold provenance.** The manuscript now states that the frozen `Phi` and OLS-8 slope thresholds are one-sided 1% lower tails from stable no-change Q1 support; the conjunction was selected on fixed Q2/Q3 development traces and frozen before Q5 scenario construction.
4. **Mechanistic interpretation of Q6.5.** The revision explains that paired schedule reversals quantify finite-budget opportunity cost under identical prefixes and budgets. It explicitly avoids claiming an image-level mechanism that the experiment did not measure.

## Suggestions not adopted

- No claimed Table I confidence-interval correction was made because the alleged mismatch was not present in the authoritative source.
- No reported typo was changed without locating it in the authoritative source.
- The negative Q6.5 result was not rhetorically converted into a success. It remains a bounded boundary result: utility is measurable and distinct, but is not predictably solved by the tested state summaries.
- No new plot was fabricated from narrative-only step examples. The existing adjacent-opportunity panel already displays machine-supported helpful, harmful, and neutral cases.

## Verification

The candidate was built from the repository root's `paper/` directory using:

```text
pdflatex -interaction=nonstopmode -halt-on-error main_submission_review_revision.tex
bibtex main_submission_review_revision
pdflatex -interaction=nonstopmode -halt-on-error main_submission_review_revision.tex
pdflatex -interaction=nonstopmode -halt-on-error main_submission_review_revision.tex
```

Verified output:

- 5 US-letter pages;
- 11 bibliography entries;
- no overfull box;
- no unresolved citation or reference;
- no fatal LaTeX/BibTeX error;
- one benign underfull page-balance notice and three pre-existing narrow-table underfull notices;
- all five pages visually inspected after raster rendering, with no clipping, overlap, or figure-text overflow.

## Next priority

Author review of `paper/main_submission_review_revision.pdf`, followed by an explicit decision whether to promote this candidate into the standalone submission package.
