# IROS Submission Package

This folder is the standalone, author-review package for the current five-page
IROS manuscript candidate. It was assembled on 2026-08-18 without running new
experiments or changing reported scientific results.

## Start here

- Final paper source: `paper/main.tex`
- Final compiled paper: `paper/main.pdf`
- Bibliography: `paper/references.bib`
- Figure/data audit: `docs/manuscript_figure_finalization_report.md`
- Manuscript audit: `docs/manuscript_finalization_report.md`
- Claim-to-evidence map: `docs/claim_evidence_matrix.md`

## Folder layout

```text
IROS_submission_final/
|-- README.md
|-- SHA256SUMS.txt
|-- docs/
|   |-- claim_evidence_matrix.md
|   |-- manuscript_figure_finalization_report.md
|   `-- manuscript_finalization_report.md
|-- paper/
|   |-- main.tex
|   |-- main.pdf
|   |-- main.bbl
|   |-- references.bib
|   |-- ieeeconf.cls
|   |-- IEEEtran.bst
|   |-- generate_submission_figures_final.py
|   `-- figures/
|       |-- fig1_system_overview_final.{pdf,svg,png}
|       |-- fig2_evidence_chain_final.{pdf,svg,png}
|       |-- fig3_q6_closed_loop_final.{pdf,svg,png}
|       `-- figure_data_provenance_final.json
`-- results/
    `-- only the five machine-readable artifacts consumed by the figure script
```

## Compile the paper

From `paper/`:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The expected output is a five-page US-letter PDF at `paper/main.pdf`.

For Overleaf or a conference source upload, upload the contents of `paper/`.
The PDF figures are the submission masters. SVG files are editable masters and
PNG files are 600-dpi review previews.

## Regenerate the figures

From the package root:

```powershell
python paper\generate_submission_figures_final.py
```

The script reads only the copied artifacts under `results/`, verifies the exact
displayed values, and rewrites the `paper/figures/*_final` exports. The Python
environment needs Matplotlib and NumPy. Figure regeneration is plotting-only;
it does not rerun Webots or any scientific experiment.

## Integrity and scope

`SHA256SUMS.txt` records every version-controlled delivery file except itself.
Local LaTeX auxiliaries, logs, Python bytecode, and archives are intentionally
excluded from the Git checkpoint. The package keeps
the manuscript's existing evidence boundaries: Q6 and Q6.5 are bounded
development results, no safer scheduler is claimed, and no Q7/Formal or
real-robot validation is represented.
