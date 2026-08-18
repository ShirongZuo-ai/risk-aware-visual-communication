# Q6.5 Generation 2 — Safety-Asymmetric Multiclass Gate

Frozen before multiclass scores were computed.

The adjacent-opportunity corpus contains helpful, harmful, and neutral labels, but the binary model merged harmful with neutral and exceeded the frozen harmful false-send limit. One final bounded interpretable model is authorized: L2 multinomial logistic regression with C in the already bounded set `{0.1, 1.0}`.

The online action rule is fixed without threshold search:

`SEND iff P(helpful) >= 0.50 and P(harmful) <= 0.25`.

The same leave-one-physical-family-out folds, 23 causal features, support, and closed-loop U0 gates apply. Candidate times remain 80, 109, and 144. No tree expansion, boosting, neural network, reinforcement learning, or threshold sweep is permitted in this generation. Failure closes Q6.5 without method freeze.

