"""Locked M9-B analysis definitions. Importing this module never reads Formal."""
from __future__ import annotations
import numpy as np
from sklearn.metrics import average_precision_score
BOOTSTRAP_REPLICATES=10000;BOOTSTRAP_SEED=20261001;EFFECT_FLOOR=.05
def family_macro_auprc(episodes,method):
 vals=[]
 for f in [f"F{i}" for i in range(1,8)]:
  q=[s for e in episodes if e["family"]==f for s in e["samples"]]
  if q and any(x["danger"] for x in q):vals.append(average_precision_score([x["danger"] for x in q],[x[method] for x in q]))
 return float(np.mean(vals)) if vals else float("nan")
def primary_decision(delta,lower,support):return "PASS" if support and delta>=EFFECT_FLOOR and lower>0 else ("insufficient_support" if not support else "FAIL")
