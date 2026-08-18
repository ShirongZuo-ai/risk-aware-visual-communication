# IROS Manuscript Figure Finalization Report

Date: 2026-08-18  
Scope: plotting and manuscript integration only; no scientific experiment was run and no result or claim was changed.

## 1. Chen Liu skill installation/path used

The primary design reference was Chen Liu's official `figures4papers` repository at `https://github.com/ChenLiu-1996/figures4papers`. Two read-only clone attempts were interrupted by a network reset, so no incomplete third-party checkout was installed or modified. The official GitHub raw files were instead read directly and used as the path-based design reference. The local implementation is the reproducible plotting script `paper/generate_submission_figures_final.py`.

## 2. Files from figures4papers consulted

- `scientific-figure-making/SKILL.md`
- `scientific-figure-making/references/design-theory.md`
- `scientific-figure-making/references/api.md`
- `scientific-figure-making/references/common-patterns.md`
- `scientific-figure-making/references/demos.md`

## 3. Figure demos used as references

- `figure_ImmunoStruct/plot_bars.py`: compact bar composition, direct values, sparse axes.
- `figure_CellSpliceNet/plot_comparison.py`: multi-panel comparison hierarchy.
- `figure_CellSpliceNet/plot_ablation.py`: restrained palette and annotation density.
- `figure_Cflows`: repository-level layout reference for wide quantitative panels.

No published figure was copied. The references informed typography, spacing, semantic color, annotations, and export policy only.

## 4. Paper-level style contract

- Semantic palette: gray = current/reference/baseline; blue = future prediction or principal R1 result; green = positive physical effect or supportive secondary result; red = adverse physical effect; amber = Safety Value or precursor.
- Meaning is never color-only: the figures also use signs, black/clear edges, markers, hatching, zero lines, and explicit direction labels.
- Typography: Arial, Helvetica, then DejaVu Sans fallback; no displayed figure text below 7 pt at the final 7.16-inch double-column width; at most three visible text levels.
- Quantitative axes: minimalist top/right spines, light grids only where useful, frameless or eliminated legends, direct annotations for exact values.
- Export: vector PDF is primary, SVG preserves editable text, and PNG is a 600-dpi review artifact.
- Decoration: no gradients, shadows, glow, glass, or 3-D effects.

The complete machine-readable contract is embedded in `paper/figures/figure_data_provenance_final.json`.

## 5. Old versus new Figure 1 assessment

The scientific structure was already correct and was preserved: sender observation and causal reasoning, finite-budget transmission, receiver hold/perception/control, and evaluator-only physical truth. The redesign is restrained rather than chart-like. It improves the sender/receiver/evaluator boundary, arrow direction, alignment, whitespace, typography hierarchy, and semantic color consistency. The central distinction, `Future Risk != Decision Value != Send Utility`, is now visually dominant. Box-bound checks verify that every box-owned label remains inside its box, and exterior labels do not intersect boxes.

Historical Figure 1 files and the historical generator were not overwritten.

## 6. Final Figure 1 paths

- `paper/figures/fig1_system_overview_final.pdf`
- `paper/figures/fig1_system_overview_final.svg`
- `paper/figures/fig1_system_overview_final.png`

## 7. Final Figure 2 paths and exact data provenance

Paths:

- `paper/figures/fig2_evidence_chain_final.pdf`
- `paper/figures/fig2_evidence_chain_final.svg`
- `paper/figures/fig2_evidence_chain_final.png`

Machine sources and displayed values:

- Motion prediction: `results/m2_trajectory/summary_metrics.csv`, filtered to `category=all_stable` and horizons 0.5/2.0 s. State-only ADE is `0.000120561`/`0.000715992` m; command-conditioned ADE is `0.000006398`/`0.000013655` m.
- Future danger: `results/m9b_formal/formal_results.json`. R0/R1/R2 AUPRC is `0.9063111357271314`/`0.9937300449778934`/`0.9997777010629078`. Primary R1-R0 is `0.08741890925076201`, with exact paired 95% CI `[0.07718078476424133, 0.09853406543813094]`, 10,000 valid replicates, 240 valid episodes, and zero exclusions.
- Q5 precursor: `results/cvc_q5_analysis/analysis.json`. Coverage is staggered slalom `3/4`, three-stage weave `5/5`, opposed gate contraction `3/4`, and reverse diagonal chicane `5/6`; aggregate `16/19 = 84.21%`; median lead `0.576 s`; IQR `[0.432, 0.776] s`; the artifact states `rule_changed_or_refit=false`.

## 8. Final Figure 3 paths and exact data provenance

Paths:

- `paper/figures/fig3_q6_closed_loop_final.pdf`
- `paper/figures/fig3_q6_closed_loop_final.svg`
- `paper/figures/fig3_q6_closed_loop_final.png`

The Q6 source is `results/cvc_q6_analysis/q6-g3-opportunity-persistent.json`. The comparison is development scheduler minus U0, and every episode uses exactly 72,000 serialized wire bytes. Family means are:

| Physical family | Danger-step delta | Minimum-clearance delta |
|---|---:|---:|
| Opposed gate contraction | -20.8 | +3.329769 mm |
| Reverse diagonal chicane | -8.4 | -3.863971 mm |
| Staggered slalom constraint | +26.2 | -14.040494 mm |
| Three-stage weave | -38.2 | +9.627778 mm |

Negative danger is safer; positive clearance is safer. Zero lines, direction text, signs, edges, and adverse hatching make this explicit. Staggered slalom remains visibly adverse on both measures.

## 9. Q6.5 visual decision

A compact Q6.5 mechanism panel was added as Figure 3(c), not as a fourth main figure. This uses the available wide layout, avoids a figure zoo, and replaces the need for a separate Q6.5 figure/table expansion. Its source is `results/cvc_q65_development/generation2_schedule_bank/analysis.json`, cell `q65-afs-01`. Adjacent opportunities are shown exactly as recorded: step 80 to 109 is neutral with danger delta 0; step 109 to 144 is helpful with danger delta -122; step 144 to 217 is harmful with danger delta +26. The panel materially supports the claim that packet utility can reverse across adjacent opportunities without implying that a scheduler was selected.

## 10. Scientific label corrections

- R2 is displayed as `0.9998`, rather than rounding to the misleading `1.000` used in an older visual.
- R0/R1/R2 are explicitly `current danger`, `state rollout`, and `command rollout`; R0 is not called state-only, and R2 is not called density.
- M2 ADE is identified as the `all_stable` stable-window result, not as a mean over 240 episodes.
- Q5 shows all four actual positive family names and exact fractions; it does not label families as seen/unseen.
- Q5 states `Frozen precursor; no refitting`, not `thresholds frozen from Slalom`.
- Q6 uses scheduler minus U0, names exact wire bytes, and states the safety direction for both metrics.
- Q6.5 is explicitly a development-only adjacent-opportunity example and is not presented as evidence of selected or generally superior scheduling.

## 11. Compiled manuscript path

- Source: `paper/main_submission_figures_final.tex`
- Compiled candidate: `paper/main_submission_figures_final.pdf`

The historical manuscript candidates remain unchanged.

## 12. Final page count

Five US-letter IEEE two-column pages.

## 13. Visual QA results

- All five pages were rendered and inspected at normal page scale.
- Figure text and captions are readable; no label, panel, box, or caption overlaps were found.
- No text is clipped or outside its intended panel/box.
- Figure 1 arrows and boundaries read cleanly with no line crossing through text.
- Figure 2 communicates the prediction-to-danger-to-precursor chain without a redundant global legend.
- Figure 3 makes the mixed strongest-baseline result and adverse slalom case immediately visible.
- The final page uses `ieeeconf.cls`'s `\IEEEtriggeratref{2}` rather than margin/font changes, removing both the earlier unbalanced-column whitespace and the `balance` overfull-vbox warning.
- The final LaTeX log has no overfull box, undefined-reference, missing-citation, or fatal warnings. Three benign underfull-hbox notices remain in the narrow summary table; visual inspection shows no overflow or readability defect.
- The plotting script performs programmatic canvas/text-bound checks and Figure 1 box-bound checks before saving.

## 14. Grayscale and print readability

Grayscale renders of all three figures were inspected. Baseline/prediction, supportive/adverse, and neutral/helpful/harmful meanings remain distinguishable through sign, position, outline, marker, hatching, zero reference, and direction text. PDF inspection reports no embedded raster image objects in the final figure PDFs; fonts are embedded/subset. SVGs retain text nodes. The final PNGs are 600 dpi review copies only.

## 15. Unresolved figure issues

No unresolved scientific-label, overlap, clipping, vector-export, grayscale, or final-size legibility issue was found. The only non-error compile notices are the three visually benign underfull table lines noted above. The controlled-scene scope and development-only Q6/Q6.5 evidence remain manuscript limitations, not figure defects.

## 16. IROS submission-quality assessment

Yes, the complete three-figure set is suitable for an IROS submission candidate: it is visually coherent, reproducible, vector-first, print-safe, scientifically traceable, and honest about adverse/null evidence. This is a figure-quality assessment, not a change to the manuscript's experimental claim strength or readiness decision.

## Reproduction and next priority

Run `D:\\Anaconda\\python.exe paper/generate_submission_figures_final.py` from the repository root, then compile `paper/main_submission_figures_final.tex` with `pdflatex`, `bibtex`, `pdflatex`, and `pdflatex` from `paper/`.

Next priority: perform an author-side 100% zoom and physical-print proof of the five-page candidate before selecting it as the authoritative submission manuscript.
