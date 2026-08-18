# Claim-Evidence Matrix

Last updated: 2026-08-13. “Supported” is limited to the named evidence and must not be generalized beyond its protocol.

| Claim | Evidence | Status | Boundary |
|---|---|---|---|
| C1: Commands improve short-horizon trajectory prediction. | Frozen M2 Webots ADE experiment: State-only stable ADE `0.000120561 m` at 0.5 s and `0.000715992 m` at 2.0 s; Command-conditioned `0.000006398 m` and `0.000013655 m`. | Supported | Dedicated simulation validation episodes; not itself danger or safety evidence. |
| C2: Predicted future motion improves future-danger estimation over current-state-only risk. | M9-A Formal descriptive R1-R0 AUPRC delta `0.087177`, CI `[0.071217, 0.108246]`. | Unsupported / insufficient support | F6 has 3 near misses versus the frozen minimum of 4; the numerical contrast cannot override the support gate. |
| C3: Command-conditioned prediction improves future-danger estimation over state-only prediction. | M9-A Formal descriptive R2-R1 AUPRC delta `0.002950`, CI `[0.002383, 0.003610]`. | Unsupported / insufficient support | F6 support fails, and the descriptive delta is also below the frozen `0.05` practical floor. |
| C4: Risk-aware visual communication reduces communication cost while preserving task-relevant information. | M5 provides byte-fair offline image-quality evidence; M6 has a null TCOBR contrast; M7 v1/v2 are `NO-GO`; M8 proxies are unqualified. | Partial/enabling with negative evidence | Do not mark generally supported. No accepted task-utility preservation result spans the claim. |
| C5: Risk-aware communication improves closed-loop navigation safety under constrained communication. | None. | Unsupported | Collision rate, navigation success, and closed-loop safety have not been evaluated. |
| C6: Benefits generalize across environments and communication conditions. | None sufficient. | Unsupported | Existing simulation scenarios and offline budgets do not establish generalization. |

M9-A-P changes no claim status. It preregisters how C2 and C3 will be tested and preserves every null, adverse, undefined, and insufficient-support outcome.
