# Final manuscript engineering report

Date: 2026-08-16  
Authoritative evidence repository: `C:\Users\ROG\Documents\risk-aware-visual-communication`  
Draft input: `C:\Users\ROG\Downloads\risk-aware-visual-communication-initial\LaTex\main.tex`

## Deliverables

- Submission source: `paper/main_submission.tex`
- Bibliography: `paper/references.bib`
- Compiled paper: `paper/main_submission.pdf`
- Reproducible figure generator: `paper/generate_submission_figures.py`
- Figures: `paper/figures/fig1_system_overview.pdf`, `fig2_evidence_chain.pdf`, and `fig3_q6_closed_loop.pdf`
- Claim provenance: `results/manuscript_claim_provenance.json`
- Change summary: `docs/manuscript_change_summary.md`

The original draft was preserved. No experiment, frozen evidence, formal-access record, protocol, scheduler, or simulator artifact was changed.

## Submission form

- Title: *From Future Danger to Communication Value: Risk-Aware Visual Communication for Robot Navigation*
- Format: IEEE conference, US Letter, two columns
- Length: 5 pages including references
- Abstract: 185 words
- Content inventory: 3 figures, 1 table, 7 references, exactly 3 stated contributions
- Recommended first venue: IROS. The current simulation-only, mechanism-focused contribution fits a conference paper better than an RA-L submission; RA-L would benefit from a selected scheduler, a sealed confirmatory closed-loop study, and hardware validation.

## Evidence and claim audit

The manuscript distinguishes three non-equivalent quantities: future physical danger, decision-level visual Safety Value, and the immediate utility of transmitting a finite-cost packet. It reports the sealed M9-B result, the frozen Q5 precursor qualification, and the exact-byte Q6 closed-loop intervention. Q6 is presented as mixed/negative against the stronger uniform-timing control; no final scheduler, Q7, formal scheduler result, real-robot result, or general safety improvement is claimed.

The trajectory predictor is correctly described as deterministic differential-drive kinematics. The primary R1 score is state-only 2-s rollout danger; command-scheduled R2 is secondary. Citation metadata was checked against primary publication pages or institutional records, and broad priority claims were removed.

## Build and visual QA

`pdflatex -interaction=nonstopmode -halt-on-error main_submission.tex` completed successfully. The final log contains no undefined references, missing citations, overfull boxes, TODO, TBD, or FIXME markers. One benign underfull box remains inside the compact evidence table and is visually acceptable.

All five rendered pages were inspected. Figures have no clipped labels, overlaps, or unreadable axes. In particular, every label placed inside a drawn box in Fig. 1 remains within that box with visible padding. Figure sources are vector PDF; PNG companions are retained for quick inspection.

## Reproducibility boundary

The manuscript is a paper-engineering snapshot of the current verified evidence. Source hashes and exact numerical provenance are recorded in `results/manuscript_claim_provenance.json`. Rebuilding figures or the PDF does not regenerate experiments. The authoritative repository remained dirty with pre-existing research work, and no commit or push was performed.

## Next priority

Before submission, obtain a human author/affiliation review and run the venue's official PDF compliance checker. Scientifically, the next priority remains a preregistered confirmatory scheduler study only after a method is selected; this manuscript does not imply that step has occurred.
