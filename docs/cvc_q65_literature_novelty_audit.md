# Literature and novelty audit for the Q6.5 terminal result

Search cutoff: 2026-08-18. Claims are deliberately bounded; no “first” claim is recommended.

| Work | Communication decision / endpoint | Relation and distinction |
|---|---|---|
| When2com (CVPR 2020) | learned who/when graph for multi-agent perception | Establishes selective communication; does not isolate one packet's counterfactual physical safety value. |
| V2VNet (ECCV 2020) | compressed features for detection and forecasting | Couples communication and motion forecasting, but not matched visual SEND/HOLD utility. |
| Predictive attention (CoRL 2020) | predicted visual attention for unsafe-condition detection/control | Predictive-attention antecedent; internal processing rather than serialized packet opportunity cost. |
| Where2comm (NeurIPS 2022) | confidence-selected spatial features for 3-D detection | Spatial task allocation driven by confidence, not marginal closed-loop safety utility. |
| TAGIC (INFOCOM Workshops 2024) | task-guided image coding for CARLA teleoperation | Strong visual-communication neighbor; no paired SEND-now/HOLD physical intervention at identical episode bytes. |
| VIS-SemCom / Direct-CP (2024) | semantic-object or direction-aware collaborative features | Task-aware selection, but no ego-risk-conditioned packet utility with navigation outcomes. |
| RAST | predicted dynamic maps and risk corridors for planning | Risk-corridor antecedent; no communication decision. |
| Value-/Age-of-Information scheduling | state-dependent update value and freshness | Standard conceptual basis for opportunity cost. This work does not claim to invent VoI; it supplies a visual robot intervention separating danger, decision relevance, and physical packet value. |
| Communication-aware robotics review | joint motion, connectivity, power, and energy | Makes broad “first risk-aware communication” claims untenable. |
| Predictive latent communication-aware UAV control (2026 preprint) | latent rollouts adapt motion and transmit power | Closest high-level threat; allocates link power/trajectory rather than matched-byte visual packet timing. |

## Defensible positioning

Task-oriented communication, event-triggered updates, VoI/AoI, predictive attention, risk-aware planning, feature selection, and communication-aware control are standard antecedents.

The narrow supported contribution is:

> We experimentally separate predicted ego danger, received-image decision relevance, and the marginal physical safety utility of spending one fixed-cost visual packet. Deterministic matched-byte SEND/HOLD replay shows that packet utility can be positive, harmful, or neutral and can reverse across adjacent opportunities; bounded causal models did not generalize safely enough to select a scheduler.

The stronger claim that risk/decision-value scheduling improves navigation over matched U0 is not supported. Any final related-work table should compare allocation unit, causal information, finite-budget semantics, physical counterfactual, exact serialized cost, closed-loop endpoint, and independent validation.
