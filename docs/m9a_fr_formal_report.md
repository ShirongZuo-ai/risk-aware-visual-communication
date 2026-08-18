# M9-A-FR formal report

The 144-episode study executed completely, but the frozen primary support gate failed: F6 contains three near-miss episodes and required at least four. C2 and C3 are therefore `insufficient_support`; descriptive estimates cannot override that decision.

## Frozen readiness and methods

The manifest contains 144 unique identities and `93xxxx` seeds. Physical radius is `0.037 m`; Calibration selected `d_near=0.013 m`. R0 is negative current physical clearance. R1 and R2 apply the frozen M2 state-only and command-conditioned predictors respectively, followed by identical physical-clearance geometry. Historical M3 radius `0.037592257 m` is structurally separate and supplementary.

AUPRC uses scikit-learn 1.7.2 `average_precision_score`. Inference uses 10,000 paired episode resamples within family, NumPy PCG64 seed `20260901`, percentile intervals, and equal family macro-weight. Calibration-only warning selection used three-step debounce, 0.5 s refractory interval, and the maximum detection rule under 0.5 false warnings/min. All methods selected `-0.015799853527419652`, Calibration detection 1.0, and zero false warnings/min.

## Results

Composition was 42 collision, 39 near-miss, and 63 safe. F1-F5/F7 each had 6/6/6; F6 had 6/3/9; F8 had 18 safe controls.

Primary 2.0 s AUPRC was R0 `0.9098727284`, R1 `0.9970495943`, and R2 `1.0000000000`. C2 was `0.0871768659`, 95% CI `[0.0712174604, 0.1082460053]`. C3 was `0.0029504057`, CI `[0.0023834361, 0.0036095984]`. Both are `insufficient_support`; C3 also misses the `0.05` floor.

Supplementary R0/R1/R2 AUPRC was `0.979867/1.000000/0.999996` at 0.5 s and `0.944528/0.998489/0.999839` at 1.0 s. At 2.0 s, physical-clearance MAE was `0.019735/0.003114/0.001915 m`; Spearman was `0.915033/0.992603/0.998409`.

The M2 command-conditioned ADE gain improves clearance fidelity, but adds only a tiny danger-ranking gain over an already near-perfect R1. The paper can report this rigorous qualified/negative result, but cannot claim confirmatory C2/C3 support or downstream safety.

## Integrity and claims

Formal access transitioned `sealed -> authorized_once` before generation. A post-generation analyzer boundary repair clamped floating-point schedule residue and rejected genuinely incomplete future command coverage; it changed no simulator output or frozen scientific definition.

C1 remains supported by M2. C2/C3 are unsupported due to insufficient support. C4 retains M5-M8 partial/negative evidence. C5/C6 remain unsupported.

## Reproduction

```powershell
python -m pytest tests/test_m9a_formal_analysis.py tests/test_m9a_i1.py tests/test_m9a_contact_semantics.py -q
python -m scripts.m9a_formal_workflow prepare
python -m scripts.m9a_formal_workflow authorize
python -m scripts.m9a_formal_workflow generate
python -m scripts.m9a_formal_workflow analyze
```

Authorization is one-shot. Generation reproduction requires a fresh sealed copy and independently authorized ledger.
