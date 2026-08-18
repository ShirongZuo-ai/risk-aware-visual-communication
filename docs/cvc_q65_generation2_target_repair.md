# CVC-Q6.5 Generation 2 — Adjacent-Opportunity Target Repair

Frozen before generation-2 schedule-bank outcomes were read.

Generation 1 is preserved and rejected: its labels often compared step 80 with fallback step 217, while the strongest U0 baseline transmitted at step 109. The predictor therefore answered a different intervention question from the closed-loop primary comparison.

Generation 2 changes only the intervention target. For every existing Q6.5 development cell, four independent deterministic schedules transmit at `[0,80,218]`, `[0,109,218]`, `[0,144,218]`, and `[0,217,218]`. The three opportunity labels are adjacent comparisons:

- step 80: SEND at 80 versus preserve to 109;
- step 109: SEND at 109 versus preserve to 144;
- step 144: SEND at 144 versus preserve to 217.

All branches remain exactly 72,000 serialized bytes. Prefix identity is required before the earlier step. The utility hierarchy and tolerances remain unchanged: collision, then a 3-step danger difference, then a 1 mm minimum-clearance difference, otherwise neutral. No threshold is refit.

The same strictly causal 23 features and the same model hierarchy/gates are used. Features are computed from the no-adaptive-send discovery replay at the earlier step. Physical family and cell identity remain forbidden. Leave-one-family-out validation remains mandatory.

If a model passes, a generation-2 scheduler considers opportunities only at steps 80, 109, and 144, sending at the first predicted-positive opportunity, otherwise at 217. The unchanged development closed-loop gate versus U0 applies. Generation 1 artifacts and failure remain part of the ledger.

